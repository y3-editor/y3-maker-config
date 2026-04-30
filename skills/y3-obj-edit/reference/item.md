# 物品物编参考 (Item)

## 🎯 物品 ID 规范

```
物品ID: 500001 - 599999 (前缀 5)
消耗品: 500001 - 509999
装备:   510001 - 519999
材料:   520001 - 529999
```

---

## 📋 物品基础字段

| 字段 | 说明 | 类型 | 示例值 |
|------|------|------|--------|
| `key` | 物品ID | 整数 | `500001` |
| `uid` | 物品ID | 字符串 | `"500001"` |
| `name` | 名称TID | 整数 | `-1935409530` |
| `description` | 描述TID | 整数 | `1917686408` |
| `icon` | 物品图标ID | 整数 | `100000` |
| `model` | 掉落物模型ID | 整数 | `10022` |
| `level` | 物品等级 | 整数 | `1` |

---

## 📦 堆叠与充能

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `maximum_stacking` | 最大堆叠数量 | `5` |
| `maximum_charging` | 最大充能数量 | `5` |
| `cur_stack` | 初始堆叠数量 | `1` |
| `cur_charge` | 初始充能数量 | `0` |

---

## 🔧 物品行为

| 字段 | 说明 | 示例值 |
|------|------|--------|
| `auto_use` | 是否自动使用 | `false` |
| `use_consume` | 使用消耗类型 | `1` |
| `discard_enable` | 可丢弃 | `true` |
| `discard_when_dead` | 死亡时丢弃 | `true` |
| `delete_on_discard` | 丢弃时删除 | `false` |
| `sale_enable` | 可出售 | `true` |
| `drop_stay_time` | 掉落物存在时间 | `9999` |
| `hp_max` | 掉落物最大生命 | `100` |

---

## 💪 属性附加字段

> ⚠️ **重要**：所有 `attached_*` 属性在 JSON 中均为 **5 元素数组**：
> `[基础属性, 基础加成, 增益属性, 增益加成, 总属性加成]`
>
> 脚本参数传入 **5 个逗号分隔的值**，或仅传单值（其余自动填 `0.0`）。
>
> ```json
> "attached_hp_max": [
>     1.0,
>     0.0,
>     0.0,
>     0.0,
>     0.0
> ]
> ```
>
> 命令行写法：
> ```bash
> -attached_hp_max "100.0,0.0,0.0,0.0,0.0"   # 5 维完整写法
> -attached_hp_max 100.0                        # 单值简写（等价于上行）
> ```

| 字段 | 说明 | 数组含义（5位） |
|------|------|----------------|
| `attached_hp_max` | 附加最大生命 | [基础属性, 基础加成, 增益属性, 增益加成, 总属性加成] |
| `attached_hp_rec` | 附加生命恢复 | 同上 |
| `attached_mp_max` | 附加最大魔法 | 同上 |
| `attached_mp_rec` | 附加魔法恢复 | 同上 |
| `attached_attack_phy` | 附加物理攻击 | 同上 |
| `attached_attack_mag` | 附加魔法攻击 | 同上 |
| `attached_defense_phy` | 附加物理防御 | 同上 |
| `attached_defense_mag` | 附加魔法防御 | 同上 |
| `attached_strength` | 附加力量 | 同上 |
| `attached_agility` | 附加敏捷 | 同上 |
| `attached_intelligence` | 附加智力 | 同上 |
| `attached_critical_chance` | 附加暴击率（**百分比**） | 同上 |
| `attached_critical_dmg` | 附加暴击伤害（**百分比**） | 同上 |
| `attached_dodge_rate` | 附加闪避率（**百分比**） | 同上 |
| `attached_hit_rate` | 附加命中率（**百分比**） | 同上 |
| `attached_pene_phy` | 附加物理穿透（**百分比**） | 同上 |
| `attached_pene_mag` | 附加魔法穿透（**百分比**） | 同上 |
| `attached_attack_speed` | 附加攻击速度（**百分比**） | 同上 |
| `attached_move_speed` | 附加移动速度 | 同上 |

---

## ⚔️ 物品技能绑定

```json
// 主动技能
"attached_ability": {
    "__tuple__": true,
    "items": [100001001]  // 技能ID列表
}

// 被动技能
"attached_passive_abilities": {
    "__tuple__": true,
    "items": [100001002]  // 被动技能ID列表
}
```

---

## 🚀 脚本命令

```bash
py -3 y3_obj_edit.py -map maps/EntryMap -type item [选项] [参数]
```

---

## 📖 脚本参数说明

### 必选参数

| 参数名 | 说明 | 类型 | 示例 |
|--------|------|------|------|
| `-create` | 创建物品：物品ID,名称,图标ID | 整数,字符串,整数 | `"510001,火焰剑,100000"` |
| `-edit` | 编辑物品：物品ID | 整数 | `510001` |

### 可选属性参数

| 参数名 | 说明 | 类型 | 示例 |
|--------|------|------|------|
| `-name` | 名称 | 字符串 | `"火焰剑"` |
| `-description` | 描述 | 字符串 | `"一把燃烧的利剑"` |
| `-icon` | 图标ID | 整数 | `100000` |
| `-model` | 掉落物模型ID | 整数 | `10022` |
| `-level` | 物品等级 | 整数 | `1` |
| `-maximum_stacking` | 最大堆叠数量 | 整数 | `5` |
| `-maximum_charging` | 最大充能数量 | 整数 | `5` |
| `-cur_stack` | 初始堆叠数量 | 整数 | `1` |
| `-cur_charge` | 初始充能数量 | 整数 | `0` |
| `-auto_use` | 是否自动使用 | 布尔 | `false` |
| `-use_consume` | 使用消耗次数 | 整数 | `1` |
| `-discard_enable` | 可丢弃 | 布尔 | `true` |
| `-discard_when_dead` | 死亡时掉落 | 布尔 | `true` |
| `-delete_on_discard` | 物品在地面上是否会自动销毁 | 布尔 | `false` |
| `-sale_enable` | 可出售 | 布尔 | `true` |
| `-drop_stay_time` | 掉落物在地面上存在时间 | 整数 | `9999` |
| `-hp_max` | 生命值 | 整数 | `100` |
| `-attached_hp_max` | 附加最大生命 | 5维浮点数组 | `100.0` |
| `-attached_hp_rec` | 附加生命恢复 | 5维浮点数组 | `5.0` |
| `-attached_mp_max` | 附加最大魔法 | 5维浮点数组 | `50.0` |
| `-attached_mp_rec` | 附加魔法恢复 | 5维浮点数组 | `3.0` |
| `-attached_attack_phy` | 附加物理攻击 | 5维浮点数组 | `50.0` |
| `-attached_attack_mag` | 附加魔法攻击 | 5维浮点数组 | `30.0` |
| `-attached_defense_phy` | 附加物理防御 | 5维浮点数组 | `20.0` |
| `-attached_defense_mag` | 附加魔法防御 | 5维浮点数组 | `15.0` |
| `-attached_strength` | 附加力量 | 5维浮点数组 | `10.0` |
| `-attached_agility` | 附加敏捷 | 5维浮点数组 | `10.0` |
| `-attached_intelligence` | 附加智力 | 5维浮点数组 | `10.0` |
| `-attached_critical_chance` | 附加暴击率（**百分比**） | 5维浮点数组 | `10.0` |
| `-attached_critical_dmg` | 附加暴击伤害（**百分比**） | 5维浮点数组 | `50.0` |
| `-attached_dodge_rate` | 附加闪避率（**百分比**） | 5维浮点数组 | `5.0` |
| `-attached_hit_rate` | 附加命中率（**百分比**） | 5维浮点数组 | `10.0` |
| `-attached_pene_phy` | 附加物理穿透（**百分比**） | 5维浮点数组 | `10.0` |
| `-attached_pene_mag` | 附加魔法穿透（**百分比**） | 5维浮点数组 | `10.0` |
| `-attached_attack_speed` | 附加攻击速度（**百分比**） | 5维浮点数组 | `20.0` |
| `-attached_move_speed` | 附加移动速度 | 5维浮点数组 | `0.5` |
| `-attached_ability` | 主动技能列表（逗号分隔技能ID） | 整数数组 | `"100001001"` |
| `-attached_passive_abilities` | 被动技能列表（逗号分隔技能ID） | 整数数组 | `"100001002,100001003"` |

### 示例

```bash
# 创建装备（火焰剑，附加物攻和暴击）
py -3 y3_obj_edit.py -map maps/EntryMap -type item -create "510001,火焰剑,100000" -level 5 -maximum_stacking 1 -attached_attack_phy 50 -attached_critical_chance 10.0 -description "一把燃烧的利剑，附加火焰伤害"

# 创建消耗品（回复药水）
py -3 y3_obj_edit.py -map maps/EntryMap -type item -create "500001,生命药水,100001" -maximum_stacking 10 -auto_use false -description "恢复100点生命值"

# 编辑物品属性
py -3 y3_obj_edit.py -map maps/EntryMap -type item -edit 510001 -attached_attack_phy 80 -attached_critical_chance 15.0
```