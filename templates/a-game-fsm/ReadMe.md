# a-game-fsm — 通用父子状态机

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 通用父子状态机 |
| 路径 | `.codemaker/templates/a-game-fsm/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `fsm`, `state-machine`, `flow`, `game-stage`, `parent-child` |
| 适用场景 | 游戏主流程（启动→准备→开始→胜利/失败→结束）、关卡子流程（波次准备→战斗→波次结算）、UI 面板流程（登录→选角→加载→游戏）、任何需要状态管控禁止跳阶段/回跳的流程 |
| 依赖 | 纯 Lua |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → FSM` |
| 参数 | `params.states` (状态枚举表)、`params.transitions` (迁移矩阵)、`params.initial` (初始状态)、`params.hooks?` (onEnter/onLeave)、`params.callbacks?` (命名回调)、`params.child?` (子状态机) |
| 测试状态 | `tested, 2026-05-29, 4/4 in agentmap (execute_lua)` |
| 集成说明 | 见下方 §集成指南 |

---

## 功能概述

自定义状态枚举 + 合法迁移矩阵 + onEnter/onLeave 钩子 + 命名回调 + 子状态机嵌套。禁止非法跳转，适合线性和分支游戏流程。

---

## 参数

```lua
M.setup({
    -- 状态枚举（key=内部名, value=显示名）
    states = {
        Init    = 'Init',
        Prepare = 'Prepare',
        Start   = 'Start',
        Win     = 'Win',
        Lose    = 'Lose',
        End     = 'End',
    },

    -- 迁移矩阵：每个状态允许迁移到哪些状态
    transitions = {
        Init    = { 'Prepare', 'Lose' },
        Prepare = { 'Start', 'Lose' },
        Start   = { 'Win', 'Lose' },
        Win     = { 'End' },
        Lose    = { 'End' },
        End     = {},
    },

    initial = 'Init',

    -- 钩子（可选）
    hooks = {
        Prepare = {
            onEnter = function() print('进入准备阶段') end,
            onLeave = function() print('离开准备阶段') end,
        },
        Start = {
            onEnter = function() SpawnEnemies() end,
        },
    },

    -- 命名回调（可选，状态变更后触发）
    callbacks = {
        Win  = function() ShowVictoryUI() end,
        Lose = function() ShowDefeatUI() end,
    },

    -- 子状态机（可选）
    child = stageFSM,
})
```

---

## 返回实例 API

| 方法 | 说明 |
|------|------|
| `fsm:tryToState(target)` | 尝试迁移。合法则执行钩子+回调，非法则忽略（可配合 log 警告） |
| `fsm:getState()` | 返回当前状态名（string） |
| `fsm:setChild(child_fsm)` | 挂接子状态机 |
| `fsm:getChild()` | 获取子状态机 |

---

## 集成指南

### 1. 基础用法

```lua
local FSM = include '.codemaker.templates.a-game-fsm.logic'

local gameFSM = FSM.setup({
    states      = { Init='Init', Lobby='Lobby', Battle='Battle', Result='Result', End='End' },
    transitions = {
        Init   = { 'Lobby', 'Result' },
        Lobby  = { 'Battle', 'Result' },
        Battle = { 'Result' },
        Result = { 'End' },
        End    = {},
    },
    initial = 'Init',
    hooks = {
        Battle = { onEnter = function() StartFight() end },
        Result = { onEnter = function() ShowResult() end },
    },
})

gameFSM:tryToState('Lobby')
-- ❌ 非法：Lobby 不能直接到 End
gameFSM:tryToState('End')
-- ✅ 合法：Lobby → Battle
gameFSM:tryToState('Battle')
```

### 2. 父子嵌套

```lua
-- 父：游戏流程
local gameFSM = FSM.setup({ ... })

-- 子：关卡内波次流程
local stageFSM = FSM.setup({
    states      = { Idle='Idle', Wave1='Wave1', Wave2='Wave2', Boss='Boss', Clear='Clear' },
    transitions = {
        Idle  = { 'Wave1' },
        Wave1 = { 'Wave2', 'Clear' },
        Wave2 = { 'Boss', 'Clear' },
        Boss  = { 'Clear' },
        Clear = {},
    },
    initial = 'Idle',
})

gameFSM:setChild(stageFSM)
```

### 3. 与 EventBus 联动

```lua
-- 状态变更时发布事件
local function make_hooks(bus, event_prefix)
    return setmetatable({}, {
        __index = function(t, state)
            t[state] = {
                onEnter = function() bus:Publish(event_prefix .. '.Enter', state) end,
                onLeave = function() bus:Publish(event_prefix .. '.Leave', state) end,
            }
            return t[state]
        end
    })
end

local fsm = FSM.setup({
    states = { ... },
    transitions = { ... },
    initial = 'Init',
    hooks = make_hooks(MyGame.bus, 'GameFlow'),
})
-- 其他模块可订阅 MyGame.bus:Subscribe('GameFlow.Enter.Start', ...)
```

---

## 架构说明

- **零依赖**：纯 Lua table，不依赖 Class 系统
- **状态用 string**：与 EventBus 事件名天然对齐，便于跨模块广播
- **非法迁移静默**：`tryToState` 对非法迁移不做任何事，调用方可在外部 `check_transition` 或自行 log
- **钩子在迁移前/后**：`onLeave(prev)` 先于 `onEnter(next)`，保证清理→初始化顺序正确
