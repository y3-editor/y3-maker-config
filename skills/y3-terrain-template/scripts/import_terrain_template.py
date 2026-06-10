#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Import a terrain template into a target Y3 map.

This script handles the *file-bridge* portion of the import:
  - Validates the template (8 map files + editor_decoration.zip).
  - Backs up the target map's affected files.
  - Overwrites the 8 map-bridge files in the target map.
  - Emits the absolute path of ``editor_decoration.zip`` in stdout so the
    Skill can hand it to MCP ``y3editor.import_object_editor``.

The Skill (NOT this script) is responsible for:
  - MCP ``save_editor`` (BEFORE this script).
  - MCP ``resize_terrain`` (BEFORE this script).
  - MCP ``restart_editor`` (AFTER this script — to load new terrain).
  - MCP ``import_object_editor`` with ``decoration_zip`` (AFTER restart).

Usage:
    python import_terrain_template.py \\
        --template       "<template-name>" \\
        --target-map-dir "<y3-project>/maps/<level>" \\
        [--apply]            # default: dry-run; must pass to actually write
        [--no-backup]        # default: backup target's affected entries
        [--ignore-version]   # allow editor_version mismatch

stdout (success / dry-run / error):
    {
      "status": "ok" | "dry-run" | "error",
      "files": [...],                   # 8 map-bridge files to overwrite
      "decoration_zip": "<abs path>",   # template's editor_decoration.zip
      "backup_dir": "<absolute path or null>",
      "warnings": [...],                # optional
      "reason":   "..."                 # only when status == "error"
    }

If import fails AFTER backup was created, the stdout payload still contains
``backup_dir`` so the user can recover manually.
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import traceback

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common  # noqa: E402

_SKILL_ROOT = os.path.dirname(_HERE)
_LIBRARY_ROOT = os.path.join(_SKILL_ROOT, "library")
_BACKUP_ROOT_NAME = ".terrain_template_backup"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="import_terrain_template",
        description="Import a terrain template into a target Y3 map",
    )
    p.add_argument("--template", required=True,
                   help="Template name in library/<template>/")
    p.add_argument("--target-map-dir", required=True,
                   help="Target Y3 map directory (e.g., <project>/maps/EntryMap)")
    p.add_argument("--apply", action="store_true",
                   help="Actually write files. Without this flag, runs in dry-run mode.")
    p.add_argument("--no-backup", action="store_true",
                   help="Skip the safety backup of target's affected entries (NOT recommended)")
    p.add_argument("--ignore-version", action="store_true",
                   help="Allow editor_version mismatch between template and target project")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# Validation steps
# ---------------------------------------------------------------------------

def _resolve_template_dir(name: str) -> str:
    _common.validate_kebab_case(name)
    template_dir = os.path.join(_LIBRARY_ROOT, name)
    if not os.path.isdir(template_dir):
        raise ValueError(f"template not found in library: {template_dir}")
    return template_dir


def _check_template_complete(template_dir: str) -> None:
    missing = _common.find_missing_template_entries(template_dir)
    if missing:
        raise ValueError(
            "missing required entries in template: " + ", ".join(missing)
        )
    polluted = _common.find_forbidden_files(template_dir)
    if polluted:
        raise ValueError(
            "template polluted: contains forbidden files "
            + ", ".join(polluted)
        )


def _load_meta(template_dir: str) -> dict:
    meta_path = os.path.join(template_dir, "template_meta.json")
    if not os.path.isfile(meta_path):
        raise ValueError(f"template_meta.json missing: {meta_path}")
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"template_meta.json is not valid JSON: {e}") from e
    if not isinstance(meta, dict):
        raise ValueError("template_meta.json root must be an object")

    required = ("name", "size", "editor_version")
    missing = [k for k in required if k not in meta]
    if missing:
        raise ValueError(
            "template_meta.json missing required fields: " + ", ".join(missing)
        )

    size = meta["size"]
    if (not isinstance(size, list) or len(size) != 2
            or not all(isinstance(x, int) and x > 0 for x in size)):
        raise ValueError(
            "template_meta.json `size` must be [width:int>0, height:int>0]"
        )
    return meta


def _check_target_map_dir(target_map_dir: str) -> None:
    if not os.path.isdir(target_map_dir):
        raise ValueError(f"--target-map-dir is not a directory: {target_map_dir}")


def _resolve_project_root(map_dir: str) -> str:
    map_dir = os.path.abspath(map_dir)
    parent = os.path.dirname(map_dir)
    if os.path.basename(parent).lower() == "maps":
        return os.path.dirname(parent)
    return parent


def _check_editor_version(meta: dict, target_map_dir: str,
                          ignore: bool, warnings: list[str]) -> None:
    template_ver = str(meta.get("editor_version", "unknown"))
    project_root = _resolve_project_root(target_map_dir)
    target_ver = _common.read_editor_version(project_root)
    if template_ver == target_ver:
        return
    msg = (f"editor version mismatch: template={template_ver!r} "
           f"target={target_ver!r}")
    if ignore:
        warnings.append(msg + " (ignored via --ignore-version)")
        return
    raise ValueError(msg + " (use --ignore-version to override)")


# ---------------------------------------------------------------------------
# Backup & overwrite (8 map-bridge files only; decoration zip handled by MCP)
# ---------------------------------------------------------------------------

def _make_backup_dir(target_map_dir: str) -> str:
    ts = datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    backup_dir = os.path.join(target_map_dir, _BACKUP_ROOT_NAME, ts)
    os.makedirs(backup_dir, exist_ok=False)
    return backup_dir


def _backup_existing(target_map_dir: str, backup_dir: str) -> None:
    """Copy each existing map-bridge file from target into backup_dir.

    Missing entries on target are silently skipped (we still want to be able
    to import into a partially-populated map).
    """
    for rel in _common.iter_map_bridge_files():
        src = os.path.join(target_map_dir, rel)
        if os.path.isfile(src):
            _common.copy_file_keep_rel(target_map_dir, backup_dir, rel)


def _overwrite_with_template(template_dir: str, target_map_dir: str) -> None:
    for rel in _common.iter_map_bridge_files():
        _common.copy_file_keep_rel(template_dir, target_map_dir, rel)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def _collect_manifest_lists() -> list[str]:
    return list(_common.TEMPLATE_FILES)


def _run(args: argparse.Namespace) -> dict:
    warnings: list[str] = []
    backup_dir: str | None = None

    template_dir = _resolve_template_dir(args.template)
    _check_template_complete(template_dir)
    meta = _load_meta(template_dir)
    _check_target_map_dir(args.target_map_dir)
    _check_editor_version(meta, args.target_map_dir,
                          args.ignore_version, warnings)

    files = _collect_manifest_lists()
    decoration_zip = os.path.abspath(
        os.path.join(template_dir, _common.TEMPLATE_DECORATION_ZIP)
    )

    if not args.apply:
        return {
            "status": "dry-run",
            "files": files,
            "decoration_zip": decoration_zip,
            "backup_dir": None,
            "warnings": warnings,
        }

    # apply mode -------------------------------------------------------------
    try:
        if not args.no_backup:
            backup_dir = _make_backup_dir(args.target_map_dir)
            _backup_existing(args.target_map_dir, backup_dir)
        _overwrite_with_template(template_dir, args.target_map_dir)
    except BaseException as e:
        # Re-raise as RuntimeError carrying backup_dir so main() can include it
        # in the error payload.
        err = RuntimeError(str(e) or e.__class__.__name__)
        err.backup_dir = backup_dir  # type: ignore[attr-defined]
        err.decoration_zip = decoration_zip  # type: ignore[attr-defined]
        raise err from e

    return {
        "status": "ok",
        "files": files,
        "decoration_zip": decoration_zip,
        "backup_dir": backup_dir,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    backup_dir_for_error: str | None = None
    decoration_zip_for_error: str | None = None
    try:
        args = _parse_args(argv if argv is not None else sys.argv[1:])
        payload = _run(args)
        _common.emit_json(payload, status_code=0)
    except SystemExit:
        raise
    except BaseException as e:
        # If the failure happened mid-apply, surface backup_dir & decoration_zip.
        backup_dir_for_error = getattr(e, "backup_dir", None)
        decoration_zip_for_error = getattr(e, "decoration_zip", None)
        reason = str(e) or e.__class__.__name__
        _common.emit_json(
            {
                "status": "error",
                "reason": reason,
                "files": [],
                "decoration_zip": decoration_zip_for_error,
                "backup_dir": backup_dir_for_error,
                "trace": traceback.format_exc().splitlines()[-1],
            },
            status_code=1,
        )


if __name__ == "__main__":
    main()
