# 直线投射物技能模板 (A 级 · 零依赖)

> **等级**：A
> 零依赖纯工具。`M.setup(params)` 传参即用，不依赖任何项目层（Class/BaseAbility/GamePlay）。
> 仅使用 y3 引擎原生 API，可跨任意 Y3 项目直接使用。

## 模板登记

### a-projectile-line

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 直线投射物视觉管线 |
| 路径 | `.codemaker/templates/a-projectile-line/` |
| 状态 | `draft` |
| 版本 | `v1.0.0` |
| 能力标签 | `projectile-line`, `mover-line`, `skill-visual`, `particle-pipeline`, `fan-spread`, `zero-dependency` |
| 适用场景 | 任何"朝某方向发射投射物，直线飞行命中敌人"的技能视觉表现。扇形散射、连续发射、单发直线。穿透/非穿透。 |
| 依赖 | —（仅 y3 引擎 API） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → { trigger, cleanup }` |
| 参数 | 见下方参数表 |
| 测试状态 | `tested, 2026-05-29, 5/5 structural in agentmap (execute_lua). Runtime path needs real units` |
| 集成说明 | 1. `local Skill = include 'a-projectile-line'` 2. `local skill = Skill.setup({...})` 3. 在事件中调用 `skill.trigger(point, angle)` |

---

## 架构

```
用户事件 (普通攻击/定时器/按键)
    │
    ▼
skill.trigger(originPoint, baseAngle)
    │
    ├── 可选: on_cast() 回调
    ├── 出手粒子 (release_particle)
    ├── 创建投射物 (y3.projectile.create)
    │   └── mover_line (mover_line)
    │       ├── on_hit → wait(0.03) → 受击粒子 + on_hit(targetUnit)
    │       └── on_remove → orb:remove()
    └── 返回

skill.cleanup() → 清理所有飞行中投射物
```

## 参数表

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `owner` | Unit | ✅ | — | 发射者单位 |
| `projectile_id` | integer | ✅ | — | 投射物模型 key |
| `projectile_speed` | number | ✅ | — | 飞行速度 |
| `projectile_count` | integer | ✅ | — | 投射物数量 |
| `projectile_size` | number | — | 1.0 | 投射物缩放 |
| `collision_radius` | number | ✅ | — | 碰撞半径 (内部自动乘 projectile_size) |
| `linear_range` | number | ✅ | — | 飞行距离 |
| `spread_angle` | number | — | 0 | 扇形角度 (0=单发, 30=均分散射) |
| `penetration` | boolean | — | false | 穿透(穿过多目标) |
| `height` | number | — | 100 | 飞行高度 |
| `release_particle` | integer | — | — | 出手粒子 ID |
| `hit_particle` | integer | — | — | 受击粒子 ID |
| `fire_mode` | "fan"\|"sequential"\|"single" | — | "fan" | 发射模式 |
| `interval` | number | — | 0.15 | 连续发射间隔 (sequential 模式) |
| `on_hit` | fun(target) | ✅ | — | 命中回调 — 在此造成伤害 |
| `on_cast` | fun() | — | — | 施法回调 — 在此广播事件 |

## 接入示例

```lua
-- 1. 引入模板
local ProjectileLine = include 'a-projectile-line'  -- 或 require

-- 2. 在技能初始化时 setup
local skill = ProjectileLine.setup({
    owner = self._unit,
    projectile_id = 112,
    projectile_speed = 1800,
    projectile_count = 3,
    projectile_size = 1.0,
    collision_radius = 100,
    linear_range = 1200,
    spread_angle = 30,
    release_particle = 103902,
    hit_particle = 104959,
    on_hit = function(targetUnit)
        -- 你的伤害逻辑
        self:doCustomDamage({ target = targetUnit, ... })
    end,
    on_cast = function()
        GamePlay.gameEventMgr:Publish(...)
    end,
})

-- 3. 在触发点调用
-- 例: 每攻击 N 次触发
unit:event("施法-出手", function(trg, data)
    if not isAtk(data.ability) then return end
    local target = data.ability_target_unit
    local angle = unit:get_point():get_angle_with(target:get_point())
    skill.trigger(unit:get_point(), angle)
end)

-- 4. 技能移除时清理
function onLose()
    skill.cleanup()
end
```

## 对比 C 级旧版

| 维度 | C 级 (c-projectile-line) | A 级 (a-projectile-line) |
|------|--------------------------|--------------------------|
| 依赖 | Class + BaseAbility + GamePlay.* | 仅 y3 引擎 API |
| 接入方式 | 继承 BaseAbility, 重写方法 | `M.setup(params)` 传参 |
| 伤害 | 绑定 doCustomDamage | `on_hit` 回调, 用户自由实现 |
| 触发 | addAtkCountEvent/startCDBasedCast | 手动调 `trigger()`, 用户控制时机 |
| 可跨项目 | ❌ | ✅ |

## 已知限制

- 不支持抛物线/贝塞尔弹道
- 不支持追踪目标 (mover_target)
- 不支持弹射 (需递归 createProjectile)
- 投射物的对偶碰撞依赖 `mover_line` 的 `hit_radius`, 非精确碰撞

## 源工程溯源

- 源逻辑: `gamePlay/ability/Multiple.lua` + `Rocket.lua` + `Dagger.lua`
- 重写日期: 2026-05-25
- 重写方式: 提取纯视觉管线, 剥离 BaseAbility/GamePlay 依赖
