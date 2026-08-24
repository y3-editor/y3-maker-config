# ECA 触发器 JSON 拼接技能

## 概述

在 Y3 编辑器中生成**可见可编辑的全局触发器实例**。

> 不是 ECA 类型注册（那是 `custom_eca/custom_eca.json` 的职责），也不是 AI/NLP 映射修正（那是 `ExternalResource/readable_eca/*.json`）。

**脚本清单**（均在技能同目录 `.codemaker/skills/eca-json-builder/` 下）：

| 脚本 | 子命令 | 说明 |
|------|--------|------|
| `eca_json_helper.py` | `template` / `validate` / `merge` / `normalize-desc` | 触发器生成与校验，零依赖 |
| `lookup.py` | `--global-events` / `<eca_name>` | 基于内建 `eca_index.json` 查找，**零依赖** |

```bash
py -3 .codemaker\skills\eca-json-builder\eca_json_helper.py template trigger_instance
py -3 .codemaker\skills\eca-json-builder\lookup.py <eca_name>
```

---

## 外部依赖

**零依赖可独立生效。** 所有脚本仅需 Python 3 标准库 + 内建 `eca_index.json`。

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
py -3 .codemaker\skills\eca-json-builder\lookup.py GAME_PAUSE
# sub_type: "t_system"  ← 全局可用

py -3 .codemaker\skills\eca-json-builder\lookup.py UNIT_DIE
# sub_type: "t_unit"    ← 仅物编可用

py -3 .codemaker\skills\eca-json-builder\lookup.py --global-events
# 列出所有全局可用事件
```

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

## ⚠️ 两条关键规则（源于实测修正）

### 规则1：GENERIC_UNIT_EVENT 参数用 ET_ 前缀

事件名在 `args_list` 中必须加 `ET_` 前缀，对应 `trigger_new.py` 中的枚举名：

```json
// ❌ 错误
{"arg_type": 100008, "sub_type": "GENERIC_UNIT_EVENT", "args_list": ["UNIT_DIE"]}

// ✅ 正确
{"arg_type": 100008, "sub_type": "GENERIC_UNIT_EVENT", "args_list": ["ET_UNIT_DIE"]}
```

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

**常用键盘按键整数值**（来源：`y3/game/const.lua` KeyboardKey）：
| 值 | 按键 |
|---|---|
| `30` | A |
| `48` | B |
| `46` | C |
| `32` | D |
| `18` | E |
| `33` | **F** |
| `34` | G |
| `16` | Q |
| `31` | S |
| `17` | W |
| `2`~`11` | 1~0（数字行） |
| `59` | F1 |
| `60` | F2 |

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
> | `INTEGER` / `UNIT_ENTITY` / `UNIT_NAME` / `SFX_ENTITY` / `POINT` | `0` |
>
> 推荐用 `var_manager.py add` 自动处理，避免手写 JSON 出错。

### 局部变量（trigger var_data）

局部变量在触发器的 `var_data` 中声明，格式：

```json
"var_data": [
    { "NEW_TIMER": {}, "UNIT_ENTITY": { "unit": 0 } },
    { "unit": 0 },
    [ "unit" ]
]
```

- `var_data[0]`: 按类型分组 `{ TYPE: { name: 0 } }`，`NEW_TIMER` 固定保留
- `var_data[1]`: 按名称索引 `{ name: 0 }`
- `var_data[2]`: 有序名称列表 `[ name ]`

### 变量引用（tuple 三元素+scope）

引用变量时 tuple 必须三元素 `["TYPE", "name", scope]`：
- `scope = "local"` → 局部变量，声明在 trigger 的 `var_data`
- `scope = "global"` → 全局变量，声明在 `globaltriggervariable.json`

```json
// 局部变量引用
{"__tuple__": true, "items": ["UNIT_ENTITY", "unit", "local"]}

// 全局变量引用
{"__tuple__": true, "items": ["UNIT_ENTITY", "unit", "global"]}
```

> ⚠️ 全局变量不在 trigger `var_data` 中声明，变量引用通过 scope 区分。

---

用 `lookup.py` 反查 ECA 的参数类型：
```bash
py -3 .codemaker\skills\eca-json-builder\lookup.py CREATE_UNIT
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

## 工作流

0. **确定目标地图目录**（强制第一步）
   - Y3 项目的触发器路径为 `maps/<地图名>/global_trigger/trigger/`
   - 当前编辑的地图名从 `maps/` 子目录获取（如 `EntryMap`）
   - 目标路径示例：`maps/EntryMap/global_trigger/trigger/`

1. **取模板**
   ```bash
   py -3 .codemaker\skills\eca-json-builder\eca_json_helper.py template trigger_instance
   ```

2. **查 ECA 参数**（确定 `args_list` 顺序和类型）
   ```bash
   py -3 .codemaker\skills\eca-json-builder\lookup.py PRINT_MESSAGE_ACTION_TO_DIALOG
   ```
   > 优先用 `lookup.py`（读内建索引，零依赖）。仅当需要引擎最新定义时才用 `eca_json_helper.py lookup`。

3. **按 param 顺序填充 args_list**，每个参数一个 Arg 节点，`arg_type`/`sub_type` 用整数 ID

4. **校验**
   ```bash
   py -3 .codemaker\skills\eca-json-builder\eca_json_helper.py validate <触发器名>.json
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
[target, 技能(CUR_ABILITY), caster, 伤害类型, 伤害值, 是否暴击]
```

| 位置 | arg_type | sub_type | 值 | 说明 |
|------|----------|----------|----|------|
| 0 | 100006 | 11 | `["UNIT_ENTITY","target","local"]` | 受伤目标 |
| 1 | 100014 | `"CUR_ABILITY"` | `[]` | 当前技能实例 |
| 2 | 100006 | 11 | `["UNIT_ENTITY","caster","local"]` | 伤害来源 |
| 3 | **100064** | 1 | `[1]` | 伤害类型（1=普通物理） |
| 4 | 100000 | 1 | `[150.0]` | 伤害值 |
| 5 | 100001 | 1 | `[false]` | 是否暴击 |

> ⚠️ 伤害类型 `arg_type=100064`（不是 100238），`args_list: [1]`
> 必须附带 `"op_arg": [null×9]` + `"op_arg_enable": [false×9]`

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
| `APPLY_DAMAGE` 目标 | 可用变量引用 `target`，也可直接用 `FOR_EACH_SELECTED_UNIT` |
| `APPLY_DAMAGE` 来源 | 填 `FOR_EACH_SELECTED_UNIT`（当前遍历单位）或 `caster` 变量均可 |

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

## 存档系统

```bash
py -3 archive_reader.py list <project_root> --map <map>
py -3 archive_reader.py read <project_root> --map <map>           # archive.json
py -3 archive_reader.py read <project_root> --map <map> --slot 1  # archive.json slot 1
py -3 archive_reader.py read <project_root> --map <map> --storage --slot RANK
```

文件：`maps/<map>/archive/{archive.json, archive_storage.json, mapscore.json}`
