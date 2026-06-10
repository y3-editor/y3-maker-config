# 贝塞尔弹道模板

提供可复用的贝塞尔轨迹计算，并驱动 Y3 投射物沿曲线路径移动到单位或点目标。

> 注意：本模板为纯 Lua 模板，不含 UI。

## 模板登记

### a-bezier-trajectory

| 字段 | 内容 |
|------|------|
| 名称 | 贝塞尔弹道模板 |
| 路径 | `.codemaker/templates/a-bezier-trajectory/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `trajectory`, `projectile`, `bezier` |
| 适用场景 | 需要让投射物按二次/三次贝塞尔曲线飞向单位或点目标，并支持速度、加速度、转直线追踪等参数的技能表现。 |
| 依赖 | Y3 原生 API：`y3.timer.loop_frame`, `y3.point.create`; 调用方需传入 `Projectile`、`Unit` 或 `Point` 对象 |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 参数 | `max_speed`, `delta_time`, `lut_segments`, `switch_ratio` |
| 测试状态 | `validated in agentmap, 2026-05-26, passed` |
| 集成说明 | 本模板不含 `.upui`；由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块并在初始化时调用 `M.setup({...})` |

## 参数详述

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `max_speed` | `number` | 否 | `3200` | 默认最大飞行速度，运动 API 未单独传入时使用。 |
| `delta_time` | `number` | 否 | `1 / 30` | 每帧推进的时间步长。 |
| `lut_segments` | `number` | 否 | `120` | 弧长查找表采样段数，越大曲线速度越平滑。 |
| `switch_ratio` | `number` | 否 | `0.2` | `mover_target` 接近目标后切换到 Y3 原生直线/追踪运动的距离比例。 |

## 接入步骤

1. **导入 UI**：本模板为纯 Lua 模板，无需导入 `.upui`
2. **融合 Lua**：由 `y3-game-spec` 调用 `y3-lua-pipeline` 把 `logic.lua` 融合到目标模块
3. **传入参数**：模块初始化时 `M.setup({...})`
4. **回归验证**：创建投射物并分别验证 `M.create`、`M.mover_target`、`M.mover_target_by_pure_heart`、`M.mover_point`

## 已知限制

- 依赖调用方传入有效的 Y3 `Projectile`、`Unit` 或 `Point` 对象；模板本身不创建投射物。
- 当前模板保留源模块的默认速度、加速度和切换比例；不同技能表现应通过参数或调用数据覆盖。
- 未包含源模块的调试速度历史统计。
- 已在 `agentmap` 测试工程中验证通过，当前状态为 `validated`。

## 源工程溯源

- 源模块：`global_script/client/tools/bezierTrajectory.lua`
- 导出日期：`2026-05-22`
- 导出工具：`y3-template-export`
