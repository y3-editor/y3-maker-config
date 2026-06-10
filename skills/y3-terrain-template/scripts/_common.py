"""
Shared utilities for the y3-terrain-template skill scripts.

This module is the *single source of truth* for the 10-entry template manifest
and the helper functions consumed by both export_terrain_template.py and
import_terrain_template.py.

Authority chain:
    spec Requirement 2  ->  references/file_manifest.md  ->  this module
Any change to the manifest must be propagated through all three.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
from typing import Iterable, Optional, Tuple

# ---------------------------------------------------------------------------
# Manifest constants (spec Requirement 2)
# ---------------------------------------------------------------------------
#
# A template now contains exactly two kinds of artifacts:
#   1) 8 plain map files copied verbatim between source-map / template / target-map.
#   2) 1 object-editor bundle (``editor_decoration.zip``) that is produced via
#      MCP ``export_object_editor`` and re-applied via MCP ``import_object_editor``.
#      The Skill (NOT this Python layer) is responsible for those MCP calls.

# 8 plain files at the map root (file-copy bridge)
TEMPLATE_FILES: Tuple[str, ...] = (
    "terrain.json",
    "texture.json",
    "terrainedit.json",
    "foliage.json",
    "texturefoliage.json",
    "decorationdata.data",
    "resourceobjectdata.data",
    "grid.data",
)

# 1 object-editor bundle, lives ONLY at the template root (never inside a Y3 map).
# Produced by MCP ``export_object_editor`` and consumed by MCP ``import_object_editor``.
TEMPLATE_DECORATION_ZIP: str = "editor_decoration.zip"

# Files that MUST NOT appear in a template directory.
# If detected during import, the script must abort with "template polluted".
FORBIDDEN_FILES: Tuple[str, ...] = (
    "logicres.json",
    "navimap.data",
    "engineeffectdata.json",
    "envtime.json",
    "todtemplate.json",
    "projectile.json",
    "decal.json",
)


# ---------------------------------------------------------------------------
# Naming validation (spec Requirement 3)
# ---------------------------------------------------------------------------

_KEBAB_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def validate_kebab_case(name: str) -> None:
    """Raise ValueError if *name* is not a valid kebab-case template name.

    Rules: lowercase letters, digits, hyphens; must start with a letter;
    length 1-64.
    """
    if not isinstance(name, str) or not name:
        raise ValueError("template name must be a non-empty string")
    if len(name) > 64:
        raise ValueError(f"template name too long ({len(name)} > 64)")
    if not _KEBAB_RE.match(name):
        raise ValueError(
            "template name must be kebab-case "
            "(lowercase letters/digits/hyphens, must start with a letter): "
            f"got {name!r}"
        )


# ---------------------------------------------------------------------------
# terrain.json size parsing (resolves OQ1)
# ---------------------------------------------------------------------------

# Multiple Y3 editor versions have used different field names for map size.
# Each candidate is a (width_key, height_key) pair tried in order.
_SIZE_KEY_CANDIDATES = (
    ("width", "height"),
    ("mapWidth", "mapHeight"),
    ("map_width", "map_height"),
    ("size_x", "size_y"),
    ("sizeX", "sizeY"),
    ("w", "h"),
)

# Some Y3 versions nest the size under a parent dict
_SIZE_NESTED_PARENTS = ("size", "mapSize", "map_size", "terrain", "header")


def _extract_size_from_dict(data: dict) -> Optional[Tuple[int, int]]:
    # Try flat keys at this level
    for w_key, h_key in _SIZE_KEY_CANDIDATES:
        if w_key in data and h_key in data:
            try:
                w = int(data[w_key])
                h = int(data[h_key])
                if w > 0 and h > 0:
                    return (w, h)
            except (TypeError, ValueError):
                continue
    # Try [w, h] / [w, h, ...] arrays under common parent names
    for parent in _SIZE_NESTED_PARENTS:
        child = data.get(parent)
        if isinstance(child, dict):
            nested = _extract_size_from_dict(child)
            if nested is not None:
                return nested
        if isinstance(child, (list, tuple)) and len(child) >= 2:
            try:
                w, h = int(child[0]), int(child[1])
                if w > 0 and h > 0:
                    return (w, h)
            except (TypeError, ValueError):
                pass
    return None


def read_terrain_size(map_dir: str) -> Tuple[int, int]:
    """Return ``(width, height)`` parsed from ``<map_dir>/terrain.json``.

    Y3 ships ``terrain.json`` as a **binary** file whose first 8 bytes are two
    little-endian unsigned 32-bit integers: ``width`` followed by ``height``.
    We try the binary layout first because that matches the production editor
    (v250804). As a fallback, if the file happens to be valid UTF-8 JSON (rare,
    legacy or third-party tooling), we try the JSON key strategies below.

    Raises:
        FileNotFoundError: if terrain.json is missing.
        ValueError: if neither format yields a plausible size.
    """
    path = os.path.join(map_dir, "terrain.json")
    if not os.path.isfile(path):
        raise FileNotFoundError(f"terrain.json not found at {path}")

    # 1) Primary: Y3 binary header (two little-endian uint32)
    try:
        with open(path, "rb") as f:
            head = f.read(8)
        if len(head) == 8:
            import struct
            w, h = struct.unpack("<II", head)
            if 0 < w <= 4096 and 0 < h <= 4096:
                return (int(w), int(h))
    except OSError as e:
        raise ValueError(f"failed to read terrain.json: {e}") from e

    # 2) Fallback: UTF-8 JSON (legacy / third-party)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (UnicodeDecodeError, json.JSONDecodeError):
        data = None

    if isinstance(data, dict):
        size = _extract_size_from_dict(data)
        if size is not None:
            return size

    candidates = ", ".join(f"{w}/{h}" for w, h in _SIZE_KEY_CANDIDATES)
    raise ValueError(
        "terrain size unknown: binary header did not yield a plausible "
        f"(width, height) in (0, 4096]; JSON fallback tried keys [{candidates}] "
        f"and nested parents {_SIZE_NESTED_PARENTS}; "
        "extend _common.read_terrain_size to support this Y3 version"
    )


# ---------------------------------------------------------------------------
# Editor version detection
# ---------------------------------------------------------------------------

# Common locations where the Y3 editor records the project version.
_VERSION_CANDIDATES = (
    "project.json",
    "y3_project.json",
    "EditorMap.json",
)
_VERSION_KEYS = ("editor_version", "editorVersion", "version", "engine_version")


def read_editor_version(project_root: str) -> str:
    """Best-effort read of the editor version from a Y3 project root.

    Returns the literal string ``"unknown"`` (NOT None) when no version can
    be found, so downstream code can serialize it directly.
    """
    if not project_root or not os.path.isdir(project_root):
        return "unknown"
    for candidate in _VERSION_CANDIDATES:
        path = os.path.join(project_root, candidate)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        if not isinstance(data, dict):
            continue
        for key in _VERSION_KEYS:
            if key in data and isinstance(data[key], (str, int, float)):
                return str(data[key])
    return "unknown"


# ---------------------------------------------------------------------------
# JSON I/O protocol for stdout
# ---------------------------------------------------------------------------

def emit_json(payload: dict, status_code: int = 0) -> None:
    """Print *payload* as a single JSON line to stdout and exit.

    Always exits the process. ``status_code`` should be 0 on success and
    non-zero on failure. The payload is written even on error so the Skill
    layer can parse a structured reason / backup_dir.
    """
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    sys.exit(status_code)


# ---------------------------------------------------------------------------
# File / directory copy helpers (preserve relative paths)
# ---------------------------------------------------------------------------

def copy_file_keep_rel(src_root: str, dst_root: str, rel_path: str) -> None:
    """Copy ``<src_root>/<rel_path>`` to ``<dst_root>/<rel_path>``.

    Creates intermediate directories as needed. Raises FileNotFoundError if
    the source file does not exist.
    """
    src = os.path.join(src_root, rel_path)
    dst = os.path.join(dst_root, rel_path)
    if not os.path.isfile(src):
        raise FileNotFoundError(f"source file not found: {src}")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)


def copy_dir_recursive(src_dir: str, dst_dir: str) -> None:
    """Recursively copy *src_dir* into *dst_dir* (overwriting on conflict).

    Uses ``shutil.copytree`` with ``dirs_exist_ok=True`` (Py3.8+). Raises
    FileNotFoundError if *src_dir* is missing or not a directory.
    """
    if not os.path.isdir(src_dir):
        raise FileNotFoundError(f"source directory not found: {src_dir}")
    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)


# ---------------------------------------------------------------------------
# Manifest checks shared by export & import
# ---------------------------------------------------------------------------

def find_missing_map_entries(map_root: str) -> list[str]:
    """Return the list of relative paths from the 8 map-bridge files that are
    NOT present at *map_root*. Empty list means everything is present.

    Used to validate both the source map (during export) and the target map's
    pre-state (when applicable). The decoration zip is NOT checked here because
    it is an MCP artifact that does not live inside Y3 maps.
    """
    missing: list[str] = []
    for rel in TEMPLATE_FILES:
        if not os.path.isfile(os.path.join(map_root, rel)):
            missing.append(rel)
    return missing


def find_missing_template_entries(template_root: str) -> list[str]:
    """Return missing entries inside a *template* directory.

    A complete template MUST contain the 8 map-bridge files plus the
    ``editor_decoration.zip`` produced by MCP ``export_object_editor``.
    """
    missing = find_missing_map_entries(template_root)
    if not os.path.isfile(os.path.join(template_root, TEMPLATE_DECORATION_ZIP)):
        missing.append(TEMPLATE_DECORATION_ZIP)
    return missing


# Backward-compatible alias for any external caller. Prefer the explicit
# helpers above in new code.
def find_missing_entries(root: str) -> list[str]:
    """Deprecated: use find_missing_map_entries / find_missing_template_entries."""
    return find_missing_map_entries(root)


def find_forbidden_files(template_root: str) -> list[str]:
    """Return any forbidden files found at the template root level.

    A non-empty result means the template is polluted and import must abort.
    """
    return [
        name
        for name in FORBIDDEN_FILES
        if os.path.isfile(os.path.join(template_root, name))
    ]


def iter_map_bridge_files() -> Iterable[str]:
    """Yield every map-bridge file relative path (8 files).

    Convenience iterator for callers that copy these files between
    source map / template / target map.
    """
    for rel in TEMPLATE_FILES:
        yield rel
