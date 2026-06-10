# b-base-view — UI 视图基类

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | UI 视图基类 |
| 路径 | `.codemaker/templates/b-base-view/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `ui`, `view`, `base-class`, `lifecycle`, `gc`, `show-hide` |
| 适用场景 | 所有 UI 面板共用的基类：生命周期（init/show/hide）、事件 GC 防泄漏、单例注册、refresh 标志。子类只需实现 `initUI` + `updateUI` |
| 依赖 | `Class` 系统 + `y3.gc.host`（或等价 GC 容器） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → View基类` |
| 参数 | `params.Class` (Class系统)、`params.create_gc_host` (GC容器)、`params.Delete` (GC销毁函数)、`params.on_register?` (单例注册)、`params.local_player_id?`、`params.local_player?` |
| 测试状态 | `tested, 2026-05-29, 4/4 in agentmap (execute_lua)` |
| 集成说明 | `local View = include '...' BView = View.setup({...})`；子类 `Extends('MyPanel', 'BView')` 后 `self:baseInit(uiNode)` |

---

## 功能概述

View 基类封装 UI 面板的四段式生命周期 + GC 事件管理：
1. **baseInit** → 注册单例 + initUI + registerEvent
2. **onShow** → 置可见 + updateUI + customShowEvt
3. **onHide** → 置不可见 + customHideEvt
4. **clear** → 解绑所有事件

子类只需关注 `initUI/registerEvent/updateUI`。

---

## 集成指南

```lua
local ViewTemplate = include '.codemaker.templates.b-base-view.logic'

-- 创建基类
local BView = ViewTemplate.setup({
    Class           = Class,
    create_gc_host  = function() return y3.gc.host() end,
    on_register     = function(name, view) UIMgr:setUIViewCtrl(name, view) end,
    local_player_id = GamePlay:getLocalPlayerId(),
    local_player    = GamePlay:getLocalPlayer(),
})

-- 子类继承
local ShopPanel = Class 'ShopPanel'
Extends('ShopPanel', 'BView')

function ShopPanel:initUI()
    -- 绑定子控件
    self._btnBuy = self._root:get_child('btnBuy')
end

function ShopPanel:registerEvent()
    self._btnBuy:event('点击', function() self:_onBuy() end)
end

function ShopPanel:updateUI(data)
    -- 刷新数据
    self._btnBuy:set_text('购买 (' .. data.price .. ')')
end
```
