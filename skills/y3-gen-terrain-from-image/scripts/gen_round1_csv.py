#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_round1_csv.py — Round 1 Step 1.5: 生成 terrain_grid.csv(v1) + texture_grid.csv(v1)

读取 cv_continent_split.py 输出的 water_mask_grid.npy 和 continent_map_grid.npy，
结合 AI 提供的纹理分配 JSON，生成初始版本的 terrain_grid.csv 和 texture_grid.csv。

用法:
  python gen_round1_csv.py \
    --water-mask <dir>/water_mask_grid.npy \
    --continent-map <dir>/continent_map_grid.npy \
    --texture-config '{"1": 147, "2": 170, "3": 165}' \
    --default-texture 147 \
    --output-dir <dir>

纹理配置格式 (--texture-config):
  JSON 对象，key=大陆ID(字符串), value=纹理ID(整数)
  例: '{"1": 147, "2": 170, "3": 165}'

小碎片大陆（未在 texture-config 中指定）会自动继承最近的大陆纹理。
"""

import json
import sys
import os
import csv
import argparse
import numpy as np


def group_continents_by_color(continent_summary_path, distance_threshold=30, min_area=5):
    """根据 avg_rgb 欧氏距离自动将大陆聚类为纹理组。

    算法：简单的 Union-Find，两两比较 avg_rgb，距离 < threshold 的归为同组。
    面积 <= min_area 的碎片大陆不参与分组，后续由 inherit_small_fragments 处理。

    Args:
        continent_summary_path: continent_summary.json 路径
        distance_threshold: RGB 欧氏距离阈值（默认 30）
        min_area: 碎片面积阈值（默认 5），面积 <= 此值的不参与分组

    Returns:
        groups: list[dict], 每组包含:
            - group_id: int (从 1 开始)
            - continent_ids: list[int]
            - avg_rgb: [R, G, B] (组内面积加权平均)
            - total_area: int
        fragments: list[int], 碎片大陆 ID 列表
    """
    import math

    with open(continent_summary_path, "r", encoding="utf-8") as f:
        continents = json.load(f)

    # 分离碎片和正常大陆
    normal = [c for c in continents if c["area"] > min_area]
    fragments = [c["id"] for c in continents if c["area"] <= min_area]

    if not normal:
        return [], fragments

    # Union-Find
    parent = {c["id"]: c["id"] for c in normal}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    # 两两比较
    for i in range(len(normal)):
        for j in range(i + 1, len(normal)):
            r1, g1, b1 = normal[i]["avg_rgb"]
            r2, g2, b2 = normal[j]["avg_rgb"]
            dist = math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)
            if dist < distance_threshold:
                union(normal[i]["id"], normal[j]["id"])

    # 收集组
    from collections import defaultdict
    group_map = defaultdict(list)
    for c in normal:
        group_map[find(c["id"])].append(c)

    groups = []
    for gid_idx, (_, members) in enumerate(sorted(group_map.items()), start=1):
        ids = [c["id"] for c in members]
        total_area = sum(c["area"] for c in members)
        # 面积加权 avg_rgb
        wr = sum(c["avg_rgb"][0] * c["area"] for c in members) / total_area
        wg = sum(c["avg_rgb"][1] * c["area"] for c in members) / total_area
        wb = sum(c["avg_rgb"][2] * c["area"] for c in members) / total_area
        groups.append({
            "group_id": gid_idx,
            "continent_ids": sorted(ids),
            "avg_rgb": [int(round(wr)), int(round(wg)), int(round(wb))],
            "total_area": total_area,
        })

    # 按面积降序
    groups.sort(key=lambda g: g["total_area"], reverse=True)
    for i, g in enumerate(groups, start=1):
        g["group_id"] = i

    return groups, fragments


def inherit_small_fragments(continent_map, texture_config, default_texture):
    """为小碎片大陆找到最近的已配置大陆，继承其纹理。

    使用膨胀迭代法：从已配置大陆向外膨胀，碰到的第一个未配置大陆就继承。

    Args:
        continent_map: (H, W) int32, 大陆编号 (0=水域)
        texture_config: dict[int, int], 已配置的 大陆ID→纹理ID
        default_texture: int, 兜底纹理ID

    Returns:
        full_config: dict[int, int], 所有大陆ID→纹理ID (含继承)
    """
    all_ids = set(int(x) for x in np.unique(continent_map) if x > 0)
    configured_ids = set(texture_config.keys())
    unconfigured_ids = all_ids - configured_ids

    if not unconfigured_ids:
        return dict(texture_config)

    print(f"  已配置大陆: {sorted(configured_ids)}")
    print(f"  未配置碎片: {sorted(unconfigured_ids)}, 自动继承最近大陆纹理")

    H, W = continent_map.shape
    inherited = {}

    for uid in unconfigured_ids:
        mask = (continent_map == uid)
        ys, xs = np.where(mask)
        if len(ys) == 0:
            inherited[uid] = default_texture
            continue

        # 从碎片中心向外搜索最近的已配置大陆
        cy, cx = int(ys.mean()), int(xs.mean())
        found = False

        for radius in range(1, max(H, W)):
            # 扫描正方形边框
            for dy in range(-radius, radius + 1):
                for dx in [-radius, radius]:  # 左右边
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < H and 0 <= nx < W:
                        neighbor_cid = int(continent_map[ny, nx])
                        if neighbor_cid in configured_ids:
                            inherited[uid] = texture_config[neighbor_cid]
                            found = True
                            break
                if found:
                    break
            if found:
                break

            for dx in range(-radius + 1, radius):  # 上下边（不含角）
                for dy in [-radius, radius]:
                    ny, nx = cy + dy, cx + dx
                    if 0 <= ny < H and 0 <= nx < W:
                        neighbor_cid = int(continent_map[ny, nx])
                        if neighbor_cid in configured_ids:
                            inherited[uid] = texture_config[neighbor_cid]
                            found = True
                            break
                if found:
                    break
            if found:
                break

        if not found:
            inherited[uid] = default_texture
            print(f"    ⚠️ 大陆 #{uid}: 未找到邻近大陆，使用默认纹理 {default_texture}")

    for uid, tex in sorted(inherited.items()):
        print(f"    大陆 #{uid} → 继承纹理 {tex}")

    full_config = dict(texture_config)
    full_config.update(inherited)
    return full_config


def bfs_inherit_cliff_tex_id(water_mask, continent_map, cliff_config):
    """水域格子通过 BFS 扩散继承最近陆地的 cliff_tex_id。

    Args:
        water_mask: (H, W) bool
        continent_map: (H, W) int32
        cliff_config: dict[int, int], 大陆ID → cliff_tex_id

    Returns:
        cliff_grid: (H, W) int32, 每格的 cliff_tex_id
    """
    from collections import deque

    H, W = water_mask.shape
    cliff_grid = np.full((H, W), -1, dtype=np.int32)

    queue = deque()

    # 初始化：陆地格子直接赋值
    for z in range(H):
        for x in range(W):
            if not water_mask[z, x]:
                cid = int(continent_map[z, x])
                cliff_grid[z, x] = cliff_config.get(cid, 0)
                # 陆地边缘（邻居有水）入队
                for dz, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                    nz, nx = z + dz, x + dx
                    if 0 <= nz < H and 0 <= nx < W and water_mask[nz, nx]:
                        queue.append((z, x))
                        break

    # BFS 向水域扩散
    while queue:
        sz, sx = queue.popleft()
        src_cid = cliff_grid[sz, sx]
        for dz, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nz, nx = sz + dz, sx + dx
            if 0 <= nz < H and 0 <= nx < W and cliff_grid[nz, nx] == -1:
                cliff_grid[nz, nx] = src_cid
                queue.append((nz, nx))

    # 兜底：未到达的格子设为 0
    cliff_grid[cliff_grid == -1] = 0
    return cliff_grid


def generate_csvs(water_mask, continent_map, full_texture_config, cliff_config, default_texture, output_dir):
    """生成 terrain_grid.csv(v1) 和 texture_grid.csv(v1)

    CSV 格式: "type,height,cliff_tex_id"

    Args:
        water_mask: (H, W) bool
        continent_map: (H, W) int32
        full_texture_config: dict[int, int], 所有大陆→纹理
        cliff_config: dict[int, int], 所有大陆→cliff_tex_id
        default_texture: int
        output_dir: str
    """
    H, W = water_mask.shape

    # BFS 计算每格的 cliff_tex_id（含水域继承）
    print("  BFS 计算水域 cliff_tex_id 继承 ...")
    cliff_grid = bfs_inherit_cliff_tex_id(water_mask, continent_map, cliff_config)

    terrain_path = os.path.join(output_dir, "terrain_grid.csv")
    texture_path = os.path.join(output_dir, "texture_grid.csv")

    water_count = 0
    land_count = 0

    with open(terrain_path, "w", newline="") as tf, \
         open(texture_path, "w", newline="") as xf:
        t_writer = csv.writer(tf)
        x_writer = csv.writer(xf)

        for z in range(H):
            t_row = []
            x_row = []
            for x in range(W):
                ctid = int(cliff_grid[z, x])
                if water_mask[z, x]:
                    t_row.append(f"deep_water,0,{ctid}")
                    x_row.append(0)
                    water_count += 1
                else:
                    t_row.append(f"ground,0,{ctid}")
                    cid = int(continent_map[z, x])
                    tex = full_texture_config.get(cid, default_texture)
                    x_row.append(tex)
                    land_count += 1
            t_writer.writerow(t_row)
            x_writer.writerow(x_row)

    return terrain_path, texture_path, water_count, land_count


def expand_group_config(groups, fragments, group_texture_config):
    """将按组分配的纹理展开为按大陆 ID 的纹理配置。

    Args:
        groups: group_continents_by_color 返回的组列表
        fragments: 碎片大陆 ID 列表（后续由 inherit_small_fragments 处理）
        group_texture_config: dict[int, int], group_id → texture_id

    Returns:
        texture_config: dict[int, int], continent_id → texture_id
    """
    texture_config = {}
    for group in groups:
        gid = group["group_id"]
        if gid in group_texture_config:
            tex = group_texture_config[gid]
            for cid in group["continent_ids"]:
                texture_config[cid] = tex
    return texture_config


def main():
    parser = argparse.ArgumentParser(
        description="Round 1 Step 1.5 — 生成 terrain_grid.csv(v1) + texture_grid.csv(v1)")
    parser.add_argument("--water-mask", required=True, help="water_mask_grid.npy 路径")
    parser.add_argument("--continent-map", required=True, help="continent_map_grid.npy 路径")
    parser.add_argument("--texture-config", default=None,
                        help='纹理配置 JSON (按大陆ID), 如 \'{"1": 147, "2": 170}\' — 与 --group-texture-config 二选一')
    parser.add_argument("--group-texture-config", default=None,
                        help='纹理配置 JSON (按组ID), 如 \'{"1": 147, "2": 170}\' — 与 --texture-config 二选一')
    parser.add_argument("--continent-summary", default=None,
                        help="continent_summary.json 路径 (--group-texture-config 或 --group-only 模式必需)")
    parser.add_argument("--group-only", action="store_true",
                        help="仅输出纹理组分组结果（不生成 CSV），供 AI 按组分配纹理")
    parser.add_argument("--color-threshold", type=int, default=30,
                        help="RGB 欧氏距离阈值（默认 30），距离 < 此值的大陆归为同组")
    parser.add_argument("--default-texture", type=int, default=147,
                        help="兜底纹理 ID (默认 147)")
    parser.add_argument("--cliff-mapping", default="",
                        help='悬崖材质映射, 格式 "continent_id:cliff_tex_id,...", 如 "1:0,2:1,3:9"')
    parser.add_argument("--output-dir", default=".", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # ── group-only 模式：只输出分组结果 ──
    if args.group_only:
        if not args.continent_summary:
            # 自动查找 continent_summary.json
            auto_path = os.path.join(args.output_dir, "continent_summary.json")
            if os.path.exists(auto_path):
                args.continent_summary = auto_path
            else:
                print("[ERROR] --group-only 需要 --continent-summary 或 output-dir 下存在 continent_summary.json")
                sys.exit(1)

        print("[Group-Only] 颜色聚类分组 ...")
        print(f"  continent_summary: {args.continent_summary}")
        print(f"  RGB 距离阈值: {args.color_threshold}")
        groups, fragments = group_continents_by_color(
            args.continent_summary, args.color_threshold)

        print(f"\n📊 分组结果 ({len(groups)} 组, {len(fragments)} 碎片):\n")
        for g in groups:
            print(f"  Group {g['group_id']}: 大陆 {g['continent_ids']}, "
                  f"avg_rgb={g['avg_rgb']}, 面积={g['total_area']}")
        if fragments:
            print(f"\n  碎片(自动继承): {fragments}")

        # 输出 JSON 供 AI 参考
        result = {"groups": groups, "fragments": fragments}
        out_path = os.path.join(args.output_dir, "texture_groups.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 分组结果已保存: {out_path}")
        print(f"\n💡 AI 请为每个 Group 分配一个纹理 ID（参考 texture-color-map.md），")
        print(f"   然后用 --group-texture-config '{{\"1\": 147, \"2\": 170}}' 调用本脚本生成 CSV。")
        return

    # ── 加载 mask/map ──
    print("[Step 1] 加载 water_mask + continent_map ...")
    if not os.path.exists(args.water_mask):
        print(f"[ERROR] water_mask 不存在: {args.water_mask}")
        sys.exit(1)
    if not os.path.exists(args.continent_map):
        print(f"[ERROR] continent_map 不存在: {args.continent_map}")
        sys.exit(1)

    water_mask = np.load(args.water_mask)
    continent_map = np.load(args.continent_map)
    H, W = water_mask.shape
    print(f"  网格尺寸: {W}x{H}")

    # ── 解析纹理配置（两种模式二选一） ──
    if args.group_texture_config:
        # 模式 B: 按组分配 → 需要 continent_summary 做聚类
        if not args.continent_summary:
            auto_path = os.path.join(args.output_dir, "continent_summary.json")
            if os.path.exists(auto_path):
                args.continent_summary = auto_path
            else:
                print("[ERROR] --group-texture-config 需要 --continent-summary")
                sys.exit(1)

        try:
            raw_group = json.loads(args.group_texture_config)
            group_tex = {int(k): int(v) for k, v in raw_group.items()}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[ERROR] group-texture-config JSON 解析失败: {e}")
            sys.exit(1)

        print(f"  模式: 按组分配纹理")
        print(f"  组纹理配置: {group_tex}")

        groups, fragments = group_continents_by_color(
            args.continent_summary, args.color_threshold)
        texture_config = expand_group_config(groups, fragments, group_tex)

        print(f"  展开后按大陆ID: {texture_config}")
        print(f"  碎片大陆(自动继承): {fragments}")

    elif args.texture_config:
        # 模式 A: 按大陆 ID 分配（向后兼容）
        try:
            raw_config = json.loads(args.texture_config)
            texture_config = {int(k): int(v) for k, v in raw_config.items()}
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[ERROR] 纹理配置 JSON 解析失败: {e}")
            print(f"  输入: {args.texture_config}")
            print(f'  期望格式: \'{{"1": 147, "2": 170}}\'')
            sys.exit(1)
        print(f"  模式: 按大陆ID分配纹理")
        print(f"  纹理配置: {texture_config}")

    else:
        print("[ERROR] 必须提供 --texture-config 或 --group-texture-config 之一")
        sys.exit(1)

    # 解析悬崖材质映射
    cliff_config = {}
    if args.cliff_mapping:
        try:
            for pair in args.cliff_mapping.split(","):
                pair = pair.strip()
                if ":" in pair:
                    k, v = pair.split(":")
                    cliff_config[int(k)] = int(v)
        except ValueError as e:
            print(f"[ERROR] cliff-mapping 解析失败: {e}")
            print(f"  输入: {args.cliff_mapping}")
            print(f'  期望格式: "1:0,2:1,3:9"')
            sys.exit(1)
    print(f"  悬崖材质映射: {cliff_config if cliff_config else '默认全部=0(泥土)'}")

    # 处理小碎片继承
    print(f"\n[Step 2] 处理小碎片大陆纹理继承 ...")
    full_config = inherit_small_fragments(
        continent_map, texture_config, args.default_texture)

    # 生成 CSV
    print(f"\n[Step 3] 生成 CSV ...")
    terrain_path, texture_path, water_count, land_count = generate_csvs(
        water_mask, continent_map, full_config, cliff_config, args.default_texture, args.output_dir)

    # 统计
    total = H * W
    continent_ids = sorted(set(int(x) for x in np.unique(continent_map) if x > 0))
    unique_textures = sorted(set(full_config.values()))
    print(f"\n✅ Round 1 CSV 生成完成！")
    print(f"   → {terrain_path}")
    print(f"   → {texture_path}")
    print(f"\n   统计:")
    print(f"     总格子: {total}")
    print(f"     水域: {water_count} ({water_count * 100.0 / total:.1f}%)")
    print(f"     陆地: {land_count} ({land_count * 100.0 / total:.1f}%)")
    print(f"     大陆数: {len(continent_ids)} ({continent_ids})")
    print(f"     纹理种类: {len(unique_textures)} 种 {unique_textures}")
    print(f"     纹理映射: {full_config}")


if __name__ == "__main__":
    main()