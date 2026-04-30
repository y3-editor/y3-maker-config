"""
decoration_postprocess.py — 装饰物后处理脚本

功能: 对 AI 输出的装饰物坐标做精修，输出可直接传给 entity_create_block 的 JSON entity list。
  - 树木: 泊松圆盘采样替代矩形填充，水域过滤，随机 yaw/scale
  - 桥梁: 水域吸附 + yaw 自动推算（垂直于河流方向）
  - 山石: 泊松散布，混用山峰+岩石模型，水域过滤

输入:
  - decoration_input.json: AI 输出的装饰物数据
      {
        "trees": [{"x_min":..,"z_min":..,"x_max":..,"z_max":..}, ...],
        "bridges": [{"x":..,"z":..,"yaw"(optional):..}, ...],
        "mountains": [{"x_min":..,"z_min":..,"x_max":..,"z_max":..}, ...]
      }
  - water_mask_grid.npy: 修正后的水域 mask (bool 矩阵)
  - 地图参数: map_w, map_h, origin_x, origin_z, grid_size

输出:
  - decoration_entities.json: entity list，可直接传给 entity_create_block

用法:
    python decoration_postprocess.py <input_json> <water_mask_npy> <map_w> <map_h> <origin_x> <origin_z> <grid_size> <output_json>
"""

import sys
import os
import json
import math
import numpy as np
from collections import deque

# ---------------------------------------------------------------------------
# 模型 ID — 桥梁保持固定，树木/山石从 catalog 动态加载
# ---------------------------------------------------------------------------
BRIDGE_MODEL = 100463

# 以下变量在 main() 中由 _load_catalog() 填充，模块级保留声明供函数引用
TREE_MODELS = []
ROCK_MODELS = []


def _load_catalog(style, catalog_path=None):
    """
    从 decoration_catalog.json 加载指定风格的模型列表。

    Args:
        style: 风格 ID（如 "temperate", "boreal" 等）
        catalog_path: catalog 文件路径，默认为 ../references/decoration_catalog.json

    Returns:
        (tree_models, rock_models) — 两个 model_id 列表
    """
    if catalog_path is None:
        catalog_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "references", "decoration_catalog.json"
        )

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    default_style = catalog.get("default_style", "temperate")
    styles = catalog.get("styles", {})

    if style not in styles:
        print(f"  [WARNING] 未知风格 '{style}'，可选值: {list(styles.keys())}")
        print(f"  [WARNING] 回退到默认风格 '{default_style}'")
        style = default_style

    style_data = styles[style]
    tree_models = [t["model_id"] for t in style_data.get("trees", [])]
    rock_models = [r["model_id"] for r in style_data.get("rocks", [])]

    print(f"  [catalog] 风格: {style} ({style_data.get('label', '?')})")
    print(f"  [catalog] 树木模型: {tree_models}")
    print(f"  [catalog] 岩石模型: {rock_models}")

    return tree_models, rock_models

ENTITY_TYPE = 16777216  # RESOURCE_MODEL = 2^24


# ---------------------------------------------------------------------------
# 泊松圆盘采样 (Task 3.1)
# ---------------------------------------------------------------------------
def poisson_disk_sample(x_min, z_min, x_max, z_max, r, rng, k=30):
    """
    在矩形区域 [x_min, x_max) × [z_min, z_max) 内生成泊松圆盘采样点。

    Args:
        x_min, z_min, x_max, z_max: 区域边界（格子坐标）
        r: 最小间距
        rng: numpy RandomState
        k: 每个活跃点的尝试次数

    Returns:
        list of (x, z) 浮点坐标
    """
    width = x_max - x_min
    height = z_max - z_min
    if width <= 0 or height <= 0:
        return []

    cell_size = r / math.sqrt(2)
    grid_w = max(1, int(math.ceil(width / cell_size)))
    grid_h = max(1, int(math.ceil(height / cell_size)))

    # 背景网格：-1 表示空
    grid = -np.ones((grid_h, grid_w), dtype=int)
    points = []
    active = []

    def grid_coords(px, pz):
        return int((pz - z_min) / cell_size), int((px - x_min) / cell_size)

    # 种子点
    seed_x = rng.uniform(x_min, x_max)
    seed_z = rng.uniform(z_min, z_max)
    points.append((seed_x, seed_z))
    active.append(0)
    gz, gx = grid_coords(seed_x, seed_z)
    gz = min(gz, grid_h - 1)
    gx = min(gx, grid_w - 1)
    grid[gz, gx] = 0

    while active:
        idx = rng.randint(0, len(active))
        point_idx = active[idx]
        px, pz = points[point_idx]
        found = False

        for _ in range(k):
            angle = rng.uniform(0, 2 * math.pi)
            dist = rng.uniform(r, 2 * r)
            nx = px + dist * math.cos(angle)
            nz = pz + dist * math.sin(angle)

            if nx < x_min or nx >= x_max or nz < z_min or nz >= z_max:
                continue

            ngz, ngx = grid_coords(nx, nz)
            ngz = min(ngz, grid_h - 1)
            ngx = min(ngx, grid_w - 1)

            # 检查邻域
            ok = True
            for dz in range(-2, 3):
                for dx in range(-2, 3):
                    cz, cx = ngz + dz, ngx + dx
                    if 0 <= cz < grid_h and 0 <= cx < grid_w:
                        other = grid[cz, cx]
                        if other >= 0:
                            ox, oz = points[other]
                            if (nx - ox) ** 2 + (nz - oz) ** 2 < r * r:
                                ok = False
                                break
                if not ok:
                    break

            if ok:
                new_idx = len(points)
                points.append((nx, nz))
                active.append(new_idx)
                grid[ngz, ngx] = new_idx
                found = True
                break

        if not found:
            active.pop(idx)

    return points


# ---------------------------------------------------------------------------
# 坐标转换
# ---------------------------------------------------------------------------
def grid_to_world(gx, gz, origin_x, origin_z, grid_size):
    """格子坐标 → 世界坐标（格子中心）"""
    wx = origin_x + (gx + 0.5) * grid_size
    wz = origin_z + (gz + 0.5) * grid_size
    return wx, wz


def is_land(x, z, water_mask, map_w, map_h):
    """检查格子坐标是否为陆地"""
    ix, iz = int(x), int(z)
    if 0 <= ix < map_w and 0 <= iz < map_h:
        return not water_mask[iz, ix]
    return False


def is_water(x, z, water_mask, map_w, map_h):
    """检查格子坐标是否为水域"""
    ix, iz = int(x), int(z)
    if 0 <= ix < map_w and 0 <= iz < map_h:
        return bool(water_mask[iz, ix])
    return False


def make_entity(pos_world, model_id, yaw=0, pitch=0, roll=0, scale=1.0,
                stick_to_ground=True, relative_height=0):
    """构造 entity_create_block 所需的 entity dict"""
    s = scale if isinstance(scale, list) else [scale, scale, scale]
    entity = {
        "type": ENTITY_TYPE,
        "pos": [pos_world[0], 0, pos_world[1]],
        "model_id": model_id,
        "yaw": round(yaw, 1),
        "pitch": pitch,
        "roll": roll,
        "scale": [round(v, 2) for v in s],
        "stick_to_ground": stick_to_ground,
    }
    if relative_height:
        entity["relative_height"] = relative_height
    return entity


# ---------------------------------------------------------------------------
# 树木处理 (Task 3.2)
# ---------------------------------------------------------------------------
def process_trees(regions, water_mask, map_w, map_h, origin_x, origin_z,
                  grid_size, rng):
    """
    处理树木区域列表，泊松采样 + 水域过滤。

    Args:
        regions: list of {x_min, z_min, x_max, z_max}
        water_mask: 2D bool ndarray
        rng: numpy RandomState

    Returns:
        (entities, stats)
    """
    entities = []
    total_sampled = 0
    total_filtered = 0

    for region in regions:
        x_min = region["x_min"]
        z_min = region["z_min"]
        x_max = region["x_max"]
        z_max = region["z_max"]

        points = poisson_disk_sample(x_min, z_min, x_max, z_max, r=2.5,
                                     rng=rng)
        total_sampled += len(points)

        for px, pz in points:
            if not is_land(px, pz, water_mask, map_w, map_h):
                total_filtered += 1
                continue

            wx, wz = grid_to_world(px, pz, origin_x, origin_z, grid_size)
            yaw = rng.uniform(0, 360)
            scale = rng.uniform(0.9, 1.1)
            model_id = rng.choice(TREE_MODELS)
            entities.append(make_entity((wx, wz), model_id, yaw=yaw,
                                        scale=scale))

    stats = {
        "placed": len(entities),
        "sampled": total_sampled,
        "water_filtered": total_filtered,
    }
    return entities, stats


# ---------------------------------------------------------------------------
# 桥梁处理 (Task 3.3)
# ---------------------------------------------------------------------------
def _find_nearest_water(x, z, water_mask, map_w, map_h, radius=5):
    """BFS 搜索最近的水域格子"""
    ix, iz = int(round(x)), int(round(z))
    if 0 <= ix < map_w and 0 <= iz < map_h and water_mask[iz, ix]:
        return ix, iz

    visited = set()
    queue = deque([(ix, iz, 0)])
    visited.add((ix, iz))

    while queue:
        cx, cz, dist = queue.popleft()
        if dist > radius:
            break
        for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, nz = cx + dx, cz + dz
            if (nx, nz) in visited:
                continue
            if 0 <= nx < map_w and 0 <= nz < map_h:
                visited.add((nx, nz))
                if water_mask[nz, nx]:
                    return nx, nz
                queue.append((nx, nz, dist + 1))

    return None


def _infer_bridge_yaw(x, z, water_mask, map_w, map_h):
    """
    十字扫描 + 对角线扫描推算桥梁 yaw。
    返回 yaw（度），桥应垂直于河流走向。
    """
    ix, iz = int(x), int(z)

    def scan_extent(dx, dz, max_dist=15):
        count = 0
        cx, cz = ix + dx, iz + dz
        while 0 <= cx < map_w and 0 <= cz < map_h and count < max_dist:
            if water_mask[cz, cx]:
                count += 1
                cx += dx
                cz += dz
            else:
                break
        return count

    # 四主方向
    h_extent = scan_extent(-1, 0) + scan_extent(1, 0)   # 水平（左+右）
    v_extent = scan_extent(0, -1) + scan_extent(0, 1)   # 垂直（上+下）

    # 对角线
    d45_extent = scan_extent(1, -1) + scan_extent(-1, 1)   # ↗↙
    d135_extent = scan_extent(-1, -1) + scan_extent(1, 1)  # ↖↘

    extents = {
        0: v_extent,      # 河流南北走向 → 桥东西 yaw=90
        45: d135_extent,   # 河流↖↘走向 → 桥↗↙ yaw=135
        90: h_extent,      # 河流东西走向 → 桥南北 yaw=0
        135: d45_extent,   # 河流↗↙走向 → 桥↖↘ yaw=45
    }

    # 河流走向 = 最宽方向, 桥 = 垂直于河流
    river_dir = max(extents, key=extents.get)
    bridge_yaw = (river_dir + 90) % 360

    # 量化到 45° 增量
    bridge_yaw = round(bridge_yaw / 45) * 45
    return bridge_yaw % 360


def process_bridges(bridges, water_mask, map_w, map_h, origin_x, origin_z,
                    grid_size):
    """
    处理桥梁列表，水域吸附 + yaw 推算。

    Args:
        bridges: list of {x, z, yaw(optional)}

    Returns:
        (entities, stats)
    """
    entities = []
    snapped = 0
    discarded = 0

    for bridge in bridges:
        bx = bridge["x"]
        bz = bridge["z"]

        if not is_water(bx, bz, water_mask, map_w, map_h):
            # 尝试吸附到最近水域
            result = _find_nearest_water(bx, bz, water_mask, map_w, map_h)
            if result is None:
                print(f"  [bridge] 丢弃: ({bx}, {bz}) 附近无水域")
                discarded += 1
                continue
            bx, bz = result
            snapped += 1

        yaw = _infer_bridge_yaw(bx, bz, water_mask, map_w, map_h)

        # 如果 AI 给了 yaw 且与推算值接近（±45°），用 AI 的
        if "yaw" in bridge:
            ai_yaw = bridge["yaw"]
            diff = abs((ai_yaw - yaw + 180) % 360 - 180)
            if diff <= 45:
                yaw = round(ai_yaw / 45) * 45

        wx, wz = grid_to_world(bx, bz, origin_x, origin_z, grid_size)
        entities.append(make_entity((wx, wz), BRIDGE_MODEL, yaw=yaw,
                                    stick_to_ground=False, relative_height=400))

    stats = {
        "placed": len(entities),
        "snapped": snapped,
        "discarded": discarded,
    }
    return entities, stats


# ---------------------------------------------------------------------------
# 山石处理 (Task 3.4)
# ---------------------------------------------------------------------------
def process_rocks(regions, water_mask, map_w, map_h, origin_x, origin_z,
                  grid_size, rng):
    """
    处理山脉区域列表，泊松散布山峰+岩石。

    Args:
        regions: list of {x_min, z_min, x_max, z_max}

    Returns:
        (entities, stats)
    """
    all_models = ROCK_MODELS
    entities = []
    total_sampled = 0
    total_filtered = 0

    for region in regions:
        x_min = region["x_min"]
        z_min = region["z_min"]
        x_max = region["x_max"]
        z_max = region["z_max"]

        points = poisson_disk_sample(x_min, z_min, x_max, z_max, r=2.0,
                                     rng=rng)
        total_sampled += len(points)

        for px, pz in points:
            if not is_land(px, pz, water_mask, map_w, map_h):
                total_filtered += 1
                continue

            wx, wz = grid_to_world(px, pz, origin_x, origin_z, grid_size)
            yaw = rng.uniform(0, 360)
            scale = rng.uniform(0.8, 1.2)
            model_id = rng.choice(all_models)
            entities.append(make_entity((wx, wz), model_id, yaw=yaw,
                                        scale=scale))

    stats = {
        "placed": len(entities),
        "sampled": total_sampled,
        "water_filtered": total_filtered,
    }
    return entities, stats


# ---------------------------------------------------------------------------
# 主入口 (Task 3.5)
# ---------------------------------------------------------------------------
def _load_map_info(output_dir):
    """从 map_info.json 读取地图参数"""
    map_info_path = os.path.join(output_dir, "map_info.json")
    if not os.path.exists(map_info_path):
        print(f"[ERROR] map_info.json 不存在: {map_info_path}")
        print("  请确认 Stage 0 已执行并保存了 map_info.json")
        sys.exit(1)
    with open(map_info_path, "r", encoding="utf-8") as f:
        info = json.load(f)
    map_w = int(info["width"])
    map_h = int(info["height"])
    grid_size = float(info.get("grid_size", 2.0))
    origin_x = -(map_w * grid_size) / 2.0
    origin_z = -(map_h * grid_size) / 2.0
    return map_w, map_h, origin_x, origin_z, grid_size


def main():
    if len(sys.argv) < 4:
        print("Usage: python decoration_postprocess.py "
              "<input_json> <water_mask_npy> <output_json>")
        print("  地图参数自动从同目录下的 map_info.json 读取")
        sys.exit(1)

    input_json = sys.argv[1]
    water_mask_npy = sys.argv[2]
    output_json = sys.argv[3]

    # 自动从 map_info.json 读取地图参数
    output_dir = os.path.dirname(os.path.abspath(water_mask_npy))
    map_w, map_h, origin_x, origin_z, grid_size = _load_map_info(output_dir)

    # 加载输入
    with open(input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    water_mask = np.load(water_mask_npy)
    rng = np.random.RandomState(42)  # 固定种子，保证可复现

    # 从 catalog 加载风格化模型
    global TREE_MODELS, ROCK_MODELS
    style = data.get("style", None)
    if style is None:
        print("[decoration_postprocess] 未指定 style，使用默认风格")
        style = "temperate"  # _load_catalog 内部也会 fallback，此处提前明示
    TREE_MODELS, ROCK_MODELS = _load_catalog(style)

    print(f"[decoration_postprocess] 地图: {map_w}x{map_h}, "
          f"origin=({origin_x},{origin_z}), grid={grid_size}")
    print(f"[decoration_postprocess] 水域格数: {water_mask.sum()}")

    all_entities = []

    # 树木
    tree_regions = data.get("trees", [])
    if tree_regions:
        tree_entities, tree_stats = process_trees(
            tree_regions, water_mask, map_w, map_h,
            origin_x, origin_z, grid_size, rng)
        all_entities.extend(tree_entities)
        print(f"[trees] 采样 {tree_stats['sampled']}, "
              f"放置 {tree_stats['placed']}, "
              f"水域过滤 {tree_stats['water_filtered']}")

    # 桥梁
    bridge_list = data.get("bridges", [])
    if bridge_list:
        bridge_entities, bridge_stats = process_bridges(
            bridge_list, water_mask, map_w, map_h,
            origin_x, origin_z, grid_size)
        all_entities.extend(bridge_entities)
        print(f"[bridges] 放置 {bridge_stats['placed']}, "
              f"吸附 {bridge_stats['snapped']}, "
              f"丢弃 {bridge_stats['discarded']}")

    # 山石
    mountain_regions = data.get("mountains", [])
    if mountain_regions:
        rock_entities, rock_stats = process_rocks(
            mountain_regions, water_mask, map_w, map_h,
            origin_x, origin_z, grid_size, rng)
        all_entities.extend(rock_entities)
        print(f"[rocks] 采样 {rock_stats['sampled']}, "
              f"放置 {rock_stats['placed']}, "
              f"水域过滤 {rock_stats['water_filtered']}")

    # 输出 — 将 numpy 类型转为原生 Python 类型
    def convert_numpy(obj):
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    def sanitize(entities):
        result = []
        for e in entities:
            clean = {}
            for k, v in e.items():
                if isinstance(v, list):
                    clean[k] = [convert_numpy(i) for i in v]
                else:
                    clean[k] = convert_numpy(v)
            result.append(clean)
        return result

    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(sanitize(all_entities), f, indent=2, ensure_ascii=False)

    print(f"[decoration_postprocess] 总计 {len(all_entities)} 个实体 → {output_json}")


if __name__ == "__main__":
    main()
