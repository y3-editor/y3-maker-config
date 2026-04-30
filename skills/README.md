# Y3 Skills 索引（进阶文档）

> 📘 **本文档面向专业用户 / 开发者**，用于深入了解各子技能、直接调用单个技能、或做产品定制。
> 🆕 **新手用户请从 [USER_GUIDE.md](../../USER_GUIDE.md) 开始**，只需要记住一个入口：`y3-game-spec`。
>
> AI 技能路由入口。按需加载 `SKILL.md`，避免 token 浪费。

**最后更新**: 2026-04-21

## 🚀 一次性技能（自动触发）

| 技能 | 触发条件 | 完成标记 | 说明 |
|------|----------|----------|------|
| **y3-env-setup** | `<agent>/env_setup_done` 不存在 | 创建该文件 | 检查 Python/Git/y3-lualib 环境 |

> ⚠️ 一次性技能在新会话开始时自动检测，完成后不再触发。

## 🎯 技能路由（进阶用户参考）

### 推荐路径（所有用户默认）

| 用户表述 | 入口 | 输出 |
|----------|------|------|
| 任何游戏开发需求 | **`y3-game-spec`** ⭐（唯一推荐入口） | 完整项目 |

### 直接调用子技能（仅限专业用户）

> ⚠️ 绕过 `y3-game-spec` 直接调用子技能，会跳过全流程编排、文档一致性校验、Gate 准入等保护机制。
> 仅在你明确知道自己在做什么、且只需要局部能力时使用。

| 用户表述 | 技能 | 输出格式 | 依赖/子技能 | 关键命令/目录 |
|----------|------|----------|-------------|---------------|
| "查询/生成/修改单位/物品/技能/Buff/投射物" | **y3-obj-edit** | JSON / MCP查询结果 | MCP y3editor | `editor_table/` |
| "做个UI/面板/界面/HUD/血条/技能栏" | **y3-ui-pipeline** ⭐ | JSON + Lua | → y3-ui-generator, y3-lua-pipeline | - |
| "写Lua逻辑代码" | **y3-lua-pipeline** | Lua | - | `script/` |
| "审查/review 已有 Lua 代码" | **y3-lua-review** | 审查报告 + 自动修复 | - | `script/` |
| "自动化测试/自动点击/UI自动化" | **y3-auto-test** 🖱️ | 坐标+操作 | MCP y3editor + desktop-automation | Editor MCP 获取控件坐标 |
| "从图片生成地形" | **y3-gen-terrain-from-image** | 地形格子数据 | MCP y3editor | `maps/` |

> ⭐ **UI 统一入口**：所有 UI 相关需求都走 `y3-ui-pipeline`，内部自动路由。
> `y3-ui-generator` 为 UI JSON 生成的内部实现，不直接暴露给用户。

## ⚡ 常用命令速查

```bash
# UI HTML → Y3 JSON
cd <agent>/skills/y3-ui-generator/scripts
py -3 html_to_y3_ui.py <input.html> <output.json>

# 提取 UI 树（减少 token）
py -3 gen_ui_tree.py <workspace_path>

# MCP 热更保存（必须按顺序）
# 1. hotfix_ui_editor → 2. 等待3秒 → 3. save_editor

# 桌面自动化点击（管理员权限）
# 1. bot_move_mouse 移动鼠标 → 2. mouse_clicker.ps1 点击
```

## 🔀 决策树

```
用户需求
  │
  ├─ 新手 / 完整游戏 / 不确定该用什么
  │     → y3-game-spec（唯一推荐入口，内部自动分发）
  │
  └─ 专业用户明确只要单点能力
        ├─ 物编 CRUD            → y3-obj-edit
        ├─ UI 开发              → y3-ui-pipeline
        ├─ Lua 代码             → y3-lua-pipeline
        ├─ Lua 审查             → y3-lua-review
        ├─ 自动化测试           → y3-auto-test
        └─ 图片生成地形         → y3-gen-terrain-from-image
```

## �️ 技能依赖关系图

```
┌─────────────────────────────────────────────────────────────────┐
│                        y3-game-spec                              │
│                      (游戏开发入口)                               │
└───────────────┬───────────────┬───────────────┬─────────────────┘
                │               │               │
                ▼               ▼               ▼
         ┌──────────┐    ┌──────────────┐    ┌──────────────┐
         │y3-obj-edit│   │y3-ui-pipeline│    │y3-lua-pipeline│
         │(物编查询/操作)│   │  (UI 入口)   │    │ (游戏逻辑)   │
         └──────────┘    └───────┬──────┘    └──────────────┘
                                 │
                    ┌────────────┼────────────┐
                    ▼            ▼            │
            ┌──────────────┐ ┌──────────────┐ │
            │y3-ui-generator│ │y3-lua-pipeline│ │
            │ (生成 JSON)   │ │ (Lua API)    │ │
            └──────────────┘ └──────────────┘ │
                                              │

         ┌──────────────────┐    ┌────────────┐
         │ y3-auto-test  │    │y3-env-setup│
         │ (桌面自动化)      │    │ (环境配置) │ ← 一次性
         └──────────────────┘    └────────────┘
```

## 📂 目录结构

```
<agent>/skills/             ← 用户功能技能
├── y3-game-spec/           ← 游戏开发指南
├── y3-obj-edit/            ← 物编查询/生成/修改（支持 MCP 查询）
├── y3-ui-pipeline/         ← UI 开发入口
├── y3-ui-generator/        ← UI JSON 生成（HTML → Y3 JSON）
├── y3-lua-pipeline/         ← UI Lua API
├── y3-lua-pipeline/        ← 非 UI Lua 代码
├── y3-env-setup/           ← 环境配置（一次性）
└── y3-auto-test/           ← 自动化测试（桌面自动化+测试规则）

<agent>/tools/              ← 辅助工具
├── screenshot_with_cursor.py  ← 截图并标记鼠标位置
└── draw_grid.py               ← 在截图上绘制坐标网格
```

## ⚡ 核心规则速查

> 详细规则见 `<agent>/rules/rules.mdc`

| 禁止 | 正确做法 |
|------|----------|
| 臆造 API/JSON 字段 | 查阅 `y3/` 源码验证 |
| 手写大型 JSON（300+行） | 使用脚本生成 |
| 手写技能栏/Buff/物品栏 UI | 使用官方组件 `type:17/18/20` |
| UI 坐标用左上角思维 | Y3 原点在**左下角** |

## 🎮 Y3 引擎速查

### UI 组件类型（常用）

| type | 名称 | 用途 |
|------|------|------|
| 1 | Button | 按钮 |
| 2 | Layer | 根面板（仅顶层） |
| 3 | TextLabel | 文本 |
| 4 | Image | 图片 |
| 5 | Progress | 进度条 |
| 6 | Model | 3D模型 |
| 7 | Layout | 布局容器 |
| 15 | InputField | 输入框 |
| **17** | **SkillBtn** | **技能按钮（官方）** |
| **18** | **BuffList** | **Buff列表（官方）** |
| **20** | **EquipSlot** | **物品槽（官方）** |

> 完整类型列表见 `knowledge/UI系统/01-字段规范.md`

### 玩家编号

| 编号 | 用途 |
|------|------|
| 1-12 | 普通玩家 |
| 31 | 中立敌对（怪物） |
| 32 | 中立友好（NPC） |

### 键盘常量

```lua
-- ✅ 正确
y3.const.KeyboardKey['KEY_1']
y3.const.KeyboardKey['KEY_F1']

-- ❌ 错误
y3.const.KeyboardKey['1']
```

## 📚 文档层级

### 权威参考（Knowledge）

| 文档 | 说明 |
|------|------|
| `knowledge/UI系统/01-字段规范.md` | **完整** UI 字段定义（type 0-74、pos_data、致命规则） |
| `knowledge/UI系统/03-官方组件.md` | **完整** 官方组件用法（SkillBtn/BuffList/EquipSlot） |
| `knowledge/UI系统/02-属性绑定.md` | UI 数据绑定 |

### 技能速查（Skills）

| 文档 | 说明 |
|------|------|
| `skills/y3-ui-generator/references/` | UI JSON 生成参考 |
| `skills/y3-lua-pipeline/references/*.md` | Lua API 参考（player/unit/ability 等） |
| `skills/y3-auto-test/SKILL.md` | 自动化测试流程（Editor MCP + 点击脚本 + 测试规则） |

### 其他

| 文档 | 路径 |
|------|------|
| 全局规则 | `<agent>/rules/rules.mdc` |
| 项目记忆 | `<agent>/memory/Memory.md` |

---

## 📊 反馈收集

每次 Skill 任务完成后询问用户：
- 📊 评分 (1-5)：1=不可用 | 3=基本可用 | 5=完美
- 🔧 是否需要人工修正？

---

*最后更新: 2026-04-21（收敛为专业用户进阶文档；新手用户请看 USER_GUIDE.md）*

