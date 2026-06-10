# 难度选择模板（difficulty-select）

多人安全的模式/难度选择 + 准备投票 + 倒计时进入游戏模板。

## 模板登记

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 难度选择模板 |
| 路径 | `.codemaker/templates/difficulty-select/` |
| 状态 | `validated` |
| 文档版本 | `v1.1.1` |
| Lua 版本 | `logic.lua v0.3.0` |
| 能力标签 | `level-select`, `difficulty`, `mode-select`, `multiplayer-ready`, `countdown-start` |
| 适用场景 | 选择玩法模式/难度后进入游戏；支持单人和多人大厅 |
| UI 文件 | `difficulty-select.upui` |
| UI 根节点/资源 | `[2]Menu_Main`; `MenuStartLevelCmp`(Prefab) |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 当前验证项目 | `空地图模板 - difficulty-select`, 2026-06-04, passed；`agentmap`, 2026-06-02, passed |

## 当前行为

### 模式/难度

- 房主权威：只有 `host_player_id` 对应玩家能修改模式/难度。
- UI 点击不直接改权威状态，只发送 `y3.sync` 请求；状态只在 `onSync` handler 内应用。
- 非房主点击模式/难度会被拒绝并输出诊断日志。
- 支持 `params.modes` 预注册多模式，例如：
  - 普通模式：`N1-N10`
  - 占位关卡名：`N1-N5`
- 运行期禁止直接 `setLevels()` 绕过同步；应使用 `params.modes + requestModeSelect()`。

### 单人/多人开始按钮

- 当前在线真实玩家数 `<= 1`：按钮显示 `开始游戏`。
- 当前在线真实玩家数 `> 1`：按钮显示 `准备(x/n)`。
- 玩家准备后刷新按钮和左下角玩家状态。

### 多人准备与倒计时

- “当前在线真实玩家”使用 `Player:is_alive()`，即 PLAYING + USER。
- 多数阈值：`floor(real_online_count / 2) + 1`。
- 多数准备达成后：先进入倒计时。
- 倒计时到 `0` 后：触发 `StartGame` / `GameEnter`，并关闭大厅面板。

## 参数详述

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `levels` | `table` | 是 | — | 默认模式关卡配置列表，格式 `{id, name, open, info, des}`；`open=1` 为截止行 |
| `modes` | `table` | 否 | `nil` | 模式表：`{ [key] = { key, name, levels, player_records } }` |
| `host_player_id` | `integer` | 是 | — | 房主玩家 ID |
| `ui_paths` | `table` | 是 | — | UI 路径配置，至少含 `panel`, `level_list`, `start_btn`；多人列表需 `player_list` |
| `countdown_seconds` | `integer` | 否 | `5` | 多数准备后的倒计时秒数 |
| `fsm_game_class` | `string` | 否 | `nil` | `GameEnter` 事件携带 |
| `fsm_stage_class` | `string` | 否 | `nil` | `GameEnter` 事件携带 |
| `player_records` | `table` | 否 | `{}` | 解锁记录 `{[sub]=passCount}` |
| `mode_key` | `string` | 否 | `''` | 初始模式 key |
| `mode_name` | `string` | 否 | `''` | 初始模式显示名 |

### UI 路径示例

```lua
local UI_PATHS = {
    panel = '[2]Menu_Main',
    level_list = '[2]Menu_Main.root.Content.1_start_LAYOUT.Content.level.level.gameMode_1_LIST',
    start_btn = '[2]Menu_Main.root.Content.1_start_LAYOUT.Content.level.control.gameStart_BTN',
    level_title = '[2]Menu_Main.root.Content.1_start_LAYOUT.Content.level.level.title.title_TEXT',
    player_list = '[2]Menu_Main.root.Content.1_start_LAYOUT.Content.player_LIST',
    normal_mode_card = '[2]Menu_Main.root.Content.1_start_LAYOUT.Content.mode.mode_LIST.1',
    idle_mode_card = '[2]Menu_Main.root.Content.1_start_LAYOUT.Content.mode.mode_LIST.2',
    placeholder_mode_card = '[2]Menu_Main.root.Content.1_start_LAYOUT.Content.mode.mode_LIST.3',
}
```

## 事件

使用 `M.on(event_name, callback)` 监听。

| 事件 | 触发时机 | 关键字段 |
|------|----------|----------|
| `LevelsChanged` | 模式/难度表同步应用后 | `mode_key`, `mode_name`, `count`, `first_config_id`, `reason` |
| `LevelSelected` | 当前难度变更后 | `mode_key`, `mode_name`, `config_id`, `sub`, `name` |
| `ReadyChanged` | 玩家准备票变化后 | `player_id`, `ready`, `ready_count`, `total`, `threshold` |
| `Countdown` | 多数准备达成后立即触发一次，然后每秒触发 | `remaining`, `total`, `mode_key`, `mode_name`, `config_id`, `sub` |
| `StartGame` | 倒计时到 0 后 | `mode_key`, `mode_name`, `config_id`, `sub`, `ready`, `total`, `threshold` |
| `GameEnter` | `StartGame` 后立即触发 | `mode_key`, `mode_name`, `config_id`, `sub`, `fsm_game_class`, `fsm_stage_class` |

## 公开 API

| API | 说明 |
|-----|------|
| `setup(params)` | 初始化模板 |
| `createLevelUI()` | 创建/刷新难度卡片和按钮/玩家列表文案 |
| `requestModeSelect(mode_key, config_id, mode_name?)` | 发送同步模式/难度选择请求 |
| `requestSelectLevel(config_id)` / `selectLevel(config_id)` | 发送同步难度选择请求 |
| `requestReady(ready)` / `startGame()` | 发送准备请求；多数达成后开始倒计时 |
| `getMode()` | 返回 `mode_key, mode_name` |
| `getSelectedLevel()` / `getSelectedSub()` | 返回当前 configId / sub |
| `getLevelStates()` | 返回当前难度列表渲染状态 |
| `getReadySummary()` | 返回 `{ready,total,threshold,started,button_text}` |
| `getStartButtonText()` | 返回当前按钮文案 |
| `refreshPlayerListUI()` / `refreshStartButtonUI()` | 手动刷新列表/按钮 |
| `resetStartState()` | 重置开始/准备状态 |
| `recordPass(sub, count?)` | 更新通关记录 |

> `_debugApplyMode`, `_debugSetReady`, `_debugStartCountdownIfReady` 仅供测试/调试，不应在正式流程中作为玩家输入入口。

## 接入示例

```lua
local difficulty_select = require 'templates.difficulty_select.logic'

local function build_levels(prefix, count)
    local levels = {}
    for i = 1, count do
        levels[i] = { id = i, name = prefix .. i, open = 0, info = '', des = '' }
    end
    return levels
end

local NORMAL = build_levels('N', 10)
local PLACEHOLDER = build_levels('N', 5)

difficulty_select.setup({
    levels = NORMAL,
    modes = {
        normal = { key = 'normal', name = '普通模式', levels = NORMAL, player_records = {} },
        placeholder = { key = 'placeholder', name = '占位关卡名', levels = PLACEHOLDER, player_records = {} },
    },
    host_player_id = 1,
    countdown_seconds = 3,
    ui_paths = UI_PATHS,
    mode_key = 'normal',
    mode_name = '普通模式',
})

difficulty_select.on('GameEnter', function(data)
    print(('enter game mode=%s config_id=%s sub=%s'):format(data.mode_key, data.config_id, data.sub))
end)

y3.game:event('游戏-初始化', function()
    -- 基础要求：至少延迟 1 帧，确保 UI 已初始化。
    y3.ltimer.wait_frame(1, function()
        difficulty_select.createLevelUI()
    end)
end)
```

> agentmap 旧分支实测：如果开发期 `.rr` / `quick_restart` 后出现旧 prefab 残留、难度卡片翻倍，可把 `createLevelUI()` 延迟到 `wait_frame(3)` 再调用，并确认只保留一个入口初始化该模块。

## 接入注意事项 / 回归靶场坑

1. UI 路径必须带完整画板前缀，如 `[2]Menu_Main.root...`。
2. `MenuStartLevelCmp` 必须按元件名称创建，不要传 UID。
3. `createLevelUI()` 需要在 UI 初始化后调用，推荐 `游戏-初始化` 后延迟至少 1 帧。
4. 多人模式不要直接运行期 `setLevels()`，该 API 在 setup 后会返回 `false`。
5. 若要支持模式切换，先在 `params.modes` 中预注册，再通过 `requestModeSelect()` 发同步请求。
6. `StartGame` 不是准备达成瞬间触发，而是倒计时到 0 后触发。
7. 不要在两处 include/require 同一入口模块并各自调用 `setup()` / `createLevelUI()`，否则会创建双倍卡片。
8. 按钮三态图片不要在代码中硬改为源工程资源 ID；当前版本只改标题文字颜色，悬停/按下样式交给 UI 编辑器配置。
9. 若 `.rr` / `quick_restart` 后 `gameMode_1_LIST` 卡片翻倍，优先检查：
   - 是否重复入口初始化；
   - 是否过早调用 `createLevelUI()`；
   - 可临时改为 `wait_frame(3)` 后创建 UI。
10. 不需要解锁判定时，所有难度配置 `open=0`，`player_records={}` 即可。

## 回归验证记录

| 日期 | 项目 | 结果 | 覆盖点 |
|------|------|------|--------|
| 2026-05-14 | TemplateTestMap | ✅ passed | 原单模式模板 |
| 2026-05-26 | agentmap（难度选择） | ✅ passed | 原模板复用与按钮状态图绕过 |
| 2026-06-02 | agentmap（结算+难度选择联调） | ✅ passed | 修复按钮三态覆盖、stale 节点累积、双模块冲突三个问题 |
| 2026-06-04 | 空地图模板 - difficulty-select | ✅ passed | 多模式 N1-N10/N1-N5、房主同步、非房主只读、多数准备、倒计时后 StartGame/GameEnter、单人/多人按钮文案 |

## 源工程溯源

- 源模块：`global_script/gamePlay/ui/menu/MenuStartGame/standalone_mode_difficulty.lua`
- 初始导出日期：`2025-05-14`
- 当前多人迭代：`2026-06-04`
