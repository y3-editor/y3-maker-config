# 魔法效果物编参考 (Modifier / Buff)

## 🎯 魔法效果 ID 规范

```
[英雄ID][1][序号]
  100001  1  01
     ↓    ↓   ↓
   洛坦 Buff  眩晕
```

| 英雄 | Buff 1 | Buff 2 | Buff 3 |
|------|--------|--------|--------|
| 洛坦 (100001) | 100001101 | 100001102 | 100001103 |
| 莉莉娅 (100002) | 100002101 | 100002102 | 100002103 |

---

## 📋 魔法效果基础字段

| 属性 | JSON 字段 | 类型 | 说明 |
|------|-----------|------|------|
| 效果ID | `key` | 整数 | |
| 效果ID | `uid` | 字符串 | |
| 名称 | `name` | TID | |
| 描述 | `description` | TID | |
| 图标 | `modifier_icon` | 整数 | |

---

## 🎭 效果类型 (modifier_type)

| 值 | 说明 |
|----|------|
| 1 | 增益 (Buff) |
| 2 | 减益 (Debuff) |

---

## ⚡ 效果表现 (modifier_effect)

| 值 | 说明 |
|----|------|
| 1 | 普通效果 |
| 2 | 控制效果 |
| 3 | 护盾效果 |
| 4 | 光环效果 |

---

## 🛡️ 效果属性字段

| 属性 | JSON 字段 | 类型 | 说明 |
|------|-----------|------|------|
| 最大层数 | `layer_max` | 整数 | |
| 死亡消失 | `disappear_when_dead` | 布尔 | |
| UI显示 | `show_on_ui` | 布尔 | |
| 护盾值 | `shield_value` | 浮点数 | 护盾类型时有效 |
| 护盾类型 | `shield_type` | 整数 | |
| 光环范围 | `influence_rng` | 浮点数 | 光环类型时有效 |
| 影响自身 | `is_influence_self` | 布尔 | |

---

## 🎨 材质颜色配置

常用颜色（RGB）：
- 红色（Debuff）: `255,100,100`
- 黄色（增益）: `255,255,100`
- 蓝色（护盾）: `100,100,255`
- 绿色（治疗）: `100,255,100`

---

## 🚀 脚本命令

```bash
py -3 y3_obj_edit.py -map maps/EntryMap -type modifier [选项] [参数]
```

---

## � 脚本参数说明

### 必选参数

| 参数名 | 说明 | 类型 | 示例 |
|--------|------|------|------|
| `-create` | 创建魔法效果：效果ID,名称,图标ID | 整数,字符串,整数 | `"100001101,眩晕,100008"` |
| `-edit` | 编辑魔法效果：效果ID | 整数 | `100001101` |

### 可选属性参数

| 参数名 | 说明 | 类型 | 示例 |
|--------|------|------|------|
| `-name` | 名称 | 字符串 | `"眩晕"` |
| `-description` | 描述 | 字符串 | `"无法行动"` |
| `-modifier_icon` | 图标ID | 整数 | `100008` |
| `-modifier_type` | 效果类型（1=增益,2=减益） | 整数 | `2` |
| `-modifier_effect` | 效果表现（1=普通,2=控制,3=护盾,4=光环） | 整数 | `2` |
| `-layer_max` | 最大层数 | 整数 | `5` |
| `-disappear_when_dead` | 死亡消失 | 布尔 | `true` |
| `-show_on_ui` | UI显示 | 布尔 | `true` |
| `-shield_value` | 护盾值 | 浮点数 | `100.0` |
| `-shield_type` | 护盾类型 | 整数 | `1` |
| `-influence_rng` | 光环范围 | 浮点数 | `5.0` |
| `-is_influence_self` | 影响自身 | 布尔 | `true` |
| `-material_color` | 材质颜色（R,G,B） | 整数数组 | `"255,100,100"` |

### 示例

```bash
# 创建减益效果（眩晕，红色）
py -3 y3_obj_edit.py -map maps/EntryMap -type modifier -create "100001101,眩晕,100008" -modifier_type 2 -modifier_effect 2 -material_color "255,100,100" -description "无法移动和攻击"

# 创建护盾效果（蓝色）
py -3 y3_obj_edit.py -map maps/EntryMap -type modifier -create "100001102,能量护盾,100009" -modifier_type 1 -modifier_effect 3 -shield_value 200 -material_color "100,100,255"

# 创建光环效果
py -3 y3_obj_edit.py -map maps/EntryMap -type modifier -create "100001103,战斗光环,100010" -modifier_type 1 -modifier_effect 4 -influence_rng 8.0 -is_influence_self true

# 编辑效果属性
py -3 y3_obj_edit.py -map maps/EntryMap -type modifier -edit 100001101 -layer_max 3 -shield_value 150
```