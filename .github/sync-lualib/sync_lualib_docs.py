#!/usr/bin/env python3
"""Sync Lua-relevant documentation from y3-maker-config to y3-lualib/doc/guide."""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import subprocess
import sys
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

FENCE_OPEN_RE = re.compile(r"^((?:[ \t]{0,3}>[ \t]?)*)[ \t]{0,3}(`{3,}|~{3,})(.*)$")
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n*", re.DOTALL)
H1_RE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
BACKTICK_REPO_PATH_RE = re.compile(
    r"^(?:<agent>/|(?:\.\./)+)?((?:skills|knowledge|memory|rules)/[^\s`]+)$"
)
SKIP_SCHEMES = ("http://", "https://", "mailto:")
FORBIDDEN_MARKERS = ("DM42", "test321321", "<agent>/", "../../skills/")
SOURCE_COMMIT_LINE_PREFIX = "- **源提交**："


@dataclass(frozen=True)
class GroupConfig:
    """Validated group entry from manifest.json."""

    id: str
    title: str
    description: str
    source_dir: str
    target_dir: str
    include: tuple[str, ...]
    exclude: tuple[str, ...]


@dataclass(frozen=True)
class Manifest:
    """Validated manifest configuration."""

    source_repo: str
    source_branch: str
    target_subdir: str
    groups: tuple[GroupConfig, ...]


@dataclass(frozen=True)
class DocSpec:
    """Single document selected by manifest."""

    group_id: str
    src_rel: str
    dst_rel: str
    title: str


@dataclass(frozen=True)
class SyncContext:
    """Shared context passed through transformation helpers."""

    source_root: Path
    target_root: Path
    manifest: Manifest
    src_to_dst: dict[str, str]
    errors: list[str]


@dataclass(frozen=True)
class TextToken:
    """Plain text span inside a line."""

    text: str


@dataclass(frozen=True)
class CodeSpanToken:
    """Inline backtick code span inside a line."""

    ticks: int
    raw: str
    full: str


@dataclass(frozen=True)
class LinkToken:
    """Inline Markdown link or image token."""

    is_image: bool
    label: str
    href_raw: str
    full: str


InlineToken = TextToken | CodeSpanToken | LinkToken


def normalize_newlines(text: str) -> str:
    """Normalize CRLF/CR line endings to LF."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def strip_frontmatter(text: str) -> str:
    """Remove leading YAML frontmatter if present."""
    return FRONTMATTER_RE.sub("", normalize_newlines(text), count=1)


def _match_fence_open(line: str) -> tuple[int, str, int] | None:
    m = FENCE_OPEN_RE.match(line)
    if not m:
        return None
    quote_prefix, marker, info = m.group(1), m.group(2), m.group(3)
    if marker[0] == "`" and "`" in info:
        return None
    return quote_prefix.count(">"), marker[0], len(marker)


def _has_quote_depth(line: str, quote_depth: int) -> bool:
    if quote_depth <= 0:
        return True
    return bool(re.match(rf"^(?:[ \t]{{0,3}}>[ \t]?){{{quote_depth}}}", line))


def _is_fence_close(line: str, quote_depth: int, fence_char: str, fence_len: int) -> bool:
    quote_pat = rf"(?:[ \t]{{0,3}}>[ \t]?){{{quote_depth}}}" if quote_depth > 0 else ""
    return bool(re.match(rf"^{quote_pat}[ \t]{{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*$", line))


def iter_lines_with_fence(text: str) -> Iterator[tuple[int, str, bool]]:
    """Yield `(line_no, line, in_fence)` for each line; fence delimiters count as `in_fence=True`."""
    in_fence = False
    quote_depth = 0
    fence_char = ""
    fence_len = 0
    for line_no, line in enumerate(text.split("\n"), start=1):
        if in_fence and not _has_quote_depth(line, quote_depth):
            in_fence = False
        if not in_fence:
            fence = _match_fence_open(line)
            if fence:
                in_fence = True
                quote_depth, fence_char, fence_len = fence
                yield line_no, line, True
                continue
            yield line_no, line, False
        else:
            yield line_no, line, True
            if _is_fence_close(line, quote_depth, fence_char, fence_len):
                in_fence = False


def _scan_code_span(line: str, start: int) -> tuple[int, int]:
    """Scan opening backticks at `start`; return `(ticks, close_index)` or `(ticks, -1)`."""
    n = len(line)
    ticks = 1
    while start + ticks < n and line[start + ticks] == "`":
        ticks += 1
    i = start + ticks
    while i < n:
        if line[i] == "`":
            run = 1
            while i + run < n and line[i + run] == "`":
                run += 1
            if run == ticks:
                return ticks, i
            i += run
        else:
            i += 1
    return ticks, -1


def _try_parse_markdown_link(line: str, start: int) -> tuple[bool, str, str, int] | None:
    """Parse `[label](href)` or `![label](href)` starting at `start`."""
    is_image = line.startswith("![", start)
    idx = start + (2 if is_image else 1)
    if not (is_image or line.startswith("[", start)):
        return None

    depth = 1
    n = len(line)
    while idx < n and depth > 0:
        ch = line[idx]
        if ch == "\\" and idx + 1 < n:
            idx += 2
            continue
        if ch == "`":
            ticks, close = _scan_code_span(line, idx)
            idx = (idx + ticks) if close == -1 else (close + ticks)
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                break
        idx += 1

    if depth != 0 or idx + 1 >= n or line[idx + 1] != "(":
        return None

    label = line[start + (2 if is_image else 1) : idx]
    href_start = idx + 2
    p = href_start
    paren_depth = 1
    while p < n and paren_depth > 0:
        ch = line[p]
        if ch == "\\" and p + 1 < n:
            p += 2
            continue
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
            if paren_depth == 0:
                break
        p += 1

    if paren_depth != 0:
        return None

    return is_image, label, line[href_start:p], p + 1


def iter_inline_tokens(line: str) -> Iterator[InlineToken]:
    """Scan a single Markdown line into plain text, inline code spans, and links."""
    buf: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "`":
            ticks, close = _scan_code_span(line, i)
            if close == -1:
                buf.append(line[i : i + ticks])
                i += ticks
                continue
            if buf:
                yield TextToken("".join(buf))
                buf.clear()
            raw = line[i + ticks : close]
            yield CodeSpanToken(ticks=ticks, raw=raw, full=line[i : close + ticks])
            i = close + ticks
            continue

        if (ch == "!" and line.startswith("![", i)) or ch == "[":
            parsed = _try_parse_markdown_link(line, i)
            if parsed is not None:
                if buf:
                    yield TextToken("".join(buf))
                    buf.clear()
                is_image, label, href_raw, end_idx = parsed
                yield LinkToken(
                    is_image=is_image,
                    label=label,
                    href_raw=href_raw,
                    full=line[i:end_idx],
                )
                i = end_idx
                continue

        buf.append(ch)
        i += 1
    if buf:
        yield TextToken("".join(buf))


def extract_title(body: str, fallback: str) -> str:
    """Extract first Markdown H1 heading outside fenced code blocks."""
    for _, line, in_fence in iter_lines_with_fence(body):
        if in_fence:
            continue
        m = H1_RE.match(line)
        if m:
            return m.group(1).strip()
    return fallback


def detect_source_sha(source_root: Path) -> str:
    """Read HEAD commit SHA from source git repository."""
    try:
        res = subprocess.run(
            ["git", "-C", str(source_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError(f"无法读取源仓库 git HEAD：{exc}") from exc
    return res.stdout.strip()


def _require_non_empty_str(mapping: dict, key: str, context: str) -> str:
    val = mapping.get(key)
    if not isinstance(val, str) or not val.strip():
        raise ValueError(f"{context} 缺少或非法字段: {key}")
    return val.strip()


def _optional_str_tuple(mapping: dict, key: str, context: str) -> tuple[str, ...]:
    val = mapping.get(key)
    if val is None:
        return ()
    if not isinstance(val, list) or not all(isinstance(x, str) and x.strip() for x in val):
        raise ValueError(f"{context}.{key} 必须为非空字符串列表")
    return tuple(x.strip() for x in val)


def load_manifest(manifest_path: Path) -> Manifest:
    """Load and validate manifest JSON into typed structures."""
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("manifest 根节点必须为 JSON 对象")

    source_repo = _require_non_empty_str(data, "source_repo", "manifest")
    source_branch = _require_non_empty_str(data, "source_branch", "manifest")
    target_subdir = _require_non_empty_str(data, "target_subdir", "manifest").strip("/")

    raw_groups = data.get("groups")
    if not isinstance(raw_groups, list) or not raw_groups:
        raise ValueError("manifest.groups 必须为非空数组")

    groups: list[GroupConfig] = []
    seen_ids: set[str] = set()
    for idx, item in enumerate(raw_groups):
        ctx_name = f"manifest.groups[{idx}]"
        if not isinstance(item, dict):
            raise ValueError(f"{ctx_name} 必须为对象")
        gid = _require_non_empty_str(item, "id", ctx_name)
        if gid in seen_ids:
            raise ValueError(f"manifest.groups 存在重复 id: {gid}")
        seen_ids.add(gid)
        groups.append(
            GroupConfig(
                id=gid,
                title=_require_non_empty_str(item, "title", ctx_name),
                description=_require_non_empty_str(item, "description", ctx_name),
                source_dir=_require_non_empty_str(item, "source_dir", ctx_name).strip("/"),
                target_dir=_require_non_empty_str(item, "target_dir", ctx_name).strip("/"),
                include=_optional_str_tuple(item, "include", ctx_name),
                exclude=_optional_str_tuple(item, "exclude", ctx_name),
            )
        )

    return Manifest(
        source_repo=source_repo,
        source_branch=source_branch,
        target_subdir=target_subdir,
        groups=tuple(groups),
    )


def collect_docs(source_root: Path, manifest: Manifest) -> list[DocSpec]:
    """Collect and validate all source Markdown files defined by manifest."""
    docs: list[DocSpec] = []
    seen_dst: set[str] = set()
    for group in manifest.groups:
        src_dir = source_root / group.source_dir
        if not src_dir.is_dir():
            raise FileNotFoundError(f"源目录不存在: {src_dir}")

        include_set = set(group.include)
        exclude_set = set(group.exclude)
        candidates = sorted(p for p in src_dir.iterdir() if p.is_file() and p.suffix == ".md")
        available_names = {p.name for p in candidates}
        missing_refs = sorted((include_set | exclude_set) - available_names)
        if missing_refs:
            raise ValueError(
                f"分组 {group.id} 的 include/exclude 包含不存在的文件: {', '.join(missing_refs)}"
            )

        matched: list[Path] = []
        for path in candidates:
            if include_set and path.name not in include_set:
                continue
            if path.name in exclude_set:
                continue
            matched.append(path)

        if not matched:
            raise ValueError(f"分组 {group.id} 未匹配到任何文档: {group.source_dir}")

        for path in matched:
            src_rel = f"{group.source_dir}/{path.name}"
            dst_rel = f"{group.target_dir}/{path.name}"
            if dst_rel in seen_dst:
                raise ValueError(f"目标路径冲突: {dst_rel}")
            seen_dst.add(dst_rel)
            body = strip_frontmatter(path.read_text(encoding="utf-8"))
            title = extract_title(body, path.stem)
            docs.append(
                DocSpec(
                    group_id=group.id,
                    src_rel=src_rel,
                    dst_rel=dst_rel,
                    title=title,
                )
            )
    return docs


def _relative_posix(from_dir: str, to_path: str) -> str:
    rel = posixpath.relpath(to_path, from_dir)
    if not rel.startswith(".") and "/" not in rel:
        return f"./{rel}"
    return rel


def _split_href(href_raw: str) -> tuple[str, str, str]:
    """Split raw markdown link target into `(path_part, fragment, title_suffix)`."""
    stripped = href_raw.strip()
    title_suffix = ""
    if stripped.startswith("<") and ">" in stripped:
        end_angle = stripped.index(">")
        url_full = stripped[1:end_angle]
        rest = stripped[end_angle + 1 :].strip()
        if rest:
            title_suffix = f" {rest}"
    else:
        m = re.match(r"^(\S+)(\s+(?:\"[^\"]*\"|'[^']*'))?$", stripped)
        if m:
            url_full = m.group(1)
            title_suffix = m.group(2) or ""
        else:
            url_full = stripped

    if "#" in url_full:
        path_part, frag = url_full.split("#", 1)
        fragment = f"#{frag}"
    else:
        path_part, fragment = url_full, ""
    return path_part, fragment, title_suffix


def _github_url(manifest: Manifest, kind: str, rel_path: str, fragment: str = "") -> str:
    quoted = urllib.parse.quote(rel_path, safe="/")
    return (
        f"https://github.com/{manifest.source_repo}/"
        f"{kind}/{manifest.source_branch}/{quoted}{fragment}"
    )


def _format_code_label(label: str) -> str:
    if label.startswith("`") and label.endswith("`") and len(label) >= 2:
        return label
    return f"`{label}`"


def _resolve_source_target(
    ctx: SyncContext,
    dst_dir: str,
    resolved: str,
    *,
    is_image: bool = False,
    fragment: str = "",
) -> tuple[str, bool, bool] | None:
    """Resolve a repo-relative source path to `(rewritten_href, in_subset, is_dir)`."""
    if (
        not resolved
        or resolved.startswith("/")
        or resolved == ".."
        or resolved.startswith("../")
    ):
        return None

    if resolved in ctx.src_to_dst:
        target_doc_path = posixpath.join(ctx.manifest.target_subdir, ctx.src_to_dst[resolved])
        rel = _relative_posix(dst_dir, target_doc_path)
        return f"{rel}{fragment}", True, False

    candidate = ctx.source_root / resolved
    if candidate.exists():
        is_dir = candidate.is_dir()
        if is_image:
            raw_url = (
                f"https://raw.githubusercontent.com/{ctx.manifest.source_repo}/"
                f"{ctx.manifest.source_branch}/{urllib.parse.quote(resolved, safe='/')}"
            )
            return raw_url, False, is_dir
        kind = "tree" if is_dir else "blob"
        return _github_url(ctx.manifest, kind, resolved, fragment), False, is_dir

    return None


def _rewrite_markdown_link(token: LinkToken, doc: DocSpec, ctx: SyncContext, line_no: int) -> str:
    path_part, fragment, title_suffix = _split_href(token.href_raw)
    prefix = "!" if token.is_image else ""

    if not path_part or path_part.startswith(SKIP_SCHEMES) or path_part.startswith("#"):
        return token.full

    unquoted_path = urllib.parse.unquote(path_part)
    dst_dir = posixpath.dirname(posixpath.join(ctx.manifest.target_subdir, doc.dst_rel))

    if unquoted_path.startswith("maps/EntryMap/script/y3/"):
        inner = unquoted_path[len("maps/EntryMap/script/y3/") :]
        if (ctx.target_root / inner).exists():
            rel = _relative_posix(dst_dir, inner)
            return f"{prefix}[{token.label}]({rel}{fragment}{title_suffix})"
        if not token.is_image:
            return _format_code_label(token.label)
        ctx.errors.append(f"{doc.src_rel}:{line_no}: 找不到目标文件 {inner}")
        return token.full

    if unquoted_path.startswith("maps/"):
        if not token.is_image:
            return _format_code_label(token.label)
        ctx.errors.append(f"{doc.src_rel}:{line_no}: 图片引用指向地图本地路径 {unquoted_path}")
        return token.full

    if unquoted_path.startswith("/"):
        ctx.errors.append(f"{doc.src_rel}:{line_no}: 相对链接不能以 `/` 开头 {token.href_raw}")
        return token.full

    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(doc.src_rel), unquoted_path))
    target = _resolve_source_target(
        ctx, dst_dir, resolved, is_image=token.is_image, fragment=fragment
    )
    if target is None:
        ctx.errors.append(
            f"{doc.src_rel}:{line_no}: 无法解析的相对链接 {token.href_raw} -> {resolved}"
        )
        return token.full

    target_href, _, _ = target
    return f"{prefix}[{token.label}]({target_href}{title_suffix})"


def _rewrite_backtick_span(token: CodeSpanToken, doc: DocSpec, ctx: SyncContext, line_no: int) -> str:
    if token.ticks != 1:
        return token.full

    raw = token.raw
    m_repo = BACKTICK_REPO_PATH_RE.match(raw)
    if m_repo:
        if raw.startswith("../"):
            resolved_raw = posixpath.normpath(posixpath.join(posixpath.dirname(doc.src_rel), raw))
        else:
            resolved_raw = posixpath.normpath(m_repo.group(1))
    elif (
        raw.endswith(".md")
        and "/" in raw
        and not raw.startswith(("/", ".", "<"))
        and not re.search(r"\s", raw)
        and (ctx.source_root / "knowledge" / raw.split("/", 1)[0]).is_dir()
    ):
        resolved_raw = posixpath.normpath(f"knowledge/{raw}")
    else:
        return token.full

    is_dir_hint = raw.endswith("/")
    resolved = resolved_raw.rstrip("/")
    dst_dir = posixpath.dirname(posixpath.join(ctx.manifest.target_subdir, doc.dst_rel))
    target = _resolve_source_target(ctx, dst_dir, resolved)
    if target is None:
        ctx.errors.append(
            f"{doc.src_rel}:{line_no}: 反引号路径指向不存在的目标 `{raw}` -> {resolved}"
        )
        return token.full

    target_href, in_subset, is_dir = target
    if in_subset:
        display = posixpath.basename(resolved)
    else:
        display = f"{resolved}/" if (is_dir and is_dir_hint) else resolved
    return f"[`{display}`]({target_href})"


def _transform_line(line: str, doc: DocSpec, ctx: SyncContext, line_no: int) -> str:
    parts: list[str] = []
    for token in iter_inline_tokens(line):
        if isinstance(token, TextToken):
            parts.append(token.text)
        elif isinstance(token, CodeSpanToken):
            parts.append(_rewrite_backtick_span(token, doc, ctx, line_no))
        else:
            parts.append(_rewrite_markdown_link(token, doc, ctx, line_no))
    return "".join(parts)


def render_doc(doc: DocSpec, ctx: SyncContext) -> str:
    """Transform a single source document and prepend static read-only banner."""
    raw_text = (ctx.source_root / doc.src_rel).read_text(encoding="utf-8")
    body = strip_frontmatter(raw_text).lstrip("\n")

    transformed_lines: list[str] = []
    for line_no, line, in_fence in iter_lines_with_fence(body):
        if in_fence:
            transformed_lines.append(line)
        else:
            transformed_lines.append(_transform_line(line, doc, ctx, line_no))

    body_out = "\n".join(transformed_lines).rstrip("\n") + "\n"
    source_url = _github_url(ctx.manifest, "blob", doc.src_rel)
    banner = (
        f"> 本文档自动同步自 [y3-maker-config]({source_url})，"
        "请勿直接编辑本文件；如需修改请向源仓库提交 PR。\n\n"
    )
    return banner + body_out


def render_readme(manifest: Manifest, docs: list[DocSpec], source_sha: str) -> str:
    """Render doc/guide/README.md index."""
    short_sha = source_sha[:7]
    repo_url = f"https://github.com/{manifest.source_repo}"
    commit_url = f"{repo_url}/commit/{source_sha}"
    source_dirs = "、".join(
        dict.fromkeys(f"`{g.source_dir}/`" for g in manifest.groups)
    )

    by_group: dict[str, list[DocSpec]] = {}
    for d in docs:
        by_group.setdefault(d.group_id, []).append(d)

    lines = [
        "# Y3 Lua 开发参考文档",
        "",
        (
            f"> 本目录内容自动同步自 [{manifest.source_repo}]({repo_url})"
            "（只读镜像，请勿直接编辑本目录下的文件；如需修改请向源仓库提交 PR）。"
        ),
        "",
        f"{SOURCE_COMMIT_LINE_PREFIX}[`{short_sha}`]({commit_url})",
        f"- **收录数量**：共 {len(docs)} 篇（筛选自 {source_dirs} 中与 Lua 开发直接相关的参考文档）",
        "- **配套入口**：接口签名与枚举查 [API 文档](../API.md)，定制虚拟机差异查 [Lua 虚拟机差异说明](../Lua虚拟机.md)，AI 使用入口见 [`y3-lib`](../skills/y3-lib/SKILL.md)",
        "",
        "## 目录导航",
        "",
    ]

    for group in manifest.groups:
        group_docs = by_group.get(group.id, [])
        lines.extend(
            [
                f"### {group.title}（`{group.target_dir}/`，{len(group_docs)} 篇）",
                "",
                group.description,
                "",
                "| 文档 | 原路径 |",
                "|------|--------|",
            ]
        )
        for doc in group_docs:
            lines.append(f"| [{doc.title}](./{doc.dst_rel}) | `{doc.src_rel}` |")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


def build_outputs(ctx: SyncContext, source_sha: str, docs: list[DocSpec]) -> dict[str, str]:
    """Build all output file contents keyed by path relative to target_subdir."""
    outputs: dict[str, str] = {}
    for doc in docs:
        outputs[doc.dst_rel] = render_doc(doc, ctx)
    outputs["README.md"] = render_readme(ctx.manifest, docs, source_sha)
    return outputs


def validate_outputs(
    outputs: dict[str, str],
    target_root: Path,
    target_subdir: str,
) -> list[str]:
    """Validate forbidden markers (including inside fences) and relative links."""
    errors: list[str] = []
    out_paths = {posixpath.join(target_subdir, rel) for rel in outputs}

    for rel, content in sorted(outputs.items()):
        cur_dir = posixpath.dirname(posixpath.join(target_subdir, rel))
        for line_no, line, in_fence in iter_lines_with_fence(content):
            for marker in FORBIDDEN_MARKERS:
                if marker in line:
                    errors.append(f"{rel}:{line_no}: 包含禁止内容 `{marker}`")
            if in_fence:
                continue

            for token in iter_inline_tokens(line):
                if not isinstance(token, LinkToken):
                    continue
                path_part, _, _ = _split_href(token.href_raw)
                if not path_part or path_part.startswith(SKIP_SCHEMES) or path_part.startswith("#"):
                    continue
                unquoted = urllib.parse.unquote(path_part)
                if unquoted.startswith("/"):
                    errors.append(f"{rel}:{line_no}: 相对链接不能以 `/` 开头 `{token.href_raw}`")
                    continue
                resolved = posixpath.normpath(posixpath.join(cur_dir, unquoted))
                if resolved == ".." or resolved.startswith("../"):
                    errors.append(f"{rel}:{line_no}: 相对链接越出仓库根目录 `{token.href_raw}`")
                elif resolved == target_subdir or resolved.startswith(f"{target_subdir}/"):
                    if resolved not in out_paths:
                        errors.append(f"{rel}:{line_no}: 断链 `{token.href_raw}` -> `{resolved}`")
                elif not (target_root / resolved).exists():
                    errors.append(f"{rel}:{line_no}: 断链 `{token.href_raw}` -> `{resolved}`")
    return errors


def _strip_source_commit_line(text: str) -> str:
    return "\n".join(
        line for line in text.split("\n") if not line.startswith(SOURCE_COMMIT_LINE_PREFIX)
    )


def _diff_target_dir(
    target_guide_root: Path, outputs: dict[str, str]
) -> tuple[list[str], list[str], list[tuple[str, str, str]]]:
    """Compare files on disk under `target_guide_root` against `outputs`."""
    actual_files = {
        p.relative_to(target_guide_root).as_posix(): p
        for p in target_guide_root.rglob("*")
        if p.is_file()
    }
    expected_keys = set(outputs.keys())
    actual_keys = set(actual_files.keys())

    extra = sorted(actual_keys - expected_keys)
    missing = sorted(expected_keys - actual_keys)
    changed: list[tuple[str, str, str]] = []
    for rel in sorted(expected_keys & actual_keys):
        actual_text = normalize_newlines(actual_files[rel].read_text(encoding="utf-8"))
        if actual_text != outputs[rel]:
            changed.append((rel, actual_text, outputs[rel]))
    return extra, missing, changed


def has_meaningful_changes(target_guide_root: Path, outputs: dict[str, str]) -> bool:
    """Return True if sync has changes beyond only refreshing the README commit SHA."""
    if not target_guide_root.is_dir():
        return True

    extra, missing, changed = _diff_target_dir(target_guide_root, outputs)
    if extra or missing:
        return True

    for rel, actual, expected in changed:
        if rel != "README.md" or _strip_source_commit_line(actual) != _strip_source_commit_line(expected):
            return True
    return False


def apply_sync(target_guide_root: Path, outputs: dict[str, str]) -> tuple[int, int]:
    """Write generated files and prune stale files under target_guide_root."""
    target_guide_root.mkdir(parents=True, exist_ok=True)
    written = 0
    for rel, content in sorted(outputs.items()):
        dst = target_guide_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        existing = normalize_newlines(dst.read_text(encoding="utf-8")) if dst.exists() else None
        if existing != content:
            dst.write_text(content, encoding="utf-8", newline="\n")
            written += 1

    expected_set = set(outputs.keys())
    removed = 0
    for path in sorted(target_guide_root.rglob("*"), reverse=True):
        if path.is_file():
            rel = path.relative_to(target_guide_root).as_posix()
            if rel not in expected_set:
                path.unlink()
                removed += 1
        elif path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return written, removed


def check_sync(target_guide_root: Path, outputs: dict[str, str]) -> list[str]:
    """Compare target_guide_root against expected outputs without modifying disk."""
    if not target_guide_root.is_dir():
        return [f"目标目录不存在: {target_guide_root}"]

    extra, missing, changed = _diff_target_dir(target_guide_root, outputs)
    diffs = [f"存在多余文件: {rel}" for rel in extra]
    diffs.extend(f"缺少目标文件: {rel}" for rel in missing)
    diffs.extend(f"内容不一致: {rel}" for rel, _, _ in changed)
    return diffs


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    default_source = Path(__file__).resolve().parents[2]
    default_manifest = Path(__file__).resolve().with_name("manifest.json")
    parser = argparse.ArgumentParser(description="Sync Lua docs from y3-maker-config to y3-lualib")
    parser.add_argument("--source", type=Path, default=default_source, help="Path to y3-maker-config")
    parser.add_argument("--target", type=Path, required=True, help="Path to y3-lualib")
    parser.add_argument("--manifest", type=Path, default=default_manifest, help="Path to manifest.json")
    parser.add_argument("--source-sha", default=None, help="Override source git commit SHA")
    parser.add_argument("--check", action="store_true", help="Verify sync state without writing files")
    parser.add_argument(
        "--skip-if-sha-only",
        action="store_true",
        help="Skip writing if only the README source commit SHA changed",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    source_root = args.source.resolve()
    target_root = args.target.resolve()
    manifest = load_manifest(args.manifest.resolve())
    source_sha = args.source_sha or detect_source_sha(source_root)
    docs = collect_docs(source_root, manifest)
    ctx = SyncContext(
        source_root=source_root,
        target_root=target_root,
        manifest=manifest,
        src_to_dst={d.src_rel: d.dst_rel for d in docs},
        errors=[],
    )

    outputs = build_outputs(ctx, source_sha, docs)
    val_errors = validate_outputs(outputs, target_root, manifest.target_subdir)
    all_errors = ctx.errors + val_errors
    if all_errors:
        prefix = "[CHECK FAIL]" if args.check else "[VALIDATION ERROR]"
        for err in all_errors:
            print(f"{prefix} {err}", file=sys.stderr)
        return 1

    target_guide_root = target_root / manifest.target_subdir
    if args.check:
        diffs = check_sync(target_guide_root, outputs)
        for err in diffs:
            print(f"[CHECK FAIL] {err}", file=sys.stderr)
        if diffs:
            return 1
        print(f"[OK] 检查通过：共 {len(outputs) - 1} 篇文档 + README.md 与源同步且校验无误。")
        return 0

    if args.skip_if_sha_only and not has_meaningful_changes(target_guide_root, outputs):
        print("[SKIP] 仅源提交 SHA 变化，无实质文档改动，跳过写入。")
        return 0

    written, removed = apply_sync(target_guide_root, outputs)
    print(
        f"[OK] 同步完成：共 {len(outputs) - 1} 篇文档 + README.md"
        f"（写入/更新 {written} 个，清理 {removed} 个），校验全部通过。"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
