---
name: eca-json-builder
description: >
  Y3 ECA JSON 拼接技能：在 Y3 编辑器中生成可见可编辑的正式 ECA 函数、
  全局触发器实例、物编触发器（单位/技能），以及读取插件函数库、ECA 数据表、
  项目自定义事件、存档数据。

  Use this skill when user mentions: ECA 函数、生成函数、ECA 触发器、生成触发器、
  全局触发器、物编触发器、trigger JSON、ECA 变量、读取插件触发器、ECA 数据表、
  项目自定义事件、存档读取。

  内部脚本技能，零依赖（Python 3 标准库 + 内建 eca_index.json）。
---

# ECA 函数与触发器 JSON 拼接技能

> 📍 **本技能是 `y3-eca-pipeline` 的内部实现**（对应 `y3-ui-pipeline` → `y3-ui-generator` 的分工）：
> 面向 ECA 需求的流程编排、加载时序、对账清单与交付报告都在 `y3-eca-pipeline`，
> 本技能只管生成器脚本、DSL 字段、参数类型与写法守卫。

> 📘 **完整文档见同目录 `eca-json-builder.md`**（841+ 行：结构定义 / Arg 类型 / sub_type 速查 / 变量系统 / 完整示例 / 物编触发器格式 / 工作流 / 参考代码索引 / 插件数据 / 数据表 / 项目事件 / 存档）。

## 概述

在 Y3 编辑器中生成**可见可编辑的正式 ECA 函数和全局触发器实例**。

> 不是 ECA 类型注册（那是 `custom_eca/custom_eca.json` 的职责），也不是 AI/NLP 映射修正（那是 `ExternalResource/readable_eca/*.json`）。

## 脚本清单

均在技能同目录 `<agent>/skills/eca-json-builder/` 下，零依赖。

| 脚本 | 用途 |
|------|------|
| `eca_json_helper.py` | 触发器生成与校验（`template`/`validate`/`merge`/`normalize-desc`/**`scan`**/**`diff`**） |
| `lookup.py` | 基于内建 `eca_index.json` 查找 ECA（`--global-events` / `<eca_name>`） |
| `gen_function.py` | 从 DSL 生成项目 ECA 函数并更新 `global_trigger/function/index.txt` |
| `gen_trigger.py` | 生成全局触发器（支持 `--dry-run` 校验、自动 var_data） |
| `read_trigger.py` / `edit_trigger.py` | 读取 / 编辑现有触发器 |
| `var_manager.py` | 全局/局部/物编组变量增删改查（`list`/`add`/`remove`/`show`） |
| `plugin_eca.py` | 插件函数库与触发器数据（`list`/`read`/`dsl`） |
| `table_reader.py` | ECA 数据表读取（`list`/`read`/`find`） |
| `project_event.py` | 项目自定义事件（`list`/`read`） |
| `archive_reader.py` | 存档系统读取（`list`/`read`） |
| `verify_trigger.py` | **一条命令跑完写法验证闭环**：lint → `import_eca` → 保存×2 → 回读 diff → valid（`--all` 批量回归） |
| `audit_triggers.py` | **静态审计第四关**（`validate`/`scan`/`diff` 之后的补刀）：ID 唯一性 / `valid` / 子触发器是否被裸整数注册 / 变量引用是否声明 / 变量 tuple 是否写成 3 元组。`--map-dir maps/<地图>` |
| `probe.py` | **探针法一条命令问编辑器**：一次造多个候选写法触发器 → 导入 → 保存 → 回读 → 输出「可用 / 作废」判定与被清空的字段路径。定位「某类型该写什么 sub_type」时用它，别手工串四轮 |
| `sync_from_source.py` | **从编辑器源码派生参数类型数据**（arg_type ID / sub_type 表 / 变量读取 sub_type / 各类 flags），产出 `eca_source_data.json` |
| `harvest_from_project.py` | **用手头工程自我校验/补全**参数类型数据（不需要源码）：`--project .`，可 `--repair` 就地修正唯一可判定的冲突项 |
| `mcp_client.py` | 极简 MCP(HTTP) 客户端 + 端口解析（供 `verify_trigger.py` 等脚本直连本地 MCP） |

```bash
py -3 <agent>\skills\eca-json-builder\eca_json_helper.py template trigger_instance
py -3 <agent>\skills\eca-json-builder\eca_json_helper.py template function_instance
py -3 <agent>\skills\eca-json-builder\lookup.py <eca_name>
py -3 <agent>\skills\eca-json-builder\gen_function.py --dry-run <函数DSL.json>
py -3 <agent>\skills\eca-json-builder\gen_trigger.py --dry-run ...
py -3 <agent>\skills\eca-json-builder\probe.py <探针DSL.json> --keep   # 定位「哪种写法能活下来」
```

## 📕 运行时陷阱（编辑器接受 ≠ 运行时生效）

**`validate` / `scan` / `diff` / lint 只能证明「写法被编辑器接受」，证明不了「运行时真的执行」。**
已收集的静默失效写法（UI 事件两条通道、群体命令无效、`ET_UNIT_DIE` 时序、探测器使用姿势、
会话/环境前置、`save_editor` 裁剪变量…）全部在
**[`runtime_pitfalls.md`](./runtime_pitfalls.md)**，包含每一步的取证方法与反例。

> 交付任何「实现完成」之前，请至少做一次 **状态探针**（往全局变量写哨兵值再看运行时读回），
> 确认触发器真的跑了 —— 只跑四种静态校验就下结论是最容易犯的错。

## 🕐 三种改动 → 三种时序（别过度重启）

| 只改了什么 | 需要 `restart_editor` 吗 | 时序 |
|-----------|------------------------|------|
| **只改触发器**（不含函数 / 变量 / 逻辑节点） | **不需要** | `save_editor` → 改文件 → 串行 `import_eca` → 等 3 秒 → `save_editor` → `diff` |
| **改了全局变量 / 逻辑节点** | **必须** | `save_editor` → `var_manager.py add`（或改 `logicres.json`）→ ⛔不再保存 → `restart_editor(save_before_restart=false)` → 串行 `import_eca` → 等 3 秒 → `save_editor` |
| **改了 ECA 函数** | **必须**，且顺序不可换 | 同上，其中"不保存重启"专为函数表设计 |

> 每次多走一轮 `restart_editor` 约 1.5~2 分钟（`save_before_restart=false` 之后还要补一次
> `save_before_restart=true` 恢复会话，否则 `y3helper` 启动游戏会卡 loading）。
> 只改触发器时别顺手重启，那是纯浪费。

## 生成后加载到编辑器

### ⚠️ 批量导入 / 删除 / 时序的三个坑

| 坑 | 现象 | 正确做法 |
|----|------|---------|
| **保存会「裁剪」未导入的触发器** | `save_editor` 以**编辑器内存**为准写回：磁盘上存在但没 `import_eca` 过的触发器文件会被**删除**，`index.txt` 条目也会被移除 | 批量新增时：先 `save_editor` 落盘编辑器当前修改 → 再生成文件 → **逐个 import 完再统一保存**（中途不要保存） |
| 保存后立刻导入会被丢弃 | `import_eca` 返回的不是 JSON（`payload=None`），触发器没进编辑器，随后保存时被裁剪 | 保存后等 1~3 秒再导入；`verify_trigger.import_trigger()` 已内置该等待并把「未返回 success」直接报错 |
| **删除触发器要连编辑器内存一起清** | 只删磁盘文件 + index 时，编辑器下次保存会把它**原样恢复**（俗称"复活"，含 index 条目） | 真删除：`edit_trigger.py --delete` 之后再 `restart_editor(save_before_restart=false)` 让编辑器忘掉它 |

### ✅ 生成期硬校验（报错即说明写法会被编辑器破坏）

`gen_trigger.py` 生成时会读工程数据做前置校验，命中即**直接报错/告警**，不必等编辑器回读：

| 校验 | 依据 | 行为 |
|------|------|------|
| 引用未声明的全局变量 | `maps/<地图>/globaltriggervariable.json` | **报错**（编辑器会标红「无效的变量」） |
| 全局变量类型与引用不一致 | 同上 | **告警**并按声明类型改写 |
| 全局 `UNIT_NAME` 变量的读取 | 实测 260616 会被清成 null | **告警** |
| `IF_THEN_ELSE` 嵌在 ELSE 分支 | 实测保存时被整体丢弃 | **报错** |
| `ITER_UI_COMP_DO` 目标控件无子节点 | 画板 JSON（`maps/<地图>/ui/*.json`）的 children 数 | **报错**（遍历为空，事件注册不上） |
| 上下文参数类型（`UNIT_TYPE_COMPARE` 字面量 / `MATH_OPERATION` 运算符等） | `PARAM_TYPE_OVERRIDE` 表，每条附证据 | 自动用正确 `arg_type` |
| **物编事件触发器里用了 `TRIGGER_PLAYER`** | 实测 09-22：`GENERIC_UNIT_EVENT`(t_unit) 的两条触发器持续 `valid=false`，**参数却完好无损** | **报错**，提示改用 `OWNER_PLAYER(<单位>)` |
| **位置参数个数超过该动作声明的 `p`** | 实测 09-23：`STR_JOIN` 传 3 个位置参数，编辑器保存后只剩 2 个（静默丢弃） | **报错**，提示把第 3 段起改写进 `op_arg` |
| **参数类型未登记在 `ARG_TYPE_ID`** | 写错 `arg_type` 会被清成 `null` 或让 `valid=false` | **报错**（不再静默退化成 100004/POINT），并给出取证步骤 |

### 🔑 参数类型数据：从源码派生（强烈推荐）

#### 📦 分发形态：维护者用源码派生，**使用者不需要源码**

| 角色 | 需要编辑器源码？ | 用什么 |
|------|----------------|--------|
| **维护者**（更新本 skill 时） | 是 | `sync_from_source.py --src <engine>` 派生一次，把 `eca_source_data.json` **随 skill 打包分发** |
| **使用者**（普通用户） | **否** | 只读随包的 `eca_source_data.json`；文件缺失时退回内置手写表并打印提示 |

三个设计保证，让「没有源码」也安全可用：

1. **数据是静态资产**，不是运行时构建步骤 —— 使用者侧零源码依赖。
2. **缺失可降级**：没有 `eca_source_data.json` 时退回内置表（已按源码校正过取值），
   未覆盖的类型会**直接报错**并给出取证步骤，不会静默生成损坏节点。
3. **使用者可自校验（不需要源码）**：

```bash
# 用「自己工程里编辑器写出的触发器」反查 (arg_type, sub_type)，与分发数据比对
py -3 <agent>\skills\eca-json-builder\harvest_from_project.py --project .
py -3 <agent>\skills\eca-json-builder\harvest_from_project.py --project . --repair   # 就地修正能唯一定位的冲突项
```

   它会报告：✅ 一致 / ❌ 与分发数据冲突 / ➖ 多候选无法判定 / ➖ 表里未声明（多为运行时动态注册的 `*_KV`）。
   这是**版本错位最早、最便宜的发现点**：若你的引擎构建与分发数据不一致，这里会直接暴露。

4. **分发数据已脱敏**：产物里**不含**引擎源码根路径，也不含源码文件清单
   （绝对路径 + 引擎目录结构属信息泄漏），只保留 `sha256` 与各项计数。
   维护者本地排查可加 `--include-source-paths`，但**带路径的产物禁止提交/分发**；
   `tests/test_generator_guards.py::test_shipped_source_data_leaks_no_paths` 会守住这条线。

> 维护者换引擎后的标准流程：`sync_from_source.py` 重跑 → `harvest_from_project.py` 自检 →
> `verify_trigger.py` 抽验一条触发器（`valid=true`）→ 提交。

`eca_index.json` 只记录参数类型的**名字**，没有 **arg_type ID**。ID 写错时编辑器不报错，
只在保存时把参数清成 `null`（如 `ROLE_RES_KEY`）或让触发器 `valid=false`（如 `WIN_OR_LOSE`）。
所以 ID 表必须**从源码派生**，不要靠猜：

```bash
py -3 <agent>\skills\eca-json-builder\sync_from_source.py --src <engine-src>              # 派生并写入产物
py -3 <agent>\skills\eca-json-builder\sync_from_source.py --src <engine-src> --dry-run    # 只看覆盖报告
```

`--src` **无默认值**（必填）：本脚本会随 skill 分发，不能把维护者本机的源码路径写死在里面。

产出 `eca_source_data.json`（含源码 sha256 指纹）。派生内容与源码对应关系：

| 产出 | 源码依据 |
|------|---------|
| `arg_type_ids`（类型名 → ID） | `eca/GameTriggerArg.py` 的 `GameTriggerArgType`：`X = reg_arg('X', const_name.Y, ...)` → ID 取 `const_name.Y`；另有 `X = const_name.Y` 直接别名 |
| `arg_types[*].sub_types`（合法 sub_type 表） | `args/*.py` 的 `@register_trigger_arg_sub_type(...)` 类体 |
| `arg_types[*].op_arg_defaults`（可选参数默认值） | 各 arg 类的 `get_op_arg(i, EAExprConst(value=v, ...))` |
| `variable_subtype`（变量读取 sub_type） | 各类型自己声明的 `VARIABLE = <值>` |
| `categories`（能否作全局/局部变量、KV、可比较） | `reg_arg` 的 `is_global_var` / `is_local_var` / `is_kv_value` / `can_compare` |

合并优先级：**源码派生 > 手写 `_HAND_ARG_TYPE_ID`**。手写表已退化为「源码未覆盖类型的兜底」；
两者不一致时会打警告（首轮实测 29 项冲突，绝大多数是手写值错，例：`WIN_OR_LOSE`
手写 100003(STring) 实际 100047、`ITEM_ENTITY` 手写 100021 实际 100031）。

> ⚠️ **版本一致性**：派生表必须与当前编辑器/引擎构建匹配。换引擎后重跑本脚本，
> 并用 `verify_trigger.py` 抽验至少一条触发器（`valid=true`）再提交。输出无时间戳，可 diff 审查。

**已知能力解锁**（此前因缺 ID 而放弃）：

- `END_GAME_FOR_ROLE`：`WIN_OR_LOSE`=100047、`ON_OR_OFF`=100048，需**填满 6 个参数**
  （`PLAYER, WIN_OR_LOSE, ON_OR_OFF, BOOLEAN, INTEGER, BOOLEAN`），实测 `valid=true`；
  注意 **`TRIGGER_PLAYER` 不能用在 `INIT_FINISHED`（t_system）里**，换具体玩家即可
- `UNIT_COMMAND`=100216 / `UNIT_GROUP_COMMAND`=101001：主动下移动/攻击移动指令
  （`UNIT_RELEASE_COMMAND` / `API_RELEASE_UNIT_GROUP_COMMAND`）
- `MOVE_DIRECTION`=100332

> ⚠️ 派生出的 `sub_types` 表**天生不完整**：一部分 sub_type 由运行时动态注册
> （`args_utils.py` 里 `TriggerKv.register_has_kv_arg` 生成的 `*_KV` 系列），静态解析看不到。
> 因此 sub_type 校验只做**告警**，不阻断。

> 📌 `op_arg` 现在支持**字面量**（字符串/数字），例如 `["STR_JOIN","A","B",{"op_arg":["C","D"]}]`
> 会生成「2 个位置参数 + `op_arg[0..1]` 启用」。`STR_JOIN` 实际支持 2 + 8 = **最多 10 段**拼接，
> 不要为了拼多段去嵌套（能跑但绕远）。

> 🔓 **已取证但不想改共享表时的逃生通路**：`{"typed_id": <int>, "value": ...}`
> 例如 `["UNIT_RELEASE_COMMAND", <单位>, {"typed_id": 100xxx, "value": ["UNIT_COMMAND_ATTACK_MOVE", <点>]}]`。
> 它会强制指定 `arg_type` 并打一条告警；取证后请补登记到 `ARG_TYPE_ID` 并写明证据来源与日期。
>
> 背景数据：`eca_index.json` 里出现过 **311** 种参数类型名，
> `ARG_TYPE_ID` 只登记了 **71** 个，**228 个必填类型仍是缺口** —— 遇到缺口不要猜 id，
> 按上面的取证步骤做，或先用 `typed_id` 就地传入。

新增规则时必须把「证据来源 + 日期」写进 `PARAM_TYPE_OVERRIDE` / lint 的注释里，不要凭推理添加。
配套自检：

```bash
py -3 <agent>\skills\eca-json-builder\tests\test_generator_guards.py      # 生成期 + lint 规则回归（18 项）
py -3 <agent>\skills\eca-json-builder\verify_trigger.py --all             # 真实编辑器闭环回归
```

> ⚠️ **每次写完触发器，请用 `verify_trigger.py` 跑闭环，不要手工串 `import_eca` / `save_editor` / `diff`。**
> 它会把 `local_var`、`valid` 这类**正常归一化**排除掉（`_BENIGN`），并额外做两项检查：
> - 保存后 `valid` 是否为 `true`
> - **保存后引用的全局变量是否还在**（`save_editor` 以编辑器内存为准，未加载的新变量会被裁剪，
>   届时引用会被标红「无效的变量」；实测一次裁剪掉全部新变量）
>
> 手工跑 diff 会把 `local_var` 的噪音混进来，真实问题容易被淹没——这是踩过的坑。

函数和触发器必须按依赖顺序加载。当前地图已在编辑器中打开时，严格执行：

> ⚠️ **`import_eca` 只热更编辑器的「编辑态」，不影响运行时。** 运行时（游戏进程）只在**启动游戏**时读取编辑器当前状态；`hotfix_status=未连接（仅编辑器侧已更新）` 是**正常现象**，不代表加载失败。想让改动在游戏里生效，**必须重新启动游戏**（`y3helper.launch_game` / `start_game`）。因此「改动 → 重启游戏 → 查运行时状态」是唯一有效的验收闭环。

1. **生成前保存**：先调用一次 `y3editor.save_editor()`，保留用户当前编辑器修改。
2. **写入函数**：生成并校验全部 `global_trigger/function/*.json` 与 `function/index.txt`，核对索引数、文件数和稳定 `func_id`。
3. **禁止生成后保存**：函数写入后不得再调用 `save_editor`；旧编辑器内存会把新函数文件和索引覆盖掉。
4. **加载函数**：调用 `y3editor.restart_editor(save_before_restart=false)`，等待原地图重新打开，再确认函数文件和索引未被改写。当前 MCP 没有独立的 `open_map` 工具；若目标地图原本未打开，不得臆造调用，需通过编辑器已有入口打开目标地图后再核对函数文件和索引。
5. **加载普通触发器**：函数已进入编辑器内存后，对各个触发器文件按顺序串行调用：

```text
y3editor.import_eca(trigger_json_path="<global_trigger/trigger/*.json 的绝对路径>")
```

- `success=true` 表示编辑器已受理；同时记录返回的 `mode`、`trigger_id` 和 `hotfix_status`。
- `hotfix_status=已推送` 表示运行时也已更新；`未连接（仅编辑器侧已更新）` 仍算编辑器加载成功，但要运行完整测试需重新启动游戏。
- 当前 `import_eca` 只接受 `global_trigger/trigger/` 下的触发器，不能传入 `global_trigger/function/` 下的函数文件。
- 不得用路径跳转、临时复制等方式把函数伪装成触发器导入。函数加载阶段必须通过地图重新打开完成。
- **含 `sub_trigger` 的文件**：**当前编辑器版本 `import_eca` 可以正常导入**（实测 `新建` 与 `覆盖` 两种模式都不会丢子触发器与裸整数注册 ID，见下方「子触发器加载实测」）。导入后等 3 秒 `save_editor`，再用 `eca_json_helper.py diff <生成副本> <回读文件>` 确认 `sub_trigger` 与裸注册 ID 仍在。
  若在其它版本上出现「`success=true` 但保存后子触发器消失」，再退回 `restart_editor(save_before_restart=false)` 加载，并在重开后同样用 `diff` 校验；注意该重启会打脏编辑器会话，之后必须补一次默认的（先保存）重启。

## ⚠️ 关键陷阱

| 项 | 规则 |
|----|------|
| `event_type` | 必须用 `lookup.py` 验证的确切名称，不可自创 |
| 自定义事件 | DSL 可以写事件名称；最终 `CUS_EVENT` 必须由 `maps/<地图名>/customevent.json` 解析为整数 ID。名称缺失或重名时禁止生成 |
| 变量 tuple | **局部变量**：`["TYPE","name","local"]`（3 元组）；**全局变量**：`["TYPE","name"]`（**2 元组，没有 scope**）。全局写成 3 元组会被编辑器判为「无效的变量」 |
| `TABLE` 字面量 | 禁止把普通 JSON 对象/列表写成 `arg_type=100011, sub_type=1`；必须先用 `SET_VARIABLE + GET_NEW_TABLE` 创建局部 TABLE，再用 `SET_TABLE_VALUE_1D`/`INSERT_TABLE_VALUE` 填值，调用时传 `sub_type="VARIABLE"` 的 TABLE 变量 |
| 变量初值类型 | STRING→`""`、BOOLEAN→`false`、FLOAT/ANGLE→`0.0`、其余→`0`（写错类型编辑器崩溃） |
| 全局变量存放位置 | 必须在 **`maps/<地图名>/globaltriggervariable.json`**（编辑器读写的就是它，里面通常还有工程自带变量）。写 `project_trigger_var.json` 编辑器**不读**，引用会全部标红。用 `var_manager.py`（已修正路径） |
| 全局变量读取 sub_type | `INTEGER`→`6`、`STRING`/`FLOAT`/`ANGLE`→`2`、`UNIT_ENTITY`→`11`、`PLAYER`/`BOOLEAN`/`NEW_TIMER`/`TABLE`→`"VARIABLE"`。写错（例如 BOOLEAN 写 `2`）会被编辑器清成 `null` |
| 实体变量赋空 | `UNIT_ENTITY` 用 `NONE_UNIT`、`UNIT_GROUP` 用 `NONE_UNIT_GROUP`；直接写字面量 `0` 会被编辑器清成 `null`（生成器已自动改写） |
| 包装类事件参数 | `GENERIC_UNIT_EVENT` 的参数 `sub_type` 必须写成事件名本身：`{"arg_type":100008,"sub_type":"GENERIC_UNIT_EVENT","args_list":["ET_UNIT_DIE"]}`。写成整数 `1` 会被编辑器**保存时清成 `null`**，触发器静默失效 |
| `op_arg`/`op_arg_enable` | event/condition/action/build_arg 四类 builder 须补全可选参数字段 |
| `SET_VARIABLE` 值参数类型 | 值参数的 `arg_type` 必须与**目标变量类型**一致，否则保存时被清成 `null`（实测：`MATH_OPERATION` 写进 `INTEGER` 变量、arg_type 用了表达式自身的 `100000`，被清空）。生成器已按目标类型自动钉死 |
| 整数自增 | 用 **`MATH_OPERATION` + `ARITHMETIC_OPERATOR`(100016)**；写成 FLOAT 版的 `ARITHMETIC_OPERATION`(100017) 会被清成 `null` |
| `UNIT_TYPE_COMPARE` 字面量 | 字面量必须写 `arg_type=100116`(UNIT_NAME)，写 `100010` 不报错但触发器 `valid=false`。另：`GET_UNIT_TYPE` 取的是**分类**(`get_subtype()`)，要比物编 Key 请用 `GET_UNIT_KEY_OF_UNIT` + `UNIT_CLASS_COMPARE` |
| `IF` 不能嵌在 ELSE 里 | ELSE 分支的动作列表里放 `IF_THEN_ELSE`，编辑器保存时会**整体丢弃**；请平铺成同层级多个 IF（生成器已直接报错拦下） |
| `ITER_UI_COMP_DO` 语义 | 它遍历「该控件的**子节点**」；用在无子节点的按钮上会**一条事件都注册不上**。注册 UI 事件应把控件 uid 直接交给 `CREATE_UI_COMP_EVENT_EX_EX`（生成器已按画板 JSON 校验子节点数） |
| 全局 `UNIT_NAME` 变量 | **读取**会被编辑器清成 `null`（实测 260616）；改存 INTEGER 编号 + 字面量分支 |
| ECA 函数身份 | `func_id` 是调用契约；重新生成时必须稳定，调用节点按该 ID 关联 |
| 函数参数描述 | 每个参数都必须在 `func_des` 中以 `{参数名}` 占位符出现，并放在调用文本的语义位置；缺失时生成器直接报错 |
| Lua Bind 参数 | `Eval_Lua_TABLE` 最多提供 5 个参数槽，代码中使用 `args[1]` 到 `args[5]` |
| 函数返回值 | `func_return`、`func_rtv_name_list`、数值动作 `400342` 和局部返回变量必须一致 |

## 🧭 UI 事件（实测可用写法）

UI 交互必须用「**父触发器 + 子触发器**」结构，直接写成普通顶层触发器收不到事件：

```jsonc
// 父触发器：INIT_FINISHED，动作里注册子触发器（DSL: {"register_sub_trigger": "子触发器名"}）
// 同时用官方动作注册控件事件（DSL: ["CREATE_UI_COMP_EVENT_EX_EX", "<控件uid>", 2, "事件名"]）
{
  "name": "某界面-UI事件注册",
  "event": [["INIT_FINISHED"]],
  "action": [{"register_sub_trigger": "某控件点击"}],
  "sub_triggers": [
    {
      "name": "某控件点击",
      // 设计期具名事件：事件名写成**普通字符串字面量**
      // （不要用 ["STR_TO_UI_EVENT","名字"]：那条是运行时注册通道，ECA 收不到，见 runtime_pitfalls §1）
      "event": [["TRIGGER_COMPONENT_EVENT", "btn_click"]],
      "action": [["SET_VARIABLE", {"var": "点击次数", "type": "INTEGER", "scope": "global"}, 1]]
    }
  ]
}
```

要点：

1. `UI_COMP_EVENT_TYPE` 是**整数**（实测 `2` = 点击生效，`1` = 左键-按下，`24`/`25` = 鼠标移入/移出）。
2. 控件用 **uid 字符串**寻址：`{"arg_type":100070,"sub_type":1,"args_list":["<uid>"]}`。
3. UI 相关 arg_type（编辑器实测）：`UI_COMP`=100070、`UI_EVENT`=100067、`UI_COMP_EVENT_TYPE`=100072、`UI_COMP_ATTR`=1001555、`UNIT_ATTRIBUTES`=100041。
4. **含 `sub_trigger` 的文件同样用 `import_eca` 加载** —— 实测当前编辑器版本 `新建`/`覆盖` 都不会丢子触发器与裸整数注册 ID（见「子触发器加载实测」）。加载后等 3 秒 `save_editor`，再用 `diff` 校验。
   （仅在 import_eca 不可用、需要退回重启加载时注意：`save_before_restart=false` 会把编辑器的地图会话搞脏，之后 `y3helper` 启动游戏会卡在 loading 30%；此时必须再补一次**默认的 `restart_editor(save_before_restart=true)`** 恢复会话。）
5. **覆盖导入是「按 `trigger_id` 合并」，不是整文件替换** —— 这一点没有任何报错：文件里**新增**的子触发器（新 ID）会被**静默丢弃**，
   而父触发器 `action` 里还留着对它们的裸整数注册，审计才会报「子触发器未被父触发 action 注册」。
   **要新增子触发器，请放进一个新的父触发器文件（新 `trigger_id`），让 `import_eca` 走「新建」**；
   导入后务必回读比对 `sub_trigger` 的数量与 ID 集合，别只看 `success=true`。
6. **UI 用例不要用 `y3runtime.trigger_ui_touch_event_by_path` 验证** —— 它只能驱动 Lua 侧监听（`左键-按下/抬起/点击`）与 Lua 的「界面-消息」，**驱动不了 ECA 的 UI 事件处理器**，会得出「ECA 收不到 UI 事件」的错误结论。UI 交互请人工点击验证。
   （注：`y3.ui.get_ui(p, "画板.父层.控件"):send_event("事件名")` 可以驱动**设计期具名事件**的子触发器，可用来验证 ECA 侧链路；但它证明不了「真实鼠标点击/悬浮能触发」。）

## 🧪 子触发器加载实测

**结论：`import_eca` 可以导入含 `sub_trigger` 的文件。** 旧文档里「含 `sub_trigger` 禁止用 `import_eca`、必须重启加载」的说法，在当前编辑器版本**不成立**（不要因此多做两次编辑器重启）。

> ⚠️ **补充实测（覆盖场景的边界）**：`import_eca` 覆盖同名 `trigger_id` 时是**按 ID 合并**：
> 同 ID 的子触发器会被更新，**文件里新增的、编辑器内存里没有的子触发器 ID 会被直接丢掉**，而父触发器 `action`
> 里的裸整数注册仍然保留 —— 于是出现「注册了 10 个，实际只有 6 个」的静默失效，`import_eca` 依旧返回 `success=true`。
> 规避：新增子触发器时**换一个新的父触发器文件（新 `trigger_id`）**，走「新建」；或先 `edit_trigger.py --delete`
> 再 `restart_editor(save_before_restart=false)` 让它忘掉旧结构。导入后必须回读比对 `sub_trigger` 的 ID 集合。

受控实验：一个触发器文件内含 **2 个子触发器**（分别监听 `TRIGGER_COMPONENT_EVENT` 与 `GENERIC_UNIT_EVENT`）+ **2 个裸整数注册 ID**。

| 场景 | 操作 | 结果 |
|------|------|------|
| 新建 | `import_eca`（`mode=新建`）→ 等 3 秒 → `save_editor` | `diff 生成副本 vs 回读文件` = **OK**；`sub_trigger` 2 个、裸整数注册 2 个、`is_conf=true` / `enabled=false` / `p_trigger_id` 全部保留 |
| 覆盖 | 把子触发器动作值 1→2 后重新生成 → `import_eca`（`mode=覆盖`）→ `save_editor` | 同上，且**新值已落盘生效** |

因此标准流程就是：`scan` → `gen_trigger` → `import_eca`（逐个串行）→ 等 3 秒 → `save_editor` → `diff` 校验。
仅当 `diff` 报出「子触发器丢失」时，才退回 `restart_editor(save_before_restart=false)` 加载，并补一次 `save_before_restart=true` 恢复编辑器会话。

## ✅ 如何确认某节点写法被编辑器接受（强烈推荐）

编辑器对不认识的写法**不报错**，而是在 `save_editor` 时把该参数**静默清成 `null`**（`GENERIC_UNIT_EVENT`、全局变量读取、实体变量赋 0 都是这么翻车的）。因此：

```bash
# 0. 先扫一遍目录：索引是否一致、哪些文件含 sub_trigger、写法 lint
py -3 <agent>/skills/eca-json-builder/eca_json_helper.py scan maps/<地图>/global_trigger/trigger

# 1. 生成（先留一份生成结果副本，用于第 5 步比对）
py -3 <agent>/skills/eca-json-builder/gen_trigger.py dsl.json
cp maps/<地图>/global_trigger/trigger/X.json /tmp/X.generated.json

# 2. import_eca（含 sub_trigger 的文件同样走 import_eca）
# 3. 等待 3 秒
# 4. save_editor
# 5. 回读比对（忽略 element_id 与键序）：
py -3 <agent>/skills/eca-json-builder/eca_json_helper.py diff /tmp/X.generated.json \
      maps/<地图>/global_trigger/trigger/X.json
#    OK  = 写法被编辑器接受；列出差异 = 有节点被清成 null / 被改写，必须换写法
```

`import_eca` 只对单个文件有效，逐个串行调用即可（含子触发器的文件也一样）。

想确定「某类型变量的读取该写什么 sub_type」时，最快的办法是**构造探针触发器**：把几种候选写法各放一个条件里 → `import_eca` → `save_editor` → 回读，活下来的那个就是正确答案。

> 💡 **ECA 的 PRINT 打印能读，但不在 `get_logs` 这条通道里**（旧文档「看不到」的说法只对了一半）：
>
> | 通道 | 路径 | 内容 |
> |------|------|------|
> | **触发器日志** | `LocalData/trigger_log/<地图名>/Log/<玩家名>_<YYYY_MM_DD_HH_MM_SS>.log`（每局一个新文件） | `PRINT_MESSAGE_ACTION_TO_DIALOG`（`DIALOG_DEBUG_TYPE`：1=Error / 2=Warning / 3=Info）与 `y3.log.*` |
> | Lua 日志 | `maps/<地图>/script/.log/lua_player01_<玩家名>.log` | Lua `print`（带 `文件:行号`） |
> | 客户端日志 | `LocalData/LocalLog/Log_*.log` | 引擎底层日志；`y3helper.get_logs` 读的是这一条 |
>
> 也就是说：**打印是有效的调试手段**，只是 `get_logs` 看不到它 —— 直接读触发器日志文件（或等 MCP 补 `channel=trigger` 参数）。
> ⚠️ 但**动作执行期报错不会落盘**（核查多份对局日志，除自己的探针外 `[Error]` 为 0 条），
> 参数被清成 `null`、动作静默失效这类问题仍然只能靠状态探针（`execute_lua` + `GameAPI.get_trigger_variable_*`）。

> 详细字段格式、完整示例、物编触发器（单位/技能）专用格式，全部见 `eca-json-builder.md`。

## 动态子触发 DSL

`gen_trigger.py` 可以从普通 trigger DSL 顶层的 `sub_triggers` 生成并写入动态子触发结构，也可用 `--dry-run` 预览。结构以技能测试目录中的编辑器实际保存样本为回归基准，不依赖活动地图中的临时触发器。每个子触发项与普通 trigger 相同，建议显式写 `id`；未写 `id` 时生成器会按父触发 ID 和子触发名称稳定派生 ID。父触发或同级子触发的 action 可用 `{"register_sub_trigger":"子触发名称或ID"}` 注册同一父级下的子触发，输出 JSON 中该 action 会被序列化为裸整数子触发 ID。未知名称/ID、同父级重复名称或重复 ID 会直接报错。

```json
{
  "name": "父触发",
  "id": 2000000001,
  "event": [["INIT_FINISHED"]],
  "action": [{"register_sub_trigger": "按键回调"}],
  "sub_triggers": [
    {
      "name": "按键回调",
      "id": 2000000002,
      "event": [["KEYBOARD_KEY_DOWN_EVENT", 18]],
      "action": [
        ["IF_THEN_ELSE",
          [["STRING_COMPARE",
            ["GET_STRING_TABLE_VAR_1D", {"var": "T", "type": "TABLE"}, "request_id"],
            "==",
            "abc"
          ]],
          [["UNREG_TRIGGER", ["CURRENT_DYNAMIC_TRIGGER_INSTANCE"]]],
          []
        ]
      ]
    }
  ]
}
```

生成结果会把所有后代子触发递归扁平写入父 JSON 的 `sub_trigger` 字典，键为字符串化子触发 ID。子触发固定是配置节点：`enabled=false`、`is_conf=true`、`p_trigger_id` 指向直接父触发 ID。编辑器样本确定了三个序列化约束：`CONDITION_LIST.arg_type=100021`、每个触发器的首个 `element_id` 为 `trigger_id * 1000000 + 1`、未使用计时器时不自动声明 `NEW_TIMER`。`IF_THEN_ELSE` 会自动写入编辑器分支布局标记 `fake_op=[2]`。回调子触发读取父触发的立即结果局部变量时，变量 tuple 仍写 `["TYPE","name","local"]`；父触发 `var_data` 会覆盖这些引用，子触发自身 `var_data` 可为空。动态子触发生命周期由注册/注销控制，常见回调结束时使用 `UNREG_TRIGGER(CURRENT_DYNAMIC_TRIGGER_INSTANCE)` 注销当前动态实例。若同步拒绝不会产生终态事件，注册动作必须放在受理条件分支内（例如 `request_id != ""`），否则会留下无法注销的动态实例。
