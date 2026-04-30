"""
cv_subregion_analysis.py — 大陆内部子区域分析脚本

功能: 利用 Round 1 的 K=50 细聚类数据，对每个大陆内部进行微簇统计分析，
      为 Round 2 AI 提供"哪些子区域可以被 CV 精确定位"的辅助信息。

输入:
  - labels_fine.npy: K=50 细聚类标签 (原图分辨率)
  - continent_map_full.npy: 大陆编号图 (原图分辨率)
  - cropped.png: 裁剪后原图
  - water_mask_full.npy: 水域 mask (原图分辨率)
  - output_dir: 输出目录
  - --min-area: 大陆最小面积阈值 (网格格子数, 默认 50)

输出:
  - continent_subregions.json: 每个大陆的微簇子区域分析结果
  - subregion_preview.png: 可视化预览图

用法:
    python cv_subregion_analysis.py <labels_fine.npy> <continent_map_full.npy> \
        <cropped.png> <water_mask_full.npy> <output_dir> [--min-area 50]
"""

import sys
import os
import json
import argparse
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import math


# ---------------------------------------------------------------------------
# CIE76 色差 (简化版，基于 RGB 欧氏距离 — 对于本场景足够)
# ---------------------------------------------------------------------------
def delta_e_rgb(rgb1, rgb2):
    """CIE76 近似: RGB 空间的欧氏距离。"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)))


# ---------------------------------------------------------------------------
# 微簇合并 (相近颜色)
# ---------------------------------------------------------------------------
def merge_close_clusters(clusters, threshold=15.0):
    """
    将 RGB 欧氏距离 < threshold 的微簇合并。

    Args:
        clusters: list of dict, 每个含 fine_id, avg_rgb, pixel_count
        threshold: RGB 空间距离阈值

    Returns:
        list of dict, 合并后的 subregion
    """
    if not clusters:
        return []

    # 按 pixel_count 降序排列
    sorted_clusters = sorted(clusters, key=lambda c: c["pixel_count"], reverse=True)

    merged = []
    used = set()

    for i, c in enumerate(sorted_clusters):
        if i in used:
            continue

        group = [c]
        used.add(i)

        for j in range(i + 1, len(sorted_clusters)):
            if j in used:
                continue
            if delta_e_rgb(c["avg_rgb"], sorted_clusters[j]["avg_rgb"]) < threshold:
                group.append(sorted_clusters[j])
                used.add(j)

        # 合并为一个 subregion
        total_px = sum(g["pixel_count"] for g in group)
        weighted_rgb = [0.0, 0.0, 0.0]
        for g in group:
            w = g["pixel_count"] / total_px
            for ch in range(3):
                weighted_rgb[ch] += g["avg_rgb"][ch] * w

        merged.append({
            "fine_ids": [g["fine_id"] for g in group],
            "avg_rgb": [int(round(v)) for v in weighted_rgb],
            "pixel_count": total_px,
        })

    return merged


# ---------------------------------------------------------------------------
# 主分析逻辑
# ---------------------------------------------------------------------------
def analyze_continents(labels_fine, continent_map, image, water_mask,
                       map_info, min_area=50):
    """
    对每个大陆内部做微簇分析。

    Args:
        labels_fine: ndarray (H, W) — K=50 微簇标签
        continent_map: ndarray (H, W) — 大陆编号图 (原图分辨率)
        image: ndarray (H, W, 3) — RGB 原图
        water_mask: ndarray (H, W) — 水域 mask (原图分辨率)
        map_info: dict — 地图信息 (width, height)
        min_area: int — 大陆最小面积阈值 (网格格子)

    Returns:
        dict — continent_subregions 数据
    """
    map_w = map_info["width"]
    map_h = map_info["height"]
    img_h, img_w = labels_fine.shape

    # 像素到网格的缩放因子
    px_per_grid_x = img_w / map_w
    px_per_grid_z = img_h / map_h

    # 获取所有大陆 ID
    unique_continents = np.unique(continent_map)
    # 排除 0 (通常是水域/边界)
    unique_continents = unique_continents[unique_continents > 0]

    result = {"continents": {}}

    for cid in unique_continents:
        c_mask = (continent_map == cid)
        total_pixels = c_mask.sum()

        # 计算网格面积
        area_grids = int(round(total_pixels / (px_per_grid_x * px_per_grid_z)))

        if area_grids < min_area:
            continue

        # 计算 bbox (网格坐标)
        ys, xs = np.where(c_mask)
        bbox_px = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
        bbox_grid = [
            int(round(bbox_px[0] / px_per_grid_x)),
            int(round(bbox_px[1] / px_per_grid_z)),
            int(round(bbox_px[2] / px_per_grid_x)),
            int(round(bbox_px[3] / px_per_grid_z)),
        ]

        # 统计内部微簇分布
        fine_in_cont = labels_fine[c_mask]
        rgb_in_cont = image[c_mask]  # (N, 3)

        unique_fines, fine_counts = np.unique(fine_in_cont, return_counts=True)

        # 构建微簇列表
        clusters = []
        for fid, cnt in zip(unique_fines, fine_counts):
            pct = cnt / total_pixels * 100
            if pct < 0.5:
                continue  # 忽略极小微簇

            sub_mask = c_mask & (labels_fine == fid)
            avg_rgb = image[sub_mask].mean(axis=0).astype(int).tolist()

            clusters.append({
                "fine_id": int(fid),
                "avg_rgb": avg_rgb,
                "pixel_count": int(cnt),
                "area_pct": round(pct, 1),
            })

        # 合并相近微簇
        merged = merge_close_clusters(clusters, threshold=15.0)

        # 识别底色 (面积最大的 subregion)
        if not merged:
            continue

        merged.sort(key=lambda s: s["pixel_count"], reverse=True)
        base_rgb = merged[0]["avg_rgb"]

        # 计算色差并标记
        subregions = []
        for sub in merged:
            area_pct = round(sub["pixel_count"] / total_pixels * 100, 1)
            de = round(delta_e_rgb(sub["avg_rgb"], base_rgb), 1)
            is_base = (sub is merged[0])
            separable = (de > 30) and not is_base

            subregions.append({
                "fine_ids": sub["fine_ids"],
                "avg_rgb": sub["avg_rgb"],
                "area_pct": area_pct,
                "delta_e": de,
                "is_base": is_base,
                "separable": separable,
            })

        result["continents"][str(int(cid))] = {
            "area_grids": area_grids,
            "bbox": bbox_grid,
            "base_rgb": base_rgb,
            "subregions": subregions,
        }

    return result


# ---------------------------------------------------------------------------
# 可视化
# ---------------------------------------------------------------------------
def generate_preview(image, continent_map, labels_fine, subregion_data, output_path):
    """
    生成 subregion_preview.png：
      - 原图
      - 大陆边界轮廓
      - 高色差 (separable) 子区域半透明着色
      - 大陆编号标注
    """
    img_h, img_w = image.shape[:2]
    base = Image.fromarray(image).convert("RGBA")
    overlay = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    overlay_arr = np.array(overlay)

    # 预定义高亮颜色 (半透明)
    highlight_colors = [
        (255, 50, 50, 100),    # 红
        (50, 255, 50, 100),    # 绿
        (50, 50, 255, 100),    # 蓝
        (255, 255, 50, 100),   # 黄
        (255, 50, 255, 100),   # 紫
        (50, 255, 255, 100),   # 青
        (255, 150, 50, 100),   # 橙
        (150, 50, 255, 100),   # 靛
    ]
    color_idx = 0

    for cid_str, cdata in subregion_data["continents"].items():
        cid = int(cid_str)
        c_mask = (continent_map == cid)

        # 高亮 separable 子区域
        for sub in cdata["subregions"]:
            if not sub.get("separable", False):
                continue

            # 获取该子区域的像素 mask
            sub_mask = np.zeros((img_h, img_w), dtype=bool)
            for fid in sub["fine_ids"]:
                sub_mask |= (labels_fine == fid)
            sub_mask &= c_mask  # 限定在该大陆内

            # 着色
            color = highlight_colors[color_idx % len(highlight_colors)]
            overlay_arr[sub_mask] = color
            color_idx += 1

    # 大陆边界轮廓
    # 用简单的膨胀-原始差集来找边界
    from scipy import ndimage
    unique_continents = np.unique(continent_map)
    unique_continents = unique_continents[unique_continents > 0]
    border_mask = np.zeros((img_h, img_w), dtype=bool)

    for cid in unique_continents:
        c_mask = (continent_map == cid)
        dilated = ndimage.binary_dilation(c_mask, iterations=2)
        border = dilated & ~c_mask
        border_mask |= border

    overlay_arr[border_mask] = (255, 255, 255, 180)

    # 合成
    overlay = Image.fromarray(overlay_arr, "RGBA")
    composite = Image.alpha_composite(base, overlay)

    # 标注大陆编号
    draw = ImageDraw.Draw(composite)
    for cid_str, cdata in subregion_data["continents"].items():
        cid = int(cid_str)
        bbox = cdata["bbox"]  # 网格坐标，需要转回像素
        c_mask = (continent_map == cid)
        ys, xs = np.where(c_mask)
        if len(xs) == 0:
            continue
        # 大陆中心
        cx = int(xs.mean())
        cy = int(ys.mean())

        # 标注文字
        sep_count = sum(1 for s in cdata["subregions"] if s.get("separable"))
        label = f"C{cid}"
        if sep_count > 0:
            label += f" ({sep_count}sep)"

        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except (IOError, OSError):
            font = ImageFont.load_default()

        # 黑色背景 + 白色文字
        text_bbox = draw.textbbox((cx, cy), label, font=font)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]
        tx = cx - tw // 2
        ty = cy - th // 2
        draw.rectangle([tx - 2, ty - 2, tx + tw + 2, ty + th + 2],
                        fill=(0, 0, 0, 180))
        draw.text((tx, ty), label, fill=(255, 255, 255, 255), font=font)

    composite.save(output_path, "PNG")
    print(f"[preview] 保存预览图 → {output_path}")


# ---------------------------------------------------------------------------
# 大陆裁剪图生成
# ---------------------------------------------------------------------------
def generate_continent_crops(image, continent_map, water_mask, subregion_data,
                              output_dir, padding_pct=0.15):
    """
    为每个大陆生成裁剪放大图，附带九宫格网格线和大陆编号标注。
    AI 通过看这些局部放大图来更精确地标注装饰物。

    Args:
        image: (H, W, 3) RGB
        continent_map: (H, W) int32
        water_mask: (H, W) bool
        subregion_data: continent_subregions.json 数据
        output_dir: 输出目录
        padding_pct: 裁剪框外扩比例（默认 15%，让周围河流也可见）
    """
    crops_dir = os.path.join(output_dir, "continent_crops")
    os.makedirs(crops_dir, exist_ok=True)

    img_h, img_w = image.shape[:2]

    for cid_str, cdata in subregion_data["continents"].items():
        cid = int(cid_str)
        c_mask = (continent_map == cid)
        ys, xs = np.where(c_mask)
        if len(xs) == 0:
            continue

        # 计算 bbox (像素坐标)
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        bw = x_max - x_min
        bh = y_max - y_min

        # 外扩 padding
        pad_x = int(bw * padding_pct)
        pad_y = int(bh * padding_pct)
        crop_x1 = max(0, x_min - pad_x)
        crop_y1 = max(0, y_min - pad_y)
        crop_x2 = min(img_w, x_max + pad_x)
        crop_y2 = min(img_h, y_max + pad_y)

        # 裁剪原图
        crop_img = image[crop_y1:crop_y2, crop_x1:crop_x2].copy()

        # 水域半透明遮罩（让大陆区域更突出）
        crop_water = water_mask[crop_y1:crop_y2, crop_x1:crop_x2]
        crop_img[crop_water] = (crop_img[crop_water] * 0.5 + np.array([30, 60, 80]) * 0.5).astype(np.uint8)

        # 非本大陆陆地区域变暗（聚焦当前大陆）
        crop_continent = continent_map[crop_y1:crop_y2, crop_x1:crop_x2]
        other_land = (~crop_water) & (crop_continent != cid)
        crop_img[other_land] = (crop_img[other_land] * 0.6).astype(np.uint8)

        # 转 PIL 绘制标注
        pil_img = Image.fromarray(crop_img)
        draw = ImageDraw.Draw(pil_img)

        # 绘制九宫格线（基于大陆在裁剪图中的 bbox）
        local_x_min = x_min - crop_x1
        local_x_max = x_max - crop_x1
        local_y_min = y_min - crop_y1
        local_y_max = y_max - crop_y1
        local_bw = local_x_max - local_x_min
        local_bh = local_y_max - local_y_min

        # 画九宫格
        grid_color = (255, 255, 0, 128)  # 黄色半透明
        for i in range(1, 3):
            # 竖线
            gx = local_x_min + int(local_bw * i / 3)
            draw.line([(gx, local_y_min), (gx, local_y_max)], fill=grid_color, width=1)
            # 横线
            gy = local_y_min + int(local_bh * i / 3)
            draw.line([(local_x_min, gy), (local_x_max, gy)], fill=grid_color, width=1)

        # 标注九宫格方位名
        try:
            font = ImageFont.truetype("arial.ttf", max(10, min(local_bw, local_bh) // 15))
        except (IOError, OSError):
            font = ImageFont.load_default()

        positions = [
            ("NW", 0, 0), ("N", 1, 0), ("NE", 2, 0),
            ("W", 0, 1),  ("C", 1, 1), ("E", 2, 1),
            ("SW", 0, 2), ("S", 1, 2), ("SE", 2, 2),
        ]
        for label, col, row in positions:
            lx = local_x_min + int(local_bw * (col + 0.5) / 3)
            ly = local_y_min + int(local_bh * (row + 0.5) / 3)
            draw.text((lx - 5, ly - 5), label, fill=(255, 255, 0), font=font)

        # 大陆标题
        try:
            title_font = ImageFont.truetype("arial.ttf", max(14, min(local_bw, local_bh) // 10))
        except (IOError, OSError):
            title_font = ImageFont.load_default()

        title = f"Continent {cid} ({cdata['area_grids']} grids)"
        draw.text((4, 4), title, fill=(255, 255, 255), font=title_font)

        # 保存
        crop_path = os.path.join(crops_dir, f"continent_{cid}.png")
        pil_img.save(crop_path, "PNG")

    n_crops = len(subregion_data["continents"])
    print(f"[crops] 生成 {n_crops} 张大陆裁剪图 → {crops_dir}/")
    return crops_dir


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="大陆内部子区域分析（Round 2 CV 辅助）"
    )
    parser.add_argument("labels_fine", help="K=50 细聚类标签 .npy")
    parser.add_argument("continent_map", help="大陆编号图 .npy (原图分辨率)")
    parser.add_argument("cropped_img", help="裁剪后原图 .png")
    parser.add_argument("water_mask", help="水域 mask .npy (原图分辨率)")
    parser.add_argument("output_dir", help="输出目录")
    parser.add_argument("--min-area", type=int, default=50,
                        help="大陆最小面积阈值 (网格格子数, 默认 50)")

    args = parser.parse_args()

    # 验证输入文件
    for path, name in [
        (args.labels_fine, "labels_fine.npy"),
        (args.continent_map, "continent_map_full.npy"),
        (args.cropped_img, "cropped.png"),
        (args.water_mask, "water_mask_full.npy"),
    ]:
        if not os.path.exists(path):
            print(f"[ERROR] 文件不存在: {path} ({name})")
            sys.exit(1)

    # 读取 map_info.json (从 output_dir 或 labels_fine 同目录)
    map_info_path = os.path.join(args.output_dir, "map_info.json")
    if not os.path.exists(map_info_path):
        map_info_path = os.path.join(
            os.path.dirname(args.labels_fine), "map_info.json"
        )
    if not os.path.exists(map_info_path):
        print(f"[ERROR] 找不到 map_info.json")
        sys.exit(1)

    with open(map_info_path, "r", encoding="utf-8") as f:
        map_info = json.load(f)
    print(f"[info] 地图: {map_info['width']}x{map_info['height']}")

    # 加载数据
    print("[info] 加载数据...")
    labels_fine = np.load(args.labels_fine)
    continent_map = np.load(args.continent_map)
    image = np.array(Image.open(args.cropped_img).convert("RGB"))
    water_mask = np.load(args.water_mask)

    print(f"  labels_fine: {labels_fine.shape}, unique={len(np.unique(labels_fine))}")
    print(f"  continent_map: {continent_map.shape}")
    print(f"  image: {image.shape}")
    print(f"  water_mask: {water_mask.shape}")

    # 确保尺寸一致
    assert labels_fine.shape == continent_map.shape, \
        f"labels_fine {labels_fine.shape} != continent_map {continent_map.shape}"
    assert labels_fine.shape[:2] == image.shape[:2], \
        f"labels_fine {labels_fine.shape} != image {image.shape[:2]}"

    # 分析
    print(f"[info] 分析大陆子区域 (min_area={args.min_area})...")
    result = analyze_continents(
        labels_fine, continent_map, image, water_mask,
        map_info, min_area=args.min_area
    )

    # 统计
    n_cont = len(result["continents"])
    n_sep = sum(
        sum(1 for s in cdata["subregions"] if s.get("separable"))
        for cdata in result["continents"].values()
    )
    print(f"[info] 分析了 {n_cont} 个大陆, 发现 {n_sep} 个高色差可分离子区域")

    # 输出 JSON
    os.makedirs(args.output_dir, exist_ok=True)
    json_path = os.path.join(args.output_dir, "continent_subregions.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[output] {json_path}")

    # 生成预览图
    preview_path = os.path.join(args.output_dir, "subregion_preview.png")
    generate_preview(image, continent_map, labels_fine, result, preview_path)

    # 生成大陆裁剪图
    water_mask = np.load(args.water_mask)
    generate_continent_crops(image, continent_map, water_mask, result, args.output_dir)

    print("[done] 子区域分析完成")


if __name__ == "__main__":
    main()
