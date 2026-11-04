# ECA 运行时陷阱清单（编辑器接受 ≠ 运行时生效）

> **为什么单独成文**：`validate` / `scan` / `diff` / `lint` 只能证明「写法被编辑器接受」，
> **证明不了「运行时真的执行」**。本文件收集的全是「四种校验全绿、触发器 `valid=true`、
> 参数一个没被清空，但游戏里什么都不会发生」的写法 —— 这类问题只能靠**运行时取证**发现。
>
> 全部条目都带**取证方法 + 反例/正例**。新增条目请沿用同一格式。

---

## 0. 判定顺序（遇到「触发器不生效」时按这个查）

| 顺序 | 检查 | 手段 |
|------|------|------|
| 1 | 写法是否被编辑器接受 | `eca_json_helper.py diff`（生成副本 vs 回读文件） |
| 2 | 触发器是否 `valid=true` / `enabled=true` / 子触发器是否被注册 | `audit_triggers.py`（自建）/ `read_trigger.py` |
| 3 | **事件到底有没有触发** | **状态探针**：在动作列表**最前面**无条件写一个哨兵值到一个全局变量，再去运行时读它（见 §5） |
| 4 | **动作到底有没有效果** | 把**同一个动作**挂到一个你确定能触发的事件上（如 `ET_UNIT_DIE`），造可控前置条件观察 |
| 5 | 是否命中本文件的已知陷阱 | 逐条比对 §1~§4 |

> ⚠️ 只做 1、2 两步就下"实现完成了"的结论，是最容易犯的错。

---

## 1. UI 事件：两条通道，只有一条能被 ECA 收到

| 通道 | 写法 | ECA 能否收到 | 证据 |
|------|------|-------------|------|
| **设计期具名事件**（推荐） | 画板控件 `event_list: [{"name":"xxx","type":1}]` + 子触发器事件写成**普通字符串字面量** `{"arg_type":100067,"sub_type":1,"args_list":["xxx"]}` | ✅ 能（工程自带官方画板的具名事件就是这么接的） | 官方画板 + 官方触发器样本；自建画板实测可用 |
| 运行时注册 | `CREATE_UI_COMP_EVENT_EX_EX(控件, 2, "事件名")` + 子触发器事件写 `["STR_TO_UI_EVENT","事件名"]` | ❌ **运行时收不到**（虽然能通过编辑器保存、`diff` 全绿） | `UI:send_event("事件名")` 打官方按钮（连同官方触发器做对照），**面板可见性完全没变** |

### 1.1 关键区分：`send_event` ≠ 真实点击

`y3.ui` 的 `UI:send_event(name)`（底层 `GameAPI.trigger_ui_event`）是**命名事件注入**，
实测**驱动不了** ECA 的 `TRIGGER_COMPONENT_EVENT`（见上表反例）。

> ✅ **修正（实测）：`UI:send_event("名字")` 可以驱动 ECA。**
> 自建画板 + 自建子触发器的场景下，用
> ```lua
> y3.ui.get_ui(player, "MyPanel.MyPanel_block.card_3"):send_event("card_3_click")
> ```
> 注入具名事件，ECA 子触发器（`TRIGGER_COMPONENT_EVENT` + 字符串字面量事件名）**确实执行**：
> 5 张卡片逐一 1:1 命中（card_1→1 … card_5→5）、确认按钮成功创建单位、
> 重开按钮成功复位整局状态，结果可复现。
>
> 上面那条"收不到"的旧结论，对照组用的是**官方 `bag` 按钮** —— 它的具名事件是给 Lua
> 处理器（`Init Main UI Event Handler`）用的。**结论修正为：通道本身是通的，UI 交互可以自动化**；
> 若某个控件点了没反应，先查它自己的 `event_list` 是否声明了该事件名、以及面板是否可见
> （**隐藏面板的控件收不到事件**：实测把面板隐藏后再注入事件，目标变量完全不变）。

### 1.2 调用 `trigger_ui_event` 的正确姿势

```lua
-- ✅ 正确：包成 Lua 对象方法（内部传 handle）
y3.ui.get_ui(player, "MyPanel.block.main_frame.card_1"):send_event("card_click")

-- ❌ 错误：直接传 Lua 对象给底层 API —— 会把运行时 Lua 虚拟机打挂
GameAPI.trigger_ui_event(player, ui_obj, "name")   -- 实测：之后 execute_lua 全部无输出，只能重启游戏
```

签名来源：`y3/object/scene_object/ui.lua` 的 `UI:send_event` → `GameAPI.trigger_ui_event(role_handle, comp_handle, event_name)`。

### 1.3 画板控件默认没有具名事件

`y3-ui-generator` 生成的节点 `event_list` 固定为空数组。
需要 ECA 接点击时，必须补具名事件（见 `y3-ui-generator/SKILL.md` 的 `data-event`）。

---

## 2. 单位命令：群体命令在本版本无效，逐只命令有效

| 动作 | 运行时效果 | 证据 |
|------|-----------|------|
| `API_RELEASE_UNIT_GROUP_COMMAND(单位组, UNIT_GROUP_COMMAND_ATTACK_MOVE(点))` | ❌ **完全没有效果**（单位原地不动） | 同款动作挂到 `ET_UNIT_DIE` 触发器上，让一只干净单位在原地等 8 秒 → 8 次采样位置完全不变 |
| `UNIT_RELEASE_COMMAND(单只单位, UNIT_COMMAND_ATTACK_MOVE(点))` | ✅ 有效 | 同条件立刻行军，实测 **200 cm/s = 2 m/s**，与 `ori_speed = 2.0` 吻合 |

**推荐写法**：创建后立刻逐只下令

```jsonc
// DSL
["SET_VARIABLE", {"var": "本波怪", "type": "UNIT_ENTITY"},
 ["CREATE_UNIT", 200101, ["RECTANGLE_RANDOM_POINT", 10005], 0.0, 31]],
["UNIT_RELEASE_COMMAND", {"var": "本波怪", "type": "UNIT_ENTITY"},
 ["UNIT_COMMAND_ATTACK_MOVE", 10003]]
```

> 用局部变量接住 `CREATE_UNIT` 的返回值，比依赖 `LAST_CREATE_UNIT` 更稳；
> 局部变量会被**父触发器**的 `var_data` 收集（子触发器自身 `var_data` 可为空，这是引擎约定）。

> `eca_index.json` 的 `lua` 字段在这两个动作上是**过期**的
> （`y3.game.api_release_unit_group_command` / `y3.game.unit_group_command_attack_move`
> 在本版本实测为 `nil`）。**不要照着 `lua` 字段去 Lua 复现**，要用 `y3/` 源码或实测确认。

---

## 3. 时序陷阱：事件触发瞬间，世界状态还没更新

| 陷阱 | 现象 | 正确做法 | 证据 |
|------|------|---------|------|
| **`ET_UNIT_DIE` 里死亡单位仍在单位组** | `GET_COUNT(PLAYER_UNIT_GROUP(31))` 在事件里读到 1（含将死单位），**0.5 秒后仍读到 1**，用 `RUN_ONCE_TIMER_NO_SAVE(0.5)` 复查也来不及 → 「最后一波清空」永远判不出来 | 改成**轮询**：事件里先写一份快照变量，条件成立时用 `RUN_LOOP_TIMER`（1 秒）反复复查，直到快照 ≤ 0 再结算；并用一个标志全局变量保证只结算一次 | Lua 侧 `get_all_units():count()` 下一帧就是 0，但 ECA 的 `GET_COUNT` 0.5 秒后仍算 1；改用轮询后一次通过 |
| **计时器动作列表里可以做嵌套 IF** | 曾怀疑「嵌套 `IF_THEN_ELSE` 被丢弃」 | 实测**会正常执行**（探针：`RUN_ONCE_TIMER_NO_SAVE` 体里放一个平写动作 + 一个嵌套 IF，两个信号都写进去了） | 双信号探针 |
| **`IF_THEN_ELSE` 不能嵌在 ELSE 分支** | 保存时被整体丢弃 | 平铺成同层级多个 IF（`gen_trigger.py` 已直接报错拦下） | 旧结论，仍成立 |

---

## 4. 会话/环境前置（会伪装成"功能坏了"）

### 4.1 y3runtime MCP 随游戏进程启停

MCP 配置（`.codemaker/mcp_settings.json`，Codex 侧为 `.codex/config.toml`）里 y3runtime 指向 `127.0.0.1:8767`，**它只在游戏运行时监听**。
而 Codex 的可调用工具清单在**会话开始时快照**，因此：

> **若会话开始时游戏没跑 → 整个会话都没有 y3runtime 工具**（表现为"无法做 UI 自动化"），
> 且中途启动游戏也**不会**补上工具。

**建议流程**：需要 UI/运行时自动化时，**先启动游戏确认 8767 在听，再开新会话**。
快速自检：`Test-NetConnection 127.0.0.1 -Port 8767`。

### 4.2 新增全局变量会被 `save_editor` 裁剪

`save_editor` 以**编辑器内存**为准写回 `globaltriggervariable.json`：
磁盘上新加、但编辑器内存里没有的变量会被**删掉**，随后所有引用它的触发器翻 `valid=false`
（症状是"触发器静默失效"，很难往变量上想）。

**唯一安全顺序**（`var_manager.py add` 现在会把这个顺序打印出来）：

```
1) save_editor                      ← 先落盘编辑器当前修改
2) var_manager.py add <名> <类型>    ← 再写新变量到磁盘
3) ⛔ 中间绝不能再 save_editor
4) restart_editor(save_before_restart=false)   ← 让编辑器读到新变量表
5) import_eca 各触发器（串行）
6) 等 3 秒 → save_editor
7) 复查：引用变量是否还在 + 触发器 valid 是否为 true
```

> 同理：**逻辑节点改名/删除**也要走 `4)~7)`（改完 `logicres.json` 后必须让编辑器重新读盘）。

### 4.3 改动类型 → 加载时序

**权威表在 `skills/y3-eca-pipeline/SKILL.md §1`**（那里是流水线的站位，本文件不再重复一张）。

这里只留一条判断依据：**"要不要重启编辑器"取决于编辑器内存里有没有这份数据**。
触发器是逐文件 `import_eca` 进来的，改触发器不必重启；变量表、逻辑节点、函数表都是
"编辑器启动时读一次"的整体数据，改完必须让它重新读盘 —— 否则 `save_editor` 会拿旧内存覆盖你的修改。

> 另一个方向同样成立：**别过度重启**。只改触发器却顺手走一遍 `restart_editor`，
> 每轮白花 1.5~2 分钟（还要补一次保存重启恢复会话）。

---

### 4.4 工程/环境类：备份范围、脚本目录、副本身份、日志位置

这几条都不会报错，但会让"看起来正常"的工程跑不起来或改不动。

| 事实 | 影响 | 应对 |
|------|------|------|
| 编辑器自动备份 `LocalData/MapBackUp/<项目名>/<地图名>/` **只覆盖地图数据** | `maps/<地图>/script/`（y3 框架库 + `main.lua` + y3-helper）**不在备份里**；目录被清空后数据"全回来了"但**游戏起不来**、插件也连不上 | 每次打开 / 保存前自己留一份工程副本；`script/` 丢了从工程 zip 还原 |
| 地图目录被清空时 `header.map` 会一起丢 | 编辑器按 `header.project` 的 `entry_map.id` 去 `maps/<名字>` 找地图，找不到就把目录名算成空串 → `open_map` 抛 `TypeError: cannot unpack non-iterable bool object`，**打不开也存不了** | 恢复时务必确认 `maps/<地图>/header.map` 在位；恢复后"不保存重启"让编辑器重读盘 |
| 同机多份工程副本**共用** `project_id` / `project_name` / `entry_map.id` | 缓存、锁（`lock/`）、`LocalData/MapBackUp/<项目名>/` 都按项目名共享 → 同时打开会互相干扰，表现可能是"保存失败" | **一次只开一个副本**，换副本前先关干净 |
| ECA 打印落在 `LocalData/trigger_log/<地图名>/Log/<玩家名>_<时间>.log`，**两个 MCP 都读不到**（`y3helper.get_logs` = 插件侧 Lua 通道；`y3editor.get_editor_log` = `LocalData/LocalLog/`） | 想用日志排查只能**shell 读文件** | 打印自带 `[ECA]` 标记（该文件里 Lua `print` 与 ECA 打印混写、前缀都是 `[ Info]:`）；动作执行期报错**不落盘**，仍要靠探针 |

### 4.5 改 `script/main.lua` 后 `quick_restart`（`.rr`）不会重读

- 实测：删掉 `main.lua` 里的演示 `print` / `y3.timer.loop` 后 quick_restart，日志仍每 5 秒打印
- 原因：`.rr` 只重启**游戏会话**，`main.lua` 只在**进程启动**时读一次
- 正确做法：`stop_game` → `launch_game` 完整换进程
- 推论：`include` 之外的模块与 `main.lua` 本身都要换进程；`include` 进来的脚本可以用游戏内 `.rd` 热重载

## 5. 状态探针：确认「触发器到底有没有跑」

ECA 没有可靠的断点，**最便宜的观测手段是往全局变量写哨兵值**：

```jsonc
// 在触发器动作列表最前面插一条（取证后删掉）
["SET_VARIABLE", {"var": "哨兵变量", "type": "INTEGER", "scope": "global"}, 777]
```

读回：`execute_lua` → `GameAPI.get_trigger_variable_integer('哨兵变量')`

| 读到的值 | 结论 |
|---------|------|
| `777` | 触发器**跑了**，但后续逻辑/条件没命中 → 查条件参数 |
| 预期业务值 | 全链路通 |
| 仍是旧值 / `0` | 触发器**根本没跑** → 查事件名、子触发器注册、`valid` |

> ⚠️ **探针本身有两个坑**：
> 1. **同一帧创建多只单位会被引擎重分配坐标**（实测同帧造 6 只怪，坐标被挪到网格点上，其中一只跑到图外），
>    做坐标/位置取证时**一帧一只**。
> 2. **坐标口径**：逻辑资源与镜头焦点是**米**，`y3.point.create` / `get_point` 是**厘米**（×100）。
>    口径搞混会得出"命令无效"的错误结论。

### 5.1 打印落在哪

| 通道 | 位置 | 内容 |
|------|------|------|
| 触发器日志 | `LocalData/trigger_log/<地图名>/Log/<玩家名>_<时间>.log` | `PRINT_MESSAGE_ACTION_TO_DIALOG`、`y3.log.*` |
| Lua 日志 | `maps/<地图>/script/.log/lua_player01_<玩家名>.log` | Lua `print`（`y3helper.get_logs` 读的是这条） |
| 客户端日志 | `LocalData/LocalLog/Log_*.log` | 引擎底层 |

> **动作执行期报错不落盘**，所以"静默失效"类问题只能靠状态探针。

---

## 6. 已知「写法限制」（会被静默清空或翻 valid=false）

完整清单见 `SKILL.md`「关键陷阱」与 `gen_trigger.py` 生成期校验；此处只列已复核的：

| 写法 | 后果 | 正确写法 |
|------|------|---------|
| `SET_VARIABLE <NEW_TIMER 变量> = 0` | 参数被清成 `null`，**整条触发器 `valid=false`** | 计时器初值交给变量默认值，不在触发器里赋值 |
| 全局 `UNIT_NAME` 变量的**读取** | 被清成 `null` | 存 **INTEGER** 编号 + 字面量分支 |
| `FLOAT_COMPARE` 混用 INTEGER 实参 | 条件恒不成立（静默） | 两侧都是整数就用 `INTEGER_COMPARE` |
| 全局 `BOOLEAN` 变量的比较 | 未验证成功 | 改用 INTEGER 状态变量（0/1） |
| `VALUE_TO_STR` | 参数类型 `VAR_TO_STR` 未登记，生成器直接报错 | 用 `INT_TO_STR` + `STR_JOIN` |
| `LOGIC_RES` 当函数用 `["LOGIC_RES", res_id]` | 不是合法函数式 sub_type | POINT/RECTANGLE 参数**直接传 res_id 整数** |
| DSL 的 `event` 写成一维数组 | 生成 `event_type: UNKNOWN`（现在会直接报错） | 必须 `"event": [["INIT_FINISHED"]]`（事件列表的列表） |
| `GET_UNIT_ATTR(单位,"ATTR_RESULT","mp_cur")`（`hp_cur` 同理） | 该槽用的是**可写属性枚举**，没有"当前值"，参数被清成 null 且**整条触发器 `valid=false`**（症状：功能静默无效、参数表面还在） | 读当前值用专用函数：`GET_HP_CUR` / `GET_MP_CUR`；`hp_max` / `mp_max` 才走 `GET_UNIT_ATTR` |
| 局部 `POINT` 变量默认值写 `0` | 编辑器 `EType.FPoint.to_value()` 要做 `float(val[0..2])` → `TypeError` → **整次保存中断、地图目录被清空**（随后 `header.map` 丢失，进入"打不开→存空→更打不开"死循环） | `POINT` 默认值必须 3 分量 `[0,0,0]`；更稳的做法是**不用 POINT 局部变量**，把 `res_id` 直接传给参数位 |
| 定时器动作（`RUN_*TIMER*`）缺 `local_var` | 编辑器自己写出的定时器动作**全部**带 `local_var`，缺了会报错 | 生成器已自动补 `{"__tuple__": true, "items": [{}, {}]}` |
| 全局触发器直接接 `UNIT_ON_ADD_EXP` | 保存后 `valid=false`（参数完好、无报错） | 全局事件里没有对应 `ET_` 包装名 → 改在发经验的动作里就地 `SET 等级 = GET_UNIT_LEVEL(...)`，或下沉到物编单位触发器 |
| 按控件名取进度条内的百分比文字 | `hp_bar` / `mp_bar` 模板里那行文字**与技能格（type:17）内部的 CD 标签同名**（都叫 `progress_percent_label`），按名字解析 uid 会撞车 | 生成画板后用后处理**改名**（如 `hp_percent_label` / `mp_percent_label`）再引用 |
| **技能触发器里写局部 `POINT` 变量** | `SET_VARIABLE <局部 POINT> = ABILITY_RELEASE_POSITION(...)` 保存后整条技能触发器 `valid=false`，参数表面完好 | 跨计时器保存区域改用**全局 `UNIT_GROUP`**：施法瞬间把范围内单位存进单位组，计时器遍历该组。`edit_trigger.py` 现在会直接拦截 |
| `EXIT_GAME` 在本地单机测试环境无效果 | UI 事件触发、触发器 `valid=true`，游戏进程不退出 | 改用 `ROLE_FORCE_QUIT(1, "玩家主动退出")`；实测可立即停止进程 |
| `FLOAT_TO_STR` 想要 0 位小数 | 只写 1 个位置参数会得到 `123.4` 这类带小数的文本 | 写成 `["FLOAT_TO_STR", 值, {"op_arg": [0]}]`，`op_arg_enable` 会由生成器置 true |
| 深色 HUD 面板用了 `data-preset="panel-bg"` | 生成出来是偏金色/棕色的面板底图 | 深色底板用 `data-preset="dark-bg"`（`906555`）；`panel-bg` 更适合弹窗/金色面板 |
| 重新生成画板后触发器大量打空 | `html_to_y3_ui.py` 旧版每次重新分配所有 uid；ECA 按 uid 寻址，全部失效 | 生成器现在默认按**名称路径复用旧 uid**；仍建议重生成后跑一次 `audit_triggers.py`（会校验触发器引用的 uid 是否还存在） |
| 官方 `GameHUD` 盖住自定义 HUD | 官方 HUD 约 992 节点，占据底部和右侧 | 把 `GameHUD.json` 根节点 `visible=false`（保留文件），再 `hotfix_ui_editor` → 等 3 秒 → `save_editor`；可用 `y3-ui-pipeline/scripts/hide_gamehud.py` |

---


---

## 7. 画板命名撞名会覆盖工程自带官方画板

`html_to_y3_ui.py` 的 ``--panel-name`` 直接决定输出文件名
``maps/<地图>/ui/<PanelName>.json``，**不做存在性检查、不备份**。

给自建画板取名与官方同名的 ``GameHUD``，会把工程自带的官方 HUD
（约 2.7 MB / 约 1000 节点 / 多个具名事件）
覆盖成自建面板。

**规避**：生成画板前先 ``ls maps/<地图>/ui/``；自建面板一律取**不含官方名的名字**
（官方常见名：``GameHUD`` / ``CommonTip`` / ``LoadingPanel`` / ``LogoPanel`` / ``loss`` / ``win`` / ``SceneUI``）。

**恢复**：同机其它工程 ``LocalData/*/maps/EntryMap/ui/GameHUD.json`` 通常留有同尺寸副本；
恢复后走 ``hotfix_ui_editor`` → 等 3 秒 → ``save_editor``，
编辑器会按自己的序列化格式重写该文件（字节数会变化，属正常）。

---

## 8. ECA 写法/时序：容易伪装成“逻辑写错”的几类

| 写法 | 症状 | 正确做法 |
|------|------|---------|
| 同一 `ET_UNIT_DIE` 事件上**拆两条触发器**：一条「扣次数」、一条「次数≤0 则失败」 | **少活一次**：某次死亡时，扣减先把值改成 0，另一条触发器紧接着判「≤0」成立 → 直接失败。两条触发器对同一事件的求值顺序不由你控制 | 合并到**同一条触发器的 IF/ELSE** 里一次求值（`IF 次数>0 THEN 扣次数+复活 ELSE 失败结算`） |
| 动作列表**首位**放 `DELETE_TIMER`，目标是已跑完/无效的计时器句柄 | 该动作报错后**整条动作列表中断**，后面的状态复位、界面切换全都没执行（表现：点「重新开始」毫无反应，但计时器确实被注销了） | 先 `IS_TIMER_VALID` 守卫，并把 `DELETE_TIMER` 放到动作列表**末尾** |
| 结算用 `END_GAME_FOR_ROLE`（方案 A） | 引擎结算模态弹出后，**玩家客户端不再处理地图 UI 事件**：自定义结算面板可见但按钮点不动，相关计时器也停住 | 需要「重新开始」可交互时改用**只用自定义画板结算**（方案 C），或改用 `END_GAME_FOR_ROLE_2` 指定自定义面板 |
| 隐藏面板里的控件 | 给隐藏面板的控件 `send_event` 完全没反应 | 事件只在**可见**控件上送达；先 `SET_UI_COMP_VISIBLE(true)` 再注入 |
| UI 事件自动化的正确姿势 | — | `y3.ui.get_ui(player, "画板.父节点.控件"):send_event("事件名")`（路径自画板一级开始、`"."` 分隔）。**不要**把 Lua 对象直接交给 `GameAPI.trigger_ui_event`（见 §1.2） |
| 状态探针的天然哨兵 | — | 全局变量默认值 + 初始化触发器赋一个不同值（如某变量默认 0、初始化写 5）：运行时读到 5 就证明触发器跑了，不必额外插探针动作 |
| 单元属性取值 | `GameAPI.get_trigger_variable_unit_entity` 返回的是裸实体，直接调 `:get_attr()` 得 `nil` | 先 `y3.unit.get_by_handle(...)` 转成 Unit 对象；单位**物编 Key** 用 `unit:get_key()`（`unit:get_type()` 返回的是分类：英雄=1、小怪=4） |
| 单位组遍历 | `for _, u in unit_group:pairs()` 会拿到 nil | 用 `unit_group:pick()` 拿到 Lua 数组再 `ipairs` |
| 单次击杀取证的干净手法 | — | `unit:kill_by(killer)` 可指定凶手，用它精确验证「击杀者 = 英雄」类分支，比控制战斗更稳 |

---

## 9. UI 自建画板的三个坑

### 9.1 自建面板必须避开官方 HUD 占位

官方 `GameHUD`（992 节点）已占满屏幕边缘。自建面板（如血条）如果和它撞位，
表现是「被官方元素挡住」。**先量再摆**，别凭截图目测：

- 量法一（最准）：直接读 `maps/<地图>/ui/GameHUD.json`，把 `pos_data.items[0]/[1]`（中心 x/y，
  Y3 原点左下）与 `size` 换算成矩形即可，无需启动游戏。
- 量法二：`y3-helper` 的 `get_ui_canvas`（只给树结构，**不含坐标**，不能用来量位置）。

官方占位参考（1920×1080，Y3 原点左下）：

| 节点 | x | y |
|------|---|---|
| `mini_map` | 0..308 | 0..244 |
| `main`（英雄信息+技能栏） | 433..1410 | 0..158 |
| `main_hp_bar` / `main_mp_bar` | 322..804 | 38..54 / 9..25 |
| `buff_list_1` | 1..901 | 182..240 |
| `hero_list` | 2..144 | 314..998 |
| `player_attr_list` | 1409..1921 | 0..100 |
| `game_time` | 821..1021 | 1013..1080 |

> 血/蓝条想「像官方那样」直接复用官方贴图：`main_hp_bar` 用 `image=133784 / bg_image=133785`，
> `main_mp_bar` 用 `image=133815 / bg_image=133785`。

### 9.2 图片控件：`data-preset` 会盖掉 `data-image`

`html_to_y3_ui.py` 的 `_add_image_fields` 判定顺序是
**先看 `data-preset`，命中就用预设图，`data-image` 被完全忽略**。

所以 `<div data-type="image" data-preset="frame" data-image="906769">` 生成出来是
`frame` 预设图（132055），而不是头像 906769 —— 症状是「卡片上没有头像，只有一块黄底边框图」。
要放自定义图片就**别写 `data-preset`**。

### 9.3 重新生成画板：uid 默认稳定，但新增/删除控件仍要重导

旧版 `html_to_y3_ui.py` 每次运行都重新分配 uid；现在默认按**名称路径复用旧 uid**，
未改动控件保持原 uid，新增节点才分配新 uid。于是常规改布局/改颜色/改文字不会让整批 ECA 引用失效。

但仍要：

1. 新增 / 删除 / 改名控件后，按控件名重新解析 uid；
2. 重导引用这些控件的触发器（`import_eca` 串行 → 等 3 秒 → `save_editor`）；
3. 跑 `audit_triggers.py`，它会报“触发器引用了画板里不存在的控件 uid”。

需要强制全部换新 uid 时加 `--no-reuse-uids`。

**永远不要在生成器脚本里硬编码 uid**：生成 DSL 时从画板 JSON 读回「控件名 → uid」；
控件**名字**是契约、uid 是结果。

---

### 9.4 画板根 layout 会被自动注入「全屏底图」→ 常驻画板盖住整张地图

`html_to_y3_ui.py` 会给**每个 layout** 自动补一张 `<layout名>_bg` 背景图（实测 `image=906896`，半透明）。
画板**根 layout 就是 1920×1080**，于是凡「常驻显示」的画板（HUD / 背包 / 状态栏）都会各自叠一张全屏半透明底图，
表现是**选完英雄进对局后，整张地图像蒙了一层灰黑色遮罩**。

**规避**：常驻画板生成时加 `--strip-root-bg`（推荐），或生成后把**根 layout 的直接子节点**
`<画板名>_bg` 删掉（只删这一个节点、不动 uid，所以 ECA 的控件引用不受影响）；
内层面板自己的 `*_bg` 保留，弹窗仍有正常底板。批量处理可用
`y3-ui-pipeline/scripts/postprocess_panel.py --strip-root-bg MyHUD,MyItemBar`。

```python
root = data["children"][0]                                  # 画板根 layout
root["children"] = [c for c in root["children"]
                    if c.get("name") != panel + "_bg"]      # 只删根节点上的全屏底图
```

> 判断标准：这个画板在对局中是否**常驻**。全屏选择界面 / 加载界面保留根底图是对的（本来就要盖住地图）。

---

### 9.5 `data-event` 写在 `data-template` 宿主上不生效；一个控件只能声明一种 `event_list` 类型

- `<div data-template="skill" data-name="skill_slot_1" data-event="tip_1" data-event-type="24">`
  生成出来的 `event_list` 为空——**模板宿主的 `event_list` 由模板 JSON 决定**，宿主上的 `data-event` 被忽略
- 想同时挂「移入 24 / 移出 25」也做不到：`data-event="a,b"` 只能共用一个 `data-event-type`
- 做法：生成后用后处理直接往画板 JSON 的 `event_list` 追加（只动 `event_list`、不碰 uid，无需重导触发器）

```python
node.setdefault("event_list", []).append({
    "action_list": [], "enabled": True, "name": "skill_tip_hide",
    "not_wait_network": False, "sound_id": None, "type": 25,
})
```

- 顺带记录：`UI_COMP_EVENT_TYPE` 实测 `1=左键按下`、`2=点击`、`24=鼠标移入`、`25=鼠标移出`

---

## 10. 用脚本施法验证技能触发器时的三个坑

`hero:cast(技能, 目标)` 是验证技能触发器最快的手段，但「没效果」至少有三种互不相干的成因。
不先排掉施法侧的两个坑，就会把「这次根本没放出去」误判成「触发器 / 技能坏了」。

| 坑 | 现象（全程无报错） | 取证方法 |
|----|--------------------|----------|
| **施法者已死亡** | `cast()` 返回成功、无异常，**CD 与蓝量都不变**，触发器自然也不触发 | 施法前先读 `unit:is_alive()`。注意 **`unit:set_hp(N)` 只写血量、不会复活**（`is_alive()` 仍为 false）→ 一旦单位被打死，其后所有施法测试的结论全部作废（实测踩过：连测 3 轮全是假的） |
| **点目标技能（圆形指示器）脚本施法放不出去** | `hero:cast(ab, 点)` 返回成功，但 CD（14s）与蓝量（60）都没消耗 = 施法没发生 | 同一英雄横向对比：单位目标（`sight_type=4`）、自身（`sight_type=0`）两类技能脚本施法都真实生效并打出伤害，只有 `sight_type=3`（圆形指示器，取点）打不出 → **点目标技能的 ECA 效果只能人工手点验证**，别在脚本里反复试。`ab:get_skill_pointer()` / `ab:get_cd()` / `ab:get_range()` 可在脚本里读回技能的真实配置 |
| **探针变量被游戏逻辑覆盖** | 读回来的不是自己写的值，据此推理整条结论都偏 | 探针只写**游戏逻辑从不写**的变量（踩过雷：拿战斗逻辑自己维护的计数类变量当探针，读回来的是它的值）；写入值用魔数（如 `1234567`），读之前先确认它真的变了 |

> 推荐判定顺序：① `is_alive()` → ② 施法后 CD / 蓝量有没有变化（确认施法真的发生）→ ③ 才看伤害与效果。

---

### 10.1 补充：指示器类型决定「怎么取目标」，写错 = 技能在真实对局里静默零效果

§10 讲的是「脚本测不出来」，这里讲的是**技能本身真的没效果** —— 两者表现几乎一样
（不报错、`valid=true`、静态校验全绿），但成因不同。

**根因**：`指示器类型` 决定玩家选的是什么，触发器里**取目标的方式必须与之匹配**：

| `sight_type` | 玩家选什么 | 触发器里正确的取法 | 用错的后果 |
|---|---|---|---|
| 0 无目标 | — | 施法者自身 / 自身周围 AOE | — |
| 1 扇形 / 2 箭头 | **方向角** | **按方向做扇形范围选取**（见下） | 用 `TARGET_UNIT_IN_ABILITY` → 打空 |
| 3 圆形 | 一个点 | `ABILITY_RELEASE_POSITION(CUR_ABILITY)` 做点 AOE | 取不到点 → 打空 |
| 4 目标 | 一个单位 | `TARGET_UNIT_IN_ABILITY(CUR_ABILITY)` | — |
| 5 单位或地点 | 单位或点 | 两种情况都要处理 | 打空 |

> ⚠️ 这类 bug **不报错，只是「放下去什么都不发生」**；而且**同工程/参考实现也可能同样写错**
> （遇到过的参考实现里，同一类技能就是同样的错误写法）→ **不能盲信参考实现**，
> 交付技能前必须**每个指示器类型各放一次**。

**方向类技能的标准解法**（实测：施法方向前方掉血、身后不掉血）：

```jsonc
["PICK_UNIT_DO_ACTION",
 ["UNIT_LIST_IN_SHAPE", ["UNIT_ENTITY_POINT", ["ABILITY_OWNER"]],
  ["CONST_SECTOR_SHAPE_NEW", 700.0, 30.0, ["GET_ABILITY_RELEASE_DIRECTION", ["CUR_ABILITY"]]],
  {"op_arg": [null,null,null,null,null,null,null,["ABILITY_OWNER"],null,null,null,null,null,null,null]}],
 [["APPLY_DAMAGE", {"source": ["ABILITY_OWNER"], "ability": ["CUR_ABILITY"],
                    "target": ["FOR_EACH_SELECTED_UNIT"], "damage_type": 1,
                    "value": 90.0, "crit": true}]]]
```

- `GET_ABILITY_RELEASE_DIRECTION(技能)` 返回**角度制**（`y3/game/math.lua` 注明「均使用角度制」），
  可直接填进 `CONST_SECTOR_SHAPE_NEW` 的第 3 参（`ANGLE` 类型）；想更接近「一条直线」用 `CONST_RECTANGLE_SHAPE_NEW(宽, 长, 方向)`。
- `UNIT_LIST_IN_SHAPE` 的 `op_arg[7]` = 排除单位（通常填施法者，避免自伤）。

**脚本施法能力地图**（§10 只覆盖了两类，这里按实测补全）：

| `sight_type` | `hero:cast(技能, 点)` 能否真正触发 |
|---|---|
| 0 无目标 / 2 箭头 / 4 目标 | ✅ 可以（箭头类传点 = 指定方向） |
| 1 扇形 / 3 圆形 | ❌ 放不出去（返回成功但**不扣蓝、不触发**）→ 只能人工手点验证 |

**读「实体类全局变量」的时机**：技能有前摇（常见 0.2s）+ 后摇（0.5s），`ABILITY_SP_END` 约 **0.7 秒后**才触发。
所以施法**同一帧**立刻读（如读「特效实体」）必然是 `nil`，会误判成「特效没创建」；
正确做法是施法同一帧用 `y3.ctimer.wait(1.0~1.2, function() ... end)` 排定采样。

---

## 11. 「改了技能触发器文件，怎么让它生效」的实测边界

背景：`edit_trigger.py` 只写盘，不改编辑器内存。以前传下来的纪律是「改完必须
`restart_editor(save_before_restart=false)`，否则编辑器保存会把盘上的新内容顶回旧值」。
用「往某技能触发器的伤害里写 41 / 向某技能容器新增一个触发器，再看保存后盘上还剩什么」实测，结论要打折：

| 问题 | 实测结果 | 结论 |
|------|----------|------|
| `import_eca` 能不能热更物编（技能）触发器 | 传 `maps/EntryMap/ability/<key>.json` 直接被拒：`Error: 本工具仅支持全局触发器（路径需包含 global_trigger/trigger/）` | **不能**。物编触发器没有热更通道 |
| 普通 `save_editor` 会不会把盘上改过的技能触发器顶回旧值 | 4 次里 **1 次**顶回（盘 41 → 存成 40）、**3 次**保留盘上新内容（含「往容器里新增一个触发器」这种最该被顶回的情形） | 这条纪律**不是稳定行为**，不能当规则用。成因未查明（猜测与编辑器是否处于「脏」状态有关） |
| `hotfix_object_editor` 是不是物编触发器的热更入口 | 1 次正面观测（盘 41 → hotfix → 保存后仍是 41）；但因为上一条「保存不一定覆盖」，这一条**不能单独证明 hotfix 真的把文件读进了编辑器内存** | **未确证**，需要更硬的判据 |
| 游戏运行时读的是「盘上的触发器文件」还是「编辑器内存 / 导出物」 | 没测出来。设计过判据（在技能容器里挂一个「施放时把 `金币` 写成 `1234567`」的探针触发器，脚本施放自身技能后读 `金币`），两次都被环境干扰：英雄在波次里十几秒就死、`execute_lua` 中途无输出 | **未确证**。这是最值得接着测的一条——若游戏直读盘上文件，迭代就不必重启编辑器 |

**判据设计的经验**（下次接着测时直接抄）：

- 用**持久且不可能撞车的现象**当判据（`金币 = 1234567`），不要用「CD / 蓝量有没有变」——CD 会在等待期间自然转到 0，蓝量也会回满，读晚了什么也证明不了。
- 施法类判据必须和**对照组**同时跑：同一局里放一个已知可用的技能（自身范围类），用它的伤害证明「这一轮施法链路是通的」，否则分不清「探针没生效」和「这次根本没放出去」。
- 环境里英雄会被波次持续打死，任何超过 ~10 秒的观测窗口都要先 `set_hp(满血)` 并确认 `is_alive()`。

### 11.1 新增证据：编辑器**确实**会把 `ability/*.json` 写回磁盘

§11 表格里「普通 `save_editor` 会不会把盘上改过的技能触发器顶回旧值」当时的结论是
「4 次里 1 次顶回，不稳定」。一次对某工程**全部**技能触发器（20 个）的对比（脚本生成副本 vs 编辑器保存后的回读文件）给了更硬的证据：

- **20/20 文件都被编辑器改写**：每个文件的 `local_variable.<trigger_id>` 被补上
  `{"variable_dict": {}, "variable_length_dict": {}}`；计时器类动作被补上
  `local_var: {"__tuple__": true, "items": [{}, {}]}`。这些都是**编辑器自己的序列化产物**，
  证明它确实把技能触发器读进了内存、并在保存时按自己的格式写回。
- 所以「`save_editor` 会覆盖盘上改动」**是一条真实路径，不是偶发**；被覆盖的是
  「编辑器内存里没有的东西」（新增文件 / 新字段 / 新变量）。
- 推荐采用的顺序：**写盘 → `restart_editor(save_before_restart=false)`（让它重读盘）→ 再 `save_editor`**，
  中途**一次 `save_editor` 都不能有**。同一轮里补齐新增全局变量，重启一次同时载入变量与技能触发器。


## 12. 静默失效与参数口径速查（补充）

| 写法 | 现象 | 正确做法 |
|------|------|---------|
| 变量引用省略 `scope` 且名字是全局变量 | 生成 3 元组局部引用；`valid=false` 或引用不存在变量 | 生成器已改为“已声明全局默认 global”；故意遮蔽时显式写 `"scope":"local"` |
| `GROUP_ADD_UNIT` 写全局 `UNIT_GROUP` | 运行时 `get_trigger_variable_unit_group` 读回 0 | 用 `PLAYER_UNIT_GROUP` / `UNIT_TYPE_UNIT_GROUP`；自定义组先做探针 |
| `GENERIC_UNIT_EVENT + ET_UNIT_BORN` 用 `KILLED_UNIT` | 保存后整条 `valid=false` | 出生事件用 `GET_UNIT_FROM_EVENT` |
| `ET_UNIT_BORN` 里直接读单位坐标做占位判断 | 单位还没到最终坐标，邻近单位的判断会漏 | 延迟 0.25s 再判断；或直接依赖物编 `collision_points` 方格碰撞 |
| `FLOAT_TO_POINT` 与 `GET_POINT_DISTANCE` 混用 | 点坐标错位 / 距离判断差 100 倍 | `FLOAT_TO_POINT` 厘米、`GET_POINT_DISTANCE` 米；`ori_speed` 物编 m/s、运行时 cm/s |
| 单个父触发器注册 >6 个子触发器 | 后面的子触发器收不到控件事件 | 拆成多个父触发器 |
| 隐藏整个 `GameHUD` | 技能栏按钮一起消失 | 保留 `main.skill_list`，其余节点按 uid 隐藏 |
