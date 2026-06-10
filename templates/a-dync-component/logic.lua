--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-dync-component
--- @version       v0.1.0
--- @entry         M.setup(params) → DyncComponent 基类
--- @params        Class, get_local_player, create_ui_prefab
--- @source        global_script/gamePlay/ui/DyncComponent.lua
--- @description   动态 Prefab 组件基类：根据资源名实例化 UI Prefab 并挂到父节点。
---                 CurrencyCmp / ItemCmp / BondCardCmp 等通用组件的父类。
---
--- 融合契约：
---   1. 依赖 Class 系统 + y3.ui_prefab
---   2. 子类继承后调用 self:initDyncComponent(resName, parent) 初始化
---   3. self._ui 即根控件，可直接操作
--- =========================================================================

local M = {}

---@class DyncComponentParams
---@field Class function|table Class 工厂
---@field get_local_player fun(): Player 获取本地玩家
---@field create_ui_prefab fun(player: Player, resName: string, parent: UI): UI y3.ui_prefab.create

--- 创建 DyncComponent 基类
---@param params DyncComponentParams
---@return table
function M.setup(params)
    assert(type(params) == 'table', 'a-dync-component: params required')
    assert(params.Class, 'a-dync-component: params.Class required')
    assert(type(params.get_local_player) == 'function', 'a-dync-component: get_local_player required')
    assert(type(params.create_ui_prefab) == 'function', 'a-dync-component: create_ui_prefab required')

    local Class = params.Class

    local Base = Class('DyncComponent')

    --- 初始化动态组件
    ---@param resName string Prefab 资源名
    ---@param parent UI 父节点
    function Base:initDyncComponent(resName, parent)
        if not resName then return end

        local player = params.get_local_player()
        local uiPrefab = params.create_ui_prefab(player, resName, parent)
        if not uiPrefab then
            log.warn('a-dync-component: prefab not found: ' .. tostring(resName))
            return
        end

        local ui = uiPrefab:get_child('')
        if not ui then
            log.warn('a-dync-component: root child not found for: ' .. tostring(resName))
            return
        end

        self._ui = ui
    end

    --- 设置可见性
    ---@param status boolean
    function Base:setVisible(status)
        if self._ui then
            self._ui:set_visible(status)
        end
    end

    --- 获取根控件
    ---@return UI|nil
    function Base:getRoot()
        return self._ui
    end

    --- 获取根控件名称
    ---@return string
    function Base:getRootName()
        if not self._ui then return '' end
        return self._ui:get_name()
    end

    return Base
end

return M
