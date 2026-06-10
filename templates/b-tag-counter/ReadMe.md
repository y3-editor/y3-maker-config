# 标签计数器（b-tag-counter）

> 简化版羁绊/标签系统内核。纯算法 + 回调，零业务依赖。

| 字段 | 值 |
|------|-----|
| 等级 | **B** |
| 名称 | 标签计数器 |
| 路径 | `.codemaker/templates/b-tag-counter/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `标签`, `计数器`, `羁绊`, `阶梯`, `计数` |
| 适用场景 | 基于标签计数的阶梯式效果系统：羁绊种族加成、收藏品套装、单位类型协同、卡牌流派计数 |
| 依赖 | `b-tag-counter.upui`（UI 元件） |
| UI 文件 | `b-tag-counter.upui` |
| UI 根节点/资源 | **画板**: `TagCounterItem`；**控件**: `root`, `icon`, `name_TEXT`, `count_TEXT` |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `tagDefs`, `callbacks.onLevelUp`, `callbacks.onLevelDown`, `callbacks.onCountChange`（详见 §参数详述） |
| 测试状态 | `tested 20/20, Y3 + standalone Lua, 2026-05-26` |
| 集成说明 | 先导入 `b-tag-counter.upui` 到编辑器，再由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块 |
| 测试文件 | `test_tag_counter.lua`（6 用例 20 断言，Y3 游戏内 + 独立 Lua 双环境通过） |

---

## §参数详述

### `params` 表结构

```lua
{
    tagDefs = {
        [tagId:integer] = {
            name = "炽焰",              -- string 标签显示名
            icon = 12345,               -- integer? 图标资源 ID（可选）
            thresholds = {2, 4, 6},     -- integer[] 触发阶梯，必须升序
        },
    },
    perPlayer = true,   -- boolean? 是否每玩家独立数据，默认 true
    callbacks = {
        onLevelUp   = fun(pid, tid, newLv, oldLv),   -- 标签升级（跨多级时逐级触发）
        onLevelDown = fun(pid, tid, newLv, oldLv),   -- 标签降级（跨多级时逐级触发）
        onCountChange = fun(pid, tid, count, lv),    -- 数量变化（可选）
    },
}
```

### callbacks 说明

| 回调 | 触发时机 | 参数 |
|------|----------|------|
| `onLevelUp` | 计数增加导致跨阶梯 | `playerId, tagId, newLevel, oldLevel` |
| `onLevelDown` | 计数减少导致跨阶梯 | `playerId, tagId, newLevel, oldLevel` |
| `onCountChange` | 每次 addTag/removeTag | `playerId, tagId, count, level` |

> **阶梯语义**：`level=0` 表示未达成任何阈值，`level=1` 达成第 1 个阈值，依此类推。
>
> **递进规则**：`addTag(n)` / `removeTag(n)` 内部逐级步进，每步 ±1 都重新检查阶梯并触发回调，确保跨级时完整链路被感知。

---

## §接入步骤

1. 在编辑器中导入 `b-tag-counter.upui`（或通过 MCP `import_ui`）
2. 将 `logic.lua` 复制到脚本目录（`maps/EntryMap/script/` 或 `global_script/map/`）
3. 在入口文件中 `include 'b-tag-counter.logic'`
4. 调用 `M.setup(params)` 获取实例

---

## §示例代码

```lua
local TagCounter = include 'b-tag-counter.logic'

local tc = TagCounter.setup({
    tagDefs = {
        [1] = { name = "召唤", thresholds = {2, 4, 6} },
        [2] = { name = "烈焰", thresholds = {3, 6} },
    },
    callbacks = {
        onLevelUp = function(pid, tid, newLv, oldLv)
            log.info(string.format("P%d TAG%d Lv%d→Lv%d", pid, tid, oldLv, newLv))
            -- 实现效果：加属性、放技能、发事件等
            local def = tc:getTagDef(tid)
            if tid == 1 and newLv == 1 then
                -- 2 个召唤：减 CD
            elseif tid == 1 and newLv == 2 then
                -- 4 个召唤：双倍伤害
            end
        end,
        onLevelDown = function(pid, tid, newLv, oldLv)
            -- 反向移除效果
        end,
    },
})

-- 使用
tc:addTag(1, 1)       -- 玩家1 获取 1 个"召唤"标签
tc:removeTag(1, 1)    -- 玩家1 失去 1 个"召唤"标签
```

---

## §API 参考

| 方法 | 说明 |
|------|------|
| `tc:addTag(pid, tid, n?)` | 增加标签计数（默认 +1） |
| `tc:removeTag(pid, tid, n?)` | 减少标签计数（默认 -1），逐级触发降级 |
| `tc:getCount(pid, tid)` | 返回当前计数 |
| `tc:getLevel(pid, tid)` | 返回当前激活阶梯（0=未激活） |
| `tc:getAllLevels(pid)` | 返回 `{tagId=level}` |
| `tc:getNextThreshold(pid, tid)` | 返回下一个阈值，nil=全部达成 |
| `tc:reset(pid, tid?)` | 重置玩家数据 |
| `tc:getTagDef(tid)` | 返回标签定义 |
| `tc:getAllTagDefs()` | 返回所有标签定义表 |

---

## §已知限制

- 不落盘（战斗内状态，重开重置）
- 阶梯阈值必须升序排列
- 标签 ID 为整数（不支持字符串 key）
- 降级以 `removeTag(pid, tid, 1)` 逐级递减为基础逻辑；单次减 N 时内部循环 N 次逐级检查，大 N 可能产生大量回调

---

## §测试

| 环境 | 命令 |
|------|------|
| Y3 游戏内 | MCP `execute_lua` 内联执行（需游戏运行中） |
| 独立 Lua | `lua .codemaker\templates\b-tag-counter\test_tag_counter.lua` |

覆盖：基本计数、跨级 onLevelUp/onLevelDown 逐级触发、getNextThreshold、reset、多玩家隔离。

## §变更记录

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1.1 | 2026-05-26 | 修复 `M.setup` 中 `New` 用法，确保 `__init` 被调用；新增测试脚本 |
| v0.1.0 | - | 初版（从 DM42 羁绊系统剥离） |

---

## §源工程溯源

- 来源：DM42 羁绊系统（`gamePlay/manager/bond/`）剥离业务后的纯内核
- 原始系统：`BondPlayerData._ownCardSet` + `_recheck` 阶梯逻辑
