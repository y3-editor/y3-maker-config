--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   b-gm-command
--- @version       v0.1.0
--- @entry         M.setup(params) → GM 控制台
--- @params        register_command, dev_only
--- @source        global_script/gamePlay/utils/GM.lua + Command.lua + GMUtils.lua
--- @description   GM 调试指令系统：注册 / 排序展示 / 记录回放 / 剪贴板拷贝。
---
--- 融合契约：
---   1. params.register_command 对接 y3.develop.command.register
---   2. 需要 UI 辅助（剪贴板、命令显示）通过 params.ui 注入
---   3. 生产环境可 params.dev_only=true 屏蔽所有指令
--- =========================================================================

local M = {}

local commands = {} ---@type { name: string, config: table }[]
local history = {}   ---@type string[]

--- 创建 GM 系统
---@param params { register_command: fun(name: string, config: table), dev_only?: boolean, on_input?: fun(player, cmd, args: string[]) }
---@return table
function M.setup(params)
    assert(type(params) == 'table', 'b-gm-command: params must be a table')
    assert(type(params.register_command) == 'function', 'b-gm-command: register_command required')

    local register_command = params.register_command
    local dev_only = params.dev_only ~= false

    local instance = {}

    --- 注册 GM 命令
    ---@param name string 命令名
    ---@param config { sort?: integer, needSync?: boolean, priority?: integer, desc?: string, onCommand: fun(...) }
    function instance:register(name, config)
        assert(type(name) == 'string', 'b-gm-command: command name required')
        assert(type(config) == 'table' and type(config.onCommand) == 'function',
            'b-gm-command: config.onCommand required')

        if dev_only then
            -- dev_only 模式下不注册到引擎，只保记录
            table.insert(commands, { name = name, config = config })
            return
        end

        register_command(name, {
            sort = config.sort or 0,
            needSync = config.needSync or false,
            priority = config.priority or 100,
            desc = config.desc or name,
            onCommand = function(...)
                config.onCommand(...)
                insert_history(name, ...)
            end,
        })

        table.insert(commands, { name = name, config = config })
    end

    --- 插入历史记录
    local function insert_history(cmd, ...)
        local text = '.' .. cmd
        local args = { ... }
        for i = 1, #args do
            text = text .. ' ' .. tostring(args[i])
        end
        -- 排除记录类命令自身
        local no_record = { clearRecord = true, printRecord = true, runRecord = true }
        if not no_record[cmd] then
            table.insert(history, text)
        end
    end

    --- 清空历史记录
    function instance:clearRecord()
        history = {}
    end

    --- 打印历史记录（返回可执行的命令序列字符串）
    ---@return string
    function instance:printRecord()
        local parts = {}
        for _, h in ipairs(history) do
            parts[#parts + 1] = h
        end
        local result = table.concat(parts, '\n')
        history = {}
        return result
    end

    --- 解析并执行输入（格式：.cmd arg1 arg2 ...）
    ---@param msg string
    ---@param player? Player
    function instance:input(msg, player)
        if not msg or msg == '' or msg:sub(1, 1) ~= '.' then return end
        local tokens = {}
        for token in string.gmatch(msg, '[^ ]+') do
            tokens[#tokens + 1] = token
        end
        local cmd_name = tokens[1]:sub(2) -- 去掉前缀 '.'
        if cmd_name == '' then return end
        local args = { select(2, table.unpack(tokens)) }

        for _, entry in ipairs(commands) do
            if entry.name == cmd_name then
                local safe_args = { player }
                for _, a in ipairs(args) do
                    safe_args[#safe_args + 1] = a
                end
                local ok, err = pcall(entry.config.onCommand, table.unpack(safe_args))
                if not ok then
                    if params.on_error then params.on_error(err) end
                end
                insert_history(cmd_name, table.unpack(args))
                return
            end
        end
    end

    --- 获取所有已注册命令列表
    ---@return { name: string, desc: string }[]
    function instance:listCommands()
        local result = {}
        for _, entry in ipairs(commands) do
            result[#result + 1] = {
                name = entry.name,
                desc = entry.config.desc or entry.name,
                sort = entry.config.sort or 0,
            }
        end
        table.sort(result, function(a, b) return a.sort < b.sort end)
        return result
    end

    return instance
end

return M
