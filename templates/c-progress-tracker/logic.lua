--- =========================================================================
--- Y3 功能模板 · logic.lua  (C 级 · 三层架构 DataSchema + Adapter + PureLogic)
--- =========================================================================
---
--- @template-id   c-progress-tracker
--- @grade         C
--- @version       v0.1.0
--- @entry         M.setup(adapter, params)
--- @architecture  three-layer (DataSchema + Adapter + PureLogic)
--- @source        global_script/gamePlay/manager/TrophyMgr.lua
--- @description   通用进度追踪框架：成就 / 任务 / 收集 / 称号解锁条件统一管理。
---                 事件驱动进度推进 → 自动检测达成 → 解锁回调 → 奖励发放。
---
--- 适用场景：
---   • 成就系统（按完成度解锁）
---   • 任务系统（每日/每周/主线，配 daily_reset / weekly_reset）
---   • 收集图鉴（怪物/物品收集进度）
---   • 称号解锁条件
---   • 引导任务进度
---
--- 接入只需 4 步：
---   1. 按 §1 DataSchema 准备 definitions
---   2. 实现 §2 Adapter 接口的 4 个核心方法（DB读写 + 奖励发放）
---   3. M.setup(adapter, params) → tracker
---   4. 业务侧调用 tracker:onEvent(playerId, event_type, value)
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 用户必须按此格式提供数据
-- ============================================================================

--- @class ProgressDef  单条进度定义
--- @field id          any        唯一 ID（成就 ID / 任务 ID / 收集 ID）
--- @field event_type  string     业务事件类型（如 "kill_boss" / "collect_item" / "play_time"）
--- @field target      number     达成目标值
--- @field reward?     any        奖励数据（透传给 adapter.grant_reward）
--- @field group?      string     分组（"daily" / "weekly" / "main" / "achievement" 等）
--- @field reset_type? string     "none" / "daily" / "weekly" / "manual"（默认 none）
--- @field condition?  fun(playerId:any, value:any, current:number, def:ProgressDef): boolean, number
---                               自定义条件检查（可选）。返回 (是否计入, 增量)。默认按 value=数值累加
--- @field auto_reward? boolean   达成时是否自动发奖（默认 false，需手动 claim）
--- @field unlock_cb?  fun(playerId, def)  解锁瞬间回调（如属性激励）
--- @field hidden?     boolean    是否隐藏（不返回到列表中，达成后才公开）
--- @field publish_at? number     何时公开（时间戳）

--- @class ProgressData  存档中的进度数据
--- @field current   number    当前进度（0~target）
--- @field unlocked  boolean   是否已达成
--- @field claimed   boolean   是否已领取奖励
--- @field unlock_ts? number   达成时间戳
--- @field reset_ts?  number   上次重置时间戳

--- @class ProgressTrackerParams
--- @field defs ProgressDef[]   定义列表
--- @field get_time? fun(): number  时间戳源（默认 os.time）

-- ============================================================================
-- §2. Adapter 接口 — 用户必须实现以下方法
-- ============================================================================

--- @class ProgressAdapter
--- @field db_load        fun(playerId:any, id:any): ProgressData|nil    加载玩家某条进度
--- @field db_save        fun(playerId:any, id:any, data: ProgressData)  保存玩家某条进度
--- @field grant_reward?  fun(playerId:any, reward:any, def:ProgressDef) 发放奖励（可选，配合 auto_reward 或 claim）
--- @field on_unlock?     fun(playerId:any, def:ProgressDef)             解锁广播（如全局通知/UI 提示）
--- @field on_progress?   fun(playerId:any, def:ProgressDef, current:number, target:number)  进度变化广播
--- @field on_error?      fun(err:string)                                异常回调

-- ============================================================================
-- §3. Pure Logic — 模板内部实现
-- ============================================================================

local function validate(adapter, params)
    assert(type(adapter) == 'table', 'c-progress-tracker: adapter required')
    assert(type(adapter.db_load) == 'function', 'c-progress-tracker: adapter.db_load required')
    assert(type(adapter.db_save) == 'function', 'c-progress-tracker: adapter.db_save required')
    assert(type(params) == 'table', 'c-progress-tracker: params required')
    assert(type(params.defs) == 'table', 'c-progress-tracker: params.defs required')
end

local function default_get_time()
    return os.time()
end

--- 计算两个时间戳是否跨日（UTC+8）
local function is_cross_day(t1, t2)
    if not t1 or not t2 then return true end
    local off = 8 * 3600
    return os.date('!%Y-%m-%d', t1 + off) ~= os.date('!%Y-%m-%d', t2 + off)
end

--- 计算两个时间戳是否跨周
local function is_cross_week(t1, t2)
    if not t1 or not t2 then return true end
    local off = 8 * 3600
    return os.date('!%Y-%W', t1 + off) ~= os.date('!%Y-%W', t2 + off)
end

--- 创建追踪器
---@param adapter ProgressAdapter
---@param params ProgressTrackerParams
---@return table
function M.setup(adapter, params)
    validate(adapter, params)

    local get_time = params.get_time or default_get_time
    local on_error = adapter.on_error or print

    -- 索引：id → def
    local def_by_id = {}
    -- 索引：event_type → defs
    local defs_by_event = {}
    -- 索引：group → defs
    local defs_by_group = {}

    for _, def in ipairs(params.defs) do
        assert(def.id ~= nil, 'c-progress-tracker: def.id required')
        assert(type(def.event_type) == 'string' or def.condition,
            'c-progress-tracker: def.event_type or def.condition required for ' .. tostring(def.id))

        def_by_id[def.id] = def

        if def.event_type then
            defs_by_event[def.event_type] = defs_by_event[def.event_type] or {}
            table.insert(defs_by_event[def.event_type], def)
        end

        local g = def.group or 'default'
        defs_by_group[g] = defs_by_group[g] or {}
        table.insert(defs_by_group[g], def)
    end

    --- 安全包装
    local function safe_call(fn, ...)
        if not fn then return end
        local ok, err = xpcall(fn, debug.traceback, ...)
        if not ok then on_error(err) end
    end

    --- 创建默认进度数据
    local function default_data()
        return { current = 0, unlocked = false, claimed = false, unlock_ts = nil, reset_ts = get_time() }
    end

    --- 加载并自动重置（按 reset_type）
    ---@param playerId any
    ---@param def ProgressDef
    ---@return ProgressData
    local function load_with_reset(playerId, def)
        local data = adapter.db_load(playerId, def.id)
        if not data then
            data = default_data()
            return data
        end

        -- 自动重置
        local now = get_time()
        if def.reset_type == 'daily' and is_cross_day(data.reset_ts, now) then
            data.current = 0
            data.unlocked = false
            data.claimed = false
            data.unlock_ts = nil
            data.reset_ts = now
            adapter.db_save(playerId, def.id, data)
        elseif def.reset_type == 'weekly' and is_cross_week(data.reset_ts, now) then
            data.current = 0
            data.unlocked = false
            data.claimed = false
            data.unlock_ts = nil
            data.reset_ts = now
            adapter.db_save(playerId, def.id, data)
        end

        return data
    end

    local instance = {}

    --- 业务事件触发：推进所有匹配该 event_type 的进度
    ---@param playerId any
    ---@param event_type string
    ---@param value? any 业务值（默认 1）
    function instance:onEvent(playerId, event_type, value)
        local defs = defs_by_event[event_type]
        if not defs then return end

        for _, def in ipairs(defs) do
            local data = load_with_reset(playerId, def)
            if data.unlocked then goto continue end

            -- 计算增量
            local should_count, delta
            if def.condition then
                should_count, delta = def.condition(playerId, value, data.current, def)
                if not should_count then goto continue end
            else
                delta = tonumber(value) or 1
            end

            local new_current = math.min(data.current + delta, def.target)
            data.current = new_current

            safe_call(adapter.on_progress, playerId, def, new_current, def.target)

            -- 检查达成
            if new_current >= def.target then
                data.unlocked = true
                data.unlock_ts = get_time()
                safe_call(def.unlock_cb, playerId, def)
                safe_call(adapter.on_unlock, playerId, def)

                -- 自动发奖
                if def.auto_reward and adapter.grant_reward then
                    safe_call(adapter.grant_reward, playerId, def.reward, def)
                    data.claimed = true
                end
            end

            adapter.db_save(playerId, def.id, data)

            ::continue::
        end
    end

    --- 直接设置进度（覆盖式，用于配置同步/GM 调试）
    ---@param playerId any
    ---@param id any
    ---@param current number
    function instance:setProgress(playerId, id, current)
        local def = def_by_id[id]
        if not def then return end

        local data = load_with_reset(playerId, def)
        if data.unlocked then return end

        data.current = math.min(current, def.target)
        if data.current >= def.target then
            data.unlocked = true
            data.unlock_ts = get_time()
            safe_call(def.unlock_cb, playerId, def)
            safe_call(adapter.on_unlock, playerId, def)
            if def.auto_reward and adapter.grant_reward then
                safe_call(adapter.grant_reward, playerId, def.reward, def)
                data.claimed = true
            end
        end
        adapter.db_save(playerId, def.id, data)
    end

    --- 增加进度（指定 id 直接 +n）
    function instance:addProgress(playerId, id, delta)
        local def = def_by_id[id]
        if not def then return end
        local data = load_with_reset(playerId, def)
        instance:setProgress(playerId, id, data.current + (delta or 1))
    end

    --- 是否已达成
    ---@param playerId any
    ---@param id any
    ---@return boolean
    function instance:isUnlocked(playerId, id)
        local def = def_by_id[id]
        if not def then return false end
        local data = load_with_reset(playerId, def)
        return data.unlocked
    end

    --- 获取进度信息
    ---@param playerId any
    ---@param id any
    ---@return { current: number, target: number, percent: number, unlocked: boolean, claimed: boolean }|nil
    function instance:getProgress(playerId, id)
        local def = def_by_id[id]
        if not def then return nil end
        local data = load_with_reset(playerId, def)
        return {
            current = data.current,
            target = def.target,
            percent = math.min(data.current / def.target * 100, 100),
            unlocked = data.unlocked,
            claimed = data.claimed,
            unlock_ts = data.unlock_ts,
        }
    end

    --- 领取奖励（需已达成 + 未领取 + adapter.grant_reward 已实现）
    ---@param playerId any
    ---@param id any
    ---@return boolean ok 是否领取成功
    function instance:claim(playerId, id)
        local def = def_by_id[id]
        if not def then return false end
        local data = load_with_reset(playerId, def)
        if not data.unlocked or data.claimed then return false end
        if not adapter.grant_reward then return false end

        safe_call(adapter.grant_reward, playerId, def.reward, def)
        data.claimed = true
        adapter.db_save(playerId, def.id, data)
        return true
    end

    --- 列出某 group 的所有进度（用于 UI 列表展示）
    ---@param playerId any
    ---@param group? string
    ---@return { id: any, def: ProgressDef, progress: table }[]
    function instance:listByGroup(playerId, group)
        local g = group or 'default'
        local defs = defs_by_group[g]
        if not defs then return {} end

        local now = get_time()
        local result = {}
        for _, def in ipairs(defs) do
            -- 隐藏成就：未达成且 publish_at 未到 → 不显示
            if def.hidden then
                local data = load_with_reset(playerId, def)
                if not data.unlocked and (not def.publish_at or now < def.publish_at) then
                    goto continue
                end
            end
            result[#result + 1] = {
                id = def.id,
                def = def,
                progress = instance:getProgress(playerId, def.id),
            }
            ::continue::
        end
        return result
    end

    --- 强制重置某条进度（GM / 跨期归档用）
    function instance:reset(playerId, id)
        local def = def_by_id[id]
        if not def then return end
        local data = default_data()
        adapter.db_save(playerId, def.id, data)
    end

    --- 强制重置某 group 的所有进度
    function instance:resetGroup(playerId, group)
        local defs = defs_by_group[group]
        if not defs then return end
        for _, def in ipairs(defs) do
            instance:reset(playerId, def.id)
        end
    end

    --- 获取定义（用于业务侧查阅元数据）
    function instance:getDef(id)
        return def_by_id[id]
    end

    --- 列出所有 group 名
    function instance:listGroups()
        local groups = {}
        for g in pairs(defs_by_group) do groups[#groups + 1] = g end
        return groups
    end

    return instance
end

return M
