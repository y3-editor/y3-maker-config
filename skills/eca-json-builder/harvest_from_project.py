# -*- coding: utf-8 -*-
"""用「用户自己工程里的触发器」校验/补全参数类型表——**不需要编辑器源码**。

为什么需要它：`eca_source_data.json` 是维护者从源码派生的**静态分发数据**，
外部用户拿不到源码。但每个 Y3 工程里都有编辑器亲手写出的触发器
（`maps/<地图>/global_trigger/**/*.json`，含官方自带样本 `trigger/UI/*.json`、
`function/ui/*.json`），里面带着真实的 `(arg_type, sub_type)` 组合。

于是可以反过来校验：某个字符串型 sub_type S 在表里只可能属于某个类型 T 时，
样本里 S 出现的 `arg_type` 应当等于 T 的 ID。相等 → 命中确认；不等 → 说明该用户的
引擎构建与分发数据不一致（**这是版本错位最早、最便宜的发现点**）。

用法：
  py -3 harvest_from_project.py --project <工程根>
  py -3 harvest_from_project.py --project <工程根> --repair    # 对唯一候选的冲突项直接改写分发数据

判定口径：
  - 字符串型 sub_type 才能反查类型（整数型 sub_type 在不同类型间大量重复，无法定位）
  - 只有「唯一候选类型」才判定，多候选一律跳过，避免误报
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(SKILL_DIR, "eca_source_data.json")


def collect_sample_pairs(project_root):
    """扫描工程里所有触发器 JSON，收集 (arg_type, sub_type) 组合及其出处。"""
    pairs = {}
    patterns = [
        os.path.join(project_root, "maps", "*", "global_trigger", "**", "*.json"),
        os.path.join(project_root, "maps", "*", "unit", "*.json"),
        os.path.join(project_root, "maps", "*", "ability", "*.json"),
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat, recursive=True))

    def walk(node, path):
        if isinstance(node, dict):
            at, st = node.get("arg_type"), node.get("sub_type")
            if isinstance(at, int) and isinstance(st, str) and st:
                key = (at, st)
                pairs.setdefault(key, set()).add(path)
            for v in node.values():
                walk(v, path)
        elif isinstance(node, list):
            for v in node:
                walk(v, path)

    for f in sorted(set(files)):
        if os.path.basename(f) == "index.txt":
            continue
        try:
            data = json.load(io.open(f, encoding="utf-8"))
        except (ValueError, OSError):
            continue
        walk(data, os.path.relpath(f, project_root).replace(os.sep, "/"))
    return pairs


def build_subtype_index(data):
    """字符串型 sub_type → 声明它的类型列表。"""
    index = {}
    for type_name, info in (data.get("arg_types") or {}).items():
        for sub_name, sub_value in (info.get("sub_types") or {}).items():
            if isinstance(sub_value, str) and sub_value == sub_name:
                index.setdefault(sub_name, []).append(type_name)
    return index


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--project", default=".", help="工程根目录（含 maps/）")
    p.add_argument("--data", default=DATA_PATH, help="eca_source_data.json 路径")
    p.add_argument("--repair", action="store_true",
                   help="对「唯一候选类型」的冲突项，直接改写分发数据里的 ID")
    args = p.parse_args(argv)

    root = os.path.abspath(args.project)
    if not os.path.isdir(os.path.join(root, "maps")):
        raise SystemExit("不是工程根目录（缺 maps/）：%s" % root)
    if not os.path.isfile(args.data):
        raise SystemExit("缺少分发数据：%s\n（请在 skill 分发包中带上 eca_source_data.json）" % args.data)

    data = json.load(io.open(args.data, encoding="utf-8"))
    ids = data.get("arg_type_ids") or {}
    sub_index = build_subtype_index(data)
    pairs = collect_sample_pairs(root)

    confirmed, conflicts, unresolved, dynamic = [], [], [], []
    for (arg_type, sub_name), where in sorted(pairs.items()):
        candidates = sub_index.get(sub_name)
        if not candidates:
            dynamic.append((sub_name, arg_type, sorted(where)[0]))
            continue
        if len(candidates) > 1:
            unresolved.append((sub_name, arg_type, candidates, sorted(where)[0]))
            continue
        tname = candidates[0]
        if ids.get(tname) == arg_type:
            confirmed.append((tname, arg_type, sub_name))
        else:
            conflicts.append((tname, arg_type, ids.get(tname), sub_name, sorted(where)[0]))

    print("工程：%s" % root)
    print("分发数据：%s（源码指纹 %s）" % (args.data, str(data.get("_source", {}).get("sha256"))[:16]))
    print("样本里出现的 (arg_type, 字符串 sub_type) 组合：%d" % len(pairs))
    print()
    print("✅ 确认一致      ：%d" % len(confirmed))
    for tname, at, sub in confirmed[:15]:
        print("     %-24s %s = %s" % (tname, sub, at))
    if len(confirmed) > 15:
        print("     ...（共 %d）" % len(confirmed))
    print()
    print("❌ 与分发数据冲突：%d" % len(conflicts))
    for tname, at, mine, sub, where in conflicts:
        print("     %-24s 样本=%s 分发数据=%s   sub_type=%s  (%s)" % (tname, at, mine, sub, where))
    print()
    print("➖ 多候选无法判定：%d（字符串 sub_type 被多个类型声明，跳过）" % len(unresolved))
    print("➖ 表里未声明    ：%d（多为运行时动态注册，如 *_KV 系列，属正常）" % len(dynamic))

    if conflicts and args.repair:
        for tname, at, mine, sub, where in conflicts:
            old = ids.get(tname)
            if old is not None:
                data["arg_type_ids"][tname] = at
                print("  [repair] %s: %s -> %s" % (tname, old, at))
        io.open(args.data, "w", encoding="utf-8").write(
            json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True))
        print("已改写 %s；请再用 verify_trigger.py 抽验一条触发器确认。" % args.data)
    elif conflicts:
        print("\n提示：加 --repair 可按样本修正（仅对能唯一定位的类型生效）；"
              "修正后请用 verify_trigger.py 抽验，并把结果回报给 skill 维护者更新分发数据。")
    return 0 if not conflicts else 1


if __name__ == "__main__":
    sys.exit(main())
