--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-bezier-trajectory
--- @version       v0.1.0
--- @entry         M.setup(params)
--- @params        max_speed, delta_time, lut_segments, switch_ratio
--- @source        global_script/client/tools/bezierTrajectory.lua
--- @description   提供可复用的贝塞尔轨迹计算，并驱动 Y3 投射物沿曲线路径移动到单位或点目标。
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块入口点
---   2. 所有外部依赖通过 M.setup(params) 传入，禁止修改 local 常量
---   3. 本模板不依赖 UI 路径
---   4. 本模板不自行注册全局事件；如需注册由融合侧决定时机
--- =========================================================================

local M = {}

local params = {
    max_speed = 3200,
    delta_time = 1 / 30,
    lut_segments = 120,
    switch_ratio = 0.2,
}

local Vec3 = {}

function Vec3.new(x, y, z)
    return { x = x or 0, y = y or 0, z = z or 0 }
end

function Vec3.add(a, b)
    return Vec3.new(a.x + b.x, a.y + b.y, a.z + b.z)
end

function Vec3.sub(a, b)
    return Vec3.new(a.x - b.x, a.y - b.y, a.z - b.z)
end

function Vec3.mul(a, s)
    return Vec3.new(a.x * s, a.y * s, a.z * s)
end

function Vec3.length(v)
    return math.sqrt(v.x * v.x + v.y * v.y + v.z * v.z)
end

function Vec3.normalize(v)
    local len = Vec3.length(v)
    if len == 0 then
        return Vec3.new(0, 1, 0)
    end
    return Vec3.mul(v, 1 / len)
end

local function validate_params()
    assert(type(params.max_speed) == "number" and params.max_speed > 0, "a-bezier-trajectory: max_speed must be positive")
    assert(type(params.delta_time) == "number" and params.delta_time > 0, "a-bezier-trajectory: delta_time must be positive")
    assert(type(params.lut_segments) == "number" and params.lut_segments >= 2, "a-bezier-trajectory: lut_segments must be >= 2")
    assert(type(params.switch_ratio) == "number" and params.switch_ratio >= 0, "a-bezier-trajectory: switch_ratio must be >= 0")
end

local function bezier_point(points, t)
    local n = #points
    if n == 2 then
        local u = 1 - t
        return Vec3.add(Vec3.mul(points[1], u), Vec3.mul(points[2], t))
    elseif n == 3 then
        local u = 1 - t
        local a = Vec3.mul(points[1], u * u)
        local b = Vec3.mul(points[2], 2 * u * t)
        local c = Vec3.mul(points[3], t * t)
        return Vec3.add(Vec3.add(a, b), c)
    elseif n == 4 then
        local u = 1 - t
        local u2, u3 = u * u, u * u * u
        local t2, t3 = t * t, t * t * t
        local a = Vec3.mul(points[1], u3)
        local b = Vec3.mul(points[2], 3 * u2 * t)
        local c = Vec3.mul(points[3], 3 * u * t2)
        local d = Vec3.mul(points[4], t3)
        return Vec3.add(Vec3.add(Vec3.add(a, b), c), d)
    end
    return points[1]
end

local function bezier_tangent(points, t)
    local n = #points
    if n == 2 then
        return Vec3.sub(points[2], points[1])
    elseif n == 3 then
        local u = 1 - t
        local term1 = Vec3.mul(Vec3.sub(points[2], points[1]), 2 * u)
        local term2 = Vec3.mul(Vec3.sub(points[3], points[2]), 2 * t)
        return Vec3.add(term1, term2)
    elseif n == 4 then
        local u = 1 - t
        local term1 = Vec3.mul(Vec3.sub(points[2], points[1]), 3 * u * u)
        local term2 = Vec3.mul(Vec3.sub(points[3], points[2]), 6 * u * t)
        local term3 = Vec3.mul(Vec3.sub(points[4], points[3]), 3 * t * t)
        return Vec3.add(Vec3.add(term1, term2), term3)
    end
    return Vec3.new(1, 0, 0)
end

local math_sqrt = math.sqrt

local function build_lut(points, segments)
    segments = segments or params.lut_segments
    local lut = {}
    local total_length = 0
    local n = #points

    local p1 = points[1]
    local p2 = points[2]
    local p3 = points[3]
    local p4 = points[4]
    local p1x, p1y, p1z = p1.x, p1.y, p1.z
    local p2x, p2y, p2z = p2.x, p2.y, p2.z
    local p3x, p3y, p3z = 0, 0, 0
    local p4x, p4y, p4z = 0, 0, 0
    if p3 then p3x, p3y, p3z = p3.x, p3.y, p3.z end
    if p4 then p4x, p4y, p4z = p4.x, p4.y, p4.z end

    local prev_x, prev_y, prev_z = p1x, p1y, p1z
    lut[1] = { t = 0, s = 0 }

    local inv_segments = 1 / segments
    for i = 1, segments do
        local t = i * inv_segments
        local x, y, z
        if n == 4 then
            local u = 1 - t
            local u2 = u * u
            local u3 = u2 * u
            local t2 = t * t
            local t3 = t2 * t
            local c2 = 3 * u2 * t
            local c3 = 3 * u * t2
            x = p1x * u3 + p2x * c2 + p3x * c3 + p4x * t3
            y = p1y * u3 + p2y * c2 + p3y * c3 + p4y * t3
            z = p1z * u3 + p2z * c2 + p3z * c3 + p4z * t3
        elseif n == 3 then
            local u = 1 - t
            local c1 = u * u
            local c2 = 2 * u * t
            local c3 = t * t
            x = p1x * c1 + p2x * c2 + p3x * c3
            y = p1y * c1 + p2y * c2 + p3y * c3
            z = p1z * c1 + p2z * c2 + p3z * c3
        else
            local u = 1 - t
            x = p1x * u + p2x * t
            y = p1y * u + p2y * t
            z = p1z * u + p2z * t
        end

        local dx = x - prev_x
        local dy = y - prev_y
        local dz = z - prev_z
        total_length = total_length + math_sqrt(dx * dx + dy * dy + dz * dz)

        lut[i + 1] = { t = t, s = total_length }
        prev_x, prev_y, prev_z = x, y, z
    end

    lut.totalLength = total_length
    return lut
end

local function get_parameter_by_distance(lut, distance)
    if distance <= 0 then return 0 end
    if distance >= lut.totalLength then return 1 end

    local low, high = 1, #lut
    while low < high do
        local mid = math.floor((low + high) / 2)
        if lut[mid].s < distance then
            low = mid + 1
        else
            high = mid
        end
    end

    if low == 1 then return 0 end

    local prev = lut[low - 1]
    local curr = lut[low]
    local segment_length = curr.s - prev.s
    if segment_length <= 0 then return curr.t end

    local ratio = (distance - prev.s) / segment_length
    return prev.t + (curr.t - prev.t) * ratio
end

local function point_to_vec3(point, height)
    return Vec3.new(point:get_x(), point:get_y(), height)
end

local function get_angle_by_dir(dir)
    local angle = 0
    if dir.x ~= 0 or dir.y ~= 0 then
        angle = math.deg(math.acos(dir.x / math.sqrt(dir.x * dir.x + dir.y * dir.y)))
        if dir.y < 0 then
            angle = 360 - angle
        end
    end
    return angle
end

local function get_rotation_by_dir(dir)
    local yaw = 0
    local pitch = 0

    if dir.x ~= 0 or dir.y ~= 0 then
        yaw = math.deg(math.acos(dir.x / math.sqrt(dir.x * dir.x + dir.y * dir.y)))
        if dir.y < 0 then
            yaw = 360 - yaw
        end
    end

    local horizontal_len = math.sqrt(dir.x * dir.x + dir.y * dir.y)
    if horizontal_len ~= 0 then
        pitch = -math.deg(math.atan(dir.z / horizontal_len))
    elseif dir.z > 0 then
        pitch = -90
    elseif dir.z < 0 then
        pitch = 90
    end

    return yaw, pitch
end

local function validate_trajectory_data(data)
    assert(data and data.orb, "a-bezier-trajectory: data.orb is required")
    assert(data.target, "a-bezier-trajectory: data.target is required")
end

function M.create(config)
    config = config or {}
    local trajectory = {
        points = config.points or {},
        initialSpeed = config.initialSpeed or config.speed or 800,
        currentSpeed = config.initialSpeed or config.speed or 800,
        acceleration = config.acceleration or 0,
        accelerationType = config.accelerationType or "linear",
        maxSpeed = config.maxSpeed or math.huge,
        minSpeed = config.minSpeed or 0,
        enableSpeedLimit = config.enableSpeedLimit ~= false,
        accelerationCurve = config.accelerationCurve,
        speedCurve = config.speedCurve,
        lut = nil,
        currentDistance = 0,
        totalTime = 0,
        isCompleted = false,
    }

    assert(#trajectory.points >= 2 and #trajectory.points <= 4, "a-bezier-trajectory: point count must be 2-4")
    trajectory.lut = build_lut(trajectory.points, config.lutSegments or params.lut_segments)

    function trajectory:getPositionAndDirection(t)
        t = math.max(0, math.min(1, t))
        local pos = bezier_point(self.points, t)
        local tangent = bezier_tangent(self.points, t)
        return pos, Vec3.normalize(tangent)
    end

    function trajectory:calculateAcceleration()
        if self.accelerationCurve then
            return self.accelerationCurve(self.totalTime, self.currentSpeed)
        end

        local base_acceleration = self.acceleration
        if self.accelerationType == "linear" then
            return base_acceleration
        elseif self.accelerationType == "quadratic" then
            return base_acceleration * (1 + self.totalTime * 0.5)
        elseif self.accelerationType == "exponential" then
            return base_acceleration * math.exp(self.totalTime * 0.1)
        end
        return base_acceleration
    end

    function trajectory:calculateSpeed(delta_time)
        if self.speedCurve then
            local progress = self.currentDistance / self.lut.totalLength
            return self.speedCurve(progress)
        end

        local new_speed = self.currentSpeed + self:calculateAcceleration() * delta_time
        if self.enableSpeedLimit then
            new_speed = math.max(self.minSpeed, math.min(self.maxSpeed, new_speed))
        end
        return new_speed
    end

    function trajectory:update(delta_time)
        if self.isCompleted then
            return self:getPositionAndDirection(1)
        end

        self.totalTime = self.totalTime + delta_time
        self.currentSpeed = self:calculateSpeed(delta_time)
        self.currentDistance = self.currentDistance + self.currentSpeed * delta_time

        if self.currentDistance >= self.lut.totalLength then
            self.currentDistance = self.lut.totalLength
            self.isCompleted = true
        end

        local t = get_parameter_by_distance(self.lut, self.currentDistance)
        return self:getPositionAndDirection(t)
    end

    function trajectory:reset()
        self.currentDistance = 0
        self.totalTime = 0
        self.currentSpeed = self.initialSpeed
        self.isCompleted = false
    end

    function trajectory:getCurrentSpeed()
        return self.currentSpeed
    end

    function trajectory:setSpeedParams(speed_params)
        if speed_params.acceleration then self.acceleration = speed_params.acceleration end
        if speed_params.maxSpeed then self.maxSpeed = speed_params.maxSpeed end
        if speed_params.minSpeed then self.minSpeed = speed_params.minSpeed end
        if speed_params.accelerationType then self.accelerationType = speed_params.accelerationType end
    end

    function trajectory:getTotalLength()
        return self.lut.totalLength
    end

    function trajectory:getProgress()
        if self.lut.totalLength <= 0 then
            return 1
        end
        return self.currentDistance / self.lut.totalLength
    end

    return trajectory
end

function M.set_dir(orb, pos, dir, angle)
    orb:set_point(y3.point.create(pos.x, pos.y))
    orb:set_height(pos.z)
    local _, pitch = get_rotation_by_dir(dir)
    orb:set_rotation(pitch, 0, angle)
end

function M.mover_target(data)
    validate_trajectory_data(data)

    local max_speed = data.max_speed or params.max_speed
    local start_point = data.orb:get_point()
    local start_height = data.orb:get_height()
    local init_angle = data.init_angle or 0
    local end_point = data.target:get_point()
    local distance = data.dis or end_point:get_distance_with(start_point)
    local target_angle = start_point:get_angle_with(end_point)
    local angle_delta = init_angle - target_angle

    local control_point = start_point:get_point_offset_vector(init_angle, distance * math.abs(angle_delta) / 135)
    local control_height = start_height + (distance / 3) * (distance / 2000) * math.abs(angle_delta) / 90

    local trajectory = M.create({
        points = {
            point_to_vec3(start_point, start_height),
            point_to_vec3(control_point, control_height),
            point_to_vec3(end_point, start_height),
        },
        initialSpeed = data.initial_speed or -1600,
        acceleration = data.acceleration or 800,
        maxSpeed = max_speed,
        minSpeed = data.min_speed or 1600,
        accelerationType = data.acceleration_type or "quadratic",
    })

    local switched_to_linear = false
    local switch_distance = data.switchDistance or (distance * params.switch_ratio)

    y3.timer.loop_frame(1, function(timer)
        local pos, dir = trajectory:update(data.delta_time or params.delta_time)
        local angle = get_angle_by_dir(dir) * -1 + 90
        local current_pos = Vec3.new(pos.x, pos.y, pos.z)
        local target_point = data.target:get_point()
        local target_pos = point_to_vec3(target_point, data.target_height or 200)
        local distance_to_target = Vec3.length(Vec3.sub(target_pos, current_pos))

        local function on_finish()
            if data.on_finish then
                data.on_finish(timer, {
                    angle = angle,
                    hight = pos.z,
                    speed = max_speed,
                })
            end
            timer:remove()
        end

        if not switched_to_linear then
            if distance_to_target > switch_distance then
                data.orb:set_point(y3.point.create(pos.x, pos.y))
                data.orb:set_height(pos.z)
                data.orb:set_facing(angle)
            else
                switched_to_linear = true
                if not data.target then
                    on_finish()
                    return
                end

                if data.target.type == "Point" then
                    local line_distance = data.orb:get_point():get_distance_with(data.target:get_point())
                    local line_angle = data.orb:get_point():get_angle_with(data.target:get_point())
                    data.orb:mover_line({
                        angle = line_angle,
                        distance = line_distance,
                        speed = max_speed,
                        fin_height = data.fin_height or 0,
                        face_angle = true,
                        on_finish = on_finish,
                    })
                    timer:remove()
                    return
                end

                data.orb:mover_target({
                    target = data.target,
                    bind_point = data.bind_point,
                    target_distance = 0,
                    speed = max_speed,
                    on_finish = on_finish,
                })
                timer:remove()
                return
            end
        elseif data.target.type == "Point" then
            data.orb:set_point(y3.point.create(pos.x, pos.y))
            data.orb:set_height(pos.z)
            data.orb:set_facing(angle)
        end

        if trajectory.isCompleted then
            on_finish()
        end
    end)
end

function M.mover_target_by_pure_heart(data)
    validate_trajectory_data(data)

    local max_speed = data.max_speed or params.max_speed
    local start_point = data.orb:get_point()
    local start_height = data.orb:get_height()
    local init_angle = data.init_angle or 0
    local end_point = data.target:get_point()
    local distance = data.dis or end_point:get_distance_with(start_point)
    local control_point = start_point:get_point_offset_vector(init_angle, distance)
    local control_height = data.parabola_height or start_height

    local trajectory = M.create({
        points = {
            point_to_vec3(start_point, start_height),
            point_to_vec3(control_point, control_height),
            point_to_vec3(end_point, start_height),
        },
        initialSpeed = data.initial_speed or -max_speed / 2,
        acceleration = data.acceleration or max_speed / 4,
        maxSpeed = max_speed,
        minSpeed = data.min_speed or max_speed / 2,
        accelerationType = data.acceleration_type or "quadratic",
    })

    y3.timer.loop_frame(1, function(timer)
        local pos, dir = trajectory:update(data.delta_time or params.delta_time)
        local angle = get_angle_by_dir(dir) * -1 + 90
        local target_point = data.target:get_point()

        local function on_finish()
            data.orb:set_point(target_point)
            if data.on_finish then
                data.on_finish(timer, {
                    angle = angle,
                    hight = pos.z,
                    speed = max_speed,
                })
            end
            timer:remove()
        end

        M.set_dir(data.orb, pos, dir, angle)

        if trajectory.isCompleted then
            on_finish()
        end
    end)
end

function M.mover_Point(data)
    return M.mover_point(data)
end

function M.mover_target_by_PureHeart(data)
    return M.mover_target_by_pure_heart(data)
end

function M.mover_point(data)
    validate_trajectory_data(data)

    local max_speed = data.max_speed or params.max_speed
    local start_point = data.orb:get_point()
    local start_height = data.orb:get_height()
    local init_angle = data.init_angle or 0
    local end_point = data.target
    local distance = end_point:get_distance_with(start_point)
    local target_angle = start_point:get_angle_with(end_point)
    local angle_delta = init_angle - target_angle

    local control_point = start_point:get_point_offset_vector(init_angle, distance * math.abs(angle_delta) / 135)
    local control_height = start_height + (distance / 3) * (distance / 2000) * math.abs(angle_delta) / 90

    local trajectory = M.create({
        points = {
            point_to_vec3(start_point, start_height),
            point_to_vec3(control_point, control_height),
            point_to_vec3(end_point, data.fin_height or 0),
        },
        initialSpeed = data.initial_speed or -1600,
        acceleration = data.acceleration or 800,
        maxSpeed = max_speed,
        minSpeed = data.min_speed or 1600,
        accelerationType = data.acceleration_type or "quadratic",
    })

    y3.timer.loop_frame(1, function(timer)
        local pos, dir = trajectory:update(data.delta_time or params.delta_time)
        local angle = get_angle_by_dir(dir) * -1 + 90

        local function on_finish()
            if data.on_finish then
                data.on_finish(timer, {
                    angle = angle,
                    hight = pos.z,
                    speed = max_speed,
                })
            end
            timer:remove()
        end

        data.orb:set_point(y3.point.create(pos.x, pos.y))
        data.orb:set_height(pos.z)
        data.orb:set_facing(angle)

        if trajectory.isCompleted then
            on_finish()
        end
    end)
end

function M.setup(user_params)
    user_params = user_params or {}
    for k, v in pairs(user_params) do
        params[k] = v
    end
    validate_params()
    return M
end

return M
