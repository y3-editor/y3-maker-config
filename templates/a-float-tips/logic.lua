--- =========================================================================
--- Y3 功能模板 · logic.lua  (A 级 · 参数注入式)
--- =========================================================================
---
--- @template-id   a-float-tips
--- @grade         A
--- @version       v0.2.0
--- @entry         M.float_text(params)
--- @params        player, text, root_ui, [pos_x], [pos_y], [duration], [prefab_id], [text_child]
--- @description   在指定位置生成浮动文本，向上飘移并渐隐消失
---
--- 融合契约：
---   1. 由 y3-ui-pipeline 自动导入 a-float-tips.upui（FloatTips 元件），无需手动操作
---   2. 调用方提供 root_ui（挂载的目标 UI 节点），如 HUD 画板
---   3. 引入本文件后调用 M.float_text(params) 即可
---   4. player 参数需支持 get_mouse_pos_x/y, get_mouse_ui_x_percent
---   5. 如使用固定坐标（pos_x/pos_y），无需开启鼠标同步
--- =========================================================================

local M = {}

local DEFAULTS = {
    prefab_id  = '11f58d69-7f2b-4131-9964-49360b398190',
    text_child = '_title_TEXT',
    duration   = 1,
}

---@class FloatTextParams
---@field player      userdata  必填: 目标玩家对象（需支持 get_mouse_pos_x/y, get_mouse_ui_x_percent）
---@field text        string    必填: 显示的文本
---@field root_ui     UI        必填: 挂载的父节点 UI（y3.ui_prefab.create 强制要求）
---@field pos_x?      number    可选: 起始X坐标（绝对像素），nil=鼠标位置
---@field pos_y?      number    可选: 起始Y坐标（绝对像素），nil=鼠标位置
---@field duration?   number    可选: 持续时间（秒），默认 1
---@field prefab_id?  string    可选: 元件 UUID，默认 FloatTips 元件
---@field text_child? string    可选: 文本子节点名，默认 '_title_TEXT'

--- 显示浮动文本（向上飘移渐隐消失）
---@param params FloatTextParams
function M.float_text(params)
    assert(params, 'float_text: params is required')
    assert(params.player, 'float_text: player is required')
    assert(params.text, 'float_text: text is required')
    assert(params.root_ui, 'float_text: root_ui is required (y3.ui_prefab.create 强制要求父节点)')

    local player     = params.player
    local text       = params.text
    local root_ui    = params.root_ui
    local pos_x      = params.pos_x or player:get_mouse_pos_x()
    local pos_y      = params.pos_y or player:get_mouse_pos_y()
    local duration   = params.duration or DEFAULTS.duration
    local prefab_id  = params.prefab_id or DEFAULTS.prefab_id
    local text_child = params.text_child or DEFAULTS.text_child

    -- 1. 创建元件（y3.ui_prefab.create 必须传 parent_ui）
    local prefab = y3.ui_prefab.create(player, prefab_id, root_ui)
    local ui = prefab:get_child()
    if not ui then
        return
    end

    -- 2. 根据鼠标在屏幕左右侧设置锚点
    local mouse_x_percent = player:get_mouse_ui_x_percent()
    local anchor_x = mouse_x_percent < 0.5 and 0 or 1
    ui:set_anchor(anchor_x, 0.5)
    ui:set_visible(true)
    ui:set_absolute_pos(pos_x, pos_y)

    -- 3. 设置文本
    local text_node = ui:get_child(text_child)
    if text_node then
        text_node:set_text(text)
    end

    -- 4. 动画：间隔后向上漂移
    y3.ltimer.wait(duration / 5, function()
        local rx, ry = ui:get_relative_x(), ui:get_relative_y()
        ui:set_anim_pos(rx, ry, rx, ry + 100, duration)
    end)

    -- 5. 动画：半程开始渐隐
    y3.ltimer.wait(duration / 2, function()
        if ui then
            ui:set_anim_opacity(100, 0, duration / 2, 1)
        end
    end)

    -- 6. 定时销毁
    y3.ltimer.wait(duration, function()
        if ui then
            ui:remove()
        end
    end)
end

return M
