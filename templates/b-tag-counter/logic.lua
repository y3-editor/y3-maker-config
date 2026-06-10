---标签计数器模板（B 级）
---纯算法 + 回调，零业务依赖，零引擎 API 调用。
---
---## 集成方式
---```lua
---local TagCounter = include 'b-tag-counter.logic'
---local tc = TagCounter.setup({
---    tagDefs = {
---        [1] = { name = "炽焰", thresholds = {2, 4, 6} },
---    },
---    callbacks = {
---        onLevelUp   = function(pid, tid, newLv, oldLv) end,
---        onLevelDown = function(pid, tid, newLv, oldLv) end,
---    },
---})
---tc:addTag(1, 1)       -- 玩家1，标签1，+1
---tc:removeTag(1, 1)    -- 玩家1，标签1，-1
---```

---@class TagDef
---@field name string 标签显示名
---@field icon? integer 标签图标资源 ID
---@field thresholds integer[] 触发阶梯，必须升序，如 {2,4,6}

---@class TagCounterCallbacks
---@field onLevelUp? fun(playerId:integer, tagId:integer, newLevel:integer, oldLevel:integer) 标签升级（可能跨多级逐级触发）
---@field onLevelDown? fun(playerId:integer, tagId:integer, newLevel:integer, oldLevel:integer) 标签降级（可能跨多级逐级触发）
---@field onCountChange? fun(playerId:integer, tagId:integer, count:integer, level:integer) 数量变化（每次 add/remove 触发一次）

---@class TagCounterParams
---@field tagDefs table<integer, TagDef> 标签定义表
---@field perPlayer? boolean 是否每玩家独立数据，默认 true
---@field callbacks? TagCounterCallbacks

local M = Class('TagCounter')

function M:__init(params)
    params = params or {}
    -- 标签定义校验 + 阶梯排序
    self._tagDefs = {}
    for tagId, def in pairs(params.tagDefs or {}) do
        local sorted = {}
        for _, v in ipairs(def.thresholds or {}) do
            sorted[#sorted + 1] = v
        end
        table.sort(sorted)
        self._tagDefs[tagId] = {
            name = def.name or ('Tag_' .. tostring(tagId)),
            icon = def.icon,
            thresholds = sorted,
        }
    end

    self._cb = params.callbacks or {}
    self._perPlayer = params.perPlayer
    if self._perPlayer == nil then
        self._perPlayer = true
    end

    ---@type table<integer, table<integer, {count:integer, level:integer}>>
    self._data = {}
end

-- ============================================================
-- 公开 API
-- ============================================================

---§1 写入标签（增加计数）
---@param playerId integer
---@param tagId integer
---@param n? integer 增加数量，默认 1
function M:addTag(playerId, tagId, n)
    n = n or 1
    if n <= 0 then return end
    local s = self:_ensure(playerId, tagId)
    s.count = s.count + n
    self:_recheck(playerId, tagId, s)
end

---§2 删除标签（减少计数）
---@param playerId integer
---@param tagId integer
---@param n? integer 减少数量，默认 1
function M:removeTag(playerId, tagId, n)
    n = n or 1
    if n <= 0 then return end
    local s = self:_ensure(playerId, tagId)
    -- 逐级递减：每减 1 重新检查阶梯，确保跨级触发完整链路
    for _ = 1, n do
        if s.count <= 0 then break end
        s.count = s.count - 1
        self:_recheck(playerId, tagId, s)
    end
end

---获取标签当前计数
---@return integer
function M:getCount(playerId, tagId)
    local s = self._data[playerId] and self._data[playerId][tagId]
    return s and s.count or 0
end

---获取标签当前激活阶梯
---@return integer 0 = 未激活任何阶梯
function M:getLevel(playerId, tagId)
    local s = self._data[playerId] and self._data[playerId][tagId]
    return s and s.level or 0
end

---获取玩家所有标签的阶梯（快照）
---@return table<integer, integer>
function M:getAllLevels(playerId)
    local result = {}
    local pd = self._data[playerId]
    if pd then
        for tagId, s in pairs(pd) do
            result[tagId] = s.level
        end
    end
    return result
end

---重置玩家数据
---@param playerId integer
---@param tagId? integer 不传则清空该玩家所有数据
function M:reset(playerId, tagId)
    if tagId then
        local pd = self._data[playerId]
        if pd then
            local s = pd[tagId]
            if s then
                s.count = 0
                self:_recheck(playerId, tagId, s)
            end
        end
    else
        self._data[playerId] = nil
    end
end

---获取标签定义
---@param tagId integer
---@return TagDef|nil
function M:getTagDef(tagId)
    return self._tagDefs[tagId]
end

---获取所有标签定义
---@return table<integer, TagDef>
function M:getAllTagDefs()
    return self._tagDefs
end

---获取下一个未达成的阶梯值
---@param playerId integer
---@param tagId integer
---@return integer|nil 返回阈值，若已全部达成返回 nil
function M:getNextThreshold(playerId, tagId)
    local def = self._tagDefs[tagId]
    if not def then return nil end
    local level = self:getLevel(playerId, tagId)
    if level >= #def.thresholds then return nil end
    return def.thresholds[level + 1]
end

-- ============================================================
-- 内部方法
-- ============================================================

function M:_ensure(playerId, tagId)
    if not self._data[playerId] then
        self._data[playerId] = {}
    end
    local pd = self._data[playerId]
    if not pd[tagId] then
        pd[tagId] = { count = 0, level = 0 }
    end
    return pd[tagId]
end

---重新检查阶梯并触发回调
function M:_recheck(playerId, tagId, s)
    local def = self._tagDefs[tagId]
    if not def then return end

    local oldLv = s.level
    -- 计算新阶梯：从高到低找第一个满足的
    local newLv = 0
    for i = #def.thresholds, 1, -1 do
        if s.count >= def.thresholds[i] then
            newLv = i
            break
        end
    end

    -- 升级链路：逐级触发，确保每级都被感知
    if newLv > oldLv then
        for lv = oldLv + 1, newLv do
            if self._cb.onLevelUp then
                self._cb.onLevelUp(playerId, tagId, lv, lv - 1)
            end
        end
    -- 降级链路：逐级触发
    elseif newLv < oldLv then
        for lv = oldLv, newLv + 1, -1 do
            if self._cb.onLevelDown then
                self._cb.onLevelDown(playerId, tagId, lv - 1, lv)
            end
        end
    end

    s.level = newLv

    -- 数量变化回调（不论阶梯是否变化都触发）
    if self._cb.onCountChange then
        self._cb.onCountChange(playerId, tagId, s.count, newLv)
    end
end

-- ============================================================
-- B 级模板入口
-- ============================================================

---B 级标准入口
---@param params TagCounterParams
---@return TagCounter
function M.setup(params)
    local inst = New('TagCounter')
    inst(params)
    return inst
end

return M
