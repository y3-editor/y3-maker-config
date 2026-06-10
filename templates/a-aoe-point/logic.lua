--- =========================================================================
--- Y3 功能模板 · logic.lua  (A 级 · 零依赖纯工具)
--- =========================================================================
---
--- @template-id   a-aoe-point
--- @grade         A
--- @version       v1.0.0
--- @entry         M.setup(params) → { trigger, cleanup }
--- @architecture  纯函数，无 Class/BaseAbility/GamePlay 依赖
--- @description   点/圆范围AOE视觉管线：预警粒子→延迟→伤害判定+命中粒子。
---                覆盖圆形(单段/多段)和矩形AOE。
---                仅依赖 y3 引擎 API，可跨项目直接使用。
---
--- 接入只需 2 步：
---   1. M.setup(params) 配置参数 + 伤害回调
---   2. 在技能触发点调用 skill.trigger(targetPoint)
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 参数定义
-- ============================================================================

---@class AoePointParams
---@field owner              Unit      施法者单位
---@field aoe_radius          number    AOE 半径 (圆形模式, 200-600)
---@field delay               number    预警→伤害延迟(秒)
---@field count?              integer   段数 (默认 1, >1 = 多段AOE)
---@field interval?           number    段间隔秒数 (多段时使用, 默认 = delay)
---@field release_particle?   integer   预警粒子 ID (陨石落下/光柱/地面标记)
---@field hit_particle?       integer   命中粒子 ID (爆炸/冲击波)
---@field release_speed?      number    预警特效播放速度 (默认 1)
---@field hit_speed?          number    命中特效播放速度 (默认 1)
---@field release_scale?      number    预警特效缩放；不填则使用 aoe_radius / 400
---@field hit_scale?          number    命中特效缩放；不填则使用 aoe_radius / 400
---@field aoe_type?           "circle"|"rect"   形状 (默认 "circle")
---@field rect_width?         number    矩形宽度 (rect 模式)
---@field rect_length?        number    矩形长度 (rect 模式)
---@field on_hit              fun(targetList: Unit[])  命中回调 — 用户在此批量伤害
---@field on_cast?            fun()                    施法回调 — 用户在此广播事件
---@field get_target_point?   fun(): Point  动态目标点 (多段用, 每段调用)

-- ============================================================================
-- §2. 入口: M.setup(params)
-- ============================================================================

--- 创建点范围AOE技能实例
---@param params AoePointParams
---@return { trigger: fun(targetPoint: Point, faceAngle?: number), cleanup: fun() }
function M.setup(params)
    -- 参数校验
    assert(params.owner,          "a-aoe-point: owner is required")
    assert(params.aoe_radius,      "a-aoe-point: aoe_radius is required")
    assert(params.delay,           "a-aoe-point: delay is required")
    assert(params.on_hit,          "a-aoe-point: on_hit is required")

    local cfg = {
        owner              = params.owner,
        aoe_radius          = params.aoe_radius,
        delay               = params.delay,
        count               = params.count             or 1,
        interval            = params.interval          or params.delay,
        release_particle    = params.release_particle,       -- 可选: 预警粒子 ID（如 105180 黄色圈）
        hit_particle        = params.hit_particle or 102919, -- 默认受击: 102919
        release_speed       = params.release_speed or 1,
        hit_speed           = params.hit_speed or 1,
        release_scale       = params.release_scale or (params.aoe_radius / 400),
        hit_scale           = params.hit_scale or (params.aoe_radius / 400),
        aoe_type            = params.aoe_type          or "circle",
        rect_width          = params.rect_width,
        rect_length         = params.rect_length,
        on_hit              = params.on_hit,
        on_cast             = params.on_cast,
        get_target_point    = params.get_target_point,
    }

    -- 如果 rect 模式, 需要宽高
    if cfg.aoe_type == "rect" then
        assert(cfg.rect_width,  "a-aoe-point: rect_width required for rect AOE")
        assert(cfg.rect_length, "a-aoe-point: rect_length required for rect AOE")
    end

    -- 管理所有 timer (用于 cleanup)
    local activeTimers = {}

    -- 前向声明 (Lua local function 不支持前向引用)
    local execSingleAoe, execMultiAoe, makeShape, doDamage

    -- ========================================================================
    -- §3. 核心: trigger(targetPoint, faceAngle)
    -- ========================================================================

    local function trigger(targetPoint, faceAngle)
        if not cfg.owner:is_alive() then return end
        if not targetPoint then return end

        if cfg.on_cast then cfg.on_cast() end

        if cfg.count == 1 then
            -- 单段 AOE
            execSingleAoe(targetPoint, faceAngle)
        else
            -- 多段 AOE
            execMultiAoe(targetPoint, faceAngle)
        end
    end

    -- ========================================================================
    -- §4. 单段 AOE
    -- ========================================================================

    execSingleAoe = function(targetPoint, faceAngle)
        local shape = makeShape(targetPoint, faceAngle)

        -- 预警粒子
        local warnParticle = nil
        if cfg.release_particle then
            warnParticle = y3.particle.create({
                type = cfg.release_particle,
                target = targetPoint,
                scale = cfg.release_scale,
                angle = faceAngle or 0,
                time = cfg.delay,  -- 粒子持续 = 延迟时间
            })
            warnParticle:set_animation_speed(cfg.release_speed)
        end

        -- 延迟后伤害：先主动移除预警粒子，避免预警残留与命中爆炸重叠。
        local t = y3.timer.wait(cfg.delay, function()
            if warnParticle then
                pcall(function()
                    warnParticle:remove()
                end)
                warnParticle = nil
            end
            doDamage(targetPoint, shape, faceAngle)
        end)
        table.insert(activeTimers, t)
    end

    -- ========================================================================
    -- §5. 多段 AOE
    -- ========================================================================

    execMultiAoe = function(targetPoint, faceAngle)
        -- 每段重新获取目标点 (目标可能移动)
        local t = y3.timer.count_loop(cfg.interval, cfg.count, function()
            local curPoint = cfg.get_target_point and cfg.get_target_point() or targetPoint
            if not curPoint then return end

            local shape = makeShape(curPoint, faceAngle)

            -- 每段预警粒子
            local warnParticle = nil
            if cfg.release_particle then
                warnParticle = y3.particle.create({
                    type = cfg.release_particle,
                    target = curPoint,
                    scale = cfg.release_scale,
                    angle = faceAngle or 0,
                    time = cfg.delay,
                })
                warnParticle:set_animation_speed(cfg.release_speed)
            end

            -- 段内延迟后伤害：先移除预警，再结算命中。
            local innerT = y3.timer.wait(cfg.delay, function()
                if warnParticle then
                    pcall(function()
                        warnParticle:remove()
                    end)
                    warnParticle = nil
                end
                doDamage(curPoint, shape, faceAngle)
            end)
            table.insert(activeTimers, innerT)
        end, nil, true)  -- immediate = true, 第一段立即触发
        table.insert(activeTimers, t)
    end

    -- ========================================================================
    -- §6. 形状创建
    -- ========================================================================

    makeShape = function(targetPoint, faceAngle)
        if cfg.aoe_type == "rect" then
            return y3.shape.create_rectangle_shape(
                cfg.rect_width, cfg.rect_length, faceAngle or 0)
        else
            return y3.shape.create_circular_shape(cfg.aoe_radius)
        end
    end

    -- ========================================================================
    -- §7. 伤害判定
    -- ========================================================================

    doDamage = function(targetPoint, shape, faceAngle)
        -- 选择器: 在形状范围内, 敌方单位
        local selector = y3.selector.create()
            :in_shape(targetPoint, shape)
            :is_enemy(cfg.owner:get_owner())

        local targets = selector:pick()

        if #targets > 0 then
            -- 命中粒子
            if cfg.hit_particle then
                local hitParticle = y3.particle.create({
                    type = cfg.hit_particle,
                    target = targetPoint,
                    scale = cfg.hit_scale,
                    angle = faceAngle or 0,
                })
                hitParticle:set_animation_speed(cfg.hit_speed)
            end

            -- 用户批量伤害回调
            cfg.on_hit(targets)
        end
    end

    -- ========================================================================
    -- §8. 清理
    -- ========================================================================

    local function cleanup()
        for _, t in ipairs(activeTimers) do
            pcall(function() t:remove() end)  -- 安全清理, 已完成的 timer remove 无害
        end
        activeTimers = {}
    end

    return {
        trigger = trigger,
        cleanup = cleanup,
    }
end

return M
