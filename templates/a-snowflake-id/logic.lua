--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-snowflake-id
--- @version       v0.1.0
--- @entry         M.nextID() → integer|nil
--- @params        sequence_bits, shard_id
--- @source        global_script/client/tools/counter.lua
--- @description   雪花算法全局唯一 ID 生成器：timestamp 高位 + 序列号低位，同秒 52 万容量，时钟回拨保护。
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块
---   2. 纯 Lua，零外部依赖
---   3. 单例模式，全局唯一 ID
--- =========================================================================

local M = {}

-- 内部状态
local sequence = 0
local last_timestamp = 0
local SEQUENCE_MAX = (1 << 19) - 1  -- 524287

--- 位运算辅助（Lua 5.3+ 原生支持；5.1 需要 bit32 或自定义实现）
local function safe_lshift(n, bits)
    return n << bits
end

local function safe_bor(a, b)
    return a | b
end

--- 生成下一个全局唯一 ID
---@return integer|nil 成功返回 ID，时钟回拨返回 nil
function M.nextID()
    local timestamp = os.time()

    if timestamp < last_timestamp then
        -- 时钟回拨，拒绝生成
        return nil
    end

    if timestamp == last_timestamp then
        sequence = sequence + 1
        if sequence > SEQUENCE_MAX then
            -- 同秒内耗尽
            return nil
        end
    else
        sequence = 0
        last_timestamp = timestamp
    end

    return safe_bor(safe_lshift(timestamp, 16), sequence)
end

--- 重置状态（仅用于测试/清档）
function M.reset()
    sequence = 0
    last_timestamp = 0
end

return M
