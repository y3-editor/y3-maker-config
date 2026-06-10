--- =========================================================================
--- Y3 功能模板 · logic.lua  (B 级 · 参数注入式)
--- =========================================================================
---
--- @template-id   b-pause-popup
--- @grade         B
--- @version       v0.1.9
--- @entry         M.setup(params) / M.setup_controller(params)
--- @params        setup: ui_paths?, on_continue, get_local_player_id?,
---                get_pause_player_id, get_pause_times, get_player_num,
---                on_exit?, show_exit_button?, get_player_name?, bind_ui_effect?,
---                colors?, texts?, skip_ui_config_check?
--- @params        setup_controller: 在 setup 参数基础上增加 keys?, max_pause_times?,
---                unlimited_single_player?, auto_bind_keys?, key_event?, allow_any_player_resume?,
---                pause_impl?, resume_impl?, can_pause?, consume_pause_time?,
---                request_resume?, sync_id?, sync_continue_button?, on_pause?, on_resume?
--- @source        global_script/gamePlay/ui/hudPopup/PausePopup.lua
--- @source_layer  [0]PAUSE
--- @description   游戏暂停弹窗：显示暂停者+剩余次数，提供继续/退出按钮
---
--- 融合契约：
---   1. 调用方导入 .upui 后，通过 M.setup(params) 注入 UI 路径与回调
---   2. 暂停/恢复/次数等业务全部通过 params 回调，模板不直接读 Mgr
---   3. 模板返回实例对象，由调用方在合适时机调 instance:show()/:hide()
---   4. M.setup() 不自动注册全局按键/暂停事件；显示时机由调用方决定
---   5. M.setup_controller() 提供可选软暂停控制器：暂停/恢复、次数、按键、弹窗联动
---      默认按键事件使用“键盘-按下”，确保暂停/恢复入口保持同步
---      继续按钮是本地 UI 事件，默认通过 y3.sync.send 广播恢复请求
---   6. 显隐只使用 UI:set_visible，不使用 UI:set_alpha 控制显隐。
---      若 visible=true 仍不可见，优先检查导入后的 UI JSON opacity 是否为 1.0。
--- =========================================================================

local M = {}

-- ============================================================================
-- 内置默认值（可由 params 覆盖）
-- ============================================================================
local tpl_DEFAULT_COLORS = {
    GREEN = '#7fff7f',
    RED   = '#ff7f7f',
}

local tpl_DEFAULT_TEXTS = {
    paused_by         = '游戏已被 %s%s#E 暂停',      -- color, name
    unlimited_pauses  = '单人模式下不限次数',
    remaining_pauses  = '你还剩 %s%d#E 次暂停权限',  -- color, times
    waiting_resume    = '请等待暂停玩家继续游戏',
}

-- 默认路径匹配 b-pause-popup.upui 导入后的完整节点树。
local tpl_DEFAULT_UI_PATHS = {
    root          = '[0]PAUSE',
    root_node     = '[0]PAUSE.root',
    mask          = '[0]PAUSE.root.bg',
    panel         = '[0]PAUSE.root.pause',
    title         = '[0]PAUSE.root.pause.content.title_TEXT',
    title_sub     = '[0]PAUSE.root.pause.content.titleSub_TEXT',
    continue_btn  = '[0]PAUSE.root.pause.control.gameContinue_BTN',
    continue_text = '[0]PAUSE.root.pause.control.gameContinue_BTN.title_TEXT',
    exit_btn      = '[0]PAUSE.root.pause.control.gameExit_BTN',
    exit_text     = '[0]PAUSE.root.pause.control.gameExit_BTN.title_TEXT',
}

local tpl_DEFAULT_VISIBLE_PATH_KEYS = {
    'root',
    'root_node',
    'mask',
    'panel',
}

-- ============================================================================
-- 内部工具
-- ============================================================================
local function tpl_get_ui(path)
    return y3.ui.get_ui(y3.player.get_local(), path)
end

local function tpl_try_get_ui(path)
    local ok, ui = pcall(tpl_get_ui, path)
    if ok then
        return ui
    end
    return nil
end

local function tpl_color(p, key)
    return (p.colors and p.colors[key]) or tpl_DEFAULT_COLORS[key] or '#ffffff'
end

local function tpl_text(p, key)
    return (p.texts and p.texts[key]) or tpl_DEFAULT_TEXTS[key] or ''
end

local function tpl_player_name(p, pid)
    if p.get_player_name then return p.get_player_name(pid) end
    local pl = y3.player(pid)
    return pl and pl:get_name() or ('Player ' .. tostring(pid))
end

local function tpl_build_visible_paths(paths, keys)
    local result = {}
    keys = keys or tpl_DEFAULT_VISIBLE_PATH_KEYS
    for _, key in ipairs(keys) do
        local path = paths[key]
        if path then
            result[#result + 1] = path
        end
    end
    return result
end

local function tpl_copy_default_paths(user_paths)
    local paths = {}
    for k, v in pairs(tpl_DEFAULT_UI_PATHS) do
        paths[k] = v
    end
    if user_paths then
        for k, v in pairs(user_paths) do
            paths[k] = v
        end
    end
    return paths
end

local function tpl_warn(message)
    print('[b-pause-popup] ' .. message)
end

local function tpl_validate_params(p)
    p.ui_paths = tpl_copy_default_paths(p.ui_paths)
    p.visible_paths = p.visible_paths or tpl_build_visible_paths(p.ui_paths, p.visible_path_keys)

    assert(p.ui_paths.root,                        '[b-pause-popup] ui_paths.root required')
    assert(p.ui_paths.title,                       '[b-pause-popup] ui_paths.title required')
    assert(p.ui_paths.title_sub,                   '[b-pause-popup] ui_paths.title_sub required')
    assert(p.ui_paths.continue_btn,                '[b-pause-popup] ui_paths.continue_btn required')
    assert(p.ui_paths.exit_btn,                    '[b-pause-popup] ui_paths.exit_btn required')
    assert(type(p.on_continue) == 'function',      '[b-pause-popup] on_continue required')
    assert(type(p.get_pause_player_id) == 'function', '[b-pause-popup] get_pause_player_id required')
    assert(type(p.get_pause_times) == 'function',  '[b-pause-popup] get_pause_times required')
    assert(type(p.get_player_num) == 'function',   '[b-pause-popup] get_player_num required')
end

local function tpl_default_local_player_id()
    local player = y3.player.get_local()
    return player and player:get_id() or 0
end

-- 只做运行时可见性/节点存在性自检，不修改 alpha/opacity。
-- 如果导入后的 JSON opacity 被错误保存为 0，必须修 UI JSON，而不是在显隐逻辑里 set_alpha。
local function tpl_check_ui_config(p)
    if p.skip_ui_config_check then
        return
    end

    local paths = p.ui_paths
    local required = {
        paths.root,
        paths.title,
        paths.title_sub,
        paths.continue_btn,
        paths.exit_btn,
    }
    for _, path in ipairs(required) do
        if not tpl_try_get_ui(path) then
            tpl_warn('UI path not found: ' .. tostring(path) .. '；请导入 b-pause-popup.upui 后重新生成 ui_tree，并按实际节点树修正 ui_paths')
        end
    end

    -- get_ui 能拿到但 visible=true 仍不显示时，最常见原因是 JSON opacity=0。
    -- 这里无法可靠读取 opacity，只输出一次排查提示。
    tpl_warn('visibility uses set_visible only. If [0]PAUSE is invisible after show(), check maps/EntryMap/ui/[0]PAUSE.json: root opacity and root.bg opacity should be 1.0, not 0.0')
end

-- ============================================================================
-- 实例工厂（闭包捕获实例独立 params）
-- ============================================================================
local function tpl_create_instance(p)
    local self = {
        _inited     = false,
        _is_show    = false,
        _local_pid  = nil,
        _panel      = nil,
        _title      = nil,
        _title_sub  = nil,
        _continue   = nil,
        _exit       = nil,
    }

    local function bind_hide_or_callback(ui, callback, fallback_hide)
        ui:add_local_event('左键-点击', function()
            if callback then
                callback()
            elseif fallback_hide then
                self:hide()
            end
        end)
    end

    local function init()
        if self._inited then return end

        self._local_pid = p.get_local_player_id and p.get_local_player_id() or tpl_default_local_player_id()
        self._panel     = tpl_get_ui(p.ui_paths.root)
        self._title     = tpl_get_ui(p.ui_paths.title)
        self._title_sub = tpl_get_ui(p.ui_paths.title_sub)
        self._continue  = tpl_get_ui(p.ui_paths.continue_btn)
        self._exit      = tpl_get_ui(p.ui_paths.exit_btn)

        if p.bind_ui_effect then
            p.bind_ui_effect(self._continue)
            p.bind_ui_effect(self._exit)
        end

        bind_hide_or_callback(self._continue, p.on_continue, false)
        bind_hide_or_callback(self._exit, p.on_exit, true)

        local continue_text = p.ui_paths.continue_text and tpl_try_get_ui(p.ui_paths.continue_text)
        if continue_text then
            continue_text:set_intercepts_operations(false)
        end
        local exit_text = p.ui_paths.exit_text and tpl_try_get_ui(p.ui_paths.exit_text)
        if exit_text then
            exit_text:set_intercepts_operations(false)
        end

        tpl_check_ui_config(p)
        self._inited = true
    end

    function self:refresh()
        local pause_pid = p.get_pause_player_id()
        local is_pause_owner = pause_pid == self._local_pid

        -- 原 [0]PAUSE UI 中“继续游戏”和“退出游戏”按钮共用同一位置，不能默认同时显示。
        -- 默认：暂停者显示继续按钮；非暂停者可通过 show_exit_button=true 显示退出按钮。
        self._continue:set_visible(is_pause_owner)
        self._exit:set_visible((not is_pause_owner) and p.show_exit_button == true)

        local name_color = tpl_color(p, 'GREEN')
        self._title:set_text(string.format(
            tpl_text(p, 'paused_by'),
            name_color,
            tpl_player_name(p, pause_pid)
        ))

        if is_pause_owner then
            if p.get_player_num() == 1 then
                self._title_sub:set_text(tpl_text(p, 'unlimited_pauses'))
            else
                local times = p.get_pause_times(self._local_pid)
                local color = times > 0 and tpl_color(p, 'GREEN') or tpl_color(p, 'RED')
                self._title_sub:set_text(string.format(tpl_text(p, 'remaining_pauses'), color, times))
            end
        else
            self._title_sub:set_text(tpl_text(p, 'waiting_resume'))
        end
    end

    function self:show()
        init()
        self:refresh()
        for _, path in ipairs(p.visible_paths) do
            local ui = tpl_try_get_ui(path)
            if ui then
                ui:set_visible(true)
            end
        end
        self._is_show = true
    end

    function self:hide()
        if p.visible_paths then
            for _, path in ipairs(p.visible_paths) do
                local ui = tpl_try_get_ui(path)
                if ui then
                    ui:set_visible(false)
                end
            end
        elseif self._panel then
            self._panel:set_visible(false)
        end
        self._is_show = false
    end

    function self:is_show()
        return self._is_show
    end

    return self
end

-- ============================================================================
-- 公开 API
-- ============================================================================
---@param user_params table
---@return table instance 含 :show() :hide() :refresh() :is_show()
function M.setup(user_params)
    local p = {}
    user_params = user_params or {}
    for k, v in pairs(user_params) do p[k] = v end
    tpl_validate_params(p)
    return tpl_create_instance(p)
end


-- ============================================================================
-- 可选暂停控制器：软暂停/恢复 + 次数管理 + 按键绑定 + 弹窗联动
-- ============================================================================
local function tpl_default_player_num()
    return y3.player_group.get_all_players():count()
end

local function tpl_shallow_copy(source)
    local result = {}
    for k, v in pairs(source or {}) do
        result[k] = v
    end
    return result
end

local function tpl_default_key_event()
    return '键盘-按下'
end

local function tpl_normalize_keys(keys)
    if keys == false then
        return {}
    end
    if keys == nil then
        return { 'P', 'F8' }
    end
    return keys
end

---@param user_params table
---@return table controller 含 :pause() :resume() :request_resume() :toggle() :is_paused() :get_popup() :get_pause_player_id() :get_pause_times(pid)
function M.setup_controller(user_params)
    local opts = tpl_shallow_copy(user_params)
    local local_player_id_fn = opts.get_local_player_id or tpl_default_local_player_id
    local get_player_num_fn = opts.get_player_num or tpl_default_player_num
    local pause_times = opts.pause_times or {}
    local max_pause_times = opts.max_pause_times or 3
    local unlimited_single_player = opts.unlimited_single_player ~= false
    local allow_any_player_resume = opts.allow_any_player_resume == true
    local sync_continue_button = opts.sync_continue_button ~= false
    local sync_id = opts.sync_id or 'b-pause-popup:resume'
    local last_toggle_time = -999

    local controller = {
        _is_paused = false,
        _pause_pid = nil,
        _popup = nil,
        _keys_bound = false,
    }

    local function get_times(pid)
        if pause_times[pid] == nil then
            pause_times[pid] = max_pause_times
        end
        return pause_times[pid]
    end

    local function set_times(pid, value)
        pause_times[pid] = value
    end

    local function can_pause(pid)
        if opts.can_pause then
            return opts.can_pause(pid, controller)
        end
        if unlimited_single_player and get_player_num_fn() == 1 then
            return true
        end
        if opts.get_pause_times then
            return opts.get_pause_times(pid) > 0
        end
        return get_times(pid) > 0
    end

    local function consume_pause_time(pid)
        if unlimited_single_player and get_player_num_fn() == 1 then
            return
        end
        if opts.consume_pause_time then
            opts.consume_pause_time(pid, controller)
            return
        end
        -- 默认由控制器内部管理次数；如果传入外部 get_pause_times，请同时传 consume_pause_time。
        if not opts.get_pause_times then
            set_times(pid, math.max(0, get_times(pid) - 1))
        end
    end

    local function player_id_of(player)
        return player and player.get_id and player:get_id() or nil
    end

    local function request_resume(pid)
        pid = pid or local_player_id_fn()
        if opts.request_resume then
            opts.request_resume(pid, controller)
            return true
        end
        -- UI:add_local_event 是本地事件；多人时不能只在点击者客户端 resume。
        -- 默认先广播，再由所有客户端在 onSync 中执行 resume/hide。
        if sync_continue_button and y3.sync and y3.sync.send then
            y3.sync.send(sync_id, { action = 'resume', pid = pid })
            return true
        end
        return controller:resume(pid)
    end

    local popup_params = tpl_shallow_copy(opts.popup_params or opts)
    popup_params.get_local_player_id = local_player_id_fn
    popup_params.get_pause_player_id = function()
        return controller._pause_pid or local_player_id_fn()
    end
    popup_params.get_pause_times = function(pid)
        if opts.get_pause_times then
            return opts.get_pause_times(pid)
        end
        return get_times(pid)
    end
    popup_params.get_player_num = get_player_num_fn
    popup_params.on_continue = function()
        request_resume(local_player_id_fn())
    end
    if opts.on_exit then
        popup_params.on_exit = opts.on_exit
    end

    controller._popup = M.setup(popup_params)

    function controller:get_popup()
        return self._popup
    end

    function controller:is_paused()
        return self._is_paused
    end

    function controller:get_pause_player_id()
        return self._pause_pid
    end

    function controller:get_pause_times(pid)
        if opts.get_pause_times then
            return opts.get_pause_times(pid)
        end
        return get_times(pid)
    end

    function controller:request_resume(pid)
        return request_resume(pid)
    end

    function controller:pause(pid)
        pid = pid or local_player_id_fn()
        if self._is_paused then
            self._popup:show()
            return true
        end
        if not can_pause(pid) then
            tpl_warn('pause rejected: no remaining pause times for player ' .. tostring(pid))
            return false
        end

        consume_pause_time(pid)
        self._is_paused = true
        self._pause_pid = pid

        if opts.pause_impl then
            opts.pause_impl(pid, self)
        else
            y3.game.enable_soft_pause()
        end
        self._popup:show()
        if opts.on_pause then
            opts.on_pause(pid, self)
        end
        return true
    end

    function controller:resume(pid)
        pid = pid or local_player_id_fn()
        if not self._is_paused then
            self._popup:hide()
            return true
        end
        if (not allow_any_player_resume) and self._pause_pid and pid ~= self._pause_pid then
            tpl_warn('resume rejected: player ' .. tostring(pid) .. ' is not pause owner ' .. tostring(self._pause_pid))
            return false
        end

        if opts.resume_impl then
            opts.resume_impl(pid, self)
        else
            y3.game.resume_soft_pause()
        end
        self._is_paused = false
        self._pause_pid = nil
        self._popup:hide()
        if opts.on_resume then
            opts.on_resume(pid, self)
        end
        return true
    end

    function controller:toggle(pid)
        pid = pid or local_player_id_fn()

        -- 软暂停后逻辑时间可能停止；恢复不能被 os.clock 去抖卡住。
        if self._is_paused then
            return self:resume(pid)
        end

        local now = os.clock()
        if now - last_toggle_time < (opts.toggle_debounce or 0.15) then
            return false
        end
        last_toggle_time = now
        return self:pause(pid)
    end

    if sync_continue_button and y3.sync and y3.sync.onSync then
        y3.sync.onSync(sync_id, function(data, source)
            if type(data) ~= 'table' or data.action ~= 'resume' then
                return
            end
            local pid = player_id_of(source) or data.pid or local_player_id_fn()
            controller:resume(pid)
        end)
    end

    function controller:bind_keys(keys)
        if self._keys_bound then
            return
        end
        self._keys_bound = true
        local key_event = opts.key_event or tpl_default_key_event()
        for _, key in ipairs(tpl_normalize_keys(keys)) do
            y3.game:event(key_event, key, function(_, data)
                local trigger_player = data and data.player
                local pid = trigger_player and trigger_player:get_id() or local_player_id_fn()
                self:toggle(pid)
            end)
        end
    end

    if opts.auto_bind_keys then
        controller:bind_keys(opts.keys)
    end

    return controller
end

return M
