--- =========================================================================
--- Y3 功能模板 · logic.lua  (B 级 · 参数注入式)
--- =========================================================================
---
--- @template-id   b-hud-top-info           -- kebab-case (B 级前缀 b-)
--- @grade         B                        -- 等级
--- @version       v0.1.0                   -- 首次导出固定
--- @entry         M.setup(params)          -- 融合入口
--- @params        ui_paths, currency_ids, get_item_config, get_local_player,
---                get_currency_num, resources, callbacks
--- @source        global_script/gamePlay/ui/hud/MainHUD.lua
--- @description   战斗 HUD 顶部信息栏：游戏模式、波次信息、游戏时间、阶段倒计时、玩家货币
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块入口点
---   2. 所有外部依赖通过 M.setup(params) 传入，禁止修改 local 常量
---   3. UI 路径通过 params.ui_paths 传入，禁止依赖本模板字面量
---   4. 本模板不自行注册全局事件；如需注册由融合侧决定时机
--- =========================================================================

local M = {}

-- ============================================================================
-- params 默认值
-- ============================================================================
local params = {
    -- ---- 必填 ----
    -- ui_paths: 所有 UI 节点 UUID 路径映射
    -- ui_paths = {
    --     game_mode       = "12971eb0-4266-46b2-bde9-c41afab96ca5",
    --     wave_title      = "7faf7342-475d-4dee-8509-32f8805c4d98",
    --     wave_counter    = "d052fecd-2053-4a3c-b6fb-fe02ced504c7",
    --     wave_prog       = "ff9a710d-41d2-47bf-8c45-d77376eaac0d",
    --     wave_prog_symb  = "27752442-c263-454f-b0f8-d89cb62c6bdf",
    --     pass_time       = "9efec1ec-7c24-42ec-abea-692539950ff0",
    --     day_night_cirle = "d47d62a7-da6c-4fdf-bd31-df40ca3ff7a8",
    --     day_dyn_frame   = "a164d70d-809d-4d74-a4e6-11abf19e1fe2",
    --     day_dyn_img     = "b4a2d7ef-aa87-4ad0-931a-309ed0baf2d3",
    --     day_img         = "7db0caf1-232e-4c0e-aeca-daf21abc5cc6",
    --     settle_btn      = "d7832372-258b-494d-becc-f462e44166bc",
    --     setting_btn     = "ff83e1e6-ccf1-4f77-8868-c48b6a60c75e",
    --     menu_btn        = "5f95f799-a4a6-4066-8b39-848571ba5e76",
    --     help_btn        = "8b2b8fb4-2db7-4bc9-82ac-01eca8dff144",
    --     exit_btn        = "a72d03d2-3ab4-41dd-8e4e-54197f70585f",
    --     jump_btn        = "d713c704-4df7-47fd-bc38-a88d8e80bf5d",
    --     camera_btn      = "28a1e765-0515-4ef1-b81d-6cfc4171d4cd",
    --     sfx_btn         = "92ebe500-5739-41d2-8414-9172ade13963",
    --     currency_nodes  = {
    --         { ui = "d658d876-8928-4483-b928-327041448829", icon = "640fecb8-343e-4d11-a163-8e4836c389f1" },
    --         { ui = "a7ce5e4b-2b64-4c2a-adee-a021fd8fd05e", icon = "04ccf226-b517-4b53-bad9-3829e1ba633d" },
    --         { ui = "8793c238-359b-4484-9c52-cceef7a48bc1", icon = "0fb077dd-1f7f-46e3-b65b-e26e2718beb6" },
    --     },
    --     power           = "1c99af6e-5abd-4885-9c55-32403c88e88e",
    --     power_text      = "36b79c35-9d28-4408-8861-319d202f81b9",
    -- },
    -- currency_ids: 货币类型 ID 列表
    -- currency_ids = { 2, 3, 4 },
    -- local_player_id: 本地玩家 ID（由融合侧传入）
    -- get_item_config: function(id) → { icon, name, des, obtain }
    -- get_currency_num: function(playerId, currencyId) → number
    -- get_local_player: function() → player object (含 getUnit / getCurrencyNum)
    -- ui_fetch: function(playerId, uuid) → UI node  （用于 y3.ui.get_ui 的封装）

    -- ---- 可选 ----
    -- resources: 图标资源 ID
    -- resources = {
    --     day_img      = 134246395,
    --     night_img    = 134258445,
    --     day_dyn_img  = 134258445,  -- 动画开始时切
    --     night_dyn_img = 134246395,
    --     jump_on  = { 134250743, 134281839, 134235940, 134261708 },
    --     jump_off = { 134242169, 134227384, 134252077, 134255095 },
    --     sfx_on   = { 134224886, 134241270, 134237603, 134274648 },
    --     sfx_off  = { 134233030, 134222483, 134252808, 134265893 },
    --     camera_on  = { 134281257, 134262950, 134245849, 134269987 },
    --     camera_off = { 134219304, 134251856, 134260993, 134264636 },
    -- },
    -- callbacks: 业务回调
    -- callbacks = {
    --     on_settle_click    = nil,  -- function()
    --     on_setting_click   = nil,  -- function(local_player)
    --     on_menu_click      = nil,  -- function(local_player)
    --     on_help_click      = nil,  -- function()
    --     on_exit_click      = nil,  -- function()
    --     on_toggle_jump     = nil,  -- function(on) → 返回新状态 boolean
    --     on_toggle_sfx      = nil,  -- function(on) → 返回新状态 boolean
    --     on_toggle_camera   = nil,  -- function(localPlayerId) → 返回锁定状态 boolean
    --     is_jump_on         = nil,  -- function() → boolean
    --     is_sfx_on          = nil,  -- function() → boolean
    --     is_camera_locked   = nil,  -- function(playerId) → boolean
    --     is_day             = nil,  -- function() → boolean
    --     on_bind_audio      = nil,  -- function(uiNode)
    --     show_tips          = nil,  -- function(tipsData)   -- 显示 Tips
    --     hide_tips          = nil,  -- function()
    -- },
}

local state = {}
local ui = {}

-- ============================================================================
-- 校验
-- ============================================================================
local function tpl_validate_params()
    assert(params.ui_paths, 'params.ui_paths is required')
    assert(params.ui_fetch, 'params.ui_fetch is required')
    assert(params.currency_ids and #params.currency_ids > 0, 'params.currency_ids is required')
    assert(params.get_item_config, 'params.get_item_config is required')
    assert(params.get_currency_num, 'params.get_currency_num is required')
    assert(params.local_player_id, 'params.local_player_id is required')
end

-- ============================================================================
-- UI 节点获取
-- ============================================================================
local function tpl_init_ui_nodes()
    local f = params.ui_fetch
    local pid = params.local_player_id
    local p = params.ui_paths

    ui.game_mode       = f(pid, p.game_mode)
    ui.wave_title      = f(pid, p.wave_title)
    ui.wave_counter    = f(pid, p.wave_counter)
    ui.wave_prog       = f(pid, p.wave_prog)
    ui.wave_prog_symb  = f(pid, p.wave_prog_symb)
    ui.pass_time       = f(pid, p.pass_time)
    ui.day_night_cirle = f(pid, p.day_night_cirle)
    ui.day_dyn_frame   = f(pid, p.day_dyn_frame)
    ui.day_dyn_img     = f(pid, p.day_dyn_img)
    ui.day_img         = f(pid, p.day_img)
    ui.settle_btn      = f(pid, p.settle_btn)
    ui.setting_btn     = f(pid, p.setting_btn)
    ui.menu_btn        = f(pid, p.menu_btn)
    ui.help_btn        = f(pid, p.help_btn)
    ui.exit_btn        = f(pid, p.exit_btn)
    ui.jump_btn        = f(pid, p.jump_btn)
    ui.camera_btn      = f(pid, p.camera_btn)
    ui.sfx_btn         = f(pid, p.sfx_btn)

    -- 货币组件
    ui.currency_nodes = {}
    if p.currency_nodes then
        for i, node in ipairs(p.currency_nodes) do
            ui.currency_nodes[i] = {
                ui   = f(pid, node.ui),
                icon = f(pid, node.icon),
            }
        end
    end

    -- 活动值（power）
    if p.power then
        ui.power      = f(pid, p.power)
        ui.power_text = f(pid, p.power_text)
    end
end

-- ============================================================================
-- 内部工具：进度条动画（简化版 SequenceProgress）
-- ============================================================================
---@param progWidget UI  进度条 mask 节点
---@param lightWidget UI? 高亮标记节点
---@param ratio number    目标比例 0-1
---@param duration? number 动画时长（秒），nil=立即
local function tpl_set_progress(progWidget, lightWidget, ratio, duration)
    ratio = math.min(1, math.max(0, ratio))
    local w = progWidget:get_width()

    if not duration then
        progWidget:set_ui_size(w * ratio, progWidget:get_height())
        if lightWidget then
            lightWidget:set_pos(w * ratio, lightWidget:get_relative_y())
        end
        return
    end

    -- 简化：直接设置目标值（Y3 自带进度条动画）
    -- 如需逐帧动画，融合侧用 y3.ltimer 实现
    progWidget:set_ui_size(w * ratio, progWidget:get_height())
    if lightWidget then
        lightWidget:set_pos(w * ratio, lightWidget:get_relative_y())
    end
end

-- ============================================================================
-- 内部工具：日夜切换动画
-- ============================================================================
local function tpl_refresh_day_night(is_day)
    local res = params.resources or {}
    if is_day then
        -- 白天
        ui.day_dyn_img:set_image(res.day_dyn_img or res.day_img)
        ui.day_img:set_image(res.day_img)
        -- 圆圈旋转 180→270→360（简化：直接设最终态）
        -- TODO: 完整动画需要引入 UIFrameTween 或等效逐帧逻辑
    else
        -- 夜晚
        ui.day_dyn_img:set_image(res.night_dyn_img or res.night_img)
        ui.day_img:set_image(res.night_img)
        -- 圆圈旋转 0→90→180
    end
end

-- ============================================================================
-- 刷新函数
-- ============================================================================

---刷新波次信息 + 阶段倒计时
---@param data { title: string, timeStr: string?, endTime: number }
function M.refresh_core_time(data)
    if not data then return end
    ui.wave_title:set_text(data.title)
    if data.timeStr then
        ui.wave_counter:set_text(data.timeStr)
    end
    state.next_time = data.endTime
end

---刷新日夜状态（由外部调用）
function M.refresh_day_night()
    local cbs = params.callbacks or {}
    local is_day = cbs.is_day and cbs.is_day()
    if is_day == nil then return end
    tpl_refresh_day_night(is_day)
end

---刷新货币（指定类型 ID 变化时调用）
---@param currency_id integer  货币类型 ID，nil 表示全量刷新
function M.refresh_currency(currency_id)
    if not params.currency_ids then return end
    local cids = params.currency_ids
    for i = 1, #cids do
        local cid = cids[i]
        if currency_id == nil or currency_id == cid then
            tpl_update_currency_node(i, cid)
        end
    end
end

---刷新游戏时间（由外部每秒调用）
---@param time_str string  格式化的时间字符串
function M.refresh_game_time(time_str)
    ui.pass_time:set_text(time_str)
end

---设置游戏模式文本
---@param mode_str string
function M.set_game_mode(mode_str)
    ui.game_mode:set_text(mode_str)
end

---设置结算按钮可见
---@param visible boolean
function M.set_settle_visible(visible)
    ui.settle_btn:set_visible(visible)
end

---设置结算按钮激活态
---@param is_active boolean
function M.set_settle_active(is_active)
    local active_node = ui.settle_btn:get_child("active")
    local reddot_node = ui.settle_btn:get_child("reddot")
    if active_node then
        active_node:set_visible(is_active)
        if is_active then active_node:play_ui_sequence(true, 0.03) end
    end
    if reddot_node then reddot_node:set_visible(is_active) end
end

-- ============================================================================
-- 货币节点更新
-- ============================================================================
local function tpl_update_currency_node(index, currency_id)
    local node = ui.currency_nodes and ui.currency_nodes[index]
    if not node then return end
    local item_info = params.get_item_config(currency_id)
    if not item_info then
        node.ui:set_visible(false)
        return
    end
    local count = params.get_currency_num(params.local_player_id, tostring(currency_id))
    node.ui:set_visible(true)
    node.icon:set_image(item_info.icon)
    -- 货币文本在 CurrencyCmp 中是 "text" 子节点
    local text_node = node.ui:get_child("text")
    if text_node then
        text_node:set_text(tostring(count))
    end
end

---刷新所有货币显示
function M.refresh_all_currency()
    M.refresh_currency(nil)
end

-- ============================================================================
-- 按钮刷新
-- ============================================================================

---刷新跳字按钮图标
function M.refresh_jump_btn()
    local cbs = params.callbacks or {}
    local on = cbs.is_jump_on and cbs.is_jump_on()
    local res = (params.resources or {})
    local icons = on and res.jump_on or res.jump_off
    if not icons then return end
    for i = 1, 4 do
        ui.jump_btn:set_btn_status_image(i, icons[i])
    end
end

---刷新特效开关按钮图标
function M.refresh_sfx_btn()
    local cbs = params.callbacks or {}
    local on = cbs.is_sfx_on and cbs.is_sfx_on()
    local res = (params.resources or {})
    -- 注意：源工程中 sfxOn=true 时用 "off" 图标（表示可点击关闭）
    local icons = on and res.sfx_off or res.sfx_on
    if not icons then return end
    for i = 1, 4 do
        ui.sfx_btn:set_btn_status_image(i, icons[i])
    end
end

---刷新镜头锁定按钮图标
function M.refresh_camera_btn()
    local cbs = params.callbacks or {}
    local locked = cbs.is_camera_locked and cbs.is_camera_locked(params.local_player_id)
    local res = (params.resources or {})
    local icons = locked and res.camera_on or res.camera_off
    if not icons then return end
    for i = 1, 4 do
        ui.camera_btn:set_btn_status_image(i, icons[i])
    end
end

-- ============================================================================
-- 事件注册
-- ============================================================================
local function tpl_register_events()
    local cbs = params.callbacks or {}

    -- 结算按钮
    if ui.settle_btn and cbs.on_settle_click then
        ui.settle_btn:add_local_event('左键-点击', cbs.on_settle_click)
    end

    -- 设置按钮
    if ui.setting_btn and cbs.on_setting_click then
        ui.setting_btn:add_local_event('左键-点击', cbs.on_setting_click)
        if cbs.on_bind_audio then cbs.on_bind_audio(ui.setting_btn) end
    end

    -- 菜单按钮
    if ui.menu_btn and cbs.on_menu_click then
        ui.menu_btn:add_local_event('左键-点击', cbs.on_menu_click)
        if cbs.on_bind_audio then cbs.on_bind_audio(ui.menu_btn) end
    end

    -- 帮助按钮
    if ui.help_btn and cbs.on_help_click then
        ui.help_btn:add_local_event('左键-点击', cbs.on_help_click)
    end

    -- 退出按钮
    if ui.exit_btn and cbs.on_exit_click then
        ui.exit_btn:add_local_event('左键-点击', cbs.on_exit_click)
    end

    -- 跳字开关
    if ui.jump_btn then
        local function tpl_jump_toggle()
            local on = cbs.is_jump_on and cbs.is_jump_on() or false
            if cbs.on_toggle_jump then
                on = cbs.on_toggle_jump(not on)
            end
            if cbs.show_tips then
                cbs.show_tips({
                    player_id = params.local_player_id,
                    str = string.format("跳字开关：当前跳字已%s", on and "#G开启" or "#R关闭"),
                })
            end
            M.refresh_jump_btn()
        end

        ui.jump_btn:add_local_event('左键-点击', tpl_jump_toggle)
        ui.jump_btn:add_local_event('鼠标-移入', function()
            if cbs.show_tips then
                local on = cbs.is_jump_on and cbs.is_jump_on() or false
                cbs.show_tips({
                    player_id = params.local_player_id,
                    str = string.format("跳字开关：当前跳字已%s", on and "#G开启" or "#R关闭"),
                })
            end
        end)
        ui.jump_btn:add_local_event('鼠标-移出', function()
            if cbs.hide_tips then cbs.hide_tips() end
        end)
        if cbs.on_bind_audio then cbs.on_bind_audio(ui.jump_btn) end
    end

    -- 相机锁定
    if ui.camera_btn then
        local function tpl_camera_toggle()
            if cbs.on_toggle_camera then
                cbs.on_toggle_camera(params.local_player_id)
            end
            if cbs.show_tips then
                local locked = cbs.is_camera_locked and cbs.is_camera_locked(params.local_player_id)
                cbs.show_tips({
                    player_id = params.local_player_id,
                    str = string.format("镜头开关：当前%s锁定", locked and "已" or "未"),
                })
            end
        end

        ui.camera_btn:add_local_event('左键-点击', tpl_camera_toggle)
        ui.camera_btn:add_local_event('鼠标-移入', function()
            if cbs.show_tips then
                local locked = cbs.is_camera_locked and cbs.is_camera_locked(params.local_player_id)
                cbs.show_tips({
                    player_id = params.local_player_id,
                    str = string.format("镜头开关：当前%s锁定", locked and "已" or "未"),
                })
            end
        end)
        ui.camera_btn:add_local_event('鼠标-移出', function()
            if cbs.hide_tips then cbs.hide_tips() end
        end)
        if cbs.on_bind_audio then cbs.on_bind_audio(ui.camera_btn) end
    end

    -- 特效开关
    if ui.sfx_btn then
        local function tpl_sfx_toggle()
            local on = cbs.is_sfx_on and cbs.is_sfx_on() or false
            if cbs.on_toggle_sfx then
                on = cbs.on_toggle_sfx(not on)
            end
            if cbs.show_tips then
                cbs.show_tips({
                    player_id = params.local_player_id,
                    str = string.format("特效开关：当前特效已%s", on and "#G开启" or "#R关闭"),
                })
            end
            M.refresh_sfx_btn()
        end

        ui.sfx_btn:add_local_event('左键-点击', tpl_sfx_toggle)
        ui.sfx_btn:add_local_event('鼠标-移入', function()
            if cbs.show_tips then
                local on = cbs.is_sfx_on and cbs.is_sfx_on() or false
                cbs.show_tips({
                    player_id = params.local_player_id,
                    str = string.format("特效开关：当前特效已%s", on and "#G开启" or "#R关闭"),
                })
            end
        end)
        ui.sfx_btn:add_local_event('鼠标-移出', function()
            if cbs.hide_tips then cbs.hide_tips() end
        end)
        if cbs.on_bind_audio then cbs.on_bind_audio(ui.sfx_btn) end
    end

    -- 货币节点 hover tips
    for i, node in ipairs(ui.currency_nodes or {}) do
        local cid = (params.currency_ids or {})[i]
        if cid and node.ui then
            node.ui:add_local_event('鼠标-移入', function()
                local item_info = params.get_item_config(cid)
                if not item_info then return end
                if cbs.show_tips then
                    cbs.show_tips({
                        player_id = params.local_player_id,
                        name = item_info.name,
                        desc = item_info.des,
                        icon = item_info.icon,
                        tips = item_info.obtain,
                        type = 'base',
                        ui = node.ui,
                    })
                end
            end)
            node.ui:add_local_event('鼠标-移出', function()
                if cbs.hide_tips then cbs.hide_tips() end
            end)
        end
    end
end

-- ============================================================================
-- 入口
-- ============================================================================
---@param user_params table  融合侧传入的参数，见 params 声明
function M.setup(user_params)
    user_params = user_params or {}
    -- 深度合并 params（浅层合并 + callbacks 子表合并）
    for k, v in pairs(user_params) do
        if k == 'callbacks' and type(v) == 'table' and type(params.callbacks) == 'table' then
            for ck, cv in pairs(v) do
                params.callbacks[ck] = cv
            end
        elseif k == 'ui_paths' and type(v) == 'table' and type(params.ui_paths) == 'table' then
            for upk, upv in pairs(v) do
                params.ui_paths[upk] = upv
            end
        elseif k == 'resources' and type(v) == 'table' and type(params.resources) == 'table' then
            for rk, rv in pairs(v) do
                params.resources[rk] = rv
            end
        else
            params[k] = v
        end
    end

    tpl_validate_params()
    tpl_init_ui_nodes()
    tpl_register_events()

    -- 初始刷新
    M.refresh_all_currency()
    M.refresh_jump_btn()
    M.refresh_sfx_btn()
    M.refresh_camera_btn()

    state._inited = true
end

---获取初始化状态
---@return boolean
function M.is_inited()
    return state._inited == true
end

return M
