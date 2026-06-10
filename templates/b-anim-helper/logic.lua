--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   b-anim-helper
--- @version       v0.1.0
--- @entry         M.setup(params) → AnimHelper 实例
--- @params        add_frame_update, game_run_time, cast_event
--- @source        global_script/gamePlay/utils/AnimHelper.lua
--- @description   单位动画播放 + 帧时刻事件回调 + 施法停止自动清理。
---
--- 融合契约：
---   1. 依赖 GameTimer 的帧回调
---   2. 依赖施法事件（游戏-施法-结束/停止）自动清理
---   3. playAnim 返回的 PlayEvent 包含 unitId + 帧时刻回调表
--- =========================================================================

local M = {}

---@class AnimHelperParams
---@field add_frame_update fun(func: fun()) 帧回调注册（GameTimer:addFrameUpdateFunc）
---@field game_run_time? fun(): number 当前游戏时间（y3.game.current_game_run_time）
---@field cast_stop_events? table 施法停止事件列表（用于注册自动清理）

--- 创建动画助手
---@param params AnimHelperParams
---@return table
function M.setup(params)
    assert(type(params) == 'table', 'b-anim-helper: params must be a table')
    assert(type(params.add_frame_update) == 'function', 'b-anim-helper: add_frame_update required')

    local add_frame_update = params.add_frame_update
    local game_run_time = params.game_run_time or function() return 0 end
    local cast_stop_events = params.cast_stop_events or {}

    local event_id_counter = 1
    local play_event_list = {} ---@type table<integer, table>
    local triggers = {} ---@type table

    --- 帧更新：检查所有 playEvent 的回调时间
    local function update()
        local current_time = game_run_time()
        for unit_id, play_event in pairs(play_event_list) do
            if play_event.event_param then
                local to_remove = {}
                for trigger_time, cb in pairs(play_event.event_param) do
                    if current_time >= trigger_time then
                        if cb then cb() end
                        to_remove[trigger_time] = true
                    end
                end
                for t in pairs(to_remove) do
                    play_event.event_param[t] = nil
                end
            end
        end
    end

    --- 注册帧更新和清理事件
    local function start()
        add_frame_update(update)
        for _, evt_cfg in ipairs(cast_stop_events) do
            local trg = evt_cfg.event:event(evt_cfg.event_name, on_cast_stop)
            table.insert(triggers, trg)
        end
    end

    --- 施法停止回调：清除对应 unit 的 playEvent
    local function on_cast_stop(trg, data)
        local unit_id = data.unit:get_id()
        if play_event_list[unit_id] then
            play_event_list[unit_id] = nil
        end
    end

    ---@class PlayAnimOptions
    ---@field anim_name string 动画名（必填）
    ---@field speed? number 播放速度（默认 1）
    ---@field start_time? number 动画开始时间（默认 0）
    ---@field end_time? number 动画结束时间（默认 -1）
    ---@field loop? boolean 是否循环（默认 false）
    ---@field back_normal? boolean 是否返回默认状态（默认 true）
    ---@field events? table<number, fun()> 帧时刻→回调映射

    --- 播放动画并注册帧事件回调
    ---@param unit Unit
    ---@param options PlayAnimOptions
    ---@return table playEvent 包含 unitId + eventParam
    local function play_anim(unit, options)
        if not unit or not options or not options.anim_name then return nil end

        local speed = options.speed or 1
        local begin_time = game_run_time()
        local unit_id = unit:get_id()

        -- 构建帧事件回调表
        local event_param = {}
        if options.events then
            for evt_time, cb in pairs(options.events) do
                local trigger_time = begin_time + evt_time / speed
                event_param[trigger_time] = cb
            end
        end

        local play_event = {
            id = event_id_counter,
            unit_id = unit_id,
            event_param = event_param,
        }
        event_id_counter = event_id_counter + 1
        play_event_list[unit_id] = play_event

        -- 播放动画
        unit:play_animation(
            options.anim_name,
            speed,
            options.start_time or 0,
            options.end_time or -1,
            options.loop or false,
            options.back_normal ~= false
        )

        return play_event
    end

    --- 手动停止某单位的 playEvent
    ---@param unit Unit
    local function stop(unit)
        if unit then
            play_event_list[unit:get_id()] = nil
        end
    end

    --- 清理所有
    local function clear()
        play_event_list = {}
        for _, trg in ipairs(triggers) do
            if trg.remove then trg:remove() end
        end
        triggers = {}
    end

    local instance = {
        start = start,
        playAnim = play_anim,
        stop = stop,
        clear = clear,
    }

    return instance
end

return M
