--- =========================================================================
--- Y3 功能模板 · logic.lua  (C 级 · 三层架构 DataSchema + Adapter + PureLogic)
--- =========================================================================
---
--- @template-id   c-wave-scheduler
--- @grade         C
--- @version       v0.1.0
--- @entry         M.setup(adapter, params)
--- @architecture  three-layer (DataSchema + Adapter + PureLogic)
--- @source        global_script/gamePlay/manager/monsterController/WaveController.lua
--- @description   时间轴关卡调度器：基于秒/帧的多类型事件混合调度。
---                 支持 4 大调度模式（一次性 / 周期 / 持续维量 / 阶段切换）。
---
--- 适用项目：塔防、Roguelike、守城、限时关卡、爬塔（任何"基于时间的怪物 / 道具
--- / 事件刷新"）。
---
--- 接入只需 3 步：
---   1. 按 §1 DataSchema 准备 schedule 配置（entries[]）
---   2. 实现 §2 Adapter 接口的 4 个核心方法（按用到的 entry kind 选择实现）
---   3. M.setup(adapter, params) → scheduler:onTick(seconds)
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 用户必须按此格式提供数据
-- ============================================================================

--- @class WaveEntry  时间轴单条配置
--- @field at         number    触发时间（秒）
--- @field kind       string    "oneshot" | "periodic" | "sustained" | "stage" | 自定义
--- @field id?        any       业务 ID（透传给 adapter，如怪物 id / 宝箱 id）
--- @field payload?   table     业务自定义数据（透传给 adapter）
--- @field interval?  number    [periodic] 周期秒数（kind=periodic 必填）
--- @field count?     integer   [periodic/oneshot] 单次触发数量（默认 1）
--- @field limit?     integer   [sustained] 目标维持数量
--- @field rate?      integer   [sustained] 单次最大补充数量（每 tick）
--- @field warn_lead? number    [stage] 阶段前 N 秒预警（默认 0=不预警）

--- @class WaveScheduleConfig
--- @field entries WaveEntry[]
--- @field warn_only_for_stage? boolean   仅 stage 类型触发预警（默认 true）

-- ============================================================================
-- §2. Adapter 接口 — 用户必须实现以下方法
-- ============================================================================

--- @class WaveAdapter
--- @field handle_oneshot?    fun(entry: WaveEntry, ctx: WaveContext)         一次性事件触发（boss/宝箱/最终BOSS）
--- @field handle_periodic?   fun(entry: WaveEntry, ctx: WaveContext)         周期触发（每 interval 秒）
--- @field handle_sustained?  fun(entry: WaveEntry, ctx: WaveContext): integer 维量补充。返回实际新增数量
--- @field handle_stage?      fun(entry: WaveEntry, ctx: WaveContext)         阶段切换（小 Boss 节点）
--- @field handle_warn?       fun(entry: WaveEntry, ctx: WaveContext)         阶段预警（提前 N 秒）
--- @field on_schedule_done?  fun()                                           全部 entries 已触发回调
--- @field on_error?          fun(err: string)                                异常回调（默认 print）

--- @class WaveContext  传给 adapter 的运行时上下文
--- @field current_time   number   当前秒数
--- @field current_stage  integer  当前已进入的阶段索引（0-based, 起始阶段=0）
--- @field active_count   integer  [sustained] 当前活跃实体数（由 adapter 上报，见 update_active_count）

-- ============================================================================
-- §3. Pure Logic — 模板内部实现
-- ============================================================================

local function validate(adapter, params)
    assert(type(adapter) == 'table', 'c-wave-scheduler: adapter required')
    assert(type(params) == 'table', 'c-wave-scheduler: params required')
    assert(type(params.entries) == 'table', 'c-wave-scheduler: params.entries required')
    for i, entry in ipairs(params.entries) do
        assert(type(entry.at) == 'number', 'c-wave-scheduler: entry[' .. i .. '].at must be number')
        assert(type(entry.kind) == 'string', 'c-wave-scheduler: entry[' .. i .. '].kind must be string')
        if entry.kind == 'periodic' then
            assert(type(entry.interval) == 'number' and entry.interval > 0,
                'c-wave-scheduler: entry[' .. i .. '].interval required for periodic')
        end
        if entry.kind == 'sustained' then
            assert(type(entry.limit) == 'integer' or type(entry.limit) == 'number',
                'c-wave-scheduler: entry[' .. i .. '].limit required for sustained')
        end
    end
end

--- 创建调度器
---@param adapter WaveAdapter
---@param params WaveScheduleConfig
---@return table
function M.setup(adapter, params)
    validate(adapter, params)

    local on_error = adapter.on_error or print

    -- 按 kind 拆分 entries 并按 at 排序
    local oneshots = {}      ---@type WaveEntry[]
    local periodics = {}     ---@type WaveEntry[]
    local sustaineds = {}    ---@type WaveEntry[]
    local stages = {}        ---@type WaveEntry[]
    local custom_entries = {} ---@type WaveEntry[]
    local entries = params.entries

    for _, entry in ipairs(entries) do
        if entry.kind == 'oneshot' then
            oneshots[#oneshots + 1] = entry
        elseif entry.kind == 'periodic' then
            periodics[#periodics + 1] = entry
        elseif entry.kind == 'sustained' then
            sustaineds[#sustaineds + 1] = entry
        elseif entry.kind == 'stage' then
            stages[#stages + 1] = entry
        else
            custom_entries[#custom_entries + 1] = entry
        end
    end

    table.sort(oneshots, function(a, b) return a.at < b.at end)
    table.sort(stages, function(a, b) return a.at < b.at end)

    -- 内部状态
    local oneshot_idx = 1   -- 下一个待触发 oneshot 在 oneshots[oneshot_idx]
    local stage_idx = 0     -- 当前已进入的阶段索引（0=未开始）
    local stage_warned = {} -- 已预警的 stage entries
    local active_counts = {} ---@type table<WaveEntry, integer>  sustained 类型的当前活跃数
    local last_periodic_fire = {} ---@type table<WaveEntry, number>  上次触发时间
    local schedule_done = false

    local instance = {}

    --- 安全调用 handler
    local function safe_call(fn, entry, ctx)
        if not fn then return end
        local ok, err_or_ret = xpcall(fn, debug.traceback, entry, ctx)
        if not ok then on_error(err_or_ret) end
        return err_or_ret
    end

    --- 构造上下文
    local function make_ctx(current_time, sustained_entry)
        return {
            current_time = current_time,
            current_stage = stage_idx,
            active_count = sustained_entry and (active_counts[sustained_entry] or 0) or 0,
        }
    end

    --- 主调度入口（外部每秒/每帧调用一次）
    ---@param current_time number 当前时间（秒）
    function instance:onTick(current_time)
        -- 1. 处理 oneshot：到点即触发
        while oneshot_idx <= #oneshots do
            local entry = oneshots[oneshot_idx]
            if current_time >= entry.at then
                local ctx = make_ctx(current_time)
                local count = entry.count or 1
                for _ = 1, count do
                    safe_call(adapter.handle_oneshot, entry, ctx)
                end
                oneshot_idx = oneshot_idx + 1
            else
                break
            end
        end

        -- 2. 处理 stage：到点切换 + 阶段事件
        for i = stage_idx + 1, #stages do
            local entry = stages[i]
            -- 预警（提前 warn_lead 秒）
            if entry.warn_lead and entry.warn_lead > 0 and not stage_warned[entry] then
                if current_time >= entry.at - entry.warn_lead then
                    stage_warned[entry] = true
                    safe_call(adapter.handle_warn, entry, make_ctx(current_time))
                end
            end
            -- 进入阶段
            if current_time >= entry.at then
                stage_idx = i
                safe_call(adapter.handle_stage, entry, make_ctx(current_time))
            else
                break
            end
        end

        -- 3. 处理 periodic：每 interval 秒触发；entry.at 为生效起始时间
        for _, entry in ipairs(periodics) do
            if current_time >= entry.at then
                local last = last_periodic_fire[entry] or (entry.at - entry.interval)
                if current_time - last >= entry.interval then
                    last_periodic_fire[entry] = current_time
                    local ctx = make_ctx(current_time)
                    local count = entry.count or 1
                    for _ = 1, count do
                        safe_call(adapter.handle_periodic, entry, ctx)
                    end
                end
            end
        end

        -- 4. 处理 sustained：维持目标数量，按 rate 补充
        for _, entry in ipairs(sustaineds) do
            if current_time >= entry.at then
                local active = active_counts[entry] or 0
                local need = math.max(entry.limit - active, 0)
                local rate = entry.rate or need
                local to_add = math.min(need, rate)
                if to_add > 0 then
                    local ctx = make_ctx(current_time, entry)
                    -- 每个 sustained entry 调用一次，由 adapter 内部完成 to_add 个补充
                    -- 这里循环调用以让 adapter 简单实现单个补充
                    local total_added = 0
                    for _ = 1, to_add do
                        local added = safe_call(adapter.handle_sustained, entry, ctx)
                        total_added = total_added + (tonumber(added) or 1)
                    end
                    active_counts[entry] = active + total_added
                end
            end
        end

        -- 5. 处理 custom：全部交给 adapter
        if #custom_entries > 0 and adapter.handle_custom then
            for _, entry in ipairs(custom_entries) do
                if current_time >= entry.at then
                    safe_call(adapter.handle_custom, entry, make_ctx(current_time))
                end
            end
        end

        -- 6. 检查是否完成
        if not schedule_done then
            local all_done = oneshot_idx > #oneshots and stage_idx >= #stages
            if all_done and adapter.on_schedule_done then
                schedule_done = true
                safe_call(function() adapter.on_schedule_done() end, nil, make_ctx(current_time))
            end
        end
    end

    --- 上报某 sustained entry 的活跃数变化（怪物死亡时调用 -1）
    ---@param entry WaveEntry
    ---@param delta integer
    function instance:updateActiveCount(entry, delta)
        active_counts[entry] = math.max((active_counts[entry] or 0) + delta, 0)
    end

    --- 直接设置某 sustained entry 的活跃数
    ---@param entry WaveEntry
    ---@param value integer
    function instance:setActiveCount(entry, value)
        active_counts[entry] = math.max(value, 0)
    end

    --- 获取当前阶段索引（0-based, 0=未进入第一个阶段）
    ---@return integer
    function instance:getCurrentStage()
        return stage_idx
    end

    --- 获取下一个阶段时间（用于 UI 倒计时）
    ---@return number|nil
    function instance:getNextStageTime()
        local next_entry = stages[stage_idx + 1]
        return next_entry and next_entry.at or nil
    end

    --- 获取下一个阶段标题
    ---@return string|nil
    function instance:getNextStageTitle()
        local next_entry = stages[stage_idx + 1]
        return next_entry and (next_entry.payload and next_entry.payload.title) or nil
    end

    --- 跳到指定阶段（GM 调试）
    ---@param target_stage integer 目标阶段索引（1-based，因为 0 表示未开始）
    ---@param current_time number 当前时间，用于 ctx
    function instance:jumpToStage(target_stage, current_time)
        target_stage = math.min(target_stage, #stages)
        for i = stage_idx + 1, target_stage do
            stage_idx = i
            safe_call(adapter.handle_stage, stages[i], make_ctx(current_time))
        end
    end

    --- 重置调度器（清局重开）
    function instance:reset()
        oneshot_idx = 1
        stage_idx = 0
        stage_warned = {}
        active_counts = {}
        last_periodic_fire = {}
        schedule_done = false
    end

    --- 列出所有 entries（调试用）
    ---@return table
    function instance:dump()
        return {
            oneshots = oneshots,
            periodics = periodics,
            sustaineds = sustaineds,
            stages = stages,
            custom = custom_entries,
            current_stage = stage_idx,
        }
    end

    return instance
end

return M
