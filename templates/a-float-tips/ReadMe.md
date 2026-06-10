# 浮动文本提示 (Float Tips)

> **等级**：A  
> 在指定位置生成浮动文本，向上飘移并渐隐消失。适用于伤害数字、金币获取、状态提示等弹字场景。  
> **v0.2.0** 起由 y3-ui-pipeline 自动导入 UI 元件，无需手动操作 `.upui`。

## 模板登记

### a-float-tips

| 字段 | 内容 |
|------|------|
| 等级 | **A** |
| 名称 | 浮动文本提示 |
| 路径 | `.codemaker/templates/a-float-tips/` |
| 状态 | `validated` |
| 版本 | `v0.2.0` |
| 能力标签 | `浮动提示`, `弹字`, `渐隐动画`, `伤害数字` |
| 适用场景 | 任何需要在指定位置显示临时文本并自动消失的场景，如伤害数字、金币获取提示、状态变化提示等 |
| 依赖 | `y3.ui_prefab.create`（父节点 UI 必传），需开启 `y3.config.sync.mouse = true` |
| UI 文件 | —（v0.2.0 起纯 Lua，UI 元件由 y3-ui-pipeline 自动创建） |
| UI 根节点/资源 | `FloatTips` 元件; `_title_TEXT` 文本控件 |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.float_text(params)` |
| 参数 | `player` (必填), `text` (必填), `root_ui` (必填), `pos_x?`, `pos_y?`, `duration?`, `prefab_id?`, `text_child?` |
| 测试状态 | `tested, 2026-05-29, EntryMap 5/5 scenarios passed` |
| 集成说明 | y3-ui-pipeline 自动导入 `.upui` → y3-lua-pipeline 融合 `logic.lua` → 调用方传入 `root_ui`（如 HUD 画板）即可使用 |

---

## 参数详述

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `player` | userdata | ✅ | — | 目标玩家对象，需支持 `get_mouse_pos_x/y`、`get_mouse_ui_x_percent` |
| `text` | string | ✅ | — | 显示的文本内容 |
| `root_ui` | UI | ✅ | — | 挂载的父节点 UI（`y3.ui_prefab.create` 强制要求父节点） |
| `pos_x` | number | ❌ | 鼠标 X | 起始 X 坐标（绝对像素） |
| `pos_y` | number | ❌ | 鼠标 Y | 起始 Y 坐标（绝对像素） |
| `duration` | number | ❌ | `1` | 总持续时间（秒） |
| `prefab_id` | string | ❌ | FloatTips UUID | 元件 UUID，可替换为自定义样式 |
| `text_child` | string | ❌ | `'_title_TEXT'` | 文本子节点名 |

## 动画时间线

以默认 `duration=1` 为例：

```
t=0     创建元件，锚点自适应（鼠标左半屏=左锚点，右半屏=右锚点）
t=0.2   开始向上飘移 100px (set_anim_pos)
t=0.5   开始淡出 (opacity 100→0)
t=1.0   元件销毁 (remove)
```

## 使用示例

```lua
-- 前置：用 y3.ui.get_ui 获取挂载的父节点
local root_ui = y3.ui.get_ui(local_player, '[HUD]HUD')  -- 或其他画板

-- 伤害数字（跟在鼠标位置）
FloatTips.float_text({
    player  = local_player,
    text    = '暴击 -999',
    root_ui = root_ui,
})

-- 固定位置弹字
FloatTips.float_text({
    player   = local_player,
    text     = '+100金币',
    root_ui  = root_ui,
    pos_x    = 800,
    pos_y    = 400,
    duration = 1.5,
})

-- 自定义元件样式
FloatTips.float_text({
    player    = local_player,
    text      = 'MISS',
    root_ui   = root_ui,
    prefab_id = 'your-custom-prefab-uuid',
    text_child = 'custom_text_node',
})
```

## 已知限制

- 依赖 `y3.ui_prefab.create` 创建元件，**必须传 root_ui**（v0.2.0 起已强制要求）
- 使用 `player:get_mouse_pos_x/y` 获取鼠标位置，需开启 `y3.config.sync.mouse = true`
- `.upui` 文件由 y3-ui-pipeline 自动导入，用户无需手动操作
- 动画使用 `y3.ltimer.wait`，注意计时器在 map unload 后自动清理
- 不处理大量弹字的合并/去重（需要时由调用方在 `float_text` 外层控制频率）
