--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-number-abbr
--- @version       v0.1.0
--- @entry         M.format(num, opts) → string | M.setup(opts) → formatter
--- @params        无（纯 Lua）
--- @source        global_script/client/damage/features.lua (formatNumber)
--- @description   大数字缩写格式化：10000→1.0w, 100000000→1.0e。可选多级缩写。
---
--- 融合契约：
---   1. 纯 Lua，零依赖
---   2. M.format(num) 直接调用，无需 setup
--- =========================================================================

local M = {}

local DEFAULT_LEVELS = {
    { threshold = 100000000, suffix = 'e', divisor = 100000000 },
    { threshold = 10000,     suffix = 'w', divisor = 10000 },
}

--- 格式化数字为缩写字符串
---@param num number
---@param opts? { levels?: {threshold:number, suffix:string, divisor:number}[], precision?: integer }
---@return string
function M.format(num, opts)
    opts = opts or {}
    local levels = opts.levels or DEFAULT_LEVELS
    local precision = opts.precision or 1

    if num < 0 then
        return '-' .. M.format(-num, opts)
    end

    for _, level in ipairs(levels) do
        if num >= level.threshold then
            return string.format('%.' .. precision .. 'f%s', num / level.divisor, level.suffix)
        end
    end

    return tostring(math.floor(num))
end

--- 创建自定义格式化器
---@param opts? { levels?: {threshold:number, suffix:string, divisor:number}[], precision?: integer }
---@return fun(num: number): string
function M.setup(opts)
    return function(num)
        return M.format(num, opts)
    end
end

return M
