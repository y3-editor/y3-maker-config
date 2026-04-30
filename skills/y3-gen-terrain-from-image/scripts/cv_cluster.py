#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cv_cluster.py — Phase 1: CV 聚类

对图片做 K-means 聚类，输出：
  - palette.json  — 每个簇的 HSV/BGR 值、像素占比
  - palette.png   — 色板可视化图片
  - cluster_preview.png — 像素分辨率预览图（每像素用簇的平均颜色着色）
  - labels.npy    — 高分辨率聚类标签矩阵（供 cv_downsample.py 使用）

用法:
  python cv_cluster.py <image_path> --k 15 --output-dir <dir> [--crop x1,y1,x2,y2] [--no-auto-crop]

注意: 本脚本不做下采样，不需要地图尺寸参数。
      下采样由 cv_downsample.py 完成。
"""

import json
import sys
import os
import argparse
import numpy as np
import cv2


def load_and_crop(image_path, crop_str=None, auto_crop=True):
    """读取图片，支持手动裁剪和自动裁剪边缘文字区域"""
    if not os.path.exists(image_path):
        print(f"[ERROR] 图片不存在: {image_path}")
        sys.exit(1)
    img = cv2.imread(image_path, cv2.IMREAD_COLOR)
    if img is None:
        print(f"[ERROR] 无法读取图片: {image_path}")
        sys.exit(1)
    print(f"  原始尺寸: {img.shape[1]}x{img.shape[0]}")

    if crop_str:
        parts = [int(x) for x in crop_str.split(",")]
        x1, y1, x2, y2 = parts
        img = img[y1:y2, x1:x2]
        print(f"  手动裁剪后: {img.shape[1]}x{img.shape[0]}")
    elif auto_crop:
        img = auto_crop_borders(img)

    return img


def auto_crop_borders(img):
    """
    自动检测并裁剪图片四条边的文字说明/图例/纯色边框区域。

    原理：对每条边做逐行/逐列扫描，检测两个特征：
    1. 颜色方差极低（纯色背景条带，如白底、黑底、灰底）
    2. 高对比度文字特征（大面积浅色背景中夹杂深色像素，或反之）

    从边缘向内扫描，一旦遇到"丰富颜色行/列"就停止裁剪。
    安全阈值：最多裁掉每条边 30% 的宽/高，防止误裁地图主体。
    """
    h, w = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    sat = hsv[:, :, 1]  # 饱和度通道

    max_crop_ratio = 0.30  # 每条边最多裁 30%

    sat_threshold = 25
    std_threshold = 60
    min_sat_rich = 30

    def is_border_strip(strip_gray, strip_sat):
        """判断一条行/列像素是否属于边框/文字区域"""
        mean_sat = np.mean(strip_sat)
        std_gray = np.std(strip_gray)

        if mean_sat < sat_threshold:
            return True
        if mean_sat < min_sat_rich and std_gray < 15:
            return True
        return False

    # --- 扫描上边 ---
    top = 0
    max_top = int(h * max_crop_ratio)
    for y in range(max_top):
        if is_border_strip(gray[y, :], sat[y, :]):
            top = y + 1
        else:
            break

    # --- 扫描下边 ---
    bottom = h
    max_bottom = h - int(h * max_crop_ratio)
    for y in range(h - 1, max_bottom - 1, -1):
        if is_border_strip(gray[y, :], sat[y, :]):
            bottom = y
        else:
            break

    # --- 扫描左边 ---
    left = 0
    max_left = int(w * max_crop_ratio)
    for x in range(max_left):
        if is_border_strip(gray[:, x], sat[:, x]):
            left = x + 1
        else:
            break

    # --- 扫描右边 ---
    right = w
    max_right = w - int(w * max_crop_ratio)
    for x in range(w - 1, max_right - 1, -1):
        if is_border_strip(gray[:, x], sat[:, x]):
            right = x
        else:
            break

    # 应用裁剪
    if top > 0 or bottom < h or left > 0 or right < w:
        crop_area = (right - left) * (bottom - top)
        orig_area = w * h
        if crop_area < orig_area * 0.4:
            print(f"  ⚠️ 自动裁剪面积过大 ({100 - crop_area*100/orig_area:.0f}%)，跳过自动裁剪")
            return img

        print(f"  🔍 自动裁剪检测: 上={top}px 下={h-bottom}px 左={left}px 右={w-right}px")
        img = img[top:bottom, left:right]
        print(f"  ✂️ 自动裁剪后: {img.shape[1]}x{img.shape[0]}")
    else:
        print(f"  ✅ 未检测到边缘文字区域，无需裁剪")

    return img


def kmeans_cluster(img, k, hsv_weights=(2.0, 1.0, 0.3)):
    """对 BGR 图像做 K-means 聚类，返回 (labels_2d, centers_bgr, centers_hsv)

    Args:
        img: BGR 图像
        k: 聚类数
        hsv_weights: HSV 通道权重 (w_h, w_s, w_v)，明度(V)降权可减少
                     深浅（高度信息）对聚类的影响，使色相主导聚类结果。
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]
    pixels = hsv.reshape(-1, 3).astype(np.float32)

    # 应用 HSV 通道权重：H 主导聚类，V 降权（深浅=高度信息，非纹理差异）
    weights = np.array(hsv_weights, dtype=np.float32)
    weighted_pixels = pixels * weights
    print(f"  HSV 权重: H={hsv_weights[0]}, S={hsv_weights[1]}, V={hsv_weights[2]}")

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 100, 1.0)
    _, labels, centers_hsv = cv2.kmeans(
        weighted_pixels, k, None, criteria, attempts=10, flags=cv2.KMEANS_PP_CENTERS
    )
    labels_2d = labels.flatten().reshape(h, w)

    # 计算每个簇的 BGR 中心（用于预览着色）
    centers_bgr = []
    for i in range(k):
        mask = (labels_2d == i)
        if mask.sum() > 0:
            mean_bgr = img[mask].mean(axis=0).astype(np.uint8)
            centers_bgr.append(mean_bgr)
        else:
            centers_bgr.append(np.array([128, 128, 128], dtype=np.uint8))

    return labels_2d, np.array(centers_bgr), centers_hsv


def generate_preview(labels_2d, centers_bgr, output_path):
    """生成像素分辨率预览图，每像素用该簇的真实平均颜色着色"""
    h, w = labels_2d.shape
    preview = np.zeros((h, w, 3), dtype=np.uint8)
    for i, bgr in enumerate(centers_bgr):
        mask = (labels_2d == i)
        preview[mask] = bgr
    cv2.imwrite(output_path, preview)
    print(f"  预览图: {output_path}")


def generate_labeled_preview(labels_2d, centers_bgr, output_path):
    """生成带簇 ID 标注的预览图。

    在每个簇的最大连通区域的质心位置叠加簇 ID 数字，
    方便用户对照 palette 表格确认每个簇在图上的位置。
    文字使用对比色（亮底黑字、暗底白字）确保可读性。
    """
    h, w = labels_2d.shape
    k = len(centers_bgr)

    # 先画底图
    preview = np.zeros((h, w, 3), dtype=np.uint8)
    for i, bgr in enumerate(centers_bgr):
        mask = (labels_2d == i)
        preview[mask] = bgr

    # 根据图片尺寸自适应字号
    font = cv2.FONT_HERSHEY_SIMPLEX
    base_dim = min(h, w)
    if base_dim >= 800:
        font_scale = 1.2
        thickness = 3
    elif base_dim >= 400:
        font_scale = 0.8
        thickness = 2
    else:
        font_scale = 0.5
        thickness = 1

    for i in range(k):
        mask_i = (labels_2d == i).astype(np.uint8)
        if mask_i.sum() == 0:
            continue

        # 找到该簇最大连通区域的质心
        num_cc, cc_labels, stats, centroids = cv2.connectedComponentsWithStats(
            mask_i, connectivity=8)

        if num_cc <= 1:
            continue

        # stats: [x, y, w, h, area], 跳过 label=0 (背景)
        areas = stats[1:, cv2.CC_STAT_AREA]
        largest_cc_idx = areas.argmax() + 1  # +1 因为跳过了背景
        cx, cy = centroids[largest_cc_idx]
        cx, cy = int(cx), int(cy)

        # 确保标注不超出图片边界
        cx = max(10, min(cx, w - 10))
        cy = max(20, min(cy, h - 10))

        # 文字对比色：亮底用黑字，暗底用白字
        bgr = centers_bgr[i]
        brightness = int(bgr[0]) * 0.114 + int(bgr[1]) * 0.587 + int(bgr[2]) * 0.299
        text_color = (0, 0, 0) if brightness > 128 else (255, 255, 255)
        outline_color = (255, 255, 255) if brightness > 128 else (0, 0, 0)

        label_text = str(i)
        # 先画轮廓（提高可读性）
        cv2.putText(preview, label_text, (cx - 5, cy + 5),
                    font, font_scale, outline_color, thickness + 2)
        # 再画正文
        cv2.putText(preview, label_text, (cx - 5, cy + 5),
                    font, font_scale, text_color, thickness)

    cv2.imwrite(output_path, preview)
    print(f"  标注预览图: {output_path}")


def generate_palette(k, centers_bgr, centers_hsv, labels_2d, output_path):
    """生成色板信息图 + JSON，展示每个簇的颜色、HSV 值、占比"""
    total = labels_2d.size
    flat = labels_2d.flatten()

    clusters_info = []
    for i in range(k):
        count = int((flat == i).sum())
        pct = count * 100.0 / total
        bgr = centers_bgr[i]
        hsv = centers_hsv[i]
        clusters_info.append({
            "cluster_id": i,
            "bgr": [int(bgr[0]), int(bgr[1]), int(bgr[2])],
            "rgb": [int(bgr[2]), int(bgr[1]), int(bgr[0])],
            "hsv_opencv": [float(hsv[0]), float(hsv[1]), float(hsv[2])],
            "hsv_human": {
                "h": round(float(hsv[0]) * 2, 1),  # 0-360
                "s": round(float(hsv[1]) / 2.55, 1),  # 0-100%
                "v": round(float(hsv[2]) / 2.55, 1)   # 0-100%
            },
            "count": count,
            "percentage": round(pct, 1)
        })

    # 按占比排序
    clusters_info.sort(key=lambda x: -x["percentage"])

    # 输出 JSON
    json_path = output_path.replace(".png", ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(clusters_info, f, indent=2, ensure_ascii=False)
    print(f"  色板 JSON: {json_path}")

    # 生成色板图片
    swatch_h = 40
    swatch_w = 60
    text_w = 320
    img_h = k * swatch_h + 20
    img_w = swatch_w + text_w + 20
    palette_img = np.ones((img_h, img_w, 3), dtype=np.uint8) * 255

    for idx, ci in enumerate(clusters_info):
        y = idx * swatch_h + 10
        bgr = ci["bgr"]
        cv2.rectangle(palette_img, (10, y), (10 + swatch_w, y + swatch_h - 4),
                       (int(bgr[0]), int(bgr[1]), int(bgr[2])), -1)
        cv2.rectangle(palette_img, (10, y), (10 + swatch_w, y + swatch_h - 4),
                       (0, 0, 0), 1)

        hsv_h = ci["hsv_human"]
        text = f"#{ci['cluster_id']:2d}  H={hsv_h['h']:5.1f} S={hsv_h['s']:4.1f}% V={hsv_h['v']:4.1f}%  {ci['percentage']:4.1f}%"
        cv2.putText(palette_img, text, (10 + swatch_w + 8, y + 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0, 0, 0), 1)

    cv2.imwrite(output_path, palette_img)
    print(f"  色板图片: {output_path}")

    # 控制台输出
    print(f"\n  簇色板 (K={k}):")
    for ci in clusters_info:
        h = ci["hsv_human"]
        bar = "█" * max(1, int(ci["percentage"] / 2))
        print(f"    簇{ci['cluster_id']:2d}: H={h['h']:5.1f}° S={h['s']:4.1f}% V={h['v']:4.1f}%  "
              f"{ci['percentage']:5.1f}% {bar}")

    return clusters_info


def main():
    parser = argparse.ArgumentParser(description="CV 聚类 Phase 1 — 聚类 + 预览 + 色板 + labels.npy")
    parser.add_argument("image_path", help="图片路径")
    parser.add_argument("--k", type=int, default=15, help="K-means 聚类数 (默认 15)")
    parser.add_argument("--crop", default=None, help="手动裁剪区域 x1,y1,x2,y2（优先于自动裁剪）")
    parser.add_argument("--no-auto-crop", action="store_true", help="禁用自动裁剪边缘文字区域")
    parser.add_argument("--hsv-weights", default="2.0,1.0,0.3",
                        help="HSV 通道权重 h,s,v（默认 2.0,1.0,0.3，V降权减少深浅对聚类的影响）")
    parser.add_argument("--output-dir", default=".", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    # Step 1: 读取图片（自动裁剪边缘文字/图例）
    print("[Step 1] 读取图片 ...")
    img = load_and_crop(args.image_path, args.crop, auto_crop=not args.no_auto_crop)

    # Step 1b: 保存裁剪后的图片（供后续 Round 使用）
    cropped_path = os.path.join(args.output_dir, "cropped.png")
    cv2.imwrite(cropped_path, img)
    print(f"  裁剪后图片已保存: {cropped_path} ({img.shape[1]}x{img.shape[0]})")

    # Step 2: K-means 聚类
    print(f"\n[Step 2] K-means 聚类 (K={args.k}) ...")
    hsv_weights = tuple(float(x) for x in args.hsv_weights.split(","))
    labels_2d, centers_bgr, centers_hsv = kmeans_cluster(img, args.k, hsv_weights)

    # Step 3: 保存 labels.npy（高分辨率聚类标签）
    print(f"\n[Step 3] 保存 labels.npy ...")
    labels_path = os.path.join(args.output_dir, "labels.npy")
    np.save(labels_path, labels_2d.astype(np.int32))
    print(f"  labels.npy: {labels_path}  shape={labels_2d.shape} dtype=int32")

    # Step 4: 保存 centers（供 downsample 使用）
    centers_bgr_path = os.path.join(args.output_dir, "centers_bgr.npy")
    np.save(centers_bgr_path, centers_bgr)
    print(f"  centers_bgr.npy: {centers_bgr_path}")

    # Step 5: 生成像素分辨率预览图
    print(f"\n[Step 4] 生成预览图 ...")
    generate_preview(labels_2d, centers_bgr,
                     os.path.join(args.output_dir, "cluster_preview.png"))

    # Step 5b: 生成带簇 ID 标注的预览图
    print(f"\n[Step 4b] 生成标注预览图 ...")
    generate_labeled_preview(labels_2d, centers_bgr,
                             os.path.join(args.output_dir, "cluster_preview_labeled.png"))

    # Step 6: 生成色板
    print(f"\n[Step 5] 生成色板 ...")
    generate_palette(
        args.k, centers_bgr, centers_hsv, labels_2d,
        os.path.join(args.output_dir, "palette.png")
    )

    print("\n✅ Phase 1 聚类完成！")
    print(f"   → cluster_preview.png  (像素分辨率预览)")
    print(f"   → cluster_preview_labeled.png  (带簇 ID 标注预览)")
    print(f"   → palette.png + palette.json  (簇色板)")
    print(f"   → labels.npy  (高分辨率聚类标签)")
    print(f"   → centers_bgr.npy  (簇 BGR 中心)")
    print(f"\n   下一步：AI 预分类识别线性特征簇 → cv_downsample.py 加权下采样")


if __name__ == "__main__":
    main()