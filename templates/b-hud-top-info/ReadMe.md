# HUD 顶部信息栏模板

> **等级**：B
> 战斗 HUD 顶部信息栏，显示游戏模式、波次信息、游戏时间、阶段倒计时、玩家货币，含日夜循环动画与功能开关按钮。

## 模板登记

### b-hud-top-info

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | HUD 顶部信息栏模板 |
| 路径 | `.codemaker/templates/b-hud-top-info/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `HUD`, `信息栏`, `货币`, `波次`, `倒计时`, `日夜` |
| 适用场景 | 需要顶部 HUD 信息栏的战斗/塔防/生存类地图，显示游戏进程关键数据 |
| 依赖 | `top_info` 画板、`CurrencyCmp` 元件（货币）、`SequenceProgress` 元件（进度条）、图标资源（货币图标/按钮态图标） |
| UI 文件 | `b-hud-top-info.upui` |
| UI 根节点/资源 | 画板 `top_info`；元件 `CurrencyCmp`、`MissionProgCmp`；图标见参数 `resources` |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `ui_paths`, `currency_ids`, `get_item_config`, `get_currency_num`, `local_player_id`, `ui_fetch`, `resources`, `callbacks` |
| 测试状态 | `validated in EntryMap, 2026-06-04, passed` |
| 集成说明 | 先导入 `b-hud-top-info.upui`，再由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块 |

## ⚠️ 集成经验（2026-06-04 验证）

| 问题 | 根因 | 解决 |
|------|------|------|
| `y3.ui.get_ui` 第一参数 | 需传 Player 对象，不能传 integer | `y3.player(pid)` 转换 |
| 货币增量节点显示绿色数字 | `goodAdd`/`woodAdd`/`killAdd` 节点默认有值 | `init_ui` 时 `set_visible(false)` |
| `get_ui` 在 `游戏-初始化` 同帧调用失败 | UI 节点未完全注册 | `y3.ltimer.wait_frame(1, fn)` 延迟 1 帧 |

### 货币节点路径

```
res_GRID.gold / res_GRID.wood / res_GRID.kill  → 主货币节点
res_GRID.goodAdd / woodAdd / killAdd           → 增量节点（需隐藏）
res_GRID.playerGoldAdd_TEXT                    → 金币增量文本（需隐藏）
```

## 功能

1. **游戏模式** — 设置当前游戏模式文本
2. **波次信息** — 刷新波次标题 + 阶段倒计时（文本 + 进度条）
3. **游戏时间** — 每秒更新已过时间显示
4. **玩家货币** — 显示 3 种货币（默认金币/木材/食物），含 hover 提示
5. **日夜循环** — 日夜切换时的动画显示
6. **结算按钮** — 显隐/激活态切换
7. **右上角按钮组** — 设置/菜单/帮助/退出（需融合侧绑定回调）
8. **功能开关按钮** — 跳字/镜头锁定/特效开关（四态图标 + Tips 提示）

## 参数详述

### `params.ui_paths`（必填）

所有 UI 节点的 UUID 映射表：

| 键 | 说明 | 示例 UUID |
|----|------|-----------|
| `game_mode` | 游戏模式文本 | `12971eb0-4266-46b2-bde9-c41afab96ca5` |
| `wave_title` | 波次标题 | `7faf7342-475d-4dee-8509-32f8805c4d98` |
| `wave_counter` | 倒计时文本 | `d052fecd-2053-4a3c-b6fb-fe02ced504c7` |
| `wave_prog` | 倒计时进度条 | `ff9a710d-41d2-47bf-8c45-d77376eaac0d` |
| `wave_prog_symb` | 进度条符号 | `27752442-c263-454f-b0f8-d89cb62c6bdf` |
| `pass_time` | 游戏时间文本 | `9efec1ec-7c24-42ec-abea-692539950ff0` |
| `day_night_cirle` | 日夜圆圈 | `d47d62a7-da6c-4fdf-bd31-df40ca3ff7a8` |
| `day_dyn_frame` | 日夜动态框 | `a164d70d-809d-4d74-a4e6-11abf19e1fe2` |
| `day_dyn_img` | 日夜动态图 | `b4a2d7ef-aa87-4ad0-931a-309ed0baf2d3` |
| `day_img` | 日夜图标 | `7db0caf1-232e-4c0e-aeca-daf21abc5cc6` |
| `settle_btn` | 结算按钮 | `d7832372-258b-494d-becc-f462e44166bc` |
| `setting_btn` | 设置按钮 | `ff83e1e6-ccf1-4f77-8868-c48b6a60c75e` |
| `menu_btn` | 菜单按钮 | `5f95f799-a4a6-4066-8b39-848571ba5e76` |
| `help_btn` | 帮助按钮 | `8b2b8fb4-2db7-4bc9-82ac-01eca8dff144` |
| `exit_btn` | 退出按钮 | `a72d03d2-3ab4-41dd-8e4e-54197f70585f` |
| `jump_btn` | 跳字开关 | `d713c704-4df7-47fd-bc38-a88d8e80bf5d` |
| `camera_btn` | 镜头锁定 | `28a1e765-0515-4ef1-b81d-6cfc4171d4cd` |
| `sfx_btn` | 特效开关 | `92ebe500-5739-41d2-8414-9172ade13963` |
| `currency_nodes` | 货币节点列表 | `{ {ui=..., icon=...}, ... }` × 3 |
| `power` | 活动值节点（可选） | `1c99af6e-5abd-4885-9c55-32403c88e88e` |
| `power_text` | 活动值文本（可选） | `36b79c35-9d28-4408-8861-319d202f81b9` |

### `params.resources`（可选，有默认值）

| 键 | 说明 | 类型 |
|----|------|------|
| `day_img` | 白天图标 ID | `integer` |
| `night_img` | 夜晚图标 ID | `integer` |
| `day_dyn_img` | 白天动态图标 ID | `integer` |
| `night_dyn_img` | 夜晚动态图标 ID | `integer` |
| `jump_on` | 跳字开启四态图标 | `{int×4}` |
| `jump_off` | 跳字关闭四态图标 | `{int×4}` |
| `sfx_on` | 特效开启四态图标 | `{int×4}` |
| `sfx_off` | 特效关闭四态图标 | `{int×4}` |
| `camera_on` | 镜头锁定四态图标 | `{int×4}` |
| `camera_off` | 镜头未锁定四态图标 | `{int×4}` |

### `params.callbacks`（可选）

| 回调 | 签名 | 说明 |
|------|------|------|
| `on_settle_click` | `function()` | 结算按钮点击 |
| `on_setting_click` | `function(local_player)` | 设置按钮点击 |
| `on_menu_click` | `function(local_player)` | 菜单按钮点击 |
| `on_help_click` | `function()` | 帮助按钮点击 |
| `on_exit_click` | `function()` | 退出按钮点击 |
| `on_toggle_jump` | `function(on)` → new_on | 跳字开关切换，返回新状态 |
| `on_toggle_sfx` | `function(on)` → new_on | 特效开关切换，返回新状态 |
| `on_toggle_camera` | `function(playerId)` | 相机锁定切换 |
| `is_jump_on` | `function()` → boolean | 查询跳字状态 |
| `is_sfx_on` | `function()` → boolean | 查询特效状态 |
| `is_camera_locked` | `function(playerId)` → boolean | 查询镜头锁定状态 |
| `is_day` | `function()` → boolean | 查询是否白天 |
| `on_bind_audio` | `function(uiNode)` | 绑定按钮音效 |
| `show_tips` | `function(tipsData)` | 显示 Tips 提示 |
| `hide_tips` | `function()` | 隐藏 Tips |

### 其他必填参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `currency_ids` | `{int, ...}` | 货币类型 ID 列表，如 `{2, 3, 4}` |
| `local_player_id` | `integer` | 本地玩家 ID |
| `ui_fetch` | `function(pid, uuid)` → UI | 由 UUID 获取 UI 节点 |
| `get_item_config` | `function(id)` → table | 获取物品配置 `{icon, name, des, obtain}` |
| `get_currency_num` | `function(pid, cid)` → int | 获取货币数量 |

## 公开 API

| 方法 | 说明 |
|------|------|
| `M.setup(params)` | 初始化，传入参数 |
| `M.refresh_core_time(data)` | 刷新波次+倒计时 |
| `M.refresh_day_night()` | 刷新日夜状态 |
| `M.refresh_currency(currency_id?)` | 刷新货币（nil=全量） |
| `M.refresh_all_currency()` | 刷新全部货币 |
| `M.refresh_game_time(time_str)` | 刷新游戏时间显示 |
| `M.set_game_mode(mode_str)` | 设置游戏模式文本 |
| `M.set_settle_visible(visible)` | 结算按钮显隐 |
| `M.set_settle_active(is_active)` | 结算按钮激活态 |
| `M.refresh_jump_btn()` | 刷新跳字按钮图标 |
| `M.refresh_sfx_btn()` | 刷新特效按钮图标 |
| `M.refresh_camera_btn()` | 刷新相机按钮图标 |
| `M.is_inited()` | 是否已初始化 |

## 接入步骤

```lua
-- 1. require 模板
local TopInfo = require 'templates.b-hud-top-info'

-- 2. 准备 ui_fetch（已有项目通常封装好）
local function ui_fetch(playerId, uuid)
    return y3.ui.get_ui(playerId, uuid) -- 或使用 GamePlay.uiHelper
end

-- 3. 调用 setup
TopInfo.setup({
    local_player_id = localPlayerId,
    ui_fetch        = ui_fetch,
    currency_ids    = { 2, 3, 4 },
    ui_paths        = {
        game_mode  = "你的UUID",
        wave_title = "你的UUID",
        -- ... 其余按表格填入
    },
    resources = {
        day_img   = 134246395,
        night_img = 134258445,
        jump_on   = { 134250743, 134281839, 134235940, 134261708 },
        jump_off  = { 134242169, 134227384, 134252077, 134255095 },
        -- ... 其余按表格填入
    },
    callbacks = {
        on_settle_click  = function() -- 打开结算界面 end,
        on_setting_click = function(p) -- 打开设置 end,
        on_toggle_jump   = function(on) return not on end,
        is_jump_on       = function() return jumpSwitchOn end,
        is_day           = function() return currentIsDay end,
        show_tips        = function(data) -- 你的 tips 系统 end,
        hide_tips        = function() -- 隐藏 tips end,
        -- ... 其余按需
    },
    get_item_config  = function(id) return configMgr:getItemConfig().getById(id) end,
    get_currency_num = function(pid, cid) return y3.player(pid):getCurrencyNum(cid) end,
})

-- 4. 在游戏循环中调用
-- 每秒：TopInfo.refresh_game_time(formatTime(curSecond))
-- 波次变化：TopInfo.refresh_core_time({ title = "第3波", timeStr = "30s", endTime = ... })
-- 货币变化：TopInfo.refresh_currency(2)
-- 日夜切换：TopInfo.refresh_day_night()
```

## 已知限制

- `.upui` 导出时 `scene_ui_names` 过滤不生效，会附带全部 8 个场景 UI（wildMonster 等），导入后可手动清理
- 日夜动画为简化版（直接切图），源工程的 UIFrameTween 逐帧动画需融合侧自行实现
- 货币 hover Tips 展示依赖融合侧注入的 `show_tips` / `hide_tips` 回调
- 进度条动画（倒计时进度条）为立即设置版本，源工程的平滑动画需融合侧配合 y3.ltimer 实现
