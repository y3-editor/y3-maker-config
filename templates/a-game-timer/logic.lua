--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-game-timer
--- @version       v0.1.0
--- @entry         M.setup(params) → Timer 实例
--- @params        ltimer, name
--- @source        global_script/gamePlay/entity/GameTimer.lua
--- @description   三层时间轴（帧/秒/分）回调调度器，支持多实例、模拟时间偏移、一键清空。
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块入口点
---   2. 所有外部依赖通过 M.setup(params) 传入
---   3. 本模板不依赖 UI、物编、配置表
---   4. 推荐用法：全局 globalTimer（菜单/UI 动画）+ 局内 inGameTimer（战斗计时）
--- =========================================================================

local M = {}

---@class GameTimerParams
---@field ltimer table y3.ltimer 引用（{ loop_frame: func, loop: func }）
---@field name? string 计时器名称

---@class GameTimerInstance
---@field addFrameUpdateFunc fun(self: GameTimerInstance, func: fun(curFrame:integer))
---@field removeFrameUpdateFunc fun(self: GameTimerInstance, func: fun(curFrame:integer))
---@field addSecondUpdateFunc fun(self: GameTimerInstance, func: fun(curSecond:integer))
---@field removeSecondUpdateFunc fun(self: GameTimerInstance, func: fun(curSecond:integer))
---@field addMinuteUpdateFunc fun(self: GameTimerInstance, func: fun(curMinute:integer))
---@field removeMinuteUpdateFunc fun(self: GameTimerInstance, func: fun(curMinute:integer))
---@field getCurFrame fun(self: GameTimerInstance): integer
---@field getCurSecond fun(self: GameTimerInstance): integer
---@field getCurMinute fun(self: GameTimerInstance): integer
---@field start fun(self: GameTimerInstance)
---@field clear fun(self: GameTimerInstance)
---@field setCurSecond fun(self: GameTimerInstance, value: integer)
---@field addCurSecond fun(self: GameTimerInstance, add: integer)

--- 验证参数合法性
local function validate_params(params)
    assert(type(params) == 'table', 'a-game-timer: params must be a table')
    assert(type(params.ltimer) == 'table', 'a-game-timer: params.ltimer is required')
    assert(type(params.ltimer.loop_frame) == 'function', 'a-game-timer: params.ltimer.loop_frame is required')
    assert(type(params.ltimer.loop) == 'function', 'a-game-timer: params.ltimer.loop is required')
end

--- 辅助：新增回调
---@param map table
---@param func function
local function add_update_func(map, func)
    table.insert(map, func)
end

--- 辅助：移除回调
---@param map table
---@param func function
local function remove_update_func(map, func)
    for i, obj in ipairs(map) do
        if obj == func then
            table.remove(map, i)
            break
        end
    end
end

--- 创建 Timer 实例
---@param params GameTimerParams
---@return GameTimerInstance
function M.setup(params)
    validate_params(params)

    local ltimer = params.ltimer
    local name = params.name or 'default'

    -- 内部状态
    local updateFrameFuncMap = {} ---@type fun(curFrame:integer)[]
    local updateSecondFuncMap = {} ---@type fun(curSecond:integer)[]
    local updateMinuteFuncMap = {} ---@type fun(curMinute:integer)[]

    local curFrame = 0
    local curSecond = 0
    local curMinute = 0
    local isStart = false

    local frameTimer = nil
    local secondTimer = nil
    local minuteTimer = nil

    -- 帧循环（每帧触发）
    local function frame_loop()
        curFrame = curFrame + 1
        for _, func in ipairs(updateFrameFuncMap) do
            func(curFrame)
        end
    end

    -- 秒循环
    local function second_loop()
        curSecond = curSecond + 1
        for _, func in ipairs(updateSecondFuncMap) do
            func(curSecond)
        end
    end

    -- 分钟循环
    local function minute_loop()
        curMinute = curMinute + 1
        for _, func in ipairs(updateMinuteFuncMap) do
            func(curMinute)
        end
    end

    ---@type GameTimerInstance
    local instance = {}

    ---注册帧更新回调（每帧调用）
    ---@param func fun(curFrame:integer)
    function instance:addFrameUpdateFunc(func) add_update_func(updateFrameFuncMap, func) end

    ---移除帧更新回调
    ---@param func fun(curFrame:integer)
    function instance:removeFrameUpdateFunc(func) remove_update_func(updateFrameFuncMap, func) end

    ---注册秒更新回调
    ---@param func fun(curSecond:integer)
    function instance:addSecondUpdateFunc(func) add_update_func(updateSecondFuncMap, func) end

    ---移除秒更新回调
    ---@param func fun(curSecond:integer)
    function instance:removeSecondUpdateFunc(func) remove_update_func(updateSecondFuncMap, func) end

    ---注册分钟更新回调
    ---@param func fun(curMinute:integer)
    function instance:addMinuteUpdateFunc(func) add_update_func(updateMinuteFuncMap, func) end

    ---移除分钟更新回调
    ---@param func fun(curMinute:integer)
    function instance:removeMinuteUpdateFunc(func) remove_update_func(updateMinuteFuncMap, func) end

    ---获取当前帧数
    ---@return integer
    function instance:getCurFrame() return curFrame end

    ---获取当前秒数
    ---@return integer
    function instance:getCurSecond() return curSecond end

    ---获取当前分钟数
    ---@return integer
    function instance:getCurMinute() return curMinute end

    ---启动计时器（再次调用无副作用）
    function instance:start()
        if isStart then return end
        isStart = true

        frameTimer = ltimer.loop_frame(1, frame_loop)
        secondTimer = ltimer.loop(1, second_loop)
        minuteTimer = ltimer.loop(60, minute_loop)
    end

    ---清除计时器：停止所有 timer，清空所有回调
    function instance:clear()
        if frameTimer then
            frameTimer:remove()
            frameTimer = nil
        end
        if secondTimer then
            secondTimer:remove()
            secondTimer = nil
        end
        if minuteTimer then
            minuteTimer:remove()
            minuteTimer = nil
        end

        updateFrameFuncMap = {}
        updateSecondFuncMap = {}
        updateMinuteFuncMap = {}

        isStart = false
    end

    ---设置当前秒数（偏移量，用于模拟快进）
    --- 注意：内部存储为 value-1，下一次 secondLoop 会先 +1 达到 value
    ---@param value integer
    function instance:setCurSecond(value)
        curSecond = value - 1
    end

    ---在当前秒数基础上增加（用于暂停补偿 / GM 快进）
    ---@param add integer 增加的秒数
    function instance:addCurSecond(add)
        curSecond = math.max(curSecond + add, 0) - 1
    end

    return instance
end

return M
