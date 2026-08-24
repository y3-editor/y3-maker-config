# Y3 ECA 能力总览

> Y3 编辑器 ECA（Event-Condition-Action）触发器系统的完整工具链。
> 基于真实大型 ECA 项目（射手大师2 / 1666 条触发器）验证 100% 往返兼容。

---

## 一、概念

ECA 是 Y3 编辑器的可视化逻辑系统，对应 JSON 数据格式。一个触发器（trigger）由四部分组成：

```
触发器 = 事件(event) + 条件(condition) + 动作(action) + 元数据
```

存放位置（容器）多达 7 种：

| 容器 | 路径 | 用途 |
|------|------|------|
| 全局触发器 | `maps/<map>/global_trigger/trigger/*.json` | 地图全局逻辑 |
| 单位触发器 | `maps/<map>/unit/<id>.json` `trigger_dict` | 单位绑定逻辑 |
| 技能触发器 | `maps/<map>/ability/<id>.json` `trigger_dict` | 技能效果 |
| Buff 触发器 | `maps/<map>/modifier/<id>.json` `trigger_dict` | 状态/Buff 效果 |
| 物品触发器 | `maps/<map>/item/<id>.json` `trigger_dict` | 物品逻辑 |
| 投射物触发器 | `maps/<map>/projectile/<id>.json` `trigger_dict` | 投射物逻辑 |
| 插件触发器 | `plugins/<uuid>/game_play/trigger_data` | 插件封装的触发器 |
| 插件函数库 | `plugins/<uuid>/game_play/func_lib_data` | 插件封装的自定义 ECA 函数 |

---

## 二、工具脚本（11 个）

均位于 `.codemaker/skills/eca-json-builder/`。

| 脚本 | 用途 | CLI 子命令 |
|------|------|-----------|
| `lookup.py` | ECA 名称验证 + 全局事件列表 | (位置参数) `--brief` `--list-events` |
| `read_trigger.py` | 触发器 JSON → DSL | (位置参数) `--container` `--key` `--all` `--out` `--raw` |
| `gen_trigger.py` | DSL → 触发器 JSON（新建） | (位置参数) `--dry-run` |
| `edit_trigger.py` | 修改/删除已有触发器 | (位置参数) `--container` `--key` `--delete` `--dry-run` |
| `plugin_eca.py` | 插件 func_lib / trigger 数据读写 | `list` `read` `dsl` |
| `table_reader.py` | ECA 数据表 CRUD | `list` `read` `find` |
| `var_manager.py` | 全局变量 / 物编组变量 CRUD | `list` `add` `remove` `show` |
| `project_event.py` | 项目自定义事件读写 | `list` `read` |
| `archive_reader.py` | 存档系统读写 | `list` `read` |
| `eca_json_helper.py` | 底层模板/校验/合并 | (库) |
| `eca_index.json` | ECA 索引数据 | (数据) |

---

## 三、DSL 格式（所有读写的中间表示）

```json
{
  "map": "EntryMap",
  "triggers": [
    {
      "name": "新建触发器",
      "id": 177635329,
      "group_id": 134233289,
      "enabled": true,
      "valid": true,
      "call_enabled": true,
      "p_trigger_id": null,
      "is_conf": false,
      "var_data": {
        "types": {"FLOAT": {"sh": 0.0}},
        "lengths": {"sh": 0},
        "order": ["sh"]
      },
      "event": [
        ["ABILITY_OBTAIN"]
      ],
      "condition": [],
      "action": [
        ["SET_VARIABLE",
         {"var": "speed", "type": "FLOAT", "scope": "actor"},
         200.0
        ],
        ["CALL_TRIGGER_FUNC",
         ["4ed2810fec3e11ee8758a8a1592de74e",
          ["GET_UNIT_FROM_EVENT"],
          {"var": "speed", "type": "FLOAT", "scope": "actor"},
          "ori_speed",
          {"op_arg": ["技能"]}
         ],
         {"call_rt_arg_idxes": [0]}
        ]
      ]
    }
  ]
}
```

### DSL 元素

| DSL 元素 | 对应 JSON | 说明 |
|----------|-----------|------|
| `["NAME", arg1, arg2, ...]` | `{"action_type": "NAME", "args_list": [...]}` | event / condition / action |
| `{"var":"X","type":"T","scope":"S"}` | `{"arg_type":...,"sub_type":11或1,"args_list":[[T,X,S]]}` | 变量引用，scope 可为 `local`/`actor` |
| `["FUNC_NAME", arg1, ...]` | `{"arg_type":...,"sub_type":"FUNC_NAME","args_list":[...]}` | 函数调用 |
| `[hex_uuid_32, arg1, ...]` | 同上，但 sub_type 为 32 字符 UUID | 自定义函数 |
| `{"op_arg": [arg1, ...]}` | `{"op_arg":[...],"op_arg_enable":[true,...]}` | 可选参数 |
| `{"bp": true}` | `{"bp": true}` | 断点标记 |
| `{"call_rt_arg_idxes": [0]}` | `{"call_rt_arg_idxes":[0]}` | 运行时实参索引 |
| 字面量 `123 / "str" / 1.5 / true` | `{"arg_type":...,"sub_type":1,"args_list":[123]}` | 直接值 |

---

## 四、命令速查

### 4.1 验证 ECA 名

```bash
py -3 lookup.py UNIT_DIE PRINT_MESSAGE_ACTION_TO_DIALOG --brief
py -3 lookup.py --list-events
```

### 4.2 阅读触发器

```bash
# 全局
py -3 read_trigger.py "触发器名" --map EntryMap
py -3 read_trigger.py --all --map EntryMap                # 全部摘要
py -3 read_trigger.py "名" --out dsl.json                # 落盘
py -3 read_trigger.py "名" --raw                         # 原 JSON

# 物编（5 种容器）
py -3 read_trigger.py --container ability --key 134233289 --map EntryMap
py -3 read_trigger.py --container modifier --key 134246396 --map EntryMap
py -3 read_trigger.py --container item --key 134218624 --map EntryMap
py -3 read_trigger.py --container unit --key 100001 --map EntryMap
py -3 read_trigger.py --container projectile --key 100001 --map EntryMap

# 直接路径
py -3 read_trigger.py --path E:\path\to\trigger.json
```

### 4.3 新建触发器

```bash
py -3 gen_trigger.py dsl.json
py -3 gen_trigger.py dsl.json --dry-run
```

### 4.4 修改触发器

```bash
# 全局
py -3 edit_trigger.py dsl.json
py -3 edit_trigger.py dsl.json --dry-run

# 物编
py -3 edit_trigger.py dsl.json --container ability --key 134233289
py -3 edit_trigger.py dsl.json --container modifier --key 134246396
```

> DSL 必须含 `id` 字段（来自 `read_trigger.py`）。`enabled`/`valid`/`call_enabled` 默认 true。
> element_id 确定性重建：`trigger_id * 1e6 + counter`。
> 自动 `.bak` 备份。

### 4.5 删除触发器

```bash
py -3 edit_trigger.py --delete "触发器名"
py -3 edit_trigger.py --delete "触发器名" --container ability --key 134233289
py -3 edit_trigger.py --delete "触发器名" --dry-run
```

### 4.6 插件函数库

```bash
py -3 plugin_eca.py list <plugin_dir>                    # 列出 func_lib_data
py -3 plugin_eca.py list <plugin_dir> --trigger          # 列出 trigger_data
py -3 plugin_eca.py read <plugin_dir> --id 1058021401    # 读单条
py -3 plugin_eca.py dsl --id 1058021401 <plugin_dir>     # 单条 DSL 形态
```

### 4.7 数据表

```bash
py -3 table_reader.py list <table.json或目录>
py -3 table_reader.py read <table.json> --row 5
py -3 table_reader.py read <table.json> --key "BOSS出现时间"
py -3 table_reader.py find <table.json> --key "保留技能时间"
```

> 主键列 auto-detect：自动尝试 `Key`/`key`/`ID`/`id`/`Name`，找不到则用首列。

### 4.8 变量管理

```bash
# 设置项目根（可选，否则 auto-detect）
set Y3_PROJECT_ROOT=E:\YourProject

# 全局变量
py -3 var_manager.py list --map <map>
py -3 var_manager.py add my_var INTEGER --map <map>
py -3 var_manager.py remove my_var --map <map>
py -3 var_manager.py show my_var --map <map>

# 物编组变量
py -3 var_manager.py list --unit 100001 --map <map>
py -3 var_manager.py add boss UNIT_ENTITY --unit 100001 --map <map>
```

`project_trigger_var.json` 不存在时自动创建。

### 4.9 项目自定义事件

```bash
py -3 project_event.py list <project_root>
py -3 project_event.py read <project_root> --id <event_id>
```

### 4.10 存档系统

```bash
py -3 archive_reader.py <project_root> list --map <map>
py -3 archive_reader.py <project_root> read --map <map>           # archive.json
py -3 archive_reader.py <project_root> read --slot 1 --map <map>  # 单个槽位
py -3 archive_reader.py <project_root> read --storage --slot RANK
py -3 archive_reader.py <project_root> read --score
```

---

## 五、容器覆盖矩阵

| 容器 | 读取 | 新建 | 修改 | 删除 |
|------|:----:|:----:|:----:|:----:|
| 全局 `global_trigger/` | ✅ | ✅ | ✅ | ✅ |
| `unit/` | ✅ | ✅ | ✅ | ✅ |
| `ability/` | ✅ | ✅ | ✅ | ✅ |
| `modifier/` | ✅ | ✅ | ✅ | ✅ |
| `item/` | ✅ | ✅ | ✅ | ✅ |
| `projectile/` | ✅ | ✅ | ✅ | ✅ |
| 插件 `func_lib_data` | ✅ | ✅ | ✅ | — |
| 插件 `trigger_data` | ✅ | ✅ | ✅ | — |

---

## 六、变量类型全表（30 种）

| 类型 | arg_type | 默认值 | 用途 |
|------|---------:|--------|------|
| `STRING` | 100003 | `""` | 字符串 |
| `BOOLEAN` | 100001 | `false` | 布尔 |
| `FLOAT` | 100000 | `0.0` | 浮点 |
| `ANGLE` | 100225 | `0.0` | 角度 |
| `INTEGER` | 100002 | `0` | 整数 |
| `POINT` | 100004 | `[0,0]` | 二维坐标 |
| `RECTANGLE` | 100009 | `0` | 矩形区域 |
| `ROUND_AREA` | 100064 | `0` | 圆形区域 |
| `POLYGON` | 100035 | `0` | 多边形区域 |
| `CURVED_PATH` | 100182 | `0` | 曲线路径 |
| `UNIT_ENTITY` | 100006 | `0` | 单位实例 |
| `UNIT_NAME` | 100116 | `""` | 单位 Key |
| `UNIT_GROUP` | 100026 | `0` | 单位组 |
| `MODIFIER_ENTITY` | 100076 | `0` | Buff 实例 |
| `MODIFIER` | 100046 | `0` | Buff Key |
| `ABILITY` | 100014 | `0` | 技能实例 |
| `ABILITY_NAME` | 100046 | `""` | 技能 Key |
| `ITEM_ENTITY` | 100021 | `0` | 物品实例 |
| `ITEM_NAME` | 100116 | `""` | 物品 Key |
| `PROJECTILE_ENTITY` | 100010 | `0` | 投射物实例 |
| `PROJECTILE` | 100031 | `0` | 投射物 Key |
| `SFX_ENTITY` | 100148 | `0` | 特效实例 |
| `LINK_SFX_ENTITY` | 100148 | `0` | 链接特效 |
| `PLAYER` | 100025 | `0` | 玩家 |
| `PLAYER_GROUP` | 100026 | `0` | 玩家组 |
| `TABLE` | 100011 | `0` | 哈希表 |
| `NEW_TIMER` | 100181 | `0` | 计时器 |
| `DAMAGE_TYPE` | 100238 | `0` | 伤害类型 |
| `UNIT_WRITE_ATTRIBUTE` | 100077 | `0` | 单位属性 |
| `DYNAMIC_TRIGGER_INSTANCE` | 100178 | `0` | 动态触发器实例 |
| `UI_PREFAB_INSTANCE` | 100301 | `0` | UI 预制体实例 |
| `STATE` | 100075 | `0` | 状态 |

> 还可解析的 arg_type 类型（仅用于 read，不做变量声明）：`CONDITION_LIST`、`CUS_EVENT`、`ABILITY_FLOAT_ATTRS`、`EVENT_UNIT`、`UNIT_TYPE`、`BOOLEAN_OPERATOR`、`ABILITY_CAST_TYPE`、`ABILITY_TYPE`、`ABILITY_EVENT`、`MODIFIER_EVENT`、`MODIFIER_EFFECT_TYPE`、`ATTR_ELEMENT`、`FLOAT_ARITHMETIC_OPERATOR`、`ROLE_RES_KEY`、`TABLE_VAR`、`SECTOR_SHAPE` 等

---

## 七、典型用法

### 7.1 修改某 Buff 行为

```bash
# 1. 读 → DSL
py -3 read_trigger.py 加速 --container modifier --key 134246396 --out buff.json

# 2. 编辑 buff.json（DSL 友好）

# 3. 写回
py -3 edit_trigger.py buff.json --container modifier --key 134246396
```

### 7.2 批量调整数据表

```bash
# 1. 查看
py -3 table_reader.py list E:\Project\maps\EntryMap\tables\游戏设定.json

# 2. 单行查
py -3 table_reader.py find E:\Project\maps\EntryMap\tables\游戏设定.json --key "BOSS出现时间"

# 3. 用 Python 调 upsert_row API（脚本调用）
```

### 7.3 全量项目验证

```bash
# 全量 round-trip 测试（参考 .codemaker/memory/sandbox/dm32_audit/batch_rt.py）
# 报告：总数 / 崩溃数 / OK 数 / 差异分布
```

---

## 八、保真度报告

基于 DM32（射手大师2）项目验证：

| 指标 | 值 |
|------|----|
| 物编触发器总数 | 1666 |
| Read → DSL → Build 崩溃数 | **0** |
| 数据保真度 | 元数据 100%（element_id 重生成是必然） |
| 局部变量类型覆盖 | 30 种 |
| 自定义函数（hex UUID） | 4261 处全保留 |
| 嵌套深度支持 | 任意层（最深 14 层验证） |

---

## 九、技能入口

| 触发词 | 入口 |
|--------|------|
| 写一条 ECA / 创建触发器 / 生成 ECA | `eca-json-builder` 技能 |
| 读触发器 / 看 ECA | 同上 |
| 改触发器 / 修改 ECA | 同上 |
| 删除触发器 / 删 ECA | 同上 |
| ECA 数据表 / 查表 / 改表 | 同上 |
| ECA 变量管理 | 同上（`var_manager.py`） |
| 插件函数库 / func_lib_data | 同上（`plugin_eca.py`） |

---

## 十、相关文档

- `.codemaker/skills/eca-json-builder/SKILL.md` — 技能详细规则
- `.codemaker/skills/eca-json-builder/eca-json-builder.md` — DSL 完整规范
- `.codemaker/skills/eca-json-builder/eca_index.json` — ECA 索引数据
- `.codemaker/memory/sandbox/dm32_audit/gap_report.md` — DM32 差距分析报告
- `.codemaker/memory/sandbox/dm32_audit/batch_rt.py` — 全量 round-trip 测试脚本

---
*最后更新：2026-06-12 / 基于 DM32（1666 条触发器）验证 100% 往返成功*
