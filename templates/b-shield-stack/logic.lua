--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   b-shield-stack
--- @version       v0.1.0
--- @entry         M.setup(adapter) → ShieldSystem
--- @adapter       create_linked_list, add_attr, get_attr, bind_buff, remove_buff
--- @source        global_script/client/unit/shield.lua
--- @description   优先级护盾栈：多源护盾按 priority 排序，消耗时从低 priority 开始扣。
---
--- 融合契约：
---   1. Adapter 提供链表实现 + 属性操作 + Buff 操作
---   2. 护盾实例只存 value/priority/buff_ref，不依赖 Class 系统
--- =========================================================================

local M = {}

---@class ShieldAdapter
---@field create_linked_list fun(): table 创建空链表 { pushHead(item), pushTail(item), pop(item), getHead():item|nil, getSize():int, forEach(fn) }
---@field add_attr fun(unit: any, attr_name: string, delta: number)
---@field get_attr fun(unit: any, attr_name: string): number
---@field bind_buff? fun(shield: table, buff: any) 关联 Buff（可选）
---@field remove_buff? fun(buff: any) 移除 Buff（可选）
---@field on_shield_break? fun(unit: any, shield: table) 护盾耗尽回调（可选）

--- 创建护盾系统
---@param adapter ShieldAdapter
---@return table
function M.setup(adapter)
    assert(type(adapter) == 'table', 'b-shield-stack: adapter required')
    assert(type(adapter.create_linked_list) == 'function', 'b-shield-stack: create_linked_list required')
    assert(type(adapter.add_attr) == 'function', 'b-shield-stack: add_attr required')
    assert(type(adapter.get_attr) == 'function', 'b-shield-stack: get_attr required')

    local create_linked_list = adapter.create_linked_list
    local addAttr = adapter.add_attr
    local getAttr = adapter.get_attr
    local bindBuff = adapter.bind_buff
    local removeBuff = adapter.remove_buff
    local onShieldBreak = adapter.on_shield_break

    --- 获取单位的护盾链表（惰性初始化）
    ---@param unit any
    ---@return table
    local function get_shields(unit)
        if not unit._shield_list then
            unit._shield_list = create_linked_list()
        end
        return unit._shield_list
    end

    --- 添加护盾（按 priority 从高到低排序）
    ---@param unit any
    ---@param value number 护盾值
    ---@param priority? integer 优先级（越大越先消耗？默认 0，插入时比 0 大的排前面）
    ---@param buff? any 关联的 Buff
    ---@return table shield
    local function add_shield(unit, value, priority, buff)
        priority = priority or 0
        local shield = {
            unit = unit,
            value = value,
            priority = priority,
            buff = buff,
        }

        local shields = get_shields(unit)

        -- 按 priority 降序插入（priority 越高越先被消耗）
        local inserted = false
        shields:forEach(function(other)
            if not inserted and other.priority < priority then
                shields:pushBefore(shield, other)
                inserted = true
            end
        end)
        if not inserted then
            shields:pushTail(shield)
        end

        -- 加到单位属性
        addAttr(unit, 'shield', value)

        return shield
    end

    --- 消耗护盾（按 priority 从高到低）
    ---@param unit any
    ---@param value number 要消耗的值
    ---@return number 实际消耗的量
    local function cost_shield(unit, value)
        if value <= 0 then return 0 end
        local shields = unit._shield_list
        if not shields or shields:getSize() == 0 then return 0 end

        local total = 0
        while total < value and shields:getSize() > 0 do
            local first = shields:getHead()
            if not first then break end

            local consumed = math.min(value - total, first.value)
            first.value = first.value - consumed
            total = total + consumed
            addAttr(unit, 'shield', -consumed)

            -- 护盾耗尽 → 移除
            if first.value <= 0 then
                shields:pop(first)
                if onShieldBreak then
                    onShieldBreak(unit, first)
                end
                -- 有关联 Buff → 移除
                if first.buff and removeBuff then
                    removeBuff(first.buff)
                end
            end
        end

        -- 确保属性不出现负护盾
        local current_shield = getAttr(unit, 'shield')
        if current_shield < 0 then
            addAttr(unit, 'shield', -current_shield)
            total = total + current_shield
        end

        return math.min(total, value)
    end

    --- 更新护盾值
    ---@param shield table
    ---@param new_value number
    ---@param multiplier? number 护盾提升系数（默认 0）
    local function update_shield(shield, new_value, multiplier)
        multiplier = multiplier or 0
        local old_value = shield.value
        local adjusted = new_value * (1 + multiplier / 100)

        shield.value = adjusted
        addAttr(shield.unit, 'shield', adjusted - old_value)
    end

    --- 移除指定护盾
    ---@param shield table
    local function remove_shield(shield)
        local unit = shield.unit
        local shields = unit._shield_list
        if shields then
            shields:pop(shield)
            addAttr(unit, 'shield', -shield.value)
        end
        if shield.buff and removeBuff then
            removeBuff(shield.buff)
        end
        shield.value = 0
        shield.buff = nil
    end

    --- 获取总护盾值
    ---@param unit any
    ---@return number
    local function get_total_shield(unit)
        return getAttr(unit, 'shield')
    end

    --- 清空单位所有护盾
    ---@param unit any
    local function clear_shields(unit)
        local shields = unit._shield_list
        if not shields then return end
        local total = 0
        shields:forEach(function(s)
            total = total + s.value
            s.value = 0
            if s.buff and removeBuff then removeBuff(s.buff) end
        end)
        addAttr(unit, 'shield', -total)
        unit._shield_list = create_linked_list()
    end

    return {
        addShield = add_shield,
        costShield = cost_shield,
        updateShield = update_shield,
        removeShield = remove_shield,
        getTotalShield = get_total_shield,
        clearShields = clear_shields,
    }
end

return M
