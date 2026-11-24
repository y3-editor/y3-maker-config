#!/usr/bin/env python3
"""Unit tests for sync_lualib_docs.py."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SYNC_DIR = Path(__file__).resolve().parent
REPO_ROOT = SYNC_DIR.parents[1]
if str(SYNC_DIR) not in sys.path:
    sys.path.insert(0, str(SYNC_DIR))

import sync_lualib_docs as sld  # noqa: E402


class SyncLualibDocsTests(unittest.TestCase):
    def _setup_workspace(self, tmp: Path) -> tuple[Path, Path, Path]:
        src = tmp / "y3-maker-config"
        dst = tmp / "y3-lualib"
        manifest_path = tmp / "manifest.json"

        (dst / "game").mkdir(parents=True)
        (dst / "game" / "const.lua").write_text("return {}\n", encoding="utf-8")
        (dst / "doc" / "skills" / "y3-lib").mkdir(parents=True)
        (dst / "doc" / "API.md").write_text("# API\n", encoding="utf-8")
        (dst / "doc" / "Lua虚拟机.md").write_text("# VM\n", encoding="utf-8")
        (dst / "doc" / "skills" / "y3-lib" / "SKILL.md").write_text("# y3-lib\n", encoding="utf-8")

        (src / "knowledge" / "核心系统").mkdir(parents=True)
        (src / "knowledge" / "物编系统").mkdir(parents=True)
        (src / "knowledge" / "UI系统").mkdir(parents=True)
        (src / "skills" / "y3-lua-pipeline" / "references").mkdir(parents=True)
        (src / "skills" / "eca-json-builder").mkdir(parents=True)
        (src / "skills" / "y3-obj-edit" / "reference").mkdir(parents=True)
        (src / "assets").mkdir(parents=True)

        (src / "skills" / "eca-json-builder" / "runtime_pitfalls.md").write_text(
            "# pitfalls\n", encoding="utf-8"
        )
        (src / "skills" / "y3-obj-edit" / "reference" / "unit.md").write_text(
            "# unit\n", encoding="utf-8"
        )
        (src / "assets" / "demo.png").write_bytes(b"png")

        (src / "knowledge" / "核心系统" / "02-属性计算公式.md").write_text(
            "# 属性计算公式\n", encoding="utf-8"
        )
        (src / "knowledge" / "核心系统" / "09-地形系统.md").write_text(
            "# 地形系统\n", encoding="utf-8"
        )
        (src / "knowledge" / "物编系统" / "06-技能.md").write_text("# 技能\n", encoding="utf-8")
        (src / "knowledge" / "物编系统" / "08-单位.md").write_text("# 单位\n", encoding="utf-8")
        (src / "knowledge" / "物编系统" / "09-建造系统.md").write_text(
            "# 建造系统\n\n- `物编系统/06-技能.md`\n- `物编系统/08-单位.md`\n",
            encoding="utf-8",
        )
        (src / "knowledge" / "UI系统" / "02-属性绑定.md").write_text(
            "# UI 属性绑定\n\n"
            "- 运行时：[maps/EntryMap/script/y3/game/const.lua](maps/EntryMap/script/y3/game/const.lua)\n"
            "- 地图产物：[maps/EntryMap/script/y3-helper/meta/playerAttrs.lua](maps/EntryMap/script/y3-helper/meta/playerAttrs.lua)\n",
            encoding="utf-8",
        )
        (src / "skills" / "y3-lua-pipeline" / "references" / "ui-events.md").write_text(
            "---\r\nname: ui-events\r\n---\r\n\r\n# Y3 UI 事件规范\r\n\r\n正文\r\n",
            encoding="utf-8",
        )
        (src / "skills" / "y3-lua-pipeline" / "references" / "mcp_safety.md").write_text(
            "# MCP Safety\n", encoding="utf-8"
        )

        manifest = {
            "source_repo": "y3-editor/y3-maker-config",
            "source_branch": "main",
            "target_subdir": "doc/guide",
            "groups": [
                {
                    "id": "core",
                    "title": "核心系统",
                    "description": "核心",
                    "source_dir": "knowledge/核心系统",
                    "target_dir": "core",
                    "exclude": ["02-属性计算公式.md"],
                },
                {
                    "id": "object",
                    "title": "物编系统",
                    "description": "物编",
                    "source_dir": "knowledge/物编系统",
                    "target_dir": "object",
                    "include": ["06-技能.md", "08-单位.md", "09-建造系统.md"],
                    "exclude": [],
                },
                {
                    "id": "ui",
                    "title": "UI 系统",
                    "description": "UI",
                    "source_dir": "knowledge/UI系统",
                    "target_dir": "ui",
                    "exclude": [],
                },
                {
                    "id": "api-notes",
                    "title": "API 规范",
                    "description": "API",
                    "source_dir": "skills/y3-lua-pipeline/references",
                    "target_dir": "api-notes",
                    "exclude": ["mcp_safety.md"],
                },
            ],
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return src, dst, manifest_path

    def _run_sync(self, src: Path, dst: Path, manifest_path: Path, *extra: str, sha: str = "11111112222222") -> int:
        return sld.main(
            [
                "--source",
                str(src),
                "--target",
                str(dst),
                "--manifest",
                str(manifest_path),
                "--source-sha",
                sha,
                *extra,
            ]
        )

    def test_frontmatter_strip_and_static_banner(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src, dst, manifest_path = self._setup_workspace(Path(td))
            self.assertEqual(self._run_sync(src, dst, manifest_path), 0)

            ui_events = (dst / "doc/guide/api-notes/ui-events.md").read_text(encoding="utf-8")
            self.assertNotIn("\r", ui_events)
            self.assertNotIn("name: ui-events", ui_events)
            self.assertIn("> 本文档自动同步自 [y3-maker-config]", ui_events)
            self.assertNotIn("1111111", ui_events)

    def test_markdown_and_backtick_link_rewrites(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src, dst, manifest_path = self._setup_workspace(Path(td))
            (src / "knowledge/核心系统/09-地形系统.md").write_text(
                "# 地形系统\n\n"
                "- `<agent>/skills/eca-json-builder/`\n"
                "- `skills/y3-obj-edit/reference/unit.md`\n"
                "- `../../skills/eca-json-builder/runtime_pitfalls.md`\n"
                "- [`unit.md`](../../skills/y3-obj-edit/reference/unit.md)\n"
                "- [公式](./02-属性计算公式.md#节1)\n",
                encoding="utf-8",
            )
            (src / "knowledge/核心系统/14-坐标与单位口径.md").write_text(
                "# 坐标口径\n\n> `knowledge/核心系统/09-地形系统.md`\n",
                encoding="utf-8",
            )
            self.assertEqual(self._run_sync(src, dst, manifest_path), 0)

            terrain = (dst / "doc/guide/core/09-地形系统.md").read_text(encoding="utf-8")
            self.assertIn(
                "[`skills/eca-json-builder/`](https://github.com/y3-editor/y3-maker-config/tree/main/skills/eca-json-builder)",
                terrain,
            )
            self.assertIn(
                "[`skills/y3-obj-edit/reference/unit.md`](https://github.com/y3-editor/y3-maker-config/blob/main/skills/y3-obj-edit/reference/unit.md)",
                terrain,
            )
            self.assertIn(
                "[`skills/eca-json-builder/runtime_pitfalls.md`](https://github.com/y3-editor/y3-maker-config/blob/main/skills/eca-json-builder/runtime_pitfalls.md)",
                terrain,
            )
            self.assertIn(
                "[`unit.md`](https://github.com/y3-editor/y3-maker-config/blob/main/skills/y3-obj-edit/reference/unit.md)",
                terrain,
            )
            self.assertNotIn("[[`", terrain)
            self.assertIn(
                "[公式](https://github.com/y3-editor/y3-maker-config/blob/main/knowledge/%E6%A0%B8%E5%BF%83%E7%B3%BB%E7%BB%9F/02-%E5%B1%9E%E6%80%A7%E8%AE%A1%E7%AE%97%E5%85%AC%E5%BC%8F.md#节1)",
                terrain,
            )

            coord = (dst / "doc/guide/core/14-坐标与单位口径.md").read_text(encoding="utf-8")
            self.assertIn("[`09-地形系统.md`](./09-地形系统.md)", coord)

            build = (dst / "doc/guide/object/09-建造系统.md").read_text(encoding="utf-8")
            self.assertIn("[`06-技能.md`](./06-技能.md)", build)
            self.assertIn("[`08-单位.md`](./08-单位.md)", build)

            bind = (dst / "doc/guide/ui/02-属性绑定.md").read_text(encoding="utf-8")
            self.assertIn("[maps/EntryMap/script/y3/game/const.lua](../../../game/const.lua)", bind)
            self.assertIn("`maps/EntryMap/script/y3-helper/meta/playerAttrs.lua`", bind)

    def test_image_link_rewrites(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src, dst, manifest_path = self._setup_workspace(Path(td))
            (src / "knowledge/核心系统/09-地形系统.md").write_text(
                "# 地形系统\n\n![本地图](../../assets/demo.png)\n![外链](https://example.com/a.png)\n",
                encoding="utf-8",
            )
            self.assertEqual(self._run_sync(src, dst, manifest_path), 0)
            terrain = (dst / "doc/guide/core/09-地形系统.md").read_text(encoding="utf-8")
            self.assertIn(
                "![本地图](https://raw.githubusercontent.com/y3-editor/y3-maker-config/main/assets/demo.png)",
                terrain,
            )
            self.assertIn("![外链](https://example.com/a.png)", terrain)

    def test_fenced_code_preserves_links_but_blocks_forbidden_markers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src, dst, manifest_path = self._setup_workspace(Path(td))
            (src / "knowledge/核心系统/09-地形系统.md").write_text(
                "# 地形系统\n\n"
                "```markdown\n[假链接](./missing.md) `skills/y3-obj-edit/reference/unit.md`\n```\n\n"
                "> ```markdown\n> [引用代码块内假链接](./missing.md)\n> ```\n\n"
                "双反引号包含 `` `not-a-repo-path` `` 不被单反引号截断，且含链接 `` `[x](./missing.md)` `` 保持原样。\n",
                encoding="utf-8",
            )
            self.assertEqual(self._run_sync(src, dst, manifest_path), 0)
            terrain = (dst / "doc/guide/core/09-地形系统.md").read_text(encoding="utf-8")
            self.assertIn("[假链接](./missing.md) `skills/y3-obj-edit/reference/unit.md`", terrain)
            self.assertIn("> [引用代码块内假链接](./missing.md)", terrain)
            self.assertIn("`` `not-a-repo-path` ``", terrain)
            self.assertIn("`` `[x](./missing.md)` ``", terrain)

            # Adding a forbidden marker inside fenced code block or <agent>/ prefix must fail BEFORE writing
            for bad_snippet in ("```lua\n-- DM42 内部示例\n```\n", "参考 `<agent>/unknown/foo.md`\n"):
                (src / "knowledge/核心系统/09-地形系统.md").write_text(
                    f"# 地形系统\n\n{bad_snippet}",
                    encoding="utf-8",
                )
                self.assertEqual(self._run_sync(src, dst, manifest_path), 1)
                after_fail = (dst / "doc/guide/core/09-地形系统.md").read_text(encoding="utf-8")
                self.assertNotIn("DM42", after_fail)
                self.assertNotIn("<agent>/", after_fail)

    def test_validate_before_write_leaves_target_clean_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src, dst, manifest_path = self._setup_workspace(Path(td))
            (src / "knowledge/核心系统/09-地形系统.md").write_text(
                "# 地形系统\n\n[断链](./does_not_exist.md)\n", encoding="utf-8"
            )
            self.assertEqual(self._run_sync(src, dst, manifest_path), 1)
            self.assertFalse((dst / "doc/guide").exists())

            (src / "knowledge/核心系统/09-地形系统.md").write_text(
                "# 地形系统\n\n[越界](../../../outside.md)\n", encoding="utf-8"
            )
            self.assertEqual(self._run_sync(src, dst, manifest_path), 1)
            self.assertFalse((dst / "doc/guide").exists())

            (src / "knowledge/核心系统/09-地形系统.md").write_text(
                "# 地形系统\n\n[根绝对路径](/outside.md)\n", encoding="utf-8"
            )
            self.assertEqual(self._run_sync(src, dst, manifest_path), 1)
            self.assertFalse((dst / "doc/guide").exists())

            val_errors = sld.validate_outputs(
                {"core/09-地形系统.md": "[根路径](/doc/API.md)\n"},
                dst,
                "doc/guide",
            )
            self.assertTrue(any("不能以 `/`" in err for err in val_errors))

    def test_include_exclude_and_manifest_schema_validation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src, dst, manifest_path = self._setup_workspace(Path(td))
            self.assertEqual(self._run_sync(src, dst, manifest_path), 0)
            self.assertFalse((dst / "doc/guide/api-notes/mcp_safety.md").exists())
            self.assertFalse((dst / "doc/guide/core/02-属性计算公式.md").exists())
            self.assertTrue((dst / "doc/guide/object/09-建造系统.md").exists())

            bad_manifest = Path(td) / "bad.json"
            bad_manifest.write_text(
                json.dumps(
                    {
                        "source_repo": "a/b",
                        "source_branch": "main",
                        "target_subdir": "doc/guide",
                        "groups": [{"id": "g1"}],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                sld.load_manifest(bad_manifest)

            bad_ref_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            bad_ref_manifest["groups"][0]["exclude"].append("nonexistent.md")
            bad_ref_path = Path(td) / "bad_ref.json"
            bad_ref_path.write_text(json.dumps(bad_ref_manifest), encoding="utf-8")
            with self.assertRaises(ValueError):
                sld.collect_docs(src, sld.load_manifest(bad_ref_path))

    def test_stale_files_pruned_and_rejected_as_link_targets(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src, dst, manifest_path = self._setup_workspace(Path(td))
            self.assertEqual(self._run_sync(src, dst, manifest_path), 0)

            # Seed stale file inside doc/guide and point a valid doc at it
            stale = dst / "doc/guide/core/obsolete.md"
            stale.write_text("stale\n", encoding="utf-8")

            val_errors = sld.validate_outputs(
                {"core/09-地形系统.md": "[old](./obsolete.md)\n"},
                dst,
                "doc/guide",
            )
            self.assertTrue(any("obsolete.md" in err for err in val_errors))

            # Normal sync prunes stale file
            self.assertEqual(self._run_sync(src, dst, manifest_path), 0)
            self.assertFalse(stale.exists())

    def test_skip_if_sha_only_and_check_behavior(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            src, dst, manifest_path = self._setup_workspace(Path(td))
            self.assertEqual(self._run_sync(src, dst, manifest_path, sha="1111111aaaaaa"), 0)

            # Missing README must still write README even with --skip-if-sha-only
            readme_path = dst / "doc/guide/README.md"
            readme_path.unlink()
            self.assertEqual(
                self._run_sync(src, dst, manifest_path, "--skip-if-sha-only", sha="2222222bbbbbb"),
                0,
            )
            self.assertIn("2222222", readme_path.read_text(encoding="utf-8"))

            # Subsequent SHA-only change with --skip-if-sha-only skips writing
            self.assertEqual(
                self._run_sync(src, dst, manifest_path, "--skip-if-sha-only", sha="3333333cccccc"),
                0,
            )
            self.assertIn("2222222", readme_path.read_text(encoding="utf-8"))

            # Force refresh without flag updates README.md while leaving docs identical
            before_doc = (dst / "doc/guide/core/09-地形系统.md").read_text(encoding="utf-8")
            self.assertEqual(self._run_sync(src, dst, manifest_path, sha="3333333cccccc"), 0)
            self.assertIn("3333333", readme_path.read_text(encoding="utf-8"))
            self.assertEqual(
                (dst / "doc/guide/core/09-地形系统.md").read_text(encoding="utf-8"),
                before_doc,
            )

            self.assertEqual(
                self._run_sync(src, dst, manifest_path, "--check", sha="3333333cccccc"), 0
            )
            (dst / "doc/guide/api-notes/ui-events.md").write_text("dirty\n", encoding="utf-8")
            self.assertEqual(
                self._run_sync(src, dst, manifest_path, "--check", sha="3333333cccccc"), 1
            )

    @staticmethod
    def _extract_workflow_push_paths(workflow_text: str) -> list[str]:
        lines = workflow_text.splitlines()
        patterns: list[str] = []
        in_on = False
        on_indent = -1
        in_push = False
        push_indent = -1
        in_paths = False
        paths_indent = -1
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            indent = len(line) - len(line.lstrip(" "))
            if stripped == "on:":
                in_on, on_indent = True, indent
                continue
            if in_on and indent <= on_indent:
                break
            if in_on and stripped == "push:":
                in_push, push_indent = True, indent
                continue
            if in_push and indent <= push_indent:
                in_push = in_paths = False
                continue
            if in_push and stripped == "paths:":
                in_paths, paths_indent = True, indent
                continue
            if in_paths:
                if indent <= paths_indent or not stripped.startswith("- "):
                    in_paths = False
                else:
                    patterns.append(stripped[2:].strip().strip("'\""))
        return patterns

    def test_workflow_push_paths_cover_real_manifest(self) -> None:
        manifest = sld.load_manifest(REPO_ROOT / ".github/sync-lualib/manifest.json")
        workflow_text = (REPO_ROOT / ".github/workflows/sync-lualib-docs.yml").read_text(
            encoding="utf-8"
        )
        patterns = self._extract_workflow_push_paths(workflow_text)
        self.assertIn(".github/sync-lualib/**", patterns)

        for group in manifest.groups:
            if group.include:
                targets = [f"{group.source_dir}/{name}" for name in group.include]
            else:
                targets = [f"{group.source_dir}/dummy.md"]
            for target in targets:
                covered = any(
                    pat == target
                    or (pat.endswith("/**") and target.startswith(pat[:-2]))
                    for pat in patterns
                )
                self.assertTrue(covered, f"{target} 未被 workflow on.push.paths 覆盖: {patterns}")


if __name__ == "__main__":
    unittest.main()
