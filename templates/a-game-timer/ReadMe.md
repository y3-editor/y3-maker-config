# a-game-timer — 三层时间轴回调调度器

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 三层时间轴回调调度器 |
| 路径 | `.codemaker/templates/a-game-timer/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `timer`, `clock`, `frame`, `second`, `minute`, `global-timer`, `game-timer` |
| 适用场景 | 任何 Y3 项目都需要时间驱动逻辑：UI 刷新、战斗计时、Boss 阶段、Buff 倒计时、AOE 轮询 — 统一走 GameTimer 而非散落裸 `y3.ltimer`，便于 GC 管理 + 模拟调试 |
| 依赖 | `y3.ltimer`（`loop_frame` / `loop`） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → TimerInstance` |
| 参数 | `params.ltimer`（必需，`{ loop_frame, loop }`）、`params.name?`（名称） |
| 测试状态 | `tested, 2026-05-29, 4/4 sync in agentmap (execute_lua). Async timer path not covered` |
| 集成说明 | 见下方 §集成指南 |

---

## 功能概述

逐帧/逐秒/逐分三层独立调度。调用方注册回调到对应层级，Timer 负责统一驱动。

典型用法：
- **globalTimer**（菜单/UI 动画/签到倒计时）— 不随游戏暂停
- **inGameTimer**（战斗/技能/Buff 持续）— 暂停时通过移除回调/清空 timer 停止

---

## 参数

```lua
M.setup({
    ltimer = y3.ltimer,      -- 必需：{ loop_frame(func, interval), loop(interval, func) }
    name   = "global",       -- 可选：调试用名称
})
```

---

## 返回实例 API

| 方法 | 说明 |
|------|------|
| `timer:start()` | 启动计时（幂等，重复调用无影响） |
| `timer:clear()` | 停止所有内部 timer + 清空所有回调 |
| `timer:addFrameUpdateFunc(fn)` | 每帧调用 `fn(curFrame)` |
| `timer:removeFrameUpdateFunc(fn)` | 移除帧回调 |
| `timer:addSecondUpdateFunc(fn)` | 每秒调用 `fn(curSecond)` |
| `timer:removeSecondUpdateFunc(fn)` | 移除秒回调 |
| `timer:addMinuteUpdateFunc(fn)` | 每分钟调用 `fn(curMinute)` |
| `timer:removeMinuteUpdateFunc(fn)` | 移除分钟回调 |
| `timer:getCurFrame()` | 返回累计帧数 |
| `timer:getCurSecond()` | 返回累计秒数 |
| `timer:getCurMinute()` | 返回累计分钟数 |
| `timer:setCurSecond(value)` | 跳转到指定秒数（GM 调试） |
| `timer:addCurSecond(n)` | 当前秒数 ±n（暂停补偿/快进） |

---

## 集成指南

### 1. 引入与创建

```lua
-- 在 main.lua 或 init.lua 中
local GameTimer = include '.codemaker.templates.a-game-timer.logic'

-- 全局 timer（UI / 菜单 / 签到 用）
MyGame.globalTimer = GameTimer.setup({ ltimer = y3.ltimer, name = "global" })
MyGame.globalTimer:start()

-- 局内 timer（战斗用，暂停时清空）
MyGame.inGameTimer = GameTimer.setup({ ltimer = y3.ltimer, name = "inGame" })
MyGame.inGameTimer:start()
```

### 2. 注册回调

```lua
-- 每帧：UI 动画 / 技能指示器
MyGame.globalTimer:addFrameUpdateFunc(function(frame)
    MyUI:updateFrame(frame)
end)

-- 每秒：战斗计时 / Buff 倒计时
MyGame.inGameTimer:addSecondUpdateFunc(function(second)
    BattleSystem:onTick(second)
end)

-- 每分钟：签到检测 / 跨日判定
MyGame.globalTimer:addMinuteUpdateFunc(function(minute)
    DailyCheck:onMinute(minute)
end)
```

### 3. GM 调试

```lua
-- 快速跳到第 120 秒（模拟战斗中期）
MyGame.inGameTimer:setCurSecond(120)

-- 快进 10 秒
MyGame.inGameTimer:addCurSecond(10)
```

### 4. 多实例模式

```lua
-- 独立 UI Timer（不受主 Timer 暂停影响）
MyGame.uiTimer = GameTimer.setup({ ltimer = y3.ltimer, name = "ui" })
MyGame.uiTimer:start()

-- 切换关卡清空旧 timer
MyGame.inGameTimer:clear()
MyGame.inGameTimer = GameTimer.setup({ ltimer = y3.ltimer, name = "inGame" })
MyGame.inGameTimer:start()
```

---

## 架构说明

- **不依赖 Class 系统**：用闭包替代 `Handler(self, ...)`、用 `setup` 工厂替代 `New`，零外部依赖
- **幂等 start**：重复调用 `start()` 不重复创建 timer，安全
- **clear 彻底解绑**：`clear()` 移除所有 3 个底层 timer + 清空 3 个回调表，不会残留引用

## 与其他模板的协作

- `b-anim-helper`：依赖 GameTimer 的帧回调驱动动画事件
- `c-buff-effect`：依赖 GameTimer 的秒回调做 Buff 持续扣血
- `a-event-bus`：可绑定时间事件（如"第 60 秒"发布刷怪事件）
