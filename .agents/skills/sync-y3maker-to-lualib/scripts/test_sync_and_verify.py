#!/usr/bin/env python3
"""Unit tests for sync_and_verify.py."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_and_verify  # noqa: E402


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def make_skill(root: Path, name: str, extra: dict[str, str] | None = None) -> None:
    write_text(root / "skills" / name / "SKILL.md", f"---\nname: {name}\ndescription: test skill {name}\n---\n# {name}\n")
    for rel, body in (extra or {}).items():
        write_text(root / "skills" / name / rel, body)


class SyncAndVerifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.source = self.base / "y3-maker-config"
        self.target = self.base / "y3-lualib"
        self.scope_path = self.base / "scope.json"

        scope = {
            "knowledge": {
                "source_dir": "knowledge",
                "target_dir": "knowledge",
                "exclude_files": ["核心系统/12-ECA系统.md"],
                "readme_strip_patterns": ["12-ECA系统.md"],
            },
            "rules": {
                "source_dir": "rules",
                "target_dir": "rules",
                "include_files": ["api-safety.mdc"],
            },
            "skills": {
                "source_dir": "skills",
                "target_dir": "skills",
                "include_dirs": ["y3-cloud-script", "y3-game-spec", "y3-resource-import", "y3-auto-test"],
                "exclude_globs": [
                    "y3-game-spec/roadmaps/*-ECA-基准版.md",
                    "y3-resource-import/temp/**",
                    "y3-auto-test/.queue/**",
                    "**/__pycache__/**",
                    "**/*.pyc",
                ],
            },
            "known_excluded_skills": ["y3-eca-pipeline"],
            "known_excluded_rules": ["rules.mdc"],
            "protected_native_paths": ["API.md", "API", "Lua虚拟机.md", "skills/y3-lib", "skills/y3-lua-vm"],
            "forbidden_patterns": ["DM42", "爆战兄弟", "E:\\\\map\\\\"],
        }
        write_text(self.scope_path, json.dumps(scope, ensure_ascii=False, indent=2))

        # Populate source
        write_text(
            self.source / "knowledge" / "README.md",
            "| [01-属性.md](./核心系统/01-属性.md) | ok |\n| [12-ECA系统.md](./核心系统/12-ECA系统.md) | eca |\n",
        )
        write_text(self.source / "knowledge" / "核心系统" / "01-属性.md", "# 属性\n")
        write_text(self.source / "knowledge" / "核心系统" / "12-ECA系统.md", "# ECA\n")
        write_text(self.source / "rules" / "api-safety.mdc", "# api safety\n")
        write_text(self.source / "rules" / "rules.mdc", "# master rules\n")
        make_skill(self.source, "y3-cloud-script")
        make_skill(
            self.source,
            "y3-game-spec",
            {"roadmaps/塔防执行案.md": "ok", "roadmaps/塔防执行案-ECA-基准版.md": "skip"},
        )
        make_skill(self.source, "y3-resource-import", {"temp/sample.json": "{}"})
        make_skill(self.source, "y3-auto-test", {".queue/.ready": "", "__pycache__/x.pyc": "bin"})
        make_skill(self.source, "y3-eca-pipeline")

        # Populate target native files
        write_text(self.target / "doc" / "API.md", "# API\n")
        write_text(self.target / "doc" / "API" / "Unit.md", "# Unit\n")
        write_text(self.target / "doc" / "Lua虚拟机.md", "# VM\n")
        write_text(self.target / "doc" / "AGENTS.md", "# Custom AGENTS\n")
        make_skill(self.target / "doc", "y3-lib")
        make_skill(self.target / "doc", "y3-lua-vm")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_dry_run_does_not_modify_target(self) -> None:
        rc = sync_and_verify.main(
            ["--source", str(self.source), "--target", str(self.target), "--scope", str(self.scope_path), "--dry-run"]
        )
        self.assertEqual(rc, 0)
        self.assertFalse((self.target / "doc" / "knowledge").exists())
        self.assertFalse((self.target / "doc" / "skills" / "y3-cloud-script").exists())

    def test_apply_filters_excludes_protects_native_and_cleans_stale(self) -> None:
        stale = self.target / "doc" / "skills" / "y3-cloud-script" / "stale.md"
        write_text(stale, "old")

        rc = sync_and_verify.main(
            ["--source", str(self.source), "--target", str(self.target), "--scope", str(self.scope_path), "--apply"]
        )
        self.assertEqual(rc, 0)

        # Native untouched
        self.assertEqual((self.target / "doc" / "AGENTS.md").read_text(encoding="utf-8"), "# Custom AGENTS\n")
        self.assertTrue((self.target / "doc" / "skills" / "y3-lib" / "SKILL.md").is_file())
        self.assertTrue((self.target / "doc" / "skills" / "y3-lua-vm" / "SKILL.md").is_file())

        # Excluded files omitted and README line stripped
        self.assertFalse((self.target / "doc" / "knowledge" / "核心系统" / "12-ECA系统.md").exists())
        readme = (self.target / "doc" / "knowledge" / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("12-ECA系统.md", readme)
        self.assertIn("01-属性.md", readme)
        self.assertFalse((self.target / "doc" / "rules" / "rules.mdc").exists())
        self.assertFalse((self.target / "doc" / "skills" / "y3-eca-pipeline").exists())
        self.assertFalse((self.target / "doc" / "skills" / "y3-game-spec" / "roadmaps" / "塔防执行案-ECA-基准版.md").exists())
        self.assertFalse((self.target / "doc" / "skills" / "y3-resource-import" / "temp" / "sample.json").exists())
        self.assertFalse((self.target / "doc" / "skills" / "y3-auto-test" / ".queue" / ".ready").exists())
        self.assertFalse(stale.exists())

    def test_verify_fails_on_forbidden_pattern_and_native_tamper(self) -> None:
        write_text(self.source / "knowledge" / "核心系统" / "01-属性.md", "internal DM42 ref\n")
        rc = sync_and_verify.main(
            ["--source", str(self.source), "--target", str(self.target), "--scope", str(self.scope_path), "--apply"]
        )
        self.assertEqual(rc, 1)

    def test_detect_unclassified_items(self) -> None:
        make_skill(self.source, "y3-new-unknown")
        write_text(self.source / "rules" / "new-rule.mdc", "# new\n")
        scope = sync_and_verify.load_scope(self.scope_path)
        warnings = sync_and_verify.detect_unclassified(self.source, scope)
        self.assertIn("[UNCLASSIFIED SKILL] skills/y3-new-unknown", warnings)
        self.assertIn("[UNCLASSIFIED RULE] rules/new-rule.mdc", warnings)

    def test_bom_in_skill_frontmatter_is_accepted(self) -> None:
        (self.source / "skills" / "y3-cloud-script" / "SKILL.md").write_bytes(
            "\ufeff---\nname: y3-cloud-script\ndescription: bom skill\n---\n# body\n".encode("utf-8")
        )
        rc = sync_and_verify.main(
            ["--source", str(self.source), "--target", str(self.target), "--scope", str(self.scope_path), "--apply"]
        )
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
