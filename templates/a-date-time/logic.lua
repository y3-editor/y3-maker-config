--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-date-time
--- @version       v0.1.0
--- @entry         M.setup(params) → 注入时间工具函数
--- @params        get_server_time
--- @source        global_script/gamePlay/utils/TimeTool.lua + DateHelper.lua
--- @description   时间格式化/时间戳转换/跨日跨周判定/倒计时/模拟时间，纯 Lua + os.date。
---
--- 融合契约：
---   1. 调用方将本文件融入目标模块
---   2. params.get_server_time 映射到 GameAPI（如 y3.game.get_current_server_time）
---   3. 返回的表可直接并入 GameAPI 或 y3 全局表
--- =========================================================================

local M = {}

--- 创建时间工具集
---@param params { get_server_time: fun(hour_offset: integer): { timestamp: integer } | nil }
---@return table 时间工具函数表
function M.setup(params)
    assert(type(params) == 'table', 'a-date-time: params must be a table')

    local SELF = {}
    local get_server_time = params.get_server_time
    local UTC_OFFSET = params.utc_offset or 8

    --- 获取当前时间戳（支持模拟时间）
    local function getTimestamp()
        if SELF._artificial_bool and SELF._artificial_time then
            return math.floor(SELF._artificial_time)
        end
        if get_server_time then
            local server = get_server_time(UTC_OFFSET)
            if server and server.timestamp then
                return math.floor(server.timestamp)
            end
        end
        return os.time()
    end

    --- 设置模拟时间（GM 调试）
    local function setTime(new_time)
        SELF._artificial_time = new_time
        SELF._artificial_bool = true
    end

    --- 关闭模拟时间
    local function setTimeOff()
        SELF._artificial_bool = false
    end

    -- =========================== 格式化 ===========================

    --- 秒数 → MM:SS
    local function countToTime(seconds, includeHour)
        seconds = math.max(0, math.floor(seconds))
        if includeHour then
            return string.format("%02d:%02d:%02d",
                math.floor(seconds / 3600),
                math.floor((seconds % 3600) / 60),
                math.floor(seconds % 60))
        else
            return string.format("%02d:%02d",
                math.floor(seconds / 60),
                math.floor(seconds % 60))
        end
    end

    --- 时间戳 → 日期时间字符串
    local function timestamp_to_datetime(ts, strType)
        local dt = os.date("!*t", ts + UTC_OFFSET * 3600)
        if strType == 1 then
            return string.format("%04d.%02d.%02d/%02d:%02d", dt.year, dt.month, dt.day, dt.hour, dt.min)
        end
        return string.format("%04d-%02d-%02d %02d:%02d", dt.year, dt.month, dt.day, dt.hour, dt.min)
    end

    --- 时间戳 → 日期
    local function timestamp_to_date(ts)
        local dt = os.date("!*t", ts + UTC_OFFSET * 3600)
        return string.format("%04d-%02d-%02d", dt.year, dt.month, dt.day)
    end

    --- 秒数 → MM:SS
    local function format_time(seconds)
        return string.format("%02d:%02d", math.floor(seconds / 60), seconds % 60)
    end

    --- 秒数 → HH:MM:SS
    local function format_time_hours(seconds)
        local h = math.floor(seconds / 3600)
        local m = math.floor((seconds % 3600) / 60)
        local s = seconds % 60
        return string.format("%02d:%02d:%02d", h, m, s)
    end

    -- =========================== 跨日/跨周判定 ===========================

    --- 基于当天 0 点计算两个时间戳相距天数
    local function getDayDiffByMidnight(epoch1, epoch2)
        local function toMidnight(ts)
            local t = os.date("!*t", ts + UTC_OFFSET * 3600)
            return os.time({ year = t.year, month = t.month, day = t.day, hour = 0, min = 0, sec = 0 })
        end
        if epoch1 == 0 then epoch1 = getTimestamp() end
        return math.floor(math.abs(toMidnight(epoch1) - toMidnight(epoch2)) / (24 * 60 * 60))
    end

    --- 是否同一天
    local function isSameDate(epoch1, epoch2)
        if not epoch1 or not epoch2 then return true end
        return os.date("!%x", epoch1 + UTC_OFFSET * 3600) == os.date("!%x", epoch2 + UTC_OFFSET * 3600)
    end

    --- 是否同一周
    local function isSameWeek(epoch1, epoch2)
        local off = UTC_OFFSET * 3600
        local y1, w1 = tostring(os.date("!%Y %W", epoch1 + off)):match("(%d+) (%d+)")
        local y2, w2 = tostring(os.date("!%Y %W", epoch2 + off)):match("(%d+) (%d+)")
        y1, w1 = tonumber(y1), tonumber(w1); y2, w2 = tonumber(y2), tonumber(w2)
        if w1 == 0 then y1 = y1 - 1; w1 = 52 end
        if w2 == 0 then y2 = y2 - 1; w2 = 52 end
        return y1 == y2 and w1 == w2
    end

    --- 获取周几（周一=1，周日=7）
    local function getDayOfWeek(ts)
        local dt = os.date("!*t", ts + UTC_OFFSET * 3600)
        return dt.wday == 1 and 7 or dt.wday - 1
    end

    --- 是否周末
    local function inWeekend(ts)
        local dow = getDayOfWeek(ts)
        return dow == 6 or dow == 7
    end

    -- =========================== 时间区间 ===========================

    --- 在时间范围内（前后可空）
    local function inTimeInterval(time, front_time, end_time)
        if front_time and time < front_time then return false end
        if end_time and time >= end_time then return false end
        return true
    end

    --- 字符串时间 → 时间戳（格式：2025-6-4-0）
    local function time_get(str)
        if not str or not string.find(str, '-') then return 0 end
        local parts = {}
        for part in string.gmatch(str, "[^-]+") do
            parts[#parts + 1] = tonumber(part) or 0
        end
        local t = os.time({
            year = parts[1], month = parts[2], day = parts[3],
            hour = parts[4] or 0, min = parts[5] or 0, sec = parts[6] or 0,
            isdst = false,
        })
        return t - UTC_OFFSET * 3600
    end

    --- 配置时间区间开关判定（data.open + data.open_time/data.end_time）
    local function is_open_by_data(data, suffix)
        suffix = suffix or ''
        if not data.open then return false end
        local open_t = data['open_time' .. suffix]
        local end_t = data['end_time' .. suffix]
        if open_t and open_t ~= '' then open_t = time_get(open_t) end
        if end_t and end_t ~= '' then end_t = time_get(end_t) end
        if not open_t and not end_t then return true end
        return inTimeInterval(getTimestamp(), open_t, end_t)
    end

    -- =========================== 未来 0 点 ===========================

    --- 明天 0 点时间戳
    local function getNextMidnightTimestamp(ts)
        local now = ts or getTimestamp()
        local t = os.date("!*t", now + UTC_OFFSET * 3600 + 24 * 3600)
        return os.time({ year = t.year, month = t.month, day = t.day, hour = 0, min = 0, sec = 0 })
    end

    --- 下周一 0 点时间戳
    local function getNextMondayMidnightTimestamp(ts)
        local now = ts or getTimestamp()
        local dow = getDayOfWeek(now)
        local days = (8 - dow) % 7
        if days == 0 then days = 7 end
        local t = os.date("!*t", now + UTC_OFFSET * 3600 + days * 24 * 3600)
        return os.time({ year = t.year, month = t.month, day = t.day, hour = 0, min = 0, sec = 0 })
    end

    -- =========================== 时间差 ===========================

    --- 时间差格式化（t1 - 当前时间）
    local function get_time_difftime(t1, strType)
        local diff = os.difftime(t1, getTimestamp())
        local days = math.floor(diff / 86400)
        local hours = math.floor((diff % 86400) / 3600)
        local mins = math.floor((diff % 3600) / 60)
        local secs = diff % 60
        if strType == 1 then
            if days > 0 then return string.format("%d天%d小时", days, hours)
            elseif hours > 0 then return string.format("%d小时%d分", hours, mins)
            else return string.format("%d分", mins) end
        end
        if days > 0 then return string.format("%d天%d小时", days, hours)
        elseif hours > 0 then return string.format("%d小时%d分%d秒", hours, mins, secs)
        elseif mins > 0 then return string.format("%d分%d秒", mins, secs)
        else return string.format("%d秒", secs) end
    end

    return {
        -- 基础
        getTimestamp = getTimestamp,
        setTime = setTime,
        setTimeOff = setTimeOff,
        -- 格式化
        countToTime = countToTime,
        timestamp_to_datetime = timestamp_to_datetime,
        timestamp_to_date = timestamp_to_date,
        format_time = format_time,
        format_time_hours = format_time_hours,
        -- 跨日/跨周
        getDayDiffByMidnight = getDayDiffByMidnight,
        isSameDate = isSameDate,
        isSameWeek = isSameWeek,
        getDayOfWeek = getDayOfWeek,
        inWeekend = inWeekend,
        -- 区间
        inTimeInterval = inTimeInterval,
        time_get = time_get,
        is_open_by_data = is_open_by_data,
        -- 未来
        getNextMidnightTimestamp = getNextMidnightTimestamp,
        getNextMondayMidnightTimestamp = getNextMondayMidnightTimestamp,
        -- 时间差
        get_time_difftime = get_time_difftime,
    }
end

return M
