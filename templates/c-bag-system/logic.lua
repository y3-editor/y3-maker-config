--- =========================================================================
--- Y3 功能模板 · logic.lua  (C 级 · 三层架构 DataSchema + Adapter + PureLogic)
--- =========================================================================
---
--- @template-id   c-bag-system
--- @grade         C
--- @version       v0.1.0
--- @entry         M.setup(adapter, params)
--- @architecture  three-layer (DataSchema + Adapter + PureLogic)
--- @source        global_script/client/bag/bag.lua
--- @description   多背包槽位管理系统 — 提供 N 个具名背包的槽位/堆叠/移动/交换/拾取流程
---
--- 接入只需 3 步：
---   1. 按 §1 DataSchema 准备物品数据格式
---   2. 实现 §2 Adapter 接口的 13 个必填方法
---   3. M.setup(your_adapter, params) 后通过 M.create / M.pre_pick 触发流程
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 用户必须按此格式提供数据
-- ============================================================================

--- @class BagConfig  单个背包配置
--- @field maxSlot   integer       初始最大槽位数 (≥1)
--- @field bagType   integer[]     接受的物品类型ID（拾取/消耗路由用）
--- @field pick?     integer       拾取优先级（数字越小越优先，缺省999最低）
--- @field cost?     integer       消耗优先级（数字越小越优先，缺省则不可从此背包消耗）
--- @field expand?   string        扩展货币 key，该货币持有量加到 maxSlot；无则不扩展

--- @class Item  用户自定义的物品表，模板不直接访问字段，全部通过 §2 Adapter 读写

--- @class Player  用户自定义的玩家对象，模板不直接访问字段

-- ============================================================================
-- §2. Adapter 接口 — 用户必须实现以下方法
-- ============================================================================

--- @class BagAdapter
--- @field get_item_config_id   fun(item:Item):integer                                          必填: 取物品配置ID
--- @field get_item_count       fun(item:Item):integer                                          必填: 取物品数量
--- @field set_item_count       fun(item:Item, n:integer)                                       必填: 设置数量（0=销毁）
--- @field get_item_owner       fun(item:Item):integer                                          必填: 取物品所属玩家ID
--- @field set_item_owner       fun(item:Item, owner_id:integer)                                必填: 设置所属
--- @field get_item_location    fun(item:Item):(bag_name:string?, slot:integer?)                 必填: 取物品所在背包名+槽位
--- @field set_item_location    fun(item:Item, bag_name:string?, slot:integer?)                  必填: 设置位置
--- @field try_stack_to_item    fun(src:Item, dst:Item):(total_stacked:boolean, partial:boolean) 必填: 尝试堆叠两物品
--- @field get_stack_limit      fun(config_id:integer):integer                                   必填: 取堆叠上限（≤1=不可堆）
--- @field is_transferable      fun(config_id:integer):boolean                                   必填: 是否可跨玩家转让
--- @field create_item          fun(player_id:integer, config_id:integer, on_create?:(fun(item:Item))):Item?  必填: 创建物品
--- @field get_player_id        fun(player:Player):integer                                       必填: 取玩家ID
--- @field get_player_currency  fun(player:Player, currency_key:string):integer                  必填: 取货币数量
--- @field is_neutral_friend    fun(player_id:integer)?:boolean                                  可选: 是否中立友好（默认 false）
--- @field on_slot_changed      fun(bag:table, slot:integer)?                                    可选: 槽位变化回调
--- @field on_item_moved        fun(item:Item, from_bag:table)?                                  可选: 物品移动回调
--- @field log                  fun(msg:string)?                                                 可选: 日志钩子

-- ============================================================================
-- §3. Pure Logic — 用户不需修改
-- ============================================================================

local adapter = nil
local cfg     = nil
local M_setup_called = false

--- @type table<string, table> 共享背包缓存
local shared_bags = {}
local pick_cache  = {}
local cost_cache  = {}

-- ---------------------------------------------------------------------------
-- 内部工具函数
-- ---------------------------------------------------------------------------

--- 排序迭代器：按 key 排序后遍历 table
--- @generic K, V
local function tpl_sort_pairs(t, comp)
    local keys = {}
    for k in pairs(t) do keys[#keys + 1] = k end
    table.sort(keys, comp or function(a, b) return a < b end)
    local i = 0
    return function()
        i = i + 1
        local k = keys[i]
        if k then return k, t[k] end
    end
end

--- 数组包含检查
--- @return boolean
local function tpl_array_has(arr, v)
    if not arr then return false end
    for i = 1, #arr do
        if arr[i] == v then return true end
    end
    return false
end

--- Adapter 校验
local function tpl_validate_adapter(a)
    assert(type(a) == 'table', 'adapter must be a table')
    local required = {
        'get_item_config_id',
        'get_item_count',
        'set_item_count',
        'get_item_owner',
        'set_item_owner',
        'get_item_location',
        'set_item_location',
        'try_stack_to_item',
        'get_stack_limit',
        'is_transferable',
        'create_item',
        'get_player_id',
        'get_player_currency',
    }
    for _, name in ipairs(required) do
        assert(type(a[name]) == 'function', 'BagAdapter missing required method: ' .. name)
    end
end

--- 安全获取 owner_id（player 为 nil 时用于共享背包）
local function tpl_safe_owner(player)
    if player then return adapter.get_player_id(player) end
    return nil
end

-- ---------------------------------------------------------------------------
-- Bag 类定义
-- ---------------------------------------------------------------------------

local Bag = {}
Bag.__index = Bag

--- 创建背包实例
--- @param player  Player?  所属玩家（共享背包传 nil）
--- @param name    string   背包名（对应 cfg.configs 中的 key）
--- @return table
local function tpl_new_bag(player, name)
    local config       = cfg.configs[name]
    local sharedConfig = cfg.shared_configs[name]
    if not config and not sharedConfig then
        error('[c-bag-system] bag config not found: ' .. tostring(name))
    end
    local bag = setmetatable({}, Bag)
    bag.player  = player
    bag.name    = name
    bag.items   = {}
    bag.shared  = false
    -- 私有配置优先于共享配置：同名时私有背包覆盖共享背包的定义
    if config then
        bag.maxSlot = config.maxSlot
    elseif sharedConfig then
        bag.maxSlot = sharedConfig.maxSlot
        bag.shared  = true
    end
    return bag
end

--- 获得玩家对象
function Bag:getPlayer()
    return self.player
end

--- 调整背包大小（裁掉尾部多余槽位）
function Bag:resize(size)
    for slot = size + 1, self.maxSlot do
        self:setSlot(slot, nil)
    end
    self.maxSlot = size
end

--- 获得当前最大槽位（含扩展）
function Bag:getMaxSlot()
    local config = cfg.configs[self.name]
    if not config then return self.maxSlot end
    local expand = config.expand
    if not expand then return self.maxSlot end
    local currency = adapter.get_player_currency(self:getPlayer(), expand)
    local int_currency = math.tointeger(currency)
    if not int_currency then
        int_currency = 0
    end
    return self.maxSlot + int_currency
end

--- 根据配置 ID 查找物品
--- @return Item?
function Bag:getItemById(cid)
    for i = 1, self.maxSlot do
        local item = self.items[i]
        if item and adapter.get_item_config_id(item) == cid
               and adapter.get_item_count(item) > 0 then
            return item
        end
    end
end

--- 判断物品是否可放入本背包
function Bag:canInsertItem(item)
    local item_owner = adapter.get_item_owner(item)
    local my_owner   = tpl_safe_owner(self.player)
    if (adapter.is_neutral_friend and adapter.is_neutral_friend(item_owner))
        or (adapter.is_neutral_friend and my_owner and adapter.is_neutral_friend(my_owner)) then
        return true
    end
    local cid = adapter.get_item_config_id(item)
    if item_owner ~= my_owner and not adapter.is_transferable(cid) then
        return false, cfg.texts.item_not_yours
    end
    return true
end

--- 交换两个物品
function Bag:exchangeItem(itemA, targetBag, itemB)
    local _, slotA       = adapter.get_item_location(itemA)
    local bagB_name, slotB = adapter.get_item_location(itemB)
    targetBag:setSlot(slotB, itemA)
    adapter.set_item_location(itemA, bagB_name, slotB)
    self:setSlot(slotA, itemB)
    adapter.set_item_location(itemB, self.name, slotA)
    if adapter.on_item_moved then adapter.on_item_moved(itemA, self) end
    if adapter.on_item_moved then adapter.on_item_moved(itemB, targetBag) end
    return true
end

--- 移动物品到指定槽位
function Bag:moveToSlot(item, targetBag, targetSlot)
    local otherItem = targetBag.items[targetSlot]
    if otherItem then
        local other_bag, other_slot = adapter.get_item_location(otherItem)
        if targetBag.name ~= other_bag or targetSlot ~= other_slot then
            return false, cfg.texts.slot_info_mismatch
        end
        -- 先尝试堆叠
        local totalStacked, partialStacked = adapter.try_stack_to_item(item, otherItem)
        if totalStacked or partialStacked then return true, otherItem end
        -- 再尝试交换
        local suc, err = self:exchangeItem(item, targetBag, otherItem)
        if not suc then return false, err end
        return suc, otherItem
    else
        return self:moveToEmptySlot(item, targetBag, targetSlot)
    end
end

--- 移动物品（自动找空位/堆叠）
function Bag:move(item, targetBag, targetSlot)
    local valid, err = self:canInsertItem(item)
    if not valid then return false, err end
    local _, slot = adapter.get_item_location(item)
    if not slot then return false, cfg.texts.item_not_in_bag end
    local targetValid, targetErr = targetBag:canInsertItem(item)
    if not targetValid then return false, targetErr end
    if targetSlot then
        return self:moveToSlot(item, targetBag, targetSlot)
    end
    -- 先尝试堆叠到同名物品
    for _, otherItem in tpl_sort_pairs(targetBag.items) do
        if item ~= otherItem then
            local _, partialStacked = adapter.try_stack_to_item(item, otherItem)
            if partialStacked then return true, otherItem end
        end
    end
    -- 找空位
    local emptySlot = targetBag:findFirstEmptySlot()
    if not emptySlot then return false, cfg.texts.bag_full end
    return self:moveToEmptySlot(item, targetBag, emptySlot)
end

--- 移动物品到空槽位
function Bag:moveToEmptySlot(item, targetBag, targetSlot)
    local _, slot = adapter.get_item_location(item)
    if not slot then return false, cfg.texts.item_not_in_bag end
    self:freeSlot(slot)
    targetBag:setSlot(targetSlot, item)
    adapter.set_item_location(item, targetBag.name, targetSlot)
    if adapter.on_item_moved then adapter.on_item_moved(item, self) end
    return true, nil
end

--- 在槽位创建物品
function Bag:createItem(slot, cid, onCreate)
    if self.items[slot] then return nil end
    local owner_id = tpl_safe_owner(self.player)
    local item = adapter.create_item(owner_id, cid, function(newItem)
        adapter.set_item_location(newItem, self.name, slot)
        if onCreate then onCreate(newItem) end
    end)
    if not item then return nil end
    self:setSlot(slot, item)
    return item
end

--- 堆叠算法（内部）
--- @return integer     remaining count
--- @return integer?    extra items generated
--- @return function[]? deferred actions
function Bag:pickAsStack(item, leftNum)
    local cid     = adapter.get_item_config_id(item)
    local stacking = adapter.get_stack_limit(cid)
    if not stacking or stacking <= 1 then return leftNum, nil, nil end
    local actions = {}
    -- (1) 尽量填满同 cid 已有物品
    for i = 1, self:getMaxSlot() do
        local it = self.items[i]
        if it and it ~= item
             and adapter.get_item_config_id(it) == cid
             and adapter.get_item_count(it) < stacking then
            local total = adapter.get_item_count(it) + leftNum
            if total > stacking then
                leftNum = total - stacking
                local locLeftNum = leftNum
                actions[#actions + 1] = function()
                    adapter.set_item_count(it, stacking)
                end
            else
                actions[#actions + 1] = function()
                    adapter.set_item_count(it, total)
                    adapter.set_item_count(item, 0)
                end
                return 0, 0, actions
            end
        end
    end
    -- (2) 多余部分另开新格子
    local extra = 0
    for i = 1, self:getMaxSlot() do
        if leftNum <= stacking then break end
        if not self.items[i] then
            extra = extra + 1
            leftNum = leftNum - stacking
            actions[#actions + 1] = function()
                self:createItem(i, cid, function(newItem)
                    adapter.set_item_location(newItem, self.name, i)
                    adapter.set_item_count(newItem, stacking)
                end)
            end
        end
    end
    -- (3) 更新原物品数量为剩余值
    if leftNum ~= adapter.get_item_count(item) then
        actions[#actions + 1] = function()
            adapter.set_item_count(item, leftNum)
        end
    end
    return leftNum, extra, actions
end

--- 找首个空槽位
function Bag:findFirstEmptySlot(skip)
    skip = skip or 0
    for i = 1, self:getMaxSlot() do
        if not self.items[i] then
            if skip <= 0 then return i end
            skip = skip - 1
        end
    end
    return nil
end

--- 释放槽位
function Bag:freeSlot(slot)
    self.items[slot] = nil
    if adapter.on_slot_changed then adapter.on_slot_changed(self, slot) end
end

--- 设置槽位
function Bag:setSlot(slot, item)
    self.items[slot] = item
    if adapter.on_slot_changed then adapter.on_slot_changed(self, slot) end
    if not item then return end
    if self.player then
        adapter.set_item_owner(item, adapter.get_player_id(self.player))
    end
end

--- 获取槽位
function Bag:getSlot(slot)
    return self.items[slot]
end

--- 预制拾取（返回 actions 队列，由调用方逐一执行）
--- @param item  Item
--- @param num?  integer  拾取数量（默认全部）
--- @return integer       剩余未拾取数量（0=全部拾取完成）
--- @return function[]?   actions 延迟执行队列
--- @return string?       错误信息
function Bag:prePick(item, num)
    num = num or adapter.get_item_count(item)
    -- 已在背包中
    local bag_name = adapter.get_item_location(item)
    if bag_name then return num, nil, cfg.texts.item_already_in_bag end
    -- 归属校验
    local valid, msg = self:canInsertItem(item)
    if not valid then return num, nil, msg end
    -- 优先堆叠
    local leftNum, extra, actions = self:pickAsStack(item, num)
    if leftNum == 0 then return 0, actions end
    if not actions then actions = {} end
    -- 剩余放入空位
    local emptySlot = self:findFirstEmptySlot(extra)
    if not emptySlot then return leftNum, actions, cfg.texts.bag_full end
    actions[#actions + 1] = function()
        self:setSlot(emptySlot, item)
        adapter.set_item_count(item, leftNum)
        adapter.set_item_owner(item, adapter.get_player_id(self.player))
        adapter.set_item_location(item, self.name, emptySlot)
    end
    return 0, actions
end

--- 是否共享背包
function Bag:isShared()
    return self.shared
end

-- ============================================================================
-- 公开 API
-- ============================================================================

--- 初始化模板
--- @param user_adapter BagAdapter
--- @param user_params   table  { configs:table<string,BagConfig>, shared_configs?:table<string,BagConfig>, neutral_friend_pid?:integer, texts?:table }
function M.setup(user_adapter, user_params)
    tpl_validate_adapter(user_adapter)
    adapter = user_adapter
    user_params = user_params or {}
    cfg = {
        configs            = user_params.configs or {},
        shared_configs     = user_params.shared_configs or {},
        neutral_friend_pid = user_params.neutral_friend_pid or 32,
        texts = {
            item_not_yours        = user_params.texts and user_params.texts.item_not_yours        or '物品不属于你',
            item_already_in_bag   = user_params.texts and user_params.texts.item_already_in_bag   or '物品已经在背包中',
            item_not_in_bag       = user_params.texts and user_params.texts.item_not_in_bag       or '物品不在背包中',
            bag_full              = user_params.texts and user_params.texts.bag_full              or '背包已满',
            bag_not_found         = user_params.texts and user_params.texts.bag_not_found         or '背包不存在',
            slot_info_mismatch    = user_params.texts and user_params.texts.slot_info_mismatch    or '目标物品槽位信息不正确',
        },
    }
    shared_bags = {}
    pick_cache  = {}
    cost_cache  = {}
    M_setup_called = true
end

--- 创建背包
--- @param player Player
--- @param name   string  背包名（对应 configs 中的 key）
--- @return table|nil
function M.create(player, name)
    if not M_setup_called then error('c-bag-system: M.setup(adapter, params) not called') end
    return tpl_new_bag(player, name)
end

--- 获取/创建共享背包
--- @return table
function M.get_shared(name)
    if not M_setup_called then error('c-bag-system: M.setup(adapter, params) not called') end
    local bag = shared_bags[name]
    if not bag then
        bag = tpl_new_bag(nil, name)
        shared_bags[name] = bag
    end
    return bag
end

--- 根据物品 bagType 获取优先拾取背包名列表
--- @return string[]
function M.get_pick_names(bagType)
    if not M_setup_called then error('c-bag-system: M.setup(adapter, params) not called') end
    if not pick_cache[bagType] then
        local result = {}
        for name, config in tpl_sort_pairs(cfg.configs) do
            if config.pick and tpl_array_has(config.bagType, bagType) then
                result[#result + 1] = name
            end
        end
        table.sort(result, function(a, b)
            return (cfg.configs[a].pick or 999) < (cfg.configs[b].pick or 999)
        end)
        pick_cache[bagType] = result
    end
    return pick_cache[bagType]
end

--- 根据物品 bagType 获取优先消耗背包名列表
--- @return string[]
function M.get_cost_names(bagType)
    if not M_setup_called then error('c-bag-system: M.setup(adapter, params) not called') end
    if not cost_cache[bagType] then
        local result = {}
        for name, config in tpl_sort_pairs(cfg.configs) do
            if config.cost and tpl_array_has(config.bagType, bagType) then
                result[#result + 1] = name
            end
        end
        table.sort(result, function(a, b)
            return cfg.configs[a].cost < cfg.configs[b].cost
        end)
        cost_cache[bagType] = result
    end
    return cost_cache[bagType]
end

--- 拾取物品到指定背包（便捷封装：Bag:prePick）
--- @param bag  table   由 M.create / M.get_shared 获取
--- @param item Item
--- @param num? integer
--- @return integer   leftNum
--- @return function[]? actions
--- @return string?   error
function M.pre_pick(bag, item, num)
    if not M_setup_called then error('c-bag-system: M.setup(adapter, params) not called') end
    if type(bag) ~= 'table' or type(bag.prePick) ~= 'function' then
        return 0, nil, 'bag must be a Bag instance from M.create() or M.get_shared()'
    end
    return bag:prePick(item, num)
end

return M
