# a-dync-component — 动态 Prefab 组件基类

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 动态 Prefab 组件基类 |
| 路径 | `.codemaker/templates/a-dync-component/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `ui`, `prefab`, `component`, `dynamic`, `base-class` |
| 适用场景 | 所有基于 Prefab 的动态 UI 组件（货币条、物品槽、卡牌、技能图标等）的基类。子类只需 `self:initDyncComponent(resName, parent)` 即完成实例化 |
| 依赖 | `Class` 系统 + `y3.ui_prefab.create` |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → DyncComponent 基类` |
| 参数 | `params.Class`, `params.get_local_player`, `params.create_ui_prefab` |
| 测试状态 | `tested, 2026-05-29, 4/4 in agentmap (execute_lua)` |
| 集成说明 | `local DC = include '...'; local Base = DC.setup({...}); Extends('CurrencyCmp', 'Base'); cmp:initDyncComponent('myPrefab', parent)` |
