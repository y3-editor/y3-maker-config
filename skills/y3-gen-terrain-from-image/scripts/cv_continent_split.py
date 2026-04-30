#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cv_continent_split.py — Round 1 辅助: 连通区域分割

读取 cv_cluster.py 输出的 labels.npy，根据 AI 指定的水域簇 ID 列表，
在原图分辨率上分割出：
  1. water_mask  — 水域像素标记 (bool)
  2. continent_map — 大陆连通区域编号 (int32, 0=水域, 1~N=大陆)

同时输出网格分辨率版本（下采样）和大陆摘要 JSON + 预览图。

用法:
  python cv_continent_split.py labels.npy --water-clusters 0,3,7 --width 65 --height 65 --output-dir <dir>
"""

import json
import sys
import os
import argparse
import numpy as np
import cv2


# ────────────────────────── 高对比度调色板 ──────────────────────────
# 用于预览图中标注不同大陆区域
CONTINENT_COLORS_BGR = [
    (80, 80, 200),    # 红
    (80, 200, 80),    # 绿
    (200, 160, 50),   # 蓝
    (50, 200, 200),   # 黄
    (200, 80, 200),   # 紫
    (200, 200, 80),   # 青
    (60, 140, 255),   # 橙
    (180, 105, 180),  # 粉
    (128, 200, 128),  # 淡绿
    (100, 100, 220),  # 珊瑚
    (200, 200, 200),  # 浅灰
    (140, 180, 80),   # 橄榄
    (80, 180, 220),   # 金
    (220, 120, 80),   # 钢蓝
    (100, 220, 180),  # 青绿
    (180, 100, 140),  # 暗粉
]

WATER_COLOR_BGR = (60, 40, 20)  # 深色表示水域


def build_water_mask(labels_2d, water_cluster_ids):
    """根据水域簇 ID 列表生成 water_mask (bool矩阵)

    Args:
        labels_2d: (img_h, img_w) int32, 聚类标签
        water_cluster_ids: list[int], 水域簇 ID

    Returns:
        water_mask: (img_h, img_w) bool, True=水域
    """
    water_set = set(water_cluster_ids)
    water_mask = np.isin(labels_2d, list(water_set))
    water_count = int(water_mask.sum())
    total = water_mask.size
    print(f"  水域像素: {water_count} / {total} ({water_count * 100.0 / total:.1f}%)")
    return water_mask


def split_continents(water_mask, erode_pixels=5):
    """对非水域像素做连通区域分割

    先对陆地做形态学腐蚀以断开桥梁/道路等窄连接体，
    再做连通分割确定大陆编号，最后用最近邻回填被腐蚀的陆地像素。

    Args:
        water_mask: (img_h, img_w) bool
        erode_pixels: 腐蚀核半径（像素），用于断开窄连接。
                      桥梁宽度通常 < 10 像素，默认 5 可断开大部分桥。

    Returns:
        continent_map: (img_h, img_w) int32, 0=水域, 1~N=大陆编号
        num_continents: 大陆数量 N
    """
    # 构造二值图：陆地=255, 水域=0
    land_binary = (~water_mask).astype(np.uint8) * 255

    # ── Phase 1: 腐蚀断开窄连接 ──
    if erode_pixels > 0:
        kernel = cv2.getStructuringElement(
            cv2.MORPH_ELLIPSE, (erode_pixels * 2 + 1, erode_pixels * 2 + 1))
        eroded = cv2.erode(land_binary, kernel, iterations=1)
        eroded_count = int((land_binary > 0).sum()) - int((eroded > 0).sum())
        print(f"  腐蚀 {erode_pixels}px: 移除 {eroded_count} 像素的窄连接体")
    else:
        eroded = land_binary

    # ── Phase 2: 在腐蚀后的陆地上做连通分割 ──
    num_labels, labels_eroded = cv2.connectedComponents(eroded, connectivity=4)
    num_continents = num_labels - 1
    print(f"  连通区域分割（腐蚀后）: {num_continents} 个大陆")

    # ── Phase 3: 回填被腐蚀的陆地像素 ──
    # 被腐蚀掉但原本是陆地的像素，用膨胀迭代分配回各大陆
    continent_map = labels_eroded.astype(np.int32)

    if erode_pixels > 0:
        # 找出需要回填的像素：原本是陆地 but 被腐蚀掉了
        needs_fill = (land_binary > 0) & (eroded == 0)
        fill_count = int(needs_fill.sum())

        if fill_count > 0:
            # 用膨胀迭代逐步回填（比 BFS 更快）
            remaining = needs_fill.copy()
            iterations = 0
            max_iterations = erode_pixels * 3  # 足够回填所有腐蚀像素

            while remaining.sum() > 0 and iterations < max_iterations:
                # 膨胀当前 continent_map 中的已知标签
                dilated = cv2.dilate(
                    continent_map.astype(np.float32),
                    cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)),
                    iterations=1
                ).astype(np.int32)

                # 只回填 remaining 中仍未分配的像素
                fill_mask = remaining & (dilated > 0)
                continent_map[fill_mask] = dilated[fill_mask]
                remaining = remaining & (continent_map == 0)
                iterations += 1

            final_unfilled = int(remaining.sum())
            print(f"  回填被腐蚀的陆地: {fill_count - final_unfilled}/{fill_count} 像素"
                  f" ({iterations} 轮膨胀)")
            if final_unfilled > 0:
                print(f"  ⚠️ {final_unfilled} 像素未能回填（孤立碎片，归入水域）")

    return continent_map, num_continents


def filter_bridge_fragments(continent_map, water_mask, labels_2d,
                            area_ratio_threshold=0.005, water_neighbor_ratio=0.3,
                            color_diff_threshold=0.5):
    """检测并过滤桥梁碎片：面积小 + 邻水 + 与相邻大陆颜色不同 → 归为水域

    三重特征检测：
    1. 面积小（占总陆地面积 < area_ratio_threshold）
    2. 边界有较高比例接触水域（water_neighbor_ratio）
    3. 主聚类簇 ID 与相邻大陆的主聚类簇 ID 不同

    Args:
        continent_map: (img_h, img_w) int32, 0=水域, 1~N=大陆
        water_mask: (img_h, img_w) bool
        labels_2d: (img_h, img_w) int32, 原始聚类标签
        area_ratio_threshold: 面积阈值（占总陆地比例），低于此值才检查
        water_neighbor_ratio: 边界像素中水域邻居占比阈值
        color_diff_threshold: 颜色差异阈值（主簇不同即视为异色）

    Returns:
        continent_map: 修改后的 continent_map（桥梁碎片已归为 0=水域）
        water_mask: 修改后的 water_mask（桥梁区域标为 True）
        bridge_count: 被过滤的桥梁碎片数
    """
    continent_map = continent_map.copy()
    water_mask = water_mask.copy()

    img_h, img_w = continent_map.shape
    total_land = int((continent_map > 0).sum())
    if total_land == 0:
        return continent_map, water_mask, 0

    area_threshold = max(total_land * area_ratio_threshold, 50)  # 至少 50 像素

    # 统计每个大陆的面积和主簇 ID
    max_cid = int(continent_map.max())
    continent_info = {}  # cid → {area, main_cluster}
    for cid in range(1, max_cid + 1):
        mask = (continent_map == cid)
        area = int(mask.sum())
        if area == 0:
            continue

        # 主簇 ID = 该大陆区域内出现最多的聚类标签
        cluster_labels = labels_2d[mask]
        counts = np.bincount(cluster_labels.flatten())
        main_cluster = int(counts.argmax())
        continent_info[cid] = {"area": area, "main_cluster": main_cluster}

    bridge_count = 0
    filtered_ids = []

    for cid, info in continent_info.items():
        # 条件 1: 面积小
        if info["area"] >= area_threshold:
            continue

        mask = (continent_map == cid)

        # 条件 2: 边界大比例接触水域
        # 膨胀 1px 得到边界区域
        mask_uint8 = mask.astype(np.uint8) * 255
        dilated = cv2.dilate(mask_uint8, cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3)))
        border = (dilated > 0) & (~mask)  # 外侧边界像素

        if border.sum() == 0:
            continue

        water_border_count = int((border & water_mask).sum())
        water_ratio = water_border_count / border.sum()

        if water_ratio < water_neighbor_ratio:
            continue  # 没有足够水域邻居，不是桥

        # 条件 3: 颜色与相邻大陆不同
        # 找相邻的大陆 ID
        neighbor_cids = set()
        border_labels = continent_map[border]
        for ncid in np.unique(border_labels):
            if ncid > 0 and ncid != cid:
                neighbor_cids.add(int(ncid))

        if neighbor_cids:
            # 检查主簇是否与所有相邻大陆都不同
            my_cluster = info["main_cluster"]
            all_different = all(
                continent_info.get(ncid, {}).get("main_cluster", -1) != my_cluster
                for ncid in neighbor_cids
            )

            if all_different:
                # 三重条件全满足 → 桥梁碎片，归为水域
                continent_map[mask] = 0
                water_mask[mask] = True
                bridge_count += 1
                filtered_ids.append(cid)
                print(f"    🌉 大陆 #{cid}: 面积={info['area']}px, "
                      f"水域邻居={water_ratio:.0%}, 主簇={my_cluster} "
                      f"(与邻居 {neighbor_cids} 不同) → 归为水域")
        else:
            # 没有陆地邻居，完全被水包围的小碎片 → 也归为水域
            continent_map[mask] = 0
            water_mask[mask] = True
            bridge_count += 1
            filtered_ids.append(cid)
            print(f"    🌉 大陆 #{cid}: 面积={info['area']}px, "
                  f"水域邻居={water_ratio:.0%}, 无陆地邻居 → 归为水域")

    if bridge_count > 0:
        print(f"  桥梁过滤: {bridge_count} 个碎片归为水域 (IDs: {filtered_ids})")
    else:
        print(f"  桥梁过滤: 未发现桥梁碎片")

    return continent_map, water_mask, bridge_count


def downsample_mask(mask_full, map_w, map_h, threshold=0.10):
    """将原图分辨率 bool mask 下采样到网格分辨率（线性特征保护）

    规则：如果格子内水域像素占比 >= threshold，则该格为水域。
    默认阈值 10%，用于保护窄河道等线性水域特征不被丢失。

    Args:
        mask_full: (img_h, img_w) bool
        map_w, map_h: 目标网格尺寸
        threshold: 水域判定阈值（默认 0.10 即 10%）

    Returns:
        mask_grid: (map_h, map_w) bool
    """
    img_h, img_w = mask_full.shape
    cell_h = img_h / map_h
    cell_w = img_w / map_w
    mask_grid = np.zeros((map_h, map_w), dtype=bool)

    for z in range(map_h):
        for x in range(map_w):
            py1 = int(round(z * cell_h))
            py2 = int(round((z + 1) * cell_h))
            px1 = int(round(x * cell_w))
            px2 = int(round((x + 1) * cell_w))
            py2 = min(py2, img_h)
            px2 = min(px2, img_w)

            block = mask_full[py1:py2, px1:px2]
            if block.size == 0:
                continue
            mask_grid[z, x] = (block.sum() / block.size) >= threshold

    return mask_grid


def downsample_continent_map(continent_map_full, water_mask_full, map_w, map_h):
    """将原图分辨率 continent_map 下采样到网格分辨率

    规则：每个格子取陆地像素中出现次数最多的大陆编号。
    如果该格子被水域主导(>=50%)，则标记为 0（水域）。

    Args:
        continent_map_full: (img_h, img_w) int32
        water_mask_full: (img_h, img_w) bool
        map_w, map_h: 目标网格尺寸

    Returns:
        continent_map_grid: (map_h, map_w) int32
    """
    img_h, img_w = continent_map_full.shape
    cell_h = img_h / map_h
    cell_w = img_w / map_w
    max_label = int(continent_map_full.max()) + 1
    grid = np.zeros((map_h, map_w), dtype=np.int32)

    for z in range(map_h):
        for x in range(map_w):
            py1 = int(round(z * cell_h))
            py2 = int(round((z + 1) * cell_h))
            px1 = int(round(x * cell_w))
            px2 = int(round((x + 1) * cell_w))
            py2 = min(py2, img_h)
            px2 = min(px2, img_w)

            water_block = water_mask_full[py1:py2, px1:px2]
            if water_block.size == 0:
                continue

            # 水域主导则标 0
            if water_block.sum() / water_block.size >= 0.5:
                grid[z, x] = 0
                continue

            # 陆地像素中取多数投票
            cont_block = continent_map_full[py1:py2, px1:px2]
            land_labels = cont_block[~water_block]
            if land_labels.size == 0:
                grid[z, x] = 0
                continue

            counts = np.bincount(land_labels.flatten(), minlength=max_label)
            counts[0] = 0  # 排除水域编号
            grid[z, x] = int(counts.argmax())

    return grid


def compute_continent_summary(continent_map_grid, map_w, map_h,
                              image_bgr=None, continent_map_full=None):
    """生成大陆摘要信息

    Args:
        continent_map_grid: (map_h, map_w) int32
        map_w, map_h: 网格尺寸
        image_bgr: (可选) 原图 BGR，传入时计算每个大陆的平均 RGB
        continent_map_full: (可选) 原图分辨率大陆图，与 image_bgr 配合使用

    Returns:
        list[dict]: 每个大陆的 {id, area, bbox, avg_rgb?}
    """
    max_id = int(continent_map_grid.max())
    summary = []

    for cid in range(1, max_id + 1):
        mask = (continent_map_grid == cid)
        area = int(mask.sum())
        if area == 0:
            continue

        zs, xs = np.where(mask)
        bbox = [int(xs.min()), int(zs.min()), int(xs.max()), int(zs.max())]
        entry = {
            "id": cid,
            "area": area,
            "bbox": bbox  # [x1, z1, x2, z2] 格点坐标
        }

        # 计算平均 RGB（基于原图分辨率 mask，精度更高）
        if image_bgr is not None and continent_map_full is not None:
            mask_full = (continent_map_full == cid)
            if mask_full.sum() > 0:
                pixels = image_bgr[mask_full]
                avg_bgr = pixels.mean(axis=0)
                entry["avg_rgb"] = [int(round(avg_bgr[2])),
                                    int(round(avg_bgr[1])),
                                    int(round(avg_bgr[0]))]

        summary.append(entry)

    # 按面积降序排列
    summary.sort(key=lambda c: -c["area"])
    return summary


def generate_continent_preview(continent_map_full, num_continents, output_path):
    """生成大陆分割预览图

    Args:
        continent_map_full: (img_h, img_w) int32
        num_continents: 大陆数量
        output_path: 输出路径
    """
    img_h, img_w = continent_map_full.shape
    preview = np.zeros((img_h, img_w, 3), dtype=np.uint8)

    # 水域用深色填充
    water_mask = (continent_map_full == 0)
    preview[water_mask] = WATER_COLOR_BGR

    # 每个大陆用不同颜色
    for cid in range(1, num_continents + 1):
        mask = (continent_map_full == cid)
        if mask.sum() == 0:
            continue
        color_idx = (cid - 1) % len(CONTINENT_COLORS_BGR)
        preview[mask] = CONTINENT_COLORS_BGR[color_idx]

    cv2.imwrite(output_path, preview)
    print(f"  大陆预览图: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Round 1 连通区域分割 — 水域标记 + 大陆分割")
    parser.add_argument("labels_npy", help="labels.npy 文件路径（cv_cluster.py 输出）")
    parser.add_argument("--water-clusters", required=True,
                        help="水域簇 ID 列表，逗号分隔（如 0,3,7）")
    parser.add_argument("--image", default=None,
                        help="(可选) 裁剪后的地图图片路径(cropped.png)，传入时计算每个大陆的平均 RGB")
    parser.add_argument("--width", type=int, default=None, help="地图网格宽度（可选，优先从 map_info.json 读取）")
    parser.add_argument("--height", type=int, default=None, help="地图网格高度（可选，优先从 map_info.json 读取）")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    water_ids = [int(c.strip()) for c in args.water_clusters.split(",")]

    # 自动从 map_info.json 读取地图尺寸（优先），命令行参数作为 fallback
    map_info_path = os.path.join(args.output_dir, "map_info.json")
    if os.path.exists(map_info_path):
        with open(map_info_path, "r", encoding="utf-8") as f:
            map_info = json.load(f)
        auto_w = int(map_info.get("width", 0))
        auto_h = int(map_info.get("height", 0))
        if auto_w > 0 and auto_h > 0:
            if args.width and args.width != auto_w:
                print(f"[WARN] --width={args.width} 与 map_info.json width={auto_w} 不一致，使用 map_info.json 的值")
            if args.height and args.height != auto_h:
                print(f"[WARN] --height={args.height} 与 map_info.json height={auto_h} 不一致，使用 map_info.json 的值")
            args.width = auto_w
            args.height = auto_h
            print(f"[map_info] 从 map_info.json 读取地图尺寸: {args.width}x{args.height}")
    
    if not args.width or not args.height:
        print("[ERROR] 无法确定地图尺寸：map_info.json 不存在且未提供 --width/--height 参数")
        sys.exit(1)

    # 加载原图（可选，用于计算大陆平均 RGB）
    image_bgr = None
    if args.image:
        if not os.path.exists(args.image):
            print(f"[WARN] 图片不存在: {args.image}，跳过 avg_rgb 计算")
        else:
            image_bgr = cv2.imread(args.image)
            print(f"  原图已加载: {args.image} ({image_bgr.shape[1]}x{image_bgr.shape[0]})")

    # Step 1: 加载 labels.npy
    print("[Step 1] 加载 labels.npy ...")
    if not os.path.exists(args.labels_npy):
        print(f"[ERROR] labels.npy 不存在: {args.labels_npy}")
        sys.exit(1)
    labels_2d = np.load(args.labels_npy)
    print(f"  labels shape: {labels_2d.shape}")

    # Step 2: 生成 water_mask
    print(f"\n[Step 2] 生成 water_mask (水域簇: {water_ids}) ...")
    water_mask_full = build_water_mask(labels_2d, water_ids)

    # Step 3: 连通区域分割
    print(f"\n[Step 3] 连通区域分割 ...")
    continent_map_full, num_continents = split_continents(water_mask_full)

    # Step 3b: 桥梁碎片过滤（面积小 + 邻水 + 异色 → 归为水域）
    print(f"\n[Step 3b] 桥梁碎片过滤 ...")
    continent_map_full, water_mask_full, bridge_count = filter_bridge_fragments(
        continent_map_full, water_mask_full, labels_2d)
    if bridge_count > 0:
        # 重新统计大陆数
        num_continents = int(continent_map_full.max())

    # Step 4: 下采样到网格分辨率
    print(f"\n[Step 4] 下采样到网格 ({args.width}x{args.height}) ...")
    water_mask_grid = downsample_mask(water_mask_full, args.width, args.height)
    continent_map_grid = downsample_continent_map(
        continent_map_full, water_mask_full, args.width, args.height)

    water_grid_count = int(water_mask_grid.sum())
    total_grid = args.width * args.height
    print(f"  网格水域: {water_grid_count} / {total_grid} ({water_grid_count * 100.0 / total_grid:.1f}%)")

    # Step 5: 保存 npy 文件
    print(f"\n[Step 5] 保存 mask/map 文件 ...")
    np.save(os.path.join(args.output_dir, "water_mask_full.npy"), water_mask_full)
    np.save(os.path.join(args.output_dir, "water_mask_grid.npy"), water_mask_grid)
    np.save(os.path.join(args.output_dir, "continent_map_full.npy"), continent_map_full)
    np.save(os.path.join(args.output_dir, "continent_map_grid.npy"), continent_map_grid)
    print(f"  water_mask_full.npy: {water_mask_full.shape} bool")
    print(f"  water_mask_grid.npy: {water_mask_grid.shape} bool")
    print(f"  continent_map_full.npy: {continent_map_full.shape} int32")
    print(f"  continent_map_grid.npy: {continent_map_grid.shape} int32")

    # Step 6: 生成大陆摘要 JSON（含平均 RGB）
    print(f"\n[Step 6] 生成大陆摘要 ...")
    # 如果传入了原图，resize 到 labels 分辨率用于 avg_rgb 计算
    image_bgr_resized = None
    if image_bgr is not None:
        img_h, img_w = labels_2d.shape
        if image_bgr.shape[:2] != labels_2d.shape:
            image_bgr_resized = cv2.resize(image_bgr, (img_w, img_h),
                                           interpolation=cv2.INTER_AREA)
        else:
            image_bgr_resized = image_bgr
    summary = compute_continent_summary(
        continent_map_grid, args.width, args.height,
        image_bgr=image_bgr_resized,
        continent_map_full=continent_map_full)
    summary_path = os.path.join(args.output_dir, "continent_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  continent_summary.json: {len(summary)} 个大陆")
    for c in summary:
        rgb_info = f", avg_rgb={c['avg_rgb']}" if 'avg_rgb' in c else ""
        print(f"    大陆 #{c['id']}: 面积={c['area']} 格, bbox={c['bbox']}{rgb_info}")

    # Step 7: 生成预览图
    print(f"\n[Step 7] 生成预览图 ...")
    generate_continent_preview(
        continent_map_full, num_continents,
        os.path.join(args.output_dir, "continent_preview.png"))

    print(f"\n✅ Round 1 连通区域分割完成！")
    print(f"   → water_mask_full/grid.npy  (水域标记)")
    print(f"   → continent_map_full/grid.npy  (大陆编号)")
    print(f"   → continent_summary.json  (大陆摘要)")
    print(f"   → continent_preview.png  (大陆预览图)")
    print(f"\n   共 {num_continents} 个大陆, {water_grid_count} 格水域")
    print(f"\n   下一步：AI 为每个大陆分配纹理 ID → 生成 terrain_grid.csv(v1) + texture_grid.csv(v1)")


if __name__ == "__main__":
    main()
