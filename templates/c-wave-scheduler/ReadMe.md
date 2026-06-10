# c-wave-scheduler — 时间轴关卡调度器

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 时间轴关卡调度器 |
| 路径 | `.codemaker/templates/c-wave-scheduler/` |
| 状态 | `verified` |
| 版本 | `v0.1.0` |
| 能力标签 | `wave`, `schedule`, `spawn`, `boss`, `stage`, `level`, `tower-defense`, `roguelike` |
| 适用场景 | 塔防、Roguelike、守城、限时关卡、爬塔。任何"时间驱动的怪物刷新 / 道具刷新 / 关卡事件"都可以用本调度器统一管理 |
| 依赖 | 纯 Lua（建议配 `a-game-timer` 提供 tick 源） |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params) → Scheduler` |
| 参数 | `params.entries`（WaveEntry 数组）、`adapter` 实现 4 个核心 handler |
| 测试状态 | `verified, 2026-06-01, 全部通过 in agentmap (波次塔防Demo)` |
| 集成说明 | 见 §集成指南 |

---

## 4 大调度模式

| kind | 用途 | 项目原型 |
|---|---|---|
| `oneshot` | 一次性事件（Boss 出场 / 宝箱 / 最终 BOSS） | type 3/5/6 |
| `periodic` | 周期触发（每 N 秒精英刷新 / 物资补给） | type 2 |
| `sustained` | 维持目标数量（基础刷怪 → 限流补充） | type 1 |
| `stage` | 阶段切换（小 Boss 节点 → 阶段 +1，触发 UI/广播） | type 4 |
| 自定义 kind | 由 `adapter.handle_custom` 接管 | — |

---

## 集成指南

### 1. 配置 entries

```lua
local schedule = {
    entries = {
        -- 第 0~60 秒持续刷小怪，维持上限 30
        { at = 0,    kind = 'sustained', id = 'goblin', limit = 30, rate = 5 },

        -- 第 30 秒起每 15 秒刷一波精英
        { at = 30,   kind = 'periodic',  id = 'orc_elite', interval = 15, count = 3 },

        -- 第 60 秒小 Boss（带 5 秒预警 + 阶段标题）
        { at = 60,   kind = 'stage',     warn_lead = 5,
          payload = { title = '第 2 波', boss_id = 'troll_chief' } },

        -- 第 60 秒同时刷 Boss
        { at = 60,   kind = 'oneshot',   id = 'troll_chief' },

        -- 第 120 秒第二波小 Boss
        { at = 120,  kind = 'stage',     warn_lead = 5,
          payload = { title = '第 3 波', boss_id = 'troll_warlord' } },

        -- 第 180 秒最终 BOSS
        { at = 180,  kind = 'oneshot',   id = 'final_dragon' },

        -- 第 30/90/150 秒掉宝箱
        { at = 30,   kind = 'oneshot',   id = 'treasure_box', payload = { tier = 1 } },
        { at = 90,   kind = 'oneshot',   id = 'treasure_box', payload = { tier = 2 } },
        { at = 150,  kind = 'oneshot',   id = 'treasure_box', payload = { tier = 3 } },
    },
}
```

### 2. 实现 Adapter

```lua
local adapter = {
    -- 一次性事件
    handle_oneshot = function(entry, ctx)
        if entry.id == 'final_dragon' then
            spawnBoss(entry.id, getBossPoint())
        elseif entry.id == 'treasure_box' then
            spawnTreasure(entry.payload.tier, getRandomPoint())
        else
            spawnUnit(entry.id, getRandomPoint())
        end
    end,

    -- 周期触发
    handle_periodic = function(entry, ctx)
        spawnUnit(entry.id, getRandomPoint())
    end,

    -- 维量补充
    handle_sustained = function(entry, ctx)
        local point = getSpawnPoint(ctx.current_stage)
        local unit = spawnUnit(entry.id, point)
        -- 单位死亡时通知 scheduler 减计数
        unit:event('单位-死亡', function()
            scheduler:updateActiveCount(entry, -1)
        end)
        return 1  -- 返回新增数量
    end,

    -- 阶段切换
    handle_stage = function(entry, ctx)
        local title = entry.payload and entry.payload.title or ('第 ' .. ctx.current_stage .. ' 波')
        ChatUI:showBroadcast('BOSS 出现：' .. title)
        AudioMgr:playBoss()
        EventBus:Publish('STAGE_CHANGED', ctx.current_stage)
    end,

    -- 阶段预警
    handle_warn = function(entry, ctx)
        AudioMgr:playWarning()
        EventBus:Publish('STAGE_WARN', entry.warn_lead)
    end,

    -- 全部完成
    on_schedule_done = function()
        EventBus:Publish('LEVEL_CLEAR')
    end,
}
```

### 3. 启动调度

```lua
local scheduler = WaveScheduler.setup(adapter, schedule)

-- 配合 a-game-timer
inGameTimer:addSecondUpdateFunc(function(s)
    scheduler:onTick(s)
end)
```

### 4. UI 联动

```lua
-- 倒计时显示
local nextStageTime = scheduler:getNextStageTime()
local nextTitle = scheduler:getNextStageTitle() or '最终BOSS'
HUD:setStageInfo(nextTitle, nextStageTime - currentTime)

-- 当前阶段
local currentStage = scheduler:getCurrentStage()
```

### 5. GM 调试

```lua
-- 跳到第 3 波
scheduler:jumpToStage(3, currentTime)

-- 重置整局
scheduler:reset()
```

---

## 与项目原型的对照

| 项目（WaveController） | 模板（c-wave-scheduler） |
|---|---|
| `type 1` 基础刷怪 + limit/rate | `kind: sustained` + `limit/rate` |
| `type 2` 精英按 time_spd | `kind: periodic` + `interval` |
| `type 3` 固定怪 | `kind: oneshot` |
| `type 4` 小 Boss 节点（阶段切换+广播+UI） | `kind: stage` + `warn_lead` + `handle_warn`/`handle_stage` |
| `type 5` 最终 BOSS | `kind: oneshot` 或单独 stage |
| `type 6` 宝箱 | `kind: oneshot` + `payload.tier` |
| `event_dispatch '玩家-游戏波次'` | `handle_stage` 中由 adapter 自行 dispatch |
| GM 设置波次/速度 | `scheduler:jumpToStage` / 直接修改 entry.limit |

---

## 限制

- 仅支持基于绝对时间的调度。条件型（杀够 N 怪触发）需在 adapter 内自行触发外部事件
- 多区域刷怪由 adapter 内部决策（sustained handler 收到 ctx 后自行选区域）
- 复杂分支关卡（杀 Boss A 进剧情 1 / 失败进剧情 2）需配合 `a-game-fsm`

---

## 验证记录

### v0.1.0 · 2026-06-01 · 波次塔防 Demo（agentmap）

**项目**：`maps/EntryMap/script/td_wave_adapter.lua` + `td_config.lua`（10 条 entry 覆盖 4 种模式）

| 测试点 | 结果 |
|---|---|
| `sustained` 限流补充（limit=8, rate=2） | ✅ 精确（用 `setActiveCount` 每秒同步活跃数） |
| `periodic` 周期触发（interval=20） | ✅ |
| `stage` 阶段切换（3 次）+ `warn_lead=5` 预警 | ✅ |
| `oneshot` 单次触发（Boss × 3 + 宝箱 × 3） | ✅ |
| `on_schedule_done` 回调 | ✅ |
| `jumpToStage` 调试 API | ✅ |
| 集成实跑：全程 277 秒无 Lua error | ✅ |
| 接入成本 | adapter ~95 行 |

**已知接入注意事项**：
- `sustained` 死亡计数推荐用**每秒扫描活跃数 + `setActiveCount`**（而非依赖死亡事件 `updateActiveCount`），更健壮
- `onTick(t)` 中 `t` 必须单调递增的绝对秒数；用 `y3.ltimer.loop(1)` 驱动即可
