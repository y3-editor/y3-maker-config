--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   b-base-panel
--- @version       v0.1.0
--- @entry         M.setup(params) → BasePanel 基类
--- @params        Class, get_ui_by_uuid, get_ui_by_path, get_local_player
--- @source        global_script/gamePlay/base/BasePanel.lua
--- @description   UI 面板基类：自动绑定 `_` 前缀子控件、UUID/路径双模查找、
---                show/hide 生命周期、isOpen 状态查询。
---
--- 融合契约：
---   1. 依赖 Class 系统 + y3.ui.get_by_handle / y3.ui.get_ui
---   2. 约定：UI 编辑器中控件名以 `_` 开头 → 自动填充 self._controls["_xxx"]
---   3. 子类重写 onShow/onHide/customInit
--- =========================================================================

local M = {}

---@class BasePanelParams
---@field Class function|table Class 工厂
---@field get_ui_by_uuid fun(player, uuid): UI y3.ui.get_by_handle
---@field get_ui_by_path fun(player, path): UI y3.ui.get_ui
---@field get_local_player fun(): Player

--- 创建 BasePanel 基类
---@param params BasePanelParams
---@return table
function M.setup(params)
    assert(type(params) == 'table', 'b-base-panel: params required')
    assert(params.Class, 'b-base-panel: Class required')
    assert(type(params.get_ui_by_uuid) == 'function', 'b-base-panel: get_ui_by_uuid required')
    assert(type(params.get_ui_by_path) == 'function', 'b-base-panel: get_ui_by_path required')
    assert(type(params.get_local_player) == 'function', 'b-base-panel: get_local_player required')

    local Class = params.Class
    local get_ui_by_uuid = params.get_ui_by_uuid
    local get_ui_by_path = params.get_ui_by_path
    local get_local_player = params.get_local_player

    local Base = Class('BasePanel')

    --- 初始化面板（通过 UI 名查找并绑定控件）
    --- name 可以是 UUID 或 UI 路径
    ---@param name string UUID 或 UI 路径
    function Base:init(name)
        self._name = name
        if self._panelObj then return end

        local localPlayer = get_local_player()

        -- 尝试通过 UUID 或路径查找
        local uuid = params.resolve_uuid and params.resolve_uuid(name)
        if uuid then
            self._panelObj = get_ui_by_uuid(localPlayer, uuid)
        else
            local uiPath = params.resolve_path and params.resolve_path(name) or name
            self._panelObj = get_ui_by_path(localPlayer, uiPath)
        end

        if not self._panelObj then
            log.warn('b-base-panel: UI not found for ' .. tostring(name))
            return
        end

        -- 自动绑定 `_` 前缀子控件
        self._controls = {}
        self:_findUnderscoreControls(self._panelObj)
        self:customInit()
    end

    --- 子类重写：自定义初始化
    function Base:customInit() end

    --- 递归查找 `_` 前缀控件并自动绑定
    ---@param parent UI
    function Base:_findUnderscoreControls(parent)
        local children = parent:get_childs()
        for _, child in pairs(children) do
            local name = child:get_name()
            if name and string.sub(name, 1, 1) == '_' then
                self._controls[name] = child
            end
            -- 递归
            self:_findUnderscoreControls(child)
        end
    end

    --- 获取已绑定控件
    ---@param name string 控件名（含 `_` 前缀）
    ---@return UI|nil
    function Base:getControl(name)
        local ctrl = self._controls[name]
        if not ctrl then
            log.warn('b-base-panel: control not found: ' .. tostring(name))
        end
        return ctrl
    end

    --- 显示面板
    ---@param name? string
    ---@param uiData? any 传递给 onShow 的数据
    function Base:show(name, uiData)
        if name then self:init(name) end
        if not self._panelObj then return end
        self._panelObj:set_visible(true)
        self:onShow(uiData)
    end

    --- 仅隐藏（不触发 onHide）
    function Base:initHide()
        if self._panelObj then
            self._panelObj:set_visible(false)
        end
    end

    --- 隐藏面板（触发 onHide）
    function Base:hide()
        if not self._panelObj then return end
        self._panelObj:set_visible(false)
        self:onHide()
    end

    --- 根据 status 自动 show/hide
    ---@param status boolean
    ---@param name? string
    ---@param uiData? any
    function Base:setViewStatus(status, name, uiData)
        if status then self:show(name, uiData) else self:hide() end
    end

    --- 是否打开
    ---@return boolean
    function Base:isOpen()
        if self._panelObj then return self._panelObj:is_visible() end
        return false
    end

    -- 子类可重写
    function Base:onShow(uiData) end
    function Base:onHide() end
    function Base:registerEvent() end
    function Base:clear() end

    return Base
end

return M
