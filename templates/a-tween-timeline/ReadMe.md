# 通用补间动画时间线模板

提供集成 `kikito/tween.lua` 的 通用补间动画时间线，支持位置、缩放、旋转、透明度等属性的持续时间、完整 easing 曲线和链式编排。

> 注意：本模板为纯 Lua 模板，不含 UI。

## 模板登记

### a-tween-timeline

| 字段 | 内容 |
|------|------|
| 名称 | 通用补间动画时间线模板 |
| 路径 | `.codemaker/templates/a-tween-timeline/` |
| 状态 | `validated` |
| 版本 | `v1.0.0` |
| 能力标签 | `ui`, `animation`, `tween`, `easing`, `kikito-tween` |
| 适用场景 | 需要用时间线编排 UI 位移、缩放、旋转、透明度等补间动画，并需要 linear/out-back/out-elastic 等缓动曲线的界面表现。 |
| 依赖 | Y3 原生 API：`y3.ltimer.loop_frame`；内联第三方库：`kikito/tween.lua 2.1.1`（MIT/BSD 许可声明已随源码保留）；UI 适配层可选支持 `set_absolute_pos`, `set_widget_absolute_scale`, `set_widget_absolute_rotation`, `set_alpha` |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 参数 | `loop_frame`, `warn`, `default_fps` |
| 测试状态 | `validated in agentmap, 2026-05-26, passed` |
| 集成说明 | 本模板不含 `.upui`；由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块并在初始化时调用 `M.setup({...})` |

## 参数详述

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `loop_frame` | `function` | 否 | `y3.ltimer.loop_frame` | 帧循环函数，签名应兼容 `loop_frame(interval_frame, callback)` 并返回带 `:remove()` 的 timer。 |
| `warn` | `function` | 否 | no-op | 警告输出函数，用于提示 `call(0, fn)` 等边界情况。 |
| `default_fps` | `number` | 否 | `30` | 将秒级 duration 转换为帧数时使用的默认帧率。 |

## 公开 API

| API | 说明 |
|-----|------|
| `M.setup(params)` | 初始化计时器、日志、帧率参数。 |
| `M.new(ui_node)` | 创建绑定某个 UI 控件的时间线。 |
| `M.new_raw(duration, subject, target, ease)` | 直接创建原生 kikito tween 对象，适合非 UI 数据补间。 |
| `tween:call(frame, fn)` | 在时间线当前位置插入回调，然后推进指定帧数。 |
| `tween:delay(frame)` / `tween:wait(seconds)` | 推进时间线。 |
| `tween:tween(duration, updater, ease)` | 用秒级 duration 和 easing 每帧调用 `updater(t, raw_t)`。 |
| `tween:move_to(x, y, duration, ease)` | 补间到绝对坐标。 |
| `tween:scale_to(x, y, duration, ease)` | 补间到绝对缩放。 |
| `tween:rotate_to(rotation, duration, ease)` | 补间到绝对旋转。 |
| `tween:alpha_to(alpha, duration, ease)` | 补间透明度。 |
| `tween:native_move_to(...)` / `native_scale_to(...)` | 优先调用 Y3 原生 UI 动画 API，作为引擎侧动画封装。 |
| `tween:start()` / `tween:stop()` | 启动或停止时间线。 |
| `M.ease(name)` | 获取命名 easing 函数。 |

## 内置缓动曲线

完整集成 `kikito/tween.lua` 的 easing 表，包括：

- `linear`
- Quad / Cubic / Quart / Quint
- Sine / Expo / Circ
- Elastic / Back / Bounce
- `in*` / `out*` / `inOut*` / `outIn*` 组合，例如 `outBack`, `inOutQuad`, `outElastic`

模板额外兼容 kebab/snake 写法，例如 `out-back`、`in-out-quad` 会映射到 kikito 的 `outBack`、`inOutQuad`。

## 接入步骤

1. **导入 UI**：本模板为纯 Lua 模板，无需导入 `.upui`
2. **融合 Lua**：由 `y3-game-spec` 调用 `y3-lua-pipeline` 把 `logic.lua` 融合到目标模块
3. **传入参数**：模块初始化时 `M.setup({ loop_frame = y3.ltimer.loop_frame, default_fps = 30, warn = function(msg) log.warn(msg) end })`
4. **创建动画**：调用 `M.new(ui_node):move_to(...):scale_to(...):start()`
5. **回归验证**：验证补间过程中 UI 每帧平滑变化，动画结束后 timer 被移除

## 使用示例

```lua
local TweenTimeline = require("logic")

TweenTimeline.setup({
    loop_frame = y3.ltimer.loop_frame,
    default_fps = 30,
    warn = function(msg)
        if log and log.warn then
            log.warn(msg)
        end
    end,
})

TweenTimeline.new(root_ui)
    :call(1, function()
        root_ui:set_visible(true)
    end)
    :move_to(520, 260, 0.8, 'out-back')
    :scale_to(1.25, 1.25, 0.35, 'out-quad')
    :move_to(260, 320, 0.8, 'in-out-quad')
    :scale_to(1.0, 1.0, 0.35, 'out-quad')
    :move_to(390, 220, 0.9, 'out-elastic')
    :call(1, function()
        root_ui:set_visible(false)
    end)
    :start()
```

## 已知限制

- 当前模板是顺序时间线；同一时间并行动画需要用 `M.new_raw` / `tween(duration, subject, target, ease, updater)` 在同一 updater 内同时设置多个属性，或后续扩展 `parallel`。
- `alpha_to` 默认从 255 开始记录透明度；如果需要读取真实当前透明度，应由调用方扩展 getter 或先显式设置起点。
- `native_move_to` / `native_scale_to` 依赖目标 UI 封装存在 `set_anim_pos` / `set_anim_scale`，否则会退化为立即设置终值。
- 已完整内联 `kikito/tween.lua` 单文件核心；后续升级第三方库时需同步保留其许可文本。
- 已在 `agentmap` 测试工程中通过 F7 手动验证，当前状态为 `validated`。

## 源工程溯源

- 源模块：`global_script/client/ui/UIFrameTween.lua`
- 第三方库：`kikito/tween.lua 2.1.1`，https://github.com/kikito/tween.lua
- 升级参考：Y3-Share「补间动画」文档
- 导出日期：`2026-05-25`
- 导出工具：`y3-template-export`
