# ECA 函数与触发器 JSON 拼接技能

## 概述

在 Y3 编辑器中生成**可见可编辑的正式 ECA 函数和全局触发器实例**。

> 不是 ECA 类型注册（那是 `custom_eca/custom_eca.json` 的职责），也不是 AI/NLP 映射修正（那是 `ExternalResource/readable_eca/*.json`）。

**脚本清单**（均在技能同目录 `<agent>/skills/eca-json-builder/` 下）：

| 脚本 | 子命令 | 说明 |
|------|--------|------|
| `eca_json_helper.py` | `template` / `validate` / `merge` / `normalize-desc` | 触发器生成与校验，零依赖 |
| `lookup.py` | `--global-events` / `<eca_name>` | 基于内建 `eca_index.json` 查找，**零依赖** |
| `gen_function.py` | 函数 DSL 文件 / `--dry-run` | 生成项目 ECA 函数并更新函数索引，零依赖 |
| `gen_trigger.py` | 触发器 DSL 文件 / `--dry-run` | 生成项目全局触发器并更新触发器索引，零依赖 |

```bash
py -3 <agent>\skills\eca-json-builder\eca_json_helper.py template trigger_instance
py -3 <agent>\skills\eca-json-builder\eca_json_helper.py template function_instance
py -3 <agent>\skills\eca-json-builder\lookup.py <eca_name>
```

---

## 外部依赖

**零依赖可独立生效。** 所有脚本仅需 Python 3 标准库 + 内建 `eca_index.json`。

### 参数类型 ID 数据（`eca_source_data.json`）

`eca_index.json` 只有参数类型的**名字**，没有 **arg_type ID**；ID 写错时编辑器不报错，
只在保存时把参数清成 `null` 或让触发器 `valid=false`。因此 ID 表由
`eca_source_data.json` 提供（类型名→ID、sub_type 表、各类型 flags、变量读取 sub_type）。

| 角色 | 需要编辑器源码？ | 做什么 |
|------|----------------|--------|
| 维护者 | 是 | `sync_from_source.py --src <engine>` 派生一次，随包分发该 JSON |
| **使用者** | **否** | 只读随包 JSON；用 `harvest_from_project.py --project .` 拿自己工程自校验/补全 |

该 JSON 缺失时会退回内置手写表（条目更少，取值已按源码校正），未覆盖类型**直接报错**而非静默损坏。

产物**已脱敏**：只含 `sha256` 与计数，不含引擎源码根路径与源码文件清单
（`--include-source-paths` 仅供维护者本地排查，带路径的产物禁止分发）。
`_source.data_version` 供维护者标记数据批次。

### 常用全局事件速查

> ⚠️ `event_type` 必须使用下表第一列的**确切名称**，不可自创。用 `lookup.py` 验证。

| event_type | sub_type | Args | 说明 |
|---|---|---|---|
| `INIT_FINISHED` | t_system | 无 | 游戏初始化 |
| `GAME_PAUSE` | t_system | 无 | 游戏暂停 |
| `GAME_RESUME` | t_system | 无 | 游戏恢复 |
| `ANY_ROLE_JOIN_GAME` | t_player | 无 | 玩家加入 |
| `ROLE_ACTIVE_EXIT_GAME_EVENT` | t_player | 无 | 玩家退出 |
| `ROLE_INPUT_MSG` | t_player | STRING(100003) | 玩家发送指定消息（全字匹配） |
| `ON_BROADCAST_MSG` | t_system | STRING(100003) | 接收广播事件 |
| `ON_CLICK_MINI_MAP_PANEL` | t_ui | MOUSE_KEY_WITHOUT_MIDDLE(200224) | 点击小地图 |

```json
// 无参事件
{"event_type": "GAME_PAUSE", "args_list": [], ...}

// 有参事件: arg_type 用括号内整数, sub_type=1
{"event_type": "ROLE_INPUT_MSG", "args_list": [
  {"arg_type": 100003, "sub_type": 1, "args_list": ["-hello"]}
], ...}
```

---

## 全局触发器 vs 物编触发器

**事件由 `sub_type` 决定归属于哪种触发器系统：**

| sub_type | 触发器类型 | 示例事件 |
|---|---|---|
| `t_system` | 全局 | `GAME_PAUSE`, `GAME_RESUME`, `INIT_FINISHED`, `ON_BROADCAST_MSG` |
| `t_player` | 全局 | `ANY_ROLE_JOIN_GAME`, `ROLE_ACTIVE_EXIT_GAME_EVENT`, `SELECT_UNIT`, `ROLE_INPUT_MSG` |
| `t_ui` | 全局 | `ON_CLICK_MINI_MAP_PANEL` |
| `t_click` | **全局** | `KEYBOARD_KEY_DOWN_EVENT`, `KEYBOARD_KEY_UP_EVENT`, `MOUSE_KEY_DOWN_EVENT` |
| `t_unit` | **物编-单位** | `UNIT_DIE`, `UNIT_BORN`, `UNIT_BE_HURT` |
| `t_ability` | **物编-技能** | `GLOBAL_ABILITY_EVENT`（包装 `ABILITY_PS_START` 等） |
| `t_item` | **物编** | `ITEM_BROKEN` |

> ⚠️ **物编触发器不能放在 `global_trigger/` 中。** 物编单位触发器路径为 `maps/<地图名>/unit/<单位Key>.json`，事件直接写 `UNIT_DIE`（不包裹 GENERIC_UNIT_EVENT），格式见下文。

用 `lookup.py` 可确认事件的 sub_type：
```bash
py -3 <agent>\skills\eca-json-builder\lookup.py GAME_PAUSE
# sub_type: "t_system"  ← 全局可用

py -3 <agent>\skills\eca-json-builder\lookup.py UNIT_DIE
# sub_type: "t_unit"    ← 仅物编可用

py -3 <agent>\skills\eca-json-builder\lookup.py --global-events
# 列出所有全局可用事件
```

---

## UI 事件触发器（必须用「父触发器 + 子触发器」）

**实测结论**：`TRIGGER_COMPONENT_EVENT` 只有写成**子触发器**（由 `INIT_FINISHED` 父触发器用裸整数注册）才会生效，写成普通顶层触发器收不到事件。

```jsonc
// 父触发器：事件 INIT_FINISHED；动作里用裸整数注册各子触发器
// DSL: {"register_sub_trigger": "卡片点击"} → 输出为裸整数子触发器 ID
{
  "trigger_name": "某界面-UI事件注册",
  "trigger_id": 1718000030,
  "event": [{"event_type": "INIT_FINISHED", "element_id": 1718000030000001, "enable": true, "args_list": []}],
  "action": [
    1718000031,                       // 裸整数 = 注册子触发器
    {                                  // 同时注册控件事件
      "action_type": "CREATE_UI_COMP_EVENT_EX_EX",
      "args_list": [
        {"arg_type": 100070, "sub_type": 1, "args_list": ["<控件uid>"]},
        {"arg_type": 100072, "sub_type": 1, "args_list": [2]},
        {"arg_type": 100003, "sub_type": 1, "args_list": ["card_click"]}
      ],
      "op_arg": [null, null], "op_arg_enable": [false, false]
    }
  ],
  "sub_trigger": {
    "1718000031": {
      "trigger_name": "卡片点击",
      "trigger_id": 1718000031,
      "p_trigger_id": 1718000030,
      "is_conf": true, "enabled": false, "valid": true,
      // 事件参数必须用官方求值 STR_TO_UI_EVENT("<名字>")
      "event": [{
        "event_type": "TRIGGER_COMPONENT_EVENT",
        "element_id": 1718000031000001,
        "enable": true,
        "args_list": [{
          "arg_type": 100067, "sub_type": "STR_TO_UI_EVENT",
          "args_list": [{"arg_type": 100003, "sub_type": 1, "args_list": ["card_click"]}]
        }]
      }],
      "action": [],
      "var_data": [{}, {}, []]
    }
  }
}
```

要点：

1. 控件用 **uid 字符串**寻址；`UI_COMP_EVENT_TYPE` 是**整数**（`1` 左键-按下、`2` 点击、`24`/`25` 鼠标移入/移出）。
2. 处理器里用 `TRIGGER_PLAYER` 取触发玩家、`GET_UI_COMP_FROM_EVENT` 取控件、`GET_UI_COMP_NAME(玩家, 控件)` 判断是哪个控件。
3. 含 `sub_trigger` 的文件**同样用 `import_eca` 加载** —— 实测当前编辑器版本 `新建`/`覆盖` 都不会丢子触发器与裸整数注册 ID（见「子触发器加载实测」一节），加载后等 3 秒 `save_editor` 再用 `diff` 校验即可。
   （若某版本上确实出现「`success=true` 但保存后子触发器消失」，才退回 `restart_editor(save_before_restart=false)` 加载；注意该重启会打脏编辑器会话，必须再补一次默认的 `restart_editor(save_before_restart=true)`，否则 `y3helper` 启动游戏会卡在 loading 30%。）
4. `y3runtime.trigger_ui_touch_event_by_path` **驱动不了 ECA 的 UI 事件**（只能触发 Lua 监听），所以 UI 用例不能靠它自动验证，必须人工点击。

### 子触发器加载实测

**`import_eca` 可以导入含 `sub_trigger` 的文件。** 旧文档「含 `sub_trigger` 禁止用 `import_eca`、必须重启加载」的说法在当前编辑器版本**不成立**。

受控实验（同一文件含 2 个子触发器：`TRIGGER_COMPONENT_EVENT` 与 `GENERIC_UNIT_EVENT` 各一，另有 2 个裸整数注册 ID）：

| 场景 | 操作 | 结果 |
|------|------|------|
| 新建 | `import_eca`（mode=新建）→ 等 3 秒 → `save_editor` | `diff 生成副本 vs 回读` = OK；`sub_trigger` 2 个、裸整数注册 2 个、`is_conf=true`/`enabled=false`/`p_trigger_id` 全保留 |
| 覆盖 | 子触发器动作值 1→2 后重新生成 → `import_eca`（mode=覆盖）→ 保存 | 同上，且新值已生效落盘 |

标准流程：`scan` → `gen_trigger` → `import_eca`（逐个串行）→ 等 3 秒 → `save_editor` → `diff` 校验。

## 项目正式 ECA 函数

**路径**：`maps/<地图名>/global_trigger/function/<函数名>.json`

项目 ECA 函数不是 `custom_eca/custom_eca.json` 中的类型注册。它是编辑器可见、可被
`CALL_TRIGGER_FUNC` 调用的函数实例，必须同时满足：

- `is_func=true`，`event=[]`，并声明 `func_id`、`func_name`、`func_category`。
- 参数写入 `func_param_list`，参数类型由同名局部变量在 `var_data` 中的分组决定。
- 每个参数名还必须在 `func_des` 中以 `{参数名}` 占位符出现，并放在调用文本的语义位置；
  例如 `通过口令加入私人副本{副本口令}，返回请求受理结果`。生成器遇到缺失占位符时直接报错。
- 返回值同时写入 `func_return`、`func_rtv_name_list`，并通过数值动作 `400342` 返回。
- 文件名写入同目录 `index.txt`；调用方通过稳定的 32 位十六进制 `func_id` 关联。

### 函数 DSL

```json
{
  "map": "EntryMap",
  "functions": [
    {
      "name": "大厅服务 - 设置匹配分数",
      "description": "更新当前玩家的匹配分数为{分数}",
      "params": [
        {"name": "分数", "type": "INTEGER", "required": true}
      ],
      "returns": [
        {"name": "result", "type": "TABLE", "var": "t"}
      ],
      "lua_bind": true
    }
  ]
}
```

```bash
# 只生成到标准输出，不写项目
py -3 <agent>\skills\eca-json-builder\gen_function.py <函数DSL.json> --dry-run

# 写入 DSL 中指定的地图
py -3 <agent>\skills\eca-json-builder\gen_function.py <函数DSL.json>

# 同一份函数定义写入另一张地图；自动 ID 在不同地图中保持一致
py -3 <agent>\skills\eca-json-builder\gen_function.py <函数DSL.json> --map MapName001

# 校验生成结果
py -3 <agent>\skills\eca-json-builder\eca_json_helper.py validate \
  "maps/EntryMap/global_trigger/function/大厅服务 - 设置匹配分数.json"
```

`lua_bind=true` 会生成以下函数体：

1. `SET_VARIABLE` 把 `Eval_Lua_<返回类型>` 的结果写入局部返回变量。
2. Lua 代码调用 `Bind['函数名'](args[1], ...)`。
3. 函数参数按 ECA 类型写入 5 个 `op_arg` 槽并启用对应位置。
4. 数值动作 `400342` 返回局部变量。

当前 `lua_bind` 模式支持恰好一个返回值，参数最多 5 个；超出限制会直接报错，不生成
可能被编辑器错误解释的 JSON。省略 `func_id`/`id` 时会按函数名生成稳定 ID；同名函数写入
多张地图会得到相同 ID。已有调用方依赖某个历史 `func_id` 时，应在 DSL 中显式保留该 ID。

`actions` 可以给函数追加普通 ECA 动作（语法与触发器的 `action` 完全一致，
复用 `gen_trigger.build_action_list` 编译）：

```json
{
  "name": "竞技场 - 结算奖励",
  "description": "给{玩家}发奖励",
  "params": [{"name": "玩家", "type": "PLAYER", "required": true}],
  "actions": [
    ["SET_VARIABLE", {"var": "临时积分", "type": "INTEGER", "scope": "local"}, 100]
  ]
}
```

- 动作按「`lua_bind` 生成的赋值动作 + `actions`」顺序拼接；不用 `lua_bind` 时，
  `actions` 就是整个函数体。
- `actions` 里引用的局部变量会自动写进 `var_data`，不用另建声明表。
- 函数没有事件，`actions` 只在函数被调用时执行；要按帧 / 定时跑仍然用触发器。

### 在触发器 DSL 中调用函数

```json
{
  "call_function": {
    "func_id": "a1377fd18bfb11f1b9d919bc08ffd172",
    "args": [
      {"type": "INTEGER", "value": 1000}
    ],
    "returns": [
      {"var": "立即结果", "type": "TABLE"}
    ]
  }
}
```

生成器会自动创建 `CALL_TRIGGER_FUNC`、`call_rt_arg_idxes`、返回变量接收槽，以及触发器的
局部 `var_data` 声明。可选参数放在 `optional_args`；用 `null` 表示该槽不启用。

### TABLE 参数的编辑器兼容结构

编辑器手写样本确认，`TABLE` 参数不能把普通 JSON 对象或列表直接写成
`{"arg_type":100011,"sub_type":1,"args_list":[{...}]}`。这种结构虽然是合法 JSON，
但编辑器无法反序列化，会导致触发器不显示并在保存时失败。

生成器遇到函数调用中的一层 TABLE 字面量时，必须展开为以下动作序列：

1. `SET_VARIABLE + GET_NEW_TABLE` 创建局部 TABLE。
2. 使用 `SET_TABLE_VALUE_1D` 写入键值；列表使用编辑器样本支持的表插入动作。
3. `CALL_TRIGGER_FUNC` 传入 `arg_type=100011, sub_type="VARIABLE"` 的局部 TABLE 变量。
4. 临时 TABLE 和返回 TABLE 都必须登记在所属触发器的 `var_data` 中，包括嵌套 `ACTION_LIST` 内创建的变量。

当前不推测嵌套 TABLE 字面量的序列化格式；需要嵌套表时，应先显式声明并构造子 TABLE，
再把子 TABLE 变量写入父 TABLE。校验器会拒绝残留的普通 JSON 对象/列表 TABLE 字面量。

---

## 生成后加载到 Y3 编辑器

项目函数是触发器的依赖，必须先进入编辑器函数表，再加载引用它们的触发器。当前
Y3 Editor MCP 的 `import_eca` 只接受 `global_trigger/trigger/` 路径，因此函数加载需要通过
重新打开地图完成。

当前地图已在编辑器中打开时，使用以下顺序：

1. 在生成任何新 JSON 前调用 `y3editor.save_editor()`，先保存用户当前编辑器修改。
2. 运行 `gen_function.py`，写入并校验全部函数 JSON 和 `function/index.txt`；核对索引数、
   文件数以及调用方使用的稳定 `func_id`。
3. 函数写入后**不要再保存编辑器**。此时编辑器内存仍是旧函数表，调用 `save_editor` 会把
   刚写入的函数文件和索引覆盖掉。
4. 调用 `y3editor.restart_editor(save_before_restart=false)`，等待原地图重新打开。重启前的
   保存必须已经在步骤 1 完成；这里禁止再次保存旧内存。
5. 地图打开后重新核对函数文件和索引。此时函数加载完成；不含 `sub_trigger` 的普通触发器
   再逐个、串行调用 `import_eca` 加载。
6. 动态 `sub_trigger` 使用技能测试目录中的编辑器实际保存样本做整表回归比对，可以由
   `gen_trigger.py` 写入。此类文件禁止用 `import_eca` 覆盖加载；写入后使用“不保存旧内存重启”，
   重开后保存一次，并确认 `sub_trigger` 与裸整数注册 ID 仍完整。

当前 MCP 没有独立的 `open_map` 工具。目标地图原本未打开时，不得臆造 MCP 调用；完成函数
生成后，通过编辑器已有入口打开目标地图，然后从步骤 5 继续。

```text
y3editor.import_eca(
  trigger_json_path="D:/.../maps/EntryMap/global_trigger/trigger/示例.json"
)
```

触发器加载规则：

1. 函数加载阶段完成后，再逐个、串行调用 `import_eca`，不要并发修改编辑器触发器树。
2. 以返回值中的 `success=true` 作为编辑器受理依据，并保留 `mode`、`trigger_id`、
   `hotfix_status` 作为验证证据。
3. `hotfix_status=已推送` 表示已同步到当前运行时；若为
   `未连接（仅编辑器侧已更新）`，编辑器加载仍成功，但新开或重启游戏后才会运行完整的新逻辑。
4. 当前工具参数明确要求路径包含 `global_trigger/trigger/`，因此不能用它导入
   `global_trigger/function/` 下的函数 JSON。不得使用路径跳转或把函数临时复制到触发器目录；
   这会绕过工具边界并可能破坏函数分组或 `func_id`。
5. **含 `sub_trigger` 的文件同样用 `import_eca` 加载**（受控实验：`新建`/`覆盖` 两种模式
   都完整保留子触发器与裸整数注册 ID）。加载后等 3 秒 `save_editor`，再用
   `eca_json_helper.py diff` 校验未被丢弃。仅当 diff 真的报出丢失时，才退回“不保存重启”流程，
   并补一次默认的（先保存）重启恢复编辑器会话。

### ⚠️ 批量导入 / 删除 / 时序的三个坑

| 坑 | 现象 | 正确做法 |
|----|------|---------|
| **保存会「裁剪」未导入的触发器** | `save_editor` 以**编辑器内存**为准写回：磁盘上存在但没 `import_eca` 过的触发器文件会被**删除**，`index.txt` 条目也会被移除 | 批量新增：先 `save_editor` 落盘编辑器当前修改 → 再生成文件 → **逐个 import 完再统一保存**（中途不要保存） |
| **保存后立刻导入会被丢弃** | `import_eca` 返回的不是 JSON（`payload=None`），触发器没进编辑器，随后保存时被裁剪 | 保存后等 1~3 秒再导入；`verify_trigger.import_trigger()` 已内置该等待并把「未返回 success」直接报错 |
| **删除触发器要连编辑器内存一起清** | 只删磁盘文件 + index，编辑器下次保存会把它**原样恢复**（俗称“复活”，含 index 条目） | 真删除：`edit_trigger.py --delete` 之后补 `restart_editor(save_before_restart=false)` 让编辑器忘掉它 |

一键闭环（把上面这些时序都封装好了）：

```bash
py -3 verify_trigger.py "触发器名"      # lint → 导入 → 保存×2 → 回读 diff → valid
py -3 verify_trigger.py --all           # 批量回归
```

---

## ✅ 写法校验：编辑器不认的写法会被静默清成 null

编辑器**不会**对不认识的参数报错，而是在 `save_editor` 时把它**清成 `null`**（或替换成默认值）。已实测踩坑的三种：

| 写法 | 编辑器保存后 | 后果 |
|------|-------------|------|
| `GENERIC_UNIT_EVENT` 参数 `sub_type` 写整数 `1` | `"args_list": [null]` | 触发器静默失效 |
| 全局变量引用写 3 元组 `["INTEGER","金币","global"]` | 参数变 `null` | 界面标红「无效的变量」 |
| 全局变量读取 `sub_type` 写错（如 `BOOLEAN` 写 `2`） | 参数变 `null` 或被替换成字面量 | 条件恒不成立 |
| `SET_VARIABLE <UNIT_ENTITY变量> = 0` | 参数变 `null` | 清空变量失败 |

**标准校验流程**（写完触发器必做）：

```bash
1. eca_json_helper.py scan <trigger目录>   # 索引一致性 + 哪些文件含 sub_trigger + 写法 lint
2. gen_trigger.py <dsl.json>               # 生成，并留一份生成结果副本
3. import_eca（逐个串行；含 sub_trigger 的文件同样可用）
4. 等 3 秒 → save_editor
5. eca_json_helper.py diff <生成副本> <回读文件>   # 比对（忽略 element_id 与键序）
   → OK = 写法合法；列出差异 = 有节点被清成 null / 被改写，必须换
```

> 比对脚本思路：`gen_trigger.py --dry-run` 拿到「生成结果」，与磁盘文件递归对比；编辑器会重排键序，所以比较前要 `json.dumps(sort_keys=True)` 归一化。

**不知道某类型变量/某事件该写什么时，用探针法问编辑器**：把几种候选写法各放一个条件/动作里 → `import_eca` → `save_editor` → 回读，活下来的就是正确答案。

> ⚠️ **`import_eca` 只更新编辑器的编辑态，不影响运行时**：运行时在**启动游戏**时才读取编辑器当前状态，`hotfix_status=未连接（仅编辑器侧已更新）` 是正常现象。要验证逻辑是否真的跑起来，必须**重启游戏**后查运行时状态。
>
> 📌 **PRINT 打印落在哪**：`PRINT_MESSAGE_ACTION_TO_DIALOG` → `y3.print_to_dialog`，输出写进
> **触发器日志** `LocalData/trigger_log/<地图名>/Log/<玩家名>_<日期_时间>.log`
> （`DIALOG_DEBUG_TYPE`：1=Error / 2=Warning / 3=Info）；`y3helper.get_logs` 读的是**客户端 Lua 日志**，所以看不到它。
> 打印是有效手段，只是要看对文件；**执行期报错不落盘**，静默失效类问题仍需状态探针（`GameAPI.get_trigger_variable_*`）。

---

## 触发器结构

### 顶层

```json
{
  "trigger_name": "新建触发器",
  "trigger_id": 1635176449,
  "p_trigger_id": null,
  "group_id": 0,
  "enabled": true,
  "valid": true,
  "call_enabled": true,
  "event": [...],
  "condition": [...],
  "action": [...],
  "var_data": [{}, {}, []]
}
```

| 字段 | 说明 |
|---|---|
| `trigger_name` | 编辑器中显示的名称 |
| `trigger_id` | 唯一 ID（建议用时间戳 int） |
| `p_trigger_id` | 父触发器 ID，顶级为 `null` |
| `group_id` | 分组 ID，0=根 |
| `event` | 事件列表，支持 OR 关系 |
| `condition` | 条件列表，支持 AND 关系 |
| `action` | 动作列表，顺序执行 |
| `var_data` | 局部变量数据 `[{}, {}, []]` 即可 |

### Event 节点

```json
{
  "event_type": "INIT_FINISHED",
  "args_list": [],
  "element_id": 1635176449000002,
  "enable": true
}
```

`event_type` 用字符串名（与 `trigger_new.py` 中 key 一致）。

### Condition 节点

```json
{
  "condition_type": "TYPE_COMPARE",
  "args_list": [<arg> ...],
  "element_id": 1635176449000003,
  "enable": true
}
```

### Action 节点

```json
{
  "action_type": "PRINT_MESSAGE_ACTION_TO_DIALOG",
  "args_list": [<arg> ...],
  "op_arg": [<arg> ...],
  "op_arg_enable": [false],
  "element_id": 1635176449000005,
  "enable": true,
  "bp": false
}
```

### Arg 节点

```json
{
  "arg_type": 100003,
  "sub_type": 1,
  "args_list": [<arg> ...]
}
```

> ⚠️ `arg_type` 用**整数 ID**；`sub_type` 对基础类型也是整数（如 `1`），对复合/函数类型是**字符串**（如 `"FLOAT_TO_POINT"`, `"KILLED_UNIT"`）。

`args_list` 元素类型：
- **dict**：嵌套 Arg 节点
- **int**：子触发器引用
- **str / float / null**：字面值

---

## ⚠️ 关键规则（源于实测修正；生成器已按这些规则加了守卫）

### 规则1：GENERIC_UNIT_EVENT 参数用 ET_ 前缀

事件名在 `args_list` 中必须加 `ET_` 前缀，对应 `trigger_new.py` 中的枚举名：

```json
// ❌ 错误
{"arg_type": 100008, "sub_type": 1, "args_list": ["ET_UNIT_DIE"]}

// ✅ 正确（sub_type 必须写成事件名本身）
{"arg_type": 100008, "sub_type": "GENERIC_UNIT_EVENT", "args_list": ["ET_UNIT_DIE"]}
```

> ⚠️ **这是最容易踩的坑**：`sub_type` 写成整数 `1` 时，编辑器**不报错**，但 `save_editor` 会把整个参数**清成 `null`**（变成 `"args_list": [null]`），触发器从此静默失效 —— 文件看起来还在，事件却是空的。
> 规律：**包装类事件**（事件名与参数类型名相同，如 `GENERIC_UNIT_EVENT`）的参数 `sub_type` 一律写该名称字符串。`gen_trigger.py` 已按此规则生成。

### 规则1b：包装类事件的事件名在 DSL 里要写成**字符串**，不是数组

`build_event` 对包装类事件（`ft == name`）是把 DSL 传进来的值**原样包一层**放进 `args_list`：

```python
# DSL 写法与产物
["GENERIC_UNIT_EVENT", "ET_UNIT_DIE"]      -> args_list: ["ET_UNIT_DIE"]      ✅
["GENERIC_UNIT_EVENT", ["ET_UNIT_DIE"]]    -> args_list: [["ET_UNIT_DIE"]]    ❌
```

> ⚠️ **实测**：写成数组的后果不是「这个触发器失效」，而是
> **整个工程保存失败**。编辑器保存时会重新校验所有触发器 →
> `TriggerArg.check_arg_name` → `ConstList.check_prefab_name('generic_unit_event', ['ET_UNIT_DIE'])`
> → `value in <set>` → `TypeError: cannot use 'list' as a set element (unhashable type: 'list')`
> → 保存抛出未捕获异常，编辑器会话变脏、之后每次保存都失败。
>
> 最坑的是**四道静态检查全都拦不住**：`--dry-run` 通过、`import_eca` 返回 `success=true`、
> 往返 `diff` 一致（编辑器就是按你给的形状存下来的）、`audit_triggers.py` 也报 `valid=true`
> （`valid` 是在保存路径的 `update_valid` 里才算的，静态审计看不到）。
> `gen_trigger.py` 现在已在该分支加字符串校验，误写会直接报错。

常用事件名（`ET_` 格式）：
| 事件 | ET_ 格式 |
|---|---|
| 单位死亡 | `ET_UNIT_DIE` |
| 单位即将死亡 | `ET_BEFORE_UNIT_DIE` |
| 单位出生 | `ET_UNIT_BORN` |

### 规则2：有 op_param 的元素必须显式填 op_arg / op_arg_enable

当 ECA 的 `op_param`（`o` 字段）不为空时，即使不填可选参数，也必须提供 `op_arg` 和 `op_arg_enable` 数组，长度与 `op_param` 一致。

> **⚠️ 两层位置**：
> - **功能子类型 Arg 节点**：当函数（如 `CREATE_UNIT`）有 op_param 时，`op_arg`/`op_arg_enable` 挂在该 Arg 上
> - **Action/Event/Condition 节点**：当动作/事件/条件本身有 op_param 时，`op_arg`/`op_arg_enable` 挂在顶层节点上（如 `NEW_CAMERA_SET_FOLLOW_UNIT`）

```json
// SET_VARIABLE 的 args_list[1] 是 CREATE_SFX_ON_POINT（有7个op_param），写法：
{
    "arg_type": 100148,
    "sub_type": "CREATE_SFX_ON_POINT",
    "args_list": [
        {"arg_type": 100066, "sub_type": 1, "args_list": [0]},
        {"arg_type": 100004, "sub_type": "UNIT_ENTITY_POINT", "args_list": [...]}
    ],
    "op_arg": [
        null, null, null, null,
        {"arg_type": 100001, "sub_type": 1, "args_list": [true]},
        {"arg_type": 100001, "sub_type": 1, "args_list": [true]},
        {"arg_type": 100001, "sub_type": 1, "args_list": [true]}
    ],
    "op_arg_enable": [false, false, false, false, false, false, false]
}
```

> 规律：`null` = 无默认值的可选参数；`{arg_type, sub_type, args_list}` = 有默认值的可选参数（enable=false 表示使用默认值）。

Action 级别示例（NEW_CAMERA_SET_FOLLOW_UNIT 有4个 op_param）：
```json
{
    "action_type": "NEW_CAMERA_SET_FOLLOW_UNIT",
    "args_list": [
        {"arg_type": 100025, "sub_type": 1, "args_list": [1]},
        {"arg_type": 100006, "sub_type": 11, "args_list": [{"__tuple__": true, "items": ["UNIT_ENTITY", "unit", "local"]}]}
    ],
    "op_arg": [null, null, null, null],
    "op_arg_enable": [false, false, false, false]
}
```

---

### 规则3：参数形状必须与定义一致（个数 + 易错动作具名）

> **实测代价**：某实战工程里，20 个技能触发器全部 `valid=true`、四道静态检查全绿，
> 运行时却**一点伤害都打不出来，伤害全落在施法者身上** —— `APPLY_DAMAGE` 的第 0 槽（伤害所属）
> 和第 2 槽（受伤目标）写反了。两槽**静态类型相同**（都是 `UNIT_ENTITY`），类型校验抓不到。

**为什么必须查 `cont`，而不是查文档**：`eca_index.json` 里每个动作都有一条 `cont` 模板，
里面的 `{#n}` **就是 `args_list` 的下标**。例如：

```
APPLY_DAMAGE  cont = 对{#2}造成{#3}类型的{#4}伤害，{#5}跳字，伤害所属{#0}所属{#1}[, ...]
             p    = [UNIT_ENTITY, ABILITY, [UNIT_ENTITY,ITEM_ENTITY,DESTRUCTIBLE_ENTITY],
                     DAMAGE_TYPE, [FLOAT,INTEGER], BOOLEAN]
```

两下一对就清楚了：**第 0 槽是「伤害所属」（伤害算在谁头上），第 2 槽才是「受伤目标」（谁掉血）**。
文档里的参数顺序属于二手转写，可能过时或写错；`cont` 是随索引一起导出的**一手依据**。

生成器现在提供 `describe_action(name, idx_data)`：任何参数相关报错都会把
「位置 → 类型」清单 + `cont` 一起打出来，不用再去翻索引。

**三道生成期守卫**（`gen_trigger.py`，写错直接报错、不落盘）：

| 守卫 | 规则 | 不拦的后果 |
|------|------|-----------|
| 个数（动作） | 位置参数个数必须等于 `len(p)` | 少传 → 后面的参数**整体前移错位**；多传 → 被编辑器静默丢弃（实测 `STR_JOIN` 第 3 段、`SET_UI_COMP_BIND_ATTR` 第 5 参都栽过） |
| 个数（嵌套调用） | 函数式参数位同样校验（`build_arg`） | 同上；错误信息里给出该函数声明的参数清单 |
| **具名（易错动作）** | 列在 `KEYWORD_ONLY_ACTIONS` 里的动作**禁止位置写法**，必须具名传参 | 参数类型相同的槽位写反 → 静默失效、行为相反 |

```python
# ✅ 具名写法（易错动作唯一允许的写法；键顺序按 p 展开，写少写多都会报错）
["APPLY_DAMAGE", {"source": ["ABILITY_OWNER"], "ability": ["CUR_ABILITY"],
                  "target": ["FOR_EACH_SELECTED_UNIT"], "damage_type": 1,
                  "value": 200.0, "crit": False}]

# ❌ 位置写法 —— 生成器直接报错（并打印上面那条 cont 与参数清单）
["APPLY_DAMAGE", ["FOR_EACH_SELECTED_UNIT"], ["CUR_ABILITY"], ["ABILITY_OWNER"], 1, 200.0, False]
```

> **新增易错动作**：把动作名按 `p` 顺序的槽位名（取自 `cont`）加进 `KEYWORD_ONLY_ACTIONS` 即可，
> 并在注释里写明证据（哪次实测、什么现象）。

**顺带一条**：**动作位不支持可选参数**。末尾直接写 `{"op_arg": ...}` 会被当成多出来的位置参数，
现在会报错并给出替代写法 —— 可选参数只能写在**函数式参数位**（嵌套在别的参数表达式里）：

```python
["SET_VARIABLE", {"var": "护盾实例", "type": "MODIFIER_ENTITY", "scope": "global"},
 ["ADD_MODIFIER", ["ABILITY_OWNER"], 900006,
  {"op_arg": [["ABILITY_OWNER"], ["CUR_ABILITY"], 15.0]}]]
```

## Arg 类型 ID 速查（来源：const_name.py）

> ⚠️ 以下 ID 均来自引擎源码 `engine/dm/commons/black_box/consts/const_name.py`，是唯一权威来源。

| ID | 名称 | 说明 |
|---|---|---|
| `100000` | `FLOAT` | 实数（字面量） |
| `100001` | `BOOLEAN` | 布尔 |
| `100002` | `INTEGER` | 整数 |
| `100003` | `STRING` | 字符串 |
| `100004` | `POINT` | 点（复合类型，需嵌套函数） |
| `100006` | `UNIT_ENTITY` | 单位实体 |
| `100008` | `GENERIC_UNIT_EVENT` | 通用单位事件（全局触发器捕获任意单位事件） |
| `100009` | `RECTANGLE` | 矩形区域（区域实体，非形状） |
| `100011` | `TABLE` | 数组参数 |
| `100015` | `COMPARISON_OPERATOR` | 比较运算符（"==", "!=", ">", "<", ">=", "<="） |
| `100022` | `ACTION_LIST` | 动作列表（嵌套动作节点） |
| `100025` | `PLAYER` | 玩家 |
| `100026` | `UNIT_GROUP` | 单位组 |
| `100046` | `MODIFIER_KEY` | 魔法效果类型 |
| `100066` | `SFX_KEY` | 特效资源Key |
| `100211` | `CIRCULAR_SHAPE` | 圆形形状（用 `CONST_CIRCULAR_SHAPE` sub_type，配合 `UNIT_LIST_IN_SHAPE`） |
| `100075` | `STATE` (BATTLE_STATE) | 单位状态枚举 |
| `100116` | `UNIT_NAME` (UNIT_KEY) | 单位类型ID |
| `100148` | `SFX_ENTITY` | 特效实体 |
| `100175` | `DIALOG_DEBUG_TYPE` | 打印对话框调用方 |
| `100225` | `ANGLE` | 角度 |
| `200220` | `KEYBOARD_KEY` | 键盘按键（整数值，见 KeyboardKey 常量） |
| `200224` | `MOUSE_KEY_WITHOUT_MIDDLE` | 鼠标按键（排除中键，0=左键 1=右键） |
| `100070` | `UI_COMP` | UI 控件（`sub_type=1` + uid 字符串） |
| `100067` | `UI_EVENT` | UI 事件（配合 `STR_TO_UI_EVENT("名字")`） |
| `100072` | `UI_COMP_EVENT_TYPE` | UI 控件事件类型（整数值） |
| `1001555` | `UI_COMP_ATTR` | 控件属性（`text_bind` / `current_value_bind` / `max_value_bind`） |
| `100041` | `UNIT_ATTRIBUTES` | 单位属性（`hp_cur` / `hp_max` / `mp_cur` / `mp_max` …） |

> ⚠️ **两个同名枚举的坑（实测）**：属性名在**绑定**和**取值**两条路上用的是**不同的枚举**：
>
> | 用途 | 动作 | 属性名从哪来 | `hp_cur` |
> |------|------|--------------|----------|
> | **绑定**控件/进度条 | `SET_UI_COMP_BIND_ATTR(玩家, 控件, "current_value_bind", "hp_cur")` | `UNIT_ATTRIBUTES`(100041) | ✅ 有 |
> | **读取**属性值 | `GET_UNIT_ATTR(单位, "ATTR_RESULT", "<属性名>")` 第 3 槽 | `UNIT_WRITE_ATTRIBUTE` | ❌ **没有**（配 `ATTR_RESULT`/`ATTR_BASE`/`ATTR_OTHER` 一律 `valid=false`） |
>
> 读**当前生命**要用专用取值函数 `GET_HP_CUR(单位)`；最大生命用
> `GET_UNIT_ATTR(单位, "ATTR_RESULT", "hp_max")`。
> 第 2 槽（`ATTR_ELEMENT_READ`）合法值：`ATTR_BASE` / `ATTR_BONUS` / `ATTR_BASE_RATIO` /
> `ATTR_BONUS_RATIO` / `ATTR_OTHER` / `ATTR_RESULT`。

---

## sub_type 完整速查（来源：各 GameTrigger*Arg.py）

**核心规则**：
- `sub_type = 1` = **字面常量**（适用于所有基础类型：FLOAT/INTEGER/STRING/BOOLEAN/UNIT_NAME/PLAYER 等）
- `sub_type` 为**字符串**时 = 调用特定函数求值（POINT、UNIT_ENTITY 等复合类型）
- `sub_type = 变量编号` = 引用变量

### FLOAT (100000)
| sub_type | 含义 |
|---|---|
| `1` | 实数常量，`args_list: [0.0]` |
| `2` | 实数变量 |
| `"CUR_GAME_TIME"` | 获取当前游戏运行时间（秒），`args_list: []` |

### INTEGER (100002)
| sub_type | 含义 |
|---|---|
| `1` | 整数常量，`args_list: [42]` |
| `6` | 整数变量 |

### STRING (100003)
| sub_type | 含义 |
|---|---|
| `1` | 字符串常量，`args_list: ["text"]` |

### BOOLEAN (100001)
| sub_type | 含义 |
|---|---|
| `1` | 布尔常量，`args_list: [true]` |
| `"VARIABLE"` | 布尔变量，`args_list: [{"__tuple__": true, "items": ["BOOLEAN", "变量名", "local"]}]`；编辑器保存的正式函数使用此格式 |

### ANGLE (100225)
| sub_type | 含义 |
|---|---|
| `1` | 角度常量，`args_list: [0.0]` |
| `2` | 角度变量 |

### UNIT_NAME (100116)  ← 单位类型ID
| sub_type | 含义 |
|---|---|
| `1` | 单位类型常量，`args_list: [100001]` |
| `2` | 单位类型变量 |

### PLAYER (100025)
| sub_type | 含义 |
|---|---|
| `1` | 预设玩家，`args_list: [1]`（玩家编号） |
| `"OWNER_PLAYER"` | 单位所属玩家，`args_list: [<UNIT_ENTITY arg>]` |
| `"TRIGGER_PLAYER"` | 触发事件的玩家 |

### POINT (100004)  ← 坐标点（必须用函数）
| sub_type | 含义 |
|---|---|
| `1` | 场景预设点（逻辑资源管理器中的点），`args_list: [res_id]` |
| `6` | **坐标转点 `FLOAT_TO_POINT`**（源码枚举值为整数 `6`，实测 JSON 中推荐用字符串 `"FLOAT_TO_POINT"`），`args_list: [<FLOAT arg x>, <FLOAT arg y>]` |
| `19` | 变量点 |
| `"GET_POINT_FROM_EVENT"` | 事件中的点 |

### UNIT_ENTITY (100006)  ← 单位实体
| sub_type | 含义 |
|---|---|
| `1` | 场景预设单位（场景中放置的单位），`args_list: [scene_unit_id]` |
| `4` | **最近创建的单位 `LAST_CREATE_UNIT`**，`args_list: []` |
| `11` | **变量引用**，`args_list: [["UNIT_ENTITY", "变量名", "local"]]`（普通数组，不是 `__tuple__`） |
| `"CREATE_UNIT"` | 创建单位并以返回值为参数（嵌套在 SET_VARIABLE 中） |
| `"ABILITY_OWNER"` | 技能拥有者（施法者），`args_list: []`，在技能触发器中使用 |
| `"CUR_UNIT"` | 当前单位（物编触发器中） |
| `"GET_UNIT_FROM_EVENT"` | 从事件获取单位 |

### STATE (100075)  ← 单位状态
| sub_type | 含义 |
|---|---|
| `1` | 状态常量，`args_list: [8192]`（整数值，见 UnitEnumState） |

**常用 STATE 整数值**（来源：`y3/game/const.lua`）：
| 值 | 状态名 |
|---|---|
| `2` | 禁止普攻 (1<<1) |
| `4` | 禁止施法 (1<<2) |
| `8` | 禁止移动 (1<<3) |
| `4096` | 不会死亡 (1<<12) |
| `8192` | **无敌** (1<<13) |
| `16384` | 无法控制 (1<<14) |
| `32768` | 无法被攻击 (1<<15) |

### GENERIC_UNIT_EVENT (100008)  ← 通用单位事件
| sub_type | 含义 |
|---|---|
| `"GENERIC_UNIT_EVENT"` | 通用单位事件，`args_list: ["ET_UNIT_DIE"]`（注意 ET_ 前缀） |

### RECTANGLE (100009)  ← 矩形区域实体
| sub_type | 含义 |
|---|---|
| `1` | 场景预设矩形区域（逻辑资源），`args_list: [res_id]` |
| `7` | 变量 |
| `"GET_USABLE_MAP_RANGE"` | **全图矩形**，`args_list: []`，返回整张地图的区域 |

### UNIT_GROUP (100026)  ← 单位组
| sub_type | 含义 |
|---|---|
| `1` | 某玩家的全部单位，`args_list: [<PLAYER arg>]` |
| `3` | **区域内单位** `AREA_UNIT_GROUP`，`args_list: [<RECTANGLE/ROUND_AREA arg>]` |
| `14` | 变量单位组 |
| `16` | 同类型单位组 `UNIT_TYPE_UNIT_GROUP`，`args_list: [<UNIT_NAME arg>]` |

### KEYBOARD_KEY (200220)  ← 键盘按键
| sub_type | 含义 |
|---|---|
| `1` | 常量按键，`args_list: [33]`（整数，见 KeyboardKey 枚举值） |
| `2` | 变量 |

**键盘按键整数值**（来源：`maps/<地图>/script/y3/game/const.lua` 的 `M.KeyboardKey`，共 106 个键）

> ⚠️ 这张表**由脚本生成，不要手写**：`py -3 build/gen_keyboard_table.py`（工程内脚本，直接解析 `const.lua`）。
> 旧版手工表**缺了 R**（只有到 F2 的几个键），照抄会出现「QWER 里只有三个能按」这种问题。

**字母**

| 按键 | 值 | 按键 | 值 | 按键 | 值 |
|---|---|---|---|---|---|
| Q | 16 | W | 17 | E | 18 |
| R | 19 | T | 20 | Y | 21 |
| U | 22 | I | 23 | O | 24 |
| P | 25 | A | 30 | S | 31 |
| D | 32 | F | 33 | G | 34 |
| H | 35 | J | 36 | K | 37 |
| L | 38 | Z | 44 | X | 45 |
| C | 46 | V | 47 | B | 48 |
| N | 49 | M | 50 |  |  |

**数字行**

| 按键 | 值 | 按键 | 值 | 按键 | 值 |
|---|---|---|---|---|---|
| 1 | 2 | 2 | 3 | 3 | 4 |
| 4 | 5 | 5 | 6 | 6 | 7 |
| 7 | 8 | 8 | 9 | 9 | 10 |
| 0 | 11 |  |  |  |  |

**F 键**

| 按键 | 值 | 按键 | 值 | 按键 | 值 |
|---|---|---|---|---|---|
| F1 | 59 | F2 | 60 | F3 | 61 |
| F4 | 62 | F5 | 63 | F6 | 64 |
| F7 | 65 | F8 | 66 | F9 | 67 |
| F10 | 68 | F11 | 87 | F12 | 88 |

**功能键**

| 按键 | 值 | 按键 | 值 | 按键 | 值 |
|---|---|---|---|---|---|
| ESCAPE | 1 | TAB | 15 | RETURN | 28 |
| LCTRL | 29 | LSHIFT | 42 | RSHIFT | 54 |
| LALT | 56 | SPACE | 57 | RCTRL | 157 |

### ACTION_LIST (100022)  ← 动作列表（嵌套）
用于 `PICK_UNIT_DO_ACTION` 等需要内联动作块的 ECA。内部直接嵌套完整 Action 节点：
```json
{
    "arg_type": 100022,
    "sub_type": 1,
    "args_list": [
        {
            "action_type": "KILL_UNIT",
            "element_id": 1750000003000006,
            "enable": true,
            "bp": false,
            "args_list": [...]
        }
    ]
}
```

### SFX_KEY (100066) / SFX_ENTITY (100148)
| 类型 | sub_type | 含义 |
|---|---|---|
| SFX_KEY | `1` | 特效资源常量，`args_list: [sfx_res_id]`（整数） |
| SFX_KEY | `4` | 变量 |
| SFX_ENTITY | `4` | 变量引用，`args_list: [{__tuple__, items: ["SFX_ENTITY", "变量名"]}]` |
| SFX_ENTITY | `"CREATE_SFX_ON_POINT"` | 在点创建特效（函数，嵌套在 SET_VARIABLE 中） |

---

## 变量系统

### 全局变量（globaltriggervariable.json）

> **变量引用默认规则（2026-10 起）**：`{"var": "名字", "type": "..."}` 省略 `scope` 时，如果该名字已在
> `globaltriggervariable.json` 声明，生成器按**全局变量**处理（2 元组）；需要在函数/触发器里故意遮蔽
> 同名全局变量时，必须显式写 `"scope": "local"`。


定义在 `maps/<地图名>/globaltriggervariable.json`。新增一个全局变量需同时更新三处：

```json
{
    "variable_dict": {
        "UNIT_ENTITY": { "unit": 0 }
    },
    "variable_group_info": [
        { "__tuple__": true, "items": ["unit", "unit"] }
    ],
    "variable_length_dict": { "unit": 0 }
}
```

> ⚠️ **默认值必须匹配类型**，否则编辑器打开变量面板时崩溃（`setText(self, str): argument 1 has unexpected type 'int'`）：
>
> | 类型 | 默认值 |
> |------|--------|
> | `STRING` | `""` |
> | `BOOLEAN` | `false` |
> | `FLOAT` / `ANGLE` | `0.0` |
> | `INTEGER` / `UNIT_ENTITY` / `UNIT_NAME` / `SFX_ENTITY` | `0` |
> | `POINT` | **`[0, 0, 0]`（3 个分量，不能写 `0`）** |
>
> 推荐用 `var_manager.py add` 自动处理，避免手写 JSON 出错。

> 🚨 **`POINT` 变量默认值写 `0` 会让整次保存失败（不是"变量面板崩溃"，是"保存失败 + 地图目录被写空"）。**
> 编辑器 `commons.black_box.meta.EType.FPoint.to_value()` 做的是
> `(float(val[0]), float(val[1]), float(val[2]))`，喂一个整数 `0` 直接抛
> `TypeError: 'int' object is not subscriptable`，栈顶是 `<local <变量名> = 0>`。
> 实测：一次保存失败后 `maps/<地图>/` 被清空、后续每次保存都失败
> （因为 `header.map` 也没了，编辑器再也找不到地图目录）。
> `gen_trigger.py` 已在 `build_var_data` 里把 POINT 默认值改成 3 分量。

### 局部变量（trigger var_data）

局部变量在触发器的 `var_data` 中声明，格式：

```json
"var_data": [
    { "NEW_TIMER": {}, "UNIT_ENTITY": { "unit": 0 } },
    { "unit": 0 },
    [ "unit" ]
]
```

- `var_data[0]`: 按类型分组 `{ TYPE: { name: 0 } }`；只有实际声明计时器变量时才包含 `NEW_TIMER`
- `var_data[1]`: 按名称索引 `{ name: 0 }`
- `var_data[2]`: 有序名称列表 `[ name ]`

### 变量引用（局部 3 元组 / 全局 2 元组）

```json
// 局部变量：三元素 ["TYPE", "name", "local"]，需在 trigger 的 var_data 中声明
{"__tuple__": true, "items": ["UNIT_ENTITY", "unit", "local"]}

// 全局变量：只有两元素 ["TYPE", "name"]，没有 scope！
{"__tuple__": true, "items": ["UNIT_ENTITY", "unit"]}
```

> ⚠️ **实测结论**：全局变量写成 3 元组并带 `"global"` 会被编辑器判为**「无效的变量」并标红**（参数在保存时被清成 `null`）。全局变量也不在 trigger `var_data` 中声明。

**全局变量存放位置**：`maps/<地图名>/globaltriggervariable.json`（编辑器读写的就是它，通常已含工程自带变量）。工程根的 `project_trigger_var.json` 编辑器**不读**。请用 `var_manager.py`（路径已修正）增删。

**全局变量引用的完整写法**（来自编辑器实际保存样本）：

```jsonc
// 写入（SET_VARIABLE 的目标）
{"arg_type": 100030, "sub_type": 1,
 "args_list": [{"__tuple__": true, "items": ["INTEGER", "金币"]}]}

// 读取（条件 / 动作参数）
{"arg_type": 100002, "sub_type": 6,
 "args_list": [{"__tuple__": true, "items": ["INTEGER", "金币"]}]}
```

读取的 `sub_type` 按变量类型取（写错会被清成 `null`）：

| 变量类型 | 读取 sub_type |
|---|---|
| `INTEGER` | `6` |
| `STRING` / `FLOAT` / `ANGLE` | `2` |
| `UNIT_ENTITY` | `11` |
| `PLAYER` / `BOOLEAN` / `NEW_TIMER` / `TABLE` | `"VARIABLE"` |

**实体变量赋空**：`UNIT_ENTITY` 用 `{"arg_type":100006,"sub_type":"NONE_UNIT","args_list":[]}`；`UNIT_GROUP` 用 `NONE_UNIT_GROUP`。直接写字面量 `0` 会被编辑器清成 `null`（`gen_trigger.py` 已自动改写并打印 `[INFO]`）。

---

用 `lookup.py` 反查 ECA 的参数类型：
```bash
py -3 <agent>\skills\eca-json-builder\lookup.py CREATE_UNIT
# param: ["UNIT_NAME", "POINT", "ANGLE", "PLAYER"]
# 然后按 param 顺序填 args_list
```

---

## 完整示例

> 推荐用 `gen_trigger.py` + DSL 生成（见 `SKILL.md`），手写示例仅供调试参考。

简单示例「游戏初始化 → 打印"321"」对应的最终 JSON 结构在 `eca_json_helper.py template trigger_instance` 输出中可见。

---

## 物编触发器（单位）专用格式

**路径**：`maps/<地图名>/unit/<单位Key>.json`

一个文件包含该单位的**所有触发器**。事件直接写名称，不包裹 `GENERIC_UNIT_EVENT`。

### 文件结构（以单位 100001 为例）

```json
{
  "local_variable": {},
  "trigger_dict": {
    "<trigger_id>": {
      "trigger_name": "新建触发器",
      "trigger_id": 332730369,
      "p_trigger_id": null,
      "group_id": 100001,
      "enabled": true,
      "valid": true,
      "call_enabled": true,
      "event": [
        {
          "event_type": "UNIT_DIE",
          "element_id": 332730369000002,
          "enable": true,
          "args_list": []
        }
      ],
      "condition": [],
      "action": [
        {
          "action_type": "PRINT_MESSAGE_ACTION_TO_DIALOG",
          "element_id": 332730369000005,
          "enable": true,
          "bp": false,
          "args_list": [
            {"arg_type": 100175, "sub_type": 1, "args_list": [3]},
            {"arg_type": 100003, "sub_type": 1, "args_list": ["321"]}
          ]
        }
      ],
      "var_data": [{}, {}, []]
    }
  },
  "trigger_group_info": [
    {
      "_trigger_group_": true,
      "group": [
        {"__tuple__": true, "items": [332730369, "新建触发器"]}
      ],
      "key": 100001,
      "name": "100001"
    }
  ],
  "trigger_version": "1.2",
  "variable_dict": {},
  "variable_group_info": [],
  "variable_length_dict": {}
}
```

### 关键差异（vs 全局触发器）

| 差异点 | 全局 | 物编（单位） |
|--------|------|-------------|
| 文件数 | 每个触发器一个文件 | 一个单位一个文件（`trigger_dict` 聚合） |
| 事件写法 | 直接写 `GAME_PAUSE` | 直接写 `UNIT_DIE`（不包裹 GENERIC_UNIT_EVENT） |
| `group_id` | `0` | = 单位 Key（如 `100001`） |
| 索引方式 | `index.txt`（JSON） | `trigger_group_info` 字段 |
| 额外顶层 | 无 | `local_variable`, `trigger_version`, `variable_dict` 等 |
| 文件创建 | AI 新建 JSON + 更新 index | 必须先确认目标单位的 JSON 文件已存在，再追加到 `trigger_dict` |

### AI 生成物编触发器的步骤

1. **确认单位 Key** 和 JSON 文件已存在：`maps/<地图名>/unit/<Key>.json`
2. 读取现有文件，获取 `trigger_dict` 和 `trigger_group_info`
3. 生成新 `trigger_id`（避免与已有冲突）
4. 追加条目到 `trigger_dict` 和 `trigger_group_info`
5. **不创建新文件**，更新已有 JSON

---

## 工程 JSON 的字节格式口径（实测基准）

> 工程 JSON 写坏的代价：编辑器**保存失败**，报错只有一行摘要，真栈埋在编辑器日志里 ——
> 排查一次很贵（曾把 `logicres.json` 写坏，之后每次保存都失败）。
> 全工程一致的硬规则已加进 `../_health_check.py`（`Project JSON format` 一项自动查）。

**硬规则（全工程一致，违反即失败）**：

| 规则 | 值 |
|------|----|
| 编码 | UTF-8，**不带 BOM** |
| 文件末尾 | **没有换行符** |

**各目录的实测风格**（都能被编辑器读，不要随手改口径）：

| 目录 | 行尾 | 非 ASCII | 缩进 |
|------|------|----------|------|
| `maps/<地图>/*.json`（工程表：`logicres.json` / `globaltriggervariable.json` …） | LF | `\uXXXX` 转义 | 4 |
| `maps/<地图>/editor/**` | CRLF（例外：`randomdecogroupinfo.json` / `tableeditorgroupinfo.json` 是 LF） | 混 | 4 |
| `maps/<地图>/ability/**`（技能触发器，脚本生成） | CRLF | 原样中文 | 4 |
| `maps/<地图>/global_trigger/**` | LF | 混 | 4 |
| `maps/<地图>/ui/**` | LF | 混 | 4 |

**写工程 JSON 的两条纪律**：

1. **一律脚本写入，禁止内联 `py -3 -c "…"`**：内联时 `ensure_ascii` 与换行转义极易和预期不符
   （实测把 `logicres.json` 写成「LF + `\uXXXX`」之后，编辑器保存直接失败、会话变脏）。
   先落 `.py` 文件再执行。
2. **改之前先做格式复现校验**：读出目标文件字节 → 用打算使用的 `json.dump` 参数重写 →
   与原文**逐字节比对**，一致才允许动它。**编辑器亲笔样本就是基准**（例：`logicres.json` 的
   口径是 `indent=4` + `\uXXXX` 转义 + LF + 末尾无换行）。

## 工作流

0. **确定目标地图目录**（强制第一步）
   - Y3 项目的触发器路径为 `maps/<地图名>/global_trigger/trigger/`
   - 当前编辑的地图名从 `maps/` 子目录获取（如 `EntryMap`）
   - 目标路径示例：`maps/EntryMap/global_trigger/trigger/`

1. **取模板**
   ```bash
   py -3 <agent>\skills\eca-json-builder\eca_json_helper.py template trigger_instance
   ```

2. **查 ECA 参数**（确定 `args_list` 顺序和类型）
   ```bash
   py -3 <agent>\skills\eca-json-builder\lookup.py PRINT_MESSAGE_ACTION_TO_DIALOG
   ```
   > 优先用 `lookup.py`（读内建索引，零依赖）。仅当需要引擎最新定义时才用 `eca_json_helper.py lookup`。

3. **按 param 顺序填充 args_list**，每个参数一个 Arg 节点，`arg_type`/`sub_type` 用整数 ID

4. **校验**
   ```bash
   py -3 <agent>\skills\eca-json-builder\eca_json_helper.py validate <触发器名>.json
   ```

5. **放入项目**
   - 将 JSON 文件写入 `maps/<地图名>/global_trigger/trigger/<触发器名>.json`
   - 编辑同目录的 `index.txt`：文件为 JSON 对象，**值为触发器在列表中的顺序索引（从0递增）**
   ```json
   {
       "旧触发器.json": 0,
       "新触发器.json": 1
   }
   ```

6. **刷新编辑器**：关闭并重新打开触发器编辑面板即可看到。

---

## 常见问题

| 问题 | 原因 | 解决 |
|---|---|---|
| 触发器不显示 | 放错目录（项目根 vs 地图子目录） | 确认路径为 `maps/<地图名>/global_trigger/trigger/` |
| 触发器不显示 | `index.txt` 未更新或格式错误 | 格式为 JSON `{"文件名.json": 0}`，非纯文本行 |
| 触发器中参数显示异常 | `arg_type`/`sub_type` 用字符串名 | 改为整数 ID（如 `100003` 而非 `"STRING"`） |
| `element_id` 冲突 | ID 重复 | `trigger_id` 用大整数（如 `1718000001`），`element_id` 在其后补零（如 `1718000001000002`） |
| ECA 名不存在 | `event_type`/`action_type` 拼写错误 | 用 `lookup.py <名称>` 验证，优先查内建索引 |
| 事件不触发 | `event_type` 名称过时 | 用 `lookup.py --global-events` 获取当前有效事件名 |
| **参数保存后变 `null` / 界面标红「无效的变量」** | 写法不被编辑器接受（全局变量 3 元组、全局读取 sub_type 写错、实体变量赋 `0`、`GENERIC_UNIT_EVENT` 参数 sub_type 写整数） | 按本文「✅ 写法校验」章节核对；改完后**回读比对**确认不再被清空 |
| 触发器存在但从不触发 | `GENERIC_UNIT_EVENT` 参数被清成 `null`（`sub_type` 写成整数 `1`） | `sub_type` 写事件名字符串，如 `"GENERIC_UNIT_EVENT"` |
| **整条触发器标红 `valid=false`，但所有参数都正常** | 物编事件（`t_unit`/`t_ability`/…）触发器里用了 `TRIGGER_PLAYER`——该事件类别里拿不到「触发玩家」 | 改用 `OWNER_PLAYER(<单位>)`。`gen_trigger.py` 已在生成期报错拦下（实测） |
| 多段字符串拼接只拼上前 2 段 | 把第 3 段起当成位置参数传了（`STR_JOIN` 只声明 2 个位置参数，其余被静默丢弃） | 第 3 段起写进 `op_arg`：`["STR_JOIN","A","B",{"op_arg":["C","D"]}]`；`STR_JOIN` 实际支持 2+8=最多 10 段（实测） |
| 参数类型拿不准就随便填 | 未登记的 `arg_type` 会被清成 `null` 或让 `valid=false` | `gen_trigger.py` 现在对未登记类型**直接报错**并给出取证步骤；先取证再补 `ARG_TYPE_ID`，不要猜 |
| 保存后引用的全局变量全部标红 | `save_editor` 以编辑器内存为准写回，未加载的新变量被裁剪 | `save_editor` → `var_manager add` → `restart_editor(save_before_restart=false)` → 再导入触发器；`verify_trigger.py` 已加保存后存活检查 |
| 参数类型 ID 拿不准 | `eca_index.json` 只有类型**名**，没有 ID；写错会被清成 `null` 或让 `valid=false` | 用 `sync_from_source.py` 从源码派生 `eca_source_data.json`（类型名→ID、sub_type 表、变量读取 sub_type、flags），手写表退化为兜底 |
| `TRIGGER_PLAYER` 在 `INIT_FINISHED` 里失效 | 它读的是事件参数 `ROLE_ID`（源码 `GameTriggerRoleArg.py`），`t_system` 事件不提供 | 换 `OWNER_PLAYER(<单位>)` / 具体玩家 / `GET_CLIENT_ROLE`；生成器已按「t_system + 物编事件家族」报错 |
| `END_GAME_FOR_ROLE` 参数被清空 | 曾以为 `WIN_OR_LOSE`/`ON_OR_OFF` 无 ID 可用 | 二者实为 **100047 / 100048**（源码派生），且需**填满 6 个参数**才 `valid=true`（实测） |
| UI 点击没反应 | 事件处理器写成普通顶层触发器 | 必须用「`INIT_FINISHED` 父触发器 + 子触发器 + 裸整数注册」结构，事件参数用 `STR_TO_UI_EVENT("名字")` |
| `import_eca` 返回成功但子触发器丢了 | 旧文档误标「含 `sub_trigger` 不能走 `import_eca`」；**实测当前版本可直接导入**（新建/覆盖均保留） | 先 `import_eca` + `save_editor` + `diff` 校验；只有 `diff` 真的报丢子触发器时，才退回 `restart_editor(save_before_restart=false)`，并补一次 `save_before_restart=true` 恢复会话 |
| 自动化点击验证 UI 结论是「收不到事件」 | `y3runtime.trigger_ui_touch_event_by_path` 只驱动 Lua 监听 | UI 用例必须人工点击验证 |

---

## 完整示例：创建单位 + 赋变量 + 添加无敌

语义：**游戏初始化 → 在(0,0)为玩家1创建单位100001 → 赋给变量unit → 给unit添加无敌状态**

> 此示例来自实际编辑器手工填参后导出，是 `CREATE_UNIT` + `ADD_STATE` 的权威参考。
> 需要同步在 `globaltriggervariable.json` 中声明 `UNIT_ENTITY` 变量 `unit`。

```json
{
    "trigger_name": "创建单位100001并添加无敌",
    "trigger_id": 1750000001,
    "p_trigger_id": null,
    "group_id": 0,
    "enabled": true,
    "valid": true,
    "call_enabled": true,
    "event": [
        {
            "event_type": "INIT_FINISHED",
            "element_id": 1750000001000002,
            "enable": true,
            "args_list": []
        }
    ],
    "condition": [],
    "action": [
        {
            "action_type": "SET_VARIABLE",
            "element_id": 1750000001000005,
            "enable": true,
            "bp": false,
            "args_list": [
                {
                    "arg_type": 100006,
                    "sub_type": 11,
                    "args_list": [{"__tuple__": true, "items": ["UNIT_ENTITY", "unit", "local"]}]
                },
                {
                    "arg_type": 100006,
                    "sub_type": "CREATE_UNIT",
                    "args_list": [
                        {"arg_type": 100116, "sub_type": 1, "args_list": [100001]},
                        {
                            "arg_type": 100004,
                            "sub_type": 6,
                            "args_list": [
                                {"arg_type": 100000, "sub_type": 1, "args_list": [0.0]},
                                {"arg_type": 100000, "sub_type": 1, "args_list": [0.0]}
                            ]
                        },
                        {"arg_type": 100225, "sub_type": 1, "args_list": [0.0]},
                        {"arg_type": 100025, "sub_type": 1, "args_list": [1]}
                    ]
                }
            ]
        },
        {
            "action_type": "ADD_STATE",
            "element_id": 1750000001000006,
            "enable": true,
            "bp": false,
            "args_list": [
                {
                    "arg_type": 100006,
                    "sub_type": 11,
                    "args_list": [{"__tuple__": true, "items": ["UNIT_ENTITY", "unit", "local"]}]
                },
                {"arg_type": 100075, "sub_type": 1, "args_list": [8192]}
            ]
        }
    ],
    "var_data": [{"NEW_TIMER": {}, "UNIT_ENTITY": {"unit": 0}}, {"unit": 0}, ["unit"]]
}
```

---
## 实战验证示例

> 完整 13 条实战 JSON 已迁移到 `test-cases/`（每个 TC-NN-*.md 含一条已验证示例）。
> 推荐方式：用 `gen_trigger.py` + DSL 生成，详见 `SKILL.md`。


## AI 使用检查清单

生成触发器前必须确认：

- [ ] 已确定地图目录（`maps/<地图名>/`）
- [ ] `event_type` 已用 `lookup.py` 验证存在且 sub_type 为 `t_system`/`t_player`/`t_ui`/`t_click`（键盘/鼠标事件为 `t_click`）
- [ ] `action_type` 已用 `lookup.py` 验证参数列表
- [ ] `trigger_id` 使用独立大整数，`element_id` 格式为 `trigger_id` 后补零（同一触发器内每个节点补不同数字，确保全局唯一）
- [ ] 写入路径为 `maps/<地图名>/global_trigger/trigger/<名称>.json`
- [ ] `index.txt` 已按 JSON 格式追加 `"<文件名>.json": 0`
- [ ] 已运行 `validate` 校验通过
- [ ] **全局变量**：确认写在 `maps/<地图名>/globaltriggervariable.json`；引用用 **2 元组**（无 scope）；读取 `sub_type` 按类型取（`INTEGER`=6 / `STRING`,`FLOAT`,`ANGLE`=2 / `UNIT_ENTITY`=11 / `PLAYER`,`BOOLEAN`,`NEW_TIMER`,`TABLE`=`"VARIABLE"`）
- [ ] **实体变量赋空**用 `NONE_UNIT`/`NONE_UNIT_GROUP`，不要写字面量 `0`
- [ ] **包装类事件**（`GENERIC_UNIT_EVENT` 等）参数 `sub_type` 写事件名字符串，不要写整数
- [ ] **UI 事件**：父触发器（`INIT_FINISHED`）+ 子触发器 + 裸整数注册；事件参数用 `STR_TO_UI_EVENT("名字")`
- [ ] **回读比对**：`import_eca` → 等 3 秒 → `save_editor` → 回读磁盘 JSON 与生成结果比对，确认没有被清成 `null` 的参数

---

## 物编触发器（技能）专用格式

**路径**：`maps/<地图名>/ability/<技能Key>.json`

### 文件结构

```json
{
  "local_variable": {
    "<trigger_id>": {
      "variable_dict": {
        "ABILITY": {"ability": 0},
        "NEW_TIMER": {},
        "UNIT_ENTITY": {"caster": 0, "target": 0}
      },
      "variable_length_dict": {"ability": 0, "caster": 0, "target": 0}
    }
  },
  "trigger_dict": {
    "<trigger_id>": { ... }
  },
  "trigger_group_info": [
    {
      "_trigger_group_": true,
      "group": [{"__tuple__": true, "items": [<trigger_id>, "<触发器名>"]}],
      "key": <技能Key>,
      "name": "<技能Key>"
    }
  ],
  "trigger_version": "1.2",
  "variable_dict": {
    "UNIT_ENTITY": {"caster": 0, "target": 0},
    "ABILITY": {"ability": 0}
  },
  "variable_group_info": [
    {"__tuple__": true, "items": ["caster", "caster"]},
    {"__tuple__": true, "items": ["target", "target"]},
    {"__tuple__": true, "items": ["ability", "ability"]}
  ],
  "variable_length_dict": {"caster": 0, "target": 0, "ability": 0}
}
```

> ⚠️ **局部变量有两处声明**：`local_variable[trigger_id].variable_dict` + 顶层 `variable_dict`，两者必须保持一致。

### 技能触发器常用事件

| 事件名 | 说明 | JSON 写法 |
|--------|------|-----------|
| `ABILITY_SP_END` | **后摇结束**（施放效果的正确时机，无参直接写） | `{"event_type":"ABILITY_SP_END","args_list":[]}` |
| `ABILITY_PS_START` | 施法开始（需 `GLOBAL_ABILITY_EVENT` 包装） | `{"event_type":"GLOBAL_ABILITY_EVENT","args_list":[{"arg_type":100008,"sub_type":"ABILITY_PS_START","args_list":[]}]}` |
| `ABILITY_CS_START` | 即将施法（需包装） | 同上，sub_type 换名 |
| `ABILITY_END` | 技能结束（需包装） | 同上 |

> ✅ **`ABILITY_SP_END` 等技能生命周期事件可以直接写 `event_type`，不需要 `GLOBAL_ABILITY_EVENT` 包装。**
> 只有需要区分具体阶段时才用包装形式。

### 技能触发器内专用 sub_type

| arg_type | sub_type | 含义 |
|----------|----------|------|
| 100006 (UNIT_ENTITY) | `"ABILITY_OWNER"` | 施法者（技能拥有者） |
| 100014 (ABILITY) | `"CUR_ABILITY"` | 当前触发此事件的技能实例 |
| 100014 (ABILITY) | `"GET_ABILITY_FROM_EVENT"` | 从事件获取技能（全局上下文） |

### APPLY_DAMAGE 参数顺序（技能触发器内）

```
[伤害所属(伤害来源), 技能, 受伤目标, 伤害类型, 伤害值, 是否跳字]
```

| 位置 | arg_type | sub_type | 值 | 说明 |
|------|----------|----------|----|------|
| 0 | 100006 | `"ABILITY_OWNER"` | `[]` | **伤害所属**（伤害算在谁头上） |
| 1 | 100014 | `"CUR_ABILITY"` | `[]` | 当前技能实例 |
| 2 | 100006 | `"TARGET_UNIT_IN_ABILITY"` / `"FOR_EACH_SELECTED_UNIT"` | `[]` | **受伤目标**（真正掉血的那个单位） |
| 3 | **100064** | 1 | `[1]` | 伤害类型（1=普通物理） |
| 4 | 100000 | 1 | `[150.0]` | 伤害值 |
| 5 | 100001 | 1 | `[false]` | 是否跳字 |

> ⚠️ 伤害类型 `arg_type=100064`（不是 100238），`args_list: [1]`
> 必须附带 `"op_arg": [null×9]` + `"op_arg_enable": [false×9]`
>
> 🚨 **第 0 槽是「伤害所属」、第 2 槽才是「受伤目标」，写反是静默失效。**
> 依据是 `eca_index.json` 里 `APPLY_DAMAGE` 的 `cont` 模板：
> 「对{#2}造成{#3}类型的{#4}伤害，{#5}跳字，伤害所属{#0}所属{#1}」
> —— `{#0}`/`{#1}`/`{#2}` 就是 `args_list` 的第 0/1/2 个元素。
> 写反的后果：目标是施法者 → **伤害全落在自己身上，敌人一点血不掉**，触发器照样 `valid=true`。
> 实测：`[FOR_EACH_SELECTED_UNIT, CUR_ABILITY, ABILITY_OWNER, 1, 200, false]`
> 用在 AOE 里，11 只怪全部毫发无伤，掉血的是英雄自己。

### ADD_STATE / REMOVE_STATE 参数

- State 参数 `arg_type: 100075`，`sub_type: 1`，`args_list: [N]`
- **每个状态值单独一条** `ADD_STATE`，不可叠加成一个整数
- 常用状态值：`2`=禁止攻击，`4`=禁止移动，`8`=禁止施法，`16`=禁止普攻

```json
{"action_type": "ADD_STATE", "args_list": [
    {"arg_type": 100006, "sub_type": 11, "args_list": [["UNIT_ENTITY","target","local"]]},
    {"arg_type": 100075, "sub_type": 1, "args_list": [4]}
], "bp": false, "element_id": ..., "enable": true}
```

### RUN_ONCE_TIMER_NO_SAVE（延迟执行，不存档）

**参数顺序：`[时间(FLOAT), 动作列表(ACTION_LIST)]`** — 没有 `NEW_TIMER` 变量参数。

```json
{
  "action_type": "RUN_ONCE_TIMER_NO_SAVE",
  "args_list": [
    {"arg_type": 100000, "sub_type": 1, "args_list": [2.0]},
    {"arg_type": 100022, "sub_type": 1, "args_list": [
      { ... 内嵌 action ... }
    ]}
  ],
  "bp": false,
  "element_id": ...,
  "enable": true,
  "local_var": {"__tuple__": true, "items": [{}, {}]}
}
```

> ⚠️ 必须带 `"local_var": {"__tuple__": true, "items": [{}, {}]}`，否则编辑器报错。

### var_data 真实格式（三元素数组）

```json
"var_data": [
    {"NEW_TIMER": {}, "UNIT_ENTITY": {"caster": 0, "target": 0}},
    {"caster": 0, "target": 0},
    ["caster", "target"]
]
```

| 索引 | 内容 |
|------|------|
| `[0]` | 变量类型字典：`{"类型名": {"变量名": 默认值}}` |
| `[1]` | 变量默认值字典：`{"变量名": 默认值}` |
| `[2]` | 变量名顺序数组：`["变量名1", "变量名2"]` |

`sub_type=11` 的 `args_list` 用**普通数组**，三元素：

```json
{"arg_type": 100006, "sub_type": 11, "args_list": [["UNIT_ENTITY", "caster", "local"]]}
```

> ⚠️ **不要用 `__tuple__` 格式**——技能触发器变量引用经实测需要普通数组 `[...]`，用 `__tuple__` 会导致变量显示无效。

### PICK_UNIT_DO_ACTION — 遍历单位组对每个单位执行动作

**对范围内所有单位造成伤害的标准写法（AoE 模板）：**

```
PICK_UNIT_DO_ACTION(
  UNIT_LIST_IN_SHAPE(圆心点, 圆形范围, [op_arg[7]=排除单位, op_arg[11]=仅敌方]),
  ACTION_LIST[内嵌 action...]
)
```

```json
{
  "action_type": "PICK_UNIT_DO_ACTION",
  "args_list": [
    {
      "arg_type": 100026,
      "sub_type": "UNIT_LIST_IN_SHAPE",
      "args_list": [
        {
          "arg_type": 100004,
          "sub_type": "ABILITY_RELEASE_POSITION",
          "args_list": [
            {"arg_type": 100014, "sub_type": "CUR_ABILITY", "args_list": []}
          ]
        },
        {
          "arg_type": 100211,
          "sub_type": "CONST_CIRCULAR_SHAPE",
          "args_list": [
            {"arg_type": 100000, "sub_type": 1, "args_list": [700.0]}
          ]
        }
      ],
      "op_arg": [
        null, null, null, null, null, null, null,
        {"arg_type": 100006, "sub_type": 11, "args_list": [["UNIT_ENTITY","caster","local"]]},
        null, null, null,
        {"arg_type": 100001, "sub_type": 1, "args_list": [true]},
        null, null, null
      ],
      "op_arg_enable": [false,false,false,false,false,false,false,true,false,false,false,true,false,false,false]
    },
    {
      "arg_type": 100022,
      "sub_type": 1,
      "args_list": [
        {
          "action_type": "APPLY_DAMAGE",
          ...
        }
      ]
    }
  ]
}
```

**关键点：**

| 要素 | 说明 |
|------|------|
| 圆心 | 用 `ABILITY_RELEASE_POSITION`（技能释放点），而不是施法者当前位置 `UNIT_ENTITY_POINT` |
| 遍历中当前单位 | `{"arg_type": 100006, "sub_type": "FOR_EACH_SELECTED_UNIT", "args_list": []}` |
| `APPLY_DAMAGE` 受伤目标（第 2 槽） | 直接用 `FOR_EACH_SELECTED_UNIT`（本轮回调到的那个单位） |
| `APPLY_DAMAGE` 伤害所属（第 0 槽） | 填施法者 `ABILITY_OWNER`。**别和受伤目标写反**，写反 = 打自己 |

**`ABILITY_RELEASE_POSITION` 写法（取技能释放点）：**
```json
{
  "arg_type": 100004,
  "sub_type": "ABILITY_RELEASE_POSITION",
  "args_list": [
    {"arg_type": 100014, "sub_type": "CUR_ABILITY", "args_list": []}
  ]
}
```

---



`GET_RANDOM_UNIT_AROUND_UNIT` 无法过滤阵营，正确做法是嵌套 `RANDOM_UNIT_IN_UNIT_GROUP(UNIT_LIST_IN_SHAPE)`：

```json
{
  "arg_type": 100006,
  "sub_type": "RANDOM_UNIT_IN_UNIT_GROUP",
  "args_list": [
    {
      "arg_type": 100026,
      "sub_type": "UNIT_LIST_IN_SHAPE",
      "args_list": [
        {
          "arg_type": 100004,
          "sub_type": "UNIT_ENTITY_POINT",
          "args_list": [
            {"arg_type": 100006, "sub_type": 11, "args_list": [["UNIT_ENTITY", "caster", "local"]]}
          ]
        },
        {
          "arg_type": 100211,
          "sub_type": "CONST_CIRCULAR_SHAPE",
          "args_list": [
            {"arg_type": 100000, "sub_type": 1, "args_list": [500.0]}
          ]
        }
      ],
      "op_arg": [
        null, null, null, null, null, null, null,
        {"arg_type": 100006, "sub_type": 11, "args_list": [["UNIT_ENTITY", "caster", "local"]]},
        null, null, null,
        {"arg_type": 100001, "sub_type": 1, "args_list": [true]},
        null, null, null
      ],
      "op_arg_enable": [false,false,false,false,false,false,false,true,false,false,false,false,false,false,false]
    }
  ]
}
```

| op_arg 索引 | 含义 | 典型值 |
|-------------|------|--------|
| `[7]` | 排除指定单位（通常填施法者） | `UNIT_ENTITY caster` |
| `[11]` | 仅敌方单位 | `BOOLEAN true` |

- `arg_type: 100211` = 圆形形状 `CONST_CIRCULAR_SHAPE`
- `arg_type: 100004 sub_type: "UNIT_ENTITY_POINT"` = 取单位所在点（圆心）

---

## 参考代码索引

| 主题 | 文件 |
|---|---|
| 触发器序列化 | `commons/black_box/trigger/base_trigger/{event,action,condition,args}/Trigger*.py` |
| ECA 定义表 | `commons/datas/trigger_new.py` |
| Arg 类型常量 | `commons/black_box/consts/const_name.py`（权威 ID 来源） |
| Arg 类型枚举 | `commons/black_box/trigger/game_trigger/eca/GameTriggerArg.py` |
| 各类型 sub_type | `commons/black_box/trigger/game_trigger/args/GameTrigger*Arg.py` |
| 键盘按键常量列表 | `editor/const_list/const_list_static_const.py` |
| 项目段持久化 | `commons/map_res/MapSection.py:CustomEcaSection` |

---

## 插件函数库与触发器数据

```bash
# 列出插件中所有触发器
py -3 plugin_eca.py list <plugin_dir>
py -3 plugin_eca.py list <plugin_dir> --trigger    # trigger_data 而非 func_lib_data

# 读取完整数据
py -3 plugin_eca.py read <plugin_dir>
py -3 plugin_eca.py read <plugin_dir> --trigger

# 单条触发器 → DSL
py -3 plugin_eca.py dsl <plugin_dir> --id 1058021401
py -3 plugin_eca.py dsl <plugin_dir> --id 981315704 --trigger
```

定义：`trigger_folder_info` + `serialized_data` 平行双数组结构。
- `func_lib_data`: 自定义 ECA 函数（无 `event`，`call_enabled=true`，带 `_function_` 标记）
- `trigger_data`: 带事件的触发器逻辑，按文件夹分组

## ECA 数据表

```bash
# 列出表格行
py -3 table_reader.py list <tables/*.json>
py -3 table_reader.py list <tables_dir>

# 读取行
py -3 table_reader.py read <table.json> --key "保留技能时间"
py -3 table_reader.py read <table.json> --row 5

# 按 Key 查找
py -3 table_reader.py find <table.json> --key "BOSS出现时间"
```

格式：`{"column_width": {...}, "table_data": {"data": [[headers], [row1], ...]}}`
插件内嵌 `table_editor_resource/table_editor_data` 同格式（按表名 keyed）。

## 项目自定义事件

```bash
py -3 project_event.py list <project_root>
py -3 project_event.py read <project_root> --id <event_id>
```

文件：`project_custom_event.json`，结构 `{"conf": {"event_id": {...}}, "group_info": [...]}`

全局触发器中的 `RECEIVE_CUSTOM_EVENT` 使用关卡自己的
`maps/<地图名>/customevent.json`。DSL 可以写事件名称，`gen_trigger.py` 会从
`group_info` 查找并把最终 `CUS_EVENT` 参数写成整数事件 ID；目标关卡没有该事件或存在重名时，
生成会直接失败。不要把事件名称字符串写入最终触发器 JSON。

## 存档系统

```bash
py -3 archive_reader.py list <project_root> --map <map>
py -3 archive_reader.py read <project_root> --map <map>           # archive.json
py -3 archive_reader.py read <project_root> --map <map> --slot 1  # archive.json slot 1
py -3 archive_reader.py read <project_root> --map <map> --storage --slot RANK
```

文件：`maps/<map>/archive/{archive.json, archive_storage.json, mapscore.json}`

---

## 动态子触发 DSL

`gen_trigger.py` 的 trigger DSL 可以构造并写入顶层 `sub_triggers` 数组，也可以用 `--dry-run` 预览；序列化结构以技能测试目录中的编辑器实际保存样本为回归基准，不依赖活动地图中的临时触发器。每个子触发项使用普通 trigger 的字段：`name`、`id`、`event`、`condition`、`action`、`sub_triggers` 等。`id` 建议显式提供；省略时生成器按直接父触发 ID 与子触发名称稳定派生 ID，因此同一 DSL 重跑会得到相同 ID。

父触发或子触发的 action 中可以写：

```json
{"register_sub_trigger": "子触发名称或ID"}
```

注册引用只解析同一父触发器下的直接子触发名称或 ID。未知引用、同父级重复名称、同父级重复 ID 都会报错。输出 JSON 中注册 action 会被写成裸整数子触发 ID，与编辑器导出的动态子触发结构一致。

```json
{
  "name": "父触发",
  "id": 2000000001,
  "event": [["INIT_FINISHED"]],
  "action": [
    {
      "call_function": {
        "func_id": "a1377fd18bfb11f1b9d919bc08ffd172",
        "args": [],
        "returns": [{"var": "T", "type": "TABLE"}]
      }
    },
    {"register_sub_trigger": "按键回调"}
  ],
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
          [
            ["UNREG_TRIGGER", ["CURRENT_DYNAMIC_TRIGGER_INSTANCE"]]
          ],
          []
        ]
      ]
    }
  ]
}
```

生成结构：

- 所有后代子触发递归扁平写入父 JSON 的 `sub_trigger` 字典，键为字符串化子触发 ID。
- 子触发固定写成配置节点：`enabled=false`、`is_conf=true`、`p_trigger_id` 指向直接父触发 ID。
- `CONDITION_LIST` 使用编辑器实测的 `arg_type=100021`；每个触发器的首个 `element_id` 从 `trigger_id * 1000000 + 1` 开始；未使用计时器时不自动声明 `NEW_TIMER`。
- `CONDITION_LIST` 参数会构建 condition 节点，可用于 `IF_THEN_ELSE` 这类动作。
- `IF_THEN_ELSE` 自动写入编辑器导出结构要求的分支布局标记 `fake_op=[2]`。
- 生成器内置补齐 `GET_STRING_TABLE_VAR_1D` 定义：`p=["TABLE","STRING"]`、`t=["STRING"]`、`o=[]`，不修改巨大索引 JSON。
- `STRING_COMPARE` 的 `BOOLEAN_OPERATOR` 参数按实测参考 JSON 使用 `arg_type=100035`。

生命周期约束：

- 动态子触发只由注册 action 激活动态实例，默认不直接启用。
- 若调用方同步拒绝时不发送完成事件，只能在已受理分支内注册动态子触发（例如先判断立即结果的 `request_id != ""`），避免生成永远无法注销的实例。
- 回调子触发需要读取父触发的立即结果局部变量时，变量 tuple 仍写 `["TYPE","name","local"]`；父触发 `var_data` 会覆盖子触发引用到的父局部变量，子触发自身 `var_data` 可为空。
- 回调完成后如需一次性生命周期，使用 `UNREG_TRIGGER(CURRENT_DYNAMIC_TRIGGER_INSTANCE)` 注销当前动态触发实例。
