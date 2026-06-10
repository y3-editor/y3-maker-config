--- =========================================================================
--- Y3 功能模板 · difficulty-select · 多人同步版
--- =========================================================================
--- @template-id   difficulty-select
--- @version       v0.3.0
--- @entry         M.setup(params)
--- @description   房主权威模式/难度选择 + 多数准备投票 + 同步倒计时进入游戏
---
--- 多人契约：
---   1. UI 本地点击只发送 y3.sync 请求；权威状态只在 onSync handler 中变更。
---   2. 模式/难度仅房主可改；非房主点击会被同步 handler 拒绝并输出诊断日志。
---   3. 单人按钮显示“开始游戏”；多人按钮显示“准备(x/n)”。
---   4. 多人开始为多数准备投票：floor(real_online_count / 2) + 1。
---   5. 多数准备后先倒计时；倒计时到 0 才触发 StartGame/GameEnter 并关闭面板。
---   6. 当前在线真实玩家使用 Player:is_alive()，等价 PLAYING + USER。
---   7. StartGame / GameEnter 事件携带 mode_key, mode_name, config_id, sub。
--- =========================================================================

local M = {}

local SYNC_MODE_SELECT = 'difficulty_select.mode_select'
local SYNC_READY_VOTE = 'difficulty_select.ready_vote'

local LEVEL_CMP_PREFAB_NAME = 'MenuStartLevelCmp'

local params = {
    -- levels            = nil, -- table, 必填，默认模式关卡配置
    -- modes             = nil, -- table, 可选，模式配置 { [key] = { key, name, levels, player_records } }
    -- host_player_id    = nil,
    -- countdown_seconds = 5,
    -- fsm_game_class    = nil,
    -- fsm_stage_class   = nil,
    -- player_records    = nil,
    -- mode_key          = nil,
    -- mode_name         = nil,
    -- ui_paths          = nil, -- table, 必填，panel / level_list / start_btn；多人列表需 player_list
}

local state = {
    open_levels = {},
    select_id = nil,
    is_start = false,
    listeners = {},
    level_prefabs_by_player = {},
    start_btn_bound_by_player = {},
    ready_votes = {},
    sync_bound = false,
    initialized = false,
}

-- =========================================================================
-- 通用工具
-- =========================================================================

local function tpl_log(message)
    print('[difficulty-select] ' .. tostring(message))
end

local function tpl_safe_get_ui(player, path)
    if not player or not path then
        return nil
    end
    local ok, ui = pcall(y3.ui.get_ui, player, path)
    if ok then
        return ui
    end
    return nil
end

local function tpl_get_host_player()
    return y3.player.get_by_id(params.host_player_id)
end

local function tpl_is_host(player)
    return player and player:get_id() == params.host_player_id
end

local function tpl_compute_open_max(levels)
    local last_id = 0
    for _, info in ipairs(levels or {}) do
        if info.open == 1 then
            return info.id - 1
        end
        last_id = info.id
    end
    return last_id
end

local function tpl_collect_open_levels(levels)
    local open_max = tpl_compute_open_max(levels)
    local list = {}
    for _, info in ipairs(levels or {}) do
        if info.id <= open_max then
            table.insert(list, info.id)
        end
    end
    return list
end

local function tpl_config_id_to_sub(open_levels, config_id)
    for sub, id in ipairs(open_levels or {}) do
        if id == config_id then
            return sub
        end
    end
    return nil
end

local function tpl_find_level(levels, config_id)
    for _, info in ipairs(levels or {}) do
        if info.id == config_id then
            return info
        end
    end
    return nil
end

local function tpl_is_level_unlocked(records, config_id, open_levels)
    local sub = tpl_config_id_to_sub(open_levels, config_id)
    if not sub then
        return false
    end
    if sub <= 1 then
        return true
    end
    return (records[sub - 1] or 0) > 0
end

local function tpl_get_mode_config(mode_key)
    local modes = params.modes
    if not modes then
        return nil
    end
    if modes[mode_key] then
        return modes[mode_key]
    end
    for _, mode in pairs(modes) do
        if mode.key == mode_key then
            return mode
        end
    end
    return nil
end

local function tpl_get_real_players()
    local list = {}
    for player in y3.player_group.get_all_players():pairs() do
        if player and player:is_alive() then
            table.insert(list, player)
        end
    end
    return list
end

local function tpl_get_render_players()
    local list = tpl_get_real_players()
    if #list > 0 then
        return list
    end

    -- 编辑器/单人早期初始化阶段可能暂时没有 PLAYING + USER；至少渲染房主 UI，避免模板不可见。
    local host = tpl_get_host_player()
    if host then
        return { host }
    end
    return {}
end

local function tpl_majority_threshold(total)
    if total <= 0 then
        return 0
    end
    return math.floor(total / 2) + 1
end

local function tpl_get_selected_payload()
    local sub = tpl_config_id_to_sub(state.open_levels, state.select_id) or 1
    local info = tpl_find_level(params.levels, state.select_id)
    return {
        sub = sub,
        config_id = state.select_id,
        name = info and info.name or ('Lv.' .. tostring(state.select_id)),
        info = info and info.info or '',
        des = info and info.des or '',
        mode_key = params.mode_key or '',
        mode_name = params.mode_name or '',
    }
end

local function tpl_emit(event_name, data)
    local cbs = state.listeners[event_name]
    if not cbs then
        return
    end
    for _, cb in ipairs(cbs) do
        cb(data)
    end
end

local function tpl_set_level_selected_style(ui, is_selected)
    local title_text = ui and ui:get_child('title_TEXT')
    if title_text then
        if is_selected then
            title_text:set_text_color(255, 226, 96, 255)
        else
            title_text:set_text_color(255, 255, 255, 255)
        end
    end
end

-- =========================================================================
-- 玩家列表 / 投票
-- =========================================================================

local function tpl_ready_summary()
    local players = tpl_get_real_players()
    local ready = 0
    local real_ids = {}
    for _, player in ipairs(players) do
        local id = player:get_id()
        real_ids[id] = true
        if state.ready_votes[id] then
            ready = ready + 1
        end
    end

    -- 清理已经离线/不再 PLAYING+USER 的旧投票。
    for id in pairs(state.ready_votes) do
        if not real_ids[id] then
            state.ready_votes[id] = nil
        end
    end

    return {
        ready = ready,
        total = #players,
        threshold = tpl_majority_threshold(#players),
        players = players,
    }
end

local function tpl_get_start_button_text(summary)
    summary = summary or tpl_ready_summary()
    if summary.total <= 1 then
        return '开始游戏'
    end
    return ('准备(%d/%d)'):format(summary.ready, summary.total)
end

local function tpl_set_start_button_text(player, text)
    local start_btn = tpl_safe_get_ui(player, params.ui_paths and params.ui_paths.start_btn)
    if not start_btn then
        return
    end

    local title_text = start_btn:get_child('title_TEXT')
    if title_text then
        title_text:set_text(text)
    else
        start_btn:set_text(text)
    end
end

function M.refreshPlayerListUI()
    local players = tpl_get_real_players()
    local render_players = tpl_get_render_players()
    local player_list_path = params.ui_paths and params.ui_paths.player_list
    if not player_list_path then
        return
    end

    for _, ui_owner in ipairs(render_players) do
        for row = 1, 4 do
            local row_ui = tpl_safe_get_ui(ui_owner, player_list_path .. '.' .. tostring(row))
            if row_ui then
                local player = players[row]
                row_ui:set_visible(player ~= nil)
                if player then
                    local name_text = row_ui:get_child('title_TEXT')
                    if name_text then
                        local player_name = player:get_name()
                        if player_name == '' then
                            player_name = '玩家' .. tostring(player:get_id())
                        end
                        name_text:set_text(player_name)
                    end

                    local state_text = row_ui:get_child('state_TEXT')
                    if state_text then
                        local ready_text = state.ready_votes[player:get_id()] and '已准备' or '未准备'
                        if tpl_is_host(player) then
                            ready_text = '房主/' .. ready_text
                        end
                        state_text:set_text(ready_text)
                    end

                    local avatar = row_ui:get_child('avatar')
                    local host = avatar and avatar:get_child('host')
                    if host then
                        host:set_visible(tpl_is_host(player))
                    end
                end
            end
        end
    end
end

function M.getReadySummary()
    local summary = tpl_ready_summary()
    return {
        ready = summary.ready,
        total = summary.total,
        threshold = summary.threshold,
        started = state.is_start,
        button_text = tpl_get_start_button_text(summary),
    }
end

function M.refreshStartButtonUI()
    local summary = tpl_ready_summary()
    local text = tpl_get_start_button_text(summary)
    for _, player in ipairs(tpl_get_render_players()) do
        tpl_set_start_button_text(player, text)
    end
end

function M.getStartButtonText()
    return tpl_get_start_button_text(tpl_ready_summary())
end


-- =========================================================================
-- 权威状态变更
-- =========================================================================

local function tpl_apply_mode_selection(mode_key, config_id, reason, mode_name)
    if state.is_start then
        tpl_log('ignore mode select after start')
        return false
    end

    local mode = tpl_get_mode_config(mode_key)
    if mode then
        params.mode_key = mode.key or mode_key or ''
        params.mode_name = mode.name or params.mode_key
        params.levels = mode.levels or params.levels
        params.player_records = mode.player_records or params.player_records or {}
    else
        params.mode_key = mode_key or params.mode_key or ''
        params.mode_name = mode_name or params.mode_name or params.mode_key
    end

    state.open_levels = tpl_collect_open_levels(params.levels)
    local target_id = config_id or state.select_id or state.open_levels[1]
    if not tpl_is_level_unlocked(params.player_records, target_id, state.open_levels) then
        target_id = state.open_levels[1]
    end
    state.select_id = target_id or 1

    M.createLevelUI()

    tpl_emit('LevelsChanged', {
        count = #state.open_levels,
        first_config_id = state.select_id,
        mode_key = params.mode_key,
        mode_name = params.mode_name,
        reason = reason,
    })
    tpl_emit('LevelSelected', tpl_get_selected_payload())
    return true
end

function M.selectLevel(config_id)
    -- 兼容旧调用名：公开选择入口只发送同步请求；权威状态由 onSync handler 应用。
    return M.requestSelectLevel(config_id)
end

local function tpl_set_countdown_button_text(remaining)
    for _, player in ipairs(tpl_get_render_players()) do
        tpl_set_start_button_text(player, ('倒计时(%d)'):format(remaining))
    end
end

local function tpl_finish_countdown(payload)
    for _, player in ipairs(tpl_get_render_players()) do
        local panel = tpl_safe_get_ui(player, params.ui_paths.panel)
        if panel then
            panel:set_visible(false)
        end
    end

    tpl_emit('StartGame', payload)
    tpl_emit('GameEnter', {
        sub = payload.sub,
        config_id = payload.config_id,
        name = payload.name,
        fsm_game_class = params.fsm_game_class,
        fsm_stage_class = params.fsm_stage_class,
        mode_key = payload.mode_key,
        mode_name = payload.mode_name,
    })
end

local function tpl_start_countdown(reason)
    if state.is_start then
        return false, '游戏已经开始'
    end

    local summary = tpl_ready_summary()
    if summary.total <= 0 then
        tpl_log('start blocked: no real online players')
        return false, '没有在线真实玩家'
    end
    if summary.ready < summary.threshold then
        return false, '准备人数不足'
    end

    -- 多数准备只进入倒计时阶段；真正 StartGame/GameEnter 必须等倒计时结束。
    state.is_start = true
    local payload = tpl_get_selected_payload()
    payload.reason = reason
    payload.ready = summary.ready
    payload.total = summary.total
    payload.threshold = summary.threshold

    local seconds = params.countdown_seconds or 5
    tpl_set_countdown_button_text(seconds)
    tpl_emit('Countdown', {
        remaining = seconds,
        total = seconds,
        mode_key = payload.mode_key,
        mode_name = payload.mode_name,
        config_id = payload.config_id,
        sub = payload.sub,
    })

    y3.timer.count_loop(1, seconds, function(timer, count)
        local remaining = seconds - count
        tpl_set_countdown_button_text(remaining)
        tpl_emit('Countdown', {
            remaining = remaining,
            total = seconds,
            mode_key = payload.mode_key,
            mode_name = payload.mode_name,
            config_id = payload.config_id,
            sub = payload.sub,
        })

        if count == seconds then
            tpl_finish_countdown(payload)
        end
    end)

    return true, nil
end

local function tpl_apply_ready_vote(player, ready)
    if state.is_start then
        return false, '游戏已经开始'
    end
    if not player or not player:is_alive() then
        tpl_log('ignore ready vote from non-real player')
        return false, '非在线真实玩家'
    end

    local player_id = player:get_id()
    state.ready_votes[player_id] = (ready ~= false)

    local summary = tpl_ready_summary()
    tpl_emit('ReadyChanged', {
        player_id = player_id,
        ready = state.ready_votes[player_id],
        ready_count = summary.ready,
        total = summary.total,
        threshold = summary.threshold,
    })
    M.refreshPlayerListUI()
    M.refreshStartButtonUI()

    if summary.total > 0 and summary.ready >= summary.threshold then
        return tpl_start_countdown('ready-majority')
    end
    return true, nil
end

-- =========================================================================
-- 同步请求与 handler
-- =========================================================================

local function tpl_bind_sync_once()
    if state.sync_bound then
        return
    end
    state.sync_bound = true

    y3.sync.onSync(SYNC_MODE_SELECT, function(data, source)
        if not data then
            return
        end
        if not tpl_is_host(source) then
            tpl_log(('reject mode select from non-host player=%s mode=%s config_id=%s'):format(
                source and tostring(source:get_id()) or 'nil',
                tostring(data.mode_key),
                tostring(data.config_id)
            ))
            return
        end
        tpl_apply_mode_selection(data.mode_key or params.mode_key, data.config_id, 'sync-mode-select', data.mode_name)
    end)

    y3.sync.onSync(SYNC_READY_VOTE, function(data, source)
        data = data or {}
        tpl_apply_ready_vote(source, data.ready ~= false)
    end)
end

function M.requestModeSelect(mode_key, config_id, mode_name)
    y3.sync.send(SYNC_MODE_SELECT, {
        mode_key = mode_key,
        mode_name = mode_name,
        config_id = config_id,
    })
    return true
end

function M.requestSelectLevel(config_id)
    return M.requestModeSelect(params.mode_key, config_id)
end

function M.requestReady(ready)
    y3.sync.send(SYNC_READY_VOTE, {
        ready = ready ~= false,
    })
    return true
end

-- =========================================================================
-- 公开 API
-- =========================================================================

function M.setup(user_params)
    user_params = user_params or {}
    for k, v in pairs(user_params) do
        params[k] = v
    end

    assert(params.levels and #params.levels > 0, '[difficulty-select] params.levels 必填且非空')
    assert(params.host_player_id, '[difficulty-select] params.host_player_id 必填')
    assert(params.ui_paths, '[difficulty-select] params.ui_paths 必填')
    assert(params.ui_paths.panel, '[difficulty-select] params.ui_paths.panel 必填')
    assert(params.ui_paths.level_list, '[difficulty-select] params.ui_paths.level_list 必填')
    assert(params.ui_paths.start_btn, '[difficulty-select] params.ui_paths.start_btn 必填')

    params.countdown_seconds = params.countdown_seconds or 5
    params.player_records = params.player_records or {}
    params.mode_key = params.mode_key or ''
    params.mode_name = params.mode_name or ''

    state.open_levels = tpl_collect_open_levels(params.levels)
    state.select_id = state.open_levels[1] or 1
    state.is_start = false
    state.listeners = {}
    state.level_prefabs_by_player = {}
    state.start_btn_bound_by_player = {}
    state.ready_votes = {}
    state.initialized = true

    tpl_bind_sync_once()

    for _, player in ipairs(tpl_get_render_players()) do
        local panel = tpl_safe_get_ui(player, params.ui_paths.panel)
        if panel then
            panel:set_visible(true)
        end
    end
end

function M.on(event_name, callback)
    state.listeners[event_name] = state.listeners[event_name] or {}
    table.insert(state.listeners[event_name], callback)
end

function M.getSelectedLevel()
    return state.select_id
end

function M.getSelectedSub()
    return tpl_config_id_to_sub(state.open_levels, state.select_id) or 1
end

function M.getLevelStates()
    local result = {}
    for _, config_id in ipairs(state.open_levels) do
        local info = tpl_find_level(params.levels, config_id)
        table.insert(result, {
            config_id = config_id,
            name = info and info.name or ('Lv.' .. config_id),
            sub = tpl_config_id_to_sub(state.open_levels, config_id) or 1,
            unlocked = tpl_is_level_unlocked(params.player_records, config_id, state.open_levels),
            info = info and info.info or '',
            des = info and info.des or '',
            is_selected = (config_id == state.select_id),
            mode_key = params.mode_key,
            mode_name = params.mode_name,
        })
    end
    return result
end

function M.setMode(mode_key, mode_name)
    -- 兼容旧调用名：setup 后不得直接改权威状态，只能发送同步请求。
    if state.initialized then
        return M.requestModeSelect(mode_key, state.select_id, mode_name)
    end
    params.mode_key = mode_key or ''
    params.mode_name = mode_name or ''
    return true
end

function M.getMode()
    return params.mode_key or '', params.mode_name or ''
end

function M.setLevels(levels, player_records)
    assert(levels and #levels > 0, '[difficulty-select] levels 必填且非空')

    -- 运行期替换难度表必须通过 params.modes + requestModeSelect 选择预注册模式，
    -- 避免本地/非房主 Lua 调用绕过 y3.sync 直接改权威状态。
    if state.initialized then
        tpl_log('setLevels ignored after setup: use params.modes + requestModeSelect for multiplayer-safe changes')
        return false, '运行期 setLevels 已禁用，请使用 params.modes + requestModeSelect'
    end

    params.levels = levels
    params.player_records = player_records or {}
    state.open_levels = tpl_collect_open_levels(params.levels)
    state.select_id = state.open_levels[1] or 1
    return true, nil
end

-- 开始按钮语义：提交/更新自己的准备票；多数达成后自动倒计时。
function M.startGame()
    return M.requestReady(true), nil
end

function M.createLevelUI()
    M.clearLevelUI()

    for _, player in ipairs(tpl_get_render_players()) do
        local list_ui = tpl_safe_get_ui(player, params.ui_paths.level_list)
        if list_ui then
            local player_id = player:get_id()
            state.level_prefabs_by_player[player_id] = {}

            for i = 1, #state.open_levels do
                local config_id = state.open_levels[i]
                local info = tpl_find_level(params.levels, config_id)
                local prefab = y3.ui_prefab.create(player, LEVEL_CMP_PREFAB_NAME, list_ui)
                local ui = prefab:get_child()

                local title_text = ui and ui:get_child('title_TEXT')
                if title_text then
                    title_text:set_text(info and info.name or ('Lv.' .. tostring(config_id)))
                end

                local is_unlocked = tpl_is_level_unlocked(params.player_records, config_id, state.open_levels)
                local lock_img = ui and ui:get_child('lock')
                if lock_img then
                    lock_img:set_visible(not is_unlocked)
                end
                if ui then
                    ui:set_button_enable(is_unlocked)
                end

                local help_img = ui and ui:get_child('help')
                if help_img then help_img:set_visible(false) end
                local clear_img = ui and ui:get_child('clear')
                if clear_img then clear_img:set_visible(false) end
                local burn_btn = ui and ui:get_child('burn_BTN')
                if burn_btn then burn_btn:set_visible(false) end

                tpl_set_level_selected_style(ui, config_id == state.select_id)

                if ui then
                    ui:add_local_event('左键-点击', function(local_player)
                        if not is_unlocked then
                            return
                        end
                        if not tpl_is_host(local_player) then
                            tpl_log(('non-host clicked difficulty ignored locally; player=%s config_id=%s'):format(
                                local_player and tostring(local_player:get_id()) or 'nil',
                                tostring(config_id)
                            ))
                        end
                        M.requestSelectLevel(config_id)
                    end)
                end

                table.insert(state.level_prefabs_by_player[player_id], { prefab = prefab, ui = ui, config_id = config_id })
            end

            if not state.start_btn_bound_by_player[player_id] then
                local start_btn = tpl_safe_get_ui(player, params.ui_paths.start_btn)
                if start_btn then
                    start_btn:add_local_event('左键-点击', function(local_player)
                        tpl_log(('ready button clicked player=%s'):format(local_player and tostring(local_player:get_id()) or 'nil'))
                        M.requestReady(true)
                    end)
                    state.start_btn_bound_by_player[player_id] = true
                end
            end
        end
    end

    M.refreshPlayerListUI()
    M.refreshStartButtonUI()
end

function M.refreshLevelUI()
    for _, list in pairs(state.level_prefabs_by_player) do
        for _, item in ipairs(list) do
            tpl_set_level_selected_style(item.ui, item.config_id == state.select_id)
        end
    end
end

function M.clearLevelUI()
    for _, list in pairs(state.level_prefabs_by_player) do
        for _, item in ipairs(list) do
            if item.prefab then
                item.prefab:remove()
            end
        end
    end
    state.level_prefabs_by_player = {}
end

function M.resetStartState()
    state.is_start = false
    state.ready_votes = {}
    M.refreshPlayerListUI()
    M.refreshStartButtonUI()
end

function M.isStarted()
    return state.is_start
end

function M.recordPass(sub, count)
    count = count or 1
    params.player_records[sub] = (params.player_records[sub] or 0) + count
end

-- =========================================================================
-- 测试/调试辅助：不绑定 UI，本地 execute_lua 可直接验证状态路径。
-- ============================================================================

function M._debugApplyMode(mode_key, config_id)
    return tpl_apply_mode_selection(mode_key, config_id, 'debug')
end

function M._debugSetReady(player_id, ready)
    local player = y3.player.get_by_id(player_id)
    return tpl_apply_ready_vote(player, ready ~= false)
end

function M._debugStartCountdownIfReady()
    return tpl_start_countdown('debug')
end

return M
