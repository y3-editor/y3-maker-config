# b-base-panel — UI 面板基类（控件自动绑定）

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | UI 面板基类（`_` 前缀控件自动绑定） |
| 路径 | `.codemaker/templates/b-base-panel/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `ui`, `panel`, `control-binding`, `convention`, `show-hide`, `lifecycle` |
| 适用场景 | 所有 UI 面板的基类：约定控件名 `_xxx` 自动绑到 `self._controls._xxx`，无需手写 N 个 get_child + 属性赋值。支持 UUID/路径双模查找，show/hide 生命周期 |
| 依赖 | `Class` 系统 + `y3.ui.get_by_handle` / `y3.ui.get_ui` |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → BasePanel` |
| 参数 | `params.Class`, `params.get_ui_by_uuid`, `params.get_ui_by_path`, `params.get_local_player`, `params.resolve_uuid?`, `params.resolve_path?` |
| 测试状态 | `tested, 2026-05-29, 4/4 in agentmap (execute_lua)` |
| 集成说明 | `Extends('ShopPanel', 'Bp')`；`panel:init('shop_uuid')` → `panel._controls._btnBuy` 自动可用 |
