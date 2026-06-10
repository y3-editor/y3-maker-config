--- =========================================================================
--- Y3 功能模板 · logic.lua  (A 级 · 零依赖纯工具)
--- =========================================================================
---
--- @template-id   a-projectile-line
--- @grade         A
--- @version       v1.0.0
--- @entry         M.setup(params) → { trigger, cleanup }
--- @architecture  纯函数，无 Class/BaseAbility/GamePlay 依赖
--- @description   直线投射物视觉管线：扇形散射/连续发射/单发，穿透/非穿透。
---                仅依赖 y3 引擎 API，可跨项目直接使用。
---
--- 接入只需 2 步：
---   1. M.setup(params) 配置参数 + 伤害回调
---   2. 在技能触发点调用 skill.trigger(originPoint, angle)
--- =========================================================================

local M = {}

-- ============================================================================
-- §1. DataSchema — 参数定义
-- ============================================================================

---@class ProjectileLineParams
---@field owner              Unit      发射者单位
---@field projectile_id      integer   投射物模型 ID（物编 key）
---@field projectile_speed   number    飞行速度 (建议 800-2000)
---@field projectile_count   integer   投射物数量
---@field projectile_size    number    投射物缩放 (默认 1.0)
---@field collision_radius   number    碰撞半径 (建议 50-150)
---@field linear_range       number    飞行距离 (600-2000)
---@field spread_angle?      number    扇形角度 (默认 0 = 单发, 30 = 扇形散射)
---@field penetration?       boolean   是否穿透 (默认 false, true = 穿过多目标)
---@field height?            number    飞行高度 (默认 100)
---@field release_particle?  integer   出手粒子 ID (可选)
---@field hit_particle?      integer   受击粒子 ID (可选)
---@field fire_mode?         "fan"|"sequential"|"single"  发射模式 (默认 "fan")
---@field interval?          number    连续发射间隔秒数 (sequential 模式时, 默认 0.15)
---@field on_hit             fun(targetUnit: Unit)  命中目标回调 — 用户在此造成伤害
---@field on_cast?           fun()                  施法回调 — 用户在此广播事件

-- ============================================================================
-- §2. 入口: M.setup(params)
-- ============================================================================

--- 创建直线投射物技能实例
---@param params ProjectileLineParams
---@return { trigger: fun(originPoint: Point, baseAngle: number), cleanup: fun() }
function M.setup(params)
    -- 参数校验 + 默认值
    assert(params.owner,              "a-projectile-line: owner is required")
    assert(params.projectile_id,       "a-projectile-line: projectile_id is required")
    assert(params.projectile_speed,    "a-projectile-line: projectile_speed is required")
    assert(params.projectile_count,    "a-projectile-line: projectile_count is required")
    assert(params.on_hit,              "a-projectile-line: on_hit is required")

    local cfg = {
        owner              = params.owner,
        projectile_id      = params.projectile_id,
        projectile_speed   = params.projectile_speed,
        projectile_count   = params.projectile_count,
        projectile_size    = params.projectile_size    or 1.0,
        collision_radius   = params.collision_radius,
        linear_range       = params.linear_range,
        spread_angle       = params.spread_angle       or 0,
        penetration        = params.penetration        or false,
        height             = params.height             or 100,
        release_particle   = params.release_particle,       -- 可选: 出手粒子 ID
        hit_particle       = params.hit_particle or 102919, -- 默认受击: 102919
        fire_mode          = params.fire_mode          or "fan",
        interval           = params.interval           or 0.15,
        on_hit             = params.on_hit,
        on_cast            = params.on_cast,
    }

    -- 碰撞半径必须乘投射物大小
    local effectiveCollision = cfg.collision_radius * cfg.projectile_size

    -- 管理所有投射物的列表（用于 cleanup）
    local activeOrbs = {}

    -- 前向声明 (Lua local function 不支持前向引用)
    local createProjectile, removeOrb

    -- ========================================================================
    -- §3. 核心: trigger(originPoint, baseAngle)
    -- ========================================================================

    local function trigger(originPoint, baseAngle)
        if not cfg.owner:is_alive() then return end

        if cfg.on_cast then cfg.on_cast() end

        local projectileSize = cfg.projectile_size
        local height = cfg.height * projectileSize
        local nowPoint = originPoint:get_point_offset_vector(baseAngle, 0)

        if cfg.fire_mode == "fan" then
            -- 扇形散射
            local count = cfg.projectile_count
            local halfSpread = cfg.spread_angle / 2

            for i = 1, count do
                local segAngle
                if count == 1 then
                    segAngle = 0
                else
                    segAngle = -halfSpread + (cfg.spread_angle) * (i - 1) / (count - 1)
                end
                local finalAngle = baseAngle + segAngle

                -- 出手粒子
                if cfg.release_particle then
                    y3.particle.create({
                        type = cfg.release_particle,
                        target = cfg.owner,
                        socket = 'attack3',
                        scale = projectileSize,
                        speed = 1,
                        angle = finalAngle,
                        follow_rotation = 2,
                        detach = true,
                    })
                end

                createProjectile(nowPoint, finalAngle, height, projectileSize, effectiveCollision)
            end

        elseif cfg.fire_mode == "sequential" then
            -- 连续发射
            local count = cfg.projectile_count
            y3.ltimer.loop_count(cfg.interval, count, function(timer, i)
                if not cfg.owner:is_alive() then
                    timer:remove()
                    return
                end
                if cfg.release_particle then
                    y3.particle.create({
                        type = cfg.release_particle,
                        target = cfg.owner,
                        socket = 'hit_point',
                        scale = projectileSize,
                        speed = 1,
                        angle = baseAngle,
                        follow_rotation = 2,
                        detach = true,
                    })
                end
                createProjectile(nowPoint, baseAngle, height, projectileSize, effectiveCollision)
            end)

        else -- single
            if cfg.release_particle then
                y3.particle.create({
                    type = cfg.release_particle,
                    target = cfg.owner,
                    socket = 'attack3',
                    scale = projectileSize,
                    speed = 1,
                    angle = baseAngle,
                    follow_rotation = 2,
                    detach = true,
                })
            end
            createProjectile(nowPoint, baseAngle, height, projectileSize, effectiveCollision)
        end
    end

    -- ========================================================================
    -- §4. 投射物创建 + mover_line
    -- ========================================================================

    createProjectile = function(nowPoint, angle, height, projectileSize, collisionRadius)
        -- 向前偏移碰撞半径+50，避免命中发射者自身
        local startPoint = nowPoint:get_point_offset_vector(angle, collisionRadius + 50)
        local orb = y3.projectile.create({
            target = startPoint,
            angle = angle,
            owner = cfg.owner,
            height = height,
            key = cfg.projectile_id,
            remove_immediately = false,
        })
        if not orb then return end

        table.insert(activeOrbs, orb)
        orb:set_scale(projectileSize, projectileSize, projectileSize)

        local speed = cfg.projectile_speed
        orb:mover_line({
            angle = angle,
            distance = cfg.linear_range,
            hit_radius = collisionRadius,
            hit_type = 0,  -- 0=只碰敌人 (引擎内置: 0=敌人 1=盟友 2=全部)
            hit_same = cfg.penetration or false,  -- 穿透时允许多次碰撞同一单位
            speed = speed,
            acceleration = 500,
            max_speed = speed * 2,
            min_speed = speed,
            face_angle = true,       -- 投射物朝向飞行方向
            absolute_height = true,  -- 保持绝对高度

            on_hit = function(mover, targetUnit)
                -- 关键时序: 先粒子后伤害
                y3.ltimer.wait(0.03, function()
                    if cfg.hit_particle and orb:is_exist() then
                        y3.particle.create({
                            type = cfg.hit_particle,
                            target = orb:get_point(),
                            scale = projectileSize,
                            speed = 2,
                            angle = angle,
                            height = orb:get_height(),
                            follow_rotation = 2,
                            detach = true,
                        })
                    end
                    -- 用户伤害回调
                    cfg.on_hit(targetUnit)

                    -- 非穿透: 命中后移除
                    if not cfg.penetration then
                        removeOrb(orb)
                    end
                end)
            end,

            on_remove = function()
                removeOrb(orb)
            end,

            on_finish = function() end,
        })
    end

    -- ========================================================================
    -- §5. 清理
    -- ========================================================================

    removeOrb = function(orb)
        for i, o in ipairs(activeOrbs) do
            if o == orb then
                table.remove(activeOrbs, i)
                break
            end
        end
        if orb:is_exist() then
            orb:remove()
        end
    end

    local function cleanup()
        for _, orb in ipairs(activeOrbs) do
            if orb:is_exist() then
                orb:remove()
            end
        end
        activeOrbs = {}
    end

    return {
        trigger = trigger,
        cleanup = cleanup,
    }
end

return M
