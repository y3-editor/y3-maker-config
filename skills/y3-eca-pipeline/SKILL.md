---
name: y3-eca-pipeline
description: |
  Y3 纯 ECA 开发的【唯一入口】：编排「需求 → 触发器 / 函数 / 变量 → 加载 → 对账 → 交付」，
  并优先挡住 ECA 特有的**静默失效**（写法被编辑器接受、运行时零效果）。
  ALWAYS use this skill when user mentions: ECA、ECA 触发器、全局触发器、ECA 函数、ECA 变量、
  触发器逻辑、刷怪波次、UI 事件接触发器、胜负结算、触发器没反应 / 不生效 / 静默失效。
  物编走 y3-obj-edit；界面走 y3-ui-pipeline；Lua 走 y3-lua-pipeline；测试执行走 y3-auto-test。
  生成器脚本与 DSL 细节在 eca-json-builder（本技能的内部实现）。
---

# Y3 ECA Pipeline

ECA 的失败形态和 Lua 不一样：Lua 报错会落 trace，ECA 会**静默失效** ——
结构校验、写法 lint、往返 `diff` 全绿，`valid=true`，参数一个没被清空，游戏里什么都不发生。
本流程每一步都为挡住静默失效服务。

## 🔴 激活即读

```
1. ../eca-json-builder/runtime_pitfalls.md   ← 静默失效清单 + 排查顺序
2. ../../memory/eca-issues/                  ← 错题本（存在时）
```

## 路由

| 需求 | 入口 |
|------|------|
| ECA 触发器 / ECA 函数 / ECA 变量 | **本技能** |
| 生成器脚本、DSL 字段、参数类型 ID、探针法 | `eca-json-builder`（内部实现） |
| 单位 / 技能 / Buff / 物品 / 投射物 | `y3-obj-edit` |
| 画板 / 元件 / 控件命名契约 | `y3-ui-pipeline` |
| 逻辑节点（点 / 区域 / 路径） | MCP `add_point` / `add_rect_area` / `add_point_path`（时序见 §1） |
| 跑测试、点击用例 | `y3-auto-test` |
| 技能触发器端到端验证（施法 → 回读 → 判定） | `scripts/verify_ability_triggers.py` |
| 运行时读写全局变量（MCP 无原生变量 API） | `scripts/probe_variables.py --list/--get/--set` |

## 1. 先判改动类型，再准时序

时序错了两头都贵：**多走一轮 `restart_editor` ≈ 2 分钟**；
**少走一步 → 新变量被 `save_editor` 裁掉 → 引用它的触发器静默失效**（实测踩过两次）。

| 改动内容 | 重启编辑器 | 动作序列 |
|---------|-----------|---------|
| 只改**全局**触发器 | 不需要 | `save_editor` → 生成 → 串行 `import_eca` → 等 3 秒 → `save_editor` |
| 只改**物编**（单位/技能）触发器 | **要** | `save_editor` → `edit_trigger.py <dsl> --container ability\|unit --key <key>` → `restart_editor(save_before_restart=false)` → `save_editor` |
| 改全局变量 | **要** | `save_editor` → `var_manager.py add/remove` → 停止保存 → `restart_editor(save_before_restart=false)` → 串行 `import_eca` → 等 3 秒 → `save_editor` |
| 改 ECA 函数 | **要**，顺序不可换 | 同上（"不保存重启"专为函数表设计） |
| 改逻辑节点 | **要** | `save_editor` → 改 `logicres.json` + `editor/existingmodelinfo.json` → `restart_editor(save_before_restart=false)` → 串行 `import_eca` → 等 3 秒 → `save_editor` |

**完成标志**：改动涉及的每一类都按对应序列走完，且每步都留下命令返回作为证据。

> `save_before_restart=false` 会把编辑器会话搞脏（之后启动游戏可能卡 loading 30%），
> 收尾补一次 `restart_editor(save_before_restart=true)` 恢复。

### 1.1 减轮次：物编触发器（技能/单位）没有热更通道，这样打组合拳

物编触发器改一次就要 `restart_editor(false)`（约 80 秒）+ 重启游戏（约 45 秒），
一轮 2 分钟起步。**多轮乱试是这类任务最大的时间黑洞**，按下面的顺序做：

1. **先验动作，再铺开**：拿不准某个动作/写法能不能活，先写一条**全局**触发器（走 `import_eca`，秒级热更）
   把它挂到你已经验证可靠的事件上（如 `GENERIC_UNIT_EVENT` + `ET_UNIT_DIE`），验通了再批量铺进物编触发器。
2. **一次重启装完所有物编改动**：把所有「需要重启才生效」的改动（新增全局变量、新增/修改函数、
   逻辑节点、全部技能触发器）攒在同一批 → **一次** `restart_editor(save_before_restart=false)`
   → 一次性把它们都读进来。中途**一次 `save_editor` 都不能有**。
3. **一轮里多改几个**：既然一轮 2 分钟，就别一次只改一个技能；同批能一起改的一起改，改完一次验。
4. 收尾补一次 `restart_editor(save_before_restart=true)` 恢复编辑器会话。

## 2. 生成

触发器 / 函数 / 变量一律**脚本生成**，先 `--dry-run` 再正式生成；生成期守卫会拦下大部分写法错误
（未声明变量、`IF` 嵌 `ELSE`、**参数个数/错位**、**易错动作的位置写法**、动作位误填 `op_arg`、
未登记 arg_type、裸事件写法等）。

> 参数顺序有疑问时**不要查文档**：查 `eca_index.json` 里那条动作的 `cont`，`{#n}` 就是
> `args_list` 的下标（生成器报错时也会自动打印出来）。实测参照：`APPLY_DAMAGE` 第 0 槽是
> 「伤害所属」、第 2 槽才是「受伤目标」，按文档的二手顺序写会把伤害打到施法者身上。

- 触发器：`gen_trigger.py <DSL> --dry-run`
- **物编触发器（技能/单位）**：容器文件在 `maps/<地图>/ability/<技能Key>.json`（与物编数据
  `editor_table/abilityall/<技能Key>.json` 是两个文件）。`edit_trigger.py --container ability --key <Key>`
  **要求容器已存在**，先用 `gen_ability_trigger.py --map <地图> --keys <Key,Key...>` 生成 194 字节空骨架，
  再用 `edit_trigger.py <DSL> --container ability --key <Key>` 写入触发器。
- `edit_trigger.py` 会**拦截 `SET_VARIABLE <局部 POINT>`**：实测在技能触发器里会让整条触发器
  `valid=false`。跨计时器保存区域改用全局 `UNIT_GROUP`（施法瞬间存单位组，计时器遍历它）；
  仅做实验时可加 `--allow-local-point`。
- 函数：`gen_function.py`。函数体有两种写法：`lua_bind: true`（转调 Lua）或
  `actions: [...]`（普通 ECA 动作 DSL，复用 `gen_trigger.build_action_list`）。
  两者可以叠加，顺序是「`lua_bind` 赋值动作 + `actions`」；`actions` 引用的局部变量
  会自动登记进 `var_data`。
- 变量：`var_manager.py add <名> <类型> --map <地图>`

**完成标志**：每个改动都有一条成功的生成命令输出（`OK [n] <名字>`）。
DSL 字段与 arg_type 规则 → `../eca-json-builder/eca-json-builder.md`。

## 3. 加载

> **批量加载用 `scripts/load_eca.py`**（把顺序固定死，避免"先保存后导入"丢文件）：
> `py -3 scripts/load_eca.py [--dsl <DSL.json>]` —— 内部做「（可选）按 DSL 重生成 → 串行
> `import_eca` → 等 3 秒 → `save_editor` → 逐个回读对拍 + 读 `valid`」，任一环节不过就非零退出。
> 只改一两个触发器时也可以 `--only a.json,b.json`。

> **物编触发器批量加载用 `scripts/load_obj_triggers.py`**：
> `py -3 scripts/load_obj_triggers.py <清单.json|目录> [--audit]`。它把「写盘 → 一次
> `restart_editor(save_before_restart=false)` → 等重开 → `save_editor` → 回读 `valid`」
> 固定成一条路径，中途不插任何 `save_editor`；`--audit` 会在通过后追加全量审计。
> 清单格式见脚本头注释。

`import_eca` **逐个串行**，每个都记录 `success` / `mode` / `trigger_id` / `hotfix_status`。

> ⚠️ **`import_eca` 只支持全局触发器**（路径必须包含 `global_trigger/trigger/`）。
> 传物编触发器路径会被直接拒绝：`Error: 本工具仅支持全局触发器（路径需包含 global_trigger/trigger/）`。
> 因此 `maps/<地图>/ability/*.json`、`maps/<地图>/unit/*.json` 这类物编触发器**没有热更通道**，
> 只能靠 `restart_editor(save_before_restart=false)` 让编辑器重读磁盘。
> 别再指望"保存一下就好"：实测「普通保存会不会把盘上改过的物编触发器顶回旧值」**不稳定**
> （4 次里 1 次顶回、3 次保留盘上新内容，含往容器里新增触发器的情况）——重启用的是确定性路径。

`hotfix_status=未连接（仅编辑器侧已更新）` 是常态、不算失败；要跑完整测试必须重启游戏。
插件运行时**只影响运行时**：想让改动在游戏里生效，重启游戏是唯一闭环。

**完成标志**：每个文件都有 `success=true` 的返回记录（缺一个就是没加载）。

## 4. 对账（静默失效在这里被抓住）

四步都要证据，缺一步等于没验：

| 步 | 手段 | 抓什么 |
|----|------|--------|
| ① | `eca_json_helper.py diff <生成副本> <回读文件>` | 参数被清成 `null` |
| ② | `py -3 ../eca-json-builder/audit_triggers.py --map-dir maps/<地图>` | ID 重复 / `valid≠true` / 子触发器未注册 / 引用未声明变量 / 变量写成 3 元组；**同时扫描 `ability/unit/item/modifier/projectile` 物编触发器容器** |
| ③ | **探针**：往全局变量写哨兵值 → 运行时读回 | 触发器**根本没跑** |
| ④ | 端到端观察：采样单位位置 / 血量 / 界面可见性 | 动作跑了但**没效果** |

> **技能类触发器**直接用脚手架跑对账 ④：
> `py -3 scripts/verify_ability_triggers.py --skill <技能Key> --slot <第几格> [--restart]`
> —— 它内部做掉「英雄存活检查 / 满血 / 传送 / 造测试怪 / 施法 / 按身份回读 / 判定」，
> 并把 **PASS / FAIL / NEEDS_MANUAL / BLOCKED** 分开报（点目标技能的脚本施法本来就放不出去，
> 会直接判 NEEDS_MANUAL 而不是误报 FAIL）。
> 会话里没连 MCP HTTP 端点时用 `--emit` 拿三段 Lua 手动执行，再用 `--judge-*` 判定。

③④ 的做法与判读表 → `../eca-json-builder/runtime_pitfalls.md §5`。

### 4.1 读 ECA 日志：**MCP 没有这条通道，只能用 shell 读文件**

> 实测：`y3editor.get_editor_log` 读的是
> `LocalData/LocalLog/Log_<时间>.log`（只有编辑器 / 启动器几行），
> `y3helper.get_logs` 读的是插件侧的 Lua 通道（格式 `[<ISO 时间戳>] 文本`，
> 只有 Lua `print`）。**这两个 MCP 都读不到 `trigger_log`。**

| 通道 | 文件 | 内容 | 谁来读 |
|------|------|------|--------|
| **触发器日志** | `<game root>\LocalData\trigger_log\<地图名>\Log\<玩家名>_<时间>.log` | **ECA `PRINT_MESSAGE_ACTION_TO_DIALOG` + Lua `print`（两条混写）** | **只能 shell 读文件** |
| Lua 日志 | 插件抓取（`maps/<地图>/script/.log/`） | Lua `print` | `y3helper.get_logs` |
| 客户端日志 | `LocalData/LocalLog/Log_<时间>.log` | 编辑器 / 启动器 | `y3editor.get_editor_log` |

读最新一局（PowerShell）：

```powershell
$d = "<game root>\LocalData\trigger_log\<地图名>\Log"
$f = Get-ChildItem -LiteralPath $d -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
"$($f.Name)  $($f.LastWriteTime)"
Get-Content -LiteralPath $f.FullName -Encoding UTF8 | Select-Object -Last 40
```

三条硬约束：

1. **一局一个文件**，命名 `<玩家名>_<时间>.log`；游戏没跑过就没有新文件（会读到旧局的）。
2. **两条通道混写、前缀一模一样（`[ Info]:`）** → 打印时自带标记（`[ECA]xxx` / `[LUA]xxx`），
   否则无法判断某一行是谁写的。实测对照：`Hello, Y3!` 来自 Lua `print`，
   `Hello World!` 来自 `New trigger.json` 里那条 ECA 打印，两者在同一个文件里长得一样。
3. **动作执行期报错不落盘**：日志里没有 `[Error]` **不等于**动作生效了
   （实测：进度条整段不工作时，日志里一条错误都没有）。打印只能证明"分支走到了"，
   **"动作有没有效果"仍然只能靠 ③④ 探针 / 端到端观察**。

**完成标志**：每条改动的触发器都有 ①②③ 的证据，且涉及表现的部分有 ④ 的观察数据；
只做静态三连（校验 / lint / diff）就宣布完成，等于把静默失效放进交付。

## 5. 交付报告

```markdown
## ECA Task Completion Report

### 1) 任务信息
- 任务描述 / 影响范围 / 改动类型（触发器 | 变量 | 函数 | 逻辑节点）

### 2) 变更文件
- 新增 / 修改 / 删除（触发器、函数、变量三字段、逻辑节点各列清楚）

### 3) 时序证据
- 是否重启编辑器（第几次）/ 是否重启游戏 / 每步命令返回摘要

### 4) 对账结果
- ① diff：逐文件 OK 或差异说明（含 benign 差异，如编辑器补写的 local_var）
- ② 审计：ID 唯一 / valid=true / 子触发器注册 / 变量引用合法
- ③ 探针：哨兵变量读回值 → 结论（跑了 / 没跑）
- ④ 观察：采样数据 → 结论（有效果 / 无效果）
- 日志：`trigger_log` 最新一局的文件名与关键行（**shell 读**；无打印则写明"未加打印"）

### 5) 已知偏差与例外
- 跳过的门禁：无 / Gx（需说明理由与风险）
- 未自动化验证的用例：逐条列出（如 UI 点击链路）与人工验证步骤

### 6) 记忆归档
- 是否新增 memory/eca-issues 记录 / 归档文件 / 一句话结论

### 7) 风险与补救
- 当前剩余风险 / 补救建议
```

## 强制执行清单

每项都要有证据，未完成不得标记任务完成：

- [ ] **路由确认**：已确认本任务属于 ECA；物编 / 界面 / Lua / 测试已分别路由出去
- [ ] **技能指示器自检**（涉及技能触发器时）：逐个技能核对该技能 `sight_type` 与触发器里「取目标方式」是否匹配
  （方向类 1/2 必须按方向做扇形选取；3 用 `ABILITY_RELEASE_POSITION`；4 用 `TARGET_UNIT_IN_ABILITY`），
  并且**每个指示器类型至少各放一次**（不匹配时不报错、只是没效果）→ `../eca-json-builder/runtime_pitfalls.md §10.1`
- [ ] **技能效果落地门禁**（Phase 1 结束时）：逐个技能标注每个效果由「物编字段」还是「技能触发器」实现；
  凡依赖伤害 / 属性，必须引用 `knowledge/物编系统/06-技能.md` 的结论
  「`ability_damage` 只是数值配置，引擎不会自动结算伤害」，不能因为填了字段就当作技能有伤害
- [ ] **前置阅读**：已读 `runtime_pitfalls.md` 与 `memory/eca-issues/`
- [ ] **时序判定**：已按 §1 判定改动类型并选对序列（含"是否需要重启编辑器"）
- [ ] **脚本生成**：触发器 / 函数 / 变量均由脚本生成，`--dry-run` 先行
- [ ] **串行加载**：每个触发器都有 `success=true` 返回记录
- [ ] **对账 ①**：每个改动文件都跑过 `diff`
- [ ] **对账 ②**：`audit_triggers.py` 全绿（ID / valid / 子触发器 / 变量 / **物编触发器容器**）
- [ ] **对账 ③**：至少一次状态探针，确认触发器真的跑了
- [ ] **对账 ④**：涉及表现的部分有端到端观察数据
- [ ] **日志取证**（触发器里有 `PRINT` 时）：**用 shell 读** `LocalData/trigger_log/<地图>/Log/` 最新一局，
  确认打印带 `[ECA]` 标记；且**不把"日志里没有 Error"当成"动作生效"**（动作报错不落盘，见 §4.1）
- [ ] **变量三字段**：新增变量在 `variable_dict` / `variable_group_info` / `variable_length_dict` 齐全
- [ ] **局部 POINT 守卫**：技能/单位/物品触发器里没有 `SET_VARIABLE <局部 POINT>`（如有，改存 `UNIT_GROUP`）
- [ ] **错题归档**：新踩的坑写入 `memory/eca-issues/`
- [ ] **交付报告**：已按 §5 输出

## 指针

| 材料 | 何时读 |
|------|--------|
| `../eca-json-builder/runtime_pitfalls.md` | 动手前；以及"触发器没反应"时的排查顺序与探针法 |
| `../eca-json-builder/eca-json-builder.md` | 写 DSL、查 arg_type / sub_type / 变量 tuple |
| `recipes.md`（本技能） | 写具体逻辑时：定时器与轮询 / 单位创建与命令 / UI 显隐与绑定与点击 / 胜负结算 / 条件与数值 |
| `references/runtime_probe_snippets.md` | 纯 ECA 验收：读变量 / 暂停清场 / 造测试怪 / 施法采样 / UI 显隐与点击 / 模拟胜负 |
| `../eca-json-builder/probe.py` | 拿不准某类型该写什么 sub_type，一条命令问编辑器 |
| `../eca-json-builder/ui_uid.py` | 按**控件名**解析画板控件 uid（控件名是契约、uid 会变；不要写死 uid） |
| `scripts/load_eca.py`（本技能） | 批量加载触发器：按 DSL 重生成 → 串行 import → 等 3s → 保存 → 回读对拍 |
| `scripts/load_obj_triggers.py`（本技能） | 物编触发器批量加载：写盘 → 一次重启 → 保存 → 回读 `valid` |
| `scripts/rename_logic_nodes.py`（本技能） | 逻辑节点改名：`logicres.json` + `existingmodelinfo.json`，改完自动重启 |
| `scripts/probe_variables.py`（本技能） | 列变量清单 / 运行时读值 / 写值；需要已连接游戏客户端 |
| `<game root>\LocalData\trigger_log\<地图名>\Log\*.log` | 查 ECA 打印（**MCP 读不到，只能 shell 读最新一局**；见 §4.1） |
| `../../memory/eca-issues/` | 同类问题复发时先翻历史 |

