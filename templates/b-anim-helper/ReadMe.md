# b-anim-helper — 单位动画事件钩子

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | 单位动画播放+帧事件调度 |
| 路径 | `.codemaker/templates/b-anim-helper/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `animation`, `frame-event`, `cast`, `skill`, `action-frame` |
| 适用场景 | 动作关键帧伤害判定、释放在指定帧触发音效、多段连击分段判定、施法被打断后自动取消剩余帧事件 |
| 依赖 | GameTimer（帧回调）、y3 施法事件 |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → AnimHelper` |
| 参数 | `params.add_frame_update`, `params.game_run_time?`, `params.cast_stop_events?` |
| 测试状态 | `validated in agentmap, 2026-05-29, passed (v0.1.1 fix: Y3 Lua closure capture order — update() must precede start())` |
| 集成说明 | `anim:playAnim(unit, { anim_name='attack', speed=1.5, events={[0.3]=onHit} })` |
