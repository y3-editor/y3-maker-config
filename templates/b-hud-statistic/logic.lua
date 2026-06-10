--- =========================================================================
--- Y3 功能模板 · logic.lua  (B 级 · 参数注入式)
--- =========================================================================
---
--- @template-id   b-hud-statistic          -- kebab-case (B 级前缀 b-)
--- @grade         B                        -- 等级
--- @version       v0.1.0                   -- 首次导出固定
--- @entry         M.setup(params)          -- 融合入口
--- @params        ui_paths, local_player_id, ui_fetch, get_platform_icon,
---                get_player_name, get_ability_info, callbacks
--- @source        global_script/gamePlay/ui/hud/StatisticView.lua
--- @description   战斗 HUD 右侧统计面板：玩家列表、伤害/击杀/承伤输出统计、技能伤害排行
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块入口点
---   2. 所有外部依赖通过 M.setup(params) 传入
---   3. UI 路径通过 params.ui_paths 传入
---   4. 本模板不自行注册全局事件；融合侧通过公开 API 推送数据
--- =========================================================================

local M = {}

-- ============================================================================
-- params 默认值
-- ============================================================================
local params = {
    -- ---- 必填 ----
    -- ui_paths: UI 节点 UUID 映射
    -- ui_paths = {
    --     root         = "74e6468e-a718-469c-97bc-8df88c5be3d0",  -- 统计面板根节点
    --     damage_btn   = "0e8ff27b-30aa-4202-b166-99bfb275af09",  -- 伤害按钮
    --     ability_btn  = "011ae92d-5619-4089-82b7-a07eb32fd5a3",  -- 技能按钮
    --     ability_bg   = "c6006d77-3361-4a1f-9a85-39c7e2f5b1b7",  -- 技能详情背景
    --     ability_view = "ee8f12d3-4c61-4d98-8243-677869dc0f21",  -- 技能详情列表区
    --     team_parent  = "173308dd-a4a6-4be2-a909-5f9556bc3c19",   -- 玩家列表父节点
    --     damage_parent = "86501027-c34d-43fe-bbc5-10d4595988fb",  -- 伤害列表父节点
    --     page_btns    = {                                         -- 翻页按钮列表
    --         { btn = "c9932191-8424-4596-80ff-be9683f11ce9", txt = "9d001a1a-ed56-4634-84dd-af6380657614" },
    --         { btn = "ddd70cd1-5e59-4c50-97cb-414422b0c9e1", txt = "f893ca57-f14f-44dc-9f5e-7d621bec8e5f" },
    --     },
    -- },
    -- local_player_id: 本地玩家 ID
    -- ui_fetch: function(playerId, uuid) → UI node
    -- get_platform_icon: function(playerId) → icon_id
    -- get_player_name: function(playerId) → name
    -- get_ability_info: function(abilityId) → { icon, name }

    -- ---- 可选 ----
    -- resources: 图标资源 ID
    -- resources = {
    --     damage_btn_on  = { 134218925, 134244717, 134267360, 134236153 },  -- 展开时四态
    --     damage_btn_off = { 134253966, 134253966, 134254583, 134229178 },  -- 收起时四态
    --     page_l_sel     = { 134268609, 134246778, 134230265, 134232119 },
    --     page_l_default = { 134281604, 134257235, 134258904, 134270632 },
    --     page_r_sel     = { 134235322, 134267463, 134267598, 134246719 },
    --     page_r_default = { 134242476, 134220623, 134258904, 134255719 },
    --     rank_bg        = { 134243886, 134230175, 134259407, 134227373 },  -- 排名底色（按玩家 1-4）
    -- },
    -- player_count: 玩家数量（默认 4），用于初始化槽位
    -- player_count = 4,
    -- callbacks: 业务回调
    -- callbacks = {
    --     on_bind_audio    = nil,  -- function(uiNode) 音效绑定
    --     on_damage_update = nil,  -- function(damage_data) 外部通知
    -- },
    -- page_labels: 页码按钮文本
    -- page_labels = { "伤害", "秒伤", "击杀" },  -- 默认
}

local state = {}
local ui = {}

-- 伤害页签常量
local PAGE_DAMAGE = 1   -- 总伤害
local PAGE_DPS    = 2   -- BOSS秒伤
local PAGE_KILL   = 3   -- 承伤/击杀（按源工程为承伤页）

-- ============================================================================
-- 校验
-- ============================================================================
local function tpl_validate_params()
    assert(params.ui_paths, 'params.ui_paths is required')
    assert(params.ui_fetch, 'params.ui_fetch is required')
    assert(params.local_player_id, 'params.local_player_id is required')
    assert(params.get_platform_icon, 'params.get_platform_icon is required')
    assert(params.get_player_name, 'params.get_player_name is required')
end

-- ============================================================================
-- UI 初始化
-- ============================================================================
local function tpl_init_ui_nodes()
    local f = params.ui_fetch
    local pid = params.local_player_id
    local p = params.ui_paths

    ui.root        = f(pid, p.root)
    ui.damage_btn  = f(pid, p.damage_btn)
    ui.ability_btn = f(pid, p.ability_btn)
    ui.ability_bg  = f(pid, p.ability_bg)
    ui.ability_view = f(pid, p.ability_view)

    -- 翻页按钮
    ui.page_btns = {}
    if p.page_btns then
        for i, pb in ipairs(p.page_btns) do
            ui.page_btns[i] = {
                btn = f(pid, pb.btn),
                txt = f(pid, pb.txt),
            }
        end
    end

    -- 伤害排行槽位（最多 4 个玩家）
    ui.damage_slots = {}
    local damage_parent = p.damage_parent and f(pid, p.damage_parent)
    if damage_parent then
        for i = 1, 4 do
            local slot = damage_parent:get_child(tostring(i))
            if slot then
                ui.damage_slots[i] = {
                    root    = slot,
                    icon    = slot:get_child("mask.avatar_IMG"),
                    pro     = slot:get_child("player_PROG"),
                    text    = slot:get_child("player_PROG.info_TEXT"),
                    text2   = slot:get_child("player_PROG.info_TEXT2"),
                    prog_img = slot:get_child("player_PROG.progress_bar_img"),
                }
            end
        end
    end

    -- 技能伤害列表（动态创建，最多 30 条）
    ui.ability_slots = {}
end

-- ============================================================================
-- 数据缓存
-- ============================================================================
local cache = {
    -- cache.damage[page][playerId] = value
    damage   = { [PAGE_DAMAGE] = {}, [PAGE_DPS] = {}, [PAGE_KILL] = {} },
    total    = { [PAGE_DAMAGE] = 0, [PAGE_DPS] = 0, [PAGE_KILL] = 0 },
    -- cache.ability_damage[playerId][abilityId] = value
    ability_damage = {},
    -- cache.ability_cast[playerId][abilityId] = count
    ability_cast = {},
    -- cache.ability_info[abilityId] = { icon, name }
    ability_info = {},
    -- 当前页
    page = PAGE_DAMAGE,
}

---初始化玩家数据结构
local function tpl_init_player_cache(player_ids)
    for _, player_id in ipairs(player_ids) do
        for _, page in ipairs({ PAGE_DAMAGE, PAGE_DPS, PAGE_KILL }) do
            cache.damage[page][player_id] = cache.damage[page][player_id] or 0
        end
        cache.ability_damage[player_id] = cache.ability_damage[player_id] or {}
        cache.ability_cast[player_id] = cache.ability_cast[player_id] or {}
    end
end

-- ============================================================================
-- 数据推送 API（由融合侧调用）
-- ============================================================================

---累加伤害
---@param source_player_id integer  伤害来源玩家
---@param target_player_id integer  伤害目标玩家
---@param value number              伤害值
---@param ability_id? integer       技能 ID（可选，用于技能统计）
function M.add_damage(source_player_id, target_player_id, value, ability_id)
    -- 总伤害（page 1）
    cache.damage[PAGE_DAMAGE][source_player_id] = (cache.damage[PAGE_DAMAGE][source_player_id] or 0) + value
    cache.total[PAGE_DAMAGE] = cache.total[PAGE_DAMAGE] + value

    -- 技能伤害
    if ability_id then
        local ad = cache.ability_damage[source_player_id]
        if ad then
            ad[ability_id] = (ad[ability_id] or 0) + value
        end
    end

    -- 承伤（page 3）
    cache.damage[PAGE_KILL][target_player_id] = (cache.damage[PAGE_KILL][target_player_id] or 0) + value
    cache.total[PAGE_KILL] = cache.total[PAGE_KILL] + value

    -- 标记需要刷新
    cache._dirty_damage = true
    if ability_id then cache._dirty_ability = true end

    local cbs = params.callbacks or {}
    if cbs.on_damage_update then
        cbs.on_damage_update({ player_id = source_player_id, value = value, ability_id = ability_id })
    end
end

---累加击杀
---@param source_player_id integer
function M.add_kill(source_player_id)
    -- 源工程中击杀数存在 page 2（在 StatisticView 的 PAGE 2 是 BOSS秒伤，击杀是单独货币）
    -- 这里简化为维护击杀计数
    cache._kills = cache._kills or {}
    cache._kills[source_player_id] = (cache._kills[source_player_id] or 0) + 1
    cache._dirty_damage = true
end

---记录技能施放
---@param player_id integer
---@param ability_id integer
function M.add_ability_cast(player_id, ability_id)
    local ac = cache.ability_cast[player_id]
    if ac then
        ac[ability_id] = (ac[ability_id] or 0) + 1
    end
    -- 缓存技能基本信息
    if not cache.ability_info[ability_id] and params.get_ability_info then
        local info = params.get_ability_info(ability_id)
        if info then
            cache.ability_info[ability_id] = info
        end
    end
    cache._dirty_ability = true
end

---设置 BOSS DPS 数据（page 2）
---@param player_id integer
---@param dps_value number  秒伤
function M.set_boss_dps(player_id, dps_value)
    cache.damage[PAGE_DPS][player_id] = dps_value
    cache._dirty_damage = true
end

---重置所有统计数据
function M.reset_all()
    for _, page in ipairs({ PAGE_DAMAGE, PAGE_DPS, PAGE_KILL }) do
        cache.damage[page] = {}
        cache.total[page] = 0
    end
    cache.ability_damage = {}
    cache.ability_cast = {}
    cache.ability_info = {}
    cache._kills = {}
    cache._dirty_damage = true
    cache._dirty_ability = true
end

-- ============================================================================
-- UI 刷新
-- ============================================================================

---刷新伤害排行视图
local function tpl_refresh_damage_view(force)
    if not force and not cache._dirty_damage then return end
    if not ui.root or not ui.root:is_visible() then return end
    cache._dirty_damage = false

    local page = cache.page
    local list = cache.damage[page]
    if not list then return end

    -- 按值排序
    local sorted = {}
    for pid, val in pairs(list) do
        if val > 0 then
            sorted[#sorted + 1] = { player_id = pid, val = math.floor(val) }
        end
    end
    table.sort(sorted, function(a, b) return a.val > b.val end)

    local total = cache.total[page] or 1
    for i = 1, math.min(#(ui.damage_slots or {}), 4) do
        local slot = ui.damage_slots[i]
        local entry = sorted[i]
        if not entry then
            slot.root:set_visible(false)
        else
            local player_id = entry.player_id
            local val = entry.val
            local icon = params.get_platform_icon(player_id)
            local name = params.get_player_name(player_id)
            local ratio = total > 0 and (val / total) or 0

            slot.icon:set_image(icon)

            if page == PAGE_DPS then
                slot.text:set_text(string.format("%.0f/s  %s", val, name))
                slot.text2:set_text("")
            elseif page == PAGE_KILL then
                -- 击杀计数
                local kills = (cache._kills or {})[player_id] or 0
                total = 0
                for _, v in pairs(cache._kills or {}) do total = total + v end
                ratio = total > 0 and (kills / total) or 0
                slot.text:set_text(string.format("%d  %s", kills, name))
                slot.text2:set_text("")
            else
                slot.text:set_text(string.format("%d  %s", val, name))
                slot.text2:set_text("")
            end

            slot.pro:set_current_progress_bar_value(100 * ratio, 0.01)

            -- 排名底色
            local res = params.resources or {}
            local bg_icons = res.rank_bg
            if bg_icons and bg_icons[player_id] then
                slot.prog_img:set_image(bg_icons[player_id])
            end

            slot.root:set_visible(true)
        end
    end
end

---刷新技能伤害排行
local function tpl_refresh_ability_view(force)
    if not force and not cache._dirty_ability then return end
    if not ui.ability_view or not ui.ability_view:is_visible() then return end
    cache._dirty_ability = false

    local player_id = params.local_player_id
    local ad = cache.ability_damage[player_id] or {}
    local ac = cache.ability_cast[player_id] or {}

    -- 排序
    local sorted = {}
    for aid, val in pairs(ad) do
        sorted[#sorted + 1] = { ability_id = aid, val = val, cnt = ac[aid] or 1 }
    end
    table.sort(sorted, function(a, b) return a.val > b.val end)

    local total_damage = cache.total[PAGE_DAMAGE] or 1

    -- 动态更新技能槽位
    for i = 1, 30 do
        if not ui.ability_slots[i] then
            -- 动态创建槽位（从 ability_view 的模板复制）
            if ui.ability_view then
                local child = ui.ability_view:get_child(tostring(i))
                if child then
                    ui.ability_slots[i] = {
                        root = child,
                        icon = child:get_child("bg.mask.avatar_IMG"),
                        pro  = child:get_child("bg.progress_BAR"),
                        text = child:get_child("bg.info_TEXT"),
                        cnt  = child:get_child("bg.cnt_TEXT"),
                    }
                end
            end
        end

        local slot = ui.ability_slots[i]
        local entry = sorted[i]
        if not entry then
            if slot then slot.root:set_visible(false) end
        else
            if not slot then goto continue end
            local info = cache.ability_info[entry.ability_id]
                or (params.get_ability_info and params.get_ability_info(entry.ability_id))
                or {}
            slot.icon:set_image(info.icon or 999)
            slot.text:set_text(tostring(math.floor(entry.val)))
            slot.cnt:set_text(string.format("%s(%d)", info.name or tostring(entry.ability_id), entry.cnt))
            slot.pro:set_current_progress_bar_value(100 * (entry.val / total_damage), 0.01)
            slot.root:set_visible(true)
        end
        ::continue::
    end
end

---强制刷新（由融合侧在每帧或定时调用）
function M.refresh()
    tpl_refresh_damage_view(true)
    tpl_refresh_ability_view(true)
end

---按需刷新（不传 force 则仅脏数据时才刷新）
function M.refresh_if_dirty()
    tpl_refresh_damage_view(false)
    tpl_refresh_ability_view(false)
end

-- ============================================================================
-- 交互事件
-- ============================================================================

---切换页面
---@param page integer  1=总伤害, 2=BOSS秒伤, 3=击杀
function M.switch_page(page)
    if page == cache.page then return end

    local res = params.resources or {}

    -- 取消旧页高亮
    local old_pb = ui.page_btns[cache.page]
    if old_pb then
        -- 刷新旧页按钮为默认态
        local icons = (cache.page <= 1) and res.page_l_default or res.page_r_default
        if icons then
            for i = 1, 4 do
                old_pb.btn:set_btn_status_image(i, icons[i])
            end
        end
        -- 文本颜色恢复
        -- TODO: 融合侧提供 set_text_color_hex
    end

    -- 设置新页
    cache.page = page

    -- 高亮新页
    local new_pb = ui.page_btns[page]
    if new_pb then
        local icons = (page <= 1) and res.page_l_sel or res.page_r_sel
        if icons then
            for i = 1, 4 do
                new_pb.btn:set_btn_status_image(i, icons[i])
            end
        end
    end

    M.refresh()
end

---切换伤害面板显隐
function M.toggle_damage_panel()
    local visible = ui.root:is_visible()
    ui.root:set_visible(not visible)

    local res = params.resources or {}
    local btn_title = ui.damage_btn:get_child("title")
    if btn_title then btn_title:set_visible(visible) end

    if not visible then
        -- 展开
        local icons = res.damage_btn_on
        if icons then
            for i = 1, 4 do
                ui.damage_btn:set_btn_status_image(i, icons[i])
            end
        end
    else
        -- 收起
        local icons = res.damage_btn_off
        if icons then
            for i = 1, 4 do
                ui.damage_btn:set_btn_status_image(i, icons[i])
            end
        end
        M.refresh()
    end
end

---切换技能详情面板显隐
function M.toggle_ability_panel()
    local visible = ui.ability_view:is_visible()
    ui.ability_view:set_visible(not visible)
    -- 旋转箭头
    -- TODO: set_widget_relative_rotation(visible and 0 or 180)

    if not visible then
        M.refresh()
    end
end

-- ============================================================================
-- 事件注册
-- ============================================================================
local function tpl_register_events()
    local cbs = params.callbacks or {}

    -- 伤害面板按钮
    if ui.damage_btn then
        ui.damage_btn:add_local_event('左键-按下', function() M.toggle_damage_panel() end)
        if cbs.on_bind_audio then cbs.on_bind_audio(ui.damage_btn) end
    end

    -- 技能面板按钮
    if ui.ability_btn then
        ui.ability_btn:add_local_event('左键-按下', function() M.toggle_ability_panel() end)
        if cbs.on_bind_audio then cbs.on_bind_audio(ui.ability_btn) end
    end

    -- 翻页按钮
    if ui.page_btns then
        local page_labels = params.page_labels or { "伤害", "秒伤", "击杀" }
        for page, pb in ipairs(ui.page_btns) do
            if pb.btn then
                pb.btn:add_local_event('左键-按下', function() M.switch_page(page) end)
                if cbs.on_bind_audio then cbs.on_bind_audio(pb.btn) end
            end
            -- 设置页签文本
            if pb.txt and page_labels[page] then
                pb.txt:set_text(page_labels[page])
            end
        end
    end

    -- 初始默认隐藏技能按钮/背景
    if ui.ability_btn then ui.ability_btn:set_visible(false) end
    if ui.ability_bg then ui.ability_bg:set_visible(false) end
end

-- ============================================================================
-- 入口
-- ============================================================================
---@param user_params table
function M.setup(user_params)
    user_params = user_params or {}
    for k, v in pairs(user_params) do
        if k == 'ui_paths' and type(v) == 'table' then
            for upk, upv in pairs(v) do params.ui_paths[upk] = upv end
        elseif k == 'resources' and type(v) == 'table' then
            params.resources = params.resources or {}
            for rk, rv in pairs(v) do params.resources[rk] = rv end
        elseif k == 'callbacks' and type(v) == 'table' then
            params.callbacks = params.callbacks or {}
            for ck, cv in pairs(v) do params.callbacks[ck] = cv end
        else
            params[k] = v
        end
    end

    tpl_validate_params()
    tpl_init_ui_nodes()
    tpl_register_events()

    -- 初始化玩家数据
    local player_ids = params.player_ids or {}
    tpl_init_player_cache(player_ids)

    -- 初始隐藏面板
    if ui.root then ui.root:set_visible(false) end
    if ui.ability_view then ui.ability_view:set_visible(false) end

    state._inited = true
end

---获取初始化状态
function M.is_inited()
    return state._inited == true
end

return M
