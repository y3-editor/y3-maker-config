# 二次确认弹窗模板

> **等级**：A
> 通用 DoubleCheck 二次确认弹窗：显示标题、内容、确认/取消按钮，并在点击后调用业务回调。

## 模板登记

### a-double-check-dialog

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 二次确认弹窗模板 |
| 路径 | `.codex/templates/a-double-check-dialog/` |
| 状态 | `validated` |
| 版本 | `v1.0.1` |
| 能力标签 | `ui`, `dialog`, `confirm`, `double-check`, `popup` |
| 适用场景 | 删除、退出、购买、解锁、分解等高风险操作前，需要弹出标题 + 内容 + 确认/取消回调的二次确认界面。 |
| 依赖 | Y3 原生 API：`y3.ui_prefab.create`, `y3.ui.get_ui`; 导入 `.upui` 后提供 `DoubleCheck` Prefab 与 `[0]DoubleCheck` 挂载画板 |
| UI 文件 | `a-double-check-dialog.upui` |
| UI 根节点/资源 | `[0]DoubleCheck`(Layer, UID `101b8f3a-0177-4bcc-b38f-59ada6bfd3c9`); `DoubleCheck`(Prefab, UID `ea35c113-4e25-4944-8f83-a4346915adfa`) |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `prefab_name`, `ui_path`, `parent_ui`, `get_parent_ui`, `player`, `get_player`, `bind_ui_effect`, `on_error`, `paths`, `auto_remove` |
| 测试状态 | `validated in agentmap, 2026-05-27, passed` |
| 集成说明 | 先导入 `.upui`，再由 `y3-lua-pipeline` 将 `logic.lua` 融合到对应模块；初始化时调用 `M.setup({...})`，业务触发点调用 `M.show(title, content, on_confirm, on_cancel)` |

## 内置资源

| 资源 | UID | 说明 |
|------|-----|------|
| `[0]DoubleCheck` | `101b8f3a-0177-4bcc-b38f-59ada6bfd3c9` | 自动创建的空画板，默认作为弹窗 Prefab 挂载父节点。 |
| `DoubleCheck` | `ea35c113-4e25-4944-8f83-a4346915adfa` | 二次确认弹窗 Prefab，含全屏遮罩、居中面板、标题、内容、确认/取消按钮。 |

Prefab 节点路径：

```text
DoubleCheck
├── mask
└── root
    ├── bg
    ├── title
    │   ├── bg
    │   └── title_TEXT
    ├── content_TEXT
    └── control
        ├── confirm_BTN
        │   └── title_TEXT
        └── cancel_BTN
            └── title_TEXT
```

## 参数详述

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `prefab_name` | `string` | 否 | `DoubleCheck` | 导入 `.upui` 后的 Prefab 名；若项目按 UID 创建，也可传 `ea35c113-4e25-4944-8f83-a4346915adfa`。 |
| `ui_path` | `string` | 否 | `[0]DoubleCheck` | 默认父 UI 路径；如果传入 `parent_ui` 或 `get_parent_ui`，则不读取该路径。 |
| `parent_ui` | `UI` | 否 | — | 直接指定弹窗挂载父节点。 |
| `get_parent_ui` | `fun(player, options): UI` | 否 | — | 动态返回弹窗挂载父节点。 |
| `player` | `Player` | 否 | `y3.player.get_local()` | 创建本地弹窗的玩家对象。 |
| `get_player` | `fun(): Player` | 否 | — | 动态返回玩家对象；优先级低于 `player`/`options.player`。 |
| `bind_ui_effect` | `fun(ui:UI)` | 否 | — | 可注入按钮音效绑定，例如 `function(btn) AudioMgr.bind(btn) end`。 |
| `on_error` | `fun(message:string)` | 否 | — | 创建失败时的错误钩子；钩子后仍会抛出错误。 |
| `paths` | `table` | 否 | 见 `logic.lua` | 覆盖标题、内容、确认按钮、取消按钮节点路径。 |
| `auto_remove` | `boolean` | 否 | `true` | 点击确认/取消并执行回调后是否自动移除弹窗。 |

## 公开 API

| API | 说明 |
|-----|------|
| `M.setup(params)` | 初始化模板参数，可重复调用覆盖配置。 |
| `M.show(title, content, on_confirm, on_cancel, options)` | 创建并显示弹窗，返回 `Dialog` 句柄。 |
| `Dialog:remove()` | 手动移除弹窗。 |
| `Dialog:get_root()` | 获取弹窗根 UI。 |
| `Dialog:get_prefab()` | 获取 `UIPrefab` 实例。 |
| `Dialog:set_title(title)` / `Dialog:set_content(content)` | 动态更新文案。 |
| `M.close_all()` | 关闭所有由本模板创建且仍活动的弹窗。 |
| `M.get_active_count()` | 返回当前活动弹窗数量。 |


## 接入注意

### show 成功但不显示

如果按键/按钮日志已触发，`M.get_active_count()` 也大于 0，但画面没有弹窗，优先检查可见性。

常见原因：`DoubleCheck` Prefab 顶层 `visible=false`。

处理方式：

1. 确认 `maps/EntryMap/ui/prefab/DoubleCheck.json` 顶层 `data.visible=true`。
2. 融合 `logic.lua` 时保留兜底：

```lua
local root = prefab:get_child()
if root.set_visible then
    root:set_visible(true)
end
```

验证方式：

```lua
local dialog = DoubleCheck.show('测试', 'visible 验证', function() end)
print(dialog:get_root():is_visible())
print(dialog:get_root():is_real_visible())
print(DoubleCheck.get_active_count())
```

期望：`true`、`true`、`1`。

改过 UI JSON 后，需要重启游戏/地图；只热重载 Lua 不一定生效。

## 接入步骤

1. **导入 UI**：`y3editor.import_ui("<abs>/a-double-check-dialog.upui")`。
2. **融合 Lua**：由 `y3-game-spec` 调用 `y3-lua-pipeline` 把 `logic.lua` 融合到目标模块。
3. **初始化**：
   ```lua
   local DoubleCheck = require('logic')
   DoubleCheck.setup({
       -- 默认使用导入的 [0]DoubleCheck 画板；如需挂到业务画板可传 parent_ui/get_parent_ui
       bind_ui_effect = function(btn)
           -- 可选：接入项目自己的 UI 音效系统
       end,
   })
   ```
4. **显示弹窗**：
   ```lua
   DoubleCheck.show(
       '确认删除',
       '该操作不可撤销，是否继续？',
       function(local_player, dialog)
           -- 确认逻辑
       end,
       function(local_player, dialog)
           -- 取消逻辑，可省略
       end
   )
   ```
5. **回归验证**：进入游戏后触发弹窗，检查标题/内容显示、确认回调、取消回调、点击后移除、按钮音效（如注入）。

## 已知限制

- 本模板只提供通用弹窗和本地 UI 点击绑定，不包含任何删除/购买/退出等业务逻辑。
- 默认用 `y3.player.get_local()` 创建本地弹窗；多人或同步业务中，确认回调内如需改同步状态，应由接入方自行发送同步事件。
- 默认挂载到随模板导入的 `[0]DoubleCheck` 空画板；若目标项目不希望新增画板，可传入业务侧 `parent_ui` 或 `get_parent_ui`。
- `.upui` 由源工程 UI JSON 精确打包为目标 Prefab + 空挂载画板；未通过在线 UI 编辑器重新导出，导入后建议在编辑器中目视检查一次资源显示。


## 变更记录

### v1.0.1 (2026-06-02)

- 记录 Prefab 顶层 `visible=false` 导致弹窗创建成功但不可见的问题。
- 在模板逻辑中补充 `root:set_visible(true)` 兜底。

### v1.0.0 (2026-05-27)

- 初始 validated 版本。

## 源工程溯源

- 源模块：`DM42/global_script/gamePlay/ui/DoubleCheck.lua`
- 源依赖：`DM42/global_script/gamePlay/ui/DyncComponent.lua`（已改写为模板内自包含创建逻辑）
- 源 UI：`DM42/maps/EntryMap/ui/prefab/DoubleCheck.json` + `DM42/maps/EntryMap/ui/[0]DoubleCheck.json`
- 导出日期：`2026-05-26`
- 验证记录：`validated in agentmap, 2026-05-27, passed`
- 导出工具：`y3-template-export`
