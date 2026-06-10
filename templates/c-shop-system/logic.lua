--- =========================================================================
--- Y3 功能模板 · logic.lua  (C 级 · 三层架构 DataSchema + Adapter + PureLogic)
--- =========================================================================
---
--- @template-id   c-shop-system
--- @grade         C
--- @version       v0.1.0
--- @entry         M.setup(adapter, params)
--- @architecture  three-layer (DataSchema + Adapter + PureLogic)
--- @source        global_script/client/shop/shop.lua
--- @description   单商店货架管理 + 购买流程 + 折扣计算 + 补货
---
--- 接入只需 3 步：
---   1. 按 §1 DataSchema 准备 Cargo / Price 数据格式
---   2. 实现 §2 Adapter 接口的 8 个必填方法（+ 2 个可选）
---   3. M.setup(adapter, params) → M.create(player, name) → shop:buyItem(slot, num)
---
--- 与 c-bag-system 的关系：
---   本模板不依赖 c-bag-system，但若同时使用，可让 adapter.pre_buy_item
---   桥接到 BagSystem.pre_pick(bag, item, num)
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 用户必须按此格式提供数据
-- ============================================================================

--- @class Price  单种货币的价格条目
--- @field id   integer|string   货币 ID（透传给 adapter.cost_currency）
--- @field num  number           价格数量

--- @class Shop.Cargo  单个货架商品
--- @field itemid    integer     商品物品的唯一 ID（透传给 adapter.get_item_by_id）
--- @field price     Price[]     购买价格（允许多种货币）
--- @field charge?   integer     捆绑数量（一次购买的最小单位，默认 1）
--- @field discount? number      固定折扣（0~1，0.8 = 8 折），与购买者 discount 叠加
--- @field cargoId?  integer     表内 ID（业务侧可选追踪用，模板不使用）

--- @class Item  用户自定义，全部走 adapter 访问

--- @class Player  用户自定义，全部走 adapter 访问

-- ============================================================================
-- §2. Adapter 接口 — 用户必须实现以下方法
-- ============================================================================

--- @class ShopAdapter
--- @field get_item_by_id      fun(itemid:integer):Item?                                            必填: 按唯一ID查物品
--- @field get_item_unique_id  fun(item:Item):integer                                               必填: 取物品唯一ID
--- @field get_item_count      fun(item:Item):integer                                               必填: 取物品库存数量
--- @field remove_item         fun(item:Item)                                                       必填: 销毁/移除物品（货架清空时调用）
--- @field clone_item          fun(player:Player, src:Item, on_init?:fun(new:Item)):Item?           必填: 克隆物品（补货用）
--- @field get_player_id       fun(player:Player):integer                                           必填: 取玩家ID
--- @field pre_buy_item        fun(player:Player, item:Item, bag_name:string?, num:integer):(left:integer, actions:function[]?, err:string?)  必填: 预拾取（验证背包空间，返回 actions 队列）
--- @field cost_currency       fun(player:Player, prices:Price[], multiplier:integer):(ok:boolean, err:string?)  必填: 扣除货币（prices 中每项 num 都乘以 multiplier）
--- @field on_cargo_changed    fun(shop:table, slot:integer)?                                       可选: 货架变化回调（UI 刷新用）
--- @field log                 fun(msg:string)?                                                     可选: 日志钩子

-- ============================================================================
-- §3. Pure Logic — 用户不需修改
-- ============================================================================

local adapter = nil
local cfg     = nil
local M_setup_called = false

-- ---------------------------------------------------------------------------
-- 内部工具
-- ---------------------------------------------------------------------------

--- 浮点截断到 N 位小数（四舍五入）
--- @param n         number
--- @param precision integer
--- @return number
local function tpl_trim_float(n, precision)
    local p = 10 ^ precision
    return math.floor(n * p + 0.5) / p
end

--- Adapter 校验
local function tpl_validate_adapter(a)
    assert(type(a) == 'table', 'adapter must be a table')
    local required = {
        'get_item_by_id',
        'get_item_unique_id',
        'get_item_count',
        'remove_item',
        'clone_item',
        'get_player_id',
        'pre_buy_item',
        'cost_currency',
    }
    for _, name in ipairs(required) do
        assert(type(a[name]) == 'function', 'ShopAdapter missing required method: ' .. name)
    end
end

-- ---------------------------------------------------------------------------
-- Shop 类定义
-- ---------------------------------------------------------------------------

local Shop = {}
Shop.__index = Shop

--- 创建商店实例
--- @param player Player
--- @param name   string
local function tpl_new_shop(player, name)
    local shop = setmetatable({}, Shop)
    shop.player      = player
    shop.name        = name
    ---@type Shop.Cargo[]?
    shop.cargos      = nil
    shop.refreshTime = 0
    return shop
end

--- 获取所属玩家
function Shop:getPlayer()
    return self.player
end

--- 批量设置货架（旧货架的物品会被 remove）
--- @param cargos       Shop.Cargo[]
--- @param refreshTime? integer
function Shop:setCargos(cargos, refreshTime)
    if self.cargos then
        for _, cargo in ipairs(self.cargos) do
            local item = adapter.get_item_by_id(cargo.itemid)
            if item then adapter.remove_item(item) end
        end
    end
    if refreshTime then
        self.refreshTime = refreshTime
    end
    self.cargos = cargos
end

--- 取/初始化货架信息表
--- @return Shop.Cargo[]
function Shop:getCargoInfos()
    if self.cargos == nil then
        self.cargos      = {}
        self.refreshTime = 0
    end
    return self.cargos
end

--- 取指定槽位的 cargo
--- @return Shop.Cargo?
function Shop:getCargo(slot)
    return self:getCargoInfos()[slot]
end

--- 标记槽位变化（仅触发回调，不修改 cargos）
function Shop:setCargo(slot, _item)
    if adapter.on_cargo_changed then adapter.on_cargo_changed(self, slot) end
end

--- 清理无效货架条目（对应物品已不存在的 cargo）
function Shop:clearInvalidCargos()
    if not self.cargos then return end
    local valids = {}
    for _, cargo in ipairs(self.cargos) do
        if adapter.get_item_by_id(cargo.itemid) then
            valids[#valids + 1] = cargo
        end
    end
    if #valids == #self.cargos then return end
    self.cargos = valids
end

--- 购买货架物品
--- @param slot     integer
--- @param num?     integer    购买数量（默认全部）
--- @param bagName? string     目标背包名（透传给 adapter.pre_buy_item）
--- @param discount? number    购买者额外折扣（0~1，与 cargo.discount 叠加取低）
--- @return Item?  成功购买的物品（含数量）
--- @return string? 错误信息
function Shop:buyItem(slot, num, bagName, discount)
    local cargos = self:getCargoInfos()
    local cargo  = cargos[slot]
    if not cargo then return nil, cfg.texts.cargo_not_found end
    local item = adapter.get_item_by_id(cargo.itemid)
    if not item then return nil, cfg.texts.item_not_found end
    num = num or adapter.get_item_count(item)
    if adapter.get_item_count(item) < num then
        return nil, cfg.texts.stock_insufficient
    end
    if num < 1 then return nil, cfg.texts.num_must_ge_zero end
    if not math.tointeger(num) then return nil, cfg.texts.num_must_int end

    local cargoNum = adapter.get_item_count(item)
    local leftNum, buyActions, err = adapter.pre_buy_item(
        self.player, item, bagName, num * (cargo.charge or 1)
    )
    if leftNum > 0 then return nil, err or cfg.texts.cannot_buy end
    if not buyActions then return nil, err or cfg.texts.cannot_buy end

    -- 折扣叠加：cargo.discount 与传入 discount 累加（取最低，不可为负）
    local prices = cargo.price
    if cargo.discount or discount then
        local curDiscount = 1
        if cargo.discount then curDiscount = curDiscount - (1 - cargo.discount) end
        if discount         then curDiscount = curDiscount - (1 - discount)         end
        if curDiscount < 0.01 then curDiscount = 0.01 end
        prices = {}
        for i, price in ipairs(cargo.price) do
            prices[i] = {
                id  = price.id,
                num = math.ceil(tpl_trim_float(price.num * curDiscount, cfg.trim_float_precision)),
            }
        end
    end

    -- 扣除货币
    local suc, costErr = adapter.cost_currency(self.player, prices, num)
    if not suc then return nil, costErr or cfg.texts.cost_failed end

    -- 补货：原物品已挪入玩家背包，货架克隆一个新物品占位
    local newItem = adapter.clone_item(self.player, item, function(newItem)
        -- 补货数量由 adapter.clone_item 的 on_init 内部实现自行设置
        -- 模板不代为 set_item_count，请实现方按 cargoNum - num 写入新物品数量
        if adapter.on_cargo_changed then adapter.on_cargo_changed(self, slot) end
    end)
    if newItem then
        cargo.itemid = adapter.get_item_unique_id(newItem)
        self:setCargo(slot, newItem)
    end

    -- 执行真正的购买动作（物品入包）
    for _, act in ipairs(buyActions) do act() end

    return item
end

-- ============================================================================
-- 公开 API
-- ============================================================================

--- 初始化模板
--- @param user_adapter ShopAdapter
--- @param user_params  table?  { trim_float_precision?:integer, texts?:table }
function M.setup(user_adapter, user_params)
    tpl_validate_adapter(user_adapter)
    adapter = user_adapter
    user_params = user_params or {}
    cfg = {
        trim_float_precision = user_params.trim_float_precision or 5,
        texts = {
            cargo_not_found    = user_params.texts and user_params.texts.cargo_not_found    or '商品不存在',
            item_not_found     = user_params.texts and user_params.texts.item_not_found     or '物品不存在',
            stock_insufficient = user_params.texts and user_params.texts.stock_insufficient or '库存不足',
            num_must_ge_zero   = user_params.texts and user_params.texts.num_must_ge_zero   or '购买数量必须大于等于0',
            num_must_int       = user_params.texts and user_params.texts.num_must_int       or '购买数量必须是整数',
            cannot_buy         = user_params.texts and user_params.texts.cannot_buy         or '无法购买',
            cost_failed        = user_params.texts and user_params.texts.cost_failed        or '扣除货币失败',
        },
    }
    M_setup_called = true
end

--- 创建商店实例
--- @param player Player
--- @param name   string
--- @return table  Shop 实例
function M.create(player, name)
    if not M_setup_called then error('c-shop-system: M.setup(adapter, params) not called') end
    return tpl_new_shop(player, name)
end

return M
