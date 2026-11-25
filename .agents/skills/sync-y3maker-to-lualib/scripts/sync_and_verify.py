#!/usr/bin/env python3
"""Sync scoped Lua documentation, rules, and skills from y3-maker-config to y3-lualib/doc."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any

DEFAULT_SCOPE_PATH = Path(__file__).resolve().parent.parent / "references" / "scope.json"
ALWAYS_PROTECTED_PATHS = ("AGENTS.md",)
TEXT_SUFFIXES = {".md", ".mdc", ".py", ".json", ".yaml", ".yml", ".lua", ".txt"}
LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\s]+)\)")
SKIP_SCHEMES = ("http://", "https://", "mailto:")


def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a POSIX glob (supporting `**`, `*`, `?`) into a compiled regex."""
    parts: list[str] = ["^"]
    i = 0
    n = len(pattern)
    while i < n:
        if pattern[i : i + 3] == "**/":
            parts.append("(?:.*/)?")
            i += 3
        elif pattern[i : i + 2] == "**":
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            parts.append("[^/]")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    parts.append("$")
    return re.compile("".join(parts))


def load_scope(scope_path: Path) -> dict[str, Any]:
    """Load and return the JSON scope configuration."""
    return json.loads(scope_path.read_text(encoding="utf-8"))


def is_protected_rel(doc_rel: str, protected_paths: list[str]) -> bool:
    """Return True if a doc-relative POSIX path falls inside a protected native path."""
    all_protected = list(protected_paths) + list(ALWAYS_PROTECTED_PATHS)
    for prot in all_protected:
        prot_norm = prot.strip("/")
        if doc_rel == prot_norm or doc_rel.startswith(prot_norm + "/"):
            return True
    return False


def strip_readme_lines(raw: bytes, patterns: list[str]) -> bytes:
    """Remove lines matching any substring pattern while preserving original line endings."""
    text = raw.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    normalized = text.replace("\r\n", "\n")
    kept = [
        line
        for line in normalized.split("\n")
        if not any(pat in line for pat in patterns)
    ]
    return newline.join(kept).encode("utf-8")


def collect_expected_files(source_root: Path, scope: dict[str, Any]) -> dict[str, bytes]:
    """Build mapping of doc-relative POSIX path -> expected file bytes."""
    expected: dict[str, bytes] = {}
    protected = scope["protected_native_paths"]

    # 1. Knowledge directory
    know_cfg = scope["knowledge"]
    know_src = source_root / know_cfg["source_dir"]
    know_dst = know_cfg["target_dir"]
    know_excludes = set(know_cfg.get("exclude_files", []))
    strip_patterns = know_cfg.get("readme_strip_patterns", [])
    for path in sorted(know_src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(know_src).as_posix()
        if rel in know_excludes:
            continue
        doc_rel = f"{know_dst}/{rel}"
        raw = path.read_bytes()
        if rel == "README.md" and strip_patterns:
            raw = strip_readme_lines(raw, strip_patterns)
        expected[doc_rel] = raw

    # 2. Rules files
    rules_cfg = scope["rules"]
    rules_src = source_root / rules_cfg["source_dir"]
    rules_dst = rules_cfg["target_dir"]
    for fname in rules_cfg["include_files"]:
        src_file = rules_src / fname
        if not src_file.is_file():
            raise FileNotFoundError(f"Included rule file missing in source: {src_file}")
        expected[f"{rules_dst}/{fname}"] = src_file.read_bytes()

    # 3. Skills directories
    skills_cfg = scope["skills"]
    skills_src = source_root / skills_cfg["source_dir"]
    skills_dst = skills_cfg["target_dir"]
    exclude_res = [glob_to_regex(pat) for pat in skills_cfg.get("exclude_globs", [])]
    for skill_name in skills_cfg["include_dirs"]:
        skill_dir = skills_src / skill_name
        if not skill_dir.is_dir():
            raise FileNotFoundError(f"Included skill directory missing in source: {skill_dir}")
        for path in sorted(skill_dir.rglob("*")):
            if not path.is_file():
                continue
            skill_rel = path.relative_to(skills_src).as_posix()
            if any(rx.match(skill_rel) for rx in exclude_res):
                continue
            expected[f"{skills_dst}/{skill_rel}"] = path.read_bytes()

    for doc_rel in expected:
        if is_protected_rel(doc_rel, protected):
            raise ValueError(f"Managed path collides with protected native path: {doc_rel}")

    return expected


def collect_existing_managed(target_doc: Path, scope: dict[str, Any]) -> dict[str, Path]:
    """Scan only the managed directories inside target/doc."""
    managed_roots = [
        target_doc / scope["knowledge"]["target_dir"],
        target_doc / scope["rules"]["target_dir"],
    ] + [
        target_doc / scope["skills"]["target_dir"] / name
        for name in scope["skills"]["include_dirs"]
    ]
    existing: dict[str, Path] = {}
    for root in managed_roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_file():
                existing[path.relative_to(target_doc).as_posix()] = path
    return existing


def detect_unclassified(source_root: Path, scope: dict[str, Any]) -> list[str]:
    """Return warning lines for source skills or rules not listed in scope."""
    warnings: list[str] = []
    known_skills = set(scope["skills"]["include_dirs"]) | set(scope.get("known_excluded_skills", []))
    skills_dir = source_root / scope["skills"]["source_dir"]
    if skills_dir.is_dir():
        for entry in sorted(skills_dir.iterdir()):
            if entry.is_dir() and entry.name not in known_skills:
                warnings.append(f"[UNCLASSIFIED SKILL] skills/{entry.name}")

    known_rules = set(scope["rules"]["include_files"]) | set(scope.get("known_excluded_rules", []))
    rules_dir = source_root / scope["rules"]["source_dir"]
    if rules_dir.is_dir():
        for entry in sorted(rules_dir.iterdir()):
            if entry.is_file() and entry.name not in known_rules:
                warnings.append(f"[UNCLASSIFIED RULE] rules/{entry.name}")
    return warnings


def validate_skill_frontmatter(skill_dir: Path, errors: list[str]) -> None:
    """Validate that SKILL.md exists and declares matching name and non-empty description."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        errors.append(f"Missing SKILL.md: {skill_dir}")
        return
    text = skill_md.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        errors.append(f"Invalid YAML frontmatter delimiters in {skill_md}")
        return
    fm = m.group(1)
    name_m = re.search(r"^name:\s*(.+?)\s*$", fm, re.MULTILINE)
    desc_m = re.search(r"^description:\s*(.*)$", fm, re.MULTILINE)
    if not name_m or not name_m.group(1).strip("'\""):
        errors.append(f"Missing frontmatter name in {skill_md}")
    else:
        parsed_name = name_m.group(1).strip("'\"")
        if parsed_name != skill_dir.name:
            errors.append(f"Skill name '{parsed_name}' != directory '{skill_dir.name}' in {skill_md}")
    if not desc_m:
        errors.append(f"Missing frontmatter description in {skill_md}")
    else:
        inline = desc_m.group(1).strip()
        if inline in ("", ">", "|"):
            following = fm[desc_m.end() :].strip()
            if not following:
                errors.append(f"Empty multiline description in {skill_md}")


def check_readme_links(readme_path: Path, doc_knowledge_dir: Path, errors: list[str]) -> None:
    """Verify every relative Markdown link in knowledge/README.md points to an existing file."""
    if not readme_path.is_file():
        errors.append(f"Missing knowledge README: {readme_path}")
        return
    text = readme_path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    in_fence = False
    for line_no, line in enumerate(text.split("\n"), start=1):
        if re.match(r"^\s*(?:```|~~~)", line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK_RE.finditer(line):
            href = match.group(3).strip()
            if href.startswith("#") or href.startswith(SKIP_SCHEMES):
                continue
            rel_part = urllib.parse.unquote(href.split("#", 1)[0])
            if not rel_part:
                continue
            resolved = posixpath.normpath(rel_part)
            if resolved.startswith(".."):
                errors.append(f"knowledge/README.md:{line_no} escapes knowledge/: {href}")
                continue
            if not (doc_knowledge_dir / resolved).exists():
                errors.append(f"knowledge/README.md:{line_no} broken link: {href}")


def verify_target(
    target_root: Path, scope: dict[str, Any], expected: dict[str, bytes]
) -> list[str]:
    """Run all post-sync integrity and guardrail checks against target/doc."""
    errors: list[str] = []
    target_doc = target_root / "doc"
    protected = scope["protected_native_paths"]

    # 1. Protected native paths exist
    for rel in protected:
        if not (target_doc / rel).exists():
            errors.append(f"Protected native path missing: doc/{rel}")

    # 2. Managed files match expected exactly
    existing = collect_existing_managed(target_doc, scope)
    for rel in sorted(set(expected) - set(existing)):
        errors.append(f"Missing synced file: doc/{rel}")
    for rel in sorted(set(existing) - set(expected)):
        errors.append(f"Unexpected extra file in managed dir: doc/{rel}")
    for rel in sorted(set(expected) & set(existing)):
        if existing[rel].read_bytes() != expected[rel]:
            errors.append(f"Content mismatch with source: doc/{rel}")

    # 3. Skill frontmatter validation (managed + native protected skills)
    skills_root = target_doc / scope["skills"]["target_dir"]
    for name in scope["skills"]["include_dirs"]:
        validate_skill_frontmatter(skills_root / name, errors)
    for rel in protected:
        if rel.startswith("skills/"):
            validate_skill_frontmatter(target_doc / rel, errors)

    # 4. Forbidden patterns scan on synced text files
    patterns = [(pat, re.compile(pat)) for pat in scope.get("forbidden_patterns", [])]
    for rel, path in sorted(existing.items()):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), start=1):
            for raw_pat, rx in patterns:
                if rx.search(line):
                    errors.append(f"Forbidden pattern '{raw_pat}' at doc/{rel}:{line_no}")

    # 5. Excluded artifacts check across doc/knowledge, doc/rules, doc/skills
    for check_sub in ("knowledge", "rules", "skills"):
        sub_dir = target_doc / check_sub
        if not sub_dir.exists():
            continue
        for p in sub_dir.rglob("*"):
            rel = p.relative_to(target_doc).as_posix()
            if (
                p.name == "12-ECA系统.md"
                or p.name.endswith("-ECA-基准版.md")
                or p.name == "__pycache__"
                or p.suffix in (".pyc", ".pyo")
                or "/temp/" in f"/{rel}/"
                or "/.queue/" in f"/{rel}/"
            ):
                errors.append(f"Excluded artifact present in target: doc/{rel}")

    # 6. Zero broken links in doc/knowledge/README.md
    know_dir = target_doc / scope["knowledge"]["target_dir"]
    check_readme_links(know_dir / "README.md", know_dir, errors)
    return errors


def apply_sync(target_root: Path, scope: dict[str, Any], expected: dict[str, bytes]) -> tuple[int, int, int]:
    """Write expected files to target/doc and remove stale files inside managed directories."""
    target_doc = target_root / "doc"
    protected = scope["protected_native_paths"]
    existing = collect_existing_managed(target_doc, scope)

    created = updated = removed = 0
    for rel, content in sorted(expected.items()):
        if is_protected_rel(rel, protected):
            raise RuntimeError(f"Refusing to write protected path: doc/{rel}")
        dst = target_doc / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(content)
            created += 1
        elif dst.read_bytes() != content:
            dst.write_bytes(content)
            updated += 1

    for rel in sorted(set(existing) - set(expected)):
        if is_protected_rel(rel, protected):
            raise RuntimeError(f"Refusing to delete protected path: doc/{rel}")
        existing[rel].unlink()
        removed += 1

    # Prune empty directories inside managed roots (never touch protected roots)
    managed_roots = [
        target_doc / scope["knowledge"]["target_dir"],
        target_doc / scope["rules"]["target_dir"],
    ] + [
        target_doc / scope["skills"]["target_dir"] / name
        for name in scope["skills"]["include_dirs"]
    ]
    for root in managed_roots:
        if not root.exists():
            continue
        for dir_path in sorted(root.rglob("*"), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()

    return created, updated, removed


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Path to y3-maker-config repo")
    parser.add_argument("--target", required=True, type=Path, help="Path to y3-lualib repo")
    parser.add_argument("--scope", type=Path, default=DEFAULT_SCOPE_PATH, help="Path to scope.json")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Preview changes and unclassified source items")
    mode.add_argument("--apply", action="store_true", help="Apply sync to target/doc and run verification")
    mode.add_argument("--verify-only", action="store_true", help="Verify target/doc against source and guardrails")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_root = args.source.resolve()
    target_root = args.target.resolve()
    scope = load_scope(args.scope.resolve())

    warnings = detect_unclassified(source_root, scope)
    for w in warnings:
        print(f"WARN: {w}")

    expected = collect_expected_files(source_root, scope)
    total_kb = sum(len(b) for b in expected.values()) / 1024.0

    if args.dry_run:
        existing = collect_existing_managed(target_root / "doc", scope)
        to_add = sorted(set(expected) - set(existing))
        to_remove = sorted(set(existing) - set(expected))
        to_update = sorted(
            rel for rel in (set(expected) & set(existing)) if existing[rel].read_bytes() != expected[rel]
        )
        print(
            f"DRY-RUN: expected={len(expected)} files ({total_kb:.1f} KB) | "
            f"add={len(to_add)} update={len(to_update)} remove={len(to_remove)}"
        )
        for label, items in (("ADD", to_add), ("UPDATE", to_update), ("REMOVE", to_remove)):
            for rel in items[:20]:
                print(f"  [{label}] doc/{rel}")
            if len(items) > 20:
                print(f"  [{label}] ... and {len(items) - 20} more")
        return 0

    if args.apply:
        created, updated, removed = apply_sync(target_root, scope, expected)
        print(
            f"APPLY: expected={len(expected)} files ({total_kb:.1f} KB) | "
            f"created={created} updated={updated} removed={removed}"
        )

    errors = verify_target(target_root, scope, expected)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        print(f"VERIFY FAILED: {len(errors)} error(s).", file=sys.stderr)
        return 1

    print(f"VERIFY PASSED: {len(expected)} managed files ({total_kb:.1f} KB), all guardrails OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
