# b-gm-command — GM 调试指令系统

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | GM 调试指令系统 |
| 路径 | `.codemaker/templates/b-gm-command/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `gm`, `debug`, `command`, `console`, `recording`, `replay` |
| 适用场景 | 测试加资源、秒杀、一键全开、录制操作回放、上线自动屏蔽 |
| 依赖 | `y3.develop.command` |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params) → GM` |
| 参数 | `params.register_command`, `params.dev_only?`, `params.on_error?` |
| 测试状态 | `tested, 2026-05-29, 4/4 in agentmap (execute_lua)` |
| 集成说明 | `gm:register('addGold', { desc='加金币', onCommand=fn }); gm:input('.addGold 1000', player)` |
