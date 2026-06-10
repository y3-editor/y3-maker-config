# 属性显示面板 (Attribute Display Panel)

> **等级**：C
> 按矩阵配置渲染 N 分区 M 行的属性列表面板，属性变化时自动刷新。
> UI 创建完全由 Adapter 控制，模板零 prefab 依赖。
> 适配任何 RPG / 数值类游戏的属性展示需求。

## 模板登记

### c-attr-display-panel

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 属性显示面板 |
| 路径 | `.codemaker/templates/c-attr-display-panel/` |
| 状态 | `validated` |
| 版本 | `v0.2.0` |
| 能力标签 | `attr-display`, `stat-panel`, `grid-view`, `auto-refresh`, `rpg-hud`, `zero-prefab` |
| 适用场景 | 属性显示面板：N 分区 M 行的属性列表（单元格=名称+数值），支持 isFloor 双模式，变化事件自动刷新。UI 创建由用户完全控制，不限 prefab/元件类型。适配任何 RPG/数值类游戏的属性展示需求。 |
| 依赖 | —（无需 .upui，UI 全由 Adapter 创建） |
| UI 文件 | — |
| UI 根节点/资源 | —（用户自行在 HUD 中搭建 Layout + GRID 容器） |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter)` |
| 参数 | `get_show_matrix`, `get_attr_name`, `get_attr_display`, `on_attr_change`, `get_unit`, `create_cell`, `update_cell`, `get_part_colors?` |
| 测试状态 | `tested, 2026-05-27, 8/8 pure + 4/4 mock UI passed` |
| 集成说明 | 需先实现 Adapter 接口（含 create_cell/update_cell），然后 `M.setup(adapter)` → `M.bind_ui(root_ui, grid_uis, player)` → `M.show()` / `M.hide()` |

---

## 变更记录

### v0.2.0 (2026-05-27)
- **移除硬编码 AttrTextCmp prefab 依赖**，删除 `.upui` 文件（362KB → 0）
- **新增 2 个必填回调**：`create_cell(parent, slot, player) → cell_ui`、`update_cell(cell_ui, attr_name, attr_value, part_color)`
- Adapter 必填方法从 5 个增至 7 个

---

## 数据契约 (DataSchema)

### AttrUISlot

```lua
---@class AttrUISlot
---@field part_id integer   分区编号 (1-indexed)
---@field row     integer   行号 (1-indexed)
---@field attr_id any       属性标识（传给 adapter 方法）
```

### AttrUIMatrix

```lua
---@class AttrUIMatrix
---@field slot_count   integer        总槽位数
---@field row_list     AttrUISlot[][]  二维数组 [part_id][row]
```

**示例矩阵**（3 分区，每个 3 行）：

```lua
{
    slot_count = 9,
    row_list = {
        -- 分区 1：战斗属性
        {
            { part_id = 1, row = 1, attr_id = '力量' },
            { part_id = 1, row = 2, attr_id = '敏捷' },
            { part_id = 1, row = 3, attr_id = '智力' },
        },
        -- 分区 2：防御属性
        {
            { part_id = 2, row = 1, attr_id = '最大生命' },
            { part_id = 2, row = 2, attr_id = '护甲' },
            { part_id = 2, row = 3, attr_id = '伤害减免' },
        },
        -- 分区 3：输出属性
        {
            { part_id = 3, row = 1, attr_id = '暴击率' },
            { part_id = 3, row = 2, attr_id = '暴击伤害' },
            { part_id = 3, row = 3, attr_id = '冷却缩减' },
        },
    },
}
```

---

## Adapter 接口

### AttrDisplayAdapter

| 方法 | 签名 | 必填 | 说明 |
|------|------|------|------|
| `get_show_matrix` | `fun(): AttrUIMatrix` | ✅ | 返回属性显示矩阵 |
| `get_attr_name` | `fun(attr_id: any): string` | ✅ | 属性显示名（如 `'力量'`） |
| `get_attr_display` | `fun(unit: userdata, attr_id: any): string` | ✅ | 格式化属性值（如 `'123'` / `'45%'` / `'12.3/s'`） |
| `on_attr_change` | `fun(callback: function): function` | ✅ | 注册变化监听；返回 `dispose()` 注销函数 |
| `get_unit` | `fun(): userdata\|nil` | ✅ | 获取数据源；返回 `nil` 时面板自动隐藏 |
| **`create_cell`** | `fun(parent: UI, slot: AttrUISlot, player: userdata): UI` | ✅ **v0.2.0 新增** | 在 parent 下创建单元格 UI，返回根节点 |
| **`update_cell`** | `fun(cell_ui: UI, attr_name: string, attr_value: string, part_color: string?)` | ✅ **v0.2.0 新增** | 更新单元格显示内容 |
| `get_part_colors` | `fun(): string[]` | ❌ | 分区标题颜色 hex 数组，缺省全白色 |
| `log` | `fun(msg: string)` | ❌ | 日志钩子 |

### create_cell 实现要点

- `parent` 是 `bind_ui` 传入的 GRID 容器节点
- `slot` 包含 `part_id`、`row`、`attr_id`，可用于差异化创建（如不同图标）
- 返回的 `cell_ui` 会被模板持有，后续 `update_cell` 会传回
- **建议**：用闭包或 adapter 字段存储子控件引用，方便 `update_cell` 时快速操作

### update_cell 实现要点

- `cell_ui` 是 `create_cell` 的返回值
- `attr_name` 和 `attr_value` 已由模板通过 `get_attr_name` / `get_attr_display` 解析好
- `part_color` 为 nil 时不设置颜色（用默认色）

---

## 最简单 create_cell / update_cell 示例（5 行）

```lua
-- 用闭包存储每个 cell 的子控件引用
local cell_children = {}

create_cell = function(parent, slot, player)
    local cell = y3.ui.create_child(parent, 'Layout')
    local nameText  = y3.ui.create_child(cell, 'Text')
    local valueText = y3.ui.create_child(cell, 'Text')
    cell_children[cell] = { name = nameText, value = valueText }
    return cell
end,

update_cell = function(cell_ui, attr_name, attr_value, part_color)
    local ch = cell_children[cell_ui]
    ch.name:set_text(attr_name)
    ch.value:set_text(attr_value)
    if part_color then ch.name:set_text_color_hex(part_color) end
end,
```

---

## 测试用 MockAdapter

用于纯 Lua 环境验证模板逻辑可用性：

```lua
local mock_unit = {}  -- 空表充当 unit

local mock_attr_values = {
    ['力量'] = 25, ['敏捷'] = 18, ['智力'] = 15,
    ['攻击'] = 120, ['护甲'] = 45, ['暴击率'] = '35%',
}

-- mock UI（纯 Lua 对象，非真实 y3 UI）
local mock_cells = {}
local function mock_ui(name)
    return { _name = name, _visible = true, _text = '', _color = '',
        set_visible = function(self, v) self._visible = v end,
        set_text = function(self, v) self._text = v end,
        set_text_color_hex = function(self, v) self._color = v end,
    }
end

local mock_adapter = {
    get_show_matrix = function()
        return {
            slot_count = 3,
            row_list = {
                { { part_id = 1, row = 1, attr_id = '力量' }, { part_id = 1, row = 2, attr_id = '敏捷' } },
                { { part_id = 2, row = 1, attr_id = '智力' } },
            },
        }
    end,
    get_attr_name = function(attr_id) return attr_id end,
    get_attr_display = function(unit, attr_id)
        return tostring(mock_attr_values[attr_id] or '0')
    end,
    on_attr_change = function(callback)
        local active = true
        return function() active = false end
    end,
    get_unit = function() return mock_unit end,
    create_cell = function(parent, slot, player)
        local cell = mock_ui('cell_' .. slot.attr_id)
        mock_cells[#mock_cells + 1] = cell
        return cell
    end,
    update_cell = function(cell_ui, attr_name, attr_value, part_color)
        cell_ui._text = attr_name .. ': ' .. attr_value
        if part_color then cell_ui._color = part_color end
    end,
    get_part_colors = function() return { "#ff5d5d", "#5dda95" } end,
}
```

---

## 使用示例（生产级）

### 结合 `b-attribute-system`

```lua
local AttrSystem = require 'b-attribute-system'
local Panel = require 'c-attr-display-panel'

-- Step 1: 创建属性系统
local sys = AttrSystem.setup()
sys:define('力量', true)
sys:define('攻击', false)
sys:define('暴击率', true)
local hero_attr = sys:instance()

-- Step 2: 存储 cell 子控件引用的闭包
local cell_refs = {}

-- Step 3: 实现 Adapter
local adapter = {
    get_show_matrix = function()
        return {
            slot_count = 3,
            row_list = {
                { { part_id = 1, row = 1, attr_id = '力量' },
                  { part_id = 1, row = 2, attr_id = '攻击' },
                  { part_id = 1, row = 3, attr_id = '暴击率' } },
            },
        }
    end,
    get_attr_name = function(attr_id) return attr_id end,
    get_attr_display = function(unit, attr_id)
        return tostring(hero_attr:get(attr_id))
    end,
    on_attr_change = function(callback)
        -- 每帧 sys:updateEvent() 后触发
        local active = true
        return function() active = false end
    end,
    get_unit = function() return {} end,
    create_cell = function(parent, slot, player)
        local cell = y3.ui.create_child(parent, 'Layout')
        local nameText  = y3.ui.create_child(cell, 'Text')
        local valueText = y3.ui.create_child(cell, 'Text')
        cell_refs[cell] = { name = nameText, value = valueText }
        return cell
    end,
    update_cell = function(cell_ui, attr_name, attr_value, part_color)
        local ch = cell_refs[cell_ui]
        ch.name:set_text(attr_name)
        ch.value:set_text(attr_value)
        if part_color then ch.name:set_text_color_hex(part_color) end
    end,
    get_part_colors = function() return { "#ff5d5d" } end,
}

-- Step 4: 创建面板
Panel.setup(adapter)
Panel.bind_ui(hud_root, { attr_grid_1 }, local_player)
Panel.show()

-- 切换页面时
Panel.hide()
Panel.show()
```

---

## 已知限制

- 不支持列式布局（多个属性并排），每个 GRID 内部是一列垂直排列
- `isFloor` 模式通过 `adapter.get_unit()` 返回不同 unit 实现，面板本身不区分模式
- `on_attr_change` 不自动关联更新帧，需调用方在帧循环中处理
- `create_cell` 创建的子控件引用需用户自行管理（闭包/adapter 字段），模板不持有子控件引用

## 测试建议

模板包含的核心能力建议至少覆盖：

1. adapter 校验（缺方法/非 table 拒绝）
2. setup → bind_ui → show → hide 完整生命周期
3. 空矩阵（0 cell）不会报错
4. `get_unit` 返回 nil 时 cell 自动隐藏
5. `on_attr_change` 在 show 时注册、hide 时注销
6. `update_cell` 正确收到已解析的 name/value/color

---

*最后更新: 2026-05-27 — v0.2.0 移除 prefab 依赖*
