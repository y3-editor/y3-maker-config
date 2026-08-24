# y3-memory-distill — 核心脚本
# 功能：扫描 sessions + lua-issues → 生成 INDEX.md + 聚类 api_issues.md
# 用法：py -3 .codemaker/skills/y3-memory-distill/scripts/distill.py

import os
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
SESSIONS_DIR = MEMORY_DIR / "sessions"
LUA_ISSUES_DIR = MEMORY_DIR / "lua-issues"
DISTILL_DIR = MEMORY_DIR / "distill"
ARCHIVE_DIR = SESSIONS_DIR / "_archive"
LAST_RUN_FILE = DISTILL_DIR / ".last_run"

# === topic 关键词 → 标签映射 ===
TOPIC_KEYWORDS = {
    "lua-api": ["api_issues", "api 错误", "attempt to call a nil", "不存在", "not found",
                "错误用法", "正确用法", "API", "get_attr", "get_ui", "bind_ability",
                "get_distance", "is_exist", "add_attr", "set_attr", "is_removed",
                "KEY_", "KeyboardKey", "get_child", "set_image", "get_icon",
                "get_cd", "get_max_cd", "set_current_progress_bar_value",
                "y3.ui.get_ui", "y3.ui_prefab", "sync.key", "include ", "module not found",
                "get_abilities_by_type", "remove_ability",
                "AbilityType", "UnitAttr"],
    "lua-trace": ["trace_issues", "traceback", "stack trace", "attempt to index",
                  "nil value", "TypeError", "param-type-mismatch", "undefined-field",
                  "KeyError", "ZeroDivisionError", "崩溃"],
    "ui-gen": ["ui-generator", "ui-pipeline", "UI JSON", "画板", "upui", "prefab",
               "GridView", "ScrollView", "type_17", "type_18", "type_20", "type_25",
               "type_10", "gen_ui_tree", "html_to_y3", "节点树", "import_ui",
               "get_ui_canvas", "网格", "列表", "grid_count", "PARENT MISMATCH"],
    "obj-edit": ["物编", "单位", "技能", "Buff", "魔法效果", "投射物", "物品",
                 "ability_cast", "sight_type", "build_list", "obj-edit",
                 "entity_create_block", "add_point", "add_rect_area"],
    "terrain": ["地形", "terrain", "纹理", "texture", "装饰物", "decoration",
                "聚类", "cv_cluster", "下采样", "泊松", "sampling", "高程",
                "水域", "water", "桥梁", "bridge", "大陆", "continent",
                "terrain_", "纹理组", "texture_group", "山脉", "mountain"],
    "eca": ["ECA", "eca-json", "gen_trigger", "read_trigger", "edit_trigger",
            "var_manager", "plugin_eca", "table_reader", "全局变量",
            "trigger_dict", "arg_type", "op_arg", "variable_dict",
            "GENERIC_UNIT_EVENT", "eca_index", "trigger_level_enable"],
    "template": ["模板", "template", "ReadMe.md", "logic.lua", "导出",
                 "template-export", "三件套", "等级机制", "A级", "B级",
                 "C级", "D级", "Adapter", "DataSchema", "MockAdapter",
                 "difficulty-select", "hud-top-info", "hud-statistic",
                 "hud-main-console", "pick-one-of-many"],
    "auto-test": ["auto-test", "y3runtime", "测试", "trigger_ui_touch",
                  "TC-", "test case", "PASS", "FAIL", "点击"],
    "spec-flow": ["y3-game-spec", "策划案", "执行案", "测试案", "测试报告",
                  "Patch Mode", "Phase 1", "Phase 2", "可行性审查",
                  "feasibility-redlines", "红线", "Gate", "归档", "archive"],
}

TOPIC_TO_SKILL = {
    "lua-api": ["y3-lua-pipeline", "y3-lua-review"],
    "lua-trace": ["y3-lua-pipeline", "y3-lua-review"],
    "ui-gen": ["y3-ui-pipeline", "y3-ui-generator"],
    "obj-edit": ["y3-obj-edit"],
    "terrain": ["y3-gen-terrain-from-image", "y3-terrain-template"],
    "eca": ["eca-json-builder"],
    "template": ["y3-template-export"],
    "auto-test": ["y3-auto-test"],
    "spec-flow": ["y3-game-spec"],
}


def tag_content(text):
    """根据内容打话题标签 — 只取 Top 3"""
    tags = defaultdict(int)
    lower = text.lower()
    for topic, keywords in TOPIC_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in lower:
                tags[topic] += 1
    if not tags:
        return ["general"]
    sorted_tags = sorted(tags.items(), key=lambda x: -x[1])
    # 只取 Top 3 话题
    return [t for t, c in sorted_tags[:3]]


def extract_session_meta(report_path):
    """从 session report 中提取元数据"""
    with open(report_path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    meta = {
        "path": str(report_path.relative_to(MEMORY_DIR)),
        "session_dir": str(report_path.parent.relative_to(MEMORY_DIR)),
        "length": len(text),
    }

    # 日期提取：YYYY-MM-DD 或 YYYY.MM.DD
    date_matches = re.findall(r"(\d{4}[-\.]\d{2}[-\.]\d{2})", text)
    if date_matches:
        try:
            d = date_matches[0].replace(".", "-")
            meta["date"] = datetime.strptime(d, "%Y-%m-%d").date().isoformat()
        except:
            meta["date"] = date_matches[0]

    # 主题提取：首 # 行
    title_m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    meta["title"] = title_m.group(1).strip() if title_m else report_path.parent.name

    # 标签
    meta["topics"] = tag_content(text)

    # 关联 skill
    skills = set()
    for t in meta["topics"]:
        if t in TOPIC_TO_SKILL:
            skills.update(TOPIC_TO_SKILL[t])
    meta["bound_skills"] = sorted(skills)

    # 修改的文件
    files = re.findall(r"(?:`|')([a-zA-Z0-9_\-\.]+\.(?:lua|py|json|md|upui|\S+\.json|\S+\.md))", text)
    # 过滤出看起来像路径的
    file_paths = [f for f in files if "/" in f or "\\" in f or "." in f]
    meta["files_mentioned"] = file_paths[:10]  # 取前十

    # 检测是否有 Lua 错误相关
    meta["has_lua_issues"] = any(
        kw in text for kw in ["attempt to call", "attempt to index", "nil",
                              "错误", "错误用法", "根因", "修复", "traceback",
                              "api_issues", "trace_issues"]
    )

    # 检测是否有物编操作
    meta["has_obj_edit"] = any(
        kw in text for kw in ["物编", "单位", "技能", "Buff", "create_unit",
                              "obj-edit", "add_ability", "build_list"]
    )

    return meta


def scan_all_sessions():
    """扫描所有 session，返回元数据表"""
    sessions = []
    no_report = []

    for session_dir in sorted(SESSIONS_DIR.iterdir()):
        if not session_dir.is_dir():
            continue
        if session_dir.name.startswith("_"):
            continue
        report = session_dir / "report.md"
        if report.exists():
            meta = extract_session_meta(report)
            meta["has_report"] = True
            sessions.append(meta)
        else:
            no_report.append(session_dir.name)

    return sessions, no_report


def build_keyword_index(sessions):
    """建立关键词→session 倒排索引"""
    index = defaultdict(set)
    for s in sessions:
        # 标签作为关键词
        for topic in s["topics"]:
            if topic != "general":
                index[topic].add(s["path"])
        # bound_skill 作为关键词
        for skill in s["bound_skills"]:
            index[skill].add(s["path"])
        # 如果有 lua issues
        if s.get("has_lua_issues"):
            index["lua-issues"].add(s["path"])
    return {k: sorted(v) for k, v in index.items()}


def generate_index_md(sessions, keyword_index, no_report):
    """生成 INDEX.md"""
    lines = [
        "# Memory Sessions 关键词索引",
        "",
        f"> 自动生成: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> Session 总数: {len(sessions)} (有 report) + {len(no_report)} (缺 report)",
        f"> 上次蒸馏: {read_last_run()}",
        "",
        "## 关键词 → 会话",
        "",
    ]

    for keyword in sorted(keyword_index.keys()):
        paths = keyword_index[keyword]
        lines.append(f"### {keyword} ({len(paths)})")
        for p in paths:
            # 取 session dir 名
            sdir = p.split("/")[-2] if "/" in p else p
            lines.append(f"- `{sdir}`")
        lines.append("")

    # 按话题分组
    lines.append("## 按话题分组")
    lines.append("")
    topic_groups = defaultdict(list)
    for s in sessions:
        for t in s["topics"]:
            if t != "general":
                topic_groups[t].append(s)

    for topic in sorted(topic_groups.keys()):
        sess_list = topic_groups[topic]
        lines.append(f"### {topic} ({len(sess_list)} sessions)")
        for s in sorted(sess_list, key=lambda x: x.get("date", ""), reverse=True):
            lines.append(f"- **{s.get('date', '?')}** {s.get('title', s['path'])}")
            if s.get('bound_skills'):
                lines.append(f"  - 🛠 {', '.join(s['bound_skills'])}")
        lines.append("")

    # 缺 report 的
    if no_report:
        lines.append("## ⚠️ 缺失 report 的会话")
        lines.append("")
        for d in no_report:
            lines.append(f"- `{d}`")
        lines.append("")

    lines.append(f"---\n*自动生成 by distill.py*")
    return "\n".join(lines)


def parse_api_issues(path):
    """解析 api_issues.md，提取每个问题条目"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    entries = []
    # 按 ## 数字标题分割（如 ## 1. / ## 2.） 或 ### 标题
    sections = re.split(r"\n(?=##\s\d+[\.\s])", text)

    for section in sections:
        if not section.strip():
            continue

        # 提取小节标题（第一行 ## / ###）
        lines_raw = section.strip().split("\n")
        title = lines_raw[0].lstrip("#").strip() if lines_raw else ""
        title = re.sub(r"^\[[\d\-]+\]\s*", "", title)  # 去掉日期前缀

        # 跳过纯元数据段
        if title in ["记录规范", "Lua Trace 问题归档", "Y3 Lua API 错题集"]:
            continue
        if len(section) < 30:
            continue

        # 提取所有 inline code 和 code block
        all_code = re.findall(r"`([^`]+)`", section)
        lua_blocks = re.findall(r"```lua\n(.*?)```", section, re.DOTALL)

        # 从代码中提取 API 调用
        api_bases = set()
        for block in lua_blocks:
            # y3.xxx / xxx:method / xxx.method
            found = re.findall(r"(?:y3\.)?([a-zA-Z_]+:[a-zA-Z_]+(?:\([^)]*\))?)", block)
            found += re.findall(r"(?:y3\.)([a-zA-Z_]+\.[a-zA-Z_]+)", block)
            found += re.findall(r"([a-zA-Z_]+\([^)]*\))", block)
            for api in found:
                # 去掉 (stuff) 只留 base
                base = re.sub(r"\(.*", "", api)
                if base in ["if", "then", "end", "local", "function", "return", "for", "do", "not", "and", "or"]:
                    continue
                api_bases.add(base)

        # 标准 API 名
        canonical = set()
        for base in api_bases:
            c = _canonical_api(base)
            if c:
                canonical.add(c)

        if not canonical:
            continue

        entries.append({
            "title": title,
            "apis": sorted(canonical),
            "has_code": len(lua_blocks) > 0,
        })

    return entries


def _canonical_api(base):
    """Normalize API name to canonical form for clustering"""
    apis = [
        "y3.ui.get_ui", "get_child", "bind_ability", "set_image", "get_icon",
        "get_cd", "get_max_cd", "set_current_progress_bar_value",
        "y3.ui_prefab.create", "is_exist", "is_alive", "get_attr",
        "set_attr", "get_distance_with", "reborn", "move_to_pos",
        "add_fast_event", "get_abilities_by_type", "remove_ability",
        "add_ability", "find_ability", "add_attr", "set_attr",
        "get_point", "get_name", "get_ui", "set_visible",
        "get_width", "set_ui_size", "KeyboardKey", "UnitAttr",
        "AbilityType", "sync.key", "display_message",
        "game:event", "ltimer.wait_frame",
    ]
    for api in apis:
        if base in api or api in base:
            return api
    return base if len(base) > 3 else None


def cluster_api_issues(entries):
    """按 API 家族聚类"""
    by_api = defaultdict(list)
    for e in entries:
        for api in e.get("apis", []):
            by_api[api].append(e)

    clusters = {}
    for api, items in by_api.items():
        if len(items) >= 2:
            clusters[api] = {
                "api": api,
                "count": len(items),
                "entries": items,
                "status": "临界" if len(items) >= 3 else "关注",
            }

    return clusters


def generate_distill_report(sessions, keyword_index, api_clusters):
    """生成蒸馏报告"""
    today = datetime.now().strftime("%Y%m%d")
    lines = [
        f"# Memory Distill 报告 — {today}",
        "",
        f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> Session 总数: {len(sessions)}",
        f"> 识别候选: {len(api_clusters)} API 聚类 + 待评估话题聚类",
        "",
        "## Step 1 — 扫描结果",
        "",
        "| 话题 | Session 数 | 关联 Skill |",
        "|------|-----------|-----------|",
    ]

    topic_counts = defaultdict(int)
    topic_skills = {}
    for s in sessions:
        for t in s["topics"]:
            if t != "general":
                topic_counts[t] += 1
                if t not in topic_skills:
                    topic_skills[t] = set()
                if s.get("bound_skills"):
                    topic_skills[t].update(s["bound_skills"])

    for topic in sorted(topic_counts.keys()):
        count = topic_counts[topic]
        skills = ", ".join(sorted(topic_skills.get(topic, set())))
        lines.append(f"| {topic} | {count} | {skills} |")
    lines.append("")

    # Step 2 — API 聚类
    lines.append("## Step 2 — API 问题聚类")
    lines.append("")
    if api_clusters:
        for api, cluster in sorted(api_clusters.items()):
            lines.append(f"### 候选: {api} ({cluster['count']} 次)")
            lines.append(f"- **状态**: {cluster['status']}")
            lines.append(f"- **提议落点**: `skills/y3-lua-pipeline/references/api_errors.md`")
            lines.append(f"- **用户决策**: [ ] accept  [ ] reject  [ ] defer")
            lines.append("")
            for e in cluster["entries"]:
                lines.append(f"  - {e['title']}")
            lines.append("")
    else:
        lines.append("无聚类候选（所有 API 错误 ≤1 次出现）")
        lines.append("")

    # Step 3 — 话题模式检测
    lines.append("## Step 3 — 话题模式检测")
    lines.append("")

    high_freq_topics = [(t, c) for t, c in topic_counts.items() if c >= 3]
    if high_freq_topics:
        for topic, count in sorted(high_freq_topics, key=lambda x: -x[1]):
            skills = ", ".join(sorted(topic_skills.get(topic, set())))
            lines.append(f"### 候选: {topic} ({count} sessions)")
            dest = f"knowledge/{topic}/" if skills else "待定"
            lines.append(f"- **关联 skill**: {skills}")
            lines.append(f"- **提议落点**: `{dest}`")
            lines.append(f"- **用户决策**: [ ] accept  [ ] reject  [ ] defer")
            lines.append("")
    else:
        lines.append("无高频话题（< 3 sessions）")

    lines.append("")
    lines.append("---")
    lines.append(f"*自动生成 by distill.py*")
    return "\n".join(lines)


def read_last_run():
    if LAST_RUN_FILE.exists():
        return LAST_RUN_FILE.read_text().strip()
    return "从未运行"


def write_last_run():
    DISTILL_DIR.mkdir(parents=True, exist_ok=True)
    LAST_RUN_FILE.write_text(datetime.now().isoformat())


def main():
    print("=" * 60)
    print("Y3 Memory Distill v0.2")
    print("=" * 60)
    print(f"项目根目录: {PROJECT_ROOT}")
    print(f"Memory 目录: {MEMORY_DIR}")
    print(f"上次运行: {read_last_run()}")
    print()

    # Step 1: 扫描
    print("[Step 1] 扫描 Session 报告...")
    sessions, no_report = scan_all_sessions()
    print(f"  有报告: {len(sessions)} 个")
    print(f"  缺报告: {len(no_report)} 个")
    if no_report:
        for d in no_report:
            print(f"    ⚠️ {d}")
    print()

    # Step 1.5: 解析 lua-issues
    print("[Step 1.5] 解析 lua-issues...")
    api_entries = []
    api_path = LUA_ISSUES_DIR / "api_issues.md"
    if api_path.exists():
        api_entries = parse_api_issues(api_path)
        print(f"  提取 {len(api_entries)} 条 API 错题")
    else:
        print(f"  ⚠️ {api_path} 不存在")
    print()

    # Step 2: 建索引 + 聚类
    print("[Step 2] 建倒排索引...")
    keyword_index = build_keyword_index(sessions)
    print(f"  关键词: {len(keyword_index)} 个")
    for kw, paths in sorted(keyword_index.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"    {kw}: {len(paths)} sessions")
    print()

    print("[Step 2.x] 聚类 API 问题...")
    api_clusters = cluster_api_issues(api_entries)
    multitouch = {k: v for k, v in api_clusters.items() if v["count"] >= 2}
    print(f"  高频 API 问题: {len(multitouch)} 个")
    for api, c in sorted(multitouch.items()):
        print(f"    {api}: {c['count']} 次")
    print()

    # Step 3: 生成输出
    print("[Step 3] 生成 INDEX.md ...")
    index_md = generate_index_md(sessions, keyword_index, no_report)
    index_path = SESSIONS_DIR / "INDEX.md"
    index_path.write_text(index_md, encoding="utf-8")
    print(f"  ✅ {index_path}")
    print()

    print("[Step 3.x] 生成蒸馏报告 ...")
    distill_md = generate_distill_report(sessions, keyword_index, multitouch)
    distill_path = DISTILL_DIR / f"distill-{datetime.now().strftime('%Y%m%d')}.md"
    distill_path.write_text(distill_md, encoding="utf-8")
    print(f"  ✅ {distill_path}")
    print()

    # Step 4: 摘要
    print("=" * 60)
    print("摘要")
    print("=" * 60)
    print(f"Session 总数: {len(sessions)}")
    print(f"关键词数: {len(keyword_index)}")
    # 话题计数（local copy from generate_distill_report 的扫描逻辑）
    _tc = defaultdict(int)
    for s in sessions:
        for t in s["topics"]:
            if t != "general":
                _tc[t] += 1

    print(f"API 聚类候选: {len(multitouch)} -> 需用户审阅")
    print(f"话题模式候选: {sum(1 for _, c in _tc.items() if c >= 3)} -> 需用户审阅")
    for t, c in sorted(_tc.items(), key=lambda x: -x[1]):
        if c >= 3:
            print(f"  {t}: {c} sessions")
    print()
    print("生成文件:")
    print(f"  INDEX.md -> {index_path}")
    print(f"  distill report -> {distill_path}")
    print()
    print("⚠️ 蒸馏报告中的候选需要你逐条 accept/reject/defer")
    print()

    # 记录时间戳
    write_last_run()
    print("✅ 完成")


if __name__ == "__main__":
    main()
