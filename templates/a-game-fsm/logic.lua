--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-game-fsm
--- @version       v0.1.0
--- @entry         M.setup(params) → FSM 实例
--- @params        states, transitions, initial, hooks, callbacks, child
--- @source        global_script/gamePlay/base/BaseGameFSM.lua
--- @description   通用父子状态机，支持自定义状态枚举、合法迁移矩阵、onEnter/onLeave 钩子、
---                回调映射、子状态机嵌套。适合游戏主流程 / 关卡流程 / UI 流程。
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块入口点
---   2. 所有外部依赖通过 M.setup(params) 传入
---   3. 本模板不依赖 UI、物编、配置表
---   4. 状态名用 string，与 EventBus 事件名对齐更佳
--- =========================================================================

local M = {}

---@class GameFSMParams
---@field states table<string, string> 状态枚举 { Init="Init", Play="Play", Done="Done", ... }
---@field transitions table<string, string[]> 迁移表 { Init={"Play"}, Play={"Done"}, Done={} }
---@field initial string 初始状态（必须是 states 中的 key）
---@field hooks? table<string, { onEnter?: function, onLeave?: function }> 钩子（可选）
---@field callbacks? table<string, function> 命名回调（如 { win=fn, lose=fn, start=fn }）
---@field child? GameFSMInstance 子状态机（可选）

---@class GameFSMInstance
---@field tryToState fun(self: GameFSMInstance, state: string)
---@field getState fun(self: GameFSMInstance): string
---@field setChild fun(self: GameFSMInstance, child: GameFSMInstance)

local function validate_params(params)
    assert(type(params) == 'table', 'a-game-fsm: params must be a table')
    assert(type(params.states) == 'table', 'a-game-fsm: params.states is required (state enum table)')
    assert(type(params.transitions) == 'table', 'a-game-fsm: params.transitions is required')
    assert(type(params.initial) == 'string', 'a-game-fsm: params.initial is required')
    assert(params.states[params.initial], 'a-game-fsm: params.initial must exist in params.states')
end

--- 创建状态机
---@param params GameFSMParams
---@return GameFSMInstance
function M.setup(params)
    validate_params(params)

    local states = params.states
    local transitions = params.transitions
    local hooks = params.hooks or {}
    local callbacks = params.callbacks or {}
    local child = params.child

    local current_state = states[params.initial]

    --- 校验迁移合法性
    ---@param target_state string
    ---@return boolean
    local function check_transition(target_state)
        local allowed = transitions[current_state]
        if not allowed then
            return false
        end
        for _, s in ipairs(allowed) do
            if s == target_state then
                return true
            end
        end
        return false
    end

    ---@type GameFSMInstance
    local instance = {}

    --- 尝试迁移到目标状态（非法则忽略）
    ---@param target_state string
    function instance:tryToState(target_state)
        if not check_transition(target_state) then
            -- log: 非法迁移 from current_state → target_state
            return
        end

        local prev_state = current_state

        -- 执行 onLeave 钩子
        local leave_hooks = hooks[prev_state]
        if leave_hooks and leave_hooks.onLeave then
            leave_hooks.onLeave()
        end

        -- 更新状态
        current_state = target_state

        -- 执行 onEnter 钩子
        local enter_hooks = hooks[target_state]
        if enter_hooks and enter_hooks.onEnter then
            enter_hooks.onEnter()
        end

        -- 执行命名回调（如 win/lose）
        if callbacks[prev_state] then
            callbacks[prev_state]()
        end
    end

    --- 获取当前状态
    ---@return string
    function instance:getState()
        return current_state
    end

    --- 设置子状态机
    ---@param child_fsm GameFSMInstance
    function instance:setChild(child_fsm)
        child = child_fsm
    end

    --- 获取子状态机
    ---@return GameFSMInstance|nil
    function instance:getChild()
        return child
    end

    return instance
end

return M
