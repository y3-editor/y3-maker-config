--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   b-selector-cache
--- @version       v0.1.0
--- @entry         M.setup(params) → SelectorCache 实例
--- @params        create_circular_shape, filter_units, get_enemy_group
--- @source        global_script/gamePlay/utils/selector_cache.lua
--- @description   单位区域选择器（带缓存）：圆形范围筛选 + 距离排序 + 最近/最远/第 K 近查询。
---
--- 融合契约：
---   1. 调用方通过 params 注入 GameAPI 实现
---   2. 缓存以单位 ID 为 key，同帧同一单位重复调用走缓存
--- =========================================================================

local M = {}

---@class SelectorCacheParams
---@field create_circular_shape fun(radius: number): table y3.shape.create_circular_shape
---@field filter_units fun(pos_handle, shape_handle, player_group_handle, ..., order_by_distance: integer): table
--- GameAPI.filter_unit_id_list_in_area_v2
---@field get_enemy_group fun(unit): table y3.player_group.get_enemy_player_group_by_player

--- 创建选择器缓存
---@param params SelectorCacheParams
---@return table
function M.setup(params)
    assert(type(params) == 'table', 'b-selector-cache: params must be a table')
    assert(type(params.create_circular_shape) == 'function', 'b-selector-cache: create_circular_shape required')
    assert(type(params.filter_units) == 'function', 'b-selector-cache: filter_units required')
    assert(type(params.get_enemy_group) == 'function', 'b-selector-cache: get_enemy_group required')

    local create_circular_shape = params.create_circular_shape
    local filter_units = params.filter_units
    local get_enemy_group = params.get_enemy_group

    local cache_group = {}   ---@type table<integer, any>
    local cache_table = {}   ---@type table<integer, table>
    local cache_point = {}   ---@type table<integer, number[]>

    local instance = {}

    --- 区域内选取单位并缓存距离
    ---@param center Unit 中心单位
    ---@param range number 半径
    function instance:cache(center, range)
        local pos = center:get_point()
        local shape = create_circular_shape(range)
        assert(pos, 'b-selector-cache: center must have a point')
        assert(shape, 'b-selector-cache: shape creation failed')

        local enemy_group = get_enemy_group(center)
        -- filter_unit_id_list_in_area_v2(pos, shape, player_group, unit_type, relation,
        --   is_alive, unit_tag, visible, camp, slot,
        --   slot_count, key_word, key_type, filter_type, obj_type, sort_key_type, asc,
        --   order_by_distance)
        local unit_group = filter_units(
            pos.handle,           -- center
            shape.handle,         -- shape
            enemy_group.handle,   -- player_group
            nil, -- unit_type
            nil, -- relation
            nil, -- is_alive
            nil, -- unit_tag
            nil, -- visible
            nil, -- camp
            0,   -- slot_count
            nil, -- key_word
            nil, -- key_type
            0,   -- filter_type
            0,   -- obj_type
            nil, -- sort_key_type
            -1,  -- asc
            0    -- order_by_distance: 0=由近到远
        )

        local id = center:get_id()
        cache_group[id] = unit_group
        cache_table[id] = unit_group and unit_group:pick() or {}
        cache_point[id] = {}

        for _, unit in ipairs(cache_table[id]) do
            table.insert(cache_point[id], pos:get_distance_with(unit:get_point()))
        end
        table.sort(cache_point[id], function(a, b) return a < b end)
    end

    --- 获取缓存中到中心最近的单位距离
    ---@param center Unit
    ---@return number|nil
    function instance:getMinRange(center)
        local id = center:get_id()
        if cache_point[id] and #cache_point[id] > 0 then
            return cache_point[id][1]
        end
        return nil
    end

    --- 获取缓存中第 K 近的单位距离（K 从 1 开始）
    ---@param center Unit
    ---@param k integer
    ---@return number|nil
    function instance:getKthRange(center, k)
        local id = center:get_id()
        if cache_point[id] and cache_point[id][k] then
            return cache_point[id][k]
        end
        return nil
    end

    --- 获取缓存中的单位列表
    ---@param center Unit
    ---@return table
    function instance:getUnits(center)
        local id = center:get_id()
        return cache_table[id] or {}
    end

    --- 获取缓存中的距离列表（已排序）
    ---@param center Unit
    ---@return number[]
    function instance:getDistances(center)
        local id = center:get_id()
        return cache_point[id] or {}
    end

    --- 清除指定单位的缓存
    ---@param center Unit
    function instance:clear(center)
        local id = center:get_id()
        cache_group[id] = nil
        cache_table[id] = nil
        cache_point[id] = nil
    end

    --- 清除所有缓存
    function instance:clearAll()
        cache_group = {}
        cache_table = {}
        cache_point = {}
    end

    return instance
end

return M
