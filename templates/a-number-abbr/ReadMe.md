# a-number-abbr — 数字缩写格式化

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 数字缩写格式化 |
| 路径 | `.codemaker/templates/a-number-abbr/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `number`, `format`, `abbreviate`, `display`, `damage-text`, `currency` |
| 适用场景 | 伤害数字显示、货币数量、战力数值、排行榜分数 — 大数缩写成 1.0w / 1.0e 形式 |
| 依赖 | 纯 Lua |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.format(num, opts?)` 或 `M.setup(opts?)` |
| 参数 | `opts.levels?` (自定义缩写层级)、`opts.precision?` (小数位，默认 1) |
| 测试状态 | `tested, 2026-05-29, 8/8 in agentmap (execute_lua)` |
| 集成说明 | `local abbr = include '...'; abbr.format(12345) → "1.2w"` |
