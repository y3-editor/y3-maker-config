# 通用属性系统 (Attribute System)

> **等级**：B
> 通用属性系统：定义属性 + 公式编译 + 依赖联动 + 边界约束 + 变化事件。
> 适用于任何 RPG / 数值类游戏的角色属性、装备加成、Buff 影响场景。

## 模板登记

### b-attribute-system

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | 通用属性系统 |
| 路径 | `.codemaker/templates/b-attribute-system/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `attribute`, `stat-system`, `formula-dsl`, `reactive`, `rpg` |
| 适用场景 | 任何 RPG / 数值类游戏的角色属性、装备/Buff 加成、套装效果。支持复杂公式合成（基础值 × (1 + 百分比)）、属性间依赖联动、边界约束、变化监听 |
| 依赖 | —（仅 Lua 标准库，需运行时支持 `load`） |
| UI 文件 | —（纯 Lua 模板） |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(opts?) → Attribute.System` |
| 参数 | `opts.default_formula?`, `opts.default_base_symbol?` |
| 测试状态 | `tested, 2026-05-27, 10/10 passed. fix: keepRate nil guard` |
| 集成说明 | 1. `local Attr = require '<path>.logic'` 2. `local sys = Attr.setup()` 3. `sys:define(name, simple, min, max)` 定义属性 4. `sys:instance()` 创建实例 5. `instance:set/add/get/event` |

---

## 核心概念

### 简易属性 (simple)
直接存储数值，调用 `set/add` 立即生效。例：力量、敏捷。

### 复杂属性 (complex)
公式合成。系统自动定义 `{base_symbol}` 和 `{%}` 等中间属性，由公式合成最终值。
- 默认公式：`{!} * (1 + 0.01 * {%})` —— 基础值 × (1 + 百分比/100)
- 例：定义"攻击力"为 complex，则自动产生 "攻击力!" 和 "攻击力%" 两个中间属性

### 公式 DSL
- `{!}` — 基础符号（默认是 `!`）
- `{%}` — 百分比加成符号
- `{属性名}` — 引用其他属性当前值
- 例：`'{力量} + {敏捷} * 0.5 + {!}'` — 攻击力 = 力量 + 敏捷×0.5 + 基础攻击

### 依赖联动
B 的公式引用 A → A 改变时 B 自动重算。`compile()` 时自动分析依赖图。

### 变化事件
仅监听的属性才进入脏列表。每帧调用 `system:updateEvent()` 批量分发。

### 边界约束
- `min/max` 可为数字（固定边界）或字符串（另一属性名）
- `keepRate=true`：边界为属性引用时，保持当前值与边界的比例（适合"血量随上限变化"场景）

---

## 参数详述

### M.setup(opts)

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `opts.default_formula` | string | ❌ | `'{!} * (1 + 0.01 * {%})'` | 默认公式（用于 simple=false 的属性） |
| `opts.default_base_symbol` | string | ❌ | `'!'` | 基础符号 |

返回 `Attribute.System` 对象。

### system:define(name, simple, min, max)

| 参数 | 类型 | 说明 |
|------|------|------|
| `name` | string | 属性名 |
| `simple` | boolean? | 是否简易属性。`true`=直接存储，`false`=公式合成 |
| `min` | number\|string? | 下限（数字 或 另一属性名） |
| `max` | number\|string? | 上限（数字 或 另一属性名） |

返回 `Attribute.Define` 对象，可链式调用：
- `:setFormula(formula)` 自定义公式（仅 complex）
- `:setBaseSymbol(sym)` 自定义基础符号
- `:setMin(min, keepRate)` / `:setMax(max, keepRate)` 重设边界
- `:recordTouch()` 启用修改前快照（与 `system:getTouched()` 配合）

### system:compile()
编译所有定义。**调用后不可再 define 新属性**。首次 `instance()` 时自动调用。

### system:instance(customData?) → Attribute.Instance
创建实例。

### system:updateEvent()
批量分发所有 dirty 实例的变化回调。**通常每帧调用一次**。

### system:enableUnknown()
启用未知属性容错。`set/add/get` 未定义属性时不报错，按裸缓存处理。

### instance:set(name, value) / instance:add(name, value)
设置 / 累加属性值。

### instance:get(name) → number
读取当前值（complex 属性会带缓存，依赖变化时自动失效）。

### instance:getMin(name) / getMax(name) → number
读取当前边界（边界为属性引用时实时计算）。

### instance:event(name, callback) → dispose
注册变化监听。返回 `dispose()` 函数用于注销。

> ⚠️ 事件不立即触发，需要在 `system:updateEvent()` 时统一分发，避免连锁修改时频繁回调。

---

## 使用示例

### 实战版：基于真实 RPG 项目属性体系

以下示例展示一个"三围（力量/敏捷/智力）+ 生命 + 攻击系 + 增伤系"的属性架构。公式采用三层加成体系（{%A} 基础加成、{%B} 最终加成、{%C} 额外），这是 DM42 工程实际使用的模式。

```lua
local Attr = require 'b-attribute-system.logic'

-- 1. 创建系统（自定义三层加成公式）
local sys = Attr.setup({
    default_formula =
        '({!} * ((1 + 0.01 * {%A}) * (1 + 0.01 * {%B})) + {%C} * (1 + 0.01 * {%B}))',
})
-- 公式解读：最终值 = (基础值 × (1+A%) × (1+B%)) + 额外值 × (1+B%)
-- {%A} 是“基础加成”层（词缀类），{%B} 是“最终加成”层（套装/光环），{%C} 是“额外”层

-- 2. 定义属性
sys:define('力量', true)       -- simple，直接存储
sys:define('敏捷', true)
sys:define('智力', true)

sys:define('最大生命', false, 0)               -- complex，默认公式，下限 0
sys:define('生命', true, 0, '最大生命')          -- simple，上限绑定最大生命
    :setMax('最大生命', true)                   -- keepRate: 比例锁定

sys:define('攻击', false, 0)                   -- complex，默认公式，下限 0

sys:define('物理固伤', false, 0)                -- complex，自定义公式引用力量
    :setFormula(
        '({!} * ((1 + 0.01 * {%A}) * (1 + 0.01 * {%B})) + {%C} * (1 + 0.01 * {%B}) + {力量} * 0.5)')
-- 物理固伤 = 标准合成 + 力量 × 0.5

sys:define('护甲', false, 0)                   -- complex，默认公式

sys:define('伤害减免', false, 0, '护甲')         -- complex，上限绑定护甲
    :setMax('护甲')
    :setFormula('{!} * 0.01 + {护甲} * 0.004')  -- 公式引用另一个 complex 属性

-- 简易属性（增伤系、特殊标签，不需要公式合成）
sys:define('物理伤害加成', true)
sys:define('魔法伤害加成', true)
sys:define('暴击率', true)
sys:define('暴击伤害', true)
sys:define('冷却缩减', true)
sys:define('攻击速度', true)
sys:define('移动速度', true)

-- 3. Y3 引擎同步标记（需要把值同步给 y3 物编属性的，标记 recordTouch）
for _, name in ipairs {
    '最大生命', '生命',
    '攻击速度', '移动速度', '冷却缩减',
    '攻击范围',
} do
    sys.defines[name]:recordTouch()
end

-- 4. 编译 + 创建实例
sys:compile()                  -- 也可省略，首次 instance() 自动
local hero = sys:instance()

-- 5. 操作属性
hero:set('力量', 20)
hero:set('敏捷', 15)
hero:set('智力', 12)

hero:set('最大生命!', 500)     -- 基础最大生命
hero:add('最大生命%A', 30)     -- +30% 基础加成
hero:add('最大生命%B', 10)     -- +10% 最终加成
hero:add('最大生命%C', 80)     -- +80 额外生命
-- 最终最大生命 = (500 * 1.3 * 1.1) + 80*1.1 = 715 + 88 = 803

hero:set('生命', 803)          -- 满血

hero:set('攻击!', 60)
hero:add('攻击%A', 20)
hero:set('物理固伤!', 40)
hero:add('物理固伤%A', 15)

print(hero:get('最大生命'))    -- 803
print(hero:get('攻击'))        -- (60 * 1.2 * 1.0) + 0*1.0 = 72
print(hero:get('物理固伤'))    -- (40 * 1.15 * 1.0) + 0*1.0 + 20*0.5 = 56

-- 6. 护甲联动伤害减免
hero:set('护甲!', 100)
hero:add('护甲%A', 50)
print(hero:get('护甲'))        -- 150
print(hero:get('伤害减免'))    -- 0*0.01 + 150*0.004 = 0.6 → 0? wait...
-- 伤害减免是 complex，其! = 0（未设置），所以 = 0 + 150*0.004 = 0.6

-- 7. 力量改变 → 物理固伤自动重算
local disp = hero:event('物理固伤', function(_, newVal, oldVal)
    print(string.format('物理固伤 %d → %d', oldVal, newVal))
end)

hero:add('力量', 10)           -- 力量 20→30
sys:updateEvent()              -- 物理固伤 56 → (40*1.15 + 30*0.5) = 61

-- 8. 血量上限翻倍 → keepRate 自动保留比例
hero:set('生命', 400)          -- 当前 400 / 803 ≈ 50%
hero:set('最大生命!', 1000)    -- 翻倍基础最大生命
print(hero:get('最大生命'))    -- 变大
print(hero:get('生命'))        -- 自动按比例放大

-- 9. recordTouch：每帧批量获取修改过的属性（用于同步 Y3 引擎）
-- 在你的帧循环中：
-- local touched = sys:getTouched()  -- { [hero] = { 生命=400, 攻击速度=... } }
-- for attr, oldVal in pairs(touched[hero] or {}) do
--     -- 同步到 y3 单位属性
-- end

disp()
```

### 边界 + keepRate 示例

```lua
sys:define('最大生命', true)
sys:define('当前生命', true, 0, '最大生命')          -- 上限 = 最大生命
                            :setMax('最大生命', true) -- keepRate: 比例锁定

local p = sys:instance()
p:set('最大生命', 1000)
p:set('当前生命', 500)        -- 50%

p:set('最大生命', 2000)       -- 上限翻倍
print(p:get('当前生命'))      -- 1000，仍保持 50%
```

### recordTouch 修改快照

```lua
sys:define('力量', true):recordTouch()

local p = sys:instance()
p:set('力量', 10)
p:add('力量', 5)             -- 内部记录 oldValue=10

local touched = sys:getTouched()
-- touched[p] = { 力量 = 10 }   能拿到改前的值
```

---

## 已知限制

- 编译后不可再 `define` 新属性（架构限制）
- 复杂属性（有公式）不支持 `minKeepRate` / `maxKeepRate`
- 依赖 Lua `load` 动态代码加载，需要运行时允许（y3 默认允许）
- `event` 不立即触发，需 `updateEvent()` 才分发；连锁修改时不会重复回调
- 公式 DSL 仅支持 `{符号}` 替换，复杂逻辑需在公式外用 simple 属性 + 手动维护

## 测试建议

模板包含的核心能力建议至少覆盖：

1. simple 属性 set/add/get
2. complex 属性 + 默认公式
3. complex 属性 + 自定义公式 + 引用其他属性
4. 数字边界 min/max
5. 属性引用边界 + keepRate
6. 依赖联动（A 改 → B 重算）
7. event 监听 + dispose
8. updateEvent 批量分发
9. recordTouch + getTouched
10. enableUnknown 容错

---

## 复用建议

- **不要照搬原工程的 `unit/attribute.lua`**：那是项目特有的 100+ 属性名定义，模板只导出引擎层
- **建议在新工程建立 `your-project/attribute-defs.lua`**，定义自己游戏需要的属性
- **属性命名建议英文**（`strength` / `attack_power`），避免编码问题
