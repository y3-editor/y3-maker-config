---
name: eca-json-builder
description: >
  Y3 ECA 触发器 JSON 拼接技能：在 Y3 编辑器中生成可见可编辑的全局触发器实例、
  物编触发器（单位/技能），以及读取插件函数库、ECA 数据表、项目自定义事件、存档数据。

  Use this skill when user mentions: ECA 触发器、生成触发器、全局触发器、物编触发器、
  trigger JSON、ECA 变量、读取插件触发器、ECA 数据表、项目自定义事件、存档读取。

  内部脚本技能，零依赖（Python 3 标准库 + 内建 eca_index.json）。
version: 1.0
updated: 2026-06-15
---

# ECA 触发器 JSON 拼接技能

> 📘 **完整文档见同目录 `eca-json-builder.md`**（841+ 行：结构定义 / Arg 类型 / sub_type 速查 / 变量系统 / 完整示例 / 物编触发器格式 / 工作流 / 参考代码索引 / 插件数据 / 数据表 / 项目事件 / 存档）。

## 概述

在 Y3 编辑器中生成**可见可编辑的全局触发器实例**。

> 不是 ECA 类型注册（那是 `custom_eca/custom_eca.json` 的职责），也不是 AI/NLP 映射修正（那是 `ExternalResource/readable_eca/*.json`）。

## 脚本清单

均在技能同目录 `.codemaker/skills/eca-json-builder/` 下，零依赖。

| 脚本 | 用途 |
|------|------|
| `eca_json_helper.py` | 触发器生成与校验（`template`/`validate`/`merge`/`normalize-desc`） |
| `lookup.py` | 基于内建 `eca_index.json` 查找 ECA（`--global-events` / `<eca_name>`） |
| `gen_trigger.py` | 生成全局触发器（支持 `--dry-run` 校验、自动 var_data） |
| `read_trigger.py` / `edit_trigger.py` | 读取 / 编辑现有触发器 |
| `var_manager.py` | 全局/局部/物编组变量增删改查（`list`/`add`/`remove`/`show`） |
| `plugin_eca.py` | 插件函数库与触发器数据（`list`/`read`/`dsl`） |
| `table_reader.py` | ECA 数据表读取（`list`/`read`/`find`） |
| `project_event.py` | 项目自定义事件（`list`/`read`） |
| `archive_reader.py` | 存档系统读取（`list`/`read`） |

```bash
py -3 .codemaker\skills\eca-json-builder\eca_json_helper.py template trigger_instance
py -3 .codemaker\skills\eca-json-builder\lookup.py <eca_name>
py -3 .codemaker\skills\eca-json-builder\gen_trigger.py --dry-run ...
```

## ⚠️ 关键陷阱

| 项 | 规则 |
|----|------|
| `event_type` | 必须用 `lookup.py` 验证的确切名称，不可自创 |
| 变量 tuple scope | `["TYPE","name","local"/"global"]`，缺 scope 会标红 |
| 变量初值类型 | STRING→`""`、BOOLEAN→`false`、FLOAT/ANGLE→`0.0`、其余→`0`（写错类型编辑器崩溃） |
| 全局变量 | 需同步写 `variable_dict` + `variable_group_info` + `variable_length_dict` 三字段 |
| `op_arg`/`op_arg_enable` | event/condition/action/build_arg 四类 builder 须补全可选参数字段 |

> 详细字段格式、完整示例、物编触发器（单位/技能）专用格式，全部见 `eca-json-builder.md`。
