# 多背包槽位管理系统

> **等级**：C
> 提供 N 个具名背包的槽位管理、物品堆叠、移动/交换、拾取预检流程。纯 Lua 模板，不含 UI。

## 模板登记

### c-bag-system

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 多背包槽位管理系统 |
| 路径 | `.codemaker/templates/c-bag-system/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `bag`, `inventory`, `slot`, `item-stack`, `pickup`, `item-move` |
| 适用场景 | 任何需要多背包 + 槽位 + 堆叠 + 移动/交换 + 拾取流程的项目（RPG / Roguelike / 塔防 / 生存） |
| 依赖 | 无（仅 y3 引擎 API + Lua 标准库） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params)` |
| 参数 | 13 个 adapter 方法（见下方「Adapter 接口」）+ `params.configs`（背包配置表）+ `params.shared_configs`（共享背包配置表）+ `params.neutral_friend_pid?` + `params.texts?`（文案覆盖） |
| 测试状态 | `tested, 2026-06-01, 3/3 structural in agentmap (execute_lua, mock adapter). Full integration needs real game objects` |
| 集成说明 | 需先实现 Adapter 接口（见下方 §Adapter 接口），然后 `M.setup(adapter, params)` → `M.create(player, name)` 创建背包 → `bag:prePick(item, num)` 拾取 / `bag:move(item, targetBag, slot?)` 移动 |

> 注意：本模板为纯 Lua 模板，不含 UI。

---

## 数据契约 (DataSchema)

### BagConfig

```lua
--- @class BagConfig  单个背包配置
--- @field maxSlot   integer       初始最大槽位数 (≥1)
--- @field bagType   integer[]     接受的物品类型ID（拾取/消耗路由用）
--- @field pick?     integer       拾取优先级（数字越小越优先，缺省999最低）
--- @field cost?     integer       消耗优先级（数字越小越优先，缺省则不可从此背包消耗）
--- @field expand?   string        扩展货币 key，该货币持有量加到 maxSlot；无则不扩展
```

---

## Adapter 接口

| 方法 | 签名 | 必填 | 说明 |
|------|------|------|------|
| `get_item_config_id` | `fun(item):integer` | ✅ | 取物品配置 ID |
| `get_item_count` | `fun(item):integer` | ✅ | 取物品数量 |
| `set_item_count` | `fun(item, n)` | ✅ | 设置数量（0=销毁） |
| `get_item_owner` | `fun(item):integer` | ✅ | 取物品所属玩家 ID |
| `set_item_owner` | `fun(item, owner_id)` | ✅ | 设置所属 |
| `get_item_location` | `fun(item):string?, integer?` | ✅ | 取物品所在背包名 + 槽位 |
| `set_item_location` | `fun(item, bag_name, slot)` | ✅ | 设置位置 |
| `try_stack_to_item` | `fun(src, dst):boolean, boolean` | ✅ | 堆叠两物品 → totalStacked, partialStacked |
| `get_stack_limit` | `fun(config_id):integer` | ✅ | 堆叠上限（≤1=不可堆） |
| `is_transferable` | `fun(config_id):boolean` | ✅ | 是否可跨玩家转让 |
| `create_item` | `fun(player_id, config_id, on_create?):item?` | ✅ | 创建物品（on_create 回调中设置初始值） |
| `get_player_id` | `fun(player):integer` | ✅ | 取玩家 ID |
| `get_player_currency` | `fun(player, currency_key):integer` | ✅ | 取货币数量 |
| `is_neutral_friend` | `fun(player_id):boolean` | — | 是否中立友好（默认 false） |
| `on_slot_changed` | `fun(bag, slot)` | — | 槽位变化回调（用于 UI 刷新） |
| `on_item_moved` | `fun(item, from_bag)` | — | 物品移动回调（用于特效/音效/日志） |
| `log` | `fun(msg)` | — | 可选日志钩子 |

---

## 测试用 MockAdapter

```lua
local MockAdapter = {}
local _items = {}
local _next_id = 0

function MockAdapter.get_item_config_id(item) return item._cid end
function MockAdapter.get_item_count(item) return item._count end
function MockAdapter.set_item_count(item, n) item._count = n end
function MockAdapter.get_item_owner(item) return item._owner end
function MockAdapter.set_item_owner(item, oid) item._owner = oid end
function MockAdapter.get_item_location(item) return item._bag, item._slot end
function MockAdapter.set_item_location(item, bag, slot) item._bag = bag; item._slot = slot end
function MockAdapter.try_stack_to_item(src, dst)
    if src._cid ~= dst._cid then return false, false end
    local limit = MockAdapter.get_stack_limit(src._cid)
    local total = dst._count + src._count
    if total <= limit then dst._count = total; src._count = 0; return true, false end
    dst._count = limit; src._count = total - limit; return false, true
end
function MockAdapter.get_stack_limit(cid) return cid == 1 and 99 or 1 end
function MockAdapter.is_transferable(cid) return true end
function MockAdapter.create_item(pid, cid, on_create)
    _next_id = _next_id + 1
    local item = { _cid = cid, _count = 1, _owner = pid, _bag = nil, _slot = nil, _id = _next_id }
    if on_create then on_create(item) end
    _items[_next_id] = item
    return item
end
function MockAdapter.get_player_id(p) return p._id end
function MockAdapter.get_player_currency(p, key) return 0 end
function MockAdapter.is_neutral_friend(pid) return pid == 32 end
function MockAdapter.on_slot_changed(bag, slot) end
function MockAdapter.on_item_moved(item, from_bag) end
```

---

## 参数详述

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `adapter` | `BagAdapter` | ✅ | — | 13 个必填方法的接口对象 |
| `params.configs` | `table<string,BagConfig>` | ✅ | — | 私有背包配置（key 即背包名） |
| `params.shared_configs` | `table<string,BagConfig>` | — | `{}` | 共享背包配置 |
| `params.neutral_friend_pid` | `integer` | — | `32` | 中立友好玩家 ID |
| `params.texts.item_not_yours` | `string` | — | `'物品不属于你'` | 归属错误文案 |
| `params.texts.item_already_in_bag` | `string` | — | `'物品已经在背包中'` | 重复拾取文案 |
| `params.texts.item_not_in_bag` | `string` | — | `'物品不在背包中'` | 源槽位空文案 |
| `params.texts.bag_full` | `string` | — | `'背包已满'` | 满包文案 |
| `params.texts.bag_not_found` | `string` | — | `'背包不存在'` | 找不到背包文案 |
| `params.texts.slot_info_mismatch` | `string` | — | `'目标物品槽位信息不正确'` | 槽位数据不一致文案 |

---

## 接入步骤

```lua
-- 1. require 模板
local BagSystem = include 'c-bag-system'

-- 2. 准备数据 schema（物品用 adapter 映射，只需背包配置）
local configs = {
    ['物品栏'] = { maxSlot = 6, bagType = {1}, pick = 1, cost = 1, expand = 'bag_expand_coin' },
    ['仓库']   = { maxSlot = 0, bagType = {1}, pick = 2, cost = 2 },
}

-- 3. 实现 Adapter（参见上方「测试用 MockAdapter」）
local MyAdapter = {
    -- ... 实现 13 个必填方法，对接你的 Item/Player 数据 ...
}
-- 把 MockAdapter 代码抄过来，替换 _cid/_count/_owner/_bag/_slot 为你的实际字段名

-- 4. setup
local M = BagSystem.setup(MyAdapter, { configs = configs })

-- 5. 使用
local player_obj = { _id = 1 }  -- 你的实际 Player 对象
local bag = M.create(player_obj, '物品栏')

-- 拾取
local item = MyAdapter.create_item(1, 1001) -- 创建物品
local left, actions, err = M.pre_pick(bag, item, 5)
if err then
    print('拾取失败:', err)
else
    for _, act in ipairs(actions) do act() end  -- 执行延迟操作
    print('拾取成功, 剩余:', left)
end

-- 移动/交换
local bag2 = M.create(player_obj, '仓库')
bag:move(item, bag2, 1)  -- 移到仓库的 1 号槽位

-- 共享背包
local shared = M.get_shared('共享仓库')

-- 路由（根据物品类型获取优先背包名列表）
local pick_names = M.get_pick_names(1)  -- {"物品栏", "仓库"}
```

---

## 已知限制

1. **`organize()` 整理功能**为空实现，未移植（源工程未实现）
2. **共享背包的玩家归属**：`M.get_shared(name)` 创建的背包 `player` 字段为 `nil`，setSlot 不自动设置 owner。如需归属，请通过 adapter 的 `on_slot_changed` 回调接管
3. **多玩家并发安全**：模板不负责锁/事务，由调用方保证
4. **物品 UI 渲染**：`on_slot_changed` 仅提供回调钩子，UI 刷新逻辑由复用方在回调中实现

---

## UI 集成经验（2026-05-28 验证）

本次在 Y3 引擎中完成了完整的 GridView + prefab 背包面板集成，记录关键踩坑：

### 1. 持久状态而非演示脚本

```lua
-- ❌ 错误：每次 UI 操作都 reset() + demo() 重跑
Demo.reset(); Demo.demo()

-- ✅ 正确：init() 一次，暴露增量 API
Demo.init()          -- 仅调一次
Demo.buy(slot, num)  -- UI 直接调
Demo.move_item(from, to)
Demo.get_bag_state()
```

### 2. prefab get_child 无需 root 前缀

```lua
-- ❌ 错误（找不到节点，返回 nil）
local icon = cell:get_child('root.item_icon')

-- ✅ 正确（prefab:get_child() 已返回根节点，直接用子节点名）
local icon = cell:get_child('item_icon')
```

> 仅当 prefab 内部存在额外的 `root` 包装层时才需要前缀。判断方法：查看 `ui_tree/*_Tree.json`。

### 3. local function 前向声明

`on_cell_click` 内部调用 `refresh_bag_grid`，而后者定义在前者之后，Lua 闭包无法访问：

```lua
-- ❌ 报错：attempt to call a nil value (global 'refresh_bag_grid')
local function on_cell_click(...)
    refresh_bag_grid(lp)  -- 此时 refresh_bag_grid 尚未定义
end
local function refresh_bag_grid(lp) ... end

-- ✅ 前向声明
local refresh_bag_grid          -- 前向声明
local function on_cell_click(...)
    refresh_bag_grid(lp)        -- OK
end
refresh_bag_grid = function(lp) ... end  -- 赋值实现
```

### 4. Y3 无原生 UI 拖拽事件

Y3 只有装备栏专用的 `界面-装备拖拽` 事件，通用控件无拖拽。建议用**两步点击**模拟移动：
- 第一次点击有物品格：选中并高亮（`set_image_color_hex('#FFD700', 200)`）
- 第二次点击目标格：调用 `M.move_item(from, to)` 完成移动

### 5. GridView prefab 关联方式

JSON 中 GridView 节点需手动设置 `prefab_sub_key` 为 prefab 的 key：

```json
"name": "item_grid",
"type": 25,
"prefab_sub_key": "07808027-0958-4f3c-8104-80b03facf2b7"
```

prefab key 来自 `maps/EntryMap/ui/prefab/<name>.json` 末尾的 `"key"` 字段。

---

## 源工程溯源

- 源模块：`global_script/client/bag/bag.lua` + `global_script/client/bag/const.lua`
- 导出日期：2026-05-28
- 导出工具：`y3-template-export`
- 验证日期：2026-05-28（含 UI 集成）
