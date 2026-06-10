# a-trace-report — HTTP 上报通道

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | HTTP 上报通道（错误上报 + BI 埋点） |
| 路径 | `.codemaker/templates/a-trace-report/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `report`, `trace`, `error`, `http`, `webhook`, `analytics`, `cooldown` |
| 适用场景 | 线上报错自动上报飞书/Popo、开局/结算/抽卡行为埋点、失败限流防雪崩、编辑器自动屏蔽 |
| 依赖 | `y3.game:request_url` + JSON 编码器（通过 params 注入） |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → TraceReporter` |
| 参数 | `params.request_url`, `params.get_player_info`, `params.json_encode` (必需，JSON 编码器), `params.is_editor_mode?`, `params.cooldown_seconds?` |
| 测试状态 | `tested, 2026-05-29, 7/7 in agentmap (execute_lua)` |
| 集成说明 | `reporter:reportError(msg, url)`；`__G__TRACKBACK__ = M.createGlobalErrorHandler(reporter, url)` |

### ⚠️ 回归靶场已知坑

| 坑 | 现象 | 修复 |
|----|------|------|
| `is_editor_mode` 必须传 `function` 非 `boolean` | `attempt to call a boolean value` | `is_editor_mode = function() return true end` |
| `get_player_info` 返回 `nil` 时模板内部 pcall 吞错 | 静默失败 | 确保返回有效 table 如 `{pid=1}` |
