# 点范围AOE技能模板 (A 级 · 零依赖)

> **等级**：A
> 零依赖纯工具。`M.setup(params)` 传参即用，不依赖任何项目层。
> 仅使用 y3 引擎原生 API，可跨任意 Y3 项目直接使用。

## 模板登记

### a-aoe-point

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 点范围AOE视觉管线 |
| 路径 | `.codex/templates/a-aoe-point/` |
| 状态 | `draft` |
| 版本 | `v1.0.0` |
| 能力标签 | `aoe`, `area-damage`, `skill-visual`, `particle-pipeline`, `circle-aoe`, `rect-aoe`, `zero-dependency` |
| 适用场景 | 任何"对地面/目标位置造成范围伤害"的技能视觉表现。圆形(单段/多段)、矩形AOE。 |
| 依赖 | —（仅 y3 引擎 API） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → { trigger, cleanup }` |
| 参数 | 见下方参数表 |
| 测试状态 | `tested, 2026-05-29, 5/5 structural in agentmap (execute_lua). Runtime path needs real units` |
| 集成说明 | 1. `local Aoe = include 'a-aoe-point'` 2. `local skill = Aoe.setup({...})` 3. 在事件中调用 `skill.trigger(targetPoint)` |

---

## 架构

```
用户事件 (定时器/攻击计数/按键)
    │
    ▼
skill.trigger(targetPoint, faceAngle)
    │
    ├── 可选: on_cast() 回调
    ├── 预警粒子 (release_particle, time=delay)
    │   ├── 视觉半径: release_scale（不填则 aoe_radius/400）
    │   └── 播放速度: release_speed（通过 set_animation_speed 生效）
    ├── timer.wait(delay)
    │   ├── 主动移除预警粒子，避免残留与命中爆炸重叠
    │   ├── selector:in_shape → pick() → 单位列表
    │   ├── 命中粒子 (hit_particle, hit_scale, hit_speed)
    │   └── on_hit(targetList)
    └── 返回

skill.cleanup() → 取消所有进行中的 timer
```

## 参数表

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `owner` | Unit | ✅ | — | 施法者单位 |
| `aoe_radius` | number | ✅ | — | AOE 半径 (圆形) |
| `delay` | number | ✅ | — | 预警→伤害延迟(秒) |
| `count` | integer | — | 1 | 段数 (>1 = 多段) |
| `interval` | number | — | =delay | 段间隔 (多段) |
| `release_particle` | integer | — | — | 预警粒子 ID |
| `hit_particle` | integer | — | `102919` | 命中粒子 ID |
| `release_speed` | number | — | `1` | 预警特效播放速度；创建粒子后调用 `Particle:set_animation_speed`，不是 `create` 参数 |
| `hit_speed` | number | — | `1` | 命中特效播放速度 |
| `release_scale` | number | — | `aoe_radius / 400` | 预警特效缩放；不同特效原始半径不同，建议按资源单独校准 |
| `hit_scale` | number | — | `aoe_radius / 400` | 命中特效缩放 |
| `aoe_type` | "circle"\|"rect" | — | "circle" | AOE 形状 |
| `rect_width` | number | rect✅ | — | 矩形宽度 |
| `rect_length` | number | rect✅ | — | 矩形长度 |
| `on_hit` | fun(targetList) | ✅ | — | 命中回调 — 在此批量伤害 |
| `on_cast` | fun() | — | — | 施法回调 |
| `get_target_point` | fun(): Point | — | — | 动态目标点 (多段用, 每段调用) |

## 接入示例

```lua
local AoePoint = include 'a-aoe-point'

-- 单段圆形 AOE：红色圆形预警圈 → 延迟 → 命中爆炸
local skill = AoePoint.setup({
    owner = self._unit,
    aoe_radius = 700,
    delay = 1.2,

    -- 当前空模板工程已验证可查到的资源：
    -- 106059 = Common_yujing02A，圆环/警戒/红色/圆形范围
    -- 100098 = 橙色火焰爆炸
    release_particle = 106059,
    hit_particle = 100098,

    -- 重要：y3.particle.create 不读取 speed 字段；模板会在创建后调用 set_animation_speed。
    -- 106059 的原始动画偏长，本工程按 1.2 秒延迟校准为 3.9。
    release_speed = 3.9,
    hit_speed = 1.0,

    -- 重要：预警视觉半径不一定等于伤害半径，不同特效需单独校准。
    -- 本工程中 aoe_radius=700 与 106059 对齐时，release_scale=1.5。
    release_scale = 1.5,
    hit_scale = 1.75,

    on_hit = function(targetList)
        for _, target in ipairs(targetList) do
            self:doCustomDamage({ target = target, ... })
        end
    end,
    on_cast = function()
        -- 可选：播放音效、广播事件、记录日志等
    end,
})

-- 触发
skill.trigger(targetUnit:get_point())

-- 多段圆形 AOE (暴风雪/流星雨)
local multiSkill = AoePoint.setup({
    owner = self._unit,
    aoe_radius = 300,
    delay = 0.3,
    count = 5,
    interval = 0.5,
    release_particle = 106059,
    hit_particle = 100098,
    release_speed = 3.9,
    release_scale = 1.5,
    get_target_point = function()
        -- 每段重新取样目标位置
        return targetUnit:get_point()
    end,
    on_hit = function(targetList) ... end,
})

-- 清理
function onLose()
    skill.cleanup()
end
```

### 调试圆校准方法

接入新预警特效时，建议先绘制真实伤害半径作为参考圆，再微调 `release_scale`。绿色调试圆代表实际 `aoe_radius`，红色预警特效代表玩家看到的范围：

```lua
local shape = y3.shape.create_circular_shape(aoe_radius)
GameAPI.debug_draw_filter_area_circular(
    targetPoint.handle,
    shape.handle,
    delay,
    '#00ff00',
    nil
)
```

当预警圈视觉边缘与调试圆基本重合后，再移除调试绘制代码。当前工程验证出的对齐参数为：`aoe_radius=700`, `release_particle=106059`, `release_scale=1.5`, `release_speed=3.9`, `delay=1.2`。

### 测试接入注意

- 若测试工程没有默认单位物编，需要先创建测试单位或替换示例单位 ID；本工程测试时创建了 `AOE测试单位 (200001)`。
- 测试代码不要固定依赖玩家 1/2，建议从 `y3.player_group.get_all_players():pick()` 获取可用玩家，并用中立敌对玩家兜底，确保 `selector:is_enemy(owner:get_owner())` 能选中目标。
- 命中特效只会在选中敌方单位后播放；若只有预警没有命中爆炸，优先检查目标阵营关系和筛选器结果。

## 已知限制

- 扇形 AOE 需自行添加 (y3.shape.create_sector_shape)
- 多段 AOE 段间隔固定, 不支持渐变加速
- 不跟踪移动目标 (多段需通过 get_target_point 重新定位)
- 预警粒子默认缩放 = `aoe_radius / 400` 只是兜底经验值；正式接入应通过调试圆校准 `release_scale`
- 特效播放速度必须通过 `Particle:set_animation_speed` 调整，不能依赖 `y3.particle.create({ speed = ... })`
- 仅设置 `time = delay` 不一定能避免预警残留；模板会在结算前主动移除预警粒子

## 源工程溯源

- 源逻辑: `gamePlay/ability/bond/Meteorite.lua` + `Katana.lua` + `LightningStaff.lua`
- 重写日期: 2026-05-25
- 重写方式: 提取纯视觉管线, 剥离 BaseAbility/GamePlay 依赖
