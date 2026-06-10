# 通用结算面板模板

> **等级**：C
> 游戏结束后展示结算面板：胜负标题 + 1-4 名玩家战绩列表 + N 项奖励汇总 + 胜利/失败插屏。采用三层架构（DataSchema + Adapter + Pure Logic），复用方实现 Adapter 接口即可接入。

## 模板登记

### c-game-settle

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 通用结算面板模板 |
| 路径 | `.codemaker/templates/c-game-settle/` |
| 状态 | `validated` |
| 版本 | `v0.1.0` |
| 能力标签 | `settle`, `game-end`, `reward-summary`, `player-stats`, `result-screen` |
| 适用场景 | 任何需要「游戏结束 → 展示结算面板（玩家战绩 + 奖励汇总）」的项目。适合 1-4 人、PVE/PVP 通用 |
| 依赖 | `c-game-settle.upui`（结算面板 + 胜利/失败插屏 + 奖励元件） |
| UI 文件 | `c-game-settle.upui` |
| UI 根节点/资源 | `[HUD]SETTLE` 画板; `settle`(结算主面板), `GameWinPopup`(胜利插屏), `GameLosePopup`(失败插屏), `GameSettleRewardCmp`(奖励元件) |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter, params)` |
| 参数 | `adapter`（7 必填 + 4 可选方法），`params.ui`（10 个 UI **路径**，格式 `画板名.父节点.控件名`），`params.res`（可选资源 ID），`params.max_players`，`params.max_rewards` |
| 测试状态 | `tested` |
| 集成说明 | 需先实现 Adapter 接口（见下方），导入 `.upui`，然后 `M.setup(adapter, params)` → `M.show_settle(is_win)` / `M.show_win_splash()` / `M.show_lose_splash()`。**注意：`params.ui` 的值为 UI 路径（非 UUID），如 `"[HUD]SETTLE.settle"`**。**`get_player_summary` 返回的 player 数据必须包含 `level` 字段（整数），否则模板内部渲染出错。** |

### ⚠️ 回归靶场坑

| 坑 | 现象 | 修复 |
|----|------|------|
| player 数据缺 `level` 字段 | `attempt to concatenate a nil value (field 'level')` | `get_player_summary` 返回加 `level=1` |
| `.upui` 导入后画板名可能非 `[0]Settle` | UI not found | 用 `y3editor.get_ui_list` 确认实际画板名（本工程为 `[HUD]SETTLE`） |
| `reward` 数据缺 `level` 字段 | 同上 | `get_rewards` 返回加 `level=1` |
| **`bg.win` 和 `bg.lose` 同时显示** | 结算面板胜负背景图叠加 | 模板 `show()` 只换图不切 visible，**接入层必须手动控制**（见下方坑说明） |

---

## 数据契约 (DataSchema)

### SettleRewardData — 单条奖励数据

```lua
---@class SettleRewardData
---@field name     string   奖励名称
---@field icon     integer  图标资源 ID
---@field descr    string   描述文本（Tooltip 用）
---@field quantity integer  数量（0 表示不显示数量文本）
---@field quality  integer  品质等级 (1-6)，对应 params.res.quality_bg 的背景图
```

### SettlePlayerSummary — 单个玩家战绩摘要

```lua
---@class SettlePlayerSummary
---@field name       string    玩家名
---@field icon       integer   平台头像 ID
---@field is_local   boolean   是否本地玩家（true 时显示高亮色）
---@field power      integer   战力值
---@field level      integer   英雄等级
---@field kills      integer   击杀数
---@field bond_count integer   羁绊获得卡数
---@field hero_icons integer[] 吸收英雄图标列表（最多 10 个，不足补 nil）
```

---

## Adapter 接口

| 方法 | 签名 | 必填 | 说明 |
|------|------|------|------|
| `get_local_player_id` | `fun(): integer` | ✅ | 返回本地玩家 ID |
| `get_rewards` | `fun(player_id: integer): SettleRewardData[]` | ✅ | 返回玩家结算奖励列表（空表无奖励） |
| `get_player_summary` | `fun(player_id: integer): SettlePlayerSummary` | ✅ | 返回玩家战绩摘要 |
| `is_valid_slot` | `fun(slot_idx: integer): boolean` | ✅ | 槽位 1-4（玩家编号）是否有效（有玩家且存活） |
| `on_quit` | `fun(player_id: integer)` | ✅ | 退出游戏回调（失败时点击退出/胜利插屏关闭） |
| `on_continue` | `fun(player_id: integer)` | ✅ | 继续游戏回调（胜利时点击继续） |
| `on_show_tooltip` | `fun(reward: SettleRewardData, ui_element: UI)` | ✅ | 鼠标悬停奖励格子时显示 Tooltip |
| `on_hide_tooltip` | `fun()` | — | 鼠标移出时隐藏 Tooltip |
| `play_sfx` | `fun(name: string)` | — | 按钮音效钩子，`name` 为 `"Enter"` |
| `on_first_fold_anim` | `fun()` | — | 首次点击继续后的动画（如主面板伸缩） |
| `format_number` | `fun(n: integer): string` | — | 大数字格式化（默认：万/亿） |
| `on_settle_changed` | `fun(callback: fun()): function` | — | 订阅奖励变化通知；返回取消订阅函数。模板收到通知后自动刷新奖励列表 |

---

## 参数详述

### `params` 顶层

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `max_players` | integer | — | 4 | 玩家槽位数量 |
| `max_rewards` | integer | — | 32 | 奖励格子最大数量（超出自动扩展） |

### `params.ui` — UI 路径映射

> ⚠️ **路径格式**：使用 `y3.ui.get_ui(player, path)` 路径，格式为 `画板名.父节点.控件名`，**不是 UUID**。

| 参数 | 类型 | 必填 | 实际路径（c-game-settle.upui 导入后） |
|------|------|------|------|
| `settle_panel` | string | ✅ | `[HUD]SETTLE.settle` |
| `settle_quit_btn` | string | ✅ | `[HUD]SETTLE.settle.list_button.button_exit` |
| `settle_continue_btn` | string | ✅ | `[HUD]SETTLE.settle.list_button.button_continue` |
| `settle_player_list` | string | ✅ | `[HUD]SETTLE.settle.main.player_LIST` |
| `settle_reward_grid` | string | ✅ | `[HUD]SETTLE.settle.main.reward_GRID` |
| `settle_win_pic` | string | ✅ | `[HUD]SETTLE.settle.bg.win` |
| `win_panel` | string | ✅ | 胜利插屏面板路径（当前 .upui 中复用 settle.bg.win） |
| `win_close_btn` | string | ✅ | 胜利插屏关闭按钮路径 |
| `lose_panel` | string | ✅ | 失败插屏面板路径 |
| `lose_close_btn` | string | ✅ | 失败插屏关闭按钮路径 |
| `colors.local_player` | string | — | `"#ffb165"` 本地玩家名颜色 |
| `colors.other_player` | string | — | `"#dbc1a9"` 其他玩家名颜色 |

### `params.res` — 资源 ID

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `win_img` | integer | — | 134223062 | 胜利标题图资源 ID |
| `lose_img` | integer | — | 134243407 | 失败标题图资源 ID |
| `empty_icon` | integer | — | 999 | 空白占位图标 ID |
| `quality_bg` | table | — | — | 品质→背景图映射 `{[1]=id, [2]=id, ...}` |

---

## 测试用 MockAdapter

```lua
local MockAdapter = {
    get_local_player_id = function() return 1 end,

    get_rewards = function(player_id)
        return {
            { name = "金币",   icon = 100001, descr = "通用货币", quantity = 500,  quality = 1 },
            { name = "神剑",   icon = 100002, descr = "传说武器", quantity = 1,    quality = 5 },
            { name = "经验药", icon = 100003, descr = "提升等级", quantity = 3,    quality = 2 },
        }
    end,

    get_player_summary = function(player_id)
        return {
            name       = "玩家" .. player_id,
            icon       = 0,
            is_local   = (player_id == 1),
            power      = 15000 + player_id * 1000,
            level      = 30 + player_id,
            kills      = 120 + player_id * 10,
            bond_count = 8 + player_id,
            hero_icons = { 200001, 200002, 200003 },
        }
    end,

    is_valid_slot = function(slot_idx) return slot_idx <= 2 end,

    on_quit     = function(pid) y3.player(pid):exit_game() end,
    on_continue = function(pid) print("玩家" .. pid .. " 继续游戏") end,

    on_show_tooltip = function(reward, ui_el)
        print(string.format("[Tooltip] %s x%d (品质%d)", reward.name, reward.quantity, reward.quality))
    end,

    on_hide_tooltip = function() end,
}
```

---

## 接入步骤

### 前置：环境准备

> 此步骤只需做一次，项目内所有模板共用。

```bash
# 在 maps/EntryMap/script/ 目录下创建软链接，让 Lua require 能找到模板
cd maps/EntryMap/script
mklink /J codemaker ..\..\..\codemaker
```

> **为什么需要软链接？**  
> Y3 Lua 的 `require` 只搜索 `script/` 和 `global_script/`，而模板放在 `.codemaker/templates/`。  
> 通过软链接将 `codemaker` 映射到 `.codemaker`，即可用 `require('codemaker.templates.xxx.logic')` 引入。

### 导入 UI

```
编辑器 → y3editor.import_ui(".codemaker/templates/c-game-settle/c-game-settle.upui")
```

导入后 UI 列表中出现 `[HUD]SETTLE` 画板即成功。

### Lua 代码接入

```lua
-- 1. 引入模板（script/ 目录下需有 codemaker 软链接指向 .codemaker）
local GameSettle = require('codemaker.templates.c-game-settle.logic')

-- 2. 实现 Adapter（参考上方 MockAdapter，替换为项目实际逻辑）
local MyAdapter = {
    get_local_player_id = function() return GamePlay.gameApp:getLocalPlayerId() end,
    get_rewards         = function(pid) return GamePlay.gameSettleMgr:getPlayerReward(pid) end,
    get_player_summary  = function(pid) ... end,
    is_valid_slot       = function(slot) ... end,
    on_quit             = function(pid) y3.player(pid):exit_game() end,
    on_continue         = function(pid) ... end,
    on_show_tooltip     = function(reward, ui_el) GamePlay.uiMgr:showTips(...) end,
    on_hide_tooltip     = function() GamePlay.uiMgr:hideTips(...) end,
    play_sfx            = function(name) GamePlay.audioMgr:bindUIEffect(...) end,
    on_settle_changed   = function(cb)
        local sub = GamePlay.gameEventMgr:Subscribe(GamePlay.localEventConst.Player.SettleChange, cb)
        return function() GamePlay.gameEventMgr:Unsubscribe(sub) end
    end,
}

-- 3. 准备 UI 路径参数（路径格式 "画板名.父节点.控件名"，非 UUID）
local ui_params = {
    settle_panel        = "[HUD]SETTLE.settle",
    settle_quit_btn     = "[HUD]SETTLE.settle.list_button.button_exit",
    settle_continue_btn = "[HUD]SETTLE.settle.list_button.button_continue",
    settle_player_list  = "[HUD]SETTLE.settle.main.player_LIST",
    settle_reward_grid  = "[HUD]SETTLE.settle.main.reward_GRID",
    settle_win_pic      = "[HUD]SETTLE.settle.bg.win",
    win_panel           = "[HUD]SETTLE.settle.bg.win",   -- 复用，如有独立插屏面板替换为实际路径
    win_close_btn       = "[HUD]SETTLE.settle.bg.win",
    lose_panel          = "[HUD]SETTLE.settle.bg.win",
    lose_close_btn      = "[HUD]SETTLE.settle.bg.win",
}

-- 4. 初始化
GameSettle.setup(MyAdapter, { ui = ui_params, max_players = 4, max_rewards = 32 })

-- 5. 游戏结束时调用
GameSettle.show_settle(true)   -- 胜利结算（玩家列表 + 奖励网格 + 继续按钮）
GameSettle.show_settle(false)  -- 失败结算（玩家列表 + 奖励网格 + 退出按钮）

-- 6. 单独使用插屏
GameSettle.show_win_splash()   -- 胜利插屏
GameSettle.show_lose_splash()  -- 失败插屏

-- 7. 销毁（取消事件订阅）
GameSettle.destroy()
```

---

## ⚠️ 接入避坑指南

### 坑：`bg.win` 和 `bg.lose` 同时显示（高频踩坑）

| 现象 | 结算面板显示时，胜利背景图和失败背景图叠加在一起 |
|------|------|
| 根因 | 模板内 `show(is_win)` 仅调用 `win_pic:set_image(...)` 切换标题图，**没有控制 `bg.win` / `bg.lose` 的 `set_visible`**；两张背景图默认都可见 |
| 影响 | `M.show_settle(true)` 时 `bg.win` 和 `bg.lose` 同时显示 |

**必须在接入层手动控制**，在 `M.show_settle()` 之后立即补充：

```lua
function M.show_settle(is_win)
    GameSettle.show_settle(is_win)

    -- ⚠️ 模板 show() 只换图，不切 visible，必须手动互斥
    local player  = y3.player.get_by_id(1)
    local bg_win  = y3.ui.get_ui(player, "[HUD]SETTLE.settle.bg.win")
    local bg_lose = y3.ui.get_ui(player, "[HUD]SETTLE.settle.bg.lose")
    if bg_win  then bg_win:set_visible(is_win == true)  end
    if bg_lose then bg_lose:set_visible(is_win ~= true) end
end
```

---

## 已知限制 & Known Issues

### 当前版本限制（v0.1.0）

| # | 描述 | 影响 | 处理建议 |
|---|------|------|----------|
| 1 | **奖励格子为空** | `reward_GRID` 是 GridView（type_25），子节点需通过元件实例化，当前 `get_child('n')` 方式无效 | 需调整 `create_reward_cmp` 改用 `GridView` 动态创建子元件 API |
| 2 | **失败时标题仍显示 VICTORY** | 失败标题图 `lose_img=134243407` **未打包到 CliCliExport/editor_icon/**，导入后资源不存在，`set_image` 静默失败保留胜利图 | 在 `CliCliExport/editor_icon/` 补充 `editor_icon134243407.zip`，或重新从编辑器导出完整 `.upui` |
| 3 | **`params.ui` 不支持 UUID** | `y3.ui.get_ui` 只接受路径字符串，不接受 UUID | 始终使用路径格式（见上方参数表） |

### 通用限制

- **不包含**奖励数据的记录/聚合逻辑（`GameSettleMgr:record()`），由 Adapter 的 `get_rewards()` 承担
- **不包含**结算按钮（HUD 上的小按钮），仅包含结算面板本体；触发入口由复用方自行实现
- 玩家列表固定读取 1-4 槽位（`params.max_players`）；不支持动态添加槽位
- 奖励网格默认 32 个槽位，超出自动扩展（`create_reward_cmp`），但 UI 元件的预制体必须提前存在
- 音效、动态图飞行动画、埋点上报为可选功能，需通过 Adapter 注入
- `scene_ui_names` 过滤不生效 → 导入 `.upui` 后可能残留无关 Scene UI，需手工清理

---

## 源工程溯源

- 源模块：`global_script/gamePlay/ui/hudPopup/gameSettle/`（6 文件） + `global_script/gamePlay/manager/GameSettleMgr.lua`
- 导出日期：2026-05-27
- 导出工具：`y3-template-export`
- 实战验证：2026-06-02 agentmap 联调（发现并修复 bg.win/bg.lose 同时显示问题）
