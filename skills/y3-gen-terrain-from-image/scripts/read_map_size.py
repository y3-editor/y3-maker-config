"""
read_map_size.py
读取 Y3 地图的 terrain.json 二进制文件，解析点阵尺寸。
用法：python read_map_size.py <map_path>
"""
import struct
import sys
import os


def read_map_size(map_path: str) -> tuple[int, int]:
    terrain_path = os.path.join(map_path, "terrain.json")
    if not os.path.exists(terrain_path):
        raise FileNotFoundError(f"未找到 terrain.json：{terrain_path}")

    with open(terrain_path, "rb") as f:
        data = f.read(8)

    if len(data) < 8:
        raise ValueError("terrain.json 文件过短，无法解析尺寸")

    size_data = struct.unpack("ii", data[:8])
    width = size_data[0] * 2
    height = size_data[1] * 2
    return width, height


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法：python read_map_size.py <map_path>")
        sys.exit(1)

    map_path = sys.argv[1]
    try:
        w, h = read_map_size(map_path)
        print(f"点阵尺寸：width={w}, height={h}")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)
