# a-date-time — 时间工具集

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 时间格式化与判定工具集 |
| 路径 | `.codemaker/templates/a-date-time/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `time`, `timestamp`, `format`, `date`, `countdown`, `cross-day`, `cross-week`, `holiday` |
| 适用场景 | 倒计时显示、跨天/跨周刷新、签到、时间区间判定、GM模拟时间调试 |
| 依赖 | `os.date` / `os.time`；可选 `params.get_server_time`（服务器时间注入） |
| UI 文件 | — |
| Lua 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → 工具函数表` |
| 参数 | `params.get_server_time?`（fun(hour_offset): {timestamp}）、`params.utc_offset?`（默认 8） |
| 测试状态 | `tested, 2026-05-29, 6/7 in agentmap (execute_lua). Known: isSameDate depends on os.date %x locale format` |
| 集成说明 | `local Time = include '...'; local t = Time.setup({ get_server_time = y3.game.get_current_server_time })` |
