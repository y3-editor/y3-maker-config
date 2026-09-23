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

> 📘 **完整文档见同目录 `eca-json-builder.md`**（841+ 行：结构定义 / Arg 类型 / sub_type 速查 / 变量系统 / 完整示例 / 物编触发器格式 / 工作流 / 参考代码索引 / 插件数据 / 数据表 / 项目事件 / 存档）。

## 概述

在 Y3 编辑器中生成**可见可编辑的正式 ECA 函数和全局触发器实例**。

> 不是 ECA 类型注册（那是 `custom_eca/custom_eca.json` 的职责），也不是 AI/NLP 映射修正（那是 `ExternalResource/readable_eca/*.json`）。

## 脚本清单

均在技能同目录 `.codemaker/skills/eca-json-builder/` 下，零依赖。

| 脚本 | 用途 |
|------|------|
| `eca_json_helper.py` | 触发器生成与校验（`template`/`validate`/`merge`/`normalize-desc`） |
| `lookup.py` | 基于内建 `eca_index.json` 查找 ECA（`--global-events` / `<eca_name>`） |
| `gen_function.py` | 从 DSL 生成项目 ECA 函数并更新 `global_trigger/function/index.txt` |
| `gen_trigger.py` | 生成全局触发器（支持 `--dry-run` 校验、自动 var_data） |
| `read_trigger.py` / `edit_trigger.py` | 读取 / 编辑现有触发器 |
| `var_manager.py` | 全局/局部/物编组变量增删改查（`list`/`add`/`remove`/`show`） |
| `plugin_eca.py` | 插件函数库与触发器数据（`list`/`read`/`dsl`） |
| `table_reader.py` | ECA 数据表读取（`list`/`read`/`find`） |
| `project_event.py` | 项目自定义事件（`list`/`read`） |
| `archive_reader.py` | 存档系统读取（`list`/`read`） |

```bash
py -3 .codemaker\skills\eca-json-builder\eca_json_helper.py template trigger_instance
py -3 .codemaker\skills\eca-json-builder\eca_json_helper.py template function_instance
py -3 .codemaker\skills\eca-json-builder\lookup.py <eca_name>
py -3 .codemaker\skills\eca-json-builder\gen_function.py --dry-run <函数DSL.json>
py -3 .codemaker\skills\eca-json-builder\gen_trigger.py --dry-run ...
```

## 生成后加载到编辑器

函数和触发器必须按依赖顺序加载。当前地图已在编辑器中打开时，严格执行：

1. **生成前保存**：先调用一次 `y3editor.save_editor()`，保留用户当前编辑器修改。
2. **写入函数**：生成并校验全部 `global_trigger/function/*.json` 与 `function/index.txt`，核对索引数、文件数和稳定 `func_id`。
3. **禁止生成后保存**：函数写入后不得再调用 `save_editor`；旧编辑器内存会把新函数文件和索引覆盖掉。
4. **加载函数**：调用 `y3editor.restart_editor(save_before_restart=false)`，等待原地图重新打开，再确认函数文件和索引未被改写。当前 MCP 没有独立的 `open_map` 工具；若目标地图原本未打开，不得臆造调用，需通过编辑器已有入口打开目标地图后再核对函数文件和索引。
5. **加载普通触发器**：函数已进入编辑器内存后，对不含 `sub_trigger` 的文件按顺序串行调用：

```text
y3editor.import_eca(trigger_json_path="<global_trigger/trigger/*.json 的绝对路径>")
```

- `success=true` 表示编辑器已受理；同时记录返回的 `mode`、`trigger_id` 和 `hotfix_status`。
- `hotfix_status=已推送` 表示运行时也已更新；`未连接（仅编辑器侧已更新）` 仍算编辑器加载成功，但要运行完整测试需重新启动游戏。
- 当前 `import_eca` 只接受 `global_trigger/trigger/` 下的触发器，不能传入 `global_trigger/function/` 下的函数文件。
- 不得用路径跳转、临时复制等方式把函数伪装成触发器导入。函数加载阶段必须通过地图重新打开完成。
- **动态子触发使用重启加载**：生成结构使用独立保存的编辑器样本做整表回归比对。含 `sub_trigger` 的文件禁止用 `import_eca` 覆盖加载；写入后必须调用 `restart_editor(save_before_restart=false)`，重开后再保存并校验子触发与裸整数注册 ID 仍完整。

## ⚠️ 关键陷阱

| 项 | 规则 |
|----|------|
| `event_type` | 必须用 `lookup.py` 验证的确切名称，不可自创 |
| 自定义事件 | DSL 可以写事件名称；最终 `CUS_EVENT` 必须由 `maps/<地图名>/customevent.json` 解析为整数 ID。名称缺失或重名时禁止生成 |
| 变量 tuple scope | `["TYPE","name","local"/"global"]`，缺 scope 会标红 |
| `TABLE` 字面量 | 禁止把普通 JSON 对象/列表写成 `arg_type=100011, sub_type=1`；必须先用 `SET_VARIABLE + GET_NEW_TABLE` 创建局部 TABLE，再用 `SET_TABLE_VALUE_1D`/`INSERT_TABLE_VALUE` 填值，调用时传 `sub_type="VARIABLE"` 的 TABLE 变量 |
| 变量初值类型 | STRING→`""`、BOOLEAN→`false`、FLOAT/ANGLE→`0.0`、其余→`0`（写错类型编辑器崩溃） |
| 全局变量 | 需同步写 `variable_dict` + `variable_group_info` + `variable_length_dict` 三字段 |
| `op_arg`/`op_arg_enable` | event/condition/action/build_arg 四类 builder 须补全可选参数字段 |
| ECA 函数身份 | `func_id` 是调用契约；重新生成时必须稳定，调用节点按该 ID 关联 |
| 函数参数描述 | 每个参数都必须在 `func_des` 中以 `{参数名}` 占位符出现，并放在调用文本的语义位置；缺失时生成器直接报错 |
| Lua Bind 参数 | `Eval_Lua_TABLE` 最多提供 5 个参数槽，代码中使用 `args[1]` 到 `args[5]` |
| 函数返回值 | `func_return`、`func_rtv_name_list`、数值动作 `400342` 和局部返回变量必须一致 |

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
