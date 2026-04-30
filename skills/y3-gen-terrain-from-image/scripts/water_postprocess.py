"""
water_postprocess.py — 水域后处理脚本

功能: 检测并填回被陆地完全包围的孤立水域区域。
算法: 使用 scipy.ndimage.label 做连通区分析，判断每个水域连通区
     是否触碰地图四边。未触碰边缘的水域 100% 为误判，填回陆地。

输入: water_mask_grid.npy (bool 矩阵, True=水域, False=陆地)
输出: water_mask_grid.npy (修正后，原地覆盖)

用法:
    python water_postprocess.py <npy_path>
"""

import sys
import numpy as np
from scipy.ndimage import label


def find_and_fill_isolated_water(water_mask: np.ndarray) -> dict:
    """
    检测被陆地完全包围的水域连通区并填回陆地。

    Args:
        water_mask: 2D bool ndarray, True=水域, False=陆地
                    会被原地修改。

    Returns:
        dict: 修复报告
            - regions_found: 孤立水域连通区数量
            - cells_filled: 被填回陆地的总格子数
            - details: 每个被填区域的 {label, size, bbox}
    """
    h, w = water_mask.shape

    # 连通区标记（4-连通）
    labeled, num_features = label(water_mask.astype(np.int32))

    filled_details = []
    total_filled = 0

    for region_id in range(1, num_features + 1):
        region_mask = labeled == region_id
        rows, cols = np.where(region_mask)

        # 判断是否触碰地图四边
        touches_edge = (
            rows.min() == 0 or
            rows.max() == h - 1 or
            cols.min() == 0 or
            cols.max() == w - 1
        )

        if not touches_edge:
            # 被陆地完全包围 → 填回陆地
            cell_count = int(region_mask.sum())
            bbox = {
                "z_min": int(rows.min()),
                "z_max": int(rows.max()),
                "x_min": int(cols.min()),
                "x_max": int(cols.max()),
            }
            water_mask[region_mask] = False
            total_filled += cell_count
            filled_details.append({
                "label": region_id,
                "size": cell_count,
                "bbox": bbox,
            })

    return {
        "regions_found": len(filled_details),
        "cells_filled": total_filled,
        "details": filled_details,
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: python water_postprocess.py <water_mask_grid.npy>")
        sys.exit(1)

    npy_path = sys.argv[1]
    water_mask = np.load(npy_path)

    print(f"[water_postprocess] 加载 {npy_path}: shape={water_mask.shape}, "
          f"水域格数={water_mask.sum()}")

    report = find_and_fill_isolated_water(water_mask)

    if report["regions_found"] == 0:
        print("[water_postprocess] 未检测到孤立水域，无需修正。")
    else:
        print(f"[water_postprocess] 检测到 {report['regions_found']} 个孤立水域区域，"
              f"共填回 {report['cells_filled']} 格:")
        for d in report["details"]:
            bbox = d["bbox"]
            print(f"  - 区域 #{d['label']}: {d['size']} 格, "
                  f"范围 x=[{bbox['x_min']}..{bbox['x_max']}] "
                  f"z=[{bbox['z_min']}..{bbox['z_max']}]")

        # 原地覆盖保存
        np.save(npy_path, water_mask)
        print(f"[water_postprocess] 已保存修正后的 {npy_path}")

    print(f"[water_postprocess] 修正后水域格数={water_mask.sum()}")


if __name__ == "__main__":
    main()
