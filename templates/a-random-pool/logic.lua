--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-random-pool
--- @version       v0.1.0
--- @entry         M.setup(params) → RandomPool 实例
--- @params        create_random_pool, name, type
--- @source        global_script/gamePlay/entity/RandomPool.lua
--- @description   加权随机池，支持字符串/整数双模 ID、抽中后可选清零、权重查询。
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块入口点
---   2. 所有外部依赖通过 M.setup(params) 传入
---   3. 可通过 params.create_random_pool 注入 GameAPI 实现，便于测试 mock
--- =========================================================================

local M = {}

---@class RandomPoolParams
---@field create_random_pool fun(): table  pool handle（GameAPI.create_random_pool 返回值）
---@field set_pool_value fun(pool: table, id: integer, weight: integer)  注入 GameAPI.set_random_pool_value
---@field get_pool_weight fun(pool: table, id: integer): integer  注入 GameAPI.get_random_pool_pointed_weight
---@field get_pool_result fun(pool: table, remain: boolean): integer  注入 GameAPI.get_bitrary_random_pool_value
---@field name? string 池名称（调试用）
---@field default_type? "int" | "string" 默认 ID 类型（首次调用 setWeight 后锁定）

---@class RandomPoolInstance
---@field setWeight fun(self: RandomPoolInstance, id: integer|string, weight: integer)
---@field getWeight fun(self: RandomPoolInstance, id: integer|string): integer
---@field getTotalWeight fun(self: RandomPoolInstance): integer
---@field getIntResult fun(self: RandomPoolInstance, remain?: boolean): integer
---@field getStrResult fun(self: RandomPoolInstance, remain?: boolean): string

local function validate_params(params)
    assert(type(params) == 'table', 'a-random-pool: params must be a table')
    assert(type(params.create_random_pool) == 'function', 'a-random-pool: params.create_random_pool is required')
    assert(type(params.set_pool_value) == 'function', 'a-random-pool: params.set_pool_value is required')
    assert(type(params.get_pool_weight) == 'function', 'a-random-pool: params.get_pool_weight is required')
    assert(type(params.get_pool_result) == 'function', 'a-random-pool: params.get_pool_result is required')
end

--- 创建随机池
---@param params RandomPoolParams
---@return RandomPoolInstance
function M.setup(params)
    validate_params(params)

    local pool_type = ''
    local default_type = params.default_type

    local rndpool = params.create_random_pool()
    if not rndpool then
        error('a-random-pool: create_random_pool() returned nil')
    end

    local set_pool_value = params.set_pool_value
    local get_pool_weight = params.get_pool_weight
    local get_pool_result = params.get_pool_result

    local weight_table = {}
    local id_to_str = {} ---@type string[]
    local str_to_id = {} ---@type table<string, integer>

    -- 内部：字符串→ID 映射
    local function get_id(str)
        if not str_to_id[str] then
            id_to_str[#id_to_str + 1] = str
            str_to_id[str] = #id_to_str
        end
        return str_to_id[str]
    end

    -- 内部：锁池类型
    local function lock_type(id)
        if pool_type == '' then
            pool_type = type(id) == 'string' and 'string' or 'int'
        end
    end

    ---@type RandomPoolInstance
    local instance = {}

    ---设置权重（支持 string 或 int ID，不可混合）
    ---@param id integer|string
    ---@param weight integer
    function instance:setWeight(id, weight)
        lock_type(id)

        if type(id) == 'string' then
            id = get_id(id)
        end

        weight_table[id] = weight
        set_pool_value(rndpool, id, weight)
    end

    ---获取某 ID 的当前权重
    ---@param id integer|string
    ---@return integer
    function instance:getWeight(id)
        if type(id) == 'string' then
            id = get_id(id)
        end
        return get_pool_weight(rndpool, id)
    end

    ---获取池总权重
    ---@return integer
    function instance:getTotalWeight()
        local total = 0
        for _, weight in pairs(weight_table) do
            total = total + weight
        end
        return total
    end

    -- 内部：从底层池获取原始结果（不做类型检查，不处理权重清零）
    ---@return integer
    local function get_raw_result()
        return get_pool_result(rndpool, true)
    end

    ---随机抽取（返回整数 ID）
    ---@param remain? boolean 是否保留权重（true=不消耗，false=抽后权重归零）
    ---@return integer
    function instance:getIntResult(remain)
        if pool_type == 'string' then
            error('a-random-pool: pool is string type, use getStrResult()')
        end
        local result = get_raw_result()
        if not remain then
            instance:setWeight(result, 0)
        end
        return result
    end

    ---随机抽取（返回字符串 ID）
    ---@param remain? boolean 是否保留权重
    ---@return string
    function instance:getStrResult(remain)
        if pool_type ~= 'string' then
            error('a-random-pool: pool is int type, use getIntResult()')
        end
        local id = get_raw_result()
        if not remain then
            instance:setWeight(id, 0)
        end
        return id_to_str[id]
    end

    return instance
end

return M
