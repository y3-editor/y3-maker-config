# 投射物物编参考 (Projectile)

## 🎯 投射物 ID 规范

```
[英雄ID][2][序号]
  100001  2  01
     ↓    ↓   ↓
   洛坦 弹道  基础
```

| 英雄 | 弹道 1 | 弹道 2 | 弹道 3 |
|------|--------|--------|--------|
| 洛坦 (100001) | 100001201 | 100001202 | 100001203 |
| 莉莉娅 (100002) | 100002201 | 100002202 | 100002203 |

---

## 📋 投射物基础字段

| 属性 | JSON 字段 | 类型 | 说明 |
|------|-----------|------|------|
| 投射物ID | `key` | 整数 | |
| 投射物ID | `uid` | 字符串 | |
| 名称 | `name` | TID | |
| 描述 | `description` | TID | |
| 图标 | `icon` | 整数 | |

---

## 🚀 移动属性

| 属性 | JSON 字段 | 说明 |
|------|-----------|------|
| 最大持续时间 | `max_duration` | 秒 |
| 特效循环 | `sfx_loop` | 是否循环播放特效 |

---

## 📝 常用特效 ID

| 特效ID | 说明 |
|--------|------|
| 102892 | 紫色弹道 |
| 102247 | 蓝色弹道 |
| 101291 | 火焰弹道 |
| 105525 | 能量球 |

---

## 🚀 脚本命令

```bash
py -3 y3_obj_edit.py -map maps/EntryMap -type projectile [选项] [参数]
```

---

## 📖 脚本参数说明

### 必选参数

| 参数名 | 说明 | 类型 | 示例 |
|--------|------|------|------|
| `-create` | 创建投射物：投射物ID,名称,图标ID | 整数,字符串,整数 | `"100001201,火球,100000"` |
| `-edit` | 编辑投射物：投射物ID | 整数 | `100001201` |

### 可选属性参数

| 参数名 | 说明 | 类型 | 示例 |
|--------|------|------|------|
| `-name` | 名称 | 字符串 | `"火球"` |
| `-description` | 描述 | 字符串 | `"燃烧的火球"` |
| `-icon` | 图标ID | 整数 | `100000` |
| `-max_duration` | 最大持续时间（秒） | 浮点数 | `5.0` |
| `-sfx_loop` | 特效循环 | 布尔 | `true` |
| `-effect_foes` | 对敌特效ID | 整数 | `102107` |
| `-effect_friend` | 对友特效ID | 整数 | `102106` |

> 💡 **特效ID说明**：`effect_foes` 和 `effect_friend` 只修改特效的主ID，保留其他配置（偏移、旋转、缩放等）

### 示例

```bash
# 创建火焰弹道投射物
py -3 y3_obj_edit.py -map maps/EntryMap -type projectile -create "100001201,火球,100000" -max_duration 5.0 -sfx_loop true -effect_foes 102107 -description "燃烧的火球投射物"

# 创建绿色弹道投射物
py -3 y3_obj_edit.py -map maps/EntryMap -type projectile -create "100001202,毒球,100001" -max_duration 3.0 -effect_foes 102106 -effect_friend 102106

# 编辑投射物特效
py -3 y3_obj_edit.py -map maps/EntryMap -type projectile -edit 100001201 -effect_foes 102892 -effect_friend 102892
```
