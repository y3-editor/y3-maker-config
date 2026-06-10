--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-trace-report
--- @version       v0.1.0
--- @entry         M.setup(params) → TraceReporter 实例
--- @params        request_url, get_player_info, is_editor_mode
--- @source        global_script/gamePlay/utils/functions.lua (UploadToPopo + ReportToBattleServer)
--- @description   HTTP 上报通道：错误上报 + BI 埋点 + 限流防雪崩 + 编辑器环境自动屏蔽。
---
--- 融合契约：
---   1. request_url 对接 y3.game:request_url
---   2. 玩家上下文通过 get_player_info 注入
---   3. 全局错误 hook 调用方自行挂 __G__TRACKBACK__
--- =========================================================================

local M = {}

--- 创建上报器
---@param params {
---   request_url: fun(url: string, body: string, callback: fun(result: any), options: table),
---   get_player_info: fun(player): { platform_name: string, platform_id: any, map_level: number, version: string, level_name: string },
---   json_encode: fun(data: table): string,  -- 注入 y3.json.encode 或等效 JSON 编码器
---   is_editor_mode?: fun(): boolean,
---   cooldown_seconds?: number  # 限流冷却秒数（默认 300）
--- }
---@return table
function M.setup(params)
    assert(type(params) == 'table', 'a-trace-report: params must be a table')
    assert(type(params.request_url) == 'function', 'a-trace-report: request_url required')
    assert(type(params.get_player_info) == 'function', 'a-trace-report: get_player_info required')
    assert(type(params.json_encode) == 'function', 'a-trace-report: json_encode required')

    local request_url = params.request_url
    local get_player_info = params.get_player_info
    local json_encode = params.json_encode
    local is_editor_mode = type(params.is_editor_mode) == 'function'
        and params.is_editor_mode
        or (type(params.is_editor_mode) == 'boolean' and function() return params.is_editor_mode end
            or function() return false end)
    local cooldown_seconds = params.cooldown_seconds or 300

    local instance = {}

    --- 上报到远程服务器
    ---@param url string
    ---@param content string 上报内容（不会被转义）
    ---@param headers? table 自定义 headers
    local function report_to_url(url, content, headers)
        if is_editor_mode() then return end
        if not content or content == '' then return end

        local options = {
            post = true,
            header = headers or { ['Content-Type'] = 'application/json' },
        }

        local body = content
        request_url(url, body, function(result)
            if not result then
                instance._report_failed = true
            end
        end, options)
    end

    --- 限流上报（失败后冷却 cooldown_seconds）
    ---@param url string
    ---@param content string
    ---@param headers? table
    local function report_with_cooldown(url, content, headers)
        if instance._cooldown_timer then return end

        report_to_url(url, content, headers)

        -- 启动冷却定时器
        instance._cooldown_timer = cooldown_seconds
    end

    --- 上报错误（自动附带玩家上下文）
    ---@param error_message string
    ---@param url string 飞书/Popo webhook URL
    function instance:reportError(error_message, url)
        if is_editor_mode() then return end
        if not error_message or error_message == '' then return end

        -- 收集玩家信息
        local player_info_str = ''
        pcall(function()
            local info = get_player_info()
            if info then
                player_info_str = string.format(" %s \n %s \n %s \n %s \n %s \n",
                    info.platform_name or 'unknown',
                    tostring(info.platform_id),
                    info.map_level or 0,
                    info.level_name or 'unknown',
                    info.version or '')
            end
        end)

        local content = player_info_str .. error_message
        -- 转义反斜杠（webhook 可能解析失败）
        content = string.gsub(content, "\\", "-")

        local body = string.format('{"message": "报错：%s"}', content)
        report_with_cooldown(url, body)
    end

    --- 上报 BI 数据（JSON 格式）
    ---@param url string
    ---@param data table 业务数据
    function instance:reportBI(url, data)
        if is_editor_mode() then return end
        local content = json_encode(data)
        report_to_url(url, content)
    end

    --- 更新冷却定时器（外部帧回调调用）
    ---@param dt number 经过时间（秒）
    function instance:updateCooldown(dt)
        if instance._cooldown_timer then
            instance._cooldown_timer = instance._cooldown_timer - dt
            if instance._cooldown_timer <= 0 then
                instance._cooldown_timer = nil
            end
        end
    end

    return instance
end

--- 创建全局错误追踪回调（挂到 __G__TRACKBACK__）
---@param reporter table TraceReporter 实例
---@param url string 上报 URL
---@param error_cache? table 错误去重表
---@return fun(message: string)
function M.createGlobalErrorHandler(reporter, url, error_cache)
    error_cache = error_cache or {}

    return function(message)
        if error_cache[message] then return end
        error_cache[message] = 1
        reporter:reportError(message, url)
    end
end

return M
