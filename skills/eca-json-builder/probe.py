# -*- coding: utf-8 -*-
"""探针法自动化：一次问编辑器「哪些候选写法能活下来」。

实战中为了定位 `ARITHMETIC_OPERATION` / `UNIT_TYPE_COMPARE` 等写法，
手工造了 17 个探针触发器、跑了 4 轮「导入→保存→回读」。这个脚本把整轮压成一条命令。

用法：
  py -3 probe.py <探针DSL.json> [--map EntryMap] [--root <工程根>] [--keep]

探针 DSL（与 `gen_trigger.py` 同格式，每个 trigger 就是一个候选写法）：
{
  "map": "EntryMap",
  "triggers": [
    {"name": "探针A-整数运算", "id": 1900000001, "event": [["INIT_FINISHED"]],
     "action": [["SET_VARIABLE", {"var":"金币","type":"INTEGER","scope":"global"},
                 ["MATH_OPERATION", {"var":"金币","type":"INTEGER","scope":"global"}, "+", 1]]]},
    {"name": "探针B-另一种写法", "id": 1900000002, "...": "..."}
  ]
}

输出：每个候选的 valid 标记 + 被编辑器清空/丢弃的字段路径 + 「可用 / 作废」判定。
默认跑完删除探针文件（编辑器内存里仍保留条目，重启编辑器后消失）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import time

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

import eca_json_helper  # noqa: E402
import gen_trigger  # noqa: E402
import mcp_client  # noqa: E402
import verify_trigger  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def remove_probe(path, trig_dir):
    """删掉探针文件并同步 index.txt（编辑器内存里的条目需重启才消失）。"""
    idx_path = os.path.join(trig_dir, "index.txt")
    fname = os.path.basename(path)
    if os.path.isfile(path):
        os.remove(path)
    if os.path.isfile(idx_path):
        with open(idx_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
        if idx.pop(fname, None) is not None:
            with open(idx_path, "w", encoding="utf-8") as f:
                json.dump(idx, f, ensure_ascii=False, indent=4)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("dsl", help="探针 DSL JSON")
    parser.add_argument("--map", default=None, help="默认取 DSL 里的 map")
    parser.add_argument("--root", default=None)
    parser.add_argument("--keep", action="store_true", help="保留探针文件")
    parser.add_argument("--no-lint", action="store_true", help="跳过本地 lint（只想问编辑器时）")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root) if args.root else mcp_client.find_project_root(args.dsl)
    if not root:
        print("找不到工程根目录，请用 --root 指定", file=sys.stderr)
        return 2
    with open(args.dsl, "r", encoding="utf-8") as f:
        dsl = json.load(f)
    map_name = args.map or dsl.get("map", "EntryMap")
    trig_dir = os.path.join(root, "maps", map_name, "global_trigger", "trigger")

    # 0) 先把编辑器当前修改落盘 —— 必须在生成探针文件**之前**做：
    #    save_editor 会以编辑器内存为准**裁剪**磁盘上未 import 过的触发器
    #    （实测：先 import+保存 A，磁盘上的 B 会被删除并移出 index.txt）。
    try:
        verify_trigger.call_editor("save_editor", root=root, expect_json=False)
        time.sleep(1.5)  # 保存异步落盘：紧接着导入会被编辑器丢弃（实测）
    except Exception as exc:  # noqa: BLE001
        print("MCP 调用失败（编辑器是否在运行？）：%s" % exc, file=sys.stderr)
        return 2

    # 1) 生成探针触发器（与正式流程同一套生成器）
    code = gen_trigger.main([args.dsl, "--root", root])
    if code != 0:
        return code

    names = [t.get("name") for t in dsl.get("triggers", []) if t.get("name")]
    paths = [os.path.join(trig_dir, name + ".json") for name in names]
    snaps = {p: verify_trigger.snapshot(p)[1] for p in paths if os.path.isfile(p)}

    # 2) 先把所有候选逐个 import，再统一保存（中途不要保存，否则未 import 的会被裁剪）
    rows = []
    try:
        imports = {}
        for path in paths:
            if not os.path.isfile(path):
                continue
            imports[path] = verify_trigger.import_trigger(path, root, flush_first=False)
        verify_trigger.flush(root)
    except Exception as exc:  # noqa: BLE001
        print("MCP 调用失败（编辑器是否在运行？）：%s" % exc, file=sys.stderr)
        return 2

    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        snap = snaps.get(path)
        if snap is None:
            rows.append((name, None, ["探针文件不存在"], "作废（生成失败）"))
            continue
        result = verify_trigger.inspect(snap, path)
        if imports.get(path) is not None and imports[path].get("success") is not True:
            result["diff"] = list(result["diff"]) + ["import_eca 未返回 success：%s" % imports[path]]
            result["ok"] = False
        if not args.no_lint and os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            errors, _warnings = [], []
            eca_json_helper._lint_editor_rejected_encodings(data, "$", errors, _warnings, path)
            if errors:
                result["diff"] = list(result["diff"]) + ["[lint] " + e for e in errors]
                result["ok"] = False
        verdict = "可用" if result["ok"] else (
            "作废（被清空/丢弃/写法有误）" if result["diff"] else "作废（valid=false）")
        rows.append((name, result["valid"], result["diff"], verdict))
        if not args.keep:
            remove_probe(path, trig_dir)

    print("\n==== 探针结果（%d 个候选） ====" % len(rows))
    for name, valid, diffs, verdict in rows:
        print("- %s | valid=%s | %s" % (name, valid, verdict))
        for item in diffs[:4]:
            print("    %s" % item)
    if not args.keep:
        print("\n探针文件已删除并同步 index.txt；编辑器内存里仍保留这些条目，"
              "继续正式导入前请先 restart_editor(save_before_restart=false)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
