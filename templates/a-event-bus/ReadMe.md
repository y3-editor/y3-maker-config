# a-event-bus — 纯 Lua 订阅发布事件总线

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 纯 Lua 订阅发布事件总线 |
| 路径 | `.codemaker/templates/a-event-bus/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `event`, `pubsub`, `subscribe`, `publish`, `decouple`, `bus` |
| 适用场景 | 跨模块解耦通信（Manager ↔ UI、Manager ↔ Manager）。替代直接引用，降低耦合度。任何需要"一处发布、多处订阅"的场景：背包变化→UI刷新+战力重算+成就检测 |
| 依赖 | 纯 Lua |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → EventBus` |
| 参数 | `params.debug?` (记录订阅源)、`params.on_error?` (异常回调)、`params.sort_mode?` ("priority"/"none") |
| 测试状态 | `tested, 2026-05-29, 5/5 in agentmap (execute_lua)` |
| 集成说明 | 见下方 §集成指南 |

---

## 功能概述

`Subscribe / Unsubscribe / Publish / Clear` 四 API。priority 排序 + xpcall 异常隔离。跨模块通信唯一通道。

---

## 参数

```lua
M.setup({
    debug     = false,       -- 是否记录订阅源信息（调试用）
    on_error  = print,       -- 监听器异常回调
    sort_mode = 'priority',  -- "priority" 按 priority 排序 / "none" 保留插入序
})
```

---

## 返回实例 API

| 方法 | 说明 |
|------|------|
| `bus:Subscribe(event, callback, priority?)` | 订阅事件。priority 默认 20，越小越先执行 |
| `bus:Unsubscribe(event, callback)` | 取消订阅（传原始 callback 引用） |
| `bus:Publish(event, ...)` | 发布事件，依次通知所有订阅者。单监听器异常不阻断后续 |
| `bus:Clear()` | 清空所有订阅 |

---

## 集成指南

### 1. 创建全局 Bus

```lua
local EventBus = include '.codemaker.templates.a-event-bus.logic'
MyGame.bus = EventBus.setup({
    debug    = y3.game.get_start_mode() == 1,  -- 编辑器环境开 debug
    on_error = log.error,
})
```

### 2. 订阅事件（定义事件常量表）

```lua
-- 先定义事件常量（放在 const/ 目录）
MyGame.Event = {
    CURRENCY_CHANGED = 'currency_changed',
    BAG_CHANGED      = 'bag_changed',
    PLAYER_DIED      = 'player_died',
    BOSS_KILLED      = 'boss_killed',
    STAGE_START      = 'stage_start',
}

-- UI 模块订阅：货币变化后刷新显示
MyGame.bus:Subscribe(MyGame.Event.CURRENCY_CHANGED, function(playerId, currencyId, newValue)
    CurrencyUI:refresh(playerId, currencyId, newValue)
end, 10)  -- priority 10：先更新数据，后刷新 UI

-- 成就模块订阅
MyGame.bus:Subscribe(MyGame.Event.BOSS_KILLED, function(playerId, bossId)
    AchievementMgr:onBossKilled(playerId, bossId)
end)
```

### 3. 发布事件

```lua
-- 数据层：货币变化时发布
MyGame.bus:Publish(MyGame.Event.CURRENCY_CHANGED, playerId, 'gold', player:getCurrency('gold'))
```

### 4. 取消订阅（如销毁 UI 时）

```lua
local function onBagChanged(playerId, slot)
    BagUI:refreshSlot(playerId, slot)
end

MyGame.bus:Subscribe(MyGame.Event.BAG_CHANGED, onBagChanged)

-- UI 销毁时
MyGame.bus:Unsubscribe(MyGame.Event.BAG_CHANGED, onBagChanged)
```

---

## 架构说明

- **零依赖**：纯 Lua table + function，不依赖 y3 引擎、不依赖 Class 系统
- **异常隔离**：`xpcall` 包装每个监听器，一个模块崩溃不影响其他
- **Priority 队列**：让"数据层"(priority<15) 先于 "UI 层"(priority>15) 执行
- **debug 模式**：记录每个订阅的 `源文件:行号`，便于排查订阅残留
