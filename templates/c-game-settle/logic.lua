--- =========================================================================
--- Y3 功能模板 · logic.lua  (C 级 · 三层架构 DataSchema + Adapter + PureLogic)
--- =========================================================================
---
--- @template-id   c-game-settle
--- @grade         C
--- @version       v0.1.0
--- @entry         M.setup(adapter, params)
--- @architecture  three-layer (DataSchema + Adapter + PureLogic)
--- @source        global_script/gamePlay/ui/hudPopup/gameSettle/
--- @description   游戏结束结算面板：胜负标题 + 玩家战绩列表 + 奖励汇总 + 胜利/失败插屏
---
--- 接入只需 3 步：
---   1. 按 §1 DataSchema 准备数据格式
---   2. 实现 §2 Adapter 接口的 7 个必填方法
---   3. M.setup(your_adapter, your_params) 后调用 M.show_settle(is_win)
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 调用方必须按此格式提供数据
-- ============================================================================

---@class SettleRewardData
---@field name     string   奖励名称
---@field icon     integer  图标资源 ID
---@field descr    string   描述文本
---@field quantity integer  数量（0 表示不显示数量）
---@field quality  integer  品质等级 (1-6)

---@class SettlePlayerSummary
---@field name       string    玩家名
---@field icon       integer   平台头像 ID
---@field is_local   boolean   是否本地玩家（高亮用）
---@field power      integer   战力值
---@field level      integer   英雄等级
---@field kills      integer   击杀数
---@field bond_count integer   羁绊获得卡数
---@field hero_icons integer[] 吸收英雄图标列表（最多 10 个）

-- ============================================================================
-- §2. Adapter 接口 — 调用方必须实现以下方法
-- ============================================================================

---@class GameSettleAdapter
---@field get_local_player_id  fun(): integer                                      必填: 返回本地玩家 ID
---@field get_rewards          fun(player_id: integer): SettleRewardData[]         必填: 返回玩家结算奖励列表
---@field get_player_summary   fun(player_id: integer): SettlePlayerSummary        必填: 返回玩家战绩摘要
---@field is_valid_slot        fun(slot_idx: integer): boolean                     必填: 槽位 1-4 是否有效玩家
---@field on_quit              fun(player_id: integer)                             必填: 退出游戏回调
---@field on_continue          fun(player_id: integer)                             必填: 继续游戏回调（胜利后）
---@field on_show_tooltip      fun(reward: SettleRewardData, ui_element: UI)       必填: 鼠标悬停显示 Tooltip
---@field on_hide_tooltip      fun()?                                               可选: 鼠标移出隐藏 Tooltip
---@field play_sfx             fun(name: string)?                                  可选: 按钮音效钩子
---@field on_first_fold_anim   fun()?                                               可选: 首次点击继续后的动画
---@field format_number        fun(n: integer): string?                            可选: 大数字格式化
---@field on_settle_changed    fun(callback: fun()): function?                     可选: 订阅奖励变化，返回取消订阅函数

-- ============================================================================
-- §3. Pure Logic — 调用方不需修改
-- ============================================================================

local adapter = nil
local params  = nil
local state   = {}

---@type table<string, UI>
local ui = {}

-- ---------------------------------------------------------------------------
-- 内部工具
-- ---------------------------------------------------------------------------

---校验 Adapter 接口完整性
local function tpl_validate_adapter(a)
    assert(type(a) == 'table', 'adapter must be a table')
    local required = {
        'get_local_player_id',
        'get_rewards',
        'get_player_summary',
        'is_valid_slot',
        'on_quit',
        'on_continue',
        'on_show_tooltip',
    }
    for _, name in ipairs(required) do
        assert(type(a[name]) == 'function',
            'GameSettleAdapter missing required method: ' .. name)
    end
end

---大数字格式化（默认万/亿）
local function tpl_format_number(n)
    if adapter.format_number then
        return adapter.format_number(n)
    end
    if n >= 100000000 then
        return string.format("%.1f亿", n / 100000000)
    elseif n >= 10000 then
        return string.format("%.1f万", n / 10000)
    end
    return tostring(n)
end

-- ---------------------------------------------------------------------------
-- 内部 — 工具函数
-- ---------------------------------------------------------------------------

---播放音效（可选）
local function tpl_play_sfx(name)
    if adapter and adapter.play_sfx then
        adapter.play_sfx(name)
    end
end

---按钮音效绑定
local function tpl_play_sfx_btn(btn_ui)
    if not btn_ui then return end
    btn_ui:add_local_event('鼠标-移入', function()
        tpl_play_sfx("Enter")
    end)
end

---安全获取 UI 子节点
local function tpl_get_child(parent, name)
    if not parent then return nil end
    return parent:get_child(name)
end

-- ---------------------------------------------------------------------------
-- GameSettleRewardCmp — 单个奖励格子
-- ---------------------------------------------------------------------------

local reward_cmps = {} ---@type table<integer, table>

local function create_reward_cmp(grid_ui, slot_idx)
    local self = {
        _ui     = tpl_get_child(grid_ui, tostring(slot_idx)),
        _slot   = slot_idx,
        _data   = nil,
        _locked = false,
    }

    if not self._ui then
        return self
    end

    local icon_img   = tpl_get_child(self._ui, "icon")
    local qty_text   = tpl_get_child(self._ui, "quantity_TEXT")
    local bg         = tpl_get_child(self._ui, "bg")
    local lock_mask  = tpl_get_child(self._ui, "lock")

    local function refresh()
        local player_id = adapter.get_local_player_id()
        local rewards = adapter.get_rewards(player_id)
        self._data = rewards and rewards[slot_idx] or nil

        if self._data then
            if icon_img then
                icon_img:set_image(self._data.icon)
            end
            if qty_text then
                qty_text:set_text(self._data.quantity > 0 and tostring(self._data.quantity) or "")
            end
            if bg and params.res.quality_bg then
                local bg_img = params.res.quality_bg[self._data.quality]
                if bg_img then
                    bg:set_image(bg_img)
                end
            end
            self._ui:set_visible(true)
        else
            if icon_img then
                icon_img:set_image(params.res.empty_icon or 999)
            end
            if qty_text then
                qty_text:set_text("")
            end
            if bg then
                bg:set_image(params.res.empty_icon or 999)
            end
            self._ui:set_visible(false)
        end

        -- 恢复锁定状态
        if lock_mask then
            lock_mask:set_visible(self._locked)
        end
    end

    local function set_locked(locked)
        self._locked = locked
        if lock_mask then
            lock_mask:set_visible(locked)
        end
    end

    -- 鼠标悬停事件
    self._ui:add_local_event('鼠标-移入', function()
        if not self._data then return end
        adapter.on_show_tooltip(self._data, self._ui)
    end)

    self._ui:add_local_event('鼠标-移出', function()
        if adapter.on_hide_tooltip then
            adapter.on_hide_tooltip()
        end
    end)

    -- 音效
    self._ui:add_local_event('鼠标-移入', function()
        tpl_play_sfx("Enter")
    end)

    return {
        refresh    = refresh,
        set_locked = set_locked,
        get_data   = function() return self._data end,
    }
end

-- ---------------------------------------------------------------------------
-- 内部 — 刷新奖励列表（前置声明，create_settle_popup 中会引用）
-- ---------------------------------------------------------------------------

local function refresh_rewards_internal(cmp_list)
    local player_id = adapter.get_local_player_id()
    local rewards = adapter.get_rewards(player_id) or {}

    -- 动态扩展奖励格子
    local max_slots = math.max(#rewards, params.max_rewards or 32)
    for i = #cmp_list + 1, max_slots do
        local grid_ui = ui.settle_reward_grid
        cmp_list[i] = create_reward_cmp(grid_ui, i)
    end

    for _, cmp in ipairs(cmp_list) do
        if cmp.refresh then
            cmp.refresh()
        end
    end
end

-- ---------------------------------------------------------------------------
-- GameSettlePlayerView — 单个玩家行
-- ---------------------------------------------------------------------------

local player_views = {} ---@type table<integer, table>

local function create_player_view(root_ui, slot_idx)
    local self = {
        _root = root_ui,
        _slot = slot_idx,
    }

    local avatar_icon  = tpl_get_child(root_ui, "avartar.icon")
    local name_text    = tpl_get_child(root_ui, "name_TEXT")
    local power_text   = tpl_get_child(root_ui, "power_TEXT")
    local level_text   = tpl_get_child(root_ui, "level_TEXT")
    local kill_text    = tpl_get_child(root_ui, "kill_TEXT")
    local bond_text    = tpl_get_child(root_ui, "bond_TEXT")
    local hero_list    = tpl_get_child(root_ui, "hero_LIST")

    local function refresh()
        if not adapter.is_valid_slot(slot_idx) then
            root_ui:set_visible(false)
            return
        end

        root_ui:set_visible(true)
        local summary = adapter.get_player_summary(slot_idx)

        if avatar_icon then
            avatar_icon:set_image(summary.icon)
        end
        if name_text then
            name_text:set_text(summary.name)
            local color = summary.is_local and
                (params.ui.colors and params.ui.colors.local_player or "#ffb165") or
                (params.ui.colors and params.ui.colors.other_player or "#dbc1a9")
            name_text:set_text_color_hex(color)
        end
        if power_text then
            power_text:set_text(tpl_format_number(summary.power))
        end
        if level_text then
            level_text:set_text("Lv." .. summary.level)
        end
        if kill_text then
            kill_text:set_text(tostring(summary.kills))
        end
        if bond_text then
            bond_text:set_text(tostring(summary.bond_count))
        end

        -- 吸收英雄图标（最多 10 个槽位）
        if hero_list then
            for i = 1, 10 do
                local slot = tpl_get_child(hero_list, tostring(i))
                if not slot then break end

                if summary.hero_icons and summary.hero_icons[i] then
                    slot:set_visible(true)
                    local icon = tpl_get_child(slot, "icon")
                    if icon then
                        icon:set_image(summary.hero_icons[i])
                    end
                else
                    slot:set_visible(false)
                end
            end
        end
    end

    return {
        refresh = refresh,
    }
end

-- ---------------------------------------------------------------------------
-- GameSettlePopup — 主结算面板
-- ---------------------------------------------------------------------------

local settle_popup = nil

local function create_settle_popup()
    local panel_ui    = ui.settle_panel
    local quit_btn    = ui.settle_quit_btn
    local continue_btn = ui.settle_continue_btn
    local player_list = ui.settle_player_list
    local reward_grid = ui.settle_reward_grid
    local win_pic     = ui.settle_win_pic

    local max_players = params.max_players or 4
    local max_rewards = params.max_rewards or 32

    local player_view_list = {}
    local reward_cmp_list  = {}

    -- 初始化玩家视图
    for i = 1, max_players do
        local child = tpl_get_child(player_list, tostring(i))
        if child then
            player_view_list[i] = create_player_view(child, i)
        end
    end

    -- 初始化奖励格子
    for i = 1, max_rewards do
        reward_cmp_list[i] = create_reward_cmp(reward_grid, i)
    end

    -- 退出按钮
    quit_btn:add_local_event('左键-点击', function()
        local pid = adapter.get_local_player_id()
        adapter.on_quit(pid)
    end)
    tpl_play_sfx_btn(quit_btn)

    -- 继续按钮
    local first_fold = true
    continue_btn:add_local_event('左键-点击', function()
        local pid = adapter.get_local_player_id()
        adapter.on_continue(pid)
        panel_ui:set_visible(false)
        state.is_showing = false

        if first_fold then
            first_fold = false
            if adapter.on_first_fold_anim then
                adapter.on_first_fold_anim()
            end
        end
    end)
    tpl_play_sfx_btn(continue_btn)

    -- 订阅奖励变化
    local unsubscribe_settle = nil
    if adapter.on_settle_changed then
        unsubscribe_settle = adapter.on_settle_changed(function()
            refresh_rewards_internal(reward_cmp_list)
        end)
    end

    local function show(is_win)
        -- 标题图
        if win_pic then
            win_pic:set_image(is_win and params.res.win_img or params.res.lose_img)
        end

        -- 刷新玩家列表
        for _, view in ipairs(player_view_list) do
            view.refresh()
        end

        -- 刷新奖励
        refresh_rewards_internal(reward_cmp_list)

        -- 胜负按钮
        if is_win then
            quit_btn:set_visible(false)
            continue_btn:set_visible(true)
        else
            quit_btn:set_visible(true)
            continue_btn:set_visible(false)
        end

        panel_ui:set_visible(true)
        state.is_showing = true
    end

    local function hide()
        panel_ui:set_visible(false)
        state.is_showing = false
    end

    local function destroy()
        if unsubscribe_settle then
            unsubscribe_settle()
            unsubscribe_settle = nil
        end
    end

    return {
        show    = show,
        hide    = hide,
        destroy = destroy,
    }
end

-- ---------------------------------------------------------------------------
-- GameWinPopup — 胜利插屏
-- ---------------------------------------------------------------------------

local win_popup = nil

local function create_win_popup()
    local panel    = ui.win_panel
    local close_btn = ui.win_close_btn

    close_btn:add_local_event('左键-点击', function()
        local pid = adapter.get_local_player_id()
        adapter.on_quit(pid)
    end)
    tpl_play_sfx_btn(close_btn)

    return {
        show = function()
            panel:set_visible(true)
        end,
        hide = function()
            panel:set_visible(false)
        end,
    }
end

-- ---------------------------------------------------------------------------
-- GameLosePopup — 失败插屏
-- ---------------------------------------------------------------------------

local lose_popup = nil

local function create_lose_popup()
    local panel    = ui.lose_panel
    local close_btn = ui.lose_close_btn

    close_btn:add_local_event('左键-点击', function()
        local pid = adapter.get_local_player_id()
        adapter.on_quit(pid)
    end)
    tpl_play_sfx_btn(close_btn)

    return {
        show = function()
            panel:set_visible(true)
        end,
        hide = function()
            panel:set_visible(false)
        end,
    }
end

-- ---------------------------------------------------------------------------
-- 公开 API
-- ---------------------------------------------------------------------------

---@param user_adapter GameSettleAdapter
---@param user_params  table
function M.setup(user_adapter, user_params)
    tpl_validate_adapter(user_adapter)
    adapter = user_adapter
    params  = user_params or {}

    -- 默认值
    params.max_players = params.max_players or 4
    params.max_rewards = params.max_rewards or 32
    params.res = params.res or {}
    params.res.empty_icon = params.res.empty_icon or 999
    params.res.win_img    = params.res.win_img    or 134223062
    params.res.lose_img   = params.res.lose_img   or 134243407
    params.ui = params.ui or {}
    params.ui.colors = params.ui.colors or {}
    params.ui.colors.local_player = params.ui.colors.local_player or "#ffb165"
    params.ui.colors.other_player = params.ui.colors.other_player or "#dbc1a9"

    -- 校验必填 UI UUID
    local required_ui = {
        'settle_panel',
        'settle_quit_btn',
        'settle_continue_btn',
        'settle_player_list',
        'settle_reward_grid',
        'settle_win_pic',
        'win_panel',
        'win_close_btn',
        'lose_panel',
        'lose_close_btn',
    }
    for _, key in ipairs(required_ui) do
        assert(params.ui[key], 'params.ui.' .. key .. ' is required')
    end

    -- 解析 UI（降级：找不到的节点 warning 而非 assert，避免部分路径不可达时整体失败）
    local local_player = y3.player.get_by_id(adapter.get_local_player_id())
    for _, key in ipairs(required_ui) do
        local ok, result = pcall(function()
            return y3.ui.get_ui(local_player, params.ui[key])
        end)
        if ok and result then
            ui[key] = result
        else
            log.warn('[c-game-settle] UI not found: ' .. tostring(params.ui[key]) .. ' (' .. key .. ')')
        end
    end
    assert(ui.settle_panel, 'settle_panel is required but not found: ' .. tostring(params.ui.settle_panel))

    -- 创建子模块
    settle_popup = create_settle_popup()
    win_popup    = create_win_popup()
    lose_popup   = create_lose_popup()

    state = {}
end

---显示结算面板
---@param is_win boolean
function M.show_settle(is_win)
    if not adapter then error('M.setup(adapter, params) not called') end
    assert(settle_popup, 'settle_popup not initialized')
    settle_popup.show(is_win)
end

---隐藏结算面板
function M.hide_settle()
    if settle_popup then
        settle_popup.hide()
    end
end

---显示胜利插屏
function M.show_win_splash()
    if not adapter then error('M.setup(adapter, params) not called') end
    if win_popup then
        win_popup.show()
    end
end

---显示失败插屏
function M.show_lose_splash()
    if not adapter then error('M.setup(adapter, params) not called') end
    if lose_popup then
        lose_popup.show()
    end
end

---销毁结算模块（取消事件订阅）
function M.destroy()
    if settle_popup and settle_popup.destroy then
        settle_popup.destroy()
    end
    settle_popup = nil
    win_popup    = nil
    lose_popup   = nil
    adapter      = nil
    state        = {}
end

return M
