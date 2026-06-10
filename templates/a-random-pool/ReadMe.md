# a-random-pool — 加权随机池

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 加权随机池 |
| 路径 | `.codemaker/templates/a-random-pool/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `random`, `weight`, `pool`, `gacha`, `drop`, `loot`, `weighted-random` |
| 适用场景 | 怪物刷新池、掉落物池、抽卡池（可消耗）、关卡随机事件池、多池并存（每池独立名） |
| 依赖 | `GameAPI.create_random_pool` / `set_random_pool_value` / `get_bitrary_random_pool_value` / `get_random_pool_pointed_weight`；通过 params 注入 |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → RandomPool` |
| 参数 | `params.create_random_pool` (必需，GameAPI 注入)、`params.set_pool_value` (必需，GameAPI 注入)、`params.get_pool_weight` (必需，GameAPI 注入)、`params.get_pool_result` (必需，GameAPI 注入)、`params.name?` (名称)、`params.default_type?` ("int"/"string") |
| 测试状态 | `tested, 2026-05-29, 4/4 int path in agentmap (execute_lua). Bug: getStrResult calls getIntResult which throws type guard error for string pools` |
| 集成说明 | 见下方 §集成指南 |

---

## 功能概述

`setWeight` 配置权重、`getIntResult/getStrResult` 抽取，支持抽后清零（消耗模式）或保留（重复模式）。字符串/整数 ID 自动映射，一个池只认一种类型。

---

## 返回实例 API

| 方法 | 说明 |
|------|------|
| `pool:setWeight(id, weight)` | 设置权重 |
| `pool:getWeight(id) → int` | 查询权重 |
| `pool:getTotalWeight() → int` | 总权重 |
| `pool:getIntResult(remain?) → int` | 抽取整数结果。remain=true 保权重 |
| `pool:getStrResult(remain?) → str` | 抽取字符串结果 |

---

## 集成指南

```lua
local Pool = include '.codemaker.templates.a-random-pool.logic'

-- 创建池
	local monsterPool = Pool.setup({
	    create_random_pool = GameAPI.create_random_pool,
	    set_pool_value     = GameAPI.set_random_pool_value,
	    get_pool_weight    = GameAPI.get_random_pool_pointed_weight,
	    get_pool_result    = GameAPI.get_bitrary_random_pool_value,
	})

-- 配权重
monsterPool:setWeight('goblin', 500)
monsterPool:setWeight('orc', 300)
monsterPool:setWeight('troll', 150)
monsterPool:setWeight('dragon', 50)

-- 抽怪
local monster = monsterPool:getStrResult()  -- 抽后权重清零，不再重复
-- 装备池保留权重
local equip = equipPool:getIntResult(true)
```
