"""
gen_water_map.py — 从 terrain_grid.csv 生成精简水域字符地图

输入: terrain_grid.csv (每个格子为 "terrain_type,h,extra")
输出: water_map.txt (W=水域 .=陆地 的字符矩阵)

用法:
    python gen_water_map.py <terrain_grid.csv> <output_water_map.txt>
"""

import sys
import csv


def main():
    if len(sys.argv) < 3:
        print("Usage: python gen_water_map.py <terrain_grid.csv> <output.txt>")
        sys.exit(1)

    input_csv = sys.argv[1]
    output_txt = sys.argv[2]

    lines = []
    with open(input_csv, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            chars = []
            for cell in row:
                # cell 格式: "terrain_type,h,extra" 如 "deep_water,0,0" 或 "ground,0,0"
                terrain_type = cell.split(",")[0].strip()
                if "water" in terrain_type.lower():
                    chars.append("W")
                else:
                    chars.append(".")
            lines.append("".join(chars))

    with open(output_txt, "w", encoding="utf-8") as f:
        # 写入坐标头
        if lines:
            width = len(lines[0])
            # x 轴标尺 (每10格标一个数字)
            header = "   "
            for x in range(width):
                if x % 10 == 0:
                    header += str(x).ljust(10)
            f.write(header.rstrip() + "\n")

        for z, line in enumerate(lines):
            f.write(f"{z:2d} {line}\n")

    print(f"[gen_water_map] {len(lines)}x{len(lines[0]) if lines else 0} → {output_txt}")
    water_count = sum(line.count("W") for line in lines)
    land_count = sum(line.count(".") for line in lines)
    print(f"  W(水域)={water_count}, .(陆地)={land_count}")


if __name__ == "__main__":
    main()
