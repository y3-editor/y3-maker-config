--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-event-bus
--- @version       v0.1.0
--- @entry         M.setup(params) → EventBus 实例
--- @params        debug, on_error
--- @source        global_script/gamePlay/manager/GameEventMgr.lua (L63-118)
--- @description   纯 Lua 订阅发布事件总线，支持 priority 排序、xpcall 异常隔离、订阅源追踪。
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块入口点
---   2. 所有外部依赖通过 M.setup(params) 传入
---   3. 本模板不依赖 UI、物编、配置表
---   4. 推荐全局单例，所有 Manager/UI 模块共用同一个 Bus
--- =========================================================================

local M = {}

---@class EventBusParams
---@field debug? boolean 是否记录订阅源信息（默认 false）
---@field on_error? fun(err: string) 异常回调（默认 print）
---@field sort_mode? string "priority" | "none"（默认 "priority"）

---@class EventBusInstance
---@field Subscribe fun(self: EventBusInstance, event: any, callback: function, priority?: integer)
---@field Unsubscribe fun(self: EventBusInstance, event: any, callback: function)
---@field Publish fun(self: EventBusInstance, event: any, ...)
---@field Clear fun(self: EventBusInstance)

--- 验证参数
local function validate_params(params)
    assert(type(params) == 'table', 'a-event-bus: params must be a table')
end

--- 创建 EventBus 实例
---@param params EventBusParams
---@return EventBusInstance
function M.setup(params)
    validate_params(params)

    local debug_mode = params.debug or false
    local on_error = params.on_error or print
    local sort_mode = params.sort_mode or 'priority'

    ---@type table<any, { f: function, p: integer, i?: string }[]>
    local ev2listeners = {}

    ---@type EventBusInstance
    local instance = {}

    ---订阅事件
    ---priority 值越小越先收到消息，相同 priority 的 listener 顺序不保证
    ---priority 未传值时默认为 20
    ---@param event any
    ---@param callback function
    ---@param priority? integer
    function instance:Subscribe(event, callback, priority)
        local listeners = ev2listeners[event]
        if listeners == nil then
            listeners = {}
            ev2listeners[event] = listeners
        end

        local entry = { f = callback, p = priority or 20 }

        -- debug 模式：记录订阅源信息
        if debug_mode then
            local info = debug.getinfo(2)
            local info_str = string.format('%s:%s', info.source, info.currentline)
            if info.name ~= nil then
                info_str = info_str .. ', name=' .. info.name
            end
            entry.i = info_str
        end

        listeners[#listeners + 1] = entry

        if sort_mode == 'priority' then
            table.sort(listeners, function(a, b) return a.p < b.p end)
        end
    end

    ---取消订阅
    ---@param event any
    ---@param callback function
    function instance:Unsubscribe(event, callback)
        local listeners = ev2listeners[event]
        if not listeners then return end

        local new_listeners = {}
        for _, v in ipairs(listeners) do
            if v.f ~= callback then
                new_listeners[#new_listeners + 1] = { f = v.f, p = v.p, i = v.i }
            end
        end

        if sort_mode == 'priority' then
            table.sort(new_listeners, function(a, b) return a.p < b.p end)
        end

        ev2listeners[event] = new_listeners
    end

    ---发布事件（按 priority 顺序通知所有订阅者）
    ---每个监听器在 xpcall 中执行，单个监听器异常不会阻断后续
    ---@param event any
    ---@param ... any 传递给监听器的参数
    function instance:Publish(event, ...)
        local listeners = ev2listeners[event]
        if not listeners then return end

        for _, l in ipairs(listeners) do
            if l.f then
                xpcall(l.f, on_error, ...)
            end
        end
    end

    ---清空所有订阅
    function instance:Clear()
        ev2listeners = {}
    end

    return instance
end

return M
