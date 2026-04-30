"""
decoration_postprocess.py — 装饰物后处理脚本 (v3 — 纹理组驱动 + 精确定位)

功能: 对 AI 输出的装饰物标注做后处理，输出可直接传给 entity_create_block 的 JSON entity list。
  - tree_cluster: 树丛精确定位
    * fine_clusters 模式（优先）: 从 labels_fine.npy 提取微簇 mask，在 mask 内泊松采样
    * position + radius 模式（兜底）: 在九宫格方位的圆形区域内泊松采样
  - mountain_chain: 连绵山脉
    * from/to 方位描述，沿连线均匀放置，加法线偏移
  - 纹理组驱动: 每个采样点查脚下纹理 → 匹配纹理组 → 从该组模型池选模型
  - 桥梁: 水域吸附 + yaw 自动推算 — 逻辑不变
  - 向后兼容: 旧 tree/mountain 类型仍可处理

输入:
  - decoration_input.json: AI 输出的装饰物数据 (v3 格式)
      {
        "continents": { "<id>": { "decorations": [...] } },
        "bridges": [{"x":..,"z":..,"yaw"(optional):..}, ...]
      }
  - water_mask_grid.npy: 修正后的水域 mask (bool 矩阵, 网格分辨率)
  - --labels-fine: labels_fine.npy (可选, 原图分辨率)
  - --continent-map: continent_map_full.npy (可选, 启用 mask 采样)
  - --texture-grid: texture_grid.csv (可选, 启用纹理组驱动模型选择)

输出:
  - decoration_entities.json: entity list，可直接传给 entity_create_block

用法:
    python decoration_postprocess.py <input_json> <water_mask_npy> <output_json> \
        [--labels-fine <path>] [--continent-map <path>] [--texture-grid <path>]
"""

import sys
import os
import json
import math
import csv
import argparse
import numpy as np
from collections import deque, defaultdict

# ---------------------------------------------------------------------------
# 模型 ID — 桥梁保持固定
# ---------------------------------------------------------------------------
BRIDGE_MODEL = 100463

# 以下变量在 main() 中由 _load_catalog() 或纹理组 catalog 填充
TREE_MODELS = []
ROCK_MODELS = []
ROCK_PICKBOUNDS = {}  # {model_id: (radius, height)}

# ---------------------------------------------------------------------------
# 纹理组 catalog (v3)
# ---------------------------------------------------------------------------
TEXTURE_GROUP_CATALOG = {}  # {"grassland": {...}, ...}
TEXTURE_ID_TO_GROUP = {}    # {194: "grassland", 11: "desert", ...}
TEXTURE_GRID = None         # 2D numpy int array, or None
TEX_GROUP_STATS = defaultdict(lambda: {"tree": 0, "mountain": 0})


def _load_texture_group_catalog(catalog_path=None):
    """
    从 texture_group_catalog.json 加载纹理组映射。

    Returns:
        (catalog_dict, tex_id_to_group, fallback_group)
    """
    if catalog_path is None:
        catalog_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "references", "texture_group_catalog.json"
        )

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    fallback = catalog.get("fallback_group", "grassland")
    groups = catalog.get("texture_groups", {})

    # 构建反查表
    tex_to_group = {}
    for group_name, group_data in groups.items():
        for tex_id in group_data.get("texture_ids", []):
            tex_to_group[tex_id] = group_name

    # 提取每组的 rock_pickbounds
    for group_name, group_data in groups.items():
        pb = {}
        for r in group_data.get("rocks", []):
            rpb = r.get("pickbound")
            if rpb and len(rpb) == 2:
                pb[r["model_id"]] = tuple(rpb)
        group_data["_rock_pickbounds"] = pb

    print(f"  [texture_group_catalog] 加载 {len(groups)} 个纹理组, "
          f"映射 {len(tex_to_group)} 种纹理 ID, fallback={fallback}")
    for gn, gd in groups.items():
        n_trees = len([t["model_id"] for t in gd.get("trees", [])])
        n_rocks = len([r["model_id"] for r in gd.get("rocks", [])])
        print(f"    {gn} ({gd.get('label','?')}): {n_trees} 树, {n_rocks} 石")

    return groups, tex_to_group, fallback


def _load_texture_grid(csv_path):
    """
    从 texture_grid.csv 读取纹理矩阵。

    Returns:
        2D numpy int array (map_h, map_w), 每个格子的纹理 ID
    """
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append([int(v) for v in row])
    grid = np.array(rows, dtype=int)
    print(f"  [texture_grid] 加载 {grid.shape[0]}x{grid.shape[1]} 纹理矩阵")
    return grid


def _select_model_by_texture(px, pz, deco_type, rng,
                              texture_grid, tex_to_group, catalog,
                              fallback_group):
    """
    根据采样点脚下纹理选择模型。

    Args:
        px, pz: 格子坐标 (float)
        deco_type: "tree" 或 "mountain"
        rng: numpy RandomState
        texture_grid: 2D int array or None
        tex_to_group: {tex_id: group_name}
        catalog: {group_name: group_data}
        fallback_group: str

    Returns:
        (model_id, group_name, rock_pickbounds_for_group) or (None, group_name, {}) if no models
    """
    group_name = fallback_group

    if texture_grid is not None:
        gx_i = int(px)
        gz_i = int(pz)
        h, w = texture_grid.shape
        if 0 <= gx_i < w and 0 <= gz_i < h:
            tex_id = int(texture_grid[gz_i, gx_i])
            group_name = tex_to_group.get(tex_id, fallback_group)
            if tex_id not in tex_to_group:
                pass  # WARNING 在统计时打印，不在每个点打印

    group_data = catalog.get(group_name)
    if group_data is None:
        group_data = catalog.get(fallback_group, {})
        group_name = fallback_group

    if deco_type == "tree":
        models = [t["model_id"] for t in group_data.get("trees", [])]
    else:
        models = [r["model_id"] for r in group_data.get("rocks", [])]

    if not models:
        return None, group_name, group_data.get("_rock_pickbounds", {})

    model_id = rng.choice(models)
    return model_id, group_name, group_data.get("_rock_pickbounds", {})


def _load_catalog_legacy(style, catalog_path=None):
    """
    [v1/v2 兼容] 从 decoration_catalog.json 加载指定风格的模型列表。
    仅在旧格式 tree/mountain 类型时使用。
    """
    if catalog_path is None:
        catalog_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "references", "decoration_catalog.json"
        )

    if not os.path.exists(catalog_path):
        print(f"  [WARNING] 旧 catalog 不存在: {catalog_path}，使用纹理组 fallback")
        return [], [], {}

    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    default_style = catalog.get("default_style", "temperate")
    styles = catalog.get("styles", {})

    if style not in styles:
        style = default_style

    style_data = styles.get(style, {})
    tree_models = [t["model_id"] for t in style_data.get("trees", [])]
    rock_models = [r["model_id"] for r in style_data.get("rocks", [])]
    rock_pickbounds = {}
    for r in style_data.get("rocks", []):
        pb = r.get("pickbound")
        if pb and len(pb) == 2:
            rock_pickbounds[r["model_id"]] = tuple(pb)

    return tree_models, rock_models, rock_pickbounds

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
# 密度映射 (v2)
# ---------------------------------------------------------------------------
DENSITY_MAP_TREE = {"sparse": 3.5, "normal": 2.0, "dense": 1.0}
DENSITY_MAP_ROCK = {"sparse": 3.5, "normal": 2.0, "dense": 1.2}

VALID_POSITIONS = {
    "northwest", "north", "northeast",
    "west", "center", "east",
    "southwest", "south", "southeast",
    "scattered",
}


# ---------------------------------------------------------------------------
# mask 采样模式 (v2): 从 labels_fine 提取微簇 mask → 下采样到网格 → 泊松采样
# ---------------------------------------------------------------------------
def build_mask_from_fine_clusters(fine_clusters, labels_fine, continent_map,
                                  continent_id, water_mask_grid, map_w, map_h):
    """
    从 labels_fine (原图分辨率) 中提取指定微簇的 mask，
    下采样到网格分辨率，返回 bool 网格 (map_h, map_w)。
    """
    img_h, img_w = labels_fine.shape
    px_per_grid_x = img_w / map_w
    px_per_grid_z = img_h / map_h

    # 在原图分辨率上构建 mask
    full_mask = np.zeros((img_h, img_w), dtype=bool)
    for fid in fine_clusters:
        full_mask |= (labels_fine == fid)

    # 限定在该大陆内
    if continent_map is not None:
        full_mask &= (continent_map == continent_id)

    # 下采样到网格分辨率: 对每个网格格子，如果原图区域内 >50% 像素命中则为 True
    grid_mask = np.zeros((map_h, map_w), dtype=bool)
    for gz in range(map_h):
        for gx in range(map_w):
            y0 = int(gz * px_per_grid_z)
            y1 = int(min((gz + 1) * px_per_grid_z, img_h))
            x0 = int(gx * px_per_grid_x)
            x1 = int(min((gx + 1) * px_per_grid_x, img_w))
            if y1 > y0 and x1 > x0:
                patch = full_mask[y0:y1, x0:x1]
                if patch.mean() > 0.3:  # 30% 覆盖率即标为 True
                    grid_mask[gz, gx] = True

    # 排除水域
    grid_mask &= ~water_mask_grid

    return grid_mask


# ---------------------------------------------------------------------------
# 方位区域采样模式 (v2): 大陆 bbox 九宫格切分
# ---------------------------------------------------------------------------
def build_mask_from_position(position, continent_map, continent_id,
                              water_mask_grid, map_w, map_h):
    """
    根据方位关键词，在大陆 bbox 的九宫格对应区域内构建采样 mask。
    返回 bool 网格 (map_h, map_w)。
    """
    if position not in VALID_POSITIONS:
        print(f"  [WARNING] 无效方位 '{position}'，降级为 scattered")
        position = "scattered"

    # 构建大陆 mask (在网格分辨率上)
    if continent_map is not None:
        img_h, img_w = continent_map.shape
        px_per_grid_x = img_w / map_w
        px_per_grid_z = img_h / map_h

        continent_grid = np.zeros((map_h, map_w), dtype=bool)
        for gz in range(map_h):
            for gx in range(map_w):
                y0 = int(gz * px_per_grid_z)
                y1 = int(min((gz + 1) * px_per_grid_z, img_h))
                x0 = int(gx * px_per_grid_x)
                x1 = int(min((gx + 1) * px_per_grid_x, img_w))
                if y1 > y0 and x1 > x0:
                    patch = (continent_map[y0:y1, x0:x1] == continent_id)
                    if patch.mean() > 0.3:
                        continent_grid[gz, gx] = True
    else:
        # 无 continent_map 时，用全图
        continent_grid = np.ones((map_h, map_w), dtype=bool)

    if position == "scattered":
        return continent_grid & ~water_mask_grid

    # 计算大陆 bbox (网格坐标)
    ys, xs = np.where(continent_grid)
    if len(xs) == 0:
        return np.zeros((map_h, map_w), dtype=bool)

    bbox_x_min, bbox_x_max = int(xs.min()), int(xs.max())
    bbox_z_min, bbox_z_max = int(ys.min()), int(ys.max())

    # 九宫格切分
    bw = bbox_x_max - bbox_x_min + 1
    bh = bbox_z_max - bbox_z_min + 1
    x_third = bw / 3.0
    z_third = bh / 3.0

    # 方位 → (col, row) 索引
    pos_to_sector = {
        "northwest": (0, 0), "north": (1, 0), "northeast": (2, 0),
        "west": (0, 1),      "center": (1, 1), "east": (2, 1),
        "southwest": (0, 2), "south": (1, 2),  "southeast": (2, 2),
    }

    col, row = pos_to_sector.get(position, (1, 1))
    sec_x_min = bbox_x_min + int(col * x_third)
    sec_x_max = bbox_x_min + int((col + 1) * x_third)
    sec_z_min = bbox_z_min + int(row * z_third)
    sec_z_max = bbox_z_min + int((row + 1) * z_third)

    # 构建方位 mask
    pos_mask = np.zeros((map_h, map_w), dtype=bool)
    sec_z_max_clamp = min(sec_z_max + 1, map_h)
    sec_x_max_clamp = min(sec_x_max + 1, map_w)
    pos_mask[sec_z_min:sec_z_max_clamp, sec_x_min:sec_x_max_clamp] = True

    # 与大陆 mask + 非水域 交集
    return continent_grid & pos_mask & ~water_mask_grid


# ---------------------------------------------------------------------------
# 在 mask 内泊松采样 (v2)
# ---------------------------------------------------------------------------
def poisson_sample_in_mask(grid_mask, r, rng, map_w, map_h):
    """
    在 bool 网格 mask 内做泊松采样。

    对于极小区域（mask 格子数 < 泊松采样最低有效面积），自动降级为
    "每个格子中心直接放置"模式，避免采样空返回。

    Args:
        grid_mask: (map_h, map_w) bool array — True 表示可放置
        r: 最小间距
        rng: numpy RandomState

    Returns:
        list of (gx, gz) 格子坐标 (浮点)
    """
    # 获取所有可用格子
    valid_zs, valid_xs = np.where(grid_mask)
    if len(valid_xs) == 0:
        return []

    n_cells = len(valid_xs)

    # 极小区域降级：如果格子数 < r^2 * 4（泊松采样几乎无法在这么小区域采到点），
    # 直接在每个格子中心放置（带小随机偏移）
    if n_cells < max(4, int(r * r * 2)):
        points = []
        for vx, vz in zip(valid_xs, valid_zs):
            px = float(vx) + rng.uniform(0.2, 0.8)
            pz = float(vz) + rng.uniform(0.2, 0.8)
            points.append((px, pz))
        return points

    # 用可用格子的 bbox 做泊松采样，然后过滤到 mask 内
    x_min = float(valid_xs.min())
    x_max = float(valid_xs.max() + 1)
    z_min = float(valid_zs.min())
    z_max = float(valid_zs.max() + 1)

    all_points = poisson_disk_sample(x_min, z_min, x_max, z_max, r, rng)

    # 过滤: 只保留在 mask 内的点
    filtered = []
    for px, pz in all_points:
        gx, gz = int(px), int(pz)
        if 0 <= gx < map_w and 0 <= gz < map_h and grid_mask[gz, gx]:
            filtered.append((px, pz))

    # 二次兜底：如果泊松采样过滤后仍然为空，但有可用格子，至少放 1 个
    if not filtered and n_cells > 0:
        idx = rng.randint(0, n_cells)
        px = float(valid_xs[idx]) + rng.uniform(0.2, 0.8)
        pz = float(valid_zs[idx]) + rng.uniform(0.2, 0.8)
        filtered.append((px, pz))

    return filtered


# ---------------------------------------------------------------------------
# v2 通用装饰物处理（树/山石）
# ---------------------------------------------------------------------------
def _compute_mountain_scale(pickbound, grid_size, target_grids=4):
    """
    根据模型 pickbound 计算山峰 scale，使其视觉覆盖约 target_grids 个格子宽。

    Args:
        pickbound: (radius, height) — 模型原始包围盒
        grid_size: 网格大小（世界单位）
        target_grids: 目标覆盖宽度（格子数）

    Returns:
        scale: float
    """
    if not pickbound:
        return 3.0  # 无包围盒数据时默认放大 3 倍

    radius = pickbound[0]
    target_world_radius = target_grids * grid_size / 2.0  # 目标半径（世界单位）

    if radius <= 0:
        return 3.0

    scale = target_world_radius / radius
    # 限制 scale 范围: 最小 1.5，最大 8.0
    scale = max(1.5, min(8.0, scale))
    return scale


def process_decoration_v2(deco, continent_id, labels_fine, continent_map,
                           water_mask_grid, map_w, map_h,
                           origin_x, origin_z, grid_size, rng,
                           model_list, scale_range=(0.9, 1.1),
                           rock_pickbounds=None):
    """
    处理单个装饰物条目 (v2 格式)。

    山峰 (mountain) 使用 count 模式：AI 指定数量，脚本在区域内均匀放置，
    并根据 pickbound 自动计算 scale 使山峰看起来足够大。

    树木 (tree) 使用泊松采样模式：按密度散布。

    Args:
        deco: {"type","density","count","fine_clusters","position"}
        continent_id: int
        labels_fine: ndarray or None
        continent_map: ndarray or None (原图分辨率)
        water_mask_grid: (map_h, map_w) bool
        model_list: list of model_id
        scale_range: (min, max) — 仅对 tree 生效
        rock_pickbounds: dict {model_id: (radius, height)} — 岩石模型包围盒

    Returns:
        (entities, stats)
    """
    deco_type = deco.get("type", "tree")
    density = deco.get("density", "normal")
    count = deco.get("count")  # 山峰数量（仅 mountain 使用）
    fine_clusters = deco.get("fine_clusters")
    position = deco.get("position")

    # 构建采样 mask
    grid_mask = None
    mode = "none"

    if fine_clusters and labels_fine is not None and continent_map is not None:
        grid_mask = build_mask_from_fine_clusters(
            fine_clusters, labels_fine, continent_map, continent_id,
            water_mask_grid, map_w, map_h
        )
        mode = "mask"
    elif position:
        grid_mask = build_mask_from_position(
            position, continent_map, continent_id,
            water_mask_grid, map_w, map_h
        )
        mode = "position"
    elif fine_clusters and labels_fine is None:
        print(f"  [WARNING] C{continent_id} {deco_type}: "
              f"有 fine_clusters 但缺少 labels_fine，降级为 scattered")
        grid_mask = build_mask_from_position(
            "scattered", continent_map, continent_id,
            water_mask_grid, map_w, map_h
        )
        mode = "scattered(fallback)"

    if grid_mask is None or grid_mask.sum() == 0:
        return [], {"placed": 0, "sampled": 0, "water_filtered": 0, "mode": mode}

    # =============================================
    # 山峰 (mountain): count 模式
    # =============================================
    if deco_type == "mountain":
        if count is None or count <= 0:
            # AI 可能用了旧格式 density 而非 count，做兼容推算
            density_to_count = {"sparse": 2, "normal": 3, "dense": 5}
            count = density_to_count.get(density, 3)

        # 在 mask 区域内随机选 count 个不重叠的位置
        valid_zs, valid_xs = np.where(grid_mask)
        n_cells = len(valid_xs)

        if n_cells == 0:
            return [], {"placed": 0, "sampled": 0, "mask_cells": 0, "mode": mode}

        # 均匀分散选点: 把可用格子随机打乱，每隔 n_cells/count 个取一个
        indices = np.arange(n_cells)
        rng.shuffle(indices)

        # 尝试用最大间距选点
        actual_count = min(count, n_cells)
        selected_indices = indices[:actual_count]

        entities = []
        for idx in selected_indices:
            gx = float(valid_xs[idx]) + rng.uniform(0.2, 0.8)
            gz = float(valid_zs[idx]) + rng.uniform(0.2, 0.8)
            wx, wz = grid_to_world(gx, gz, origin_x, origin_z, grid_size)

            model_id = rng.choice(model_list)
            yaw = rng.uniform(0, 360)

            # 根据 pickbound 自动计算 scale
            pb = rock_pickbounds.get(model_id) if rock_pickbounds else None
            base_scale = _compute_mountain_scale(pb, grid_size, target_grids=4)
            # 加点随机变化 (±15%)
            scale = base_scale * rng.uniform(0.85, 1.15)

            entities.append(make_entity((wx, wz), model_id, yaw=yaw, scale=scale))

        stats = {
            "placed": len(entities),
            "sampled": actual_count,
            "mask_cells": int(grid_mask.sum()),
            "mode": f"count({count})",
        }
        return entities, stats

    # =============================================
    # 树木 (tree): 泊松采样模式
    # =============================================
    density_map = DENSITY_MAP_TREE
    r = density_map.get(density, density_map["normal"])

    points = poisson_sample_in_mask(grid_mask, r, rng, map_w, map_h)

    # 安全上限
    MAX_ENTITIES_PER_DECO = 50
    if len(points) > MAX_ENTITIES_PER_DECO:
        rng.shuffle(points)
        points = points[:MAX_ENTITIES_PER_DECO]
        print(f"  [WARNING] C{continent_id} tree: 采样点过多, 截断为 {MAX_ENTITIES_PER_DECO}")

    entities = []

    for px, pz in points:
        wx, wz = grid_to_world(px, pz, origin_x, origin_z, grid_size)
        yaw = rng.uniform(0, 360)
        scale = rng.uniform(scale_range[0], scale_range[1])
        model_id = rng.choice(model_list)
        entities.append(make_entity((wx, wz), model_id, yaw=yaw, scale=scale))

    stats = {
        "placed": len(entities),
        "sampled": len(points),
        "mask_cells": int(grid_mask.sum()),
        "mode": mode,
    }
    return entities, stats


# ---------------------------------------------------------------------------
# v3: tree_cluster 处理
# ---------------------------------------------------------------------------
def build_mask_from_circle(center_x, center_z, radius, continent_map,
                            continent_id, water_mask_grid, map_w, map_h):
    """
    在九宫格方位的中心点周围构建圆形采样 mask。

    Args:
        center_x, center_z: 圆心格子坐标
        radius: 半径（格子数），clamp 到 [1, 10]
    """
    radius = max(1, min(10, radius))

    grid_mask = np.zeros((map_h, map_w), dtype=bool)
    for gz in range(max(0, int(center_z - radius)),
                    min(map_h, int(center_z + radius) + 1)):
        for gx in range(max(0, int(center_x - radius)),
                        min(map_w, int(center_x + radius) + 1)):
            dist = math.sqrt((gx - center_x) ** 2 + (gz - center_z) ** 2)
            if dist <= radius:
                grid_mask[gz, gx] = True

    # 限定在大陆内
    if continent_map is not None:
        img_h, img_w = continent_map.shape
        px_per_grid_x = img_w / map_w
        px_per_grid_z = img_h / map_h
        continent_grid = np.zeros((map_h, map_w), dtype=bool)
        for gz in range(map_h):
            for gx in range(map_w):
                y0 = int(gz * px_per_grid_z)
                y1 = int(min((gz + 1) * px_per_grid_z, img_h))
                x0 = int(gx * px_per_grid_x)
                x1 = int(min((gx + 1) * px_per_grid_x, img_w))
                if y1 > y0 and x1 > x0:
                    patch = (continent_map[y0:y1, x0:x1] == continent_id)
                    if patch.mean() > 0.3:
                        continent_grid[gz, gx] = True
        grid_mask &= continent_grid

    grid_mask &= ~water_mask_grid
    return grid_mask


def _get_position_center(position, continent_map, continent_id, map_w, map_h):
    """
    获取九宫格方位在大陆 bbox 中的中心坐标。

    Returns:
        (center_x, center_z) 格子坐标
    """
    pos_to_sector = {
        "northwest": (0, 0), "north": (1, 0), "northeast": (2, 0),
        "west": (0, 1),      "center": (1, 1), "east": (2, 1),
        "southwest": (0, 2), "south": (1, 2),  "southeast": (2, 2),
    }

    if continent_map is not None:
        img_h, img_w = continent_map.shape
        px_per_grid_x = img_w / map_w
        px_per_grid_z = img_h / map_h
        continent_grid = np.zeros((map_h, map_w), dtype=bool)
        for gz in range(map_h):
            for gx in range(map_w):
                y0 = int(gz * px_per_grid_z)
                y1 = int(min((gz + 1) * px_per_grid_z, img_h))
                x0 = int(gx * px_per_grid_x)
                x1 = int(min((gx + 1) * px_per_grid_x, img_w))
                if y1 > y0 and x1 > x0:
                    patch = (continent_map[y0:y1, x0:x1] == continent_id)
                    if patch.mean() > 0.3:
                        continent_grid[gz, gx] = True
        ys, xs = np.where(continent_grid)
    else:
        ys = np.arange(map_h)
        xs = np.arange(map_w)

    if len(xs) == 0:
        return map_w / 2.0, map_h / 2.0

    bbox_x_min, bbox_x_max = float(xs.min()), float(xs.max())
    bbox_z_min, bbox_z_max = float(ys.min()), float(ys.max())
    bw = bbox_x_max - bbox_x_min + 1
    bh = bbox_z_max - bbox_z_min + 1

    if position == "scattered":
        return bbox_x_min + bw / 2.0, bbox_z_min + bh / 2.0

    col, row = pos_to_sector.get(position, (1, 1))
    x_third = bw / 3.0
    z_third = bh / 3.0

    center_x = bbox_x_min + (col + 0.5) * x_third
    center_z = bbox_z_min + (row + 0.5) * z_third

    return center_x, center_z


def process_tree_cluster(deco, continent_id, labels_fine, continent_map,
                          water_mask_grid, map_w, map_h,
                          origin_x, origin_z, grid_size, rng,
                          texture_grid, tex_to_group, tex_catalog,
                          fallback_group):
    """
    处理 tree_cluster 类型装饰物 (v3)。

    支持两种定位模式:
      1. fine_clusters（优先）: 从 labels_fine 提取 mask
      2. position + radius（兜底）: 圆形区域泊松采样
    """
    density = deco.get("density", "normal")
    fine_clusters = deco.get("fine_clusters")
    position = deco.get("position")
    radius = deco.get("radius")

    # 构建采样 mask
    grid_mask = None
    mode = "none"

    if fine_clusters and labels_fine is not None and continent_map is not None:
        grid_mask = build_mask_from_fine_clusters(
            fine_clusters, labels_fine, continent_map, continent_id,
            water_mask_grid, map_w, map_h
        )
        mode = "mask"
    elif position:
        if radius is not None and radius > 0:
            # 圆形区域模式
            cx, cz = _get_position_center(
                position, continent_map, continent_id, map_w, map_h)
            grid_mask = build_mask_from_circle(
                cx, cz, radius, continent_map, continent_id,
                water_mask_grid, map_w, map_h)
            mode = f"circle(r={radius})"
        else:
            # 旧的九宫格方位模式 fallback
            grid_mask = build_mask_from_position(
                position, continent_map, continent_id,
                water_mask_grid, map_w, map_h)
            mode = "position"
    elif fine_clusters and labels_fine is None:
        print(f"  [WARNING] C{continent_id} tree_cluster: "
              f"有 fine_clusters 但缺少 labels_fine，降级为 scattered")
        grid_mask = build_mask_from_position(
            "scattered", continent_map, continent_id,
            water_mask_grid, map_w, map_h)
        mode = "scattered(fallback)"

    if grid_mask is None or grid_mask.sum() == 0:
        return [], {"placed": 0, "sampled": 0, "mode": mode}

    density_map = DENSITY_MAP_TREE
    r = density_map.get(density, density_map["normal"])

    points = poisson_sample_in_mask(grid_mask, r, rng, map_w, map_h)

    MAX_ENTITIES_PER_CLUSTER = 50
    if len(points) > MAX_ENTITIES_PER_CLUSTER:
        rng.shuffle(points)
        points = points[:MAX_ENTITIES_PER_CLUSTER]

    entities = []
    for px, pz in points:
        model_id, group_name, _ = _select_model_by_texture(
            px, pz, "tree", rng,
            texture_grid, tex_to_group, tex_catalog, fallback_group)
        if model_id is None:
            continue

        wx, wz = grid_to_world(px, pz, origin_x, origin_z, grid_size)
        yaw = rng.uniform(0, 360)
        scale = rng.uniform(0.9, 1.1)
        entities.append(make_entity((wx, wz), model_id, yaw=yaw, scale=scale))
        TEX_GROUP_STATS[group_name]["tree"] += 1

    stats = {
        "placed": len(entities),
        "sampled": len(points),
        "mask_cells": int(grid_mask.sum()),
        "mode": mode,
    }
    return entities, stats


# ---------------------------------------------------------------------------
# v3: mountain_chain 处理
# ---------------------------------------------------------------------------
def process_mountain_chain(deco, continent_id, labels_fine, continent_map,
                            water_mask_grid, map_w, map_h,
                            origin_x, origin_z, grid_size, rng,
                            texture_grid, tex_to_group, tex_catalog,
                            fallback_group):
    """
    处理 mountain_chain 类型装饰物 (v3)。

    沿 from→to 线段均匀放置 count 座山峰，加法线随机偏移。
    """
    from_pos = deco.get("from", "center")
    to_pos = deco.get("to", "center")
    count = deco.get("count", 3)

    if count <= 0:
        return [], {"placed": 0, "mode": "mountain_chain(0)"}

    # 获取起点和终点的格子坐标
    from_x, from_z = _get_position_center(
        from_pos, continent_map, continent_id, map_w, map_h)
    to_x, to_z = _get_position_center(
        to_pos, continent_map, continent_id, map_w, map_h)

    # 沿线均匀取 count 个点
    chain_points = []
    if count == 1:
        # 单点: 取 from/to 中点
        mx = (from_x + to_x) / 2.0
        mz = (from_z + to_z) / 2.0
        chain_points.append((mx, mz))
    else:
        for i in range(count):
            t = i / (count - 1)
            px = from_x + t * (to_x - from_x)
            pz = from_z + t * (to_z - from_z)
            chain_points.append((px, pz))

    # 计算法线方向（垂直于 from→to 线段）
    dx = to_x - from_x
    dz = to_z - from_z
    line_len = math.sqrt(dx * dx + dz * dz)
    if line_len > 0:
        norm_x = -dz / line_len
        norm_z = dx / line_len
    else:
        norm_x, norm_z = 1.0, 0.0

    entities = []
    for px, pz in chain_points:
        # 加法线偏移 ±1~2 格
        offset = rng.uniform(-2.0, 2.0)
        px += norm_x * offset
        pz += norm_z * offset

        # 水域检查
        if not is_land(px, pz, water_mask_grid, map_w, map_h):
            continue

        model_id, group_name, group_pb = _select_model_by_texture(
            px, pz, "mountain", rng,
            texture_grid, tex_to_group, tex_catalog, fallback_group)
        if model_id is None:
            continue

        wx, wz = grid_to_world(px, pz, origin_x, origin_z, grid_size)
        yaw = rng.uniform(0, 360)

        # 自动 scale
        pb = group_pb.get(model_id)
        base_scale = _compute_mountain_scale(pb, grid_size, target_grids=4)
        scale = base_scale * rng.uniform(0.85, 1.15)

        entities.append(make_entity((wx, wz), model_id, yaw=yaw, scale=scale))
        TEX_GROUP_STATS[group_name]["mountain"] += 1

    stats = {
        "placed": len(entities),
        "sampled": len(chain_points),
        "mode": f"chain({from_pos}->{to_pos}, count={count})",
    }
    return entities, stats


# ---------------------------------------------------------------------------
# 主入口 (v3)
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
    parser = argparse.ArgumentParser(
        description="装饰物后处理 (v3 — 纹理组驱动 + 精确定位)"
    )
    parser.add_argument("input_json", help="decoration_input.json")
    parser.add_argument("water_mask_npy", help="water_mask_grid.npy")
    parser.add_argument("output_json", help="输出 decoration_entities.json")
    parser.add_argument("--labels-fine", default=None,
                        help="labels_fine.npy (可选, 启用 mask 采样)")
    parser.add_argument("--continent-map", default=None,
                        help="continent_map_full.npy (可选, 启用 mask 采样)")
    parser.add_argument("--texture-grid", default=None,
                        help="texture_grid.csv (可选, 启用纹理组驱动模型选择)")

    args = parser.parse_args()

    # 自动从 map_info.json 读取地图参数
    output_dir = os.path.dirname(os.path.abspath(args.water_mask_npy))
    map_w, map_h, origin_x, origin_z, grid_size = _load_map_info(output_dir)

    # 加载输入
    with open(args.input_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    water_mask = np.load(args.water_mask_npy)
    rng = np.random.RandomState(42)

    # 可选: 加载 fine labels 和 continent map
    labels_fine = None
    continent_map = None
    if args.labels_fine and os.path.exists(args.labels_fine):
        labels_fine = np.load(args.labels_fine)
        print(f"[info] labels_fine: {labels_fine.shape}")
    if args.continent_map and os.path.exists(args.continent_map):
        continent_map = np.load(args.continent_map)
        print(f"[info] continent_map: {continent_map.shape}")

    if labels_fine is None or continent_map is None:
        print("[info] mask 采样不可用 (缺少 labels_fine 或 continent_map)")

    # ---- v3: 加载纹理组 catalog ----
    global TEXTURE_GROUP_CATALOG, TEXTURE_ID_TO_GROUP, TEXTURE_GRID, TEX_GROUP_STATS
    global TREE_MODELS, ROCK_MODELS, ROCK_PICKBOUNDS

    tex_catalog = {}
    tex_to_group = {}
    fallback_group = "grassland"
    texture_grid = None

    try:
        tex_catalog, tex_to_group, fallback_group = _load_texture_group_catalog()
        TEXTURE_GROUP_CATALOG = tex_catalog
        TEXTURE_ID_TO_GROUP = tex_to_group
    except Exception as e:
        print(f"  [WARNING] 无法加载纹理组 catalog: {e}")
        print(f"  [WARNING] 将使用旧 style fallback")

    if args.texture_grid and os.path.exists(args.texture_grid):
        texture_grid = _load_texture_grid(args.texture_grid)
        TEXTURE_GRID = texture_grid
    else:
        print("[info] texture_grid 不可用，所有采样点使用 grassland fallback")

    # v1/v2 兼容: 加载旧 catalog（仅旧格式 tree/mountain 需要）
    style = data.get("style", "temperate")
    TREE_MODELS, ROCK_MODELS, ROCK_PICKBOUNDS = _load_catalog_legacy(style)

    print(f"[decoration_postprocess v3] 地图: {map_w}x{map_h}, "
          f"origin=({origin_x},{origin_z}), grid={grid_size}")
    print(f"[decoration_postprocess v3] 水域格数: {water_mask.sum()}")

    all_entities = []

    # ---- v3 格式: continents.{id}.decorations ----
    continents_data = data.get("continents", {})
    if continents_data:
        for cid_str, cdata in continents_data.items():
            cid = int(cid_str)
            decorations = cdata.get("decorations", [])

            for deco in decorations:
                deco_type = deco.get("type", "tree")

                # v3 新类型路由
                if deco_type == "tree_cluster":
                    entities, stats = process_tree_cluster(
                        deco, cid, labels_fine, continent_map,
                        water_mask, map_w, map_h,
                        origin_x, origin_z, grid_size, rng,
                        texture_grid, tex_to_group, tex_catalog,
                        fallback_group)
                    all_entities.extend(entities)
                    print(f"  [C{cid} tree_cluster] mode={stats['mode']}, "
                          f"mask_cells={stats.get('mask_cells', '?')}, "
                          f"placed={stats['placed']}")

                elif deco_type == "mountain_chain":
                    entities, stats = process_mountain_chain(
                        deco, cid, labels_fine, continent_map,
                        water_mask, map_w, map_h,
                        origin_x, origin_z, grid_size, rng,
                        texture_grid, tex_to_group, tex_catalog,
                        fallback_group)
                    all_entities.extend(entities)
                    print(f"  [C{cid} mountain_chain] mode={stats['mode']}, "
                          f"placed={stats['placed']}")

                else:
                    # v2 兼容: 旧格式 tree/mountain
                    model_list = TREE_MODELS if deco_type == "tree" else ROCK_MODELS
                    scale_range = (0.9, 1.1) if deco_type == "tree" else (0.8, 1.2)

                    entities, stats = process_decoration_v2(
                        deco, cid, labels_fine, continent_map,
                        water_mask, map_w, map_h,
                        origin_x, origin_z, grid_size, rng,
                        model_list, scale_range,
                        rock_pickbounds=ROCK_PICKBOUNDS
                    )
                    all_entities.extend(entities)
                    print(f"  [C{cid} {deco_type}(legacy)] mode={stats['mode']}, "
                          f"mask_cells={stats.get('mask_cells', '?')}, "
                          f"placed={stats['placed']}")

    # ---- v1 兼容: 旧格式 trees/mountains ----
    tree_regions = data.get("trees", [])
    if tree_regions:
        tree_entities, tree_stats = process_trees(
            tree_regions, water_mask, map_w, map_h,
            origin_x, origin_z, grid_size, rng)
        all_entities.extend(tree_entities)
        print(f"[trees-legacy] 采样 {tree_stats['sampled']}, "
              f"放置 {tree_stats['placed']}, "
              f"水域过滤 {tree_stats['water_filtered']}")

    mountain_regions = data.get("mountains", [])
    if mountain_regions:
        rock_entities, rock_stats = process_rocks(
            mountain_regions, water_mask, map_w, map_h,
            origin_x, origin_z, grid_size, rng)
        all_entities.extend(rock_entities)
        print(f"[rocks-legacy] 采样 {rock_stats['sampled']}, "
              f"放置 {rock_stats['placed']}, "
              f"水域过滤 {rock_stats['water_filtered']}")

    # ---- 桥梁 (不变) ----
    bridge_list = data.get("bridges", [])
    if bridge_list:
        bridge_entities, bridge_stats = process_bridges(
            bridge_list, water_mask, map_w, map_h,
            origin_x, origin_z, grid_size)
        all_entities.extend(bridge_entities)
        print(f"[bridges] 放置 {bridge_stats['placed']}, "
              f"吸附 {bridge_stats['snapped']}, "
              f"丢弃 {bridge_stats['discarded']}")

    # ---- v3: 按纹理组统计输出 ----
    if TEX_GROUP_STATS:
        print("\n[统计] 按纹理组分布:")
        for group_name, counts in sorted(TEX_GROUP_STATS.items()):
            label = tex_catalog.get(group_name, {}).get("label", "?")
            print(f"  {group_name} ({label}): "
                  f"树 {counts['tree']}, 山 {counts['mountain']}")

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

    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(sanitize(all_entities), f, indent=2, ensure_ascii=False)

    print(f"\n[decoration_postprocess v3] 总计 {len(all_entities)} 个实体 → {args.output_json}")


if __name__ == "__main__":
    main()
