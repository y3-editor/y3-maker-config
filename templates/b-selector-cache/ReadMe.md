# b-selector-cache — 区域单位选择器（缓存版）

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | 区域单位选择器（缓存版） |
| 路径 | `.codemaker/templates/b-selector-cache/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `selector`, `area`, `unit`, `cache`, `range`, `enemy`, `distance` |
| 适用场景 | AI索敌（最近敌人）、AOE范围预判、高频率技能选目标（同帧复用cache）、伤害分摊判定 |
| 依赖 | `y3.shape.create_circular_shape` + `GameAPI.filter_unit_id_list_in_area_v2` + `y3.player_group` |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → SelectorCache` |
| 参数 | `params.create_circular_shape`, `params.filter_units`, `params.get_enemy_group` |
| 测试状态 | `tested, 2026-05-29, 7/7 in agentmap (execute_lua)` |
| 集成说明 | `M.setup({...}); selector:cache(unit, range); units = selector:getUnits(unit)` |
