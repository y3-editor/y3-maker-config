# 技能物编参考 (Ability)

## 🎯 技能 ID 规范

```
[英雄ID][技能槽位][等级修饰]
  100001  00       1
     ↓     ↓       ↓
   洛坦    Q      基础
```

| 英雄 | Q 技能 | W 技能 | E 技能 | R 技能 |
|------|--------|--------|--------|--------|
| 洛坦 (100001) | 100001001 | 100001002 | 100001003 | 100001004 |
| 莉莉娅 (100002) | 100002001 | 100002002 | 100002003 | 100002004 |

---

## 📋 技能基础字段

| 属性 | JSON 字段 | 类型 | 说明 |
|------|-----------|------|------|
| 技能ID | `key` | 整数 | |
| 技能ID | `uid` | 字符串 | |
| 名称 | `name` | TID | |
| 描述 | `description` | TID | |
| 图标 | `ability_icon` | 整数 | |
| 技能类型 | `ability_cast_type` | 整数 | 2=主动技能 |
| 最大等级 | `ability_max_level` | 整数 | 通常为 5 |

---

## 🎯 释放方式 (sight_type)

| 值 | 释放方式 | 说明 |
|----|----------|------|
| 0 | 立即释放 | 点击技能直接释放 |
| 1 | 选地点（圆形） | 显示圆形指示器 |
| 2 | 选地点（扇形） | 显示扇形指示器 |
| 3 | 选地点（箭头） | 显示矩形/箭头指示器 |
| 4 | 选目标单位 | 需要点选一个单位 |

### 指示器相关字段

| 字段 | 说明 |
|------|------|
| `circle_radius` | 圆形指示器半径 |
| `sector_radius` | 扇形指示器半径 |
| `sector_angle` | 扇形指示器角度 |
| `arrow_length` | 箭头指示器长度 |
| `arrow_width` | 箭头指示器宽度 |

---

## ⚔️ 技能数值字段（等级数组）

| 属性 | JSON 字段 | 说明 |
|------|-----------|------|
| 冷却时间 | `cold_down_time` | `["8"]` |
| 魔法消耗 | `ability_cost` | `["50"]` |
| 生命消耗 | `ability_hp_cost` | `["0"]` |
| 基础伤害 | `ability_damage` | `["100"]` |
| 伤害范围 | `ability_damage_range` | `["3.0"]` |
| 施法距离 | `ability_cast_range` | `["10.0"]` |

---

## 🎭 技能表现字段

| 属性 | JSON 字段 | 类型 | 说明 |
|------|-----------|------|------|
| 立即释放 | `is_immediate` | 布尔 | |
| 近战技能 | `is_meele` | 布尔 | |
| 施法前摇 | `ability_cast_point` | 浮点数 | |
| 施法后摇 | `ability_bw_point` | 浮点数 | |
| 施法动画 | `cast_animation` | 字符串 | |

---

## 🚀 脚本命令

```bash
py -3 y3_obj_edit.py -map maps/EntryMap -type ability [选项] [参数]
```

---

## 📖 脚本参数说明

### 必选参数

| 参数名 | 说明 | 类型 | 示例 |
|--------|------|------|------|
| `-create` | 创建技能：技能ID,名称,图标ID | 整数,字符串,整数 | `"100001001,火球术,100508"` |
| `-edit` | 编辑技能：技能ID | 整数 | `100001001` |

### 可选属性参数

| 参数名 | 说明 | 类型 | 示例 |
|--------|------|------|------|
| `-name` | 名称 | 字符串 | `"火球术"` |
| `-description` | 描述 | 字符串 | `"向目标发射一个火球"` |
| `-ability_icon` | 图标ID | 整数 | `100508` |
| `-ability_max_level` | 最大等级 | 整数 | `5` |
| `-sight_type` | 释放方式（0=立即,1=圆形,2=扇形,3=箭头,4=选目标） | 整数 | `1` |
| `-cold_down_time` | 冷却时间 | 单值字符串 | `"8"` |
| `-ability_cost` | 魔法消耗 | 单值字符串 | `"50"` |
| `-ability_damage` | 基础伤害 | 单值字符串 | `"100"` |
| `-ability_cast_range` | 施法距离 | 单值字符串 | `"10.0"` |
| `-ability_damage_range` | 伤害范围 | 单值字符串 | `"3.0"` |
| `-circle_radius` | 圆形指示器半径 | 单值字符串 | `"5.0"` |
| `-sector_radius` | 扇形指示器半径 | 单值字符串 | `"10.0"` |
| `-sector_angle` | 扇形指示器角度 | 单值字符串 | `"60"` |
| `-arrow_length` | 箭头长度 | 单值字符串 | `"5.0"` |
| `-arrow_width` | 箭头宽度 | 单值字符串 | `"2.0"` |
| `-ability_cast_point` | 施法前摇 | 浮点数 | `0.2` |
| `-ability_bw_point` | 施法后摇 | 浮点数 | `0.5` |
| `-is_immediate` | 是否立即释放 | 布尔 | `true` |
| `-is_meele` | 是否近战技能 | 布尔 | `false` |
| `-required_level` | 技能学习等级需求（逗号分隔整数，长度=ability_max_level） | 整数数组 | `"1,3,5,7,9"` |

> ⚠️ **数值字段说明**：
> - `cold_down_time`、`ability_cost`、`ability_damage` 等数值字段**只需填写一个值**，不需要逗号分隔
> - 引擎会自动将该值应用到所有技能等级
> - **只有 `required_level` 需要逗号分隔**，且长度必须等于 `ability_max_level`

### 示例

```bash
# 创建主动技能（圆形范围指示器，5级技能需要1/3/5/7/9级学习）
py -3 y3_obj_edit.py -map maps/EntryMap -type ability -create "100001001,火球术,100508" -ability_max_level 5 -sight_type 1 -cold_down_time "8" -ability_cost "50" -ability_damage "100" -circle_radius "5.0" -required_level "1,3,5,7,9" -description "向目标位置发射火球，对范围内敌人造成伤害"

# 创建立即释放技能（3级技能，1/2/3级学习）
py -3 y3_obj_edit.py -map maps/EntryMap -type ability -create "100001002,战吼,100509" -ability_max_level 3 -sight_type 0 -is_immediate true -cold_down_time "15" -required_level "1,2,3"

# 编辑技能冷却和学习等级需求
py -3 y3_obj_edit.py -map maps/EntryMap -type ability -edit 100001001 -cold_down_time "6" -ability_damage "120" -required_level "1,4,7,10,13"
```
