# 纯 ECA 运行时探针片段

> 用途：没有 y3-auto-test 的纯 ECA 验收时，直接用 `execute_lua` 做状态注入、采样和 UI 点击。
> 这些片段只用于测试，不要写进游戏业务文件。
> 片段里的变量名、画板名、单位 ID 都是占位示例，使用时替换成当前工程的真实名字。

## 1. 读取全局变量

```lua
return {
  state = GameAPI.get_trigger_variable_integer('游戏状态'),
  wave = GameAPI.get_trigger_variable_integer('波次'),
  gold = GameAPI.get_trigger_variable_integer('金币'),
  remaining = GameAPI.get_trigger_variable_integer('剩余次数'),
  settled = GameAPI.get_trigger_variable_integer('结算标志'),
}
```

## 2. 暂停战斗并清场

```lua
GameAPI.set_trigger_variable_integer('游戏状态', 0)
local hero = y3.unit.get_by_handle(GameAPI.get_trigger_variable_unit_entity('英雄'))
for _, u in ipairs(y3.player(31):get_all_units():pick()) do
  u:kill_by(hero)
end
if hero and not hero:is_alive() then hero.handle:api_revive(nil) end
if hero then
  hero:set_hp(hero:get_attr('hp_max'))
  hero:set_mp(hero:get_attr('mp_max'))
end
```

## 3. 造一只静音测试怪

```lua
local hero = y3.unit.get_by_handle(GameAPI.get_trigger_variable_unit_entity('英雄'))
local p = hero:get_point()
local dummy = y3.unit.create_unit(
  y3.player(31), 200001, y3.point.create(p:get_x() + 400, p:get_y(), 0), 0)  -- 200001 换成工程内已有的单位模板 ID
dummy:set_attr('攻击间隔', 100, '基础')
dummy:set_attr('alarm_range', 0, '基础')
return { key = dummy:get_key(), hp = dummy:get_hp() }
```

## 4. 施法并采样（必须查存活 / CD / 蓝量 / 效果）

```lua
local hero = y3.unit.get_by_handle(GameAPI.get_trigger_variable_unit_entity('英雄'))
local ab = hero:get_ability_by_slot(y3.const.AbilityType.HERO, 1)
local dummy = y3.player(31):get_all_units():pick()[1]
local before = dummy:get_hp()
local cd0 = ab:get_cd()
hero:cast(ab, dummy)
y3.ctimer.wait(1.2, function()
  _G.__probe = {
    alive = hero:is_alive(),
    before = before,
    after = dummy:get_hp(),
    cd0 = cd0,
    cd1 = ab:get_cd(),
    mp = hero:get_mp(),
  }
end)
```

> 点目标（`sight_type=3`）和扇形（`1`）在脚本里可能放不出去；先看 CD/蓝量是否变化，
> 没变化就是“这次没放出去”，不要误判成技能坏了。

## 5. Buff / 状态采样

```lua
local d = y3.player(31):get_all_units():pick()[1]
return {
  speed = d:get_attr('ori_speed'),
  no_attack = d:has_state(2),
  no_move = d:has_state(8),
  untargetable = d:has_state(32768),
  shield = d.handle:api_get_unit_shield_value(2),
}
```

## 6. UI 显隐

```lua
local p = y3.player(1)
local function vis(path)
  local ok, ui = pcall(function() return y3.ui.get_ui(p, path) end)
  if ok and ui then
    local o, v = pcall(function() return ui:is_visible() end)
    if o then return v end
  end
end
return {
  select_panel = vis('MySelectPanel.block'),
  hud = vis('MyHUD.block'),
  items = vis('MyBagPanel.block'),
  result = vis('MyResultPanel.block'),
  exit = vis('MyExitConfirm.block'),
}
```

## 7. 发送 UI 具名事件（驱动 ECA）

```lua
local p = y3.player(1)
y3.ui.get_ui(p, 'MySelectPanel.block.card_3.card_btn_3'):send_event('card_3_click')
```

> 面板必须是可见的；隐藏面板的控件收不到事件。

## 8. 模拟胜利 / 失败

```lua
-- 胜利：把波次顶到 10 并清空怪物，等 1 秒轮询
GameAPI.set_trigger_variable_integer('游戏状态', 1)
GameAPI.set_trigger_variable_integer('结算标志', 0)
GameAPI.set_trigger_variable_integer('波次', 10)
local hero = y3.unit.get_by_handle(GameAPI.get_trigger_variable_unit_entity('英雄'))
for _, u in ipairs(y3.player(31):get_all_units():pick()) do u:kill_by(hero) end

-- 失败：剩余次数置 0 后杀死英雄
-- GameAPI.set_trigger_variable_integer('剩余次数', 0)
-- hero:kill_by(nil)
```

## 9. 物品栏与装备属性

```lua
local hero = y3.unit.get_by_handle(GameAPI.get_trigger_variable_unit_entity('英雄'))
local items = {}
for _, it in ipairs(hero:get_all_items():pick()) do
  items[#items + 1] = string.format('%s(slot_type=%s, slot=%s)',
    it:get_name(), tostring(it:get_slot_type()), tostring(it:get_slot()))
end
return { items = items, attack = hero:get_attr('attack_phy'), hp_max = hero:get_attr('hp_max') }
```
