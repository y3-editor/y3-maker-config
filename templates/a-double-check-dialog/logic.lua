--- =========================================================================
--- Y3 功能模板 · logic.lua  (A 级 · 参数注入式)
--- =========================================================================
---
--- @template-id   a-double-check-dialog
--- @grade         A
--- @version       v0.1.0
--- @entry         M.setup(params)
--- @params        prefab_name, ui_path, parent_ui, get_parent_ui, bind_ui_effect
--- @source        DM42/global_script/gamePlay/ui/DoubleCheck.lua
--- @description   创建带标题、内容、确认/取消按钮和回调的二次确认弹窗。
---
--- 融合契约：
---   1. 先导入 a-double-check-dialog.upui，确保存在 DoubleCheck Prefab。
---   2. 所有外部依赖通过 M.setup(params) 或 M.show(..., options) 注入。
---   3. 默认挂载到随模板导入的 [0]DoubleCheck 画板；也可传 parent_ui/get_parent_ui 覆盖。
---   4. 本模板只绑定本地 UI 点击事件；确认/取消后的业务行为由回调决定。
--- =========================================================================

local M = {}

local params = {
    prefab_name = 'DoubleCheck',
    ui_path = '[0]DoubleCheck',
    event_click = '左键-点击',
    auto_remove = true,
    paths = {
        title = 'root.title.title_TEXT',
        content = 'root.content_TEXT',
        confirm = 'root.control.confirm_BTN',
        cancel = 'root.control.cancel_BTN',
    },
    default_title = '确认操作',
    default_content = '',
    confirm_text = nil,
    cancel_text = nil,
    player = nil,
    parent_ui = nil,
    get_player = nil,
    get_parent_ui = nil,
    bind_ui_effect = nil,
    on_error = nil,
}

local active_dialogs = {}

local Dialog = {}
Dialog.__index = Dialog

local function tpl_merge(dst, src)
    if type(src) ~= 'table' then
        return dst
    end
    for k, v in pairs(src) do
        if k == 'paths' and type(v) == 'table' then
            dst.paths = dst.paths or {}
            for path_key, path_value in pairs(v) do
                dst.paths[path_key] = path_value
            end
        else
            dst[k] = v
        end
    end
    return dst
end

local function tpl_call_error(message)
    if type(params.on_error) == 'function' then
        params.on_error(message)
    end
end

local function tpl_assert_y3()
    assert(y3 and y3.ui_prefab and y3.ui_prefab.create, 'a-double-check-dialog requires y3.ui_prefab.create')
    if not (params.parent_ui or type(params.get_parent_ui) == 'function') then
        assert(y3.ui and y3.ui.get_ui, 'a-double-check-dialog requires y3.ui.get_ui or an injected parent_ui')
    end
end

local function tpl_get_player(options)
    if options and options.player then
        return options.player
    end
    if params.player then
        return params.player
    end
    if type(params.get_player) == 'function' then
        return params.get_player()
    end
    if y3 and y3.player and y3.player.get_local then
        return y3.player.get_local()
    end
    return nil
end

local function tpl_get_parent_ui(player, options)
    if options and options.parent_ui then
        return options.parent_ui
    end
    if params.parent_ui then
        return params.parent_ui
    end
    if type(params.get_parent_ui) == 'function' then
        return params.get_parent_ui(player, options)
    end
    local ui_path = (options and options.ui_path) or params.ui_path
    if ui_path and y3 and y3.ui and y3.ui.get_ui then
        return y3.ui.get_ui(player, ui_path)
    end
    return nil
end

local function tpl_get_child(root, path, label)
    assert(root and root.get_child, 'a-double-check-dialog root ui is invalid')
    local child = root:get_child(path)
    assert(child, 'a-double-check-dialog missing ui node: ' .. tostring(label) .. ' (' .. tostring(path) .. ')')
    return child
end

local function tpl_set_text(ui, text)
    if text ~= nil and ui and ui.set_text then
        ui:set_text(tostring(text))
    end
end

local function tpl_bind_effect(ui)
    if type(params.bind_ui_effect) == 'function' and ui then
        params.bind_ui_effect(ui)
    end
end

local function tpl_bind_click(ui, callback)
    assert(ui and ui.add_local_event, 'a-double-check-dialog button ui is invalid')
    ui:add_local_event(params.event_click, callback)
end

function Dialog:remove()
    if self._removed then
        return
    end
    self._removed = true
    active_dialogs[self] = nil
    if self.prefab and self.prefab.remove then
        self.prefab:remove()
        return
    end
    if self.root and self.root.remove then
        self.root:remove()
    end
end

function Dialog:get_root()
    return self.root
end

function Dialog:get_prefab()
    return self.prefab
end

function Dialog:set_title(title)
    tpl_set_text(self.title_ui, title)
end

function Dialog:set_content(content)
    tpl_set_text(self.content_ui, content)
end

local function tpl_create_dialog(title, content, on_confirm, on_cancel, options)
    options = options or {}
    tpl_assert_y3()

    local player = tpl_get_player(options)
    assert(player, 'a-double-check-dialog requires params.player/options.player or y3.player.get_local()')

    local parent_ui = tpl_get_parent_ui(player, options)
    assert(parent_ui, 'a-double-check-dialog requires params.parent_ui/options.parent_ui or params.ui_path')

    local prefab_name = options.prefab_name or params.prefab_name
    local prefab = y3.ui_prefab.create(player, prefab_name, parent_ui)
    assert(prefab, 'a-double-check-dialog can not create prefab: ' .. tostring(prefab_name))

    local root = prefab:get_child()
    assert(root, 'a-double-check-dialog can not get prefab root: ' .. tostring(prefab_name))
    -- 导入后的 Prefab 顶层可能是 visible=false；实例化成功但不可见时，
    -- 这里强制打开根节点作为跨项目复用兜底。
    if root.set_visible then
        root:set_visible(true)
    end

    local paths = params.paths
    local dialog = setmetatable({
        player = player,
        parent_ui = parent_ui,
        prefab = prefab,
        root = root,
        on_confirm = on_confirm,
        on_cancel = on_cancel,
        auto_remove = options.auto_remove ~= nil and options.auto_remove or params.auto_remove,
    }, Dialog)

    dialog.title_ui = tpl_get_child(root, paths.title, 'title')
    dialog.content_ui = tpl_get_child(root, paths.content, 'content')
    dialog.confirm_btn = tpl_get_child(root, paths.confirm, 'confirm')
    dialog.cancel_btn = tpl_get_child(root, paths.cancel, 'cancel')

    tpl_set_text(dialog.title_ui, title or params.default_title)
    tpl_set_text(dialog.content_ui, content or params.default_content)
    tpl_set_text(dialog.confirm_btn:get_child('title_TEXT'), options.confirm_text or params.confirm_text)
    tpl_set_text(dialog.cancel_btn:get_child('title_TEXT'), options.cancel_text or params.cancel_text)

    tpl_bind_effect(dialog.confirm_btn)
    tpl_bind_effect(dialog.cancel_btn)

    tpl_bind_click(dialog.confirm_btn, function(local_player)
        if type(dialog.on_confirm) == 'function' then
            dialog.on_confirm(local_player, dialog)
        end
        if dialog.auto_remove then
            dialog:remove()
        end
    end)

    tpl_bind_click(dialog.cancel_btn, function(local_player)
        if type(dialog.on_cancel) == 'function' then
            dialog.on_cancel(local_player, dialog)
        end
        if dialog.auto_remove then
            dialog:remove()
        end
    end)

    active_dialogs[dialog] = true
    return dialog
end

function M.setup(user_params)
    tpl_merge(params, user_params)
    assert(type(params.prefab_name) == 'string' and params.prefab_name ~= '', 'params.prefab_name must be a non-empty string')
    assert(type(params.paths) == 'table', 'params.paths must be a table')
    assert(type(params.paths.title) == 'string', 'params.paths.title must be a string')
    assert(type(params.paths.content) == 'string', 'params.paths.content must be a string')
    assert(type(params.paths.confirm) == 'string', 'params.paths.confirm must be a string')
    assert(type(params.paths.cancel) == 'string', 'params.paths.cancel must be a string')
    return M
end

function M.show(title, content, on_confirm, on_cancel, options)
    local ok, result = pcall(tpl_create_dialog, title, content, on_confirm, on_cancel, options)
    if ok then
        return result
    end
    tpl_call_error(result)
    error(result)
end

function M.close_all()
    local list = {}
    for dialog in pairs(active_dialogs) do
        list[#list + 1] = dialog
    end
    for _, dialog in ipairs(list) do
        dialog:remove()
    end
end

function M.get_active_count()
    local count = 0
    for _ in pairs(active_dialogs) do
        count = count + 1
    end
    return count
end

M.setup()

return M
