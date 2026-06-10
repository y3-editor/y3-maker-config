# Y3 功能模板库

本目录是 Y3 项目的「功能模板库」入口。每个子目录为一个**功能模板**，由 `y3-template-export` skill 从现有模块打包产出，由 `y3-game-spec` 在 Phase 2 做模板匹配后通过 `y3-ui-pipeline` / `y3-lua-pipeline` 复用。

---

## 0. 模板等级机制（强制）

每个模板必须在 ID 前缀和 ReadMe 的「等级」字段中明确归属一个等级。等级决定**架构形态**、**复用门槛**、**自动匹配策略**。

| 等级 | ID 前缀 | 定位 | 架构形态 | 复用门槛 | 自动匹配 |
|------|---------|------|---------|---------|---------|
| **A** | `a-` 或无前缀 | **通用模板** | `M.setup(params)` 单函数 + 扁平 params | 极低，传值即可 | ✅ 优先匹配 |
| **B** | `b-` | **大多数项目可复用** | `M.setup(params)` + 少量回调 | 低，准备配置 + 实现 1-3 个回调 | ✅ 次优匹配 |
| **C** | `c-` | **相对复杂业务逻辑**（自行判断是否与当前项目适配） | **三层架构**：DataSchema + Adapter 接口 + Pure Logic | 中，需实现 Adapter（7-15 个方法） | ⚠️ 仅候选，需用户确认 |
| **D** | `d-` | **个别项目专用**（不知道是啥不推荐使用） | 任意，强业务耦合 | 高，需读源工程才能用 | ❌ 不参与自动匹配 |

### 等级判定规则
- **A 级**：纯工具/算法/通用 UI 模式，零业务耦合（贝塞尔/对象池/二次确认）
- **B 级**：业务通用骨架，依赖少量配置和回调（掉落组/通用 Tips/暂停菜单）
- **C 级**：业务逻辑骨架，需用户实现接口才能跑（多选一抽卡/通用结算/属性系统）
- **D 级**：源工程深度定制实现，跨项目移植成本极高（羁绊/特定 Mgr/特定关卡）

### 选级冲突仲裁
- 不确定 A/B → 选 B
- 不确定 B/C → 选 C
- 不确定 C/D → 选 D
- D 级模板**不应主动导出**，除非用户明确要求"工程归档"

---

## 1. 模板目录条目格式

每个模板必须在本文件 §7 登记一条 15 字段表格，模板自身 `ReadMe.md` 内也必须包含同样字段：

| 字段 | 说明 | 取值约束 |
|------|------|---------|
| 等级 | A/B/C/D 等级标识 | 必填，与 ID 前缀一致 |
| 名称 | 面向人类的中文模板名 | 简洁可识别 |
| 路径 | 模板目录路径 | `.codemaker/templates/<template-id>/` |
| 状态 | 模板可用性状态 | `draft` / `validated` |
| 版本 | 模板版本 | 语义化版本，首次导出 `v0.1.0`，首个正式版 `v1.0.0` |
| 能力标签 | 用于 `y3-game-spec` 模板匹配的短 tag | 3-5 个为宜 |
| 适用场景 | 长句描述模板覆盖的功能边界 | 来自导出时的范围确认 |
| 依赖 | 物编 key / UI 根节点 / 外部模块 | 无填 `—` |
| UI 文件 | 模板的 `.upui` 文件名 | `<template-id>.upui` 或 `—`（纯 Lua 模板） |
| UI 根节点/资源 | 涉及的画板名 / 控件 / 自定义资源 | `画板名`; `控件1`, `资源1` |
| Lua 入口 | 模板入口 Lua 文件 | 固定 `logic.lua` |
| 入口签名 | `M.setup(...)` 的形参 | A/B: `params`；C: `adapter` |
| 参数 | 简短参数名清单（详细在模板 ReadMe 的「参数详述」段） | 逗号分隔 |
| 测试状态 | 验证情况 | `not tested` 或 `validated in <TestMap>, <YYYY-MM-DD>, passed` |
| 集成说明 | 默认接入流程描述 | A/B: 默认 `先导入 .upui，再由 y3-lua-pipeline 将 logic.lua 融合到对应模块`；C: 追加 `需先实现 Adapter 接口` |

## 2. 模板包结构（三件套）

每个模板目录**必须**包含且**仅**包含以下文件：

```
.codemaker/templates/<template-id>/
├── <template-id>.upui   ← UI 导出文件（纯 Lua 模板可省略）
├── logic.lua            ← 唯一 Lua 入口（强制单文件 + 自包含）
└── ReadMe.md            ← 模板自身说明（含 13 字段表 + 参数详述 + 接入步骤 + 已知限制 + 源工程溯源）
```

不允许包含：临时文件（`.bak` / `.tmp` / `.log`）、多个 `.lua` 文件、子目录。

## 3. 可用性规则（硬性约束）

1. **状态机**：`draft` → 测试工程验证通过后用户手工升级为 `validated`，skill 不得自动升级
2. **`y3-game-spec` 自动匹配**：仅匹配 `validated` 状态的模板；`draft` 模板不参与自动匹配
3. **版本规约**：首次导出 `v0.1.0`，首个正式版 `v1.0.0`，后续语义化版本
4. **入口契约**：
   - A/B 级：`logic.lua` 必须暴露 `M.setup(params)` 作为融合入口
   - C 级：`logic.lua` 必须暴露 `M.setup(adapter)`，且 `setup` 内部必须做 `tpl_validate_adapter` 校验
5. **自包含**：`logic.lua` 仅允许 `require("y3...")` 或使用 `GameAPI.*` / Lua 标准库；禁止业务模块 require、禁止业务全局变量、禁止第三方 lua 库
6. **参数化优先**：所有玩家编号、物编 key、UI 路径、地图名、资源名等环境相关字面量必须通过 `params` / `adapter` 传入，禁止硬编码
7. **不含调试残留**：禁止未参与主功能的 `print` / `logger.*` / `debug.*` 调用
8. **不跨模板依赖**：两个模板若功能耦合，要么合并为一个，要么各自独立
9. **C 级三层分离**（仅 C 级）：
   - **DataSchema 层**：在 `logic.lua` 顶部用 EmmyLua `@class` 注释描述
   - **Adapter 层**：在 `logic.lua` 中定义 `@class XxxAdapter` 接口 + `tpl_validate_adapter` 校验函数
   - **Pure Logic 层**：核心算法不直接读外部数据，全部通过 `adapter.get_xxx()` 拉取，通过 `adapter.on_xxx()` 通知

## 4. 模板 ReadMe.md 结构（模板自身）

### 4.1 通用段落（A/B/C/D 全适用）

模板自身的 `ReadMe.md` 必须包含以下段落（顺序固定）：

```markdown
# <人类可读模板名称>

> **等级**：A / B / C / D
> <1-2 句话描述>

## 模板登记
<### template-id 标题 + 14 字段表格>

## 内置资源（可选）
<UID 到资源名的映射表，便于追溯随 .upui 导入的元件/资源>

## 参数详述
<参数名 / 类型 / 必填 / 默认值 / 说明 表格>

## 接入步骤
<给复用方的 4-6 步操作指引>

## 已知限制
<列出未覆盖的功能边界；无则填 `暂无已知限制`>

## 源工程溯源
- 源模块：<源路径>
- 导出日期：<YYYY-MM-DD>
- 导出工具：`y3-template-export`
```

### 4.2 C 级追加强制段落

C 级模板因为采用三层架构（DataSchema + Adapter + Pure Logic），ReadMe **必须**在「参数详述」前追加以下三段：

```markdown
## 数据契约 (DataSchema)

列出所有用户必须按格式提供的 typed table 结构定义。每个结构用 EmmyLua `@class` 风格描述：

```lua
--- @class PickPoolItem
--- @field id        integer  唯一 ID
--- @field weight    integer  权重 (>0)
--- @field data?     any      业务自定义透传字段（模板不读取）
```

## Adapter 接口

列出用户必须实现的所有方法。`必填` 列必须明示，否则视为可选。

| 方法 | 签名 | 必填 | 说明 |
|------|------|------|------|
| `get_pool` | `fun(pid:integer):PickPoolItem[]` | ✅ | 返回当前可抽卡池 |
| `on_picked` | `fun(pid:integer, item:PickPoolItem)` | ✅ | 玩家选中后业务回调 |
| `log` | `fun(msg:string)?` | — | 可选日志钩子 |

## 测试用 MockAdapter

提供一份**全打桩**的 Adapter 实现，复用方可以零业务侵入跑通流程：

```lua
local MockAdapter = {
    get_pool = function() return { {id=1,weight=1}, {id=2,weight=1} } end,
    on_picked = function(pid, item) print('picked:', item.id) end,
    -- ... 其它方法的最简实现
}
```
```

### 4.3 C 级 「接入步骤」 写作要求

C 级的「接入步骤」段必须以**完整可运行的 demo**（30-50 行）形式给出，覆盖：
1. require 模板
2. 准备数据 schema
3. 实现 Adapter
4. 调 `M.setup(adapter)` 完成接入
5. 调主入口方法触发流程

## 5. 与生态的衔接

| 阶段 | 工具 | 责任 |
|------|------|------|
| **导出**（产出模板） | `y3-template-export` | 把现有模块打包为 `draft` 候选 |
| **登记** | `y3-template-export` 自动 / 用户手工 | 在本文件 §7 追加条目 |
| **测试** | 用户在测试工程手工 | 验证通过后状态 → `validated` |
| **匹配** | `y3-game-spec` Phase 2 | 读取本文件 §7，按能力标签 + 适用场景做模糊匹配 |
| **应用** | `y3editor.import_ui` + `y3-lua-pipeline` | 导入 `.upui`，融合 `logic.lua` 到目标模块 |

## 6. 制作模板流程

由 `y3-template-export` skill 自动化执行（详见 `skills/y3-template-export/SKILL.md`）。9 步流程，4 个人工卡点（步骤 1 / 4 / 5 / 7）：

1. **范围确认 🔒** —— 模板 ID + 入口文件 + 唯一主功能
2. **UI 导出** —— `y3editor.export_ui` 精确导出，`include_dependencies=true`
3. **lua 提取** —— 从入口文件递归扫描 require 闭包
4. **硬编码确认 🔒** —— 5 类硬编码识别 + 用户确认参数化方案
5. **核心提炼确认 🔒** —— 删次要功能 / 去外部业务依赖 / 内联工具函数
6. **写 logic.lua** —— 单文件 + 头部注释 + 自包含 + grep 自检
7. **ReadMe 确认 🔒** —— 13 字段表 + 用户确认
8. **追加登记入口** —— 在本文件 §7 追加条目
9. **测试提示 + 自检** —— 提示用户去测试工程验证

---

## 7. 当前可用模板

### a-aoe-point

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 点范围AOE视觉管线 |
| 路径 | `.codemaker/templates/a-aoe-point/` |
| 状态 | `validated` |
| 版本 | `v1.0.0` |
| 能力标签 | `aoe`, `area-damage`, `skill-visual`, `particle-pipeline`, `circle-aoe`, `rect-aoe`, `zero-dependency` |
| 适用场景 | 任何"对地面/目标位置造成范围伤害"的技能视觉表现。圆形(单段/多段)/矩形AOE。仅依赖 y3 引擎 API，可跨项目使用。 |
| 依赖 | —（仅 y3 引擎 API） |
| UI 文件 | —（纯 Lua 模板） |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → { trigger, cleanup }` |
| 参数 | `owner`, `aoe_radius`, `delay`, `count`, `interval`, `release_particle`, `hit_particle`, `aoe_type`, `rect_width`, `rect_length`, `on_hit`, `on_cast`, `get_target_point` |
| 测试状态 | `tested, 2026-06-01, 3/3 smoke PASS` |
| 集成说明 | 1. `include 'a-aoe-point'` 2. `M.setup({...})` 3. `skill.trigger(targetPoint)` |

---

### a-bezier-trajectory

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 贝塞尔弹道模板 |
| 路径 | `.codemaker/templates/a-bezier-trajectory/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `trajectory`, `projectile`, `bezier` |
| 适用场景 | 需要让投射物按二次/三次贝塞尔曲线飞向单位或点目标，并支持速度、加速度、转直线追踪等参数的技能表现。 |
| 依赖 | Y3 原生 API：`y3.timer.loop_frame`, `y3.point.create`; 调用方需传入 `Projectile`、`Unit` 或 `Point` 对象 |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `max_speed`, `delta_time`, `lut_segments`, `switch_ratio` |
| 测试状态 | `validated in agentmap, 2026-05-26, passed` |
| 集成说明 | 本模板不含 `.upui`；由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块并在初始化时调用 `M.setup({...})` |

---

### a-date-time

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 时间格式化与判定工具集 |
| 路径 | `.codemaker/templates/a-date-time/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `time`, `timestamp`, `format`, `date`, `countdown`, `cross-day`, `cross-week` |
| 适用场景 | 倒计时显示、跨天/跨周刷新、签到、时间区间判定、GM模拟时间调试 |
| 依赖 | `os.date` / `os.time`；可选 `params.get_server_time` |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → 工具函数表` |
| 参数 | `params.get_server_time?`, `params.utc_offset?` (默认 8) |
| 测试状态 | `tested, 2026-06-01, 12/12 PASS` |
| 集成说明 | `local Time = include '...'; local t = Time.setup({ get_server_time = y3.game.get_current_server_time })` |

---

### a-double-check-dialog

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 二次确认弹窗模板 |
| 路径 | `.codemaker/templates/a-double-check-dialog/` |
| 状态 | `validated` |
| 版本 | `v1.0.0` |
| 能力标签 | `ui`, `dialog`, `confirm`, `double-check`, `popup` |
| 适用场景 | 删除、退出、购买、解锁、分解等高风险操作前，需要弹出标题 + 内容 + 确认/取消回调的二次确认界面。 |
| 依赖 | Y3 原生 API：`y3.ui_prefab.create`, `y3.ui.get_ui`; 导入 `.upui` 后提供 `DoubleCheck` Prefab 与 `[0]DoubleCheck` 挂载画板 |
| UI 文件 | `a-double-check-dialog.upui` |
| UI 根节点/资源 | `[0]DoubleCheck`(Layer, UID `101b8f3a-0177-4bcc-b38f-59ada6bfd3c9`); `DoubleCheck`(Prefab, UID `ea35c113-4e25-4944-8f83-a4346915adfa`) |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `prefab_name`, `ui_path`, `parent_ui`, `get_parent_ui`, `player`, `get_player`, `bind_ui_effect`, `on_error`, `paths`, `auto_remove` |
| 测试状态 | `validated in agentmap, 2026-05-27, passed` |
| 集成说明 | 先导入 `.upui`，再由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块；初始化时调用 `M.setup({...})`，业务触发点调用 `M.show(title, content, on_confirm, on_cancel)` |

---

### a-event-bus

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 纯 Lua 订阅发布事件总线 |
| 路径 | `.codemaker/templates/a-event-bus/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `event`, `pubsub`, `subscribe`, `publish`, `decouple`, `bus` |
| 适用场景 | 跨模块解耦通信（Manager ↔ UI、Manager ↔ Manager）。替代直接引用，降低耦合度。背包变化→UI刷新+战力重算+成就检测 |
| 依赖 | 纯 Lua |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → EventBus` |
| 参数 | `params.debug?`, `params.on_error?`, `params.sort_mode?` ("priority"/"none") |
| 测试状态 | `tested, 2026-06-01, 4/4 PASS` |
| 集成说明 | `local EventBus = include '...'; MyGame.bus = EventBus.setup({})` |

---

### a-float-tips

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 浮动文本提示 |
| 路径 | `.codemaker/templates/a-float-tips/` |
| 状态 | `validated` |
| 版本 | `v0.2.0` |
| 能力标签 | `浮动提示`, `弹字`, `渐隐动画`, `伤害数字` |
| 适用场景 | 任何需要在指定位置显示临时文本并自动消失的场景，如伤害数字、金币获取提示、状态变化提示等 |
| 依赖 | `y3.ui_prefab.create`（父节点 UI 必传），需开启 `y3.config.sync.mouse = true` |
| UI 文件 | —（v0.2.0 纯 Lua，元件由 pipeline 自动创建） |
| UI 根节点/资源 | `FloatTips` 元件; `_title_TEXT` 文本控件 |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.float_text(params)` |
| 参数 | `player` (必填), `text` (必填), `root_ui` (必填), `pos_x?`, `pos_y?`, `duration?`, `prefab_id?`, `text_child?` |
| 测试状态 | `tested, 2026-05-29, EntryMap 5/5 scenarios passed` |
| 集成说明 | y3-ui-pipeline 自动导入 `.upui` → y3-lua-pipeline 融合 `logic.lua` → 调用方传入 `root_ui` 即可使用 |

---

### a-game-timer

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 三层时间轴回调调度器 |
| 路径 | `.codemaker/templates/a-game-timer/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `timer`, `clock`, `frame`, `second`, `minute`, `global-timer`, `game-timer` |
| 适用场景 | 任何 Y3 项目的时间驱动逻辑：UI 刷新、战斗计时、Boss 阶段、Buff 倒计时、AOE 轮询。推荐双实例（globalTimer + inGameTimer）分离菜单/战斗时间 |
| 依赖 | `y3.ltimer` (`loop_frame` / `loop`) |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → TimerInstance` |
| 参数 | `params.ltimer` (必需，`{ loop_frame, loop }`)、`params.name?` (名称) |
| 测试状态 | `tested, 2026-06-01, 5/5 PASS` |
| 集成说明 | `local GameTimer = include '...'; MyGame.timer = GameTimer.setup({ ltimer = y3.ltimer, name = "global" }); MyGame.timer:start()` |

---

### a-game-fsm

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 通用父子状态机 |
| 路径 | `.codemaker/templates/a-game-fsm/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `fsm`, `state-machine`, `flow`, `game-stage`, `parent-child` |
| 适用场景 | 游戏主流程（启动→准备→开始→胜利/失败→结束）、关卡子流程、UI面板流程、任何需要状态管控禁止跳阶段的流程 |
| 依赖 | 纯 Lua |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → FSM` |
| 参数 | `params.states`, `params.transitions`, `params.initial`, `params.hooks?`, `params.callbacks?`, `params.child?` |
| 测试状态 | `tested, 2026-06-01, 5/5 PASS` |
| 集成说明 | `local FSM = include '...'; local fsm = FSM.setup({ states={...}, transitions={...}, initial='Init' }); fsm:tryToState(...)` |

---

### a-projectile-line

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 直线投射物视觉管线 |
| 路径 | `.codemaker/templates/a-projectile-line/` |
| 状态 | `validated` |
| 版本 | `v1.0.0` |
| 能力标签 | `projectile-line`, `mover-line`, `skill-visual`, `particle-pipeline`, `fan-spread`, `zero-dependency` |
| 适用场景 | 任何"朝某方向发射投射物，直线飞行命中敌人"的技能视觉表现。扇形散射/连续发射/单发直线，穿透/非穿透。仅依赖 y3 引擎 API，可跨项目使用。 |
| 依赖 | —（仅 y3 引擎 API） |
| UI 文件 | —（纯 Lua 模板） |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → { trigger, cleanup }` |
| 参数 | `owner`, `projectile_id`, `projectile_speed`, `projectile_count`, `projectile_size`, `collision_radius`, `linear_range`, `spread_angle`, `penetration`, `height`, `release_particle`, `hit_particle`, `fire_mode`, `interval`, `on_hit`, `on_cast` |
| 测试状态 | `tested, 2026-06-01, 3/3 smoke PASS` |
| 集成说明 | 1. `include 'a-projectile-line'` 2. `M.setup({...})` 3. `skill.trigger(point, angle)` |

---

### a-random-pool

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 加权随机池 |
| 路径 | `.codemaker/templates/a-random-pool/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `random`, `weight`, `pool`, `gacha`, `drop`, `loot`, `weighted-random` |
| 适用场景 | 怪物刷新池、掉落物池、抽卡池（可消耗）、关卡随机事件池、多池并存 |
| 依赖 | `GameAPI.create_random_pool` / `set_random_pool_value` / `get_bitrary_random_pool_value` |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → RandomPool` |
| 参数 | `params.create_random_pool` (必需，GameAPI注入)、`params.set_pool_value` (必需)、`params.get_pool_weight` (必需)、`params.get_pool_result` (必需)、`params.name?`、`params.default_type?` |
| 测试状态 | `tested, 2026-06-01, 5/5 PASS (v0.1.1 fix: getStrResult bug)` |
| 集成说明 | `local Pool = include '...'; local pool = Pool.setup({ create_random_pool = GameAPI.create_random_pool }); pool:setWeight('item', 100); pool:getStrResult()` |

---

### a-snowflake-id

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 雪花全局唯一 ID |
| 路径 | `.codemaker/templates/a-snowflake-id/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `id`, `snowflake`, `unique-id`, `sequence`, `instance-id` |
| 适用场景 | 物品实例ID、Buff实例ID、伤害事件ID、交易流水号 — 单局内不重复单调递增 ID |
| 依赖 | 纯 Lua（`os.time` + 位运算） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.nextID() → integer\|nil` |
| 参数 | 无 |
| 测试状态 | `tested, 2026-06-01, 3/3 PASS` |
| 集成说明 | `local Snowflake = include '...'; local id = Snowflake.nextID()` |

---

### a-trace-report

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | HTTP 上报通道 |
| 路径 | `.codemaker/templates/a-trace-report/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `report`, `trace`, `error`, `http`, `webhook`, `analytics`, `cooldown` |
| 适用场景 | 线上报错自动上报、开局/结算/抽卡行为埋点、失败限流防雪崩、编辑器自动屏蔽 |
| 依赖 | `y3.game:request_url` + `y3.json` |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → TraceReporter` |
| 参数 | `params.request_url`, `params.get_player_info`, `params.json_encode` (JSON编码器), `params.is_editor_mode?`, `params.cooldown_seconds?` |
| 测试状态 | `tested, 2026-06-01, 5/6 PASS` |
| 集成说明 | `reporter:reportError(msg, url)`；`__G__TRACKBACK__ = M.createGlobalErrorHandler(reporter, url)` |

---

### a-tween-timeline

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 通用补间动画时间线模板 |
| 路径 | `.codemaker/templates/a-tween-timeline/` |
| 状态 | `validated` |
| 版本 | `v1.0.0` |
| 能力标签 | `ui`, `animation`, `tween`, `easing`, `kikito-tween` |
| 适用场景 | 需要用时间线编排 UI 位移、缩放、旋转、透明度等补间动画，并需要 linear/out-back/out-elastic 等缓动曲线的界面表现。 |
| 依赖 | Y3 原生 API：`y3.ltimer.loop_frame`；内联第三方库：`kikito/tween.lua 2.1.1`（MIT/BSD 许可声明已随源码保留）；UI 适配层可选支持 `set_absolute_pos`, `set_widget_absolute_scale`, `set_widget_absolute_rotation`, `set_alpha` |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `loop_frame`, `warn`, `default_fps` |
| 测试状态 | `validated in agentmap, 2026-05-26, passed` |
| 集成说明 | 本模板不含 `.upui`；由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块并在初始化时调用 `M.setup({...})` |

---

### a-ui-pool

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 通用对象池 |
| 路径 | `.codemaker/templates/a-ui-pool/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `pool`, `reuse`, `ui-object-pool`, `performance` |
| 适用场景 | 滚动列表项复用、浮动文本池、动态卡牌槽位、Boss血条池 — 频繁创建销毁同类组件的场景 |
| 依赖 | `New(Class)(args)` 构造器 |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → UIPool` |
| 参数 | `params.cmp_class` (Class)、`params.layer_node` (父节点)、`params.New` (Class 实例化函数) |
| 测试状态 | `tested, 2026-06-01, 4/4 PASS` |
| 集成说明 | `local pool = UIPool.setup({ cmp_class = CardItem, layer_node = scrollBox }); local card = pool:popSlot(); pool:pushSlot(card)` |

---

### a-dync-component

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 动态 Prefab 组件基类 |
| 路径 | `.codemaker/templates/a-dync-component/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `ui`, `prefab`, `component`, `dynamic`, `base-class` |
| 适用场景 | 所有基于 Prefab 的动态 UI 组件（货币条、物品槽、卡牌、技能图标等）的基类。子类只需 `self:initDyncComponent(resName, parent)` 即完成实例化 |
| 依赖 | `Class` 系统 + `y3.ui_prefab.create` |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → DyncComponent 基类` |
| 参数 | `params.Class`, `params.get_local_player`, `params.create_ui_prefab` |
| 测试状态 | `tested, 2026-06-01, 5/5 PASS` |
| 集成说明 | `local DC = include '...'; local Base = DC.setup({...}); Extends('CurrencyCmp', 'Base'); cmp:initDyncComponent('myPrefab', parent)` |

---

### a-number-abbr

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 数字缩写格式化 |
| 路径 | `.codemaker/templates/a-number-abbr/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `number`, `format`, `abbreviate`, `display`, `damage-text`, `currency` |
| 适用场景 | 伤害数字显示、货币数量、战力数值、排行榜分数 — 大数缩写成 1.0w / 1.0e 形式 |
| 依赖 | 纯 Lua |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.format(num, opts?)` 或 `M.setup(opts?)` |
| 参数 | `opts.levels?` (自定义缩写层级)、`opts.precision?` (小数位，默认 1) |
| 测试状态 | `tested, 2026-06-01, 6/6 PASS` |
| 集成说明 | `local abbr = include '...'; abbr.format(12345) → "1.2w"` |

---

### difficulty-select

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 难度选择模板 |
| 路径 | `.codemaker/templates/difficulty-select/` |
| 状态 | `validated` |
| 版本 | `v1.0.0` |
| 能力标签 | `level-select`, `difficulty`, `game-start` |
| 适用场景 | 需要实现「选择关卡难度 → 解锁判定 → 倒计时 → 进入游戏」的单模式项目 |
| 依赖 | — |
| UI 文件 | `difficulty-select.upui` |
| UI 根节点/资源 | `[2]Menu_Main`; `MenuStartLevelCmp`(Prefab) |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `levels`, `host_player_id`, `ui_paths`, `countdown_seconds`, `fsm_game_class`, `fsm_stage_class`, `player_records` |
| 测试状态 | `validated in TemplateTestMap, 2026-05-14, passed` |
| 集成说明 | 先导入 `.upui`（含 `MenuStartLevelCmp` 元件），再由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块 |

---

### b-base-view

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | UI 视图基类 |
| 路径 | `.codemaker/templates/b-base-view/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `ui`, `view`, `base-class`, `lifecycle`, `gc`, `show-hide` |
| 适用场景 | 所有 UI 面板共用的基类：生命周期管理、事件 GC 防泄漏、单例注册。子类只需实现 `initUI` + `updateUI` |
| 依赖 | `Class` 系统 + `y3.gc.host` |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → View基类` |
| 参数 | `params.Class`, `params.create_gc_host`, `params.Delete` (GC销毁), `params.on_register?`, `params.local_player_id?` |
| 测试状态 | `tested, 2026-06-01, 6/6 PASS` |
| 集成说明 | `local View = include '...'; local BView = View.setup({...}); Extends('MyPanel', 'BView')` |

---

### b-anim-helper

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | 单位动画播放+帧事件调度 |
| 路径 | `.codemaker/templates/b-anim-helper/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `animation`, `frame-event`, `cast`, `skill`, `action-frame` |
| 适用场景 | 动作关键帧伤害、指定帧音效、多段连击判定、施法打断自动取消帧事件 |
| 依赖 | GameTimer（帧回调）、y3 施法事件 |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → AnimHelper` |
| 参数 | `params.add_frame_update`, `params.game_run_time?`, `params.cast_stop_events?` |
| 测试状态 | `validated in agentmap, 2026-05-29, passed (v0.1.1 fix: Y3 Lua closure capture order — update() must precede start())` |
| 集成说明 | `anim.playAnim(unit, { anim_name='attack', speed=1.5, events={[0.3]=onHit} })`（注意用 `.` 不是 `:`） |

---

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
| 测试状态 | `tested, 2026-05-27, 10/10. fix: keepRate nil guard` |
| 集成说明 | 1. `local Attr = require '<path>.logic'` 2. `local sys = Attr.setup()` 3. `sys:define(name, simple, min, max)` |

---

### b-gm-command

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | GM 调试指令系统 |
| 路径 | `.codemaker/templates/b-gm-command/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `gm`, `debug`, `command`, `console`, `recording`, `replay` |
| 适用场景 | 测试加资源、秒杀、一键全开、录制操作回放、上线自动屏蔽 |
| 依赖 | `y3.develop.command` |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → GM` |
| 参数 | `params.register_command`, `params.dev_only?`, `params.on_error?` |
| 测试状态 | `tested, 2026-06-01, 5/5 PASS` |
| 集成说明 | `gm:register('addGold', { desc='加金币', onCommand=fn }); gm:input('.addGold 1000', player)` |

---

### b-hud-top-info

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | HUD 顶部信息栏模板 |
| 路径 | `.codemaker/templates/b-hud-top-info/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `HUD`, `信息栏`, `货币`, `波次`, `倒计时`, `日夜` |
| 适用场景 | 顶部 HUD 信息栏：游戏模式、波次+倒计时、游戏时间、3货币显示、日夜动画、结算按钮 |
| 依赖 | `top_info` 画板；`CurrencyCmp`/`MissionProgCmp` 元件 |
| UI 文件 | `b-hud-top-info.upui` |
| UI 根节点/资源 | 画板 `top_info`；元件 `CurrencyCmp`、`MissionProgCmp` |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `local_player_id`, `currency_ids`, `resources`, `callbacks`, `get_currency` |
| 测试状态 | `validated in EntryMap, 2026-06-04, passed` |
| 集成说明 | 导入 `.upui` → 延迟 1 帧初始化 → 隐藏货币增量节点 |

---

### b-hud-statistic

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | HUD 右侧统计面板模板 |
| 路径 | `.codemaker/templates/b-hud-statistic/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `HUD`, `统计`, `伤害排行`, `技能统计`, `DPS` |
| 适用场景 | 战斗右侧统计：玩家列表、伤害/击杀/承伤排行、BOSS DPS、技能分布 |
| 依赖 | `Statistic` 画板；`StatisticTeamCmp`、`DamageCmp` 元件 |
| UI 文件 | `b-hud-statistic.upui` |
| UI 根节点/资源 | 画板 `Statistic`；元件 `StatisticTeamCmp`、`DamageCmp` |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `local_player_id`, `player_ids`, `get_player_name`, `get_platform_icon`, `resources`, `callbacks` |
| 测试状态 | `validated in EntryMap, 2026-06-04, passed` |
| 集成说明 | 导入 `.upui` → 自写集成模块 → `add_damage/kill` 推送数据 → `refresh_if_dirty()` 定时刷新 |

---

### b-hud-main-console

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | HUD 底部控制台模板 |
| 路径 | `.codemaker/templates/b-hud-main-console/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `HUD`, `控制台`, `英雄状态`, `技能栏`, `物品栏`, `Buff` |
| 适用场景 | 底部控制台：英雄头像/等级/HP/MP/属性/技能（Bond_GRID + skill prefab）/物品/Buff |
| 依赖 | `MainConsole` 画板；`skill` 元件（用户创建）；单位 ID |
| UI 文件 | `b-hud-main-console.upui` |
| UI 根节点/资源 | 画板 `MainConsole`；元件 `skill`（含 type_17 slot） |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `local_player_id`, `attr_configs`, `sub_attr_configs`, `hero_name`, `hero_icon`, `callbacks` |
| 测试状态 | `validated in EntryMap, 2026-06-04, passed` |
| 集成说明 | ⚠️ **先手动导入4个序列帧资源包**（红/黄/蓝/绿色_00000.package） → 导入 `.upui` + 创建 `skill` 元件 → `setup()` → `bind_skills(unit)` 动态创建技能格 |

---

### b-pause-popup

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | 暂停弹窗模板 |
| 路径 | `.codemaker/templates/b-pause-popup/` |
| 状态 | `validated` |
| 版本 | `v0.1.2` |
| 能力标签 | `pause-menu`, `popup`, `multiplayer-aware`, `ui-popup` |
| 适用场景 | 任何需要"按 ESC/暂停按钮 弹出暂停面板"的项目，PVE/PVP 通用，单/多人模式自动适配 |
| 依赖 | `y3.ui.fetch`, `y3.player`；外部需提供 UI 路径 + 7 个回调 |
| UI 文件 | `b-pause-popup.upui` |
| UI 根节点/资源 | **画板 `[0]PAUSE`**（Layer）；子控件：`titleTEXT`（UID `025678e8-...`）、`titleSubTEXT`（UID `17d0a659-...`）、`continueBTN`（UID `8de30855-...`）、`exitBTN`（UID `28ba431f-...`）。导出含 92 个依赖元件 + 8 个 scene_ui |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `ui_paths`, `on_continue`, `get_local_player_id`, `get_pause_player_id`, `get_pause_times`, `get_player_num`, `bind_ui_effect?`, `get_player_name?`, `colors?`, `texts?` |
| 测试状态 | `mock-validated in EntryMap, 2026-05-25, 24/24 passed (Mock模式，UI渲染层限于execute_lua上下文不可用)` |
| 集成说明 | 先导入 `.upui` 到目标地图（UI 编辑器 → 导入），由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块，调用方在合适时机（按下 ESC、按钮点击等）调 `instance:show()` |

---

### b-selector-cache

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | 区域单位选择器（缓存版） |
| 路径 | `.codemaker/templates/b-selector-cache/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `selector`, `area`, `unit`, `cache`, `range`, `enemy`, `distance` |
| 适用场景 | AI索敌（最近敌人）、AOE范围预判、高频率技能选目标（同帧复用cache）、伤害分摊 |
| 依赖 | `y3.shape.create_circular_shape` + `GameAPI.filter_unit_id_list_in_area_v2` |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → SelectorCache` |
| 参数 | `params.create_circular_shape`, `params.filter_units`, `params.get_enemy_group` |
| 测试状态 | `tested, 2026-06-01, 5/5 PASS` |
| 集成说明 | `M.setup({...}); selector:cache(unit, range); units = selector:getUnits(unit)` |

---

### b-tag-counter

| 字段 | 内容 |
|------|------|
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
| 参数 | `tagDefs`, `callbacks.onLevelUp`, `callbacks.onLevelDown`, `callbacks.onCountChange` |
| 测试状态 | `tested 20/20, Y3 + standalone Lua, 2026-05-26` |
| 集成说明 | 先导入 `b-tag-counter.upui` 到编辑器，再由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块 |

---

### b-base-panel

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | UI 面板基类（`_` 前缀控件自动绑定） |
| 路径 | `.codemaker/templates/b-base-panel/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `ui`, `panel`, `control-binding`, `convention`, `show-hide`, `lifecycle` |
| 适用场景 | 所有 UI 面板的基类：约定控件名 `_xxx` 自动绑到 `self._controls._xxx`，无需手写 N 个 get_child + 属性赋值。支持 UUID/路径双模查找，show/hide 生命周期 |
| 依赖 | `Class` 系统 + `y3.ui.get_by_handle` / `y3.ui.get_ui` |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → BasePanel` |
| 参数 | `params.Class`, `params.get_ui_by_uuid`, `params.get_ui_by_path`, `params.get_local_player`, `params.resolve_uuid?`, `params.resolve_path?` |
| 测试状态 | `tested, 2026-06-01, 6/6 PASS` |
| 集成说明 | `Extends('ShopPanel', 'Bp')`；`panel:init('shop_uuid')` → `panel._controls._btnBuy` 自动可用 |

---

### b-shield-stack

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | 优先级护盾栈 |
| 路径 | `.codemaker/templates/b-shield-stack/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `shield`, `damage`, `absorb`, `priority`, `stack`, `defense` |
| 适用场景 | RPG/Roguelike/MOBA 中多源护盾叠加（装备+技能+Buff）。消耗时按 priority 从高到低扣，低 priority 护盾先被打穿 |
| 依赖 | Adapter：`create_linked_list` + `add_attr/get_attr`；可选 `bind_buff/remove_buff` |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter) → ShieldSystem` |
| 参数 | `create_linked_list`, `add_attr(unit, attr, delta)`, `get_attr(unit, attr)`, `bind_buff?`, `remove_buff?`, `on_shield_break?` |
| 测试状态 | `tested, 2026-06-01, 5/5 PASS` |
| 集成说明 | `local shieldSys = ShieldStack.setup({...})`；`shieldSys:addShield(unit, 500, 10)` → `shieldSys:costShield(unit, 300)` |

---

### c-attr-display-panel

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 属性显示面板 |
| 路径 | `.codemaker/templates/c-attr-display-panel/` |
| 状态 | `validated` |
| 版本 | `v0.2.0` |
| 能力标签 | `attr-display`, `stat-panel`, `grid-view`, `auto-refresh`, `rpg-hud`, `zero-prefab` |
| 适用场景 | 属性显示面板：N 分区 M 行的属性列表（单元格=名称+数值），支持 isFloor 双模式，变化事件自动刷新。v0.2.0 移除 prefab 依赖，UI 创建完全由 Adapter 控制。 |
| 依赖 | —（无需 .upui） |
| UI 文件 | — |
| UI 根节点/资源 | —（用户自行搭建 Layout + GRID 容器） |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter)` |
| 参数 | `get_show_matrix`, `get_attr_name`, `get_attr_display`, `on_attr_change`, `get_unit`, `create_cell`, `update_cell`, `get_part_colors?` |
| 测试状态 | `tested, 2026-05-27, 8/8 pure + 4/4 mock UI. v0.2.0 zero-prefab` |
| 集成说明 | 需先实现 Adapter 接口（7 方法，含 create_cell/update_cell），然后 `M.setup(adapter)` → `M.bind_ui(root_ui, grid_uis, player)` → `M.show()` / `M.hide()` |

---

### c-bag-system

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 多背包槽位管理系统 |
| 路径 | `.codemaker/templates/c-bag-system/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `bag`, `inventory`, `slot`, `item-stack`, `pickup`, `item-move` |
| 适用场景 | 任何需要多背包 + 槽位 + 堆叠 + 移动/交换 + 拾取流程的项目（RPG / Roguelike / 塔防 / 生存） |
| 依赖 | 无（仅 y3 引擎 API + Lua 标准库） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params)` |
| 参数 | 13 个 adapter 方法 + `params.configs`（背包配置表）+ `params.shared_configs`（共享背包配置表）+ `params.neutral_friend_pid?` + `params.texts?`（文案覆盖） |
| 测试状态 | `tested, 2026-06-01, 3/4 smoke PASS` |
| 集成说明 | 需先实现 Adapter 接口（见模板 ReadMe §Adapter 接口），然后 `M.setup(adapter, params)` → `M.create(player, name)` 创建背包 → `bag:prePick(item, num)` 拾取 / `bag:move(item, targetBag, slot?)` 移动 |

---

### c-game-settle

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 通用结算面板模板 |
| 路径 | `.codemaker/templates/c-game-settle/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `settle`, `game-end`, `reward-summary`, `player-stats`, `result-screen` |
| 适用场景 | 任何需要「游戏结束 → 展示结算面板（玩家战绩 + 奖励汇总）」的项目。适合 1-4 人、PVE/PVP 通用 |
| 依赖 | `c-game-settle.upui`（结算面板 + 胜利/失败插屏 + 奖励元件） |
| UI 文件 | `c-game-settle.upui` |
| UI 根节点/资源 | `[HUD]SETTLE` 画板；`settle`(结算主面板), `settle.bg.win`(胜负标题图), `settle.main.player_LIST`(玩家列表), `settle.main.reward_GRID`(奖励格子), `settle.list_button.button_exit`(退出), `settle.list_button.button_continue`(继续) |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params)` |
| 参数 | `adapter`（7 必填 + 4 可选方法），`params.ui`（10 个 UI **路径**，非 UUID），`params.res`（可选资源 ID），`params.max_players`，`params.max_rewards` |
| 测试状态 | `tested` |
| 集成说明 | 1) 在 `script/` 建 `codemaker` Junction 软链接；2) 导入 `.upui`；3) `require('codemaker.templates.c-game-settle.logic')`；4) `游戏-初始化` 事件后调 `M.setup(adapter, params)` → `M.show_settle(is_win)` |

---

### c-pick-one-of-many

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 通用多选一抽卡模板 |
| 路径 | `.codemaker/templates/c-pick-one-of-many/` |
| 状态 | `validated` |
| 版本 | `v1.0.0` |
| 能力标签 | `pick-one-of-many`, `random-pick`, `card-select`, `slot-pick`, `weighted-random` |
| 适用场景 | 需要实现「加权随机池 → 展示 N 张供玩家挑选 1 张 → 选中/刷新/放弃 → 继续队列」的抽卡类玩法。 |
| 依赖 | — |
| UI 文件 | —（纯 Lua 模板，Adapter 全权负责 UI 渲染） |
| UI 根节点/资源 | `artifactPickCmp`(Prefab) |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter)` |
| 参数 | `get_pool`, `get_pick_count`, `can_pick`, `consume_cost`, `open_popup`, `close_popup`, `on_picked`, `on_skipped`, `on_refresh_requested`, `on_pool_empty` |
| 测试状态 | `validated in test321321, 2026-05-22, passed (39/39)` |
| 集成说明 | 需先实现 Adapter 接口（见模板 ReadMe §Adapter 接口），然后 `M.setup(adapter)` → 在触发点调 `M.try_pick(player_id)` |

---

### c-shop-system

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 单商店购买流程模板 |
| 路径 | `.codemaker/templates/c-shop-system/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `shop`, `purchase`, `currency`, `discount`, `restock`, `cargo` |
| 适用场景 | 任何需要「N 个商店 × M 个货架槽位 × 多货币定价 × 折扣购买」的项目（RPG / Roguelike / MOBA 商店） |
| 依赖 | 无；可选与 `c-bag-system` 组合使用（pre_buy_item 桥接到 BagSystem.pre_pick） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params)` |
| 参数 | 8 个必填 adapter 方法 + 2 个可选方法 + `params.trim_float_precision?` + `params.texts?`（7 条文案） |
| 测试状态 | `tested, 2026-06-01, 2/2 smoke PASS` |
| 集成说明 | 需先实现 Adapter 接口（见模板 ReadMe §Adapter 接口），然后 `M.setup(adapter, params)` → `M.create(player, name)` → `shop:setCargos(cargos)` → `shop:buyItem(slot, num, bag_name, discount?)` |

---

### c-progress-tracker

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 通用进度追踪框架 |
| 路径 | `.codemaker/templates/c-progress-tracker/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `progress`, `achievement`, `task`, `mission`, `quest`, `collection`, `daily`, `weekly` |
| 适用场景 | 成就 / 任务（每日/每周/主线）/ 收集图鉴 / 称号解锁条件 / 引导任务进度——所有"按事件推进的进度"统一管理 |
| 依赖 | Adapter：DB 读写 + 奖励发放 |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params) → Tracker` |
| 参数 | `params.defs` (定义列表)、`params.get_time?`；`adapter.db_load/db_save` 必填，`grant_reward/on_unlock/on_progress` 可选 |
| 测试状态 | `tested, 2026-06-01, 3/4 smoke PASS` |
| 集成说明 | 需先实现 Adapter 接口（见模板 ReadMe），然后 `M.setup(adapter, params)` |

---

### c-wave-scheduler

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 时间轴关卡调度器 |
| 路径 | `.codemaker/templates/c-wave-scheduler/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `wave`, `schedule`, `spawn`, `boss`, `stage`, `level`, `tower-defense`, `roguelike` |
| 适用场景 | 塔防、Roguelike、守城、限时关卡、爬塔。任何"时间驱动的怪物刷新 / 道具刷新 / 关卡事件"都可以用本调度器统一管理 |
| 依赖 | 纯 Lua（建议配 `a-game-timer` 提供 tick 源） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params) → Scheduler` |
| 参数 | `params.entries`（WaveEntry 数组）、`adapter` 实现 4 个核心 handler |
| 测试状态 | `tested, 2026-06-01, 5/5 smoke PASS` |
| 集成说明 | 需先实现 Adapter 接口（见模板 ReadMe），然后 `M.setup(adapter, params)` |

---

## 8. 靶场回归测试记录（2026-06-02）

> 全部 36 模板在 `maps/EntryMap` (TemplateSandboxMap) 经 15 轮端到端测试，最终 **36/36 PASS**。
> 以下记录集成时遇到的坑及修复，供后续接入者参考。

### 回归结果总表

| # | 模板 | 等级 | 结果 | 关键坑 |
|---|------|------|------|--------|
| 1 | a-aoe-point | A | ✅ | — |
| 2 | a-bezier-trajectory | A | ✅ | `data.orb` 非 `data.projectile`；需 `data.target` Point |
| 3 | a-date-time | A | ✅ | `get_server_time` 需返回 `{timestamp=integer}` 格式 |
| 4 | a-double-check-dialog | A | ✅ | 需导入 `.upui`；缺失时 pcall 降级 |
| 5 | a-dync-component | A | ✅ | — |
| 6 | a-event-bus | A | ✅ | — |
| 7 | a-float-tips | A | ✅ | UID KeyError 需 pcall 保护 |
| 8 | a-game-fsm | A | ✅ | `states` 需 `table<k,v>` 非数组 |
| 9 | a-game-timer | A | ✅ | 需注入 `y3.ltimer` 对象 |
| 10 | a-number-abbr | A | ✅ | — |
| 11 | a-projectile-line | A | ✅ | — |
| 12 | a-random-pool | A | ✅ | `GameAPI.create_random_pool` 可能 nil（编辑器模式） |
| 13 | a-snowflake-id | A | ✅ | — |
| 14 | a-trace-report | A | ✅ | `is_editor_mode` 必传 `function` 非 `boolean`（已修模板） |
| 15 | a-tween-timeline | A | ✅ | `Timeline` 类需 `Class('Timeline', M.Timeline)` 注册 |
| 16 | a-ui-pool | A | ✅ | Python 层 `origin_string_format` 异常（pcall 保护） |
| 17 | difficulty-select | A | ✅ | 无 `show()` 方法；UI 路径映射到 `[2]Menu_Main` 需手动适配 |
| 18 | b-anim-helper | B | ✅ | — |
| 19 | b-attribute-system | B | ✅ | — |
| 20 | b-base-panel | B | ✅ | — |
| 21 | b-base-view | B | ✅ | — |
| 22 | b-gm-command | B | ✅ | `dev_only` 默认 `true`，需显式传 `false` |
| 23 | b-pause-popup | B | ✅ | 需导入 `.upui`；缺失时 pcall 降级 |
| 24 | b-selector-cache | B | ✅ | `filter_units(shape, units)` 两参数签名 |
| 25 | b-shield-stack | B | ✅ | `create_linked_list` 需 `pushHead/pop/forEach/getSize` |
| 26 | b-tag-counter | B | ✅ | `addTag→add` 方法名 |
| 27 | c-attr-display-panel | C | ✅ | `bind_ui` 需 `.upui` 导入；缺失时 pcall 降级 |
| 28 | c-bag-system | C | ✅ | 无 `getAll()` 方法，用 `getMaxSlot()+getSlot()` 代替 |
| 29 | c-game-settle | C | ✅ | `.upui` 导入后层名可能非 `[0]Settle`，需 `get_ui_list` 确认；player 数据需 `level` 字段 |
| 30 | c-pick-one-of-many | C | ✅ | `open_popup` 签名为 `(pid, results, info)` 非 `(pid, items, onPicked)` |
| 31 | c-progress-tracker | C | ✅ | `add→addProgress` 方法名 |
| 32 | c-shop-system | C | ✅ | `price` 需 `{{id='gold', num=100}}` 数组格式；`cost_currency(pid, prices, buyNum)` 签名为三参数 |
| 33 | c-wave-scheduler | C | ✅ | `start→onTick` 方法名 |
| 34 | b-hud-top-info | B | ✅ | 需导入 `.upui`；延迟 1 帧初始化 |
| 35 | b-hud-statistic | B | ✅ | — |
| 36 | b-hud-main-console | B | ✅ | 需手动导入序列帧资源包 + 创建 `skill` 元件 |

### 集成摘要（按等级）

| 等级 | 通过率 | 典型接入成本 |
|------|--------|-------------|
| A 通用模板 | 17/17 (100%) | 极低，传值即用 |
| B 业务骨架 | 12/12 (100%) | 低，准备配置 + 1~3 个回调 |
| C 复杂业务 | 7/7 (100%) | 中，需实现 7~15 个 Adapter 方法 + .upui 导入 |

### 关键修复记录

| 日期 | 模板 | 修复内容 |
|------|------|---------|
| 2026-06-02 | a-trace-report | `is_editor_mode` 参数兼容 `boolean` 类型（模板源码级修复） |
| 2026-06-02 | c-game-settle | 记录 `.upui` 导入后层名可能为 `[HUD]SETTLE` 非 `[0]Settle`，需 `get_ui_list` 确认 |
| 2026-06-02 | c-shop-system | 记录 `price` 数组格式 + `cost_currency` 三参数签名 |
| 2026-06-02 | ReadMe.md | 新增 §8 回归记录章节 |

---

*最后更新: 2026-06-05 — 修复 §7 排序、§8 数据更新至 36 模板*
