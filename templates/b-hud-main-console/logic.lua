--- =========================================================================
--- Y3 功能模板 · logic.lua  (B 级 · 参数注入式)
--- =========================================================================
---
--- @template-id   b-hud-main-console       -- kebab-case (B 级前缀 b-)
--- @grade         B                        -- 等级
--- @version       v0.1.0                   -- 首次导出固定
--- @entry         M.setup(params)          -- 融合入口
--- @params        ui_paths, local_player_id, ui_fetch, get_unit_attr,
---                get_unit_level, get_unit_exp, get_item_config, callbacks
--- @source        global_script/gamePlay/ui/hud/MainHUD.lua + TargetInfoView.lua
--- @description   战斗 HUD 底部控制台：选中目标属性/名称/HP/MP/Buff + 英雄状态/等级/经验/技能/物品栏
---
--- 融合契约：
---   1. 所有外部依赖通过 M.setup(params) 传入
---   2. UI 路径通过 params.ui_paths 传入
---   3. 本模板不自行注册全局事件
--- =========================================================================

local M = {}

-- ============================================================================
-- params
-- ============================================================================
local params = {
    -- ---- 必填 ----
    -- ui_paths: 所有 UI 节点 UUID 映射
    -- ui_paths = {
    --     -- 目标信息区 (TargetInfoView)
    --     target_root      = "a1fd1423-2a1d-4304-8b01-d2d75352373d",
    --     target_icon      = "96e4b9d8-dad6-445e-8f8d-19c88421c1e3",
    --     target_name      = "ec101d2a-ce2e-44aa-ba92-3719b92880e4",
    --     target_monster_tag = "45515128-1851-4f3a-890c-e8d150ba8649",
    --     target_main_attr = "25f98dc0-353c-42fc-8651-b73493fc9495",
    --     target_buff_view = "ed6e589f-6e41-405b-b401-832daaef35bf",
    --     target_ability_view = "1659a0aa-576d-462a-8cde-00c048032c05",
    --     target_hp_prog   = "784c4fb1-1f3d-4378-ab0e-5f74321f0a4f",
    --     target_hp_text   = "ccc17d2d-ad33-4998-93b5-6f151428e873",
    --     target_mp_prog   = "11a49061-49b6-4d10-a380-634778c195ef",
    --     target_mp_text   = "4420aa4f-a0fd-4cd6-898c-623c66625e2c",
    --     target_attr_parent = "84f2f7bc-8451-4e86-86aa-b3a82f394903",  -- 目标属性列表父节点
    --     target_bond_view = "11da8526-56c0-4da0-86ac-d423334284c5",    -- 羁绊视图（可选）
    --     -- 英雄状态区
    --     hero_icon        = "cb9b4a46-9283-42f6-83c2-02ca6c8900be",
    --     hero_name        = "191a3f6a-6552-4a44-a222-6e24d6def18a",
    --     lv_text          = "c7e2fb01-f407-462a-b49a-4292095a184f",
    --     exp_prog         = "dccdf7d8-0434-4b40-9653-78121251bb7c",
    --     exp_text         = "7ff1b8ed-6fa6-4666-b7e4-69c77b0b4bb5",
    --     hp_prog          = "b83ea37a-2e00-40c9-b44b-6ce66b096f62",
    --     hp_text          = "caa2d29a-5a68-4c0f-aeea-cbdad1983c94",
    --     hp_extra_text    = "3e31532d-87d9-44c2-ab84-4bf5cd4ceb6b",
    --     mp_prog          = "41567eec-14cc-4f5a-a7b8-a14a0d79490c",
    --     mp_text          = "355b75f9-26da-4524-9f51-082afe5a0fc5",
    --     mp_extra_text    = "a06c35f5-f69c-41b2-b29e-040af342d37d",
    --     revive_prog      = "b384dfc5-5cc0-48fa-9ea6-71b28083f4e5",
    --     revive_text      = "b5a830c5-c5ec-422d-b7c5-162dfb2dac3c",
    --     attr_btn         = "1e630bcc-eb22-41b5-aeaa-50efe8a59f7d",
    --     attr_detail_view = "1f03fbbf-70d2-4000-b7d9-b14150cbe644",
    --     buff_view        = "f3b2c9e0-2006-4d96-b21c-d4433ddf7210",
    --     ability_d_btn    = "e1d035bb-75ba-47e4-8a92-a2c207692b06",
    --     ability_f2_btn   = "1e80c820-66f5-4e21-9c52-49589113c7e5",
    --     ability_main_btn = "dd00aa83-a903-4989-a6d0-72e540b4db75",
    --     bag_btn          = "928baf7c-9bac-4bb8-9462-4e0d836deaad",
    --     item_view        = "af1fe15f-b962-4994-9985-910b8a4ad12a",      -- 物品栏父节点
    --     attr_list_parent = "b42090f3-cc97-422c-b530-9fe2ab7f7ab5",     -- 主属性列表父节点
    --     attr_list4_parent = "8ce4403f-8c2f-4256-8921-1bcf1d40f478",    -- 次属性列表父节点
    --     attr_list2       = { "02bf9681-edee-4684-9b82-787d6061eb46", ... }, -- 力量/敏捷/智力
    --     attr_list3       = { "ec933e1d-fe8d-4655-8fa7-2d34b0c9cc53", ... }, -- 额外加成
    -- },
    -- local_player_id: 本地玩家 ID
    -- ui_fetch: function(pid, uuid) → UI
    -- get_unit_attr: function(unit, attr_name_or_id) → value
    -- get_unit_level: function(unit) → level
    -- get_unit_exp: function(unit) → cur_exp, upgrade_exp

    -- ---- 可选 ----
    -- callbacks: 业务回调
    -- callbacks = {
    --     on_select_unit        = nil,  -- function(unit) 选中单位时
    --     on_deselect_unit      = nil,  -- function() 取消选中
    --     on_attr_btn_click     = nil,  -- function() 属性面板按钮点击
    --     on_bag_btn_click      = nil,  -- function() 背包按钮点击
    --     on_ability_click      = nil,  -- function(key) 技能按钮点击
    --     on_attr_hover         = nil,  -- function(index, player_id) 属性 hover
    --     on_attr_hover_out     = nil,  -- function()
    --     on_buff_hover         = nil,  -- function(buff, index, player_id)
    --     on_buff_hover_out     = nil,  -- function()
    --     on_bind_audio         = nil,  -- function(uiNode)
    --     get_hero_config       = nil,  -- function(heroId) → { icon, name, main_attr }
    --     get_ability_ctrl      = nil,  -- function(playerId, key) → baseAbility
    --     get_bag               = nil,  -- function(playerId, bagName) → bag
    --     get_item_slot         = nil,  -- function(bag, slot) → item
    --     format_number         = nil,  -- function(n, useK?) → str  (原 FormatNumber_3)
    --     get_attr_config       = nil,  -- function() → { getById, formatAttrValue }
    --     get_max_lv            = nil,  -- function() → maxLv
    --     get_main_attr_type    = nil,  -- function(unit) → 0/1/2/3
    -- },
    -- resources: 图标资源（主属性图标等）
    -- resources = {
    --     main_attr_icons = { 力图标, 敏图标, 智图标, 通用图标 },
    --     monster_tag_elite = 134xxx,
    --     monster_tag_boss  = 134xxx,
    -- },
    -- target_attr_ids: 目标属性ID列表 { 30, 66, 38, 1, 8, 15 }
    -- target_attr_ids = { 30, 66, 38, 1, 8, 15 },
    -- hero_attr_ids: 英雄主属性ID { 30, 1, 8, 15 }
    -- hero_attr_ids = { 30, 1, 8, 15 },
    -- hero_sub_attr_ids: 英雄次属性ID { 66, 38 }
    -- hero_sub_attr_ids = { 66, 38 },
    -- item_bag_name: 物品栏名称
    -- item_bag_name = "物品栏",
}

local state = {}
local ui = {}

-- ============================================================================
-- 校验
-- ============================================================================
local function tpl_validate_params()
    assert(params.ui_paths, 'params.ui_paths is required')
    assert(params.ui_fetch, 'params.ui_fetch is required')
    assert(params.local_player_id, 'params.local_player_id is required')
    assert(params.get_unit_attr, 'params.get_unit_attr is required')
end

-- ============================================================================
-- UI 初始化
-- ============================================================================
local function tpl_init_ui_nodes()
    local f = params.ui_fetch
    local pid = params.local_player_id
    local p = params.ui_paths

    -- 目标信息区
    ui.target = {
        root        = p.target_root and f(pid, p.target_root),
        icon        = p.target_icon and f(pid, p.target_icon),
        name        = p.target_name and f(pid, p.target_name),
        monster_tag = p.target_monster_tag and f(pid, p.target_monster_tag),
        main_attr   = p.target_main_attr and f(pid, p.target_main_attr),
        buff_view   = p.target_buff_view and f(pid, p.target_buff_view),
        hp_prog     = p.target_hp_prog and f(pid, p.target_hp_prog),
        hp_text     = p.target_hp_text and f(pid, p.target_hp_text),
        mp_prog     = p.target_mp_prog and f(pid, p.target_mp_prog),
        mp_text     = p.target_mp_text and f(pid, p.target_mp_text),
        attr_parent = p.target_attr_parent and f(pid, p.target_attr_parent),
    }

    -- 英雄状态区
    ui.hero = {
        icon       = p.hero_icon and f(pid, p.hero_icon),
        name       = p.hero_name and f(pid, p.hero_name),
        lv_text    = p.lv_text and f(pid, p.lv_text),
        exp_prog   = p.exp_prog and f(pid, p.exp_prog),
        exp_text   = p.exp_text and f(pid, p.exp_text),
        hp_prog    = p.hp_prog and f(pid, p.hp_prog),
        hp_text    = p.hp_text and f(pid, p.hp_text),
        hp_extra   = p.hp_extra_text and f(pid, p.hp_extra_text),
        mp_prog    = p.mp_prog and f(pid, p.mp_prog),
        mp_text    = p.mp_text and f(pid, p.mp_text),
        mp_extra   = p.mp_extra_text and f(pid, p.mp_extra_text),
        revive_prog = p.revive_prog and f(pid, p.revive_prog),
        revive_text = p.revive_text and f(pid, p.revive_text),
        attr_btn   = p.attr_btn and f(pid, p.attr_btn),
        buff_view  = p.buff_view and f(pid, p.buff_view),
        buff_list  = {}, -- 从 buff_view 子节点获取
    }

    -- 技能按钮
    ui.ability = {
        d    = p.ability_d_btn and f(pid, p.ability_d_btn),
        f2   = p.ability_f2_btn and f(pid, p.ability_f2_btn),
        main = p.ability_main_btn and f(pid, p.ability_main_btn),
    }

    -- 物品栏
    ui.bag = {
        btn      = p.bag_btn and f(pid, p.bag_btn),
        item_view = p.item_view and f(pid, p.item_view),
        slots    = {},
    }

    -- 英雄属性列表
    ui.attr_list_parent  = p.attr_list_parent and f(pid, p.attr_list_parent)
    ui.attr_list4_parent = p.attr_list4_parent and f(pid, p.attr_list4_parent)
    ui.attr_list2 = {}
    if p.attr_list2 then
        for i, uuid in ipairs(p.attr_list2) do
            ui.attr_list2[i] = f(pid, uuid)
        end
    end
    ui.attr_list3 = {}
    if p.attr_list3 then
        for i, uuid in ipairs(p.attr_list3) do
            ui.attr_list3[i] = f(pid, uuid)
        end
    end

    -- buff 子节点列表
    if ui.hero.buff_view then
        local children = ui.hero.buff_view:get_childs()
        if children then
            for i, child in ipairs(children) do
                ui.hero.buff_list[i] = child
            end
        end
    end

    -- 物品栏子节点
    if ui.bag.item_view then
        for i = 1, 6 do
            ui.bag.slots[i] = ui.bag.item_view:get_child(tostring(i))
        end
    end

    -- 目标 buff 子节点
    if ui.target.buff_view then
        local children = ui.target.buff_view:get_childs()
        ui.target.buff_list = children or {}
    end
end

-- ============================================================================
-- 内部工具
-- ============================================================================

---格式化数字（默认简单版本，可由 format_number 回调覆盖）
local function tpl_format_number(n, use_k)
    local cb = params.callbacks or {}
    if cb.format_number then return cb.format_number(n, use_k) end
    if n >= 10000 and use_k then
        return string.format("%.1f万", n / 10000)
    end
    return tostring(math.floor(n))
end

---设置进度条
local function tpl_set_progress(prog_widget, ratio)
    if not prog_widget then return end
    ratio = math.min(1, math.max(0, ratio))
    prog_widget:set_ui_size(prog_widget:get_width() * ratio, prog_widget:get_height())
end

-- ============================================================================
-- 英雄状态刷新
-- ============================================================================

---刷新英雄基础信息（头像/名称）
---@param hero_id? integer  英雄配置 ID
function M.refresh_hero_info(hero_id)
    local cbs = params.callbacks or {}
    if not hero_id or not cbs.get_hero_config then return end
    local cfg = cbs.get_hero_config(hero_id)
    if not cfg then return end
    if ui.hero.icon then ui.hero.icon:set_image(cfg.icon) end
    if ui.hero.name then ui.hero.name:set_text(cfg.name) end
end

---刷新英雄等级/经验
---@param unit Unit
function M.refresh_hero_level_exp(unit)
    if not unit then return end
    local lv = params.get_unit_level(unit)
    local cur_exp = params.get_unit_exp(unit)
    local next_exp = unit.get_upgrade_exp and unit:get_upgrade_exp() or 1

    local cbs = params.callbacks or {}
    local max_lv = cbs.get_max_lv and cbs.get_max_lv() or 999

    if ui.hero.lv_text then
        ui.hero.lv_text:set_text(tostring(unit.storage_get and unit:storage_get('lv') or lv))
    end
    if ui.hero.exp_prog then
        if lv >= max_lv then
            ui.hero.exp_prog:set_current_progress_bar_value(100)
            if ui.hero.exp_text then ui.hero.exp_text:set_text("已满级") end
        else
            ui.hero.exp_prog:set_current_progress_bar_value(cur_exp / next_exp * 100)
            if ui.hero.exp_text then
                ui.hero.exp_text:set_text(string.format("%d/%d", cur_exp, next_exp))
            end
        end
    end
end

---刷新英雄生命值
---@param unit Unit
function M.refresh_hero_hp(unit)
    if not unit then return end
    local max_hp = math.floor(params.get_unit_attr(unit, "最大生命") or 0)
    local cur_hp = math.floor(params.get_unit_attr(unit, "生命") or 0)
    if ui.hero.hp_text then
        ui.hero.hp_text:set_text(string.format("%d/%d", cur_hp, max_hp))
    end
    if ui.hero.hp_prog then
        -- 源工程用 SequenceProgress 的 setProg
        -- 简化：设进度条 0-100
        local ratio = max_hp > 0 and (cur_hp / max_hp) or 0
        ui.hero.hp_prog:set_current_progress_bar_value(ratio * 100, 0)
    end
end

---刷新英雄魔法值
---@param unit Unit
function M.refresh_hero_mp(unit)
    if not unit then return end
    local max_mp = math.floor(params.get_unit_attr(unit, "最大魔法") or 0)
    local cur_mp = math.floor(params.get_unit_attr(unit, "魔法") or 0)
    if ui.hero.mp_text then
        ui.hero.mp_text:set_text(string.format("%d/%d", cur_mp, max_mp))
    end
    if ui.hero.mp_prog then
        local ratio = max_mp > 0 and (cur_mp / max_mp) or 0
        ui.hero.mp_prog:set_current_progress_bar_value(ratio * 100, 0)
    end
end

---刷新生命恢复/魔法恢复
---@param unit Unit
function M.refresh_hero_regen(unit)
    if not unit then return end
    local hp_regen = math.floor(params.get_unit_attr(unit, "生命恢复") or 0)
    local mp_regen = math.floor(params.get_unit_attr(unit, "魔法恢复") or 0)
    if ui.hero.hp_extra then
        ui.hero.hp_extra:set_text(string.format("+%d", hp_regen))
    end
    if ui.hero.mp_extra then
        ui.hero.mp_extra:set_text(string.format("+%d", mp_regen))
    end
end

---刷新英雄属性列表
---@param unit Unit
---@param attr_ids table  属性 ID 列表
---@param widgets table   对应的 UI 控件列表
---@param prefix? string  前缀（如 "+"）
function M.refresh_attr_list(unit, attr_ids, widgets, prefix)
    if not unit then return end
    prefix = prefix or ""
    local f = params.get_unit_attr
    for i = 1, #attr_ids do
        local w = widgets[i]
        if w then
            local val = f(unit, attr_ids[i]) or 0
            local str = string.format("%s%d", prefix, val)
            if prefix == "+" and str == "+0" then str = "" end
            w:set_text(str)
        end
    end
end

---刷新英雄主属性
---@param unit Unit
function M.refresh_hero_main_attr(unit)
    local attr_ids = params.hero_attr_ids or { 30, 1, 8, 15 }
    -- 假设 hero_attr_list 从 attr_list_parent 子节点获取
    if ui.attr_list_parent then
        for i, aid in ipairs(attr_ids) do
            local w = ui.attr_list_parent:get_child(i .. ".value_TEXT")
            if w then
                w:set_text(tostring(math.floor(params.get_unit_attr(unit, aid) or 0)))
            end
        end
    end
end

---刷新英雄次属性
---@param unit Unit
function M.refresh_hero_sub_attr(unit)
    local attr_ids = params.hero_sub_attr_ids or { 66, 38 }
    if ui.attr_list4_parent then
        for i, aid in ipairs(attr_ids) do
            local w = ui.attr_list4_parent:get_child(i .. ".value_TEXT")
            if w then
                w:set_text(tostring(math.floor(params.get_unit_attr(unit, aid) or 0)))
            end
        end
    end
end

---刷新英雄 Buff 列表
---@param unit Unit
function M.refresh_hero_buffs(unit)
    if not unit or not ui.hero.buff_view then return end
    ui.hero.buff_view:set_buff_on_ui(unit)
end

---刷新复活读条
---@param time_left? number  nil=隐藏
function M.refresh_revive(time_left)
    if not ui.hero.revive_prog then return end
    if not time_left then
        ui.hero.revive_prog:set_visible(false)
    else
        ui.hero.revive_prog:set_visible(true)
        if ui.hero.revive_text then
            ui.hero.revive_text:set_text(string.format("%.1f", time_left))
        end
    end
end

---刷新英雄技能图标
---@param ability_ctrl table?  技能控制器（含 getAbility/基类方法）
---@param key string?  "D" / "F2" / "Main"
function M.refresh_ability_icon(ability_ctrl, key)
    local btn = ui.ability[key]
    if not btn then return end
    if ability_ctrl then
        local ab = ability_ctrl.getAbility and ability_ctrl:getAbility()
        if ab then btn:bind_ability(ab) end
    else
        -- 清除
        local slot = btn:get_child("slot")
        if slot then slot:bind_ability() end
        local icon = btn:get_child("slot.icon")
        if icon then icon:set_image(999) end
    end
end

-- ============================================================================
-- 物品栏刷新
-- ============================================================================

---刷新物品栏槽位
---@param bag table  背包对象（含 getSlot 方法）
function M.refresh_item_bag(bag)
    if not bag or not ui.bag.slots then return end
    for i, slot_ui in ipairs(ui.bag.slots) do
        local item = bag:getSlot(i)
        if item then
            local item_info = item._itemCfgInfo or {}
            local icon = slot_ui:get_child("slot.icon")
            if icon then icon:set_image(item_info.icon or 999) end
            local num = slot_ui:get_child("slot.stack") or slot_ui:get_child("slot.count")
            if num then num:set_text(tostring(item:getNum() or "")) end
        else
            local icon = slot_ui:get_child("slot.icon")
            if icon then icon:set_image(999) end
            local num = slot_ui:get_child("slot.stack") or slot_ui:get_child("slot.count")
            if num then num:set_text("") end
        end
    end
end

-- ============================================================================
-- 目标信息刷新 (TargetInfoView)
-- ============================================================================

---绑定选中目标单位
---@param unit Unit
function M.bind_target_unit(unit)
    if not unit then
        M.clear_target_unit()
        return
    end
    state.target_unit = unit
    if ui.target.root then ui.target.root:set_visible(true) end

    -- 图标
    local icon_id = unit:get_icon()
    if unit.has_tag and unit:has_tag('hero') then
        icon_id = unit.storage_get and unit:storage_get('icon') or icon_id
    end
    if ui.target.icon then ui.target.icon:set_image(icon_id) end

    -- 名称 + 怪物标签
    local name = (unit.storage_get and unit:storage_get("oriName")) or unit:get_name()
    local monster_type = unit.storage_get and unit:storage_get('monster_type')
    if ui.target.monster_tag then ui.target.monster_tag:set_visible(false) end
    if monster_type == 2 then -- Elite
        if ui.target.monster_tag then
            ui.target.monster_tag:set_visible(true)
            local res = params.resources or {}
            if res.monster_tag_elite then ui.target.monster_tag:set_image(res.monster_tag_elite) end
        end
        name = string.format("[精英] %s", name)
    elseif monster_type == 3 then -- Boss
        if ui.target.monster_tag then
            ui.target.monster_tag:set_visible(true)
            local res = params.resources or {}
            if res.monster_tag_boss then ui.target.monster_tag:set_image(res.monster_tag_boss) end
        end
        name = string.format("[BOSS] %s", name)
    end
    if ui.target.name then ui.target.name:set_text(name) end

    -- 属性刷新
    M.refresh_target_attrs()

    -- Buff 绑定
    if ui.target.buff_view then
        ui.target.buff_view:set_buff_on_ui(unit)
    end

    -- 主属性图标
    local cbs = params.callbacks or {}
    if cbs.get_main_attr_type and ui.target.main_attr then
        local at = cbs.get_main_attr_type(unit)
        local res = params.resources or {}
        local icons = res.main_attr_icons
        if icons then ui.target.main_attr:set_image(icons[at + 1] or 999) end
    end

    -- 通知外部
    if cbs.on_select_unit then cbs.on_select_unit(unit) end
end

---清除选中目标
function M.clear_target_unit()
    state.target_unit = nil
    if ui.target.root then ui.target.root:set_visible(false) end
    local cbs = params.callbacks or {}
    if cbs.on_deselect_unit then cbs.on_deselect_unit() end
end

---刷新目标属性
function M.refresh_target_attrs()
    local unit = state.target_unit
    if not unit then return end
    local attr_ids = params.target_attr_ids or { 30, 66, 38, 1, 8, 15 }
    if ui.target.attr_parent then
        local f = params.get_unit_attr
        for i, aid in ipairs(attr_ids) do
            local w = ui.target.attr_parent:get_child(i .. ".attr")
            if w then
                w:set_text(tostring(math.floor(f(unit, aid) or 0)))
            end
        end
    end

    -- HP
    local max_hp = math.floor(params.get_unit_attr(unit, "最大生命") or 0)
    local cur_hp = math.floor(params.get_unit_attr(unit, "生命") or 0)
    if ui.target.hp_text then
        ui.target.hp_text:set_text(string.format("%s/%s", tpl_format_number(cur_hp), tpl_format_number(max_hp)))
    end
    local hp_ratio = max_hp > 0 and (cur_hp / max_hp) or 0
    -- 目标 HP/MP 用进度条（源工程用 SequenceProgress）
    if ui.target.hp_prog then
        ui.target.hp_prog:set_current_progress_bar_value(hp_ratio * 100, 0)
    end

    -- MP（目标默认显示 -/- ）
    if ui.target.mp_text then
        ui.target.mp_text:set_text("-/-")
    end
    if ui.target.mp_prog then
        ui.target.mp_prog:set_current_progress_bar_value(100, 0)
    end
end

-- ============================================================================
-- 事件注册
-- ============================================================================
local function tpl_register_events()
    local cbs = params.callbacks or {}
    local pid = params.local_player_id

    -- 属性按钮点击
    if ui.hero.attr_btn then
        ui.hero.attr_btn:add_local_event('左键-点击', function()
            if cbs.on_attr_btn_click then cbs.on_attr_btn_click() end
        end)
    end

    -- 背包按钮
    if ui.bag.btn then
        ui.bag.btn:add_local_event('左键-按下', function()
            if cbs.on_bag_btn_click then cbs.on_bag_btn_click() end
        end)
    end

    -- 技能按钮点击
    for key, btn in pairs(ui.ability) do
        if btn then
            btn:add_local_event('左键-按下', function()
                if cbs.on_ability_click then cbs.on_ability_click(key) end
            end)
        end
    end

    -- Buff hover（英雄）
    for i, buff_widget in ipairs(ui.hero.buff_list) do
        buff_widget:add_local_event('鼠标-移入', function()
            if cbs.on_buff_hover then cbs.on_buff_hover(nil, i, pid) end
        end)
        buff_widget:add_local_event('鼠标-移出', function()
            if cbs.on_buff_hover_out then cbs.on_buff_hover_out() end
        end)
    end

    -- Buff hover（目标）
    if ui.target.buff_list then
        for i, buff_widget in ipairs(ui.target.buff_list) do
            buff_widget:add_local_event('鼠标-移入', function()
                if cbs.on_buff_hover then cbs.on_buff_hover(nil, i, pid) end
            end)
            buff_widget:add_local_event('鼠标-移出', function()
                if cbs.on_buff_hover_out then cbs.on_buff_hover_out() end
            end)
        end
    end

    -- 属性 hover（英雄主属性列表）
    if ui.attr_list_parent then
        for i = 1, 4 do
            local w = ui.attr_list_parent:get_child(i .. ".value_TEXT")
            if w then
                w:add_local_event('鼠标-移入', function()
                    if cbs.on_attr_hover then cbs.on_attr_hover(i, pid) end
                end)
                w:add_local_event('鼠标-移出', function()
                    if cbs.on_attr_hover_out then cbs.on_attr_hover_out() end
                end)
            end
        end
    end
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

    -- 初始隐藏目标面板
    if ui.target.root then ui.target.root:set_visible(false) end
    if ui.hero.revive_prog then ui.hero.revive_prog:set_visible(false) end

    state._inited = true
end

---获取初始化状态
function M.is_inited()
    return state._inited == true
end

---获取当前选中目标单位
---@return Unit?
function M.get_target_unit()
    return state.target_unit
end

return M
