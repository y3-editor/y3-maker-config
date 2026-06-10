---
name: y3-template-export
description: |
  Y3 功能模板导出器。把项目中现有模块自动化打包为 `.codemaker/templates/<id>/` 三件套
  （`logic.lua` + `<id>.upui` + `ReadMe.md`），并追加 `draft` 条目到 `.codemaker/templates/ReadMe.md`。

  支持 4 个等级（A/B/C/D，详见 §3 与 `templates/ReadMe.md §0`）：
  - A 通用模板（单层 params）
  - B 大多数项目可复用（单层 params + 回调）
  - C 相对复杂业务逻辑（三层架构 DataSchema + Adapter + Pure Logic）
  - D 个别项目专用（不推荐导出）

  ALWAYS use this skill when user mentions:
  导出模板、打包模块、做成模板、模块复用、模板化、export template、package module。

  本 skill 与 y3-lua-pipeline / y3-ui-pipeline 完全解耦：仅做"导出"，不做融合、应用、审查。
---

# y3-template-export

把"现有模块"按 `.codemaker/templates/ReadMe.md §6` 自动化打包为 `draft` 模板候选。

## 1. 流程总图（先看这张）

```
        ┌────────────────────────┐
[用户]→ │ 1. 范围确认 🔒          │
        └───────────┬────────────┘
                    ↓
        ┌────────────────────────┐
        │ 2. UI 导出              │── y3editor.export_ui
        └───────────┬────────────┘
                    ↓
        ┌────────────────────────┐
        │ 3. lua 提取（仅读）     │── grep require / 闭包扫描
        └───────────┬────────────┘
                    ↓
        ┌────────────────────────┐
[用户]→ │ 4. 硬编码确认 🔒        │── 5 类 grep
        └───────────┬────────────┘
                    ↓
        ┌────────────────────────┐
[用户]→ │ 5. 核心提炼确认 🔒      │── 删次要/去业务依赖
        └───────────┬────────────┘
                    ↓
        ┌────────────────────────┐
        │ 6. 写 logic.lua         │── 单入口 + 头部注释 + 自检 grep
        └───────────┬────────────┘
                    ↓
        ┌────────────────────────┐
[用户]→ │ 7. ReadMe 确认 🔒       │── 14 字段 + C级额外3段
        └───────────┬────────────┘
                    ↓
        ┌────────────────────────┐
        │ 8. 追加登记入口         │── 仅追加，不改其它
        └───────────┬────────────┘
                    ↓
        ┌────────────────────────┐
        │ 9. 测试提示 + 自检       │── 输出验证清单
        └────────────────────────┘
```

**4 个人工卡点（步骤 1 / 4 / 5 / 7）必须独立确认，不可合并、不可跳过。**

## 2. 职责边界

| ✅ 本 skill 做 | ❌ 本 skill 不做 |
|---|---|
| 自动化 9 步流程产出 `draft` 候选 | 融合 `logic.lua` 到新地图 → `y3-lua-pipeline` |
| 5 类硬编码识别 + 用户确认后改写 | 模板应用到新地图 → `y3-game-spec` |
| 核心代码提炼（去外部业务依赖） | 升级状态为 `validated` → 用户手工 |
| `y3editor.export_ui` 精确导出 UI | UI JSON 生成 → `y3-ui-pipeline` |
| 在 `.codemaker/templates/ReadMe.md` 追加条目 | lua 风格审查 → `y3-lua-review` |

### 解耦红线（硬性）
- ❌ 禁止 `use_skill("y3-lua-pipeline")` / `use_skill("y3-ui-pipeline")`
- ❌ 禁止引用上述两个 skill 的 `scripts/` / `references/`
- ✅ 仅依赖：`read_file` / `grep_search` / `glob_search` / `edit` / `write` + `y3editor` MCP（`get_ui_list` / `export_ui`）

### 写入边界
| 类型 | 路径 | 方式 |
|---|---|---|
| 白名单 | `.codemaker/templates/<id>/` | 新建目录 |
| 白名单 | `.codemaker/templates/ReadMe.md` | **仅追加** |
| 黑名单 | `editor_table/` / `global_script/` / `maps/` | **严禁修改**（只读阅读） |

## 3. 模板等级机制（强制）

每个模板必须归属一个等级，决定 **架构形态**、**ID 前缀**、**ReadMe 段落要求**、**自动匹配策略**。

| 等级 | ID 前缀 | 定位 | 架构形态 | 入口签名 | 自动匹配 |
|------|---------|------|---------|---------|---------|
| **A** | `a-` 或无前缀 | 通用模板（纯工具/算法/UI 模式） | 单层：`M.setup(params)` | `params:table` | ✅ 优先 |
| **B** | `b-` | 大多数项目可复用（业务通用骨架） | 单层：`M.setup(params)` + 少量回调 | `params:table` | ✅ 次优 |
| **C** | `c-` | 相对复杂业务逻辑（自行判断是否适配） | **三层**：DataSchema + Adapter + Pure Logic | `adapter:object` | ⚠️ 候选 |
| **D** | `d-` | 个别项目专用（不知道是啥不推荐使用） | 任意，强业务耦合 | 任意 | ❌ 不参与 |

### 等级判定速查
- **A 级**：零业务耦合（贝塞尔/对象池/二次确认/UI Tween）
- **B 级**：少量业务回调（掉落组/通用 Tips/暂停菜单）
- **C 级**：完整业务流程需用户实现接口才能跑（多选一抽卡/通用结算/属性系统）
- **D 级**：源工程深度定制（特定羁绊/特定 Mgr/特定关卡）

### 选级冲突仲裁
- 不确定 A/B → 选 B
- 不确定 B/C → 选 C
- 不确定 C/D → 选 D
- D 级模板**不应主动导出**，除非用户明确要求"工程归档"

### 等级对流程的影响

| 流程步骤 | A/B 级 | C 级 |
|---------|--------|------|
| 步骤 1 范围确认 | 确认 ID + 入口 + 主功能 | **追加**：确认等级 = C + Adapter 接口清单 |
| 步骤 6 写 logic.lua | 单层 `M.setup(params)` | **三层架构**（见 §11.2） |
| 步骤 7 ReadMe 确认 | 14 字段表 + 常规段落 | **追加**：数据契约 + Adapter 接口 + MockAdapter 三段（见 `templates/ReadMe.md §4.2`） |
| 步骤 9 自检 | 通用 11 项 | **追加** 4 项 C 级特有自检 |

## 4. 触发与首句

用户说「导出模板 / 打包模块 / 做成模板 / 模块复用 / 模板化 / export template / package module」→ 激活本 skill。

激活后**第一句话必须是**：
> "好，我将把 `<module>` 打包为模板。按 `.codemaker/templates/ReadMe.md §6` 的 9 步流程执行，其中 4 个人工卡点需要你确认。请先告诉我：**模板等级**（A/B/C/D，见 §3）？**模板 ID 是什么**（kebab-case，带等级前缀如 `c-pick-one-of-many`）？**模块入口文件在哪里**？**模板的唯一主功能是什么**（一句话）？"

## 5. 输入校验（启动后立即做）

- [ ] **模板等级**：A / B / C / D 之一
- [ ] **模板 ID**：kebab-case，仅 `[a-z0-9-]`，长度 2-48，首尾非 `-`
  - **ID 前缀必须与等级一致**：B 级用 `b-`、C 级用 `c-`、D 级用 `d-`，A 级可省略前缀
  - 非法示例 → 错误文案：
    - `计分系统` → 含中文，建议 `score-system`
    - `Score_System` → 下划线+大写，建议 `score-system`
    - `-score` → 首字符为连字符
    - `a` → 长度不足
    - `pick-one` 且等级=C → 等级与前缀不匹配，建议 `c-pick-one`
- [ ] `.codemaker/templates/<id>/` **不存在**（避免覆盖既有模板）
- [ ] 模块入口文件：路径存在 + 后缀 `.lua` + 位于 `maps/` 或 `global_script/`
- [ ] `y3editor` MCP 可用（`get_ui_list` 试探）

---

## 6. 步骤 1：范围确认 🔒

**输入**：用户口语描述

**动作**：与用户对齐 4 件事 → 等级、模板 ID、入口文件、唯一主功能（C 级追加 Adapter 接口清单）

**卡点 prompt（A/B/D 级）**：
```
我将按以下范围打包模板 `<template-id>`（等级 <A/B/D>）：

入口文件：<path-to-lua>
包含功能：
  - <功能 1>
不包含：
  - <反例 1>

确认这个范围吗？
  [ ] 确认
  [ ] 需要调整：<说明>
```

**卡点 prompt（C 级）**：
```
我将按 C 级（三层架构）打包模板 `<template-id>`：

入口文件：<path-to-lua>
主功能：<一句话>
包含功能：
  - <功能 1>
不包含：
  - <反例 1>

【C 级特有】Adapter 接口规划：
  数据契约 (DataSchema):
    - <class 1>: <字段列表>
  Adapter 必填方法 (<N> 个):
    - <method_1>(...) → ... : <说明>
    - ...
  Adapter 可选方法:
    - <method_opt>(...) : <说明>

确认这个范围 + 接口设计吗？
  [ ] 确认
  [ ] 需要调整：<说明>
```

未确认 → 不得进入步骤 2。

---

## 7. 步骤 2：UI 导出

### 调用规约（`y3editor.export_ui`）

```
output_path          = <ABS .codemaker/templates/<id>/>   必填，绝对路径
output_filename      = "<template-id>.upui"                禁止用默认 clicli_export.upui
layer_names          = [...]                               步骤 3 扫描 ∩ get_ui_list
prefab_names         = [...]                               同上
scene_ui_names       = [...]                               同上
include_dependencies = true                                硬约束
```

### 强制约束
- `output_path` **必须绝对路径**
- `layer_names` / `prefab_names` / `scene_ui_names` **至少一个非空**（三空 = 整工程导出，禁止）
- `include_dependencies = true`（带上图标/模型/声音）
- **C 级纯 Lua 模板**：`include_dependencies` 可用 `false`（参考 Prefab 不需带资源），但 A/B 级 UI 模板必须 `true`

### 编辑器前置条件（`export_ui` 调用前必做）
- **UI 编辑器必须已打开**（否则 `export_ui` 报错 `UI 编辑器未打开` 或超时 30s）
- 唤醒方式：先调 `y3editor.screenshot_ui`（传入任意已有 layer 名如 `[2]Menu_Main`），自动打开 UI 编辑器后等待 2s

### 工具已知限制（来自实战验证）

| 限制 | 表现 | 对策 |
|------|------|------|
| `scene_ui_names` 过滤不生效 | 即使传无效名 `["__none__"]`，仍导出全部 8 个 scene UI（带 500KB 元数据） | **必须**在 ReadMe「已知限制」注明，用户导入后可手工清理 |
| `layer_names` 为空时全量导出 | 17 个 layer 全部打入 .upui（含 10MB `Menu_Main`） | **必须**至少传 1 个最小 layer（如 `LogoPanel`） |
| `prefab_names` 过滤生效 | `ui_prefab.json` 仅含目标 Prefab UID ✅ | 正常使用 |

### 前置 + 后置自检
- **前置**：先 `y3editor.get_ui_list` 拿全量 UI 名，与步骤 3 的 UI 候选集做交集，过滤同名非 UI
- **前置**：确保 UI 编辑器已打开（先调 `screenshot_ui` 唤醒）
- **后置体积**：
  - <10MB 正常 / 10-50MB 提示用户 / >50MB 警告并要求精简后重导
- **后置内容校验**：解压 `.upui`，检查 `ui_prefab.json` 是否仅含目标 Prefab，若含无关 layer 的 JSON（除 `LogoPanel` 外）→ 警告

### 边界情况
- **模块无 UI**：跳过本步，模板内不产生 `.upui`，ReadMe 的 `UI 文件` 字段填 `—`
- **多画板**：`layer_names` 传多个，`export_ui` 支持一次合并
- **隐式依赖元件**：靠 `include_dependencies=true` 自动带上，无需显式列入 `prefab_names`

### 常见错误
| 现象 | 原因 | 对策 |
|---|---|---|
| MCP 报 output_path not absolute | 传了相对路径 | 用绝对路径 |
| 文件名变成 clicli_export.upui | 漏传 output_filename | 强制传 `<id>.upui` |
| .upui 缺少图标/模型 | include_dependencies=false | 强制 true |
| 导出了不相关画板 | layer_names 为空 = 全量 | 禁止三空 |

---

## 8. 步骤 3：lua 提取（仅读）

**依赖闭包扫描规则**（从入口文件为种子递归收集）：
1. 直接 require：`require\("([^"]+)"\)`
2. 同目录 `.lua` 启发式（默认不纳入，标记候选，步骤 4 让用户确认）
3. 事件名字面量：`EventType\.\w+` / `y3\.game\.event_on\("([^"]+)"`

**grep 局限**（必须在步骤 4 卡点提醒用户复核）：
- 动态拼接 `require("module." .. name)`
- 运行时 `loadstring` / `dofile`
- 通过全局函数间接引用的模块

**输出**：lua 文件候选集合（仅内存，不落盘）

---

## 9. 步骤 4：硬编码确认 🔒

### 5 类识别模式

| # | 类型 | grep 模式（核心） | 默认处理 |
|---|---|---|---|
| 1 | 玩家编号 | `y3\.player\(\s*\d+\s*\)` / `Player\(\s*\d+\s*\)` / `player_id\s*==?\s*\d+` | 参数化 → `params.player_ids[i]` |
| 2 | 物编 key | snake_case 字符串 + 邻接 `y3.unit/ability/buff/item/projectile.<create\|fetch\|get>` | 参数化 → `params.<semantic>_key` |
| 3 | UI 路径 | `y3\.ui\.fetch\(\s*"([^"]+)"\s*\)` / `GetUIByName\(\s*"([^"]+)"\s*\)` | 参数化 → `params.ui_paths.<name>` |
| 4 | 地图路径/名 | `"maps/[^"]+"` / `"[Ee]ntry[Mm]ap[^"]*"` / `(map_name\|current_map)\s*==?\s*"[^"]+"` | 参数化 `params.map_name` 或显式映射 + `-- TODO` |
| 5 | 资源名 | snake_case + 邻接 `y3.effect/sound.<play\|create>` / `\.set_(icon\|model)\(` | 参数化 → `params.resources.<name>` |

### 排除项（grep 前必须先剥离）
- 行注释 `--` / 块注释 `--[[ ]]`
- 多行字符串说明文本 `[[ ]]`
- 标注 `-- SKILL:ignore-hardcode` 的行
- 玩家编号为 `0`（任意玩家占位）

### 卡点 prompt
```
扫描得到 <N> 条硬编码：

### 1. 玩家编号（<n1> 处）
- <file>:<line>   <原文>   → 建议：参数化 params.player_ids[1]
### 2. 物编 key（<n2> 处）
- ...
### 3. UI 路径（<n3> 处）
### 4. 地图路径/名（<n4> 处）
### 5. 资源名（<n5> 处）

另外请复核以下 grep 无法识别的遗漏：
  [ ] 动态 require（require("module." .. name)）
  [ ] 运行时 loadstring / dofile
  [ ] 通过全局函数间接引用的模块

请确认：
  [ ] 方案 OK
  [ ] 需要调整：<说明哪些条目改为显式映射或保留>
```

### 处理方式
- **首选 参数化**：`logic.lua` 顶部 `local params = {...}`，ReadMe `参数` 字段登记
- **次选 显式映射**：保留字面量 + `-- TODO: 替换为项目实际值`，ReadMe `参数` 注明"需人工补充"

### ⚠️ 禁止
- 禁止不经用户确认就改写
- 禁止"全自动识别 + 全自动改写"

未确认 → 不得进入步骤 5。

---

## 10. 步骤 5：核心提炼确认 🔒

**目标**：让 `logic.lua` **自包含、最精简、可独立运行**。

### 两条核心约束

#### 约束 A：仅核心成功路径
- ✅ 保留：主功能成功路径上的所有代码 + 必要参数校验
- ❌ 删除：与主功能无关的次要功能、调试日志、性能埋点、统计上报、注释掉的旧实现、多版本兼容分支（除非主功能必需）

#### 约束 B：去除一切外部业务依赖

| 类型 | 是否允许 require | 备注 |
|---|---|---|
| `y3.*`（含 y3-lualib 子模块如 `y3.unit`） | ✅ 允许 | |
| `GameAPI.*` | ✅ 允许（全局，无需 require） | |
| Lua 标准库（`math`/`string`/`table`/`os`） | ✅ 允许 | |
| **项目业务模块** | ❌ 禁止 | 删除或内联或重写 |
| **项目共享工具函数** | ❌ 禁止 | 必须内联，前缀 `tpl_` |
| **第三方 lua 库**（即使 `inspect`/`json`） | ❌ 禁止 | |

### 处理矩阵

| 遇到的依赖 | 在主功能中的角色 | 处理方式 |
|---|---|---|
| 业务模块 require | 不参与主功能（日志/监控/分析） | **删除** require + 删除所有调用点 |
| 业务模块 require | 参与且简单（<5 行） | **内联**为顶部 local，前缀 `tpl_` |
| 业务模块 require | 参与且复杂 | **重写**为 y3.*/GameAPI.*/纯 Lua，或在 ReadMe `已知限制` 标注 |
| 项目共享工具函数 | 任意 | **始终内联**（仅搬移用到的部分），前缀 `tpl_` |
| 主动通知外部业务（广播/事件） | 任意 | **删除**调用点（不通知谁是复用方的事） |
| 接收外部业务输入（监听） | 主功能必需 | 改为 `params.on_xxx` 回调，或改为 y3.* 原生事件 |
| 业务全局变量（GameState/Analytics 等） | 主功能必需 | 通过 `params` 传入 |

### 卡点 prompt
```
## 核心代码提炼清单（需你确认）

主功能（来自步骤 1）：<一句话>

### 1. 待删除的次要功能（<n1> 处）
- <file>:<lines>   <段落简介>

### 2. 待删除的业务系统调用（<n2> 处）
- <file>:<line>   <调用片段>   <角色：广播/上报/日志>   → 删除

### 3. 待内联的工具函数（<n3> 处）
- 来源：<utils 路径>:<函数名>
- 处理：内联为 logic.lua 顶部 local function tpl_<name>（仅搬本模板用到的部分）

### 4. 待重写的业务依赖（<n4> 处）
- <file>:<line>   <依赖名>   → 处理：参数化 / 重写 / 删除

### 5. 删除后保留的核心成功路径（预览）
  function M.setup(params)
    -- ... 主功能代码 ...
  end

请确认：
  [ ] 方案 OK
  [ ] 需要调整：<说明>
```

### 边界情况
- **主功能必需广播给外部** → 在 `params` 暴露**回调**（`params.on_score_changed = function(...) end`），由复用方注入；禁止模板内直接调 `EventBus.fire(...)`
- **跨模板依赖** → 禁止。耦合的两个模板要么合一，要么各自独立
- **用户要求保留"看似次要"代码** → 尊重，但在 ReadMe `已知限制` 标注

### ⚠️ 禁止
- 禁止不经用户确认就删除/内联/重写
- 禁止与步骤 4 合并为单次卡点
- 禁止跨模板依赖

### 与步骤 4 的边界
| 步骤 | 处理重点 |
|---|---|
| 步骤 4 | **数据**层：玩家编号、物编 key、UI 路径、地图名、资源名等字面量 |
| 步骤 5 | **结构**层：保留哪些功能、删除哪些功能、依赖谁、调用谁 |

未确认 → 不得进入步骤 6。

---

## 11. 步骤 6：写 logic.lua

### 单入口契约
模板内**有且仅有一个** `logic.lua`。源模块原本分多文件 → 压到单文件（用 local 表/函数）。

### 11.1 A/B 级头部注释 + 骨架
```lua
--- =========================================================================
--- Y3 功能模板 · logic.lua  (A/B 级 · 参数注入式)
--- =========================================================================
---
--- @template-id   <template-id>           -- kebab-case (B 级前缀 b-)
--- @grade         A | B                   -- 等级
--- @version       v0.1.0                  -- 首次导出固定
--- @entry         M.setup(params)         -- 融合入口
--- @params        <param1>, <param2>      -- 外部参数清单
--- @source        <source-path>           -- 源模块路径（可选但推荐）
--- @description   <一句话描述>
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块入口点
---   2. 所有外部依赖通过 M.setup(params) 传入，禁止修改 local 常量
---   3. UI 路径通过 params.ui_paths 传入，禁止依赖本模板字面量
---   4. 本模板不自行注册全局事件；如需注册由融合侧决定时机
--- =========================================================================

local M = {}

local params = {
    -- player_ids   = nil,    -- table<int>, 必填
    -- ui_paths     = nil,    -- {main_hud=..., score_text=...}, 必填
    -- target_score = 100,    -- int, 可选
}

local state = {
    -- scores_by_player = {},
}

local function validate_params()
    -- assert(params.player_ids and #params.player_ids > 0, "...")
end

function M.setup(user_params)
    user_params = user_params or {}
    for k, v in pairs(user_params) do params[k] = v end
    validate_params()
    -- TODO: 模块实际初始化逻辑
end

return M
```

### 11.2 C 级三层架构头部注释 + 骨架

C 级 logic.lua **必须**遵循以下三层布局（DataSchema → Adapter → Pure Logic），禁止任何变体。

```lua
--- =========================================================================
--- Y3 功能模板 · logic.lua  (C 级 · 三层架构 DataSchema + Adapter + PureLogic)
--- =========================================================================
---
--- @template-id   c-<name>                -- 必须 c- 前缀
--- @grade         C
--- @version       v0.1.0
--- @entry         M.setup(adapter)        -- 注入 Adapter
--- @architecture  three-layer (DataSchema + Adapter + PureLogic)
--- @source        <source-path>
--- @description   <一句话描述>
---
--- 接入只需 3 步：
---   1. 按 §1 DataSchema 准备数据格式
---   2. 实现 §2 Adapter 接口的 N 个必填方法
---   3. M.setup(your_adapter) 后调主入口方法触发流程
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 用户必须按此格式提供数据
-- ============================================================================
--- @class <SchemaName>
--- @field <field_1>  <type>  <说明>
--- ...

-- ============================================================================
-- §2. Adapter 接口 — 用户必须实现以下方法
-- ============================================================================
--- @class <AdapterName>
--- @field <method_1>  <signature>  必填: <说明>
--- @field <method_2>  <signature>  必填: <说明>
--- @field log         fun(msg:string)?  可选: 日志钩子

-- ============================================================================
-- §3. Pure Logic — 用户不需修改
-- ============================================================================

local adapter = nil
local state   = {}

local function tpl_validate_adapter(a)
    assert(type(a) == 'table', 'adapter must be a table')
    local required = { 'method_1', 'method_2' --[[ 列出所有必填 ]] }
    for _, name in ipairs(required) do
        assert(type(a[name]) == 'function',
            '<AdapterName> missing required method: ' .. name)
    end
end

-- ... 纯算法函数（一律 tpl_ 前缀） ...

---@param user_adapter <AdapterName>
function M.setup(user_adapter)
    tpl_validate_adapter(user_adapter)
    adapter = user_adapter
    state   = {}
end

-- 公开 API 必须只通过 adapter.get_xxx() / adapter.on_xxx() 与外部交互
function M.do_something(player_id)
    if not adapter then error('M.setup(adapter) not called') end
    -- ...
end

return M
```

### 11.3 C 级硬性约束（自检命中即失败）

| 检查项 | 模式 | 期望 |
|---|---|---|
| 入口签名 | `function M\.setup\(adapter\)` | ✅ 必须出现 |
| 内部校验 | `function tpl_validate_adapter` | ✅ 必须出现 |
| nil-adapter 守护 | `if not adapter then error` | ✅ 至少 1 处 |
| 直接全局调用 | 业务全局 `EventBus\.` / `Analytics\.` / `GameState\.` 出现在非注释行 | ❌ 0 命中 |
| 业务字面量 | 步骤 4 五类硬编码 | ❌ 0 命中或带 TODO |
| 三层注释段 | `§1. DataSchema` / `§2. Adapter` / `§3. Pure Logic` | ✅ 三段都在 |

### 命名约定
- 内联工具/重写业务函数 → **必须**加 `tpl_` 前缀（`local function tpl_format_score(n) ... end`）
- `M.*` 公开 API 不需前缀（module 表已隔离）

### 写入后自检（grep，命中即失败）

| 检查项 | 模式 | 期望 |
|---|---|---|
| 业务模块 require | `require\(\s*["'](?!y3[\./])[^"']+["']\s*\)` | 0 命中 |
| 全局业务变量 | `\b(EventBus\|Analytics\|GameState\|Utils)\.\w+` | 0 命中（除非已参数化） |
| 调试日志残留 | `\b(print\|logger\.\w+\|debug\.\w+)\s*\(` | 0 命中（除非主功能必需） |
| 注释掉的旧代码 | `^\s*--\s*[a-zA-Z_].*\(.*\)` 行数 | ≤ 总行数 5% |
| 5 类硬编码（步骤 4 模式） | 见 §9 表格 | 0 命中或残留均有 `-- TODO` |

---

## 12. 步骤 7：模板 ReadMe.md 确认 🔒

### 14 字段（严格对齐 `.codemaker/templates/ReadMe.md §1`）

```markdown
# <人类可读模板名称>

> **等级**：A / B / C / D
> <1-2 句话描述用途>

## 模板登记

### <template-id>

| 字段 | 内容 |
|------|------|
| 等级 | **A** / **B** / **C** / **D**（必须与 ID 前缀一致） |
| 名称 | <中文名，例：HUD 状态栏模板> |
| 路径 | `.codemaker/templates/<template-id>/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `<tag1>`, `<tag2>`, `<tag3>` |
| 适用场景 | <步骤 1 范围描述正式版> |
| 依赖 | <物编 key / UI 根节点 / 外部模块；无填 `—`> |
| UI 文件 | `<template-id>.upui` 或 `—` |
| UI 根节点/资源 | `<画板名>`; `<控件名>`, `<图片>`, `<音效>` |
| Lua 入口 | `logic.lua` |
| 入口签名 | A/B: `M.setup(params)`；C: `M.setup(adapter)` |
| 参数 | `<param1>`, `<param2>`（C 级填 `<adapter_method_1>`, ...） |
| 测试状态 | `not tested` |
| 集成说明 | A/B: 先导入 `.upui`，再由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块；C: 追加 "需先实现 Adapter 接口（见模板 ReadMe §Adapter 接口）" |
```

### C 级追加强制段落

C 级 ReadMe **必须**在「参数详述」前追加三段（详见 `templates/ReadMe.md §4.2`）：

1. **数据契约 (DataSchema)** — 每个 typed table 用 EmmyLua `@class` 描述
2. **Adapter 接口** — 列出所有方法：方法 / 签名 / 必填 / 说明
3. **测试用 MockAdapter** — 提供全打桩 demo，复用方零业务跑通

且 C 级「接入步骤」段必须以**完整可运行 demo**（30-50 行）形式给出，覆盖 require / 数据准备 / Adapter 实现 / setup / 触发方法 5 个动作。

### 字段硬约束
- **等级**：必填 A/B/C/D，必须与 ID 前缀一致（B→`b-` / C→`c-` / D→`d-` / A→可省略）
- **状态**：必填 `draft`，**禁止**自动写 `validated`
- **版本**：首次导出固定 `v0.1.0`
- **测试状态**：必填 `not tested`
- **Lua 入口**：固定 `logic.lua`
- **入口签名**：A/B 必须 `M.setup(params)`，C 必须 `M.setup(adapter)`
- **UI 文件**：纯 Lua 模板填 `—`，并在正文加 `> 注意：本模板为纯 Lua 模板，不含 UI`

### 卡点 prompt
```
模板 ReadMe.md 已生成：

<完整内容>

请确认：
  [ ] OK
  [ ] 需要调整：<说明哪些字段改什么>
```

未确认 → 不得进入步骤 8。

---

## 13. 步骤 8：追加登记入口

**定位策略**：在 `.codemaker/templates/ReadMe.md` 中找 `## 7. 当前可用模板`
- **首选**：在该标题**之前**插入新条目（与既有示例同格式）
- **次选**：找不到 → 追加到文件末尾 + 日志记录警告 + 提示用户手工调整

**追加内容**：完整 14 字段表格（与模板内 ReadMe 一致），外包 `### <template-id>` 标题。

**等级排序建议**：插入位置按 A → B → C → D 等级排序，同级按字母顺序。

### ⚠️ 禁止
- 禁止修改 §1-§6 规范文字
- 禁止批量修改已有条目
- 禁止写入 `validated` 状态

---

## 14. 步骤 9：测试提示 + 自检

### 提示文本
```
✅ 模板 `<template-id>` 已打包为 draft：
   - 目录：.codemaker/templates/<template-id>/
   - 登记：.codemaker/templates/ReadMe.md

下一步（需你手工完成，本 skill 不做）：
  1. 打开"模板测试工程"（专用空工程，如 test321321）
  2. 导入 .upui + 融合 logic.lua（可调 y3-game-spec 或手工）
  3. 运行测试用例

  【A/B 级验证路径】
    L1: 写测试脚本（≥10 用例）→ 游戏里 include → 看 ALL TESTS PASSED
    满足 → 可升 validated

  【C 级验证路径（强制两层）】
    L1: 写测试脚本（≥15 用例）→ 游戏里跑 → 看 ALL TESTS PASSED
    L2: 写真实 Demo（含 UI Adapter）→ 手动交互 → 确认完整流程可用
        L2 期间遇到的 API 陷阱 → 必须归档到 lua-issues/api_issues.md
        并补充到模板 ReadMe 的「接入步骤」段（含代码示例）
    L1+L2 均通过 → 可升 validated
    仅 L1 通过 → 标记 "validated-logic-only"（y3-game-spec 不自动匹配）

  4. 验证通过后，把登记条目的：
       状态     draft      → validated
       版本     v0.1.0     → v1.0.0（首个正式版）
       测试状态 not tested → validated in <TestMap>, <YYYY-MM-DD>, passed (N/N)
```

### 交付自检清单（任一失败 → 禁止宣布完成）

**通用项（A/B/C/D 全适用）**

- [ ] `.codemaker/templates/<id>/ReadMe.md` 存在且 14 字段齐全（含「等级」「入口签名」字段）
- [ ] `.codemaker/templates/<id>/logic.lua` 存在，是唯一 `.lua` 文件
- [ ] `logic.lua` 头部含 `@template-id` / `@grade` / `@version` / `@entry`
- [ ] **等级前缀一致**：B→`b-*` / C→`c-*` / D→`d-*` / A→可省略
- [ ] `.codemaker/templates/<id>/<id>.upui` 存在 + 体积合理（纯 Lua 模板可豁免）
- [ ] 模板目录无其它文件（无 `.bak` / `.tmp` / `.log`）
- [ ] 5 类硬编码 grep `logic.lua` 无残留（或残留均带 `-- TODO`）
- [ ] **自包含合规**：`logic.lua` 所有 require 仅匹配 `^y3[\./]`，无业务模块 require
- [ ] **无外部业务全局**：`logic.lua` 无 `EventBus.` / `Analytics.` / `GameState.` / `Utils.`（除非已 params/adapter 化）
- [ ] **无调试残留**：无未参与主功能的 `print(...)` / `logger.*(...)` / `debug.*(...)`
- [ ] `.codemaker/templates/ReadMe.md` 比流程前多一个条目，其它内容字节级不变
- [ ] 条目状态 = `draft`，测试状态 = `not tested`
- [ ] `editor_table/` / `global_script/` / `maps/` 下 `git status` 清洁

**C 级追加项**

- [ ] `logic.lua` 入口签名为 `function M.setup(adapter)`
- [ ] `logic.lua` 含 `tpl_validate_adapter` 函数且 `setup` 内调用
- [ ] `logic.lua` 含 `§1. DataSchema` / `§2. Adapter` / `§3. Pure Logic` 三段注释
- [ ] 公开 API（`M.xxx`）至少 1 处 `if not adapter then error` 守护
- [ ] 模板 ReadMe 含「数据契约」「Adapter 接口」「测试用 MockAdapter」三段
- [ ] 「接入步骤」段为 30-50 行完整可运行 demo

**自检失败时**：列出失败项 → 不追加登记条目（已追加则回滚）→ 提示用户手动检查。

---

## 15. 流程禁令

- ❌ 禁止跳步（如跳过核心提炼直接写 logic.lua）
- ❌ 禁止倒置（如先追加登记再写 logic.lua）
- ❌ 禁止合并卡点（必须 4 次独立确认，不可"一次确认全部"）
- ❌ 未确认时不得生成后续产物 / 不得调 MCP 写操作
- ❌ 禁止修改源工程文件（`maps/` / `global_script/` / `editor_table/` 只读）

## 16. 唯一权威规范

`.codemaker/templates/ReadMe.md` —— 本 skill 所有规则均派生自此文件 §0-§6（§0 等级机制 / §1-§6 模板规范）。
冲突时以 `.codemaker/templates/ReadMe.md` 为准。
