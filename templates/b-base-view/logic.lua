--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   b-base-view
--- @version       v0.1.0
--- @entry         M.setup(params) → View 基类
--- @params        Class, create_gc_host, Delete, on_register
--- @source        global_script/gamePlay/base/BaseView.lua
--- @description   UI 视图基类：生命周期管理（init/onShow/onHide）、事件 GC 防泄漏、单例注册、refresh 标志。
---
--- 融合契约：
---   1. 调用方将本文件融入 UI 模块
---   2. 需提供 Class 系统 + y3.gc.host (或等价 GC 容器)
---   3. params.Delete 注入 GC 销毁函数
---   4. 可选提供 on_register 钩子用于单例注册
--- =========================================================================

local M = {}

---@class BaseViewParams
---@field Class any Class 工厂（如 require "y3.tools.class"）
---@field create_gc_host fun(): table GC 容器构造器（如 y3.gc.host）
---@field Delete fun(host: table) GC 销毁函数（如 y3.tools.gc 导出的 Delete）
---@field on_register? fun(class_name: string, view: table) 单例注册钩子（如 UIMgr.setUIViewCtrl）
---@field local_player_id? number 本地玩家 ID（可选，默认 nil）
---@field local_player? table 本地玩家（可选，默认 nil）

--- 创建 View 基类
---@param params BaseViewParams
---@return table View 基类表（用于 Extends/Class 继承）
function M.setup(params)
    assert(type(params) == 'table', 'b-base-view: params must be a table')
    assert(type(params.Class) == 'function' or type(params.Class) == 'table',
        'b-base-view: params.Class is required')
    assert(type(params.create_gc_host) == 'function',
        'b-base-view: params.create_gc_host is required')
    assert(type(params.Delete) == 'function',
        'b-base-view: params.Delete is required')

    local Class = params.Class
    local create_gc_host = params.create_gc_host
    local Delete = params.Delete
    local on_register = params.on_register

    local View = Class 'BaseView'

    --- 基础初始化（子类在 initUI 中调用 baseInit）
    ---@param uiNode UI 根节点
    function View:baseInit(uiNode)
        if not uiNode then return end

        self._triggerList = create_gc_host()
        self._root = uiNode
        self._isVisible = false
        self._localPlayerId = params.local_player_id
        self._localPlayer = params.local_player

        -- 单例注册
        if on_register then
            local class_name = type(Class.type) == 'function' and Class.type(self) or nil
            if class_name then
                on_register(class_name, self)
            end
        end

        self:initUI()
        self:registerEvent()
    end

    -- 以下为可被子类重写的模板方法
    function View:initUI() end
    function View:registerEvent() end
    function View:unregisterEvent() end
    function View:updateUI(data) end
    function View:customShowEvt() end
    function View:customHideEvt() end

    --- 显示视图
    ---@param data? any 传递给 updateUI 的数据
    function View:onShow(data)
        self._isVisible = true
        self._refresh = true
        self:updateUI(data)
        self:customShowEvt()
        self._root:set_visible(true)
    end

    --- 隐藏视图
    function View:onHide()
        self._isVisible = false
        self:customHideEvt()
        self._root:set_visible(false)
    end

    --- 是否处于显示状态
    ---@return boolean
    function View:isOpen()
        return self._isVisible
    end

    --- 绑定事件到 GC 容器（destroy 时自动清理）
    ---@param trigger any 触发器对象
    function View:addTrigger(trigger)
        self._triggerList:bindGC(trigger)
    end

    --- 清空所有绑定事件
    function View:clear()
        Delete(self._triggerList)
        self._triggerList = create_gc_host()
    end

    return View
end

return M
