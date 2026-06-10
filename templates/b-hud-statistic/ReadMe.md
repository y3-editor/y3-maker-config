# HUD 右侧统计面板模板

> **等级**：B
> 战斗 HUD 右侧统计面板，展示玩家列表、多页伤害/击杀/承伤排行、技能伤害分布。

## 模板登记

### b-hud-statistic

| 字段 | 内容 |
|------|------|
| 等级 | **B** |
| 名称 | HUD 右侧统计面板模板 |
| 路径 | `.codemaker/templates/b-hud-statistic/` |
| 状态 | `validated` |
| 版本 | `v0.1.1` |
| 能力标签 | `HUD`, `统计`, `伤害排行`, `技能统计`, `DPS` |
| 适用场景 | 需要伤害统计面板的战斗/塔防/生存类地图，展示玩家之间伤害/击杀/承伤排行和技能分布 |
| 依赖 | `Statistic` 画板；`StatisticTeamCmp`、`DamageCmp` 元件；图标资源 |
| UI 文件 | `b-hud-statistic.upui` |
| UI 根节点/资源 | 画板 `Statistic`；元件 `StatisticTeamCmp`、`DamageCmp`；图标见 `resources` 参数 |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(params)` |
| 参数 | `ui_paths`, `local_player_id`, `ui_fetch`, `player_ids`, `get_platform_icon`, `get_player_name`, `get_ability_info`, `resources`, `callbacks` |
| 测试状态 | `validated in EntryMap, 2026-06-04, passed` |
| 集成说明 | 先导入 `b-hud-statistic.upui`，再由 `y3-lua-pipeline` 将 `logic.lua` 融合 |

## ⚠️ 集成经验（2026-06-04 验证）

| 问题 | 根因 | 解决 |
|------|------|------|
| 技能类型未搜全 | `get_ability_by_slot` 需遍历英雄/命令/普通三种类型 | 全部搜索后去重 |
| 伤害槽子节点路径 | 子节点需 `get_child('mask.avatar_IMG')` 等层级路径 | 从 `player_LIST.1` 开始取 |

## 功能

1. **伤害排行** — 按总伤害排序，显示玩家头像/名称/伤害值/占比进度条
2. **BOSS 秒伤** — BOSS 战 DPS 排行
3. **击杀计数** — 玩家击杀数排行
4. **技能分布** — 展开查看各技能伤害占比+施放次数
5. **面板折叠** — 点击按钮展开/收起伤害面板和技能详情
6. **手动刷新** — 融合侧每帧/定时调用 `M.refresh()` 或 `M.refresh_if_dirty()`

## 参数详述

### `params.ui_paths`（必填）

| 键 | 说明 |
|----|------|
| `root` | 统计面板根节点 UUID |
| `damage_btn` | 伤害面板按钮 UUID |
| `ability_btn` | 技能详情按钮 UUID |
| `ability_bg` | 技能详情背景 UUID |
| `ability_view` | 技能列表父节点 UUID |
| `team_parent` | 玩家列表父节点 UUID |
| `damage_parent` | 伤害排行父节点 UUID |
| `page_btns` | 翻页按钮列表 `{ {btn=..., txt=...}, ... }` |

### `params.resources`（可选）

| 键 | 说明 |
|----|------|
| `damage_btn_on` | 伤害面板展开时四态图标 |
| `damage_btn_off` | 伤害面板收起时四态图标 |
| `page_l_sel` | 左按钮选中四态图标 |
| `page_l_default` | 左按钮默认四态图标 |
| `page_r_sel` | 右按钮选中四态图标 |
| `page_r_default` | 右按钮默认四态图标 |
| `rank_bg` | 排名底色（按玩家 1-4） |

### `params.callbacks`（可选）

| 回调 | 说明 |
|------|------|
| `on_bind_audio` | 绑定按钮音效 |
| `on_damage_update` | 伤害更新外部通知 |

### 其他必填参数

| 参数 | 说明 |
|------|------|
| `local_player_id` | 本地玩家 ID |
| `ui_fetch` | `function(pid, uuid) → UI` |
| `player_ids` | 所有玩家 ID 列表 |
| `get_platform_icon` | `function(pid) → icon_id` |
| `get_player_name` | `function(pid) → name` |
| `get_ability_info` | `function(aid) → {icon, name}` 可选 |

## 公开 API

| 方法 | 说明 |
|------|------|
| `M.setup(params)` | 初始化 |
| `M.add_damage(src_pid, tgt_pid, val, ability_id?)` | 累加伤害 |
| `M.add_kill(src_pid)` | 累加击杀 |
| `M.add_ability_cast(pid, aid)` | 记录技能施放 |
| `M.set_boss_dps(pid, dps)` | 设置 BOSS DPS |
| `M.reset_all()` | 重置全部数据 |
| `M.refresh()` | 强制刷新 UI |
| `M.refresh_if_dirty()` | 仅脏数据时刷新 |
| `M.toggle_damage_panel()` | 切换伤害面板 |
| `M.toggle_ability_panel()` | 切换技能面板 |
| `M.switch_page(page)` | 切换页签 |
| `M.is_inited()` | 是否已初始化 |

## 接入步骤

```lua
local StatPanel = require 'templates.b-hud-statistic'

StatPanel.setup({
    local_player_id  = localPlayerId,
    player_ids       = { 1, 2, 3, 4 },
    ui_fetch         = function(pid, uuid) return y3.ui.get_ui(pid, uuid) end,
    get_platform_icon = function(pid) return y3.player(pid):get_platform_icon() end,
    get_player_name   = function(pid) return y3.player(pid):get_name() end,
    get_ability_info  = function(aid)
        return { icon = y3.ability.get_icon_by_key(aid), name = y3.ability.get_name_by_key(aid) }
    end,
    ui_paths = {
        root = "你的UUID",
        -- ...
    },
    resources = {
        rank_bg = { 134243886, 134230175, 134259407, 134227373 },
        -- ...
    },
})

-- 游戏事件中推送数据
y3.game:event_on('伤害-结算后', function(trg, damage)
    local src = damage.source:get_owner():get_id()
    local tgt = damage.target:get_owner():get_id()
    local val = damage:getFinalValue()
    StatPanel.add_damage(src, tgt, val, damage.ability and damage.ability:get_key())
end)

-- 定期刷新
y3.ltimer.loop(0.3, function() StatPanel.refresh_if_dirty() end)
```

## 已知限制

- `.upui` 导出时 `scene_ui_names` 过滤不生效，含额外场景 UI
- 技能面板槽位假设 UI 中已预置 30 个子节点
- BOSS DPS 数据需融合侧自行计算后通过 `set_boss_dps` 传入
- 页码文本颜色切换依赖融合侧提供 `set_text_color_hex`
