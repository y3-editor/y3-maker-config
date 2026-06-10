--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-ui-pool
--- @version       v0.1.0
--- @entry         M.setup(params) → UIPool 实例
--- @params        cmp_class, layer_node, New
--- @source        global_script/client/ui/UIPool.lua
--- @description   通用对象池（不限于 UI），支持 pop/push + onPop/onPush 生命周期钩子。
---
--- 融合契约：
---   1. 调用方将本文件融入目标模块
---   2. cmp_class 需支持 `New(name)(layer_node)` 构造签名
---   3. params.New 注入 Class 构造器（如 y3.tools.class 导出的 New）
---   4. 组件可选择性实现 `onPop()` / `onPush()` 钩子
--- =========================================================================

local M = {}

---@class UIPoolParams
---@field cmp_class table Class 构造函数表（如 Component 的 Class 定义）
---@field layer_node any 父节点（传入构造器）
---@field New fun(class: table): fun(args: ...): any Class 实例化函数（如 y3.tools.class 导出的 New）

---@class UIPoolInstance
---@field popSlot fun(self: UIPoolInstance): any
---@field pushSlot fun(self: UIPoolInstance, slot: any)

local function validate_params(params)
    assert(type(params) == 'table', 'a-ui-pool: params must be a table')
    assert(type(params.cmp_class) == 'table', 'a-ui-pool: params.cmp_class is required')
    assert(params.layer_node ~= nil, 'a-ui-pool: params.layer_node is required')
    assert(type(params.New) == 'function', 'a-ui-pool: params.New is required')
end

--- 创建对象池
---@param params UIPoolParams
---@return UIPoolInstance
function M.setup(params)
    validate_params(params)

    local cmp_class = params.cmp_class
    local layer_node = params.layer_node
    local New = params.New

    local slot_list = {}

    ---@type UIPoolInstance
    local instance = {}

    --- 取出一个组件（池空则新建）
    ---@return any
    function instance:popSlot()
        local slot
        if #slot_list == 0 then
            slot = New(cmp_class)(layer_node)
        else
            slot = table.remove(slot_list)
        end
        if slot.onPop then
            slot:onPop()
        end
        return slot
    end

    --- 放回一个组件
    ---@param slot any
    function instance:pushSlot(slot)
        if slot.onPush then
            slot:onPush()
        end
        table.insert(slot_list, slot)
    end

    return instance
end

return M
