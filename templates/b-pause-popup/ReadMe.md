# 暂停弹窗模板 (b-pause-popup)

> **等级**：B
> 通用游戏暂停弹窗：显示暂停发起者信息 + 剩余暂停次数 + 继续/退出按钮，支持单人/多人模式区分。
>
> ✅ **本模板现在有两种接入方式**：
> - `M.setup()`：只复用原始 `[0]PAUSE` UI，暂停/恢复由项目自己的 PauseMgr 管。
> - `M.setup_controller()`：在 UI 基础上内置软暂停/恢复、暂停者、次数管理、P/F8 同步按键和“继续游戏”按钮联动。
>
> 因此，如果你想要“按键后真正暂停游戏”，请接入 `M.setup_controller()`，不要只调用 `M.setup()`。

## 模板登记

### b-pause-popup

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | 暂停弹窗模板 |
| 路径 | `.codex/templates/b-pause-popup/` |
| 状态 | `validated` |
| 版本 | `v0.1.9` |
| 能力标签 | `pause-menu`, `popup`, `multiplayer-aware`, `ui-popup` |
| 适用场景 | 任何需要"按 ESC/暂停按钮 弹出暂停面板"的项目，PVE/PVP 通用，单/多人模式自动适配 |
| 依赖 | `y3.ui.get_ui`, `y3.player`, `y3.game.enable_soft_pause`, `y3.game.resume_soft_pause`；默认使用导入后的 `[0]PAUSE` 完整路径 |
| UI 文件 | `b-pause-popup.upui` |
| UI 根节点/资源 | **画板 `[0]PAUSE`**（Layer）；子控件：`titleTEXT`（UID `025678e8-...`）、`titleSubTEXT`（UID `17d0a659-...`）、`continueBTN`（UID `8de30855-...`）、`exitBTN`（UID `28ba431f-...`）。导出含 92 个依赖元件 + 8 个 scene_ui |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)`（纯 UI 组件） / `M.setup_controller(params)`（暂停控制器） |
| 参数 | `setup`: `ui_paths?`, `on_continue`, `get_pause_player_id`, `get_pause_times`, `get_player_num` 等；`setup_controller`: 增加 `auto_bind_keys?`, `keys?`, `key_event?`, `max_pause_times?`, `pause_impl?`, `resume_impl?`, `request_resume?`, `sync_continue_button?`, `sync_id?`, `can_pause?`, `consume_pause_time?` 等 |
| 测试状态 | `runtime-validated in EntryMap, 2026-06-09：原 [0]PAUSE UI，set_visible 显隐；setup_controller 软暂停/恢复接入；request_resume 单机同步回环通过；多开继续按钮问题已按 y3.sync.send 修复，仍建议目标项目做多开回归` |
| 集成说明 | 先导入 `.upui` 到目标地图（UI 编辑器 → 导入）；只要 UI 用 `M.setup()`，需要内置软暂停/恢复则用 `M.setup_controller()` |

---

## 参数详述

### 必填参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `on_continue` | `fun()` | 点击“继续游戏”按钮时触发，调用方需调对应解除暂停逻辑，并按业务需要调用 `instance:hide()` |
| `get_pause_player_id` | `fun():integer` | 返回当前暂停发起者玩家 ID |
| `get_pause_times` | `fun(player_id):integer` | 返回该玩家剩余可暂停次数 |
| `get_player_num` | `fun():integer` | 返回当前在场玩家数（用于区分单/多人模式） |

### 可选参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `ui_paths.root` | string | `[0]PAUSE` | UI Layer 路径；默认匹配模板 `.upui` 导入后的完整节点树 |
| `ui_paths.root_node` | string | `[0]PAUSE.root` | 根容器路径，用于显隐兜底 |
| `ui_paths.mask` | string | `[0]PAUSE.root.bg` | 遮罩路径，用于显隐兜底 |
| `ui_paths.panel` | string | `[0]PAUSE.root.pause` | 面板容器路径，用于显隐兜底 |
| `ui_paths.title` | string | `[0]PAUSE.root.pause.content.title_TEXT` | 暂停信息文本（显示“游戏已被 X 暂停”） |
| `ui_paths.title_sub` | string | `[0]PAUSE.root.pause.content.titleSub_TEXT` | 副标题文本（显示剩余次数/等待提示） |
| `ui_paths.continue_btn` | string | `[0]PAUSE.root.pause.control.gameContinue_BTN` | 继续游戏按钮 |
| `ui_paths.continue_text` | string | `[0]PAUSE.root.pause.control.gameContinue_BTN.title_TEXT` | 继续按钮文字；模板会关闭其操作拦截，避免盖住按钮 |
| `ui_paths.exit_btn` | string | `[0]PAUSE.root.pause.control.gameExit_BTN` | 退出按钮 |
| `ui_paths.exit_text` | string | `[0]PAUSE.root.pause.control.gameExit_BTN.title_TEXT` | 退出按钮文字；模板会关闭其操作拦截，避免盖住按钮 |
| `visible_paths` | string[] | root/root_node/mask/panel | `show()`/`hide()` 批量 `set_visible` 的节点；不建议包含文本/按钮，除非导入后被单独隐藏 |
| `get_local_player_id` | `fun():integer` | `y3.player.get_local():get_id()` | 返回本机玩家 ID |
| `on_exit` | `fun()` | nil | 点击“退出游戏”按钮时触发；未提供时默认隐藏弹窗 |
| `show_exit_button` | boolean | `false` | 非暂停者是否显示退出按钮；原 UI 中继续/退出按钮同位置，模板不会同时显示两者 |
| `get_player_name` | `fun(pid):string` | `y3.player(pid):get_name()` | 自定义玩家名解析 |
| `bind_ui_effect` | `fun(ui_node)` | nil | 按钮音效绑定回调 |
| `colors.GREEN` | string | `#7fff7f` | 绿色文本（高亮玩家名/剩余次数 > 0） |
| `colors.RED` | string | `#ff7f7f` | 红色文本（剩余次数 = 0） |
| `texts.paused_by` | string | `游戏已被 %s%s#E 暂停` | 主标题模板（参数：颜色、玩家名） |
| `texts.unlimited_pauses` | string | `单人模式下不限次数` | 单人模式副标题 |
| `texts.remaining_pauses` | string | `你还剩 %s%d#E 次暂停权限` | 多人模式剩余次数模板 |
| `texts.waiting_resume` | string | `请等待暂停玩家继续游戏` | 等待提示 |
| `skip_ui_config_check` | boolean | `false` | 跳过模板初始化时的路径/透明度排查提示 |

### 显隐约定

模板显隐只使用 `UI:set_visible(true/false)`，**不使用 `UI:set_alpha()` 控制显隐**。如果 `visible=true` 但画面不可见，优先检查导入后的 UI JSON：

```text
maps/EntryMap/ui/[0]PAUSE.json
  [0]PAUSE.opacity      应为 1.0
  [0]PAUSE.root.bg.opacity 如存在，也应为 1.0
```

不要用 `set_alpha(255)` 在 Lua 里掩盖 JSON 配置问题；应修正 UI JSON 或重新导入正确模板。

## 暂停控制器入口：`M.setup_controller(params)`

`M.setup()` 只负责 UI 组件；`M.setup_controller()` 是完整功能入口，额外提供软暂停/恢复、暂停者、次数管理、按键绑定和弹窗联动。

### 控制器参数

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `auto_bind_keys` | boolean | `false` | 是否自动绑定测试按键 |
| `keys` | string[] | `{ 'P', 'F8' }` | 自动绑定的暂停/恢复按键 |
| `key_event` | string | `键盘-按下` | 自动绑定使用的按键事件；默认用同步键盘事件，避免本地事件直接修改游戏同步状态 |
| `max_pause_times` | integer | `3` | 多人模式下每名玩家默认可暂停次数 |
| `pause_times` | table | `{}` | 外部传入的玩家次数表；未提供时控制器内部维护 |
| `unlimited_single_player` | boolean | `true` | 单人模式是否不限暂停次数 |
| `allow_any_player_resume` | boolean | `false` | 是否允许非暂停者恢复 |
| `pause_impl` | `fun(pid, controller)` | `y3.game.enable_soft_pause()` | 自定义暂停实现 |
| `resume_impl` | `fun(pid, controller)` | `y3.game.resume_soft_pause()` | 自定义恢复实现 |
| `request_resume` | `fun(pid, controller)` | nil | 自定义“继续游戏”按钮恢复请求；用于接入项目 PauseMgr |
| `sync_continue_button` | boolean | `true` | 默认将本地 UI 继续按钮点击通过 `y3.sync.send` 同步给所有客户端后再恢复/隐藏 |
| `sync_id` | string | `b-pause-popup:resume` | 继续按钮同步消息 ID；多实例时建议自定义避免冲突 |
| `can_pause` | `fun(pid, controller):boolean` | 按次数判断 | 自定义是否允许暂停 |
| `consume_pause_time` | `fun(pid, controller)` | 内部次数 -1 | 自定义扣减次数；如果传了外部 `get_pause_times`，建议同时传它 |
| `on_pause` | `fun(pid, controller)` | nil | 暂停后回调 |
| `on_resume` | `fun(pid, controller)` | nil | 恢复后回调 |
| `popup_params` | table | nil | 传给内部 `M.setup()` 的 UI 参数；不传则复用当前参数 |

### 控制器 API

| 方法 | 说明 |
|------|------|
| `controller:pause(pid?)` | 执行软暂停、扣次数、显示弹窗 |
| `controller:resume(pid?)` | 执行恢复、隐藏弹窗；适合同步事件中调用 |
| `controller:request_resume(pid?)` | 发送恢复请求；默认用 `y3.sync.send` 广播，供本地 UI 按钮/测试调用 |
| `controller:toggle(pid?)` | 暂停/恢复切换，内置 0.15 秒去抖 |
| `controller:is_paused()` | 当前是否处于暂停状态 |
| `controller:get_popup()` | 获取内部 UI instance |
| `controller:get_pause_player_id()` | 获取当前暂停者 |
| `controller:get_pause_times(pid)` | 获取剩余暂停次数 |
| `controller:bind_keys(keys?)` | 手动绑定暂停/恢复按键 |

### 最小功能接入

```lua
local PausePopupTpl = require 'template.b-pause-popup.logic'

local pause_controller = PausePopupTpl.setup_controller({
    auto_bind_keys = true,
    keys = { 'P', 'F8' },
    max_pause_times = 3,
})

-- 也可以由自己的按钮/事件调用
-- pause_controller:pause()
-- pause_controller:resume()
```

## 实例 API

`M.setup(params)` 返回的 instance 含以下方法：

| 方法 | 说明 |
|------|------|
| `instance:show()` | 显示暂停弹窗（首次自动初始化 + refresh） |
| `instance:hide()` | 隐藏暂停弹窗 |
| `instance:refresh()` | 刷新副标题/按钮可见性（暂停者变化时调用） |
| `instance:is_show()` | 查询当前是否显示中 |

---

## 触发入口集成指引（复用方必读）

如果使用 `M.setup_controller()`，模板会处理软暂停/恢复、次数、默认 P/F8 同步按键和继续按钮；如果只使用 `M.setup()`，以下职责仍由复用方自行实现：

| 职责 | 复用方需做的事 |
|------|---------------|
| **按键/按钮触发暂停** | `setup_controller(auto_bind_keys=true)` 会自动绑定默认同步 `键盘-按下`，并使用事件里的 `data.player` 作为暂停/恢复发起者；纯 UI 模式下才需要项目自己监听 ESC/P/F8 或按钮 |
| **暂停状态同步** | 默认按键入口使用同步 `键盘-按下`；继续按钮是本地 UI 事件，模板默认通过 `y3.sync.send` 同步恢复请求；其他本地 UI/异步入口应由项目 PauseMgr 或 `y3.sync.send` 先同步后再调用暂停/恢复 |
| **暂停状态变化时显示/隐藏弹窗** | `setup_controller()` 会自动联动；纯 UI 模式下在暂停事件回调里调 `instance:show()`，恢复时调 `instance:hide()` |
| **次数上限管理** | `setup_controller()` 可内部维护；纯 UI 或外部 PauseMgr 模式下由 `get_pause_times(pid)` 回调暴露给模板 |
| **系统菜单（如 `[0]System`）** | 本模板**不**包含 ESC 呼出的系统菜单画板，需复用方自己实现 |

### 推荐入口骨架

```lua
-- 1. 初始化暂停弹窗模板（一次性）
local PausePopupTpl = require 'template.b-pause-popup.logic'
local pause_popup = PausePopupTpl.setup({
    ui_paths = { ... },  -- 见下方"集成示例"
    get_local_player_id = function() return y3.player.get_local():get_id() end,
    get_pause_player_id = function() return MyPauseMgr.pause_pid end,
    get_pause_times     = function(pid) return MyPauseMgr.times[pid] or 0 end,
    get_player_num      = function() return #MyPauseMgr.players end,
    on_continue         = function() MyPauseMgr:request_resume() end,
})

-- 2. ESC 监听 + 系统菜单（复用方实现，本模板不提供）
y3.game.event_on('键盘-按下', function(_, _, player, key)
    if key == y3.const.KeyboardKey['KEY_ESCAPE'] then
        SystemMenu:toggle(player)  -- 由复用方实现
    end
end)

-- 3. 系统菜单的"暂停游戏"按钮回调（复用方实现）
function SystemMenu:on_click_pause_btn()
    local pid = y3.player.get_local():get_id()
    if MyPauseMgr.times[pid] <= 0 and MyPauseMgr.player_num > 1 then
        return  -- 次数耗尽
    end
    MyPauseMgr:request_pause(pid)  -- 内部广播给所有客户端
end

-- 4. 暂停事件分发：所有客户端收到后弹出本模板
MyPauseMgr:on_pause_changed(function(is_paused, pause_pid)
    if is_paused then
        pause_popup:show()
    else
        pause_popup:hide()
    end
end)
```

---

## 集成示例

### 推荐：使用内置暂停控制器

```lua
local PausePopupTpl = require 'template.b-pause-popup.logic'

local pause_controller = PausePopupTpl.setup_controller({
    -- ui_paths 可省略；默认匹配 b-pause-popup.upui 导入后的 [0]PAUSE 完整节点树。
    auto_bind_keys = true,
    keys = { 'P', 'F8' },
    max_pause_times = 3,
    unlimited_single_player = true,
    allow_any_player_resume = false,
    on_pause = function(pid, ctrl)
        print('paused by', pid, 'remain', ctrl:get_pause_times(pid))
    end,
    on_resume = function(pid)
        print('resumed by', pid)
    end,
})
```

### 只复用 UI：外部 PauseMgr 自己控制暂停

```lua
local PausePopupTpl = require 'template.b-pause-popup.logic'

local pause_popup
pause_popup = PausePopupTpl.setup({
    get_pause_player_id = function() return GameMgr:get_pause_player_id() end,
    get_pause_times     = function(pid) return GameMgr:get_pause_times(pid) end,
    get_player_num      = function() return GameMgr:get_player_num() end,
    on_continue         = function()
        GameMgr:resume()
        pause_popup:hide()
    end,
    show_exit_button    = false,
})

GameMgr:on_pause_changed(function(is_paused)
    if is_paused then
        pause_popup:show()
    else
        pause_popup:hide()
    end
end)
```

## 已知限制

1. **`.upui` 体积约 8MB**：导出完整 `[0]PAUSE` 画板，含 92 个依赖元件（图标/图片资源等）。正常。
2. **`.upui` 含 8 个 scene_ui 元数据**：`export_ui` 的 `scene_ui_names` 过滤参数当前不生效，无法精确剔除，约 500KB 元数据；不影响功能。
3. **退出按钮**：默认沿用源工程行为隐藏退出按钮。原 UI 中“继续游戏”和“退出游戏”按钮同位置，模板默认不会同时显示两者；`show_exit_button = true` 时仅非暂停者显示退出按钮，点击行为由 `on_exit` 提供，未提供 `on_exit` 时点击只隐藏弹窗。
4. **子控件路径**：默认路径为 `[0]PAUSE.root.pause.content.title_TEXT` 等完整层级。导入后必须用 `ui_tree/[0]PAUSE_Tree.json` 或 `get_ui_canvas("[0]PAUSE")` 核对；如节点命名不同，需在 `params.ui_paths` 修正。
5. **触发入口可选**：`M.setup()` 仍是不带业务的纯 UI 入口；`M.setup_controller()` 已内置软暂停/恢复、次数管理和可选按键绑定。默认按键事件为同步 `键盘-按下`，并以事件参数 `data.player` 作为暂停者；继续按钮因 `UI:add_local_event` 是本地事件，模板默认用 `y3.sync.send` 广播恢复请求后让所有客户端一起 `resume()/hide()`。系统菜单等更复杂业务仍建议接入项目自己的 PauseMgr。
6. **不含系统菜单画板**：源工程的 `[0]System` 画板不在本模板内，复用方需自行设计或导入系统菜单 UI。
7. **API 兼容性**：模板使用 `y3.ui.get_ui(player, path)` 获取 UI 节点，使用 `UI:set_visible` 控制显隐，使用 `UI:add_local_event` 绑定按钮点击。目标项目若使用不同 UI API，融合时需适配。

---

## 集成踩坑记录（EntryMap 实测）

> 以下为 2026-05-25 在 EntryMap 项目中实际集成测试时遇到的问题及解决方案，供后续复用方参考。

### 坑 1：`[0]` Layer 面板需要 `create_layer` 激活

**现象**：`y3.ui.get_ui(player, '[0]PAUSE')` 报 `UI "[0]PAUSE" 不存在`。

**原因**：`[0]` 前缀的 Layer 型面板不会自动对玩家可见，需显式调用 `GameAPI.create_layer` 激活。

**解决**：
```lua
local pause_uid = 'b9af7398-d83b-4610-80d6-3177d077b1e9'  -- [0]PAUSE 的 UID
GameAPI.create_layer(y3.player.get_local().handle, pause_uid)
```

> 调用 `create_layer` 后 `get_ui` 才能找到该 Layer 及其子节点。延迟 1 帧再初始化模板更稳妥。

### 坑 2：`.upui` 导入后节点层级可能与源工程不同

**现象**：模板默认路径 `[0]PAUSE.title_TEXT` 报不存在，实际节点树为 `[0]PAUSE.root.pause.title.title_TEXT`。

**原因**：`.upui` 导出保留了源工程的完整节点树（含 `root` → `pause` 中间容器），目标地图导入后层级不变。

**解决**：导入 `.upui` 后，务必用 `helper.get_ui_canvas("[0]PAUSE", depth=5)` 查看实际节点树，修正 `params.ui_paths`。

**EntryMap 实际路径**（y3-helper get_ui_canvas 输出）：
```
[0]PAUSE
  root
    pause
      title / title_TEXT        → 静态标签（不要用）
      content / title_TEXT      → **暂停信息文本（用这个）**
      content / titleSub_TEXT   → 副标题文本
      control / gameContinue_BTN → 继续按钮
      control / gameExit_BTN     → 退出按钮
```

对应 `ui_paths`（注意 title 指向 content 下的 title_TEXT！）：
```lua
ui_paths = {
    root         = '[0]PAUSE',
    title        = '[0]PAUSE.root.pause.content.title_TEXT',
    title_sub    = '[0]PAUSE.root.pause.content.titleSub_TEXT',
    continue_btn = '[0]PAUSE.root.pause.control.gameContinue_BTN',
    exit_btn     = '[0]PAUSE.root.pause.control.gameExit_BTN',
}
```

### 坑 3：只接 `M.setup()` 会只有 UI，没有真实暂停

**现象**：P/F8 或按钮能显示 `[0]PAUSE`，但游戏逻辑没有暂停。

**原因**：`M.setup()` 是保留给项目自有 PauseMgr 的纯 UI 入口；它只刷新文案、按钮和显隐，不会调用 `enable_soft_pause()`。

**解决**：

- 需要模板自带暂停/恢复：使用 `M.setup_controller()`。
- 项目已有 PauseMgr：继续用 `M.setup()`，但必须由 PauseMgr 在同步暂停事件里调用 `instance:show()` / `instance:hide()`。

```lua
local PausePopupTpl = include 'templates.b_pause_popup.logic'

local controller = PausePopupTpl.setup_controller({
    auto_bind_keys = true,
    keys = { 'P', 'F8' },
    max_pause_times = 3,
})
```

`setup_controller()` 默认会调用：

```lua
y3.game.enable_soft_pause()
y3.game.resume_soft_pause()
```

### 坑 4：多实例共享 params 导致状态污染（v0.1.1 已修复）

**现象**：多实例之间 `colors`/`texts` 等参数互相覆盖。

**原因**：`params` 是模块级 table，`M.setup()` 用 `for k,v in pairs(user_params) do params[k]=v end` 直接覆盖。

**修复**：v0.1.1 改为每次 `setup()` 创建独立 `p` 副本，内部函数通过闭包捕获。

### 坑 5：`visible=true` 但画面不可见，优先检查 JSON opacity

**现象**：`set_visible(true)` 后日志正常，`is_real_visible()` 也为 true，但画面没有弹窗。

**原因**：导入/保存过程中 UI JSON 可能出现透明度为 0，例如：

```text
[0]PAUSE.opacity = 0.0
[0]PAUSE.root.bg.opacity = 0.0
```

这会让 UI 即使可见也完全透明。

**解决**：修正 `maps/EntryMap/ui/[0]PAUSE.json` 中相关 `opacity` 为 `1.0`，重新生成 UI 树并重启/热更。不要用 `ui:set_alpha(255)` 作为显隐逻辑的补丁。

```bash
python3 .codex/skills/y3-ui-pipeline/gen_ui_tree.py .
```

### 坑 6：不要用 `set_alpha` 控制弹窗显隐

**错误做法**：

```lua
ui:set_visible(true)
ui:set_alpha(255)
ui:set_alpha(0)
```

**推荐做法**：

```lua
ui:set_visible(true)
ui:set_visible(false)
```

`UI:set_alpha()` 的语义是“不透明度”，不是业务显隐状态；滥用会导致状态判断、点击拦截和后续维护混乱。

### 坑 7：调试日志叠字可能被误判为 UI 文本

开发模式下 `print` 可能显示在游戏画面上。截图中出现的白色日志文字不代表 UI TextLabel 已渲染。验证 UI 时应结合：

1. 截图中的面板/按钮是否出现；
2. `get_ui_canvas` 是否有目标节点；
3. 暂时减少日志输出，避免遮挡 UI。

### 坑 8：初始化/按键事件可能重复，测试入口要幂等/去抖

EntryMap 测试中出现过 `游戏-初始化` / 日志重复输出。若测试入口重复绑定按键，按一次 P/F8 可能执行两次 toggle，表现为“按了没反应”。

**建议**：

```lua
if _G.__pause_popup_key_bound then return end
_G.__pause_popup_key_bound = true

local last_toggle_time = -999
y3.game:event('键盘-按下', 'P', function()
    local now = os.clock()
    if now - last_toggle_time < 0.15 then return end
    last_toggle_time = now
    -- toggle
end)
```

### 坑 9：继续按钮是本地 UI 事件，不能只在点击者客户端恢复

**现象**：多开时，点击“继续游戏”后只有点击者的 `[0]PAUSE` 消失，其他玩家 UI 仍然显示。

**原因**：`UI:add_local_event('左键-点击', ...)` 不会同步到其他玩家。按钮回调里直接 `controller:resume()` 只会在点击者客户端执行。

**解决**：v0.1.8 起，`setup_controller()` 默认将继续按钮处理为同步恢复请求：

```lua
y3.sync.send('b-pause-popup:resume', { action = 'resume', pid = pid })
y3.sync.onSync('b-pause-popup:resume', function(data, source)
    controller:resume(source:get_id())
end)
```

复用方如果已有 PauseMgr，可以覆盖：

```lua
PausePopupTpl.setup_controller({
    request_resume = function(pid, controller)
        MyPauseMgr:request_resume(pid)
    end,
})
```

### 坑 10：多人按键入口必须使用触发玩家，不要用本机玩家

**现象**：多人时每个客户端都可能把暂停者判断成自己，导致“谁能继续”“剩余次数”显示错乱。

**原因**：同步 `键盘-按下` 事件回调里如果使用 `y3.player.get_local()`，每个客户端拿到的是不同本机玩家，而不是按键触发者。

**解决**：v0.1.7 起，默认按键绑定使用事件参数 `data.player`：

```lua
y3.game:event('键盘-按下', 'P', function(_, data)
    local pid = data.player:get_id()
    controller:toggle(pid)
end)
```

### 坑 11：不要为了恢复按键改成本地按键事件

**现象**：软暂停后担心同步按键事件不推进，于是把 P/F8 改为 `本地-键盘-按下`。

**风险**：本地按键事件直接调用暂停/恢复会改变同步状态，存在多人不同步风险。

**解决**：默认仍使用同步 `键盘-按下`。如果项目确实要从本地输入发起请求，应先 `y3.sync.send`，再在 `onSync` 中统一调用暂停/恢复。

---

### 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v0.1.0 | — | 初始导出 |
| v0.1.1 | 2026-05-25 | 修复：`y3.ui.fetch`→`y3.ui.get_ui`（标准 API）；修复：多实例共享 params 状态污染 Bug |
| v0.1.2 | 2026-05-26 | 新增「集成踩坑记录」章节；EntryMap 实测：`create_layer` 激活 + 子控件路径修正 + 暂停逻辑接入 |
| v0.1.3 | 2026-06-08 | EntryMap 复测迭代：默认路径改为真实 `[0]PAUSE.root.pause...` 层级；显隐只用 `set_visible`；新增 JSON `opacity=0` 排查；新增按键去抖/重复初始化建议；新增 `on_exit` / `show_exit_button` / `visible_paths` |
| v0.1.9 | 2026-06-09 | 根据集成问题复盘整理代码/文档：明确 `setup()` 与 `setup_controller()` 边界、补充多人本地 UI 同步坑、让 `controller:request_resume()` 返回请求结果，更新测试清单 |
| v0.1.8 | 2026-06-09 | 继续按钮从本地直接 `resume()` 改为默认 `y3.sync.send` 广播恢复请求，修复多开时只有点击者 UI 消失的问题；新增 `request_resume` / `sync_continue_button` / `sync_id` |
| v0.1.7 | 2026-06-09 | 多人按键路径改为使用同步事件参数 `data.player` 作为暂停/恢复发起者，避免多人时误用各客户端本机玩家 ID |
| v0.1.6 | 2026-06-09 | 将控制器默认按键事件恢复为同步 `键盘-按下`，避免本地按键事件直接修改游戏同步状态；保留 `key_event` 作为高级覆盖项 |
| v0.1.5 | 2026-06-09 | 短暂尝试本地按键恢复软暂停；后续因同步风险在 v0.1.6 改回同步按键事件 |
| v0.1.4 | 2026-06-09 | 新增 `M.setup_controller()` 功能入口：内置 `enable_soft_pause` / `resume_soft_pause`、暂停者、次数管理、按键绑定与弹窗联动；保留 `M.setup()` 纯 UI 模式 |

---

## 测试要点（升级到 validated 前需覆盖）

- [x] 单人模式：暂停后副标题显示"单人模式下不限次数"
- [x] 多人模式且本机为暂停者：显示剩余次数（绿色 > 0 / 红色 = 0）
- [x] 多人模式且本机非暂停者：显示"请等待暂停玩家继续游戏"，继续按钮隐藏
- [x] 点击继续按钮：触发 `on_continue` 回调
- [x] `controller:request_resume()`：单机同步回环触发 `y3.sync.send` → `onSync` → `resume()`
- [x] `bind_ui_effect` 为 nil 时不报错
- [x] `colors`/`texts` 自定义可正常覆盖
- [x] `instance:show()` 后调 `instance:hide()` 后再 `show()`：状态正确
- [x] 多实例隔离：不同 `setup()` 创建的实例互不干扰（v0.1.1 修复）
- [ ] 多开回归：点击继续按钮后所有玩家 `[0]PAUSE` 同时隐藏（v0.1.8 已按 `y3.sync.send` 修复，目标项目仍需多开验证）
