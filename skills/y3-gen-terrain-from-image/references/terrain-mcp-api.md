# Y3 地形 MCP 接口速查

> 所有 Y3 编辑器可用的 cmd 定义在：`I:\map\src\Server\server\engine\dm\editor\controller\state_new\`
> cmd 实现在：`I:\map\src\Server\server\engine\dm\editor\model\command\EditSceneCmdImpl.py`
> MCP handler 实现在：`I:\map\src\Server\server\engine\dm\editor\mcp\handlers\terrain_handlers.py`

---

## ✅ 已实现的 MCP Tool（13 个）

| MCP Tool | 对应 cmd             | 用途                         | Pass |
|----------|----------------------|------------------------------|------|
| `terrain_set_height_block` | `TILE_HEIGHT_OFFSET` | 悬崖高度（抬高/降低/整平） | 1    |
| `terrain_set_deep_water_block` | `TILE_DEEP_WATER_FLAG` | 深水（不可通行）            | 1    |
| `terrain_set_shallow_water_block` | `TILE_SHALLOW_WATER_FLAG` | 浅水（可通行）            | 1    |
| `terrain_set_plain_water_block` | `TILE_PLAIN_WATER_FLAG` | 平面水                      | 1    |
| `terrain_erase_plain_water_block` | `TILE_ERASE_PLAIN_WATER_FLAG` | 擦除平面水         | 1    |
| `terrain_set_road_block` | `TILE_ROAD_FLAG` | 斜坡/道路                | 1    |
| `terrain_set_crack_block` | `TILE_CRACK_FLAG` | 裂缝（地形空洞）            | 1    |
| `terrain_hill_lift_block` | `TERRAIN_HILL_LIFT` | 地形隆起/降低              | 1    |
| `terrain_hill_flat_block` | `TERRAIN_HILL_FLAT` | 地形推平                | 1    |
| `terrain_hill_smooth_block` | `TERRAIN_HILL_SMOOTH` | 地形平滑                | 1    |
| `terrain_hill_steep_block` | `TERRAIN_HILL_STEEP` | 地形陡峭化             | 1    |
| `terrain_cover_draw_block` | `COVER_DRAW` | 绘制地面纹理（材质层）   | 2    |
| `terrain_get_block` | （读取接口）       | 读取地形状态             | Verify |

---

## 新增 MCP 接口指南

新增 MCP 接口时，参考现有 `terrain_handlers.py` 的模式：

1. 在 `handlers/terrain_handlers.py`（或新建 `handlers/xxx_handlers.py`）中实现 handler 函数
2. 在 `tools.py` 中注册 tool
3. 核心模式：读 `cells` 数组 → 循环调 `do_cmd`
4. **植被坐标系注意**：植被用 `calculate_foliage_grid_pos`，地形用 `calculate_terrain_grid_pos`

---

## 注意事项

1. `COVER_DRAW`（已有 MCP）vs `DRAW_TEXTURE`（缺失）：前者是材质层整格替换，后者是混合纹理层支持渐变
2. 植被/装饰物的坐标系与地形不同——`foliage_grid` vs `terrain_grid`
3. `ENTITY_CREATE` 的 `entities_info` 是复杂结构，包含 `type`、`pos`、`model_id` 等多个字段
4. `TERRAIN_HILL_HOLLOW`（镂空）与 `TILE_CRACK_FLAG`（裂缝）功能接近但实现不同