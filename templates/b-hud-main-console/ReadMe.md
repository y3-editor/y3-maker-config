# HUD 底部控制台模板

> **等级**：B
> 战斗 HUD 底部控制台，展示选中目标属性 + 英雄状态（等级/经验/HP/MP/技能/物品/Buff）。

---

## ⚠️ 使用前必读：需手动导入序列帧资源

本模板的进度条动画依赖 4 个序列帧资源包，**不会随 `.upui` 自动导入**，需要手动操作：

**资源位置**：模板文件夹 `.codemaker/templates/b-hud-main-console/` 下的 4 个 `.package` 文件夹

| 资源包 | 用途 |
|--------|------|
| `红色_00000.package` | 进度条序列帧（红色） |
| `黄色_00000.package` | 进度条序列帧（黄色） |
| `蓝色_00000.package` | 进度条序列帧（蓝色） |
| `绿色_00000.package` | 进度条序列帧（绿色） |

**导入步骤**（每个 `.package` 都要操作）：
1. 在 Y3 编辑器「资源管理器」面板，右键目标目录
2. 选择「导入资源」
3. 选中对应的 `.package` 文件夹，确认导入

> 导入完成后，进度条动画才能正常显示。如果进度条显示异常（空白/默认贴图），优先检查这4个资源是否已导入。

---

## 模板登记

### b-hud-main-console

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | HUD 底部控制台模板 |
| 路径 | `.codemaker/templates/b-hud-main-console/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `HUD`, `控制台`, `英雄状态`, `目标信息`, `物品栏`, `Buff` |
| 适用场景 | 需要底部控制台的地图，展示选中目标的属性/HP/Buff + 英雄头像/等级/经验/HP/MP/技能栏/物品栏/Buff |
| 依赖 | `MainConsole` 画板；`ItemCmp`、`HeroAbilityCmp`、`AttrTextCmp`、`SequenceProgress` 元件；图标资源 |
| UI 文件 | `b-hud-main-console.upui` |
| UI 根节点/资源 | 画板 `MainConsole`；元件 `ItemCmp`、`HeroAbilityCmp`、`AttrTextCmp`；图标见模板 ReadMe |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `ui_paths`, `local_player_id`, `ui_fetch`, `get_unit_attr`, `get_unit_level`, `get_unit_exp`, `target_attr_ids`, `callbacks` |
| 测试状态 | `validated in EntryMap, 2026-06-04, passed` |
| 集成说明 | 先导入 `b-hud-main-console.upui`，再由 `y3-lua-pipeline` 将 `logic.lua` 融合 |

## ⚠️ 集成经验（2026-06-04 验证）

### 关键适配要点

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `attr_configs` 中 `'攻击'` 返回 0 | Y3 正确 key 是 `'物理攻击'` | 参考 `y3/game/const.lua` UnitAttr 枚举 |
| `'力量'`/`'敏捷'`/`'智力'` = 10 默认值 | Y3 无这三个属性 | 改用 `'物理防御'`/`'法术攻击'`/`'法术防御'` |
| HP 进度条 `mask_w=40`（扁条） | `mask` 已被 `set_ui_size` 修改，不能作为满血基准 | **用父容器 `heroHP_BAR:get_width()` 作基准**，mask 动态缩放 |
| `exp_TEXT` / `level_TEXT` 显示浮点 | `get_level()`/`get_exp()` 返回定点数 | `math.floor()` 确保整数，`exp_TEXT` 单独设置 |
| `y3.ui.get_ui` 第一参数 | 需传 `Player` 对象 | `y3.player(pid)` 转换，不能传 integer |

### 画板节点路径（实测 EntryMap）

```
根路径前缀：MainConsole.MainConsole

HP Bar 容器：      .main.bar.hp.heroHP_BAR          (Layout, w=461)
  └ mask：         .main.bar.hp.heroHP_BAR.mask      (动态宽度)
  └ cur_TEXT：     .main.bar.hp.heroHP_BAR.cur_TEXT  (实为 "cur_TEXT" 非 "hp_TEXT")
  └ extra_TEXT：   .main.bar.hp.heroHP_BAR.extra_TEXT (实为 "extra_TEXT" 非 "regen_TEXT")

MP Bar 同理（路径：.main.bar.mp.heroMP_BAR）

英雄头像区 avatar：
  头像图：        .avatar.main.mask.heroAvatar_IMG
  名称：          .avatar.main.title.title_TEXT
  等级：          .avatar.level_TEXT
  经验条：        .avatar.exp_RPOG          (type_41 ProgressBar)
  经验文本：      .avatar.exp_RPOG.exp_TEXT

技能槽（type_17 官方控件，bind_ability 绑定）：
  D 技能：        .common_skill.1.slot      → slot:bind_ability(ability)
  F2 技能：       .common_skill.2.slot      → slot:bind_ability(ability)
  主技能：        .main.heroSkill.slot

属性格：          .attr_GRID.1-4  (icon + title_TEXT + value_TEXT)
次属性：          .avatar.attr.1-2  (icon + value_TEXT)
物品栏：          .gearbag.item_GRID.1-6   (type_20 官方)
Buff 列表：       .buff.buff_list           (type_19 官方，自动驱动)
```

### attr_configs 正确示例

```lua
attr_configs = {
    { attr = '物理攻击', title = '攻击' },
    { attr = '物理防御', title = '护甲' },
    { attr = '法术攻击', title = '法攻' },
    { attr = '法术防御', title = '法防' },
},
sub_attr_configs = {
    { attr = '攻击速度', title = '攻速' },
    { attr = '移动速度', title = '移速' },
}
```

### Bond_GRID + skill prefab 技能列表（推荐方案）

**工作流**：
1. 在 UI 编辑器里创建元件 `skill`，包含 `slot [type_17]`（技能按钮）+ `bg`/`frame`/`shortcut` 等子节点
2. 在画板中放置 `Bond_GRID [type_25]`（GridView），**在编辑器里设好格子大小和间距**
3. 运行时用 Lua 动态创建 prefab 实例并绑定技能

```lua
-- 收集单位全部自定义技能（英雄→命令→普通，跳过 key=999 普攻）
local abilities = {}
local seen = {}
for _, ab_type in ipairs({ '英雄', '命令', '普通' }) do
    for i = 1, 8 do
        local a = unit:get_ability_by_slot(ab_type, i)
        if a and a:get_key() ~= 999 and not seen[a:get_key()] then
            seen[a:get_key()] = true
            abilities[#abilities + 1] = a
        end
    end
end

-- 为每个技能创建 skill prefab 并绑定
for _, ability in ipairs(abilities) do
    local ins = y3.ui_prefab.create(player, 'skill', bond_grid)
    if ins then
        local slot = ins:get_child('slot')
        if slot then
            slot:bind_ability(ability)   -- 绑定技能（层数/状态）
            -- ⚠️ 不调用 bind_unit：cd_prog 方向反（就绪度 0→100），用手动刷新代替

            -- ⚠️ bind_ability 不自动赋值图标，必须手动 set_image
            local icon_node = slot:get_child('icon')
            if icon_node then
                local ok, icon_id = pcall(function() return ability:get_icon() end)
                if ok and icon_id and icon_id ~= 0 then
                    icon_node:set_image(icon_id)
                end
            end
        end
        skill_prefab_insts[#skill_prefab_insts+1] = ins
        skill_abilities[#skill_abilities+1] = ability  -- 同步缓存，用于 CD 刷新
    end
end

-- 手动刷新 CD 遮罩（放在 0.5s 定时器里调用）
-- cd_prog 值 = cd_rem/cd_max*100，满=100=冷却中，0=可使用
function refresh_skill_cd()
    for i, ins in ipairs(skill_prefab_insts) do
        local ab = skill_abilities[i]
        if not ab then break end
        local slot = ins:get_child('slot')
        local cd_prog = slot and slot:get_child('cd_prog')
        if cd_prog then
            local cd_rem = ab:get_cd() or 0
            local cd_max = ab:get_max_cd() or 0
            local pct = (cd_max > 0) and math.max(0, math.min(100, (cd_rem/cd_max)*100)) or 0
            cd_prog:set_current_progress_bar_value(pct)
        end
    end
end
```

**⚠️ CD 冷却遮罩方向反了（已验证根因）**：
- `bind_unit` 让引擎驱动 `cd_prog`，但方向是**就绪度**（CD完成=100，冷却中=0）
- 遮罩需要**剩余度**（冷却中=100，CD完成=0）—— 方向相反
- **正确做法**：不调用 `bind_unit`，定时器手动写 `cd_prog:set_current_progress_bar_value(cd_rem/cd_max*100)`

**⚠️ 图标不生效**：
- `bind_ability` 不自动把技能图标赋值到 `icon` 子节点
- 必须手动：`slot:get_child('icon'):set_image(ability:get_icon())`

**⚠️ GridView 格子比例问题（常见坑）**：
- 如果技能图标显示比例不对（被压扁/拉伸），根本原因是 **skill prefab 设计尺寸 ≠ Bond_GRID 格子大小**
- **正确做法**：在 UI 编辑器里将 Bond_GRID 的「格子宽度」和「格子高度」设置为与 skill prefab 一致的正方形尺寸
- 不推荐用 Lua `set_ui_gridview_size` 强制覆盖（会绕过编辑器设置，后续难维护）
- prefab 热更+保存+重启游戏后才能被 `y3.ui_prefab.create` 识别；否则报 `KeyError: 'skill'`



```lua
-- 推荐方案：Bond_GRID + skill prefab，支持任意数量技能
local bond_grid = y3.ui.get_ui(player, 'MainConsole.MainConsole.main.Bond_GRID')
local insts = {}

-- 收集技能（英雄→命令→普通，跳过 key=999 普攻）
local abilities = {}
local seen = {}
for _, ab_type in ipairs({ '英雄', '命令', '普通' }) do
    for i = 1, 8 do
        local a = unit:get_ability_by_slot(ab_type, i)
        if a and a:get_key() ~= 999 and not seen[a:get_key()] then
            seen[a:get_key()] = true
            abilities[#abilities + 1] = a
        end
    end
end

-- 动态创建 skill prefab 并绑定
for _, ability in ipairs(abilities) do
    local ins = y3.ui_prefab.create(player, 'skill', bond_grid)
    if ins then
        local slot = ins:get_child('slot')
        if slot then slot:bind_ability(ability) end
        insts[#insts + 1] = ins
    end
end
```

> ⚠️ **prefab 注意事项**：
> - prefab 需先在编辑器里创建并热更+保存后重启游戏，才能被 `y3.ui_prefab.create` 识别
> - 未注册时报 `KeyError: 'skill'`
> - `ins:get_child('slot')` — 路径相对于 prefab 根节点一层之后（不带 `root.` 前缀）





> **等级**：B
> 战斗 HUD 底部控制台，展示选中目标属性 + 英雄状态（等级/经验/HP/MP/技能/物品/Buff）。

## 模板登记

### b-hud-main-console

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | HUD 底部控制台模板 |
| 路径 | `.codemaker/templates/b-hud-main-console/` |
| 状态 | `draft` |
| 版本 | `v0.1.0` |
| 能力标签 | `HUD`, `控制台`, `英雄状态`, `目标信息`, `物品栏`, `Buff` |
| 适用场景 | 需要底部控制台的地图，展示选中目标的属性/HP/Buff + 英雄头像/等级/经验/HP/MP/技能栏/物品栏/Buff |
| 依赖 | `MainConsole` 画板；`ItemCmp`、`HeroAbilityCmp`、`AttrTextCmp`、`SequenceProgress` 元件；图标资源 |
| UI 文件 | `b-hud-main-console.upui` |
| UI 根节点/资源 | 画板 `MainConsole`；元件 `ItemCmp`、`HeroAbilityCmp`、`AttrTextCmp`；图标见模板 ReadMe |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `ui_paths`, `local_player_id`, `ui_fetch`, `get_unit_attr`, `get_unit_level`, `get_unit_exp`, `target_attr_ids`, `callbacks` |
| 测试状态 | `not tested` |
| 集成说明 | 先导入 `b-hud-main-console.upui`，再由 `y3-lua-pipeline` 将 `logic.lua` 融合 |

## 功能

1. **选中目标信息** — 绑定/清除目标单位，显示头像/名称/怪物标签/六维属性/HP/MP/Buff
2. **英雄头像名称** — 根据 hero_id 刷新英雄头像和名称
3. **英雄等级经验** — 刷新等级数字 + 经验进度条
4. **英雄 HP/MP** — 生命值/魔法值文本 + 进度条，含恢复速率
5. **英雄属性** — 主属性列表（攻击/力量/敏捷/智力）+ 次属性（攻速/护甲）+ 额外加成
6. **英雄技能栏** — D/F2/Main 技能图标绑定
7. **物品栏** — 6 格物品槽位刷新
8. **Buff 栏** — 英雄 + 目标的 Buff 图标 + hover 事件
9. **复活读条** — 死亡后的复活倒计时进度条

## 参数详述

### `params.ui_paths`（必填）

见 `logic.lua` 头部注释，共 30+ 个 UUID 映射，分为：
- **目标信息区** (target_*)：root / icon / name / monster_tag / main_attr / buff_view / hp/mp prog+text / attr_parent
- **英雄状态区** (hero_*)：icon / name / lv / exp / hp / mp / revive / attr / buff
- **技能按钮** (ability_*)：d / f2 / main
- **物品栏** (bag_*)：btn / item_view
- **属性列表** (attr_list*)：parent + list2 + list3 + list4

### `params.callbacks`（可选）

| 回调 | 签名 | 说明 |
|------|------|------|
| `on_select_unit` | `function(unit)` | 选中目标单位时 |
| `on_deselect_unit` | `function()` | 取消选中时 |
| `on_attr_btn_click` | `function()` | 属性面板按钮点击 |
| `on_bag_btn_click` | `function()` | 背包按钮点击 |
| `on_ability_click` | `function(key)` | 技能按钮点击 |
| `on_attr_hover` | `function(index, pid)` | 属性 hover |
| `on_attr_hover_out` | `function()` | 属性 hover 离开 |
| `on_buff_hover` | `function(buff, idx, pid)` | Buff hover |
| `on_buff_hover_out` | `function()` | Buff hover 离开 |
| `on_bind_audio` | `function(uiNode)` | 绑定音效 |
| `get_hero_config` | `function(hid) → {icon,name}` | 英雄配置查询 |
| `get_ability_ctrl` | `function(pid,key) → ctrl` | 技能控制器 |
| `get_bag` | `function(pid,name) → bag` | 背包对象 |
| `get_main_attr_type` | `function(unit) → 0-3` | 主属性类型 |
| `format_number` | `function(n,useK) → str` | 数字格式化 |

### 其他参数

| 参数 | 说明 |
|------|------|
| `target_attr_ids` | 目标属性 ID 列表（默认 `{30,66,38,1,8,15}`） |
| `hero_attr_ids` | 英雄主属性 ID（默认 `{30,1,8,15}`） |
| `hero_sub_attr_ids` | 英雄次属性 ID（默认 `{66,38}`） |
| `item_bag_name` | 物品栏名称（默认 `"物品栏"`） |
| `resources` | 图标资源（main_attr_icons / monster_tag_elite / monster_tag_boss） |

## 公开 API

### 英雄状态

| 方法 | 说明 |
|------|------|
| `M.refresh_hero_info(hero_id)` | 刷新头像/名称 |
| `M.refresh_hero_level_exp(unit)` | 刷新等级/经验 |
| `M.refresh_hero_hp(unit)` | 刷新 HP |
| `M.refresh_hero_mp(unit)` | 刷新 MP |
| `M.refresh_hero_regen(unit)` | 刷新恢复速率 |
| `M.refresh_hero_main_attr(unit)` | 刷新主属性 |
| `M.refresh_hero_sub_attr(unit)` | 刷新次属性 |
| `M.refresh_hero_buffs(unit)` | 刷新 Buff 列表 |
| `M.refresh_revive(time_left?)` | 刷新复活读条 |
| `M.refresh_ability_icon(ctrl, key)` | 刷新技能图标 |

### 目标信息

| 方法 | 说明 |
|------|------|
| `M.bind_target_unit(unit)` | 绑定选中目标 |
| `M.clear_target_unit()` | 清除选中目标 |
| `M.refresh_target_attrs()` | 刷新目标属性 |
| `M.get_target_unit()` | 获取当前目标单位 |

### 物品栏

| 方法 | 说明 |
|------|------|
| `M.refresh_item_bag(bag)` | 刷新物品栏 |

### 通用

| 方法 | 说明 |
|------|------|
| `M.setup(params)` | 初始化 |
| `M.is_inited()` | 是否已初始化 |

## 接入步骤

```lua
local Console = require 'templates.b-hud-main-console'

Console.setup({
    local_player_id = localPlayerId,
    ui_fetch        = function(pid, uuid) return y3.ui.get_ui(pid, uuid) end,
    get_unit_attr   = function(unit, attr) return GetUnitAttr(unit, attr) end,
    get_unit_level  = function(unit) return unit:get_level() end,
    get_unit_exp    = function(unit) return unit:get_exp(), unit:get_upgrade_exp() end,
    target_attr_ids = { 30, 66, 38, 1, 8, 15 },
    ui_paths = {
        target_root  = "你的UUID",
        hero_icon    = "你的UUID",
        -- ... 全部填入
    },
    resources = {
        main_attr_icons   = { 134xxx, 134xxx, 134xxx, 134xxx },
        monster_tag_elite = 134xxx,
        monster_tag_boss  = 134xxx,
    },
    callbacks = {
        get_hero_config    = function(hid) return configMgr:getHeroConfig().getById(hid) end,
        get_ability_ctrl   = function(pid, key) return heroCtrl:getUnitAbility(key) end,
        get_bag            = function(pid, name) return y3.player(pid):getBag(name) end,
        get_main_attr_type = function(unit) return GetUnitAttr(unit, '主属性') end,
        format_number      = function(n, k) return FormatNumber(n, k) end,
        on_bag_btn_click   = function() -- 打开背包 end,
        on_buff_hover      = function(buff, idx, pid) -- 显示 Buff Tips end,
        on_buff_hover_out  = function() -- 隐藏 Tips end,
    },
})

-- 游戏事件中：
-- 英雄升级：Console.refresh_hero_level_exp(unit)
-- 属性变化：Console.refresh_hero_hp(unit); Console.refresh_hero_mp(unit)
-- 选中目标：Console.bind_target_unit(target_unit)
-- 物品变化：Console.refresh_item_bag(bag)
```

## 已知限制

- `.upui` 导出含全部 8 个场景 UI
- 英雄属性列表假设 UI 结构为 `parent:get_child("N.value_TEXT")`
- 目标 HP/MP 进度条使用简化版 `set_current_progress_bar_value`，源工程的 `SequenceProgress` 平滑动画需融合侧实现
- 按钮音效绑定需融合侧注入 `on_bind_audio`
- 英雄技能栏仅支持 D/F2/Main 三个键位
