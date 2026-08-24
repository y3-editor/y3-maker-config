# _health_check.py — Skill / Rule / Memory 健康度自检
# 用法：py -3 .codemaker/skills/_health_check.py
# 输出：stdout 报告

import os
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = PROJECT_ROOT / "skills"
RULES_DIR = PROJECT_ROOT / "rules"
MEMORY_DIR = PROJECT_ROOT / "memory"
TEMPLATES_DIR = PROJECT_ROOT / "templates"

NOW = datetime.now().strftime("%Y%m%d")

# 内部工具目录，不要求 SKILL.md
INTERNAL_SKILLS = {"y3-memory-distill"}


def read_text(fpath):
    with open(fpath, 'r', encoding='utf-8-sig', errors='replace') as f:
        return f.read()


def is_text_file(fpath):
    """快速判断是否为文本文件（读前 512 字节，无 null 字节）"""
    try:
        with open(fpath, 'rb') as f:
            chunk = f.read(512)
        return b'\x00' not in chunk and len(chunk) > 0
    except Exception:
        return False


def count_lines(fpath):
    with open(fpath, 'r', encoding='utf-8-sig', errors='replace') as f:
        return sum(1 for _ in f)


# ── 1. U+FFFD ──────────────────────────────────
def check_ufffd():
    issues = []
    for root, _, files in os.walk(PROJECT_ROOT):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in ('.md', '.mdc', '.lua', '.json', '.py'):
                continue
            fpath = os.path.join(root, fname)
            if not is_text_file(fpath):
                continue
            c = read_text(fpath)
            if '\ufffd' not in c:
                continue
            rel = os.path.relpath(fpath, PROJECT_ROOT)
            for i, line in enumerate(c.split('\n'), 1):
                if '\ufffd' in line:
                    issues.append(f"{rel}:{i}: {line[:60].strip()}")
                    break
    return issues


# ── 2. SKILL.md 必备段落 ─────────────────────────
def check_skill_essentials():
    issues = []
    for sd in sorted(SKILLS_DIR.iterdir()):
        if not sd.is_dir() or sd.name.startswith('_'):
            continue
        if sd.name in INTERNAL_SKILLS:
            continue
        skill_md = sd / "SKILL.md"
        if not skill_md.exists():
            issues.append(f"{sd.name}: MISSING SKILL.md")
            continue
        c = read_text(skill_md)
        if not c.startswith('---'):
            issues.append(f"{sd.name}: 缺少 YAML frontmatter")
        if not re.search(r'触发|trigger|ALWAYS use this skill when', c, re.I):
            issues.append(f"{sd.name}: 缺少触发词")
        if not re.search(r'工作流|workflow|流程|步骤|Step', c, re.I):
            issues.append(f"{sd.name}: 缺少工作流说明")
    return issues


# ── 3. references 行数 ─────────────────────────
def check_references_size():
    issues = []
    for sd in sorted(SKILLS_DIR.iterdir()):
        if not sd.is_dir() or sd.name.startswith('_'):
            continue
        ref_dir = sd / "references"
        if not ref_dir.exists():
            continue
        for fpath in ref_dir.iterdir():
            if fpath.suffix not in ('.md', '.mdc'):
                continue
            n = count_lines(fpath)
            if n > 500:
                issues.append(f"{sd.name}/references/{fpath.name}: {n} 行 > 500!")
            elif n > 400:
                issues.append(f"{sd.name}/references/{fpath.name}: {n} 行 (接近 500)")
    return issues


# ── 4. rules 索引一致性 ─────────────────────────
def check_rules_index():
    issues = []
    rules_md = RULES_DIR / "rules.mdc"
    if not rules_md.exists():
        issues.append("rules.mdc 不存在")
        return issues

    c = read_text(rules_md)
    m_section = re.search(r'##\s*📁\s*规则文件索引\s*\n((?:\|.*\n)+)', c)
    if not m_section:
        issues.append("找不到「规则文件索引」表格")
        return issues

    table_lines = m_section.group(1).strip().split('\n')
    indexed = set()
    for line in table_lines:
        m = re.match(r'\|\s*`([^`]+)`\s*\|', line)
        if m:
            indexed.add(m.group(1))

    actual = {f.name for f in RULES_DIR.iterdir() if f.suffix in ('.mdc', '.json')}

    for fname in actual - indexed:
        issues.append(f"文件存在但索引未列出: {fname}")
    for fname in indexed - actual:
        if fname == 'spec-config.json':
            if not (PROJECT_ROOT / 'spec-config.json').exists():
                issues.append(f"索引引用 {fname} 但文件不存在")
        elif fname in ('skills/*/SKILL.md', "knowledge/UI系统/03-官方组件.md"):
            continue  # 非 rules/ 目录引用，非此检查项
        else:
            issues.append(f"索引引用不存在的文件: {fname}")

    return issues


# ── 5. 内部死链 ──────────────────────────────────
def check_dead_links():
    issues = []
    # 白名单：ASCII 流程图中的伪链接（不是真 markdown 链接）
    # 这些是文档中预期存在但尚未生成的文件
    PSEUDO_PATTERNS = {
        '设计案.md', '执行案.md', '测试案.md', '测试报告.md',
    }
    for root, _, files in os.walk(PROJECT_ROOT):
        rel_root = os.path.relpath(root, PROJECT_ROOT).replace('\\', '/')
        if rel_root.startswith(('memory/sessions', 'memory/distill')):
            continue
        for fname in files:
            if not fname.endswith(('.md', '.mdc')):
                continue
            fpath = os.path.join(root, fname)
            c = read_text(fpath)
            for m in re.finditer(r'\]\(([^)\s]+\.md[c]?)\)', c):
                link = m.group(1)
                if not link or link.startswith('http'):
                    continue
                name = os.path.basename(link)
                if name in PSEUDO_PATTERNS:
                    continue
                base = os.path.dirname(fpath)
                target = os.path.normpath(os.path.join(base, link))
                if not os.path.exists(target):
                    rel = os.path.relpath(fpath, PROJECT_ROOT)
                    issues.append(f"{rel} → {link}")
                    if len(issues) >= 15:
                        return issues
    return issues


# ── 6. 模板 ReadMe ──────────────────────────────
def check_template_readme():
    issues = []
    readme = TEMPLATES_DIR / "ReadMe.md"
    if not readme.exists():
        issues.append("templates/ReadMe.md 不存在")
        return issues
    c = read_text(readme)
    if 'A 级' not in c:
        issues.append("缺少 A 级模板说明")
    if 'B 级' not in c:
        issues.append("缺少 B 级模板说明")
    if '接入' not in c:
        issues.append("缺少接入步骤说明")
    return issues


# ── 7. lua issues 条目 ──────────────────────────
def check_lua_issues():
    issues = []
    for name in ('api_issues.md', 'trace_issues.md'):
        fpath = MEMORY_DIR / "lua-issues" / name
        if not fpath.exists():
            issues.append(f"lua-issues/{name} 不存在")
    return issues


def main():
    print("=" * 60)
    print(f"  Y3 Agent Health Check — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    checks = [
        ("U+FFFD scan", check_ufffd),
        ("SKILL essentials", check_skill_essentials),
        ("References size", check_references_size),
        ("Rules index", check_rules_index),
        ("Dead links", check_dead_links),
        ("Template ReadMe", check_template_readme),
        ("Lua Issues", check_lua_issues),
    ]

    all_ok = True
    for name, fn in checks:
        res = fn()
        if res:
            print(f"\nFAIL {name} — {len(res)} issue(s):")
            for r in res:
                print(f"  - {r}")
            all_ok = False
        else:
            print(f"PASS {name}")

    print("\n" + "=" * 60)
    if all_ok:
        print("  ALL GREEN")
    else:
        print("  ISSUES FOUND")
    print("=" * 60)


if __name__ == "__main__":
    main()
