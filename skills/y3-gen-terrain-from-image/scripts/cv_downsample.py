#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cv_downsample.py — Phase 2: 加权下采样

读取 cv_cluster.py 输出的 labels.npy，下采样到地图网格尺寸。
支持线性特征保护：通过 --linear-clusters 参数指定需要保护的簇 ID，
当这些簇在某个格子中的像素占比超过阈值时，优先保留该簇。

输出：
  - cluster_grid.csv          — W×H 网格，值为簇编号
  - cluster_preview_grid.png  — 网格分辨率预览图（放大到原图尺寸）

用法:
  # 传统多数投票（兼容旧行为）
  python cv_downsample.py labels.npy --width 65 --height 65 --output-dir <dir>

  # 带线性特征保护
  python cv_downsample.py labels.npy --width 65 --height 65 --linear-clusters 5,1,11 --output-dir <dir>

  # 自定义阈值
  python cv_downsample.py labels.npy --width 65 --height 65 --linear-clusters 5,1,11 --threshold 0.05 --output-dir <dir>
"""

import csv
import sys
import os
import argparse
import numpy as np
import cv2


def downsample(labels_2d, img_h, img_w, map_w, map_h, k,
               linear_clusters=None, threshold=0.10):
    """
    下采样到地图网格。
    
    Args:
        labels_2d: 高分辨率聚类标签矩阵 (img_h x img_w)
        img_h, img_w: 图片尺寸
        map_w, map_h: 目标网格尺寸
        k: 簇数量
        linear_clusters: 需要保护的线性特征簇 ID 集合（set 或 None）
        threshold: 线性特征保护阈值（占比超过此值即保留）
    
    Returns:
        grid: (map_h x map_w) 网格，值为簇编号
        stats: 统计信息 dict
    """
    grid = np.zeros((map_h, map_w), dtype=np.int32)
    cell_h = img_h / map_h
    cell_w = img_w / map_w

    linear_set = set(linear_clusters) if linear_clusters else set()
    
    # 统计
    linear_protected_count = 0
    total_cells = map_w * map_h

    for z in range(map_h):
        for x in range(map_w):
            py1 = int(round(z * cell_h))
            py2 = int(round((z + 1) * cell_h))
            px1 = int(round(x * cell_w))
            px2 = int(round((x + 1) * cell_w))
            py2 = min(py2, img_h)
            px2 = min(px2, img_w)

            block = labels_2d[py1:py2, px1:px2]
            if block.size == 0:
                grid[z][x] = 0
                continue

            counts = np.bincount(block.flatten(), minlength=k)
            total_pixels = block.size

            # 线性特征保护逻辑
            if linear_set:
                # 计算所有线性特征簇在此格子中的总占比
                linear_pixel_count = sum(counts[c] for c in linear_set if c < k)
                linear_ratio = linear_pixel_count / total_pixels

                if linear_ratio >= threshold:
                    # 在线性特征簇中选占比最高的
                    best_linear = max(linear_set, key=lambda c: counts[c] if c < k else 0)
                    grid[z][x] = best_linear
                    linear_protected_count += 1
                    continue

            # 普通多数投票
            grid[z][x] = counts.argmax()

    stats = {
        "total_cells": total_cells,
        "linear_protected": linear_protected_count,
        "linear_protected_pct": round(linear_protected_count * 100.0 / total_cells, 1) if total_cells > 0 else 0
    }

    return grid, stats


def generate_preview_grid(grid, map_w, map_h, centers_bgr, output_path, target_size=None):
    """
    生成网格分辨率预览图，每格用该簇的真实平均颜色着色。
    可选放大到指定尺寸。
    """
    preview = np.zeros((map_h, map_w, 3), dtype=np.uint8)
    for z in range(map_h):
        for x in range(map_w):
            ci = grid[z][x]
            if ci < len(centers_bgr):
                preview[z, x] = centers_bgr[ci]
            else:
                preview[z, x] = [128, 128, 128]

    # 放大到目标尺寸（如原图尺寸）
    if target_size:
        preview = cv2.resize(preview, target_size, interpolation=cv2.INTER_NEAREST)

    cv2.imwrite(output_path, preview)
    print(f"  网格预览图: {output_path}")


def write_grid_csv(grid, map_w, map_h, output_path):
    """输出 cluster_grid.csv，每格为簇编号"""
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for z in range(map_h):
            writer.writerow([int(grid[z][x]) for x in range(map_w)])
    print(f"  网格 CSV: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="CV 下采样 Phase 2 — 加权下采样（支持线性特征保护）")
    parser.add_argument("labels_npy", help="labels.npy 文件路径（cv_cluster.py 输出）")
    parser.add_argument("--width", type=int, required=True, help="地图网格宽度")
    parser.add_argument("--height", type=int, required=True, help="地图网格高度")
    parser.add_argument("--linear-clusters", default=None,
                        help="需要保护的线性特征簇 ID，逗号分隔（如 5,1,11）")
    parser.add_argument("--threshold", type=float, default=0.10,
                        help="线性特征保护阈值（默认 0.10，即 10%%）")
    parser.add_argument("--centers-bgr", default=None,
                        help="centers_bgr.npy 路径（默认与 labels.npy 同目录）")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Step 1: 加载 labels.npy
    print("[Step 1] 加载 labels.npy ...")
    if not os.path.exists(args.labels_npy):
        print(f"[ERROR] labels.npy 不存在: {args.labels_npy}")
        sys.exit(1)
    labels_2d = np.load(args.labels_npy)
    img_h, img_w = labels_2d.shape
    k = int(labels_2d.max()) + 1
    print(f"  labels shape: {labels_2d.shape}, K={k}")

    # Step 2: 加载 centers_bgr.npy（用于预览图）
    print("\n[Step 2] 加载 centers_bgr.npy ...")
    centers_bgr_path = args.centers_bgr
    if centers_bgr_path is None:
        centers_bgr_path = os.path.join(os.path.dirname(args.labels_npy), "centers_bgr.npy")
    if not os.path.exists(centers_bgr_path):
        print(f"[WARNING] centers_bgr.npy 不存在: {centers_bgr_path}，预览图将使用灰色")
        centers_bgr = np.full((k, 3), 128, dtype=np.uint8)
    else:
        centers_bgr = np.load(centers_bgr_path)
        print(f"  centers_bgr: {centers_bgr_path}")

    # Step 3: 解析线性特征簇
    linear_clusters = None
    if args.linear_clusters:
        linear_clusters = [int(c.strip()) for c in args.linear_clusters.split(",")]
        print(f"\n[Step 3] 线性特征簇: {linear_clusters}, 阈值: {args.threshold:.0%}")
    else:
        print(f"\n[Step 3] 未指定线性特征簇，使用传统多数投票")

    # Step 4: 下采样
    print(f"\n[Step 4] 下采样到 {args.width}x{args.height} ...")
    grid, stats = downsample(
        labels_2d, img_h, img_w, args.width, args.height, k,
        linear_clusters=linear_clusters, threshold=args.threshold
    )

    print(f"  总格子数: {stats['total_cells']}")
    if linear_clusters:
        print(f"  线性特征保护格子: {stats['linear_protected']} ({stats['linear_protected_pct']}%)")

    # Step 5: 生成网格预览图（放大到原图尺寸）
    print(f"\n[Step 5] 生成网格预览图 ...")
    generate_preview_grid(
        grid, args.width, args.height, centers_bgr,
        os.path.join(args.output_dir, "cluster_preview_grid.png"),
        target_size=(img_w, img_h)
    )

    # Step 6: 输出网格 CSV
    print(f"\n[Step 6] 输出网格 CSV ...")
    write_grid_csv(grid, args.width, args.height,
                   os.path.join(args.output_dir, "cluster_grid.csv"))

    print("\n✅ Phase 2 下采样完成！")
    if linear_clusters:
        print(f"   线性特征保护: {stats['linear_protected']} 格子 ({stats['linear_protected_pct']}%)")
    print(f"   → cluster_preview_grid.png  (网格分辨率预览)")
    print(f"   → cluster_grid.csv  (每格簇编号)")


if __name__ == "__main__":
    main()