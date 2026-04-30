#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cv_cluster_analysis.py — Round 1 辅助: 双重聚类交叉分析

在粗聚类(K=15)基础上新增细聚类(K=50)，对每个粗簇做交叉分析，
输出内部纹理复杂度、颜色统计、空间形态、边界邻居等多维特征，
生成 palette_enhanced.json 帮助 AI 更精确地识别水域。

用法:
  python cv_cluster_analysis.py <cropped_image_path> \
    --labels-coarse labels.npy \
    --palette palette.json \
    --k-fine 50 \
    --hsv-weights 2.0,1.0,0.3 \
    --output-dir <dir>

输出:
  - labels_fine.npy            — 细聚类标签矩阵 (int32)
  - palette_enhanced.json      — 增强色板 (palette.json 超集)
"""

import json
import sys
import os
import argparse
import math
import numpy as np
import cv2


# ────────────────────────── 细聚类 ──────────────────────────

def kmeans_cluster_fine(img_bgr, k_fine, hsv_weights=(2.0, 1.0, 0.3)):
    """对 BGR 图像做细粒度 K-means 聚类

    复用与 cv_cluster.py 相同的 HSV 加权策略，确保颜色空间一致。

    Args:
        img_bgr: (H, W, 3) BGR 图像
        k_fine: 细聚类数 (默认 50)
        hsv_weights: HSV 通道权重 (w_h, w_s, w_v)

    Returns:
        labels_fine_2d: (H, W) int32, 细聚类标签
        centers_bgr_fine: (k_fine, 3) uint8, 每个细簇的平均 BGR
    """
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    pixels = hsv.reshape(-1, 3).astype(np.float32)

    weights = np.array(hsv_weights, dtype=np.float32)
    weighted_pixels = pixels * weights

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1.0)
    _, labels, _ = cv2.kmeans(
        weighted_pixels, k_fine, None, criteria, attempts=10,
        flags=cv2.KMEANS_PP_CENTERS
    )
    labels_fine_2d = labels.flatten().reshape(h, w).astype(np.int32)

    # 计算每个细簇的平均 BGR
    centers_bgr_fine = []
    for i in range(k_fine):
        mask = (labels_fine_2d == i)
        if mask.sum() > 0:
            mean_bgr = img_bgr[mask].mean(axis=0).astype(np.uint8)
            centers_bgr_fine.append(mean_bgr)
        else:
            centers_bgr_fine.append(np.array([128, 128, 128], dtype=np.uint8))

    return labels_fine_2d, np.array(centers_bgr_fine)


# ────────────────────────── 内部微簇分布分析 ──────────────────────────

def analyze_internal_complexity(labels_coarse_2d, labels_fine_2d, centers_bgr_fine,
                                 k_coarse, min_pct=1.0, top_n=5):
    """对每个粗簇统计其区域内的细聚类分布

    Args:
        labels_coarse_2d: (H, W) int32, 粗聚类标签
        labels_fine_2d: (H, W) int32, 细聚类标签
        centers_bgr_fine: (k_fine, 3) uint8, 细簇平均 BGR
        k_coarse: 粗簇数量
        min_pct: 最低占比阈值(%)，低于此值的微簇不计入 fine_cluster_count
        top_n: 输出 top-N 微簇明细

    Returns:
        dict: { coarse_id: { fine_cluster_count, fine_cluster_entropy,
                              dominant_fine_ratio, fine_clusters } }
    """
    result = {}
    for ci in range(k_coarse):
        mask = (labels_coarse_2d == ci)
        total_pixels = int(mask.sum())
        if total_pixels == 0:
            result[ci] = {
                "fine_cluster_count": 0,
                "fine_cluster_entropy": 0.0,
                "dominant_fine_ratio": 0.0,
                "fine_clusters": []
            }
            continue

        # 统计该粗簇区域内每个细簇的像素数
        fine_labels_in_region = labels_fine_2d[mask]
        fine_counts = np.bincount(fine_labels_in_region.flatten(),
                                   minlength=len(centers_bgr_fine))

        # 计算各细簇占比
        fine_pcts = fine_counts / total_pixels * 100.0

        # fine_cluster_count: 占比 > min_pct 的细簇数量
        significant_mask = fine_pcts > min_pct
        fine_cluster_count = int(significant_mask.sum())

        # Shannon entropy (以所有非零细簇计算)
        nonzero_pcts = fine_pcts[fine_pcts > 0]
        probs = nonzero_pcts / nonzero_pcts.sum()
        entropy = -float(np.sum(probs * np.log2(probs + 1e-12)))

        # dominant_fine_ratio: 最大细簇的占比 (0~1)
        dominant_fine_ratio = float(fine_pcts.max() / 100.0)

        # top-N 细簇明细
        sorted_fine_ids = np.argsort(-fine_pcts)
        fine_clusters_detail = []
        for rank in range(min(top_n, len(sorted_fine_ids))):
            fid = int(sorted_fine_ids[rank])
            pct = float(fine_pcts[fid])
            if pct <= 0:
                break
            bgr = centers_bgr_fine[fid]
            fine_clusters_detail.append({
                "fine_id": fid,
                "rgb": [int(bgr[2]), int(bgr[1]), int(bgr[0])],
                "pct": round(pct, 1)
            })

        result[ci] = {
            "fine_cluster_count": fine_cluster_count,
            "fine_cluster_entropy": round(entropy, 2),
            "dominant_fine_ratio": round(dominant_fine_ratio, 3),
            "fine_clusters": fine_clusters_detail
        }

    return result


# ────────────────────────── 颜色统计 ──────────────────────────

def analyze_color_stats(img_bgr, labels_coarse_2d, k_coarse):
    """对每个粗簇计算颜色统计和纹理能量

    Args:
        img_bgr: (H, W, 3) BGR 原图
        labels_coarse_2d: (H, W) int32
        k_coarse: 粗簇数量

    Returns:
        dict: { coarse_id: { rgb_std_mean, rgb_range_mean, laplacian_var } }
    """
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    result = {}
    for ci in range(k_coarse):
        mask = (labels_coarse_2d == ci)
        total_pixels = int(mask.sum())

        if total_pixels < 10:
            result[ci] = {
                "rgb_std_mean": 0.0,
                "rgb_range_mean": 0.0,
                "laplacian_var": 0.0
            }
            continue

        # RGB 标准差
        pixels_rgb = img_rgb[mask].astype(np.float64)
        rgb_std = pixels_rgb.std(axis=0)  # 每通道标准差
        rgb_std_mean = float(rgb_std.mean())

        # RGB range (max - min per channel)
        rgb_min = pixels_rgb.min(axis=0)
        rgb_max = pixels_rgb.max(axis=0)
        rgb_range = rgb_max - rgb_min
        rgb_range_mean = float(rgb_range.mean())

        # Laplacian 方差 — 仅在 mask 区域内计算
        # 方法：取该簇的 bounding box，mask 外像素置 0，计算 Laplacian
        ys, xs = np.where(mask)
        y1, y2 = ys.min(), ys.max() + 1
        x1, x2 = xs.min(), xs.max() + 1

        gray_patch = gray[y1:y2, x1:x2].copy()
        mask_patch = mask[y1:y2, x1:x2]

        # 在 mask 外的像素用中位数填充，避免边界对 Laplacian 的影响
        median_val = int(np.median(gray_patch[mask_patch]))
        gray_patch[~mask_patch] = median_val

        laplacian = cv2.Laplacian(gray_patch, cv2.CV_64F)
        # 只取 mask 内的 Laplacian 值计算方差
        laplacian_values = laplacian[mask_patch]
        laplacian_var = float(laplacian_values.var()) if laplacian_values.size > 0 else 0.0

        result[ci] = {
            "rgb_std_mean": round(rgb_std_mean, 1),
            "rgb_range_mean": round(rgb_range_mean, 1),
            "laplacian_var": round(laplacian_var, 1)
        }

    return result


# ────────────────────────── 空间形态分析 ──────────────────────────

def analyze_spatial_shape(labels_coarse_2d, k_coarse):
    """对每个粗簇计算空间形态特征

    Args:
        labels_coarse_2d: (H, W) int32
        k_coarse: 粗簇数量

    Returns:
        dict: { coarse_id: { compactness, elongation, num_components, largest_area_ratio } }
    """
    result = {}
    for ci in range(k_coarse):
        mask = (labels_coarse_2d == ci)
        total_pixels = int(mask.sum())

        if total_pixels < 50:
            result[ci] = {
                "compactness": 0.0,
                "elongation": 1.0,
                "num_components": 0,
                "largest_area_ratio": 0.0
            }
            continue

        mask_uint8 = mask.astype(np.uint8) * 255

        # 连通区域分析
        num_cc, cc_labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask_uint8, connectivity=8)
        num_components = num_cc - 1  # 减去背景

        if num_components == 0:
            result[ci] = {
                "compactness": 0.0,
                "elongation": 1.0,
                "num_components": 0,
                "largest_area_ratio": 0.0
            }
            continue

        # 找最大连通区域
        areas = stats[1:, cv2.CC_STAT_AREA]  # 跳过背景
        largest_idx = areas.argmax() + 1  # +1 因为跳过了背景
        largest_area = int(areas.max())
        largest_area_ratio = largest_area / total_pixels

        # 最大连通区域 mask
        largest_mask = (cc_labels == largest_idx).astype(np.uint8) * 255

        # 凸包面积 → compactness = area / convex_hull_area
        contours, _ = cv2.findContours(largest_mask, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        compactness = 0.0
        if contours:
            hull = cv2.convexHull(contours[0])
            hull_area = cv2.contourArea(hull)
            if hull_area > 0:
                compactness = largest_area / hull_area

        # 等效椭圆 → elongation = 长轴 / 短轴
        elongation = 1.0
        if largest_area >= 5:
            # fitEllipse 需要至少 5 个点
            points = np.column_stack(np.where(cc_labels == largest_idx))
            if len(points) >= 5:
                try:
                    # fitEllipse 接受 (x, y) 格式
                    points_xy = points[:, ::-1].astype(np.float32)
                    ellipse = cv2.fitEllipse(points_xy)
                    (cx, cy), (axis_a, axis_b), angle = ellipse
                    major = max(axis_a, axis_b)
                    minor = min(axis_a, axis_b)
                    if minor > 0:
                        elongation = major / minor
                except cv2.error:
                    # fitEllipse 可能在退化情况下失败
                    elongation = 1.0

        result[ci] = {
            "compactness": round(float(compactness), 3),
            "elongation": round(float(elongation), 2),
            "num_components": int(num_components),
            "largest_area_ratio": round(float(largest_area_ratio), 3)
        }

    return result


# ────────────────────────── 边界邻居分析 ──────────────────────────

def analyze_border_neighbors(labels_coarse_2d, k_coarse):
    """统计每个粗簇边界接触的其他粗簇 ID

    Args:
        labels_coarse_2d: (H, W) int32
        k_coarse: 粗簇数量

    Returns:
        dict: { coarse_id: [neighbor_id_1, neighbor_id_2, ...] }
    """
    result = {}
    for ci in range(k_coarse):
        mask = (labels_coarse_2d == ci)
        if mask.sum() == 0:
            result[ci] = []
            continue

        # 膨胀 1px 得到外层边界
        mask_uint8 = mask.astype(np.uint8) * 255
        kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
        dilated = cv2.dilate(mask_uint8, kernel, iterations=1)
        border = (dilated > 0) & (~mask)

        if border.sum() == 0:
            result[ci] = []
            continue

        # 统计边界上的簇 ID
        border_labels = labels_coarse_2d[border]
        neighbor_ids = sorted(set(int(x) for x in np.unique(border_labels) if x != ci))
        result[ci] = neighbor_ids

    return result


# ────────────────────────── 合并输出 ──────────────────────────

def merge_to_enhanced_palette(palette_data, complexity, color_stats,
                                spatial_shape, border_neighbors):
    """将所有分析结果合并到 palette 数据中，生成 palette_enhanced.json

    Args:
        palette_data: list[dict], 原始 palette.json 数据
        complexity: dict from analyze_internal_complexity
        color_stats: dict from analyze_color_stats
        spatial_shape: dict from analyze_spatial_shape
        border_neighbors: dict from analyze_border_neighbors

    Returns:
        list[dict]: 增强后的 palette 数据
    """
    enhanced = []
    for entry in palette_data:
        ci = entry["cluster_id"]
        new_entry = dict(entry)  # 保留所有原始字段

        new_entry["internal_complexity"] = complexity.get(ci, {
            "fine_cluster_count": 0,
            "fine_cluster_entropy": 0.0,
            "dominant_fine_ratio": 0.0,
            "fine_clusters": []
        })

        new_entry["color_stats"] = color_stats.get(ci, {
            "rgb_std_mean": 0.0,
            "rgb_range_mean": 0.0,
            "laplacian_var": 0.0
        })

        new_entry["spatial_shape"] = spatial_shape.get(ci, {
            "compactness": 0.0,
            "elongation": 1.0,
            "num_components": 0,
            "largest_area_ratio": 0.0
        })

        new_entry["border_neighbors"] = border_neighbors.get(ci, [])

        enhanced.append(new_entry)

    return enhanced


# ────────────────────────── 摘要打印 ──────────────────────────

def print_summary(enhanced_palette):
    """打印每个粗簇的关键指标一览表"""
    print("\n  ┌──────┬────────┬───────┬─────────┬──────────┬──────────┬──────────┬───────────┐")
    print("  │ 簇ID │ 占比%  │ fine# │ entropy │ dom_rat  │ rgb_std  │ lap_var  │ elong     │")
    print("  ├──────┼────────┼───────┼─────────┼──────────┼──────────┼──────────┼───────────┤")

    for entry in enhanced_palette:
        ci = entry["cluster_id"]
        pct = entry["percentage"]
        ic = entry["internal_complexity"]
        cs = entry["color_stats"]
        ss = entry["spatial_shape"]

        fine_count = ic["fine_cluster_count"]
        entropy = ic["fine_cluster_entropy"]
        dom_ratio = ic["dominant_fine_ratio"]
        rgb_std = cs["rgb_std_mean"]
        lap_var = cs["laplacian_var"]
        elong = ss["elongation"]

        # 简单标记：可能是水域的特征
        flags = ""
        if fine_count <= 4 and dom_ratio > 0.6:
            flags += "💧"
        if fine_count >= 8 and rgb_std > 25:
            flags += "🏔️"

        print(f"  │ {ci:4d} │ {pct:5.1f}% │ {fine_count:5d} │ {entropy:7.2f} │ "
              f"{dom_ratio:8.3f} │ {rgb_std:8.1f} │ {lap_var:8.1f} │ {elong:8.2f}  │ {flags}")

    print("  └──────┴────────┴───────┴─────────┴──────────┴──────────┴──────────┴───────────┘")
    print("  💧 = 低复杂度(倾向水域)  🏔️ = 高复杂度(倾向陆地)")


# ────────────────────────── main ──────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Round 1 双重聚类交叉分析 — 生成 palette_enhanced.json")
    parser.add_argument("image_path", help="裁剪后的图片路径 (cropped.png)")
    parser.add_argument("--labels-coarse", required=True,
                        help="粗聚类标签 labels.npy 路径")
    parser.add_argument("--palette", required=True,
                        help="原始 palette.json 路径")
    parser.add_argument("--k-fine", type=int, default=50,
                        help="细聚类 K 值 (默认 50)")
    parser.add_argument("--hsv-weights", default="2.0,1.0,0.3",
                        help="HSV 通道权重 h,s,v (与粗聚类保持一致)")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # ── Step 1: 加载输入 ──
    print("[Step 1] 加载输入文件 ...")
    if not os.path.exists(args.image_path):
        print(f"[ERROR] 图片不存在: {args.image_path}")
        sys.exit(1)
    img_bgr = cv2.imread(args.image_path, cv2.IMREAD_COLOR)
    if img_bgr is None:
        print(f"[ERROR] 无法读取图片: {args.image_path}")
        sys.exit(1)
    print(f"  图片尺寸: {img_bgr.shape[1]}x{img_bgr.shape[0]}")

    labels_coarse = np.load(args.labels_coarse).astype(np.int32)
    print(f"  粗聚类标签: {labels_coarse.shape}, 簇数={labels_coarse.max() + 1}")
    k_coarse = int(labels_coarse.max()) + 1

    with open(args.palette, "r", encoding="utf-8") as f:
        palette_data = json.load(f)
    print(f"  palette.json: {len(palette_data)} 条目")

    # ── Step 2: 细聚类 ──
    hsv_weights = tuple(float(x) for x in args.hsv_weights.split(","))
    print(f"\n[Step 2] 细聚类 (K={args.k_fine}, HSV权重={hsv_weights}) ...")
    labels_fine, centers_bgr_fine = kmeans_cluster_fine(
        img_bgr, args.k_fine, hsv_weights)

    labels_fine_path = os.path.join(args.output_dir, "labels_fine.npy")
    np.save(labels_fine_path, labels_fine)
    print(f"  labels_fine.npy: {labels_fine.shape} dtype=int32")

    # ── Step 3: 交叉分析 — 内部微簇分布 ──
    print(f"\n[Step 3] 交叉分析 — 内部微簇分布 ...")
    complexity = analyze_internal_complexity(
        labels_coarse, labels_fine, centers_bgr_fine, k_coarse)
    for ci in range(k_coarse):
        ic = complexity[ci]
        print(f"  簇{ci:2d}: fine_count={ic['fine_cluster_count']:2d}, "
              f"entropy={ic['fine_cluster_entropy']:.2f}, "
              f"dominant={ic['dominant_fine_ratio']:.3f}")

    # ── Step 4: 交叉分析 — 颜色统计 ──
    print(f"\n[Step 4] 交叉分析 — 颜色统计 + Laplacian ...")
    color_stats = analyze_color_stats(img_bgr, labels_coarse, k_coarse)
    for ci in range(k_coarse):
        cs = color_stats[ci]
        print(f"  簇{ci:2d}: rgb_std={cs['rgb_std_mean']:.1f}, "
              f"rgb_range={cs['rgb_range_mean']:.1f}, "
              f"laplacian={cs['laplacian_var']:.1f}")

    # ── Step 5: 交叉分析 — 空间形态 ──
    print(f"\n[Step 5] 交叉分析 — 空间形态 ...")
    spatial = analyze_spatial_shape(labels_coarse, k_coarse)
    for ci in range(k_coarse):
        ss = spatial[ci]
        print(f"  簇{ci:2d}: compact={ss['compactness']:.3f}, "
              f"elong={ss['elongation']:.2f}, "
              f"components={ss['num_components']}, "
              f"largest_ratio={ss['largest_area_ratio']:.3f}")

    # ── Step 6: 交叉分析 — 边界邻居 ──
    print(f"\n[Step 6] 交叉分析 — 边界邻居 ...")
    neighbors = analyze_border_neighbors(labels_coarse, k_coarse)
    for ci in range(k_coarse):
        print(f"  簇{ci:2d}: neighbors={neighbors[ci]}")

    # ── Step 7: 合并输出 palette_enhanced.json ──
    print(f"\n[Step 7] 合并输出 palette_enhanced.json ...")
    enhanced = merge_to_enhanced_palette(
        palette_data, complexity, color_stats, spatial, neighbors)

    enhanced_path = os.path.join(args.output_dir, "palette_enhanced.json")
    with open(enhanced_path, "w", encoding="utf-8") as f:
        json.dump(enhanced, f, indent=2, ensure_ascii=False)
    print(f"  palette_enhanced.json: {enhanced_path}")

    # ── 摘要 ──
    print(f"\n[摘要] 各粗簇关键指标一览:")
    print_summary(enhanced)

    print(f"\n✅ 双重聚类交叉分析完成！")
    print(f"   → labels_fine.npy  (K={args.k_fine} 细聚类标签)")
    print(f"   → palette_enhanced.json  (增强色板，含内部复杂度/颜色统计/空间形态/邻居)")
    print(f"\n   下一步：AI 参考 palette_enhanced.json 判断水域簇")


if __name__ == "__main__":
    main()
