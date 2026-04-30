---
name: y3-obj-edit
description: >
  Y3 物编编辑器：查询、创建和修改物编数据（单位、技能、魔法效果、投射物、物品）。
  
  ALWAYS use this skill when user mentions: 生成物编、创建单位、生成怪物、生成敌人、生成英雄、创建技能、
  创建Buff、创建魔法效果、创建投射物、做个怪物、做个Boss、设计技能、设计Buff、
  修改物编、调整属性、修改技能属性、修改Buff、批量修改、更新数值、物编数据、
  查询物编、获取物编、查看物编、物编信息。
  
  This skill handles querying, creating and editing objects.
version: 5.0
updated: 2026-04-20
---

# Y3 物编编辑器 v5.0

> **分发型技能**：提供物编查询和创建/修改两大功能。

---

## 🎯 功能一览

| 功能 | 说明 | 方式 |
|------|------|------|
| **查询物编** | 查询现有物编数据 | MCP 工具 |
| **创建/修改物编** | 新建或修改物编属性 | 脚本命令 |

---

## 📖 功能一：查询现有物编数据

通过 MCP 工具 `y3editor` 查询当前地图中已有的物编数据。

### 查询 MCP 工具

| 物编类型 | MCP 工具 | 参数说明 |
|----------|----------|----------|
| **单位** | `y3editor.get_editor_unit_custom_data` | `id_list`: 物编ID数组，`key_list`: 字段名数组 |
| **技能** | `y3editor.get_ability_all_custom_data` | 同上 |
| **物品** | `y3editor.get_editor_item_custom_data` | 同上 |
| **魔法效果** | `y3editor.get_modifier_all_custom_data` | 同上 |
| **投射物** | `y3editor.get_projectile_all_custom_data` | 同上 |

### 查询示例

```json
// 查询所有自定义单位（无参数返回全部）
y3editor.get_editor_unit_custom_data {}

// 查询指定ID的单位
y3editor.get_editor_unit_custom_data {"id_list": [134200001, 134200002]}

// 查询指定字段
y3editor.get_editor_unit_custom_data {"key_list": ["name", "hp_max", "attack"]}

// 组合查询
y3editor.get_editor_unit_custom_data {"id_list": [134200001], "key_list": ["name", "hp_max"]}
```

### 查询流程

```
用户请求查询物编
    │
    ▼
确定物编类型（单位/技能/物品/魔法效果/投射物）
    │
    ▼
调用对应的 MCP 查询工具
    │
    ▼
返回物编数据给用户
```

---

## 📝 功能二：创建或修改物编

通过脚本命令创建新物编或修改现有物编。

### 物编类型路由

| 物编类型 | 参考文档 |
|----------|----------|
| **单位**（英雄、怪物、NPC） | `reference/unit.md` |
| **物品**（装备、消耗品、材料） | `reference/item.md` |
| **技能**（主动、被动技能） | `reference/ability.md` |
| **魔法效果**（Buff/Debuff） | `reference/modifier.md` |
| **投射物**（弹道、技能特效） | `reference/projectile.md` |

### 创建/修改流程

```
第一步：根据物编类型查找 reference/ 下的参考文档
       → 参考文档中包含脚本命令，用于新建或修改该类型物编

第二步：循环第一步，直到处理完所有需要处理的物编类型

第三步：热更并保存（一次性执行）
```

---

## ⛔ 核心禁令

| 禁止 | 正确做法 |
|------|----------|
| 读取 `data_template/` 下的模板 JSON | 通过脚本命令操作 |
| 读取或编辑生成的物编 JSON 文件 | 通过脚本命令操作 |
| 臆造物编 ID | 查询现有物编后再决定 |

> **说明**：所有物编创建/修改必须通过 `reference/` 中定义的脚本命令完成，查询则使用 MCP 工具。

---

## 🔴 热更并保存（创建/修改后必须执行）

```
# 1. 热更物编
y3editor.hotfix_object_editor

# 2. 等待 3 秒

# 3. 保存
y3editor.save_editor
```

> **注意**：查询操作不需要热更和保存。

---

*最后更新: 2026-04-20 v5.0 - 新增 MCP 查询功能*