--- =========================================================================
--- Y3 功能模板 · logic.lua  (C 级 · 三层架构 DataSchema + Adapter + PureLogic)
--- =========================================================================
---
--- @template-id   c-pick-one-of-many
--- @grade         C
--- @version       v0.1.0
--- @entry         M.setup(adapter)
--- @architecture  three-layer (DataSchema + Adapter + PureLogic)
--- @source        gamePlay/manager/bond/BondPlayerData.lua
---                 gamePlay/manager/ArtifactMgr.lua
---                 gamePlay/manager/TreasureMgr.lua
--- @description   通用「N 选 1」抽卡骨架：加权随机池 → 抽 N 张 → 弹窗展示 → 玩家选择/刷新/放弃 → 业务回调
---
--- 接入只需 3 步：
---   1. 按 §1 DataSchema 准备数据格式
---   2. 实现 §2 Adapter 接口的 10 个必填方法
---   3. M.setup(your_adapter) 后调 M.try_pick(player_id) 触发流程
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 用户必须按此格式提供数据
-- ============================================================================

--- @class PickPoolItem  抽卡池中的单个条目
--- @field id        integer  唯一标识（模板不读取内容，透传给 Adapter 回调）
--- @field weight    integer  权重 (>0)
--- @field group?    string   分组标签（同一 group 内最多抽出 1 张，为空则不限制）
--- @field data?     any      业务自定义透传字段（模板不读取）

--- @class PickResult  抽卡结果中的单张
--- @field item   PickPoolItem  抽中的条目
--- @field slot   integer  展示槽位 (1 .. pick_count)

--- @class PickPopupInfo  传给 Adapter.open_popup 的上下文
--- @field can_refresh  boolean  是否允许刷新
--- @field can_skip     boolean  是否允许放弃
--- @field pick_count   integer  本次展示数量
--- @field pick_serial  integer  本局第几次抽卡（从 1 开始）

-- ============================================================================
-- §2. Adapter 接口 — 用户必须实现以下方法
-- ============================================================================

--- @class PickAdapter
--- @field get_pool              fun(player_id:integer): PickPoolItem[]        必填: 返回当前可抽卡池（含权重）
--- @field get_pick_count        fun(player_id:integer): integer               必填: 一次抽几张 (>= 1)
--- @field can_pick              fun(player_id:integer): boolean, string?      必填: 是否允许抽卡，（false, 拒绝理由）
--- @field consume_cost          fun(player_id:integer): boolean               必填: 扣费，（true=成功）
--- @field open_popup            fun(player_id:integer, results:PickResult[], info:PickPopupInfo)
---                                                                            必填: 打开选择 UI（不阻塞模板流程）
--- @field close_popup           fun(player_id:integer)                        必填: 关闭选择 UI
--- @field on_picked             fun(player_id:integer, item:PickPoolItem)     必填: 玩家选中后的业务回调
--- @field on_skipped            fun(player_id:integer)                        必填: 玩家放弃后的业务回调
--- @field on_refresh_requested  fun(player_id:integer): boolean               必填: 用户点刷新，（true=允许刷新，false=拒绝）
--- @field on_pool_empty         fun(player_id:integer)                        必填: 卡池为空时的通知
---
--- 可选:
--- @field on_pick_rejected      fun(player_id:integer, reason:string)?        可选: 抽卡被拒通知（用于 UI 提示）
--- @field random_fn             fun(): float?                                 可选: 随机数生成器（默认 math.random，单测可注入 seed）
--- @field log                   fun(msg:string)?                              可选: 日志钩子（默认 print）

-- ============================================================================
-- §3. Pure Logic — 用户不需修改
-- ============================================================================

local adapter = nil
local state   = {}  --- @type table<integer, {results:PickResult[], picked:boolean, serial:integer}>

--- 校验 Adapter 必填方法
--- @param a PickAdapter
local function tpl_validate_adapter(a)
    assert(type(a) == 'table', 'adapter must be a table')
    local required = {
        'get_pool', 'get_pick_count', 'can_pick', 'consume_cost',
        'open_popup', 'close_popup', 'on_picked', 'on_skipped',
        'on_refresh_requested', 'on_pool_empty',
    }
    for _, name in ipairs(required) do
        assert(type(a[name]) == 'function',
            'PickAdapter missing required method: ' .. name)
    end
end

--- 取随机数 [0, 1)
--- @return number
local function tpl_random()
    if adapter.random_fn then
        return adapter.random_fn()
    end
    return math.random()
end

--- 加权随机抽 N 张（去重、支持 group 排他）
--- @param pool PickPoolItem[]
--- @param count integer
--- @return PickResult[]
local function tpl_weighted_pick(pool, count)
    if #pool == 0 then
        return {}
    end

    -- 计算总权重
    local total_weight = 0
    for _, item in ipairs(pool) do
        if item.weight > 0 then
            total_weight = total_weight + item.weight
        end
    end
    if total_weight <= 0 then
        return {}
    end

    -- 深拷贝池（避免修改外部数据）
    local remaining = {}
    for i, item in ipairs(pool) do
        remaining[i] = { item = item, idx = i }
    end

    local results = {}
    local picked_groups = {}  --- @type table<string, boolean>
    local max_pick = math.min(count, #remaining)

    for slot = 1, max_pick do
        -- 重新计算当前剩余总权重
        local cur_weight = 0
        for _, r in ipairs(remaining) do
            if r.item.weight > 0 then
                cur_weight = cur_weight + r.item.weight
            end
        end
        if cur_weight <= 0 then
            break
        end

        -- 加权随机
        local roll = tpl_random() * cur_weight
        local accum = 0
        local pick_idx = nil
        for i, r in ipairs(remaining) do
            if r.item.weight > 0 then
                accum = accum + r.item.weight
                if roll < accum then
                    pick_idx = i
                    break
                end
            end
        end
        if not pick_idx then
            break
        end

        local picked = table.remove(remaining, pick_idx)
        results[slot] = { item = picked.item, slot = slot }

        -- group 排他：移除同 group 的其他条目
        if picked.item.group then
            picked_groups[picked.item.group] = true
            local filtered = {}
            for _, r in ipairs(remaining) do
                if not picked_groups[r.item.group or ''] then
                    filtered[#filtered + 1] = r
                end
            end
            remaining = filtered
        end
    end

    return results
end

--- 内部日志
--- @param msg string
local function tpl_log(msg)
    if adapter.log then
        adapter.log('[c-pick-one-of-many] ' .. msg)
    else
        print('[c-pick-one-of-many] ' .. msg)
    end
end

-- ============================================================================
-- 公开 API
-- ============================================================================

---@param user_adapter PickAdapter
function M.setup(user_adapter)
    tpl_validate_adapter(user_adapter)
    adapter = user_adapter
    state   = {}
end

--- 抽卡入口
--- 校验 → 扣费 → 随机抽 N 张 → 开 UI
--- @param player_id integer
--- @return boolean  是否成功触发
function M.try_pick(player_id)
    if not adapter then
        error('M.setup(adapter) not called')
    end

    -- 检查是否有未完成的抽卡
    local s = state[player_id]
    if s and not s.picked then
        -- 重新打开 UI（比如切回游戏后 UI 被关了）
        if adapter.get_pick_count and pcall(adapter.get_pick_count, player_id) then
            adapter.open_popup(player_id, s.results, {
                can_refresh = false,
                can_skip = true,
                pick_count = #s.results,
                pick_serial = s.serial or 1,
            })
        end
        tpl_log(string.format('player %d: pending pick still open', player_id))
        return true
    end

    -- 前置校验
    local ok, reason = adapter.can_pick(player_id)
    if not ok then
        tpl_log(string.format('player %d: rejected (%s)', player_id, reason or 'unknown'))
        if adapter.on_pick_rejected then
            adapter.on_pick_rejected(player_id, reason or '')
        end
        return false
    end

    -- 扣费
    if not adapter.consume_cost(player_id) then
        tpl_log(string.format('player %d: consume_cost failed', player_id))
        return false
    end

    -- 获取卡池
    local pool = adapter.get_pool(player_id)
    if not pool or #pool == 0 then
        tpl_log(string.format('player %d: pool empty', player_id))
        adapter.on_pool_empty(player_id)
        return false
    end

    -- 过滤权重为 0 的条目
    local valid_pool = {}
    for _, item in ipairs(pool) do
        if item.weight > 0 then
            valid_pool[#valid_pool + 1] = item
        end
    end

    local count = adapter.get_pick_count(player_id)
    local results = tpl_weighted_pick(valid_pool, count)

    if #results == 0 then
        tpl_log(string.format('player %d: weighted pick returned empty', player_id))
        adapter.on_pool_empty(player_id)
        return false
    end

    -- 记录状态
    local new_serial = (state[player_id] and state[player_id].serial or 0) + 1
    state[player_id] = {
        results = results,
        picked = false,
        serial = new_serial,
    }

    adapter.open_popup(player_id, results, {
        can_refresh = true,
        can_skip = true,
        pick_count = #results,
        pick_serial = new_serial,
    })

    tpl_log(string.format('player %d: opened pick (%d/%d results)', player_id, #results, count))
    return true
end

--- 玩家选中第 slot 张
--- @param player_id integer
--- @param slot integer  1 起始
function M.confirm_pick(player_id, slot)
    if not adapter then
        error('M.setup(adapter) not called')
    end
    local s = state[player_id]
    if not s then
        tpl_log(string.format('player %d: confirm_pick but no state', player_id))
        return
    end
    if s.picked then
        tpl_log(string.format('player %d: already picked', player_id))
        return
    end

    local r = s.results[slot]
    if not r then
        tpl_log(string.format('player %d: invalid slot %d', player_id, slot))
        return
    end

    s.picked = true
    adapter.close_popup(player_id)
    adapter.on_picked(player_id, r.item)
    tpl_log(string.format('player %d: picked slot %d (id=%s)', player_id, slot, tostring(r.item.id)))

    -- 清理状态，准备下次抽卡
    state[player_id] = nil
end

--- 玩家放弃本次抽卡
--- @param player_id integer
function M.skip_pick(player_id)
    if not adapter then
        error('M.setup(adapter) not called')
    end
    local s = state[player_id]
    if not s then
        return
    end

    adapter.close_popup(player_id)
    adapter.on_skipped(player_id)
    tpl_log(string.format('player %d: skipped', player_id))
    state[player_id] = nil
end

--- 玩家请求刷新（重新随机抽 N 张）
--- @param player_id integer
--- @return boolean  是否成功刷新
function M.refresh_pick(player_id)
    if not adapter then
        error('M.setup(adapter) not called')
    end
    local s = state[player_id]
    if not s then
        return false
    end
    if s.picked then
        return false
    end

    -- 检查是否允许刷新
    if not adapter.on_refresh_requested(player_id) then
        tpl_log(string.format('player %d: refresh rejected', player_id))
        return false
    end

    -- 先关闭当前 UI（先关旧再算新，UX 更流畅）
    adapter.close_popup(player_id)

    -- 重新随机
    local pool = adapter.get_pool(player_id)
    local valid_pool = {}
    for _, item in ipairs(pool) do
        if item.weight > 0 then
            valid_pool[#valid_pool + 1] = item
        end
    end

    local count = adapter.get_pick_count(player_id)
    local results = tpl_weighted_pick(valid_pool, count)

    if #results == 0 then
        adapter.on_pool_empty(player_id)
        return false
    end

    s.results = results
    s.picked = false

    adapter.open_popup(player_id, results, {
        can_refresh = true,
        can_skip = true,
        pick_count = #results,
        pick_serial = s.serial or 1,
    })

    tpl_log(string.format('player %d: refreshed pick (%d results)', player_id, #results))
    return true
end

--- 只读获取当前抽卡结果（供 UI refresh 用）
--- @param player_id integer
--- @return PickResult[]?
function M.peek_results(player_id)
    if not adapter then
        error('M.setup(adapter) not called')
    end
    local s = state[player_id]
    if not s then
        return nil
    end
    return s.results
end

--- 是否有未完成的抽卡
--- @param player_id integer
--- @return boolean
function M.has_pending(player_id)
    if not adapter then
        error('M.setup(adapter) not called')
    end
    local s = state[player_id]
    return s ~= nil and not s.picked
end

return M
