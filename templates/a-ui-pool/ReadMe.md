# a-ui-pool — 通用 UI/组件对象池

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 通用 UI/组件对象池 |
| 路径 | `.codex/templates/a-ui-pool/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `pool`, `reuse`, `ui-object-pool`, `performance` |
| 适用场景 | 滚动列表项复用、浮动文本池、动态卡牌槽位、Boss 血条/小怪头标池——任何“频繁创建/销毁同类组件”的场景 |
| 依赖 | `New(Class)(args)` 构造器，或等价的注入式实例化函数 |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → UIPool` |
| 参数 | `params.cmp_class`、`params.layer_node`、`params.New` |
| 集成说明 | `local pool = UIPool.setup({ cmp_class = CardItem, layer_node = scrollBox, New = New }); local card = pool:popSlot(); pool:pushSlot(card)` |

---

## 功能概述

`a-ui-pool` 是一个轻量对象池模块，用于复用同类 UI/组件对象，减少频繁创建和销毁带来的性能开销。

它本身**不负责创建可见 UI 面板**，也不直接操作 UI 显示状态；它只负责：

- 池为空时创建一个新组件；
- 池不为空时复用已回收组件；
- 取出组件时调用可选的 `onPop()`；
- 回收组件时调用可选的 `onPush()`。

组件是否显示、隐藏、刷新数据、解绑事件，应由组件自身在 `onPop()` / `onPush()` 中处理。

---

## 适用场景

适合所有“同类对象数量多、生命周期短、反复出现”的场景，例如：

- 背包格子、商店商品项、排行榜条目；
- 伤害飘字、治疗飘字、金币获得提示；
- 技能卡、装备卡、抽卡结果卡；
- 小怪血条、Boss 血条、单位头顶标记；
- Toast、奖励提示、战斗事件提示。

---

## 参数契约

```lua
local pool = UIPool.setup({
    cmp_class = CardItem,
    layer_node = scrollBox,
    New = New,
})
```

| 参数 | 必填 | 说明 |
|------|------|------|
| `cmp_class` | 是 | 组件 Class 表，例如 `CardItem` |
| `layer_node` | 是 | 传给组件构造器的父节点/挂载节点 |
| `New` | 是 | 实例化函数，调用形式必须兼容 `New(cmp_class)(layer_node)` |

### 构造约定

对象池在需要创建新组件时会执行：

```lua
local slot = New(cmp_class)(layer_node)
```

因此传入的 `New` 必须返回一个可继续调用的构造函数。

---

## 返回实例 API

| 方法 | 说明 |
|------|------|
| `pool:popSlot()` | 从池中取出一个组件；池为空则新建 |
| `pool:pushSlot(slot)` | 将组件回收到池中，等待下次复用 |

---

## 生命周期钩子

组件可以选择实现以下方法：

```lua
function CardItem:onPop()
    -- 取出时调用：通常用于显示、重置状态、绑定数据
end

function CardItem:onPush()
    -- 回收时调用：通常用于隐藏、清理数据、解绑引用
end
```

这两个钩子是**可选的**：

- 如果组件实现了 `onPop()`，`popSlot()` 会自动调用；
- 如果组件实现了 `onPush()`，`pushSlot()` 会自动调用；
- 如果组件没有实现这些方法，对象池仍会正常工作。

---

## 复用顺序：LIFO

当前对象池使用 **LIFO** 策略：

> Last In, First Out —— 后放入池的对象，会先被取出。

示例：

```lua
pool:pushSlot(slotA)
pool:pushSlot(slotB)

local first = pool:popSlot()  -- slotB
local second = pool:popSlot() -- slotA
```

这适合多数对象池场景，因为最近回收的对象通常更容易立即复用，且实现简单。

如果业务需要“先回收、先复用”的队列语义，则应明确改造为 FIFO，并同步调整使用约定。

---

## 使用示例

```lua
local UIPool = include 'templates.a_ui_pool.logic'

local CardItem = include 'ui.card_item'

local card_pool = UIPool.setup({
    cmp_class = CardItem,
    layer_node = scrollBox,
    New = New,
})

local card = card_pool:popSlot()
card:setData(cardData)

-- 使用完毕后回收
card_pool:pushSlot(card)
```

组件自身可以负责显示/隐藏：

```lua
function CardItem:onPop()
    self.root:set_visible(true)
end

function CardItem:onPush()
    self.root:set_visible(false)
    self.data = nil
end
```

---

## 注意事项

- 不要把对象池理解为 UI 生成器；它只负责复用对象。
- 被回收的组件应在 `onPush()` 中清理状态，避免残留旧数据。
- 取出的组件应在 `onPop()` 或外部调用中重新绑定数据。
- 当前模块不处理 `nil` 入池或重复入池策略；调用方应保证 `pushSlot(slot)` 传入的是有效且未重复回收的对象。
- 当前 LIFO 顺序属于模块行为约定；如果未来改变复用顺序，应视为行为变更。
