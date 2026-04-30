#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_round4_csv.py — Round 4 Step 4.3: 更新 decoration_grid.csv(v1→v2 final)

将 AI 识别的桥梁和树木追加到 decoration_grid.csv（已包含 Round 2 的山峰）。

用法:
  python gen_round4_csv.py \
    --decoration-csv <dir>/decoration_grid.csv \
    --bridges '[{"x":33,"z":10},{"x":34,"z":20}]' \
    --trees '[{"x":52,"z":8},{"x":54,"z":9}]' \
    --bridge-model-id 100301 \
    --tree-model-id 100302 \
    --output-dir <dir>

参数:
  --bridges: 桥梁位置 JSON 或文件，每个元素包含 x, z（可选 model_id）
  --trees: 树木位置 JSON 或文件，支持两种格式:
           - 单点: {"x":52, "z":8}
           - 矩形区域: {"x1":50, "z1":2, "x2":58, "z2":10}（自动展开为区域内每个格子）
           每个元素可选 model_id
  两者均可选，不传则不追加
"""

import json
import sys
import os
import csv
import argparse


def parse_json_or_file(value, label="参数"):
    """解析 JSON 字符串或文件路径"""
    if value is None:
        return []
    if os.path.isfile(value):
        with open(value, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            print(f"[ERROR] {label} 既不是有效文件也不是有效 JSON: {e}")
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Round 4 Step 4.3 — 更新 decoration_grid.csv(v2 final)")
    parser.add_argument("--decoration-csv", required=True,
                        help="decoration_grid.csv(v1) 路径（包含山峰）")
    parser.add_argument("--bridges", default=None,
                        help='桥梁位置 JSON 或文件, 如 \'[{"x":33,"z":10}]\'')
    parser.add_argument("--trees", default=None,
                        help='树木位置 JSON 或文件, 如 \'[{"x":52,"z":8}]\'')
    parser.add_argument("--bridge-model-id", type=int, default=100301,
                        help="默认桥梁模型 ID (默认 100301)")
    parser.add_argument("--tree-model-id", type=int, default=100302,
                        help="默认树木模型 ID (默认 100302)")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # 读取现有装饰物
    existing = []
    if os.path.exists(args.decoration_csv):
        with open(args.decoration_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                existing.append(row)
    print(f"[Round 4] 更新 decoration_grid.csv ...")
    print(f"  现有装饰物: {len(existing)} 个")

    # 解析桥梁
    bridges_raw = parse_json_or_file(args.bridges, "--bridges")
    bridges = []
    for b in bridges_raw:
        bridges.append({
            "x": str(b["x"]),
            "z": str(b["z"]),
            "type": "bridge",
            "model_id": str(b.get("model_id", args.bridge_model_id))
        })

    # 解析树木（支持单点 {x,z} 和矩形区域 {x1,z1,x2,z2} 两种格式）
    trees_raw = parse_json_or_file(args.trees, "--trees")
    trees = []
    for t in trees_raw:
        if "x1" in t and "z1" in t and "x2" in t and "z2" in t:
            # 矩形区域：展开为区域内每个格子
            x_min, x_max = min(t["x1"], t["x2"]), max(t["x1"], t["x2"])
            z_min, z_max = min(t["z1"], t["z2"]), max(t["z1"], t["z2"])
            for tx in range(x_min, x_max + 1):
                for tz in range(z_min, z_max + 1):
                    trees.append({
                        "x": str(tx),
                        "z": str(tz),
                        "type": "tree",
                        "model_id": str(t.get("model_id", args.tree_model_id))
                    })
        else:
            # 单点格式
            trees.append({
                "x": str(t["x"]),
                "z": str(t["z"]),
                "type": "tree",
                "model_id": str(t.get("model_id", args.tree_model_id))
            })

    # 合并
    all_deco = existing + bridges + trees

    # 写出
    output_path = os.path.join(args.output_dir, "decoration_grid.csv")
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["x", "z", "type", "model_id"])
        writer.writeheader()
        writer.writerows(all_deco)

    # 统计
    type_counts = {}
    for d in all_deco:
        t = d["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    print(f"\n✅ decoration_grid.csv(v2 final) 更新完成！")
    print(f"   总装饰物: {len(all_deco)} 个")
    for t, c in sorted(type_counts.items()):
        print(f"     {t}: {c} 个")
    print(f"   → {output_path}")


if __name__ == "__main__":
    main()