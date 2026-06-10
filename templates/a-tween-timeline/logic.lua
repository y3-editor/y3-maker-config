--- =========================================================================
--- Y3 功能模板 · logic.lua
--- =========================================================================
---
--- @template-id   a-tween-timeline
--- @version       v0.3.0
--- @entry         M.setup(params)
--- @params        loop_frame, warn, default_fps
--- @source        global_script/client/ui/UIFrameTween.lua
--- @description   集成 kikito/tween.lua 的通用补间动画时间线，支持完整 easing 曲线和链式编排。
---
--- 融合契约：
---   1. 调用方将本文件内容融入目标模块入口点
---   2. 所有外部依赖通过 M.setup(params) 传入，禁止修改 local 常量
---   3. 本模板不依赖 UI 路径
---   4. 本模板不自行注册全局事件；如需注册由融合侧决定时机
---
--- Third-party notice:
---   Includes kikito/tween.lua 2.1.1 from https://github.com/kikito/tween.lua
---   tween.lua license text is embedded in tpl_kikito_tween._LICENSE below.
--- =========================================================================

local function tpl_create_kikito_tween()
local tween = {
  _VERSION     = 'tween 2.1.1',
  _DESCRIPTION = 'tweening for lua',
  _URL         = 'https://github.com/kikito/tween.lua',
  _LICENSE     = [[
    MIT LICENSE

    Copyright (c) 2014 Enrique García Cota, Yuichi Tateno, Emmanuel Oga

    Permission is hereby granted, free of charge, to any person obtaining a
    copy of this software and associated documentation files (the
    "Software"), to deal in the Software without restriction, including
    without limitation the rights to use, copy, modify, merge, publish,
    distribute, sublicense, and/or sell copies of the Software, and to
    permit persons to whom the Software is furnished to do so, subject to
    the following conditions:

    The above copyright notice and this permission notice shall be included
    in all copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
    OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
    MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
    CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
    TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
    SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
  ]]
}

-- easing

-- Adapted from https://github.com/EmmanuelOga/easing. See LICENSE.txt for credits.
-- For all easing functions:
-- t = time == how much time has to pass for the tweening to complete
-- b = begin == starting property value
-- c = change == ending - beginning
-- d = duration == running time. How much time has passed *right now*

local pow, sin, cos, pi, sqrt, abs, asin = math.pow or function(a, b) return a ^ b end, math.sin, math.cos, math.pi, math.sqrt, math.abs, math.asin

-- linear
local function linear(t, b, c, d) return c * t / d + b end

-- quad
local function inQuad(t, b, c, d) return c * pow(t / d, 2) + b end
local function outQuad(t, b, c, d)
  t = t / d
  return -c * t * (t - 2) + b
end
local function inOutQuad(t, b, c, d)
  t = t / d * 2
  if t < 1 then return c / 2 * pow(t, 2) + b end
  return -c / 2 * ((t - 1) * (t - 3) - 1) + b
end
local function outInQuad(t, b, c, d)
  if t < d / 2 then return outQuad(t * 2, b, c / 2, d) end
  return inQuad((t * 2) - d, b + c / 2, c / 2, d)
end

-- cubic
local function inCubic (t, b, c, d) return c * pow(t / d, 3) + b end
local function outCubic(t, b, c, d) return c * (pow(t / d - 1, 3) + 1) + b end
local function inOutCubic(t, b, c, d)
  t = t / d * 2
  if t < 1 then return c / 2 * t * t * t + b end
  t = t - 2
  return c / 2 * (t * t * t + 2) + b
end
local function outInCubic(t, b, c, d)
  if t < d / 2 then return outCubic(t * 2, b, c / 2, d) end
  return inCubic((t * 2) - d, b + c / 2, c / 2, d)
end

-- quart
local function inQuart(t, b, c, d) return c * pow(t / d, 4) + b end
local function outQuart(t, b, c, d) return -c * (pow(t / d - 1, 4) - 1) + b end
local function inOutQuart(t, b, c, d)
  t = t / d * 2
  if t < 1 then return c / 2 * pow(t, 4) + b end
  return -c / 2 * (pow(t - 2, 4) - 2) + b
end
local function outInQuart(t, b, c, d)
  if t < d / 2 then return outQuart(t * 2, b, c / 2, d) end
  return inQuart((t * 2) - d, b + c / 2, c / 2, d)
end

-- quint
local function inQuint(t, b, c, d) return c * pow(t / d, 5) + b end
local function outQuint(t, b, c, d) return c * (pow(t / d - 1, 5) + 1) + b end
local function inOutQuint(t, b, c, d)
  t = t / d * 2
  if t < 1 then return c / 2 * pow(t, 5) + b end
  return c / 2 * (pow(t - 2, 5) + 2) + b
end
local function outInQuint(t, b, c, d)
  if t < d / 2 then return outQuint(t * 2, b, c / 2, d) end
  return inQuint((t * 2) - d, b + c / 2, c / 2, d)
end

-- sine
local function inSine(t, b, c, d) return -c * cos(t / d * (pi / 2)) + c + b end
local function outSine(t, b, c, d) return c * sin(t / d * (pi / 2)) + b end
local function inOutSine(t, b, c, d) return -c / 2 * (cos(pi * t / d) - 1) + b end
local function outInSine(t, b, c, d)
  if t < d / 2 then return outSine(t * 2, b, c / 2, d) end
  return inSine((t * 2) -d, b + c / 2, c / 2, d)
end

-- expo
local function inExpo(t, b, c, d)
  if t == 0 then return b end
  return c * pow(2, 10 * (t / d - 1)) + b - c * 0.001
end
local function outExpo(t, b, c, d)
  if t == d then return b + c end
  return c * 1.001 * (-pow(2, -10 * t / d) + 1) + b
end
local function inOutExpo(t, b, c, d)
  if t == 0 then return b end
  if t == d then return b + c end
  t = t / d * 2
  if t < 1 then return c / 2 * pow(2, 10 * (t - 1)) + b - c * 0.0005 end
  return c / 2 * 1.0005 * (-pow(2, -10 * (t - 1)) + 2) + b
end
local function outInExpo(t, b, c, d)
  if t < d / 2 then return outExpo(t * 2, b, c / 2, d) end
  return inExpo((t * 2) - d, b + c / 2, c / 2, d)
end

-- circ
local function inCirc(t, b, c, d) return(-c * (sqrt(1 - pow(t / d, 2)) - 1) + b) end
local function outCirc(t, b, c, d)  return(c * sqrt(1 - pow(t / d - 1, 2)) + b) end
local function inOutCirc(t, b, c, d)
  t = t / d * 2
  if t < 1 then return -c / 2 * (sqrt(1 - t * t) - 1) + b end
  t = t - 2
  return c / 2 * (sqrt(1 - t * t) + 1) + b
end
local function outInCirc(t, b, c, d)
  if t < d / 2 then return outCirc(t * 2, b, c / 2, d) end
  return inCirc((t * 2) - d, b + c / 2, c / 2, d)
end

-- elastic
local function calculatePAS(p,a,c,d)
  p, a = p or d * 0.3, a or 0
  if a < abs(c) then return p, c, p / 4 end -- p, a, s
  return p, a, p / (2 * pi) * asin(c/a) -- p,a,s
end
local function inElastic(t, b, c, d, a, p)
  local s
  if t == 0 then return b end
  t = t / d
  if t == 1  then return b + c end
  p,a,s = calculatePAS(p,a,c,d)
  t = t - 1
  return -(a * pow(2, 10 * t) * sin((t * d - s) * (2 * pi) / p)) + b
end
local function outElastic(t, b, c, d, a, p)
  local s
  if t == 0 then return b end
  t = t / d
  if t == 1 then return b + c end
  p,a,s = calculatePAS(p,a,c,d)
  return a * pow(2, -10 * t) * sin((t * d - s) * (2 * pi) / p) + c + b
end
local function inOutElastic(t, b, c, d, a, p)
  local s
  if t == 0 then return b end
  t = t / d * 2
  if t == 2 then return b + c end
  p,a,s = calculatePAS(p,a,c,d)
  t = t - 1
  if t < 0 then return -0.5 * (a * pow(2, 10 * t) * sin((t * d - s) * (2 * pi) / p)) + b end
  return a * pow(2, -10 * t) * sin((t * d - s) * (2 * pi) / p ) * 0.5 + c + b
end
local function outInElastic(t, b, c, d, a, p)
  if t < d / 2 then return outElastic(t * 2, b, c / 2, d, a, p) end
  return inElastic((t * 2) - d, b + c / 2, c / 2, d, a, p)
end

-- back
local function inBack(t, b, c, d, s)
  s = s or 1.70158
  t = t / d
  return c * t * t * ((s + 1) * t - s) + b
end
local function outBack(t, b, c, d, s)
  s = s or 1.70158
  t = t / d - 1
  return c * (t * t * ((s + 1) * t + s) + 1) + b
end
local function inOutBack(t, b, c, d, s)
  s = (s or 1.70158) * 1.525
  t = t / d * 2
  if t < 1 then return c / 2 * (t * t * ((s + 1) * t - s)) + b end
  t = t - 2
  return c / 2 * (t * t * ((s + 1) * t + s) + 2) + b
end
local function outInBack(t, b, c, d, s)
  if t < d / 2 then return outBack(t * 2, b, c / 2, d, s) end
  return inBack((t * 2) - d, b + c / 2, c / 2, d, s)
end

-- bounce
local function outBounce(t, b, c, d)
  t = t / d
  if t < 1 / 2.75 then return c * (7.5625 * t * t) + b end
  if t < 2 / 2.75 then
    t = t - (1.5 / 2.75)
    return c * (7.5625 * t * t + 0.75) + b
  elseif t < 2.5 / 2.75 then
    t = t - (2.25 / 2.75)
    return c * (7.5625 * t * t + 0.9375) + b
  end
  t = t - (2.625 / 2.75)
  return c * (7.5625 * t * t + 0.984375) + b
end
local function inBounce(t, b, c, d) return c - outBounce(d - t, 0, c, d) + b end
local function inOutBounce(t, b, c, d)
  if t < d / 2 then return inBounce(t * 2, 0, c, d) * 0.5 + b end
  return outBounce(t * 2 - d, 0, c, d) * 0.5 + c * .5 + b
end
local function outInBounce(t, b, c, d)
  if t < d / 2 then return outBounce(t * 2, b, c / 2, d) end
  return inBounce((t * 2) - d, b + c / 2, c / 2, d)
end

tween.easing = {
  linear    = linear,
  inQuad    = inQuad,    outQuad    = outQuad,    inOutQuad    = inOutQuad,    outInQuad    = outInQuad,
  inCubic   = inCubic,   outCubic   = outCubic,   inOutCubic   = inOutCubic,   outInCubic   = outInCubic,
  inQuart   = inQuart,   outQuart   = outQuart,   inOutQuart   = inOutQuart,   outInQuart   = outInQuart,
  inQuint   = inQuint,   outQuint   = outQuint,   inOutQuint   = inOutQuint,   outInQuint   = outInQuint,
  inSine    = inSine,    outSine    = outSine,    inOutSine    = inOutSine,    outInSine    = outInSine,
  inExpo    = inExpo,    outExpo    = outExpo,    inOutExpo    = inOutExpo,    outInExpo    = outInExpo,
  inCirc    = inCirc,    outCirc    = outCirc,    inOutCirc    = inOutCirc,    outInCirc    = outInCirc,
  inElastic = inElastic, outElastic = outElastic, inOutElastic = inOutElastic, outInElastic = outInElastic,
  inBack    = inBack,    outBack    = outBack,    inOutBack    = inOutBack,    outInBack    = outInBack,
  inBounce  = inBounce,  outBounce  = outBounce,  inOutBounce  = inOutBounce,  outInBounce  = outInBounce
}



-- private stuff

local function copyTables(destination, keysTable, valuesTable)
  valuesTable = valuesTable or keysTable
  local mt = getmetatable(keysTable)
  if mt and getmetatable(destination) == nil then
    setmetatable(destination, mt)
  end
  for k,v in pairs(keysTable) do
    if type(v) == 'table' then
      destination[k] = copyTables({}, v, valuesTable[k])
    else
      destination[k] = valuesTable[k]
    end
  end
  return destination
end

local function checkSubjectAndTargetRecursively(subject, target, path)
  path = path or {}
  local targetType, newPath
  for k,targetValue in pairs(target) do
    targetType, newPath = type(targetValue), copyTables({}, path)
    table.insert(newPath, tostring(k))
    if targetType == 'number' then
      assert(type(subject[k]) == 'number', "Parameter '" .. table.concat(newPath,'/') .. "' is missing from subject or isn't a number")
    elseif targetType == 'table' then
      checkSubjectAndTargetRecursively(subject[k], targetValue, newPath)
    else
      assert(targetType == 'number', "Parameter '" .. table.concat(newPath,'/') .. "' must be a number or table of numbers")
    end
  end
end

local function checkNewParams(duration, subject, target, easing)
  assert(type(duration) == 'number' and duration > 0, "duration must be a positive number. Was " .. tostring(duration))
  local tsubject = type(subject)
  assert(tsubject == 'table' or tsubject == 'userdata', "subject must be a table or userdata. Was " .. tostring(subject))
  assert(type(target)== 'table', "target must be a table. Was " .. tostring(target))
  assert(type(easing)=='function', "easing must be a function. Was " .. tostring(easing))
  checkSubjectAndTargetRecursively(subject, target)
end

local function getEasingFunction(easing)
  easing = easing or "linear"
  if type(easing) == 'string' then
    local name = easing
    easing = tween.easing[name]
    if type(easing) ~= 'function' then
      error("The easing function name '" .. name .. "' is invalid")
    end
  end
  return easing
end

local function performEasingOnSubject(subject, target, initial, clock, duration, easing)
  local t,b,c,d
  for k,v in pairs(target) do
    if type(v) == 'table' then
      performEasingOnSubject(subject[k], v, initial[k], clock, duration, easing)
    else
      t,b,c,d = clock, initial[k], v - initial[k], duration
      subject[k] = easing(t,b,c,d)
    end
  end
end

-- Tween methods

local Tween = {}
local Tween_mt = {__index = Tween}

function Tween:set(clock)
  assert(type(clock) == 'number', "clock must be a positive number or 0")

  self.initial = self.initial or copyTables({}, self.target, self.subject)
  self.clock = clock

  if self.clock <= 0 then

    self.clock = 0
    copyTables(self.subject, self.initial)

  elseif self.clock >= self.duration then -- the tween has expired

    self.clock = self.duration
    copyTables(self.subject, self.target)

  else

    performEasingOnSubject(self.subject, self.target, self.initial, self.clock, self.duration, self.easing)

  end

  return self.clock >= self.duration
end

function Tween:reset()
  return self:set(0)
end

function Tween:update(dt)
  assert(type(dt) == 'number', "dt must be a number")
  return self:set(self.clock + dt)
end


-- Public interface

function tween.new(duration, subject, target, easing)
  easing = getEasingFunction(easing)
  checkNewParams(duration, subject, target, easing)
  return setmetatable({
    duration  = duration,
    subject   = subject,
    target    = target,
    easing    = easing,
    clock     = 0
  }, Tween_mt)
end
return tween
end


local tpl_kikito_tween = tpl_create_kikito_tween()

local M = {}

local params = {
    loop_frame = nil,
    warn = nil,
    default_fps = 30,
}

local Timeline = {}
Timeline.__index = Timeline

local function tpl_noop()
end

local function validate_params()
    if params.loop_frame == nil and y3 and y3.ltimer then
        params.loop_frame = y3.ltimer.loop_frame
    end

    assert(type(params.loop_frame) == 'function', 'a-tween-timeline: params.loop_frame must be a function')

    if params.warn == nil then
        params.warn = tpl_noop
    end
    assert(type(params.warn) == 'function', 'a-tween-timeline: params.warn must be a function')
    assert(type(params.default_fps) == 'number' and params.default_fps > 0, 'a-tween-timeline: params.default_fps must be positive')
end

local function normalize_frame(frame, api_name)
    assert(type(frame) == 'number', 'a-tween-timeline: ' .. api_name .. ' frame must be a number')
    assert(frame >= 0, 'a-tween-timeline: ' .. api_name .. ' frame must be >= 0')
    return math.floor(frame)
end

local function seconds_to_frames(seconds)
    assert(type(seconds) == 'number', 'a-tween-timeline: duration must be a number')
    assert(seconds >= 0, 'a-tween-timeline: duration must be >= 0')
    return math.max(1, math.floor(seconds * params.default_fps + 0.5))
end

local function frame_dt()
    return 1 / params.default_fps
end

local function remove_timer(timer)
    if timer and timer.remove then
        timer:remove()
    end
end

local function get_value(ui, getter_name, fallback)
    if ui and ui[getter_name] then
        local ok, value = pcall(function()
            return ui[getter_name](ui)
        end)
        if ok and value ~= nil then
            return value
        end
    end
    return fallback or 0
end

local function get_easing_name(ease)
    if ease == nil then return 'linear' end
    if type(ease) == 'string' then
        local normalized = ease:gsub('%-', '_')
        local aliases = {
            in_quad = 'inQuad', out_quad = 'outQuad', in_out_quad = 'inOutQuad', out_in_quad = 'outInQuad',
            in_cubic = 'inCubic', out_cubic = 'outCubic', in_out_cubic = 'inOutCubic', out_in_cubic = 'outInCubic',
            in_quart = 'inQuart', out_quart = 'outQuart', in_out_quart = 'inOutQuart', out_in_quart = 'outInQuart',
            in_quint = 'inQuint', out_quint = 'outQuint', in_out_quint = 'inOutQuint', out_in_quint = 'outInQuint',
            in_sine = 'inSine', out_sine = 'outSine', in_out_sine = 'inOutSine', out_in_sine = 'outInSine',
            in_expo = 'inExpo', out_expo = 'outExpo', in_out_expo = 'inOutExpo', out_in_expo = 'outInExpo',
            in_circ = 'inCirc', out_circ = 'outCirc', in_out_circ = 'inOutCirc', out_in_circ = 'outInCirc',
            in_elastic = 'inElastic', out_elastic = 'outElastic', in_out_elastic = 'inOutElastic', out_in_elastic = 'outInElastic',
            in_back = 'inBack', out_back = 'outBack', in_out_back = 'inOutBack', out_in_back = 'outInBack',
            in_bounce = 'inBounce', out_bounce = 'outBounce', in_out_bounce = 'inOutBounce', out_in_bounce = 'outInBounce',
        }
        return aliases[normalized] or ease
    end
    return ease
end

local function add_action(self, frame, callback)
    frame = normalize_frame(frame, 'call')
    assert(type(callback) == 'function', 'a-tween-timeline: call callback must be a function')

    if frame == 0 then
        params.warn('a-tween-timeline: sequential call with frame 0 executes at current timeline position')
    end

    table.insert(self._actions, {
        frame = self._total_frame,
        actions = { callback },
    })
    return self:delay(frame)
end

function Timeline:__update()
    local action = self._actions[1]
    if action and action.frame == self._execute_frame then
        table.remove(self._actions, 1)
        for _, callback in ipairs(action.actions) do
            local ok, err = pcall(callback)
            if not ok then
                params.warn('a-tween-timeline callback error: ' .. tostring(err))
            end
        end
    end
end

function Timeline:delay(frame)
    frame = normalize_frame(frame, 'delay')
    self._total_frame = self._total_frame + frame
    return self
end

function Timeline:wait(seconds)
    return self:delay(seconds_to_frames(seconds))
end

function Timeline:call(frame, callback)
    return add_action(self, frame, callback)
end

function Timeline:tween(duration, subject, target, ease, on_update, on_finish)
    local tween_obj = tpl_kikito_tween.new(duration, subject, target, get_easing_name(ease))
    local frames = seconds_to_frames(duration)
    for i = 1, frames do
        self:call(1, function()
            local done = tween_obj:update(frame_dt())
            if on_update then
                on_update(subject, tween_obj.clock, tween_obj.duration)
            end
            if done and on_finish then
                on_finish(subject)
            end
        end)
    end
    return self
end

function Timeline:move_to(x, y, duration, ease)
    local ui = self._ui
    local subject = { x = get_value(ui, 'get_absolute_x', 0), y = get_value(ui, 'get_absolute_y', 0) }
    return self:tween(duration, subject, { x = x, y = y }, ease, function(value)
        if ui and ui.set_absolute_pos then
            ui:set_absolute_pos(value.x, value.y)
        end
    end)
end

function Timeline:scale_to(x, y, duration, ease)
    local ui = self._ui
    y = y or x
    local subject = { x = get_value(ui, 'get_absolute_scale_x', 1), y = get_value(ui, 'get_absolute_scale_y', 1) }
    return self:tween(duration, subject, { x = x, y = y }, ease, function(value)
        if ui and ui.set_widget_absolute_scale then
            ui:set_widget_absolute_scale(value.x, value.y)
        end
    end)
end

function Timeline:rotate_to(rotation, duration, ease)
    local ui = self._ui
    local subject = { value = get_value(ui, 'get_absolute_rotation', 0) }
    return self:tween(duration, subject, { value = rotation }, ease, function(value)
        if ui and ui.set_widget_absolute_rotation then
            ui:set_widget_absolute_rotation(value.value)
        end
    end)
end

function Timeline:alpha_to(alpha, duration, ease)
    local ui = self._ui
    local subject = { value = self._last_alpha or 255 }
    return self:tween(duration, subject, { value = alpha }, ease, function(value)
        self._last_alpha = value.value
        if ui and ui.set_alpha then
            ui:set_alpha(value.value)
        end
    end)
end

function Timeline:native_move_to(x, y, duration, ease_type)
    local ui = self._ui
    return self:call(1, function()
        if ui and ui.set_anim_pos then
            ui:set_anim_pos(get_value(ui, 'get_absolute_x', 0), get_value(ui, 'get_absolute_y', 0), x, y, duration, ease_type)
        elseif ui and ui.set_absolute_pos then
            ui:set_absolute_pos(x, y)
        end
    end):wait(duration)
end

function Timeline:native_scale_to(x, y, duration, ease_type)
    local ui = self._ui
    y = y or x
    return self:call(1, function()
        if ui and ui.set_anim_scale then
            ui:set_anim_scale(get_value(ui, 'get_absolute_scale_x', 1), get_value(ui, 'get_absolute_scale_y', 1), x, y, duration, ease_type)
        elseif ui and ui.set_widget_absolute_scale then
            ui:set_widget_absolute_scale(x, y)
        end
    end):wait(duration)
end

function Timeline:start()
    if self._timer then
        return self
    end
    if #self._actions == 0 then
        return self
    end

    self._timer = params.loop_frame(1, function()
        self:__update()
        self._execute_frame = self._execute_frame + 1

        if self._execute_frame > self._total_frame then
            self:stop()
        end
    end)

    return self
end

function Timeline:stop()
    remove_timer(self._timer)
    self._timer = nil
    self._actions = {}
    return self
end

function Timeline:is_running()
    return self._timer ~= nil
end

function Timeline:get_ui()
    return self._ui
end

function M.new(ui_node)
    return setmetatable({
        _ui = ui_node,
        _actions = {},
        _timer = nil,
        _execute_frame = 1,
        _total_frame = 1,
        _last_alpha = nil,
    }, Timeline)
end

function M.new_raw(duration, subject, target, ease)
    return tpl_kikito_tween.new(duration, subject, target, get_easing_name(ease))
end

function M.ease(name)
    return tpl_kikito_tween.easing[get_easing_name(name)]
end

function M.setup(user_params)
    user_params = user_params or {}
    for key, value in pairs(user_params) do
        params[key] = value
    end
    validate_params()
    return M
end

M.kikito_tween = tpl_kikito_tween
M.easing = tpl_kikito_tween.easing

return M
