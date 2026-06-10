#!/usr/bin/env python3
"""
Export a Y3 map's terrain art layer into the local template library.

A complete template now contains:
  - 8 plain map files copied verbatim from the source map.
  - 1 ``editor_decoration.zip`` produced by MCP ``export_object_editor``
    (BEFORE invoking this script). The Skill is responsible for the MCP call;
    this script only takes the resulting zip path via ``--decoration-zip``.

Usage:
    python export_terrain_template.py \\
        --map-dir         "<y3-project>/maps/<level>" \\
        --name            "<kebab-case-name>" \\
        --description     "<human readable description>" \\
        --decoration-zip  "<absolute path to editor_decoration.zip>" \\
        [--force]

stdout (success):
    {"status":"ok","name":..,"size":[w,h],"path":..,"file_count":N}

stdout (failure):
    {"status":"error","reason":"..."}
    (exit code != 0; partial template directory is automatically cleaned up)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import sys
import traceback
import zipfile

# Make sibling _common.py importable regardless of CWD
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common  # noqa: E402

# Library root: <skill_root>/library/
_SKILL_ROOT = os.path.dirname(_HERE)
_LIBRARY_ROOT = os.path.join(_SKILL_ROOT, "library")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="export_terrain_template",
        description="Export Y3 map terrain art layer to the template library",
    )
    p.add_argument("--map-dir", required=True,
                   help="Source Y3 map directory (e.g., <project>/maps/EntryMap)")
    p.add_argument("--name", required=True,
                   help="Template name in kebab-case")
    p.add_argument("--description", required=True,
                   help="Human-readable template description (written to readme.md)")
    p.add_argument("--decoration-zip", required=True,
                   help=("Absolute path to editor_decoration.zip pre-produced by "
                         "MCP y3editor.export_object_editor (object_types=['editor_decoration']). "
                         "The Skill must invoke that MCP BEFORE running this script."))
    p.add_argument("--force", action="store_true",
                   help="Overwrite an existing template with the same name")
    return p.parse_args(argv)


# ---------------------------------------------------------------------------
# readme.md template
# ---------------------------------------------------------------------------

_README_TEMPLATE = """# {name}

## 模板名

`{name}`

## 地图尺寸

{w} × {h}

## 模板说明

{description}

## 源关卡

`{source_map}`

## 导出时间

{exported_at}

## 包含文件清单

{files_block}

## 说明

- 8 个 `.json` / `.data` 文件（地形 / 纹理 / 植被 / 装饰物布局 / 资源摆件 / 碰撞）走文件直拷
- `editor_decoration.zip` 由 MCP `export_object_editor` 产出，导入时由 MCP `import_object_editor` 应用

## 导入风险提示

装饰物 / 资源摆件将被整体覆盖；如目标关卡有针对装饰物 ID 的脚本引用，导入后引用将失效。建议导入前 `git commit` 当前关卡。
"""


def _format_files_block(files: list[str]) -> str:
    return "\n".join(f"- `{f}`" for f in files)


# ---------------------------------------------------------------------------
# Core export logic
# ---------------------------------------------------------------------------

def _validate_inputs(args: argparse.Namespace) -> None:
    if not os.path.isdir(args.map_dir):
        raise ValueError(f"--map-dir is not a directory: {args.map_dir}")
    _common.validate_kebab_case(args.name)
    if not os.path.isfile(args.decoration_zip):
        raise ValueError(
            f"--decoration-zip not found: {args.decoration_zip} "
            "(produce it first via MCP y3editor.export_object_editor)"
        )
    # Sanity-check the zip is a real zip archive.
    if not zipfile.is_zipfile(args.decoration_zip):
        raise ValueError(
            f"--decoration-zip is not a valid zip archive: {args.decoration_zip}"
        )


def _check_source_complete(map_dir: str) -> None:
    missing = _common.find_missing_map_entries(map_dir)
    if missing:
        raise ValueError(
            "missing required entries in source map: " + ", ".join(missing)
        )


def _prepare_template_dir(name: str, force: bool) -> str:
    template_dir = os.path.join(_LIBRARY_ROOT, name)
    if os.path.exists(template_dir):
        if not force:
            raise ValueError(
                f"template already exists: {template_dir} (use --force to overwrite)"
            )
        shutil.rmtree(template_dir)
    os.makedirs(template_dir, exist_ok=False)
    return template_dir


def _copy_map_files(src_root: str, dst_root: str) -> list[str]:
    """Copy the 8 map-bridge files from *src_root* to *dst_root*.

    Returns the list of relative paths actually copied.
    """
    copied: list[str] = []
    for rel in _common.iter_map_bridge_files():
        _common.copy_file_keep_rel(src_root, dst_root, rel)
        copied.append(rel)
    return copied


def _stage_decoration_zip(decoration_zip_src: str, template_dir: str) -> str:
    """Copy the MCP-produced decoration zip into the template directory.

    Returns the relative path written (always ``editor_decoration.zip``).
    """
    rel = _common.TEMPLATE_DECORATION_ZIP
    dst = os.path.join(template_dir, rel)
    shutil.copy2(decoration_zip_src, dst)
    return rel


def _write_meta(template_dir: str, *, name: str, description: str,
                size: tuple[int, int], source_map: str,
                editor_version: str,
                files: list[str]) -> dict:
    meta = {
        "name": name,
        "description": description,
        "size": [size[0], size[1]],
        "source_map": source_map,
        "exported_at": datetime.datetime.now(datetime.timezone.utc)
                       .isoformat(timespec="seconds"),
        "editor_version": editor_version,
        # Files actually packaged (flat list).
        "files": list(files),
        # Bundle layout descriptor — useful for forward compat / tooling.
        "decoration_bundle": _common.TEMPLATE_DECORATION_ZIP,
        "format_version": 2,
    }
    meta_path = os.path.join(template_dir, "template_meta.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return meta


def _write_readme(template_dir: str, meta: dict) -> None:
    readme_path = os.path.join(template_dir, "readme.md")
    body = _README_TEMPLATE.format(
        name=meta["name"],
        w=meta["size"][0],
        h=meta["size"][1],
        description=meta["description"],
        source_map=meta["source_map"],
        exported_at=meta["exported_at"],
        files_block=_format_files_block(meta["files"]),
    )
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(body)


def _resolve_project_root(map_dir: str) -> str:
    """Best-effort: ``<project>/maps/<level>`` -> ``<project>``.

    If the parent of map_dir is named "maps", return its grandparent. Otherwise
    fall back to the parent. Returned path is used only by
    ``read_editor_version`` which itself tolerates a wrong root.
    """
    map_dir = os.path.abspath(map_dir)
    parent = os.path.dirname(map_dir)
    if os.path.basename(parent).lower() == "maps":
        return os.path.dirname(parent)
    return parent


def _run(args: argparse.Namespace) -> dict:
    _validate_inputs(args)
    _check_source_complete(args.map_dir)
    size = _common.read_terrain_size(args.map_dir)
    project_root = _resolve_project_root(args.map_dir)
    editor_version = _common.read_editor_version(project_root)

    template_dir = _prepare_template_dir(args.name, args.force)
    try:
        files = _copy_map_files(args.map_dir, template_dir)
        zip_rel = _stage_decoration_zip(args.decoration_zip, template_dir)
        files.append(zip_rel)
        meta = _write_meta(
            template_dir,
            name=args.name,
            description=args.description,
            size=size,
            source_map=os.path.basename(os.path.normpath(args.map_dir)),
            editor_version=editor_version,
            files=files,
        )
        _write_readme(template_dir, meta)
    except BaseException:
        # Cleanup the half-written template
        shutil.rmtree(template_dir, ignore_errors=True)
        raise

    return {
        "status": "ok",
        "name": args.name,
        "size": [size[0], size[1]],
        "path": template_dir,
        "file_count": len(meta["files"]),
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    try:
        args = _parse_args(argv if argv is not None else sys.argv[1:])
        payload = _run(args)
        _common.emit_json(payload, status_code=0)
    except SystemExit:
        raise
    except BaseException as e:
        reason = str(e) or e.__class__.__name__
        _common.emit_json(
            {"status": "error", "reason": reason,
             "trace": traceback.format_exc().splitlines()[-1]},
            status_code=1,
        )


if __name__ == "__main__":
    main()
