# b-shield-stack — 优先级护盾栈

## 模板信息

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | 优先级护盾栈 |
| 路径 | `.codemaker/templates/b-shield-stack/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `shield`, `damage`, `absorb`, `priority`, `stack`, `defense` |
| 适用场景 | RPG/Roguelike/MOBA 中多源护盾叠加（装备+技能+Buff）。消耗时按 priority 从高到低扣，低 priority 护盾先被打穿 |
| 依赖 | Adapter：`create_linked_list` + `add_attr/get_attr`；可选 `bind_buff/remove_buff` |
| UI 文件 | — |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter) → ShieldSystem` |
| 参数 (Adapter) | `create_linked_list`, `add_attr(unit, attr, delta)`, `get_attr(unit, attr)`, `bind_buff?`, `remove_buff?`, `on_shield_break?` |
| 测试状态 | `tested, 2026-05-29, 5/5 in agentmap (execute_lua)` |
| 集成说明 | `local shieldSys = ShieldStack.setup({...})`；`shieldSys:addShield(unit, 500, 10)` → `shieldSys:costShield(unit, 300)` |

---

## 功能

- **addShield**(unit, value, priority?, buff?) → shield 实例
- **costShield**(unit, damage) → 实际伤害吸收量
- **updateShield**(shield, newValue, multiplier?)
- **removeShield**(shield) / **clearShields**(unit)
- **getTotalShield**(unit)
