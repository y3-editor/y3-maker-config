# -*- coding: utf-8 -*-
"""把 MCP 创建的逻辑节点改成语义化中文名（logicres.json + editor/existingmodelinfo.json）。

为什么需要脚本：两个文件序列化口径不同，手改会破坏格式。

| 文件 | 格式 |
|------|------|
| `maps/<地图>/logicres.json` | UTF-8 无 BOM、LF、4 空格缩进、`ensure_ascii=True` |
| `maps/<地图>/editor/existingmodelinfo.json` | UTF-8 无 BOM、**CRLF**、1 空格缩进、`ensure_ascii=True` |

改完必须让编辑器重读盘：`restart_editor(save_before_restart=false)`。
中间只要插一次 `save_editor`，编辑器内存里的旧名字就会把盘上的改名顶回去。
本脚本默认会调用这次重启（`--no-restart` 可跳过）。

用法：
    py -3 rename_logic_nodes.py --rename "10000=英雄出生点,10001=刷怪点-左上"
    py -3 rename_logic_nodes.py --names-file names.json
    py -3 rename_logic_nodes.py --names-file names.json --dry-run

names.json 格式：`{"10000": "英雄出生点", "10001": "刷怪点-左上"}`

退出码：0 成功；1 校验失败 / 节点缺失 / 重启失败。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", "eca-json-builder"))
sys.path.insert(0, BUILDER_DIR)


def find_root(start=None):
    cur = os.path.abspath(start or os.getcwd())
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, "maps")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(start or os.getcwd())


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def dump_lf(obj):
    text = json.dumps(obj, indent=4, separators=(", ", ": "), ensure_ascii=True)
    return text.encode("utf-8")


def dump_crlf(obj):
    text = json.dumps(obj, indent=1, separators=(", ", ": "), ensure_ascii=True)
    return text.replace("\n", "\r\n").encode("utf-8")


def verify(path, dump):
    raw = read_bytes(path)
    obj = json.loads(raw.decode("utf-8"))
    out = dump(obj)
    if raw != out:
        raise SystemExit(
            "[!] 格式复现校验失败，拒绝改写：%s\n"
            "    原文 %d 字节 / 复现 %d 字节\n"
            "    原文尾 %r\n    复现尾 %r"
            % (path, len(raw), len(out), raw[-40:], out[-40:])
        )
    return obj


def parse_rename(text):
    names = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise SystemExit("[!] --rename 格式应为 res_id=名字，出错项：%s" % part)
        rid, name = part.split("=", 1)
        names[int(rid.strip())] = name.strip()
    return names


def main():
    ap = argparse.ArgumentParser(description="逻辑节点改名（logicres + existingmodelinfo）")
    ap.add_argument("--map", dest="map_name", default="EntryMap")
    ap.add_argument("--root", default=None)
    ap.add_argument("--rename", default=None, help="10000=名字,10001=名字")
    ap.add_argument("--names-file", default=None, help="JSON：{res_id: 名字}")
    ap.add_argument("--group", default="1024", help="logicres 顶层分组键，默认 1024")
    ap.add_argument("--no-restart", action="store_true", help="只改盘，不调用重启")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.names_file:
        with open(args.names_file, "r", encoding="utf-8") as fh:
            names = {int(k): v for k, v in json.load(fh).items()}
    elif args.rename:
        names = parse_rename(args.rename)
    else:
        ap.error("请用 --rename 或 --names-file 提供改名表")
    if not names:
        ap.error("改名表为空")

    root = find_root(args.root)
    logicres = os.path.join(root, "maps", args.map_name, "logicres.json")
    modelinfo = os.path.join(root, "maps", args.map_name, "editor", "existingmodelinfo.json")
    for path in (logicres, modelinfo):
        if not os.path.isfile(path):
            raise SystemExit("[!] 找不到文件：%s" % path)

    logic = verify(logicres, dump_lf)
    info = verify(modelinfo, dump_crlf)

    group = logic.get(args.group)
    if not isinstance(group, dict):
        raise SystemExit("[!] logicres.json 缺少分组 %r（现有：%s）"
                         % (args.group, list(logic)[:10]))

    missing = [rid for rid in names if str(rid) not in group]
    if missing:
        raise SystemExit("[!] logicres.json 缺少节点：%s" % missing)

    print("工程根：%s" % root)
    print("改名计划（%d 个）：" % len(names))
    for rid, name in sorted(names.items()):
        old = group[str(rid)].get("name")
        print("   %-8s %-18s -> %s" % (rid, old, name))
    if args.dry_run:
        print("\n(--dry-run) 未写入")
        return 0

    for rid, name in names.items():
        group[str(rid)]["name"] = name

    model_hits = {rid: 0 for rid in names}
    for item in info:
        items = item.get("items")
        if not items or len(items) < 3:
            continue
        rid, kind = items[0], items[2]
        if rid in names and str(kind) == str(args.group):
            items[1] = names[rid]
            model_hits[rid] += 1

    holes = [rid for rid, n in model_hits.items() if n == 0]
    if holes:
        raise SystemExit("[!] existingmodelinfo.json 里找不到这些节点，未写入：%s" % holes)

    with open(logicres, "wb") as fh:
        fh.write(dump_lf(logic))
    print("[写盘] %s" % logicres)
    with open(modelinfo, "wb") as fh:
        fh.write(dump_crlf(info))
    print("[写盘] %s（%d 条）" % (modelinfo, sum(model_hits.values())))

    if args.no_restart:
        print("\n[!] 已跳过重启。请立刻手动执行 restart_editor(save_before_restart=false)，")
        print("    并在那之前不要调用 save_editor，否则编辑器会用旧名字顶回盘上内容。")
        return 0

    try:
        from mcp_client import editor_client  # noqa: E402
        client = editor_client(root)
        print("\n[重启] restart_editor(save_before_restart=false) ...")
        client.call("restart_editor", {"save_before_restart": False})
        print("[重启] 已下发，等待编辑器重新打开地图")
        time.sleep(8.0)
    except Exception as exc:  # noqa: BLE001
        print("\n[!] 重启失败：%s" % str(exc)[:200])
        print("    改名已写盘，但编辑器内存仍是旧名。")
        print("    请立刻手动 restart_editor(save_before_restart=false)，中间不要 save_editor。")
        return 1

    print("\n完成。下一步建议：重新打开地图后 save_editor 一次，把改名固化进编辑器。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
