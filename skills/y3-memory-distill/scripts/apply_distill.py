# apply_distill.py — 蒸馏报告 apply 脚本
# 输入: memory/distill/distill-YYYYMMDD.md (含用户 [x] accept 标记)
# 输出: 修改的目标文件 + session 标记 + apply 日志
# 用法: py -3 .codemaker/skills/y3-memory-distill/scripts/apply_distill.py <distill_file>

import os
import re
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MEMORY_DIR = PROJECT_ROOT / "memory"
SESSIONS_DIR = MEMORY_DIR / "sessions"
DISTILL_DIR = MEMORY_DIR / "distill"
LAST_RUN_FILE = DISTILL_DIR / ".last_run"


def read_text(fpath):
    with open(fpath, 'r', encoding='utf-8-sig') as f:
        return f.read()


def write_text(fpath, content):
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(content)


def parse_distill_report(path):
    """解析蒸馏报告，提取所有 [x] accept 候选"""
    content = read_text(path)
    candidates = []

    # 匹配每个候选块
    blocks = re.split(r'\n### 候选:', content)
    for block in blocks[1:]:
        # 检查是否 accept
        if '[x] accept' not in block:
            continue

        # 提取 file_path
        fp_m = re.search(r'提议落点[：:]\s*`?([^\s`\n]+)`?', block)
        if not fp_m:
            continue
        file_path = fp_m.group(1)

        # 提取 diff
        diff_m = re.search(r'```diff\n(.*?)```', block, re.DOTALL)
        if not diff_m:
            continue
        diff_text = diff_m.group(1)

        # 提取来源 sessions
        src_m = re.search(r'来源 sessions[：:](.*?)\n', block)
        sessions = []
        if src_m:
            sessions = [s.strip() for s in re.findall(r'session-\S+', src_m.group(1))]

        # 提取聚类主题
        topic_m = re.search(r'聚类主题[：:]\s*(\S+)', block)
        topic = topic_m.group(1) if topic_m else 'unknown'

        candidates.append({
            "file_path": file_path,
            "diff": diff_text,
            "sessions": sessions,
            "topic": topic,
        })

    return candidates


def apply_candidate(candidate):
    """应用单个候选 diff 到目标文件"""
    target = PROJECT_ROOT / candidate["file_path"]
    if not target.exists():
        return False, f"目标文件不存在: {target}"

    diff_text = candidate["diff"]
    original = read_text(target)

    # 解析 diff: + 开头的是新增行
    # 简单策略：在文件末尾追加新增内容
    additions = []
    for line in diff_text.split('\n'):
        if line.startswith('+ '):
            additions.append(line[2:])
        elif line.startswith('+'):
            additions.append(line[1:])

    if not additions:
        return False, "diff 中没有新增行"

    new = original.rstrip('\n') + '\n\n---\n\n' + '\n'.join(additions) + '\n'
    write_text(target, new)

    return True, f"已追加 {len(additions)} 行到 {target.name}"


def mark_sessions(sessions, target_path):
    """在来源 session 的 report.md 中标记 [distilled→target]"""
    for session_id in sessions:
        session_dir = SESSIONS_DIR / session_id
        if not session_dir.exists():
            continue
        report = session_dir / "report.md"
        if not report.exists():
            continue
        content = read_text(report)
        marker = f"[distilled→{target_path}]"
        if marker in content:
            continue
        write_text(report, content.rstrip('\n') + f'\n\n{marker}\n')


def main():
    if len(sys.argv) < 2:
        print("用法: py -3 apply_distill.py <distill-YYYYMMDD.md>")
        sys.exit(1)

    distill_path = Path(sys.argv[1])
    if not distill_path.is_absolute():
        distill_path = DISTILL_DIR / distill_path.name
    if not distill_path.exists():
        print(f"文件不存在: {distill_path}")
        sys.exit(1)

    candidates = parse_distill_report(distill_path)
    if not candidates:
        print("未找到 [x] accept 候选，无需 apply")
        return

    print(f"找到 {len(candidates)} 个 accept 候选\n")

    log_entries = []
    for i, cand in enumerate(candidates, 1):
        print(f"[{i}/{len(candidates)}] {cand['topic']} → {cand['file_path']}")
        ok, msg = apply_candidate(cand)
        status = "OK" if ok else "FAIL"
        print(f"  {status}: {msg}")

        if ok:
            mark_sessions(cand["sessions"], cand["file_path"])

        log_entries.append({
            "candidate": i,
            "topic": cand["topic"],
            "target": cand["file_path"],
            "status": status,
            "message": msg,
        })

    # 写 apply 日志
    now = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = DISTILL_DIR / f"apply-{now}.log"
    log_content = f"# Distill Apply Log — {now}\n"
    log_content += f"来源: {distill_path.name}\n"
    log_content += f"应用候选数: {len(candidates)}\n\n"
    for entry in log_entries:
        log_content += f"- [{entry['status']}] {entry['topic']} → {entry['target']}\n"
        log_content += f"  {entry['message']}\n"
    write_text(log_path, log_content)

    # 更新 .last_run
    write_text(LAST_RUN_FILE, datetime.now().isoformat())

    ok_count = sum(1 for e in log_entries if e["status"] == "OK")
    print(f"\n完成: {ok_count}/{len(candidates)} 成功")
    print(f"日志: {log_path}")


if __name__ == "__main__":
    main()
