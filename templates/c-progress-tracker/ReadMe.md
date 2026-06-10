# c-progress-tracker — 通用进度追踪框架

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 通用进度追踪框架 |
| 路径 | `.codemaker/templates/c-progress-tracker/` |
| 状态 | `verified` |
| 版本 | `v0.1.0` |
| 能力标签 | `progress`, `achievement`, `task`, `mission`, `quest`, `collection`, `daily`, `weekly` |
| 适用场景 | 成就 / 任务（每日/每周/主线）/ 收集图鉴 / 称号解锁条件 / 引导任务进度——所有"按事件推进的进度"统一管理 |
| 依赖 | Adapter：DB 读写 + 奖励发放 |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params) → Tracker` |
| 参数 | `params.defs` (定义列表)、`params.get_time?`；`adapter.db_load/db_save` 必填，`grant_reward/on_unlock/on_progress` 可选 |
| 测试状态 | `verified, 2026-06-01, 全部通过 in agentmap (波次塔防Demo)` |
| 集成说明 | 见 §集成指南 |

---

## 核心特性

- **事件驱动**：业务侧 `tracker:onEvent(playerId, 'kill_boss', 1)` → 自动推进所有匹配 `event_type='kill_boss'` 的定义
- **自定义条件**：`def.condition` 闭包返回 `(should_count, delta)`，复杂条件（"连续 3 天登录"/"特定怪物 + 必须暴击"）一行实现
- **自动重置**：`reset_type: daily/weekly` 跨日/跨周自动归零（首次访问时检查）
- **分组**：`group` 字段把进度归类（achievement/daily/main/collection），`listByGroup` 一次拉一类用于 UI
- **自动 vs 手动发奖**：`auto_reward=true` 达成立即发奖；否则 `tracker:claim(playerId, id)` 手动领取
- **隐藏成就**：`hidden=true` 未达成不显示；`publish_at` 时间戳到达后公开
- **解锁回调**：`unlock_cb` 用于属性激励（如成就解锁后加属性）

---

## 集成指南

### 1. 定义 defs

```lua
local defs = {
    -- 成就：累计击杀 1000 怪
    {
        id = 'ach_kill_1000',
        event_type = 'kill_monster',
        target = 1000,
        group = 'achievement',
        reward = { type='currency', id='gold', num=500 },
        unlock_cb = function(playerId, def)
            -- 成就附带属性激励
            AttrSystem:addBaseAttr(playerId, '攻击', 10)
        end,
    },

    -- 每日任务：每日登录
    {
        id = 'daily_login',
        event_type = 'daily_login',
        target = 1,
        group = 'daily',
        reset_type = 'daily',
        reward = { type='currency', id='diamond', num=10 },
    },

    -- 每周任务：本周击杀 50 个 Boss
    {
        id = 'weekly_kill_boss_50',
        event_type = 'kill_boss',
        target = 50,
        group = 'weekly',
        reset_type = 'weekly',
        reward = { type='item', id=2001, num=1 },
    },

    -- 收集图鉴：收集 100 个不同物品
    {
        id = 'collect_100',
        event_type = 'collect_item',
        target = 100,
        group = 'collection',
        condition = function(playerId, value, current, def)
            -- 同一物品只算一次
            local key = 'collected_' .. tostring(value)
            if PlayerData:get(playerId, key) then return false, 0 end
            PlayerData:set(playerId, key, true)
            return true, 1
        end,
    },

    -- 隐藏成就：暴击伤害 100w（达成才公开）
    {
        id = 'ach_crit_1m',
        event_type = 'damage_dealt',
        target = 1000000,
        group = 'achievement',
        hidden = true,
        condition = function(playerId, dmg_data, current, def)
            if not dmg_data.is_crit then return false, 0 end
            return true, dmg_data.value
        end,
    },
}
```

### 2. 实现 Adapter

```lua
local adapter = {
    db_load = function(playerId, id)
        return GamePlay.dbMgr.trophyDB:getTrophyConfig(playerId, id)
    end,

    db_save = function(playerId, id, data)
        GamePlay.dbMgr.trophyDB:saveTrophyConfig(playerId, id, data)
    end,

    grant_reward = function(playerId, reward, def)
        if reward.type == 'currency' then
            y3.player(playerId):addCurrency(reward.id, reward.num)
        elseif reward.type == 'item' then
            BagSystem:addItem(playerId, reward.id, reward.num)
        end
    end,

    on_unlock = function(playerId, def)
        UI:showMsgImportant({
            playerId = playerId,
            name = def.id,
            des = '解锁成就',
        })
    end,

    on_progress = function(playerId, def, current, target)
        UI:refreshProgressBar(def.id, current, target)
    end,
}
```

### 3. 启动并业务接入

```lua
local Tracker = include '.codemaker.templates.c-progress-tracker.logic'
MyGame.tracker = Tracker.setup(adapter, { defs = defs })

-- 业务事件触发
y3.game:event_on('单位-死亡', function(trg, data)
    if data.unit:isMonster() then
        MyGame.tracker:onEvent(playerId, 'kill_monster', 1)
        if data.unit:isBoss() then
            MyGame.tracker:onEvent(playerId, 'kill_boss', 1)
        end
    end
end)

-- 玩家登录
MyGame.tracker:onEvent(playerId, 'daily_login', 1)

-- 伤害事件（隐藏成就）
y3.game:event_on('伤害-结算后', function(trg, dmg)
    if dmg.target:isMonster() then
        MyGame.tracker:onEvent(playerId, 'damage_dealt', {
            value = dmg:getFinalValue(),
            is_crit = dmg:isCrit(),
        })
    end
end)
```

### 4. UI 列表展示

```lua
-- 成就面板
local achievements = MyGame.tracker:listByGroup(playerId, 'achievement')
for _, item in ipairs(achievements) do
    local p = item.progress
    print(string.format('%s: %d/%d (%.1f%%) %s',
        item.id, p.current, p.target, p.percent,
        p.unlocked and (p.claimed and '已领' or '可领') or '进行中'))
end

-- 每日任务列表
local dailies = MyGame.tracker:listByGroup(playerId, 'daily')

-- 领取奖励
local ok = MyGame.tracker:claim(playerId, 'daily_login')
```

### 5. GM 调试

```lua
-- 直接设置进度
MyGame.tracker:setProgress(playerId, 'ach_kill_1000', 999)

-- 重置某条
MyGame.tracker:reset(playerId, 'daily_login')

-- 重置整组（赛季归档）
MyGame.tracker:resetGroup(playerId, 'weekly')
```

---

## 与项目原型的对照

| 项目（TrophyMgr） | 模板（c-progress-tracker） |
|---|---|
| `addTrophyProg(playerId, id, prog, dirSet)` | `tracker:addProgress` / `setProgress` |
| `isUnlock` | `tracker:isUnlocked` |
| `getProg` | `tracker:getProgress.current` |
| `getQualityCountList` | `listByGroup` 后业务侧统计 |
| `recordSucc/recordFail` | 通过 `def.condition` 实现 |
| `activeBaseAttr`（解锁后加属性） | `def.unlock_cb` 内调用业务方法 |
| 跨日/周自动重置（daily/weekly DB） | `reset_type: 'daily' / 'weekly'` |
| 隐藏成就（notRelease） | `hidden=true` + `publish_at` |

---

## 限制

- 单条 def 只对应一个 event_type（多个事件类型驱动同一进度需写 `condition` 或拆多个 def 共享 reward）
- 不内置事件去重（同一事件被发多次 → 进度多次推进）；如需去重在 `condition` 内自行实现
- 多语言/动态文案不在模板内（`def.name/des` 由业务侧自行存）
- 不内置 UI 渲染，仅提供数据接口（配 `b-base-view` 自定义 UI）

---

## 验证记录

### v0.1.0 · 2026-06-01 · 波次塔防 Demo（agentmap）

**项目**：`maps/EntryMap/script/td_tracker_adapter.lua` + `td_config.lua`（7条进度定义）

| 测试点 | 结果 |
|---|---|
| `onEvent` 推进 + 达成自动解锁 | ✅ |
| `auto_reward=true` 自动发奖（gold） | ✅ |
| 多 def 同 event 同步推进（kill_monster → ach_kill_100 + daily_kill_30） | ✅ |
| `hidden=true` 未达成不出现在 listByGroup | ✅ |
| `setProgress` 后 hidden 成就公开 | ✅ |
| `claim` 手动领取 + 幂等（重复 false） | ✅ |
| `reset_type='daily'` 每日进度定义 | ✅ |
| 集成实跑：全程 277 秒无 Lua error | ✅ |
| 接入成本 | adapter ~45 行，defs 约 50 行 |

**已知接入注意事项**：
- `db_load/db_save` 为 mock 内存实现，生产时替换为 `y3.save_data` 即可
- 模板纯 Lua，无任何 Y3 引擎依赖，可单独 execute_lua 测试
