# -*- coding: utf-8 -*-
"""生成「物编技能触发器」容器骨架文件 —— 这是 edit_trigger.py --container ability 的前置步骤。

背景：技能触发器存放在 `maps/<地图>/ability/<技能Key>.json`，与物编数据
（`maps/<地图>/editor_table/abilityall/<技能Key>.json`）是两个文件。
`edit_trigger.py --container ability --key <技能Key>` **要求容器文件已存在**
（不存在时直接报 `ability file not found`），而编辑器只在「某个技能被挂上触发器」时才创建它。
本脚本负责补上这一步：写出与编辑器一致的 194 字节空骨架，之后就能用 edit_trigger 填内容。

用法：
  py -3 gen_ability_trigger.py --map EntryMap --keys 100001001,100001002
  py -3 gen_ability_trigger.py --map EntryMap --keys 100001001 --force   # 覆盖已有非空文件
  py -3 gen_ability_trigger.py --map EntryMap --keys-file keys.txt

退出码：0 成功；1 有文件被跳过/出错。
"""
from __future__ import annotations
import argparse
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 与编辑器实际写出的空容器完全一致（顺序也保持一致，便于 diff）
SKELETON = {
    "local_variable": {},
    "trigger_dict": {},
    "trigger_group_info": [],
    "trigger_version": "1.2",
    "variable_dict": {},
    "variable_group_info": [],
    "variable_length_dict": {},
}


def find_project_root(start: str | None = None) -> str:
    cur = os.path.abspath(start or os.getcwd())
    while True:
        if os.path.isdir(os.path.join(cur, "maps")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise SystemExit("error: 找不到工程根（向上找不到 maps 目录），请用 --root 指定")
        cur = parent


def is_empty_container(data: dict) -> bool:
    """只认「空骨架」为可安全覆盖的对象。"""
    return (not data.get("trigger_dict")
            and not data.get("trigger_group_info")
            and not data.get("local_variable"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="生成物编技能触发器容器骨架")
    ap.add_argument("--map", default="EntryMap", help="地图名（默认 EntryMap）")
    ap.add_argument("--keys", help="技能 Key，逗号分隔，如 100001001,100001002")
    ap.add_argument("--keys-file", help="从文本文件读技能 Key（每行一个，# 开头为注释）")
    ap.add_argument("--root", default=None, help="工程根（默认自动向上查找 maps 目录）")
    ap.add_argument("--force", action="store_true",
                    help="即使容器已含触发器也覆盖（默认跳过，避免抹掉已有内容）")
    args = ap.parse_args(argv)

    keys: list[str] = []
    if args.keys:
        keys += [k.strip() for k in args.keys.split(",") if k.strip()]
    if args.keys_file:
        with open(args.keys_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.split("#", 1)[0].strip()
                if line:
                    keys.append(line)
    if not keys:
        ap.error("请用 --keys 或 --keys-file 指定至少一个技能 Key")

    root = args.root or find_project_root()
    out_dir = os.path.join(root, "maps", args.map, "ability")
    os.makedirs(out_dir, exist_ok=True)

    rc = 0
    for key in keys:
        path = os.path.join(out_dir, key + ".json")
        if os.path.isfile(path) and not args.force:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                if not is_empty_container(existing):
                    print(f"skip {key}: 已含触发器内容（要覆盖请加 --force）")
                    rc = 1
                    continue
            except Exception as exc:  # noqa: BLE001 - 读不动就当作不可安全覆盖
                print(f"skip {key}: 读不出内容（{exc}），要覆盖请加 --force")
                rc = 1
                continue
        with open(path, "w", encoding="utf-8") as f:
            json.dump(SKELETON, f, ensure_ascii=False, indent=2)
        print(f"OK  {key} -> {path}")

    print(f"\n下一步：py -3 edit_trigger.py <触发器DSL.json> --container ability --key <技能Key>")
    return rc


if __name__ == "__main__":
    sys.exit(main())
