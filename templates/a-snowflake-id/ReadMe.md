# a-snowflake-id — 雪花全局唯一 ID

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 雪花全局唯一 ID |
| 路径 | `.codemaker/templates/a-snowflake-id/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `id`, `snowflake`, `unique-id`, `sequence`, `instance-id` |
| 适用场景 | 物品实例ID、Buff实例ID、伤害事件ID、交易流水号 — 单局内不重复的单调递增 ID |
| 依赖 | 纯 Lua（`os.time` + 位运算） |
| UI 文件 | — |
| UI 根节点/资源 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.nextID() → integer|nil` |
| 参数 | 无（纯函数） |
| 测试状态 | `tested, 2026-05-29, 4/4 in agentmap (execute_lua)` |
| 集成说明 | `local Snowflake = include '...'; local id = Snowflake.nextID()` |
