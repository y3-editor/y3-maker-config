# roguelike-survival

> ⚠️ **TERRAIN-ONLY 模板（仅地形）** — 本模板**不含** `editor_decoration.zip`。
> 地形 / 纹理 / 植被 / 装饰物布局 / 碰撞可完整导入；装饰物**物编**（模型 / 图标 / 属性）**不会还原**。
> 导入时 `import_terrain_template.py` 会返回 `decoration_zip: null` + warning，需**跳过** MCP `import_object_editor`。
> 清理原因：该 zip 达 134 MB（`include_dependencies=true` 打入了装饰物模型资源 `editor_model.kkres`）。清理时间 2026-09-23。
> 如需恢复完整模板：开编辑器打开源关卡 `EntryMap`，重跑 MCP `export_object_editor` 后重新导出模板。

## 模板名

`roguelike-survival`

## 地图尺寸

64 × 64

## 模板说明

肉鸽生存游戏模板

## 源关卡

`EntryMap`

## 导出时间

2026-05-15T01:45:20+00:00

## 包含文件清单

- `terrain.json`
- `texture.json`
- `terrainedit.json`
- `foliage.json`
- `texturefoliage.json`
- `decorationdata.data`
- `resourceobjectdata.data`
- `grid.data`

> ~~`editor_decoration.zip`~~ — 已清理（terrain-only 模式）

## 说明

- 8 个 `.json` / `.data` 文件（地形 / 纹理 / 植被 / 装饰物布局 / 资源摆件 / 碰撞）走文件直拷
- 原 `editor_decoration.zip` 由 MCP `export_object_editor` 产出、导入时由 MCP `import_object_editor` 应用；**本模板已删除该 zip**，导入时须跳过该步

## 逻辑节点

> 以下为地图中预设的逻辑节点坐标，供 Lua 代码通过 `y3.point.get_point_by_res_id()` 或 `y3.area.get_area_by_res_id()` 引用。导入模板后需通过 MCP `add_point` 等工具手动摆放到位。

| ID | 名称 | Y3 类型 | 坐标 (x, y) | 用途 |
|------|------|---------|-------------|------|
| F-3.5.2-逻辑-刷怪点-左上 | 出怪点（左上） | Point | （-6400, -6400） | 波次怪物刷新位置 |
| F-3.5.2-逻辑-刷怪点-右上 | 出怪点（右上） | Point | （6400, -6400） | 波次怪物刷新位置 |
| F-3.5.2-逻辑-刷怪点-左下 | 出怪点（左下） | Point | （-6400, 6400） | 波次怪物刷新位置 |
| F-3.5.2-逻辑-刷怪点-右下 | 出怪点（右下） | Point | （6400, 6400） | 波次怪物刷新位置 |
| F-3.5.2-逻辑-英雄出生点 | 防守基地（中心） | Point | （0, 0） | 英雄初始与复活位置 |
> 坐标值为编辑器坐标（cm），64×64 地图范围约 [-6400, 6400]。

### 布局示意

```
┌──────────────────────────────────┐
│ 左上出怪点               右上出怪点 │
│                                    │
│                                    │
│            中心防守基地             │
│                                    │
│                                    │
│ 左下出怪点               右下出怪点 │
└──────────────────────────────────┘
```

## 导入风险提示

装饰物 / 资源摆件将被整体覆盖；如目标关卡有针对装饰物 ID 的脚本引用，导入后引用将失效。
