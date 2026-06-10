--- =========================================================================
--- Y3 功能模板 · logic.lua  (C 级 · 三层架构 DataSchema + Adapter + PureLogic)
--- =========================================================================
---
--- @template-id   c-attr-display-panel
--- @grade         C
--- @version       v0.2.0
--- @entry         M.setup(adapter)
--- @architecture  three-layer (DataSchema + Adapter + PureLogic)
--- @source        global_script/gamePlay/ui/hud/MainHUDAttrDetail.lua
--- @description   属性显示面板：按矩阵配置渲染 N 分区 M 行的属性列表，变化事件自动刷新。
---                UI 创建完全由 Adapter 控制，模板不绑定任何 prefab/元件。
---
--- 接入只需 3 步：
---   1. 按 §1 DataSchema 准备属性矩阵数据
---   2. 实现 §2 Adapter 接口的 7 个必填方法（含 create_cell / update_cell）
---   3. M.setup(your_adapter) → M.bind_ui(root, grids, player) → M.show()
---
--- v0.2.0 变更：
---   - 移除硬编码 AttrTextCmp prefab 依赖
---   - 新增 create_cell / update_cell 回调，UI 创建完全交还用户
---   - 删除 .upui 文件（362KB → 0）
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 用户必须按此格式提供数据
-- ============================================================================
--- @class AttrUISlot
--- @field part_id integer   分区编号 (1-indexed)
--- @field row     integer   行号 (1-indexed)
--- @field attr_id any       属性标识（传给 adapter 方法）

--- @class AttrUIMatrix
--- @field slot_count   integer        总槽位数 = #row_list 元素总数
--- @field row_list     AttrUISlot[][]  二维数组 [part_id][row]

-- ============================================================================
-- §2. Adapter 接口 — 用户必须实现以下方法
-- ============================================================================
--- @class AttrDisplayAdapter
--- @field get_show_matrix  fun(): AttrUIMatrix            必填: 返回属性显示矩阵
--- @field get_attr_name    fun(attr_id: any): string      必填: 属性显示名
--- @field get_attr_display fun(unit: userdata, attr_id: any): string  必填: 格式化属性值（如 '123' / '45%'）
--- @field on_attr_change   fun(callback: function): function  必填: 注册变化监听 → 返回 dispose
--- @field get_unit         fun(): userdata|nil             必填: 获取数据源（nil=无单位时自动隐藏）
--- @field create_cell      fun(parent: UI, slot: AttrUISlot, player: userdata): UI  必填: 创建单元格UI → 返回根节点
--- @field update_cell      fun(cell_ui: UI, attr_name: string, attr_value: string, part_color: string?)  必填: 更新单元格内容
--- @field get_part_colors? fun(): string[]                 可选: 分区颜色 hex 数组
--- @field log?             fun(msg: string)               可选: 日志钩子

-- ============================================================================
-- §3. Pure Logic — 用户不需修改
-- ============================================================================

local adapter = nil
local state   = {
    ui_root       = nil,    ---@type UI|nil  面板根节点
    cells         = {},     ---@type table<integer, UI>  按 slotIndex 索引的 cell
    grid_parents  = {},     ---@type UI[]  分区 GRID 父节点
    part_count    = 0,      ---@type integer
    row_per_grid  = {},     ---@type integer[]
    is_visible    = false,  ---@type boolean
    change_disposer = nil, ---@type function|nil
}

local function tpl_log(msg)
    if adapter and adapter.log then
        adapter.log('[c-attr-display-panel] ' .. msg)
    end
end

local function tpl_validate_adapter(a)
    assert(type(a) == 'table', 'AttrDisplayAdapter must be a table')
    local required = {
        'get_show_matrix',
        'get_attr_name',
        'get_attr_display',
        'on_attr_change',
        'get_unit',
        'create_cell',
        'update_cell',
    }
    for _, name in ipairs(required) do
        assert(type(a[name]) == 'function',
            'AttrDisplayAdapter missing required method: ' .. name)
    end
end

--- 刷新全部 cell
local function tpl_refresh_all()
    if not state.is_visible then
        return
    end

    local unit = adapter.get_unit()
    if not unit then
        -- 无单位 → 全部隐藏
        for _, cell_ui in pairs(state.cells) do
            if cell_ui then
                cell_ui:set_visible(false)
            end
        end
        return
    end

    local matrix = adapter.get_show_matrix()

    local colors = nil
    if adapter.get_part_colors then
        colors = adapter.get_part_colors()
    end

    local slot_index = 0
    for part_id, row_data in ipairs(matrix.row_list or {}) do
        local part_color = colors and colors[part_id]
        for _, slot in ipairs(row_data or {}) do
            slot_index = slot_index + 1
            local cell_ui = state.cells[slot_index]
            if cell_ui then
                local name  = adapter.get_attr_name(slot.attr_id)
                local value = adapter.get_attr_display(unit, slot.attr_id)
                adapter.update_cell(cell_ui, name, value, part_color)
            end
        end
    end
end

-- ============================================================================
-- 公开 API
-- ============================================================================

--- 初始化面板（注入 Adapter）
---@param user_adapter AttrDisplayAdapter
function M.setup(user_adapter)
    tpl_validate_adapter(user_adapter)
    adapter = user_adapter
    state   = {
        ui_root       = nil,
        cells         = {},
        grid_parents  = {},
        part_count    = 0,
        row_per_grid  = {},
        is_visible    = false,
        change_disposer = nil,
    }
end

--- 绑定 UI 节点
---@param root_ui     UI    面板容器节点
---@param grid_uis    UI[]  分区 GRID 节点列表
---@param player      userdata  本地玩家对象
function M.bind_ui(root_ui, grid_uis, player)
    if not adapter then error('M.setup(adapter) not called') end

    state.ui_root      = root_ui
    state.grid_parents = grid_uis
    state.part_count   = #grid_uis

    local matrix = adapter.get_show_matrix()
    local row_per_grid = {}
    for part_id = 1, state.part_count do
        local row_data = matrix.row_list[part_id]
        row_per_grid[part_id] = row_data and #row_data or 0
    end
    state.row_per_grid = row_per_grid

    -- 通过 adapter.create_cell 按矩阵创建所有 cell
    state.cells = {}
    local slot_index = 0
    for part_id = 1, state.part_count do
        local parent = grid_uis[part_id]
        local row_data = matrix.row_list[part_id]
        for row = 1, (row_data and #row_data or 0) do
            slot_index = slot_index + 1
            local slot = row_data[row]
            local cell = adapter.create_cell(parent, slot, player)
            state.cells[slot_index] = cell
        end
    end
end

--- 显示面板
function M.show()
    if not state.ui_root then error('M.bind_ui() not called') end
    state.ui_root:set_visible(true)
    state.is_visible = true

    -- 注册变化监听
    if not state.change_disposer then
        state.change_disposer = adapter.on_attr_change(function()
            tpl_refresh_all()
        end)
    end

    tpl_refresh_all()
end

--- 隐藏面板
function M.hide()
    if not state.ui_root then return end
    state.ui_root:set_visible(false)
    state.is_visible = false

    -- 注销监听
    if state.change_disposer then
        state.change_disposer()
        state.change_disposer = nil
    end
end

--- 手动刷新
function M.refresh()
    tpl_refresh_all()
end

--- 查询面板是否可见
---@return boolean
function M.is_visible()
    return state.is_visible
end

return M
