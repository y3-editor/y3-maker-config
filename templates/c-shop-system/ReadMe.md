# 单商店购买流程模板

> **等级**：C
> 单商店货架管理 + 购买流程 + 折扣计算 + 自动补货。纯 Lua 模板，不含 UI。

## 模板登记

### c-shop-system

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 单商店购买流程模板 |
| 路径 | `.codemaker/templates/c-shop-system/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `shop`, `purchase`, `currency`, `discount`, `restock`, `cargo` |
| 适用场景 | 任何需要「N 个商店 × M 个货架槽位 × 多货币定价 × 折扣购买」的项目（RPG / Roguelike / MOBA 商店） |
| 依赖 | 无；可选与 `c-bag-system` 组合使用（pre_buy_item 桥接到 BagSystem.pre_pick） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params)` |
| 参数 | 8 个必填 adapter 方法 + 2 个可选方法 + `params.trim_float_precision?` + `params.texts?`（7 条文案） |
| 测试状态 | `tested, 2026-06-01, 3/3 structural in agentmap (execute_lua, mock adapter). Full integration needs real game objects` |
| 集成说明 | 需先实现 Adapter 接口（见模板 ReadMe §Adapter 接口），然后 `M.setup(adapter, params)` → `M.create(player, name)` → `shop:setCargos(cargos)` → `shop:buyItem(slot, num, bag_name, discount?)` |

> 注意：本模板为纯 Lua 模板，不含 UI。

### ⚠️ 回归靶场坑

| 坑 | 现象 | 修复 |
|----|------|------|
| `cargo.price` 需 `{{id='currency', num=100}}` 数组格式 | `attempt to index a number value (local 'price')` | 改为 `price = {{id='gold', num=100}}` |
| `cargo.itemid` 字段名 | `attempt to index a number value (local 'item')` | setCargos 用 `itemid` 小写（非 `itemId`） |
| `cost_currency(pid, prices, buyNum)` 三参数 | adapter 签名不匹配 | 非 `cost_currency(pid, key, amount)` |

---

## 数据契约 (DataSchema)

### Price

```lua
--- @class Price  单种货币的价格条目
--- @field id   integer|string   货币 ID（透传给 adapter.cost_currency）
--- @field num  number           价格数量
```

### Shop.Cargo

```lua
--- @class Shop.Cargo  单个货架商品
--- @field itemid    integer     商品物品的唯一 ID
--- @field price     Price[]     购买价格（允许多种货币）
--- @field charge?   integer     捆绑数量（一次购买的最小单位，默认 1）
--- @field discount? number      固定折扣（0~1，0.8 = 8 折）
--- @field cargoId?  integer     表内 ID（业务侧追踪用，模板不使用）
```

---

## Adapter 接口

| 方法 | 签名 | 必填 | 说明 |
|------|------|------|------|
| `get_item_by_id` | `fun(itemid):item?` | ✅ | 按唯一 ID 查物品对象 |
| `get_item_unique_id` | `fun(item):integer` | ✅ | 取物品唯一 ID（补货后回写 cargo.itemid） |
| `get_item_count` | `fun(item):integer` | ✅ | 取物品库存数量 |
| `remove_item` | `fun(item)` | ✅ | 销毁/移除物品（setCargos 清空旧货架时调用） |
| `clone_item` | `fun(player, src, on_init?):item?` | ✅ | 克隆物品用于补货 |
| `get_player_id` | `fun(player):integer` | ✅ | 取玩家 ID |
| `pre_buy_item` | `fun(player, item, bag_name?, num):left, actions, err` | ✅ | 预拾取：验证背包空间，返回 actions 队列 |
| `cost_currency` | `fun(player, prices, multiplier):ok, err` | ✅ | 扣除货币（prices 每项 num 乘以 multiplier） |
| `on_cargo_changed` | `fun(shop, slot)` | — | 货架变化回调（UI 刷新用） |
| `log` | `fun(msg)` | — | 日志钩子 |

---

## 测试用 MockAdapter

```lua
local MockShop = {}
local _items, _next_id = {}, 0
local _player_currency = { [1] = { gold = 1000 } }

function MockShop.get_item_by_id(id) return _items[id] end
function MockShop.get_item_unique_id(it) return it._id end
function MockShop.get_item_count(it) return it._count end
function MockShop.remove_item(it) _items[it._id] = nil end
function MockShop.clone_item(player, src, on_init)
    _next_id = _next_id + 1
    local new = { _id = _next_id, _cid = src._cid, _count = src._count, _owner = player._id }
    _items[_next_id] = new
    if on_init then on_init(new) end
    return new
end
function MockShop.get_player_id(p) return p._id end
function MockShop.pre_buy_item(player, item, bag_name, num)
    -- 假设背包永远有空间，直接返回 actions
    return 0, { function() item._count = item._count - num end }, nil
end
function MockShop.cost_currency(player, prices, mult)
    local pc = _player_currency[player._id] or {}
    for _, p in ipairs(prices) do
        local need = p.num * mult
        if (pc[p.id] or 0) < need then return false, '货币不足:' .. p.id end
    end
    for _, p in ipairs(prices) do pc[p.id] = pc[p.id] - p.num * mult end
    return true
end
function MockShop.on_cargo_changed(shop, slot) end

-- 测试用辅助
function MockShop.create_test_item(cid, count)
    _next_id = _next_id + 1
    local it = { _id = _next_id, _cid = cid, _count = count }
    _items[_next_id] = it
    return it
end
```

---

## 参数详述

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `adapter` | `ShopAdapter` | ✅ | — | 8 必填 + 2 可选方法 |
| `params.trim_float_precision` | `integer` | — | `5` | 折扣计算时浮点截断小数位数 |
| `params.texts.*` | `string` | — | 中文默认值 | 7 条错误文案覆盖 |

---

## 接入步骤

```lua
-- 1. require 模板
local ShopSystem = include 'c-shop-system'

-- 2. 实现 Adapter（参见上方「测试用 MockAdapter」）
local MyShopAdapter = {
    -- ... 实现 8 个必填方法 ...
}

-- 3. setup
ShopSystem.setup(MyShopAdapter, {
    trim_float_precision = 5,
})

-- 4. 创建商店
local player = { _id = 1 }
local shop   = ShopSystem.create(player, '武器店')

-- 5. 上架商品
local sword_item = MyShopAdapter.create_test_item(101, 1)  -- 1 把剑
local potion_item = MyShopAdapter.create_test_item(201, 10) -- 10 瓶药

shop:setCargos({
    {
        itemid = MyShopAdapter.get_item_unique_id(sword_item),
        price  = { { id = 'gold', num = 100 } },
        charge = 1,
    },
    {
        itemid   = MyShopAdapter.get_item_unique_id(potion_item),
        price    = { { id = 'gold', num = 10 } },
        charge   = 1,
        discount = 0.8,  -- 8 折
    },
})

-- 6. 玩家购买
local bought, err = shop:buyItem(2, 3, '物品栏', 0.9)  -- 购买槽位2，3瓶药，玩家有9折
if err then
    print('购买失败:', err)
else
    print('购买成功:', bought)
end

-- 7. 清理无效条目（物品被销毁后）
shop:clearInvalidCargos()
```

---

## 与 `c-bag-system` 的组合使用

模板本身**不依赖** `c-bag-system`，但实战中两者常需协同：

```lua
local BagSystem  = include 'c-bag-system'
local ShopSystem = include 'c-shop-system'

-- 让 ShopAdapter.pre_buy_item 桥接到 BagSystem
function MyShopAdapter.pre_buy_item(player, item, bag_name, num)
    local bag = BagSystem.create(player, bag_name)  -- 或缓存复用
    return BagSystem.pre_pick(bag, item, num)
end
```

两套 Adapter 可共享：`get_item_count` / `get_player_id` / `clone_item`（部分项目）。

---

## 已知限制

1. **商品刷新逻辑**未包含：模板只持有 `refreshTime` 字段，是否定时刷新由复用方决定
2. **库存补货数量**：`buyItem` 中 `clone_item` 的 `on_init` 回调仅做槽位变化通知，**补货物品数量需由 adapter.clone_item 实现内自行处理**（建议在实现中按 src 的剩余数量克隆）
3. **多人并发安全**：未加锁，由调用方保证
4. **折扣下界**：折扣叠加后若 < 0.01 自动钳制（不会出现免费购买）

---

## UI 集成经验（2026-05-28 验证）

本次在 Y3 引擎中完成了 ShopPanel 商店面板集成，记录关键踩坑：

### 1. ShopAdapter.pre_buy_item 必须复用同一背包实例

```lua
-- ❌ 错误：每次调用都创建新背包，物品入不了玩家已有的背包
function ShopAdapter.pre_buy_item(player, item, bag_name, num)
    local bag = BagSystem.create(player, bag_name)  -- 每次新建！
    return BagSystem.pre_pick(bag, item, num)
end

-- ✅ 正确：用注册表复用已有背包实例
local _bag_registry = {}
local function get_or_create_bag(player, bag_name)
    local pid = player._id
    _bag_registry[pid] = _bag_registry[pid] or {}
    _bag_registry[pid][bag_name] = _bag_registry[pid][bag_name]
        or BagSystem.create(player, bag_name)
    return _bag_registry[pid][bag_name]
end

function ShopAdapter.pre_buy_item(player, item, bag_name, num)
    local bag = get_or_create_bag(player, bag_name)
    return BagSystem.pre_pick(bag, item, num)
end
```

### 2. clone_item 补货数量需在实现中自行设置

`buyItem` 内的 `clone_item on_init` 回调不会自动 `set_item_count`，需要在 `adapter.clone_item` 实现中处理剩余库存：

```lua
function ShopAdapter.clone_item(player, src, on_init)
    -- src._count 是购买后的剩余库存
    local new_item = create_item(player._id, src._key, src._count > 0 and src._count or 1)
    if on_init then on_init(new_item) end
    return new_item
end
```

### 3. 持久状态设计

商店状态（货架）在游戏中应只 `setup + create` 一次，UI 购买直接调 `shop:buyItem()`，不要每次 reset：

```lua
-- 初始化一次
ShopSystem.setup(adapter, params)
local shop = ShopSystem.create(player, '武器店')
shop:setCargos(cargos)

-- UI 购买按钮直接调
local item, err = shop:buyItem(slot, num, bag_name, discount)
```

### 4. 折后价显示建议

`math.ceil(price.num * curDiscount)` 已做四舍五入，`trim_float_precision=0` 可强制取整，避免出现 9.9 这类浮点数显示。

---

## 源工程溯源

- 源模块：`global_script/client/shop/shop.lua`
- 导出日期：2026-05-28
- 导出工具：`y3-template-export`
- 验证日期：2026-05-28（含 UI 集成）
