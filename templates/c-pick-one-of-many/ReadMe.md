# 通用多选一抽卡模板

> **等级**：C
> 通用「N 选 1」随机抽卡骨架——加权随机池 → 抽 N 张 → 弹窗展示 → 玩家选择/刷新/放弃 → 业务回调。适用场景：羁绊卡牌抽取、神器三选一、法宝升级、商店盲盒等任何"随机出N个让玩家挑1个"的玩法。

## 模板登记

### c-pick-one-of-many

| 字段 | 内容 |
|------|------|
| 等级 | **C** |
| 名称 | 通用多选一抽卡模板 |
| 路径 | `templates/c-pick-one-of-many/` |
| 状态 | `validated` |
| 版本 | `v1.0.0` |
| 能力标签 | `pick-one-of-many`, `random-pick`, `card-select`, `slot-pick`, `weighted-random` |
| 适用场景 | 需要实现「加权随机池 → 展示 N 张供玩家挑选 1 张 → 选中/刷新/放弃 → 继续队列」的抽卡类玩法。 |
| 依赖 | — |
| UI 文件 | —（纯 Lua 模板，Adapter 全权负责 UI 渲染） |
| UI 根节点/资源 | —（参见「接入步骤」中的 Prefab 创建示例） |
| Lua 入口 | `logic.lua` |
| 入口签名 | `M.setup(adapter)` |
| 参数 | `get_pool`, `get_pick_count`, `can_pick`, `consume_cost`, `open_popup`, `close_popup`, `on_picked`, `on_skipped`, `on_refresh_requested`, `on_pool_empty` |
| 测试状态 | `validated in test321321, 2026-05-22, passed (39/39)` |
| 集成说明 | 需先实现 Adapter 接口（见 §Adapter 接口），然后 `M.setup(adapter)` → 在触发点调 `M.try_pick(player_id)` |

> 注意：本模板为**纯 Lua 模板**，不提供 `.upui`。UI 渲染逻辑由 Adapter 的 `open_popup`/`close_popup` 全权负责。Adapter 内部可自由选择 Prefab，下方「内置资源」提供了源工程使用的 `artifactPickCmp` Prefab UID 作为参考。

---

## 内置资源

| 资源 | UID | 说明 |
|------|-----|------|
| `artifactPickCmp` (Prefab) | `b862c4f7-4a2d-49c6-9742-49035c48f988` | 极简卡槽参考：bg(按钮) + descr_TEXT(文本)，3 张品质背景图(`134247399`/`134254375`/`134246865`)。复用方可直接 `y3.ui_prefab.create(player, UID, parent)` 后绑定到 Adapter.open_popup |

参考节点树：
```
root
├── bg (按钮，点击区域)
│   └── descr_TEXT (文本，选择项描述)
```

接口约定：
- 点击 `bg` → 调 `M.confirm_pick(player_id, slot)`
- 刷新按钮（如有）→ 调 `M.refresh_pick(player_id)`
- 放弃按钮（如有）→ 调 `M.skip_pick(player_id)`
- UI 中根据 `info.can_refresh` / `info.can_skip` 控制按钮显隐

---

## 数据契约 (DataSchema)

```lua
--- @class PickPoolItem  抽卡池中的单个条目
--- @field id        integer  唯一标识（模板不读取内容，透传给 Adapter 回调）
--- @field weight    integer  权重 (>0)
--- @field group?    string   分组标签（同一 group 内最多抽出 1 张，为空则不限制）
--- @field data?     any      业务自定义透传字段（模板不读取）

--- @class PickResult  抽卡结果中的单张
--- @field item   PickPoolItem  抽中的条目
--- @field slot   integer  展示槽位 (1 .. pick_count)

--- @class PickPopupInfo  传给 Adapter.open_popup 的上下文
--- @field can_refresh  boolean  是否允许刷新
--- @field can_skip     boolean  是否允许放弃
--- @field pick_count   integer  本次展示数量
--- @field pick_serial  integer  本局第几次抽卡（从 1 开始）
```

---

## Adapter 接口

| 方法 | 签名 | 必填 | 说明 |
|------|------|------|------|
| `get_pool` | `fun(pid:integer): PickPoolItem[]` | ✅ | 返回当前可抽卡池（含权重）。权重为 0 的条目会被自动过滤 |
| `get_pick_count` | `fun(pid:integer): integer` | ✅ | 一次抽几张（≥1） |
| `can_pick` | `fun(pid:integer): boolean, string?` | ✅ | 是否允许抽卡。`false` 时第二个返回值为 UI 提示文字 |
| `consume_cost` | `fun(pid:integer): boolean` | ✅ | 扣费。`true`=成功扣费，`false`=余额不足（模板不做提示） |
| `open_popup` | `fun(pid, results, info)` | ✅ | 打开选择 UI。`results:PickResult[]`, `info:PickPopupInfo` |
| `close_popup` | `fun(pid)` | ✅ | 关闭选择 UI |
| `on_picked` | `fun(pid, item:PickPoolItem)` | ✅ | 玩家选中后的业务回调（发放奖励等） |
| `on_skipped` | `fun(pid)` | ✅ | 玩家放弃后的业务回调（退还货币等） |
| `on_refresh_requested` | `fun(pid): boolean` | ✅ | 用户点刷新。`true`=允许刷新（模板会重新随机），`false`=拒绝 |
| `on_pool_empty` | `fun(pid)` | ✅ | 卡池为空时的通知（卡池空但被调用 try_pick） |

| 方法 | 签名 | 必填 | 说明 |
|------|------|------|------|
| `on_pick_rejected` | `fun(pid, reason:string)` | — | 抽卡被拒时的 UI 提示钩子 |
| `random_fn` | `fun(): float` | — | 自定义随机数生成器（默认 `math.random`，单测可注入 seed） |
| `log` | `fun(msg:string)` | — | 日志钩子（默认 `print`） |

---

## 测试用 MockAdapter

```lua
local MockAdapter = {
    _pool = {
        { id = 1, weight = 30, data = { name = '力量符文', icon = 12345 } },
        { id = 2, weight = 20, data = { name = '敏捷符文', icon = 12346 } },
        { id = 3, weight = 10, data = { name = '智力符文', icon = 12347 } },
        { id = 4, weight = 40, data = { name = '通用符文', icon = 12348 } },
    },

    get_pool = function(self, pid)
        return self._pool
    end,

    get_pick_count = function(pid) return 3 end,

    can_pick = function(pid)
        -- 模拟：每次抽卡间隔 3 秒
        local last = (self._last_pick_time or {})[pid] or 0
        if os.time() - last < 3 then
            return false, '冷却中'
        end
        return true
    end,

    consume_cost = function(self, pid)
        self._last_pick_time = self._last_pick_time or {}
        self._last_pick_time[pid] = os.time()
        return true
    end,

    open_popup = function(pid, results, info)
        print(string.format('=== 抽卡 #%d（%d 张）===', info.pick_serial, info.pick_count))
        for i, r in ipairs(results) do
            print(string.format('  [%d] id=%d %s', r.slot, r.item.id, (r.item.data or {}).name or ''))
        end
        print('  刷新=' .. tostring(info.can_refresh) .. ' 放弃=' .. tostring(info.can_skip))
        -- 自动选择第一张（演示用）
        print('  → 自动选择 slot 1')
        PickOneOfMany.confirm_pick(pid, 1)
    end,

    close_popup = function(pid) end,

    on_picked = function(pid, item)
        print(string.format('  奖励发放: id=%d', item.id))
    end,

    on_skipped = function(pid)
        print(string.format('  玩家放弃, 退还货币'))
    end,

    on_refresh_requested = function(pid)
        return true  -- 允许刷新
    end,

    on_pool_empty = function(pid)
        print('  卡池已空！')
    end,
}

PickOneOfMany = require('templates.c-pick-one-of-many.logic')
PickOneOfMany.setup(MockAdapter)
PickOneOfMany.try_pick(1)
```

---

## 接入步骤

1. **融合 Lua**：由 `y3-game-spec` 调用 `y3-lua-pipeline` 把 `logic.lua` 融合到目标模块
2. **实现 Adapter**：创建 Adapter 表，实现 10 个必填方法（参考 §测试用 MockAdapter）
3. **初始化**：
   ```lua
   PickTpl.setup(your_adapter)
   ```
4. **缓存 parent 节点**（`open_popup` 需要一个 UI 节点作为 Prefab 挂载容器）：
   ```lua
   -- ⚠️ 必须延迟 1 帧，游戏-初始化同帧调用 y3.ui.get_ui 会失败
   -- ⚠️ 路径格式为 "layer名.节点名"，不能直接传节点 UID
   y3.game:event('游戏-初始化', function()
       y3.player.with_local(function(player)
           y3.ltimer.wait_frame(1, function()
               cached_panel = y3.ui.get_ui(player, 'your_layer.your_node')
           end)
       end)
   end)
   ```
5. **在 `open_popup` 里创建 Prefab 卡槽**：
   ```lua
   local slot = y3.ui_prefab.create(player, 'artifactPickCmp', cached_panel)
   -- ⚠️ artifactPickCmp 的节点路径从 prefab 根节点起算：
   --    bg 节点路径为 'root.bg'（不是 'bg'）
   --    文字节点路径为 'root.bg.descr_TEXT'
   local bg   = slot:get_child('root.bg')
   local desc = slot:get_child('root.bg.descr_TEXT')
   desc:set_text(item.data.name)
   bg:add_local_event('左键-点击', function() M.confirm_pick(pid, slot_idx) end)
   ```
6. **在 `close_popup` 里移除**：`for _, slot in ipairs(active_slots) do slot:remove() end`
7. **键盘触发（如需）**：
   ```lua
   -- ⚠️ global_main.lua 的游戏-初始化里必须先开启键盘同步
   y3.config.sync.key = true
   -- ⚠️ 字母键用单字母大写 'F'，不是 'KEY_F'（数字键才用 'KEY_1' 前缀）
   y3.game:event('本地-键盘-按下', y3.const.KeyboardKey['F'], function() ... end)
   ```
8. **触发抽卡**：`M.try_pick(player_id)`
9. **回归验证**：跑测试用例

## 已知限制

- 不含 UI 渲染主逻辑，需要实现方具备 UI 开发能力（Adapter 全权负责 `open_popup`/`close_popup`）
- **UI 节点获取时机**：`y3.ui.get_ui` 在 `游戏-初始化` 同帧调用会失败，必须延迟 1 帧（`y3.ltimer.wait_frame(1, fn)`）
- **UI 节点路径格式**：`y3.ui.get_ui` 需要 `"layer名.节点名"` 格式，直接传节点 UID 无效
- **Prefab 子节点路径**：`y3.ui_prefab.create` 返回的 `UIPrefab`，调 `get_child` 时路径从 prefab 根节点起算。`artifactPickCmp` 的正确路径是 `root.bg` 和 `root.bg.descr_TEXT`（不是 `bg`）
- **键盘事件前置**：使用键盘触发时，必须在 `global_main.lua` 的 `游戏-初始化` 回调里设置 `y3.config.sync.key = true`，在地图 main.lua 里设置无效
- **键盘常量格式**：字母键用单字母大写（`'F'`），数字键用 `'KEY_1'` 前缀，功能键直接用 `'F9'`
- 不支持"多连抽队列"（如 3 连抽时自动打开下一次），需业务侧循环调用 `try_pick`
- 不支持"替换抽卡"（如选中后弹出二次弹窗：保留/替换），需扩展实现
- 权重为 0 的条目会被自动过滤（与源工程 `BondPlayerData` 的 `_discardPool` 行为一致）

## 源工程溯源

- 源模块：`gamePlay/manager/bond/BondPlayerData.lua:tryDrawCard/gainCardByPick`
- 源模块：`gamePlay/manager/ArtifactMgr.lua:showPick/pickSlot`
- 源模块：`gamePlay/manager/TreasureMgr.lua:openPickPopup/onPickCompleted`
- 导出日期：`2026-05-22`
- 导出工具：`y3-template-export`
