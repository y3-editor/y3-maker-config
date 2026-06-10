# 🧠 全局记忆系统

> **最后更新**：2026-05-15  
> **项目状态**：Y3游戏引擎项目  

## 📋 项目概览

**项目名称**：agentmap  
**项目类型**：Y3游戏引擎开发项目  
**当前阶段**：塔防游戏已完成验证，Agent 框架持续迭代中

## 🎯 项目目标

- [ ] 建立完整的工作记忆系统
- [ ] 实现跨会话的工作连续性
- [ ] 支持项目进展追踪

## 🔧 技术栈

- **游戏引擎**：Y3
- **开发环境**：CodeMaker AI
- **记忆系统**：基于文件的会话管理

### 2026-05-15：执行案多文档拆分机制

- **决策**：大型项目执行案支持拆分为多个子文档，避免单文件过大
- **核心变更**：
  - **拆分触发**：F-ID > 30 / 3+ 独立模块 / 用户主动要求
  - **命名规范**：`{gameName}执行案_主控.md` + `{gameName}执行案_{Phase/模块名}.md`
  - **低耦合原则**：按 Phase 拆分优先、跨文档依赖显式声明、禁循环依赖、尾部章节归主控
  - **一致性校验适配**：`doc-consistency.mdc` 支持多文档模式遍历合并
- **涉及文件**：`phase-2-execution.md`(新增§3)、`doc-consistency.mdc`(规则1扩展)、`SKILL.md`(命名表)
- **session**: `session-2026.05.15-11.19-执行案多文档拆分`

### 2026-05-14：执行案 spec 优化（实战验证驱动）

- **决策**：基于塔防实战验证成果，双向优化 `phase-2-execution.md` spec 规范
- **核心变更**：
  - **Phase 结构简化**：1A/1B/1C/2/2.a/2.b → Phase 1~6 直线序列（塔防验证更高效）
  - **功能清单分层**：Phase 1(物编) 7列简化格式 / Phase 2~4(Lua/UI) 9列完整格式
  - **功能模板降级**：从强制 Phase 1A~2.b 改为可选增强，有模板时才插入
  - **新增固定章节**：Bug修复记录表、附录(关键实现参考) — 实战验证必需
  - **已知风险与未决项**：从可选升级为强制
- **涉及文件**：`phase-2-execution.md`(全面重写)、`SKILL.md`(Phase划分表+模板支持章节)
- **session**: `session-2026.05.14-17.49-执行案spec优化`

### 2026-05-15：塔防工程实战知识库导出

- **决策**：将塔防工程（✅ 已验证可用）的全部实战知识导出为独立知识库
- **文件**：`.codemaker/knowledge/实战工程参考/塔防工程实战知识库.md`
- **内容**：工程架构(6模块) / 物编ID速查(15个) / 物编陷阱(4项) / Lua核心模式(8项) / Bug修复记录(7条) / 数值迭代工作流
- **session**: `session-2026.05.14-17.49-执行案spec优化`

## 📚 重要决策记录

### 2025-07-18：optimize-decoration-pipeline（v3 纹理组驱动）
- **决策**：装饰物系统从全局 style 升级为纹理组驱动 + 精确定位
- **核心变更**：
  - **废弃全局 `style`** → 纹理组驱动：每个采样点查脚下纹理 → 匹配纹理组 → 从该组模型池选模型
  - **新增 `texture_group_catalog.json`**：8 纹理组 × 170+ 纹理 ID × 5+ 模型/组（grassland/autumn/desert/ice_snow/jungle/dirt/rock/road）
  - **tree_cluster 精确定位**：fine_clusters（CV mask 优先）+ position+radius（圆形区域兜底）
  - **mountain_chain 连绵山脉**：from/to 方位描述，沿连线均匀放置 + 法线偏移
  - **6 步 Round 2 工作流**：2.0 前置准备 → 2.1 AI 标注 → 2.2 纹理组映射 → 2.3 采样分配 → 2.4 实体生成 → 2.5 统计自检
  - **decoration_postprocess.py 重构**：v3 核心引擎
  - **round2_decoration_prompt.md 重写**：引导 AI 产出 v3 JSON
  - **文档全面更新**：SKILL.md、decoration-model-ids.md、废弃旧 decoration_catalog.json
- **端到端验证**：68 实体产出，纹理匹配正确（C2→grassland, C3→autumn）
- **OpenSpec change**: `optimize-decoration-pipeline`

### 2026-04-28：optimize-decoration-generation 归档
- **决策**：优化 y3-gen-terrain-from-image 技能的装饰物生成逻辑
- **核心变更**：
  - **CV 子区域分析** (`cv_subregion_analysis.py`): 分析大陆内 K=50 微簇，识别可分离区域
  - **混合定位策略**: mask 模式(高精度 fine_clusters) + 方位模式(兜底 position 九宫格)
  - **Prompt 重构**: 逐大陆标注 + 大陆裁剪放大图(continent_crops) + 自检机制(Step D)
  - **密度控制**: sparse/normal/dense 三档泊松采样
  - **山峰自动缩放**: 基于 pickbound 的 count-based 放置（解决"鹅卵石"问题）
  - **大陆 Crops**: 九宫格标注的局部放大图，提升 AI 视觉精度
- **新增 Specs**: `cv-subregion-analysis`、`decoration-hybrid-positioning`（已同步到 main specs）
- **状态**: 16/18 tasks 完成，已归档
- **OpenSpec change**: `optimize-decoration-generation`（归档至 `archive/2026-04-28-optimize-decoration-generation`）

### 2026-04-27：optimize-terrain-gen-skill 实现
- **决策**：优化 y3-gen-terrain-from-image 技能
- **核心变更**：
  - 水域后处理（连通区分析填回孤立水域）
  - 装饰物后处理（泊松采样树木、桥梁水域吸附+yaw推算、山石散布）
  - MCP entity_create_block rotation bug 修复（rotation → yaw/pitch/roll）
- **关键原则**：不做 AI 无法做好的事（高度/多纹理/道路），用确定性后处理兜底
- **状态**：13/16 tasks 完成，3 个测试任务待验证
- **OpenSpec change**：`optimize-terrain-gen-skill`

### 2026-03-26：建立记忆系统
- **决策**：采用基于文件的记忆系统
- **原因**：确保跨会话工作连续性
- **结构**：全局Memory.md + sessions目录

### 2026-04-20：y3-game-spec 可行性审查机制改造
- **决策**：把可行性审查从 Step 9 单点检查改为「Step 1.5 + 每步实时审查」+ 严格化引擎能力红线
- **背景**：用户测试塔防生成时发现 ① 审查太晚导致 8 步白问 ② 审查太松导致兽人必须死(3D)被判通过
- **落地**：
  - 新建 `.codemaker/skills/y3-game-spec/feasibility-redlines.md`（176 行红线清单）
  - 改造 `game-design-guide.md`（673→1025 行）：移除模板体系、新增 Step 1.5 红线校验、新增「实时红线审查模板」、Step 9 改为跨步冲突+复审、补齐策划案模板章节
  - 改造 `SKILL.md`：新增红线机制相关核心禁令
- **重要纪律**（新增到经验沉淀）：
  - 改写超过 200 行的文件**必须**用 `replace_in_file`，**禁止**用 `edit_file`（本次发生过 edit_file 把整个 912 行文件清空的事故）
  - 引擎能力红线（视角/操作/物理类）一律不允许"勉强凑活"，命中即驳回并提供 ≥2 个 Y3 可行替代方案
- **救场记录**：edit_file 清空文件后，通过 `svn revert` 还原到 r752168 版本（673 行），再通过 10 次 replace_in_file 增量重建到 1025 行
- **session 报告**：`.codemaker/memory/sessions/session-2026.04.20-17.03-spec流程红线机制改造/report.md`

### 2026-03-26：制定变更记录规则
- **决策**：所有重要变更必须记录到记忆系统
- **原因**：确保工作连续性和上下文完整性
- **影响**：AI助手必须严格遵循变更记录原则
- **标准**：定义了6项记录触发条件和3项质量标准

### 2026-03-27：完成7日签到面板功能开发
- **决策**：实现完整的7日签到系统，包含UI面板和交互逻辑
- **技术方案**：使用y3-ui-generator + y3-lua-pipeline技能组合
- **核心成果**：
  - UI面板：`CheckinPanel.json` (28个组件，Y3标准格式)
  - Lua脚本：5个核心模块 (~850行代码)
  - 测试框架：完整的自动化测试套件
  - 调试工具：10个快捷键功能
- **OpenSpec变更**：seven-day-checkin-panel (32/52任务完成，已归档)
- **技术亮点**：
  - 按钮互斥选择逻辑实现
  - 完整的状态管理机制
  - 模块化测试框架设计
  - 错误处理和异常恢复

### 2026-04-02：y3-ui-generator 增加用户确认环节
- **决策**：为 UI 生成流程增加两个确认检查点，让用户可以在关键节点介入修改
- **技术方案**：通过显式用户确认实现交互式检查点
- **核心变更**：
  - **Step 1.5 草图确认**：生成结构草图后询问用户是否满意，支持多轮修改
  - **Step 3.5 预览确认**：HTML预览打开后询问用户确认布局，支持多轮调整
  - 调整步骤顺序：Step 2 (生成HTML) → Step 3 (打开预览) → Step 3.5 (确认) → Step 4 (转换JSON)
- **新增能力规格**：
  - `ui-gen-sketch-confirm`：草图确认交互能力
  - `ui-gen-preview-confirm`：预览确认交互能力
- **OpenSpec变更**：ui-generator-add-confirm-steps (13/13任务完成，已归档)
- **测试验证**：通过生成 `moba_hud_test` 面板完成完整流程测试

### 2026-04-03：UI 生成器支持 GridView + ScrollView
- **决策**：为 `y3-ui-generator` 技能新增 GridView (type:25) 和 ScrollView (type:10) 支持
- **作者**：刘冰 | SVN: 750909 | ticket: #98701
- **核心成果**：
  - `html_to_y3_ui.py`：新增 grid/list 类型解析 + `--prefab` 输出模式 + prefab_sub_key 注入
  - `SKILL.md`：新增 Step 0.3 网格/列表识别 + Step 1.8 Prefab 子流程 + 🔴 Grid 行列识别规则 + 🔴 List 方向规则
  - `widget_template_config.md`：新增 grid/list 识别关键字
- **关键修复**：
  - ZeroDivisionError：`grid_count` 行/列为 0 导致引擎崩溃 → 强制 `max(1)`
  - 行列识别错误："4×5 格子" 被映射为 `(1, 4)` → 新增识别对照表，`data-rows` 和 `data-cols` 改为必填
- **OpenSpec变更**：ui-gen-grid-list-support-98701（已归档）

### 2026-04-10：重构 Lua Pipeline（统一 + API 白名单）
- **决策**：将 `y3-ui-official` 合并到 `y3-lua-pipeline`，基于 v250804 usage-guide 重写 SKILL.md，建立 API 白名单机制
- **核心变更**：
  - **删除** `y3-ui-official/` 目录，8 个 UI reference 文件合并到 `y3-lua-pipeline/references/`（共 22 个）
  - **重写** `y3-lua-pipeline/SKILL.md`：嵌入 877 行 usage-guide 的 Part 1/2/3（y3 库结构 + 9 类代码模式 + API 快速参考）
  - **精简** `rules.mdc` Lua 规则为 4 条强制声明（替代原 Hard Gates 大段章节）
  - **增强** `api-safety.mdc` 增加 API 白名单引用
  - **更新** `y3-ui-pipeline`、`y3-game-spec`、`y3-ui-generator` 等所有关联文件的引用
- **新增 Specs**：`unified-lua-pipeline`、`api-whitelist-enforcement`（已同步到 main specs）
- **OpenSpec 变更**：refactor-lua-pipeline (12/12 任务完成，已归档)
- **关键规则**：所有 Lua 代码必须通过 `y3-lua-pipeline` 编写，API 使用必须可追溯到 SKILL.md 或 references

### 2026-04-14：MCP Server Timer 链修复 (mcp-terrain-timer-chain)
- **决策**：将 terrain_handlers.py 中所有 `_do_cmd` 调用从 HTTP 工作线程调度到引擎主线程
- **根因**：`ThreadingMixIn` + 高频请求导致引擎 API 并发调用，概率性崩溃（10054/10061/JSON 截断）
- **核心变更**：
  - 新增 `_execute_cells_via_timer()` 通用 Timer 回调链执行器
  - 19 个地形/实体函数的 `for cell` 循环改为 Timer 回调链（每 cell 间隔 0.05s）
  - `BATCH_SIZE` 50→300，HTTP 请求减少 ~83%
  - 所有 return 值和 errors 改为英文
- **改动文件**：`terrain_handlers.py`（Server 端）、`mcp_batch_writer.py`（Client 端）
- **OpenSpec 变更**：mcp-terrain-timer-chain（24/24 任务完成）
- **排查教训**：先排除了 UTF-8 编码假设和 flush 假设，最终通过对比分析确认是线程安全问题

### 2026-05-22：模板等级机制 + C 级三层架构 + c-pick-one-of-many 模板导出

- **决策**：为 `y3-template-export` skill 引入 A/B/C/D 四级模板等级机制，C 级采用三层架构（DataSchema + Adapter + Pure Logic）
- **核心变更**：
  - **`templates/ReadMe.md`**：新增 §0 等级机制（4 级定义 + ID 前缀 + 选级仲裁）/ 13→14 字段表（加「等级」「入口签名」）/ §3 增 C 级三层架构约束 / §4 拆 4.1 通用 + 4.2 C 级强制三段（数据契约/Adapter 接口/MockAdapter）+ 4.3 C 级接入步骤要求
  - **`skills/y3-template-export/SKILL.md`**：description 加等级说明 / 新增 §3 等级机制（判定速查 + 冲突仲裁 + 流程影响表）/ §4 首句加问等级 / §5 校验等级与前缀一致 / §6 C 级追加 Adapter 接口卡点 / §11 拆 11.1 A/B 级骨架 + 11.2 C 级三层骨架 + 11.3 C 级硬性约束 / §12 14 字段 + C 级强制段落 / §14 自检加 6 项 C 级特有 / 全文章节编号 +1
  - **Demo 实战验证**（`test321321` 工程）：按 F 键→属性三选一弹窗→点击选中，完整跑通
  - **lua-issues/api_issues.md 新增**：`y3.ui.get_ui` 路径格式 / 调用时机 / `get_child` 路径起点 / `sync.key` 设置位置 / KeyboardKey 字母键格式（共 5 条）
  - **修复**：`refresh_pick` 的 `close_popup` 提前到 `on_refresh_requested` 后立即执行（UX 改进，先关旧 UI 再算新结果）
  - **`templates/ReadMe.md §7`**：登记 c-pick-one-of-many 为 draft v0.1.0
  - **`difficulty-select`**：补「等级=A」字段
- **设计决策**：
  - C 级不导出 `.upui`（ArtifactPickCmp Prefab export_ui 两次超时），模板为纯 Lua，ReadMe 截图替代参考
  - Adapter 11 方法（10 必填 + 3 可选），random_fn 可注入用于单测
  - group 字段支持"同 group 排他"的抽卡机制
  - BondPickCardCmp 深度定制（393 行 / 品质背景 / 标签图标 / ConfigMgr 依赖），确认 C 级 UI 全由 Adapter 负责
- **涉及文件**：`templates/ReadMe.md`, `skills/y3-template-export/SKILL.md`, `templates/c-pick-one-of-many/logic.lua`, `templates/c-pick-one-of-many/ReadMe.md`
- **session**: `session-2026.05.22-11.01-C级模板机制与pick-one导出`
- **决策**：基于 `Y3AgentRoadMap.md` 策划案实现完整 RPG 游戏逻辑
- **技术方案**：y3-lua-pipeline + y3-ui-generator 技能组合
- **核心成果**：
  - **UI 面板**：
    - `HeroSelectPanel.json`：5 英雄选择界面
    - `GameHUD.json`：游戏 HUD（金币/经验/波次/怪物数/血蓝条）
  - **Lua 脚本**：`rpg_game.lua` (~530 行代码)
    - 英雄选择系统（按钮点击 + 键盘快捷键）
    - 波次刷怪系统（5 波，含 Boss）
    - HUD 实时更新（0.5 秒刷新）
    - 物品掉落系统（概率掉落）
    - 英雄死亡复活（5 秒自动复活）
- **关键 API 验证**：
  - `player:display_message()` 广播消息
  - `btn:add_fast_event('左键-按下', callback)` 按钮点击
  - `y3.ui.get_ui(player, "Panel.widget.child")` 点号路径
  - `y3.player.get_by_id(31)` 中立敌对玩家
- **调试快捷键**：1-5(选英雄) / N(跳波) / G(加金) / R(重载)

## 🔗 相关资源

- 项目根目录：`.`
- Y3编辑器相关技能已可用
- OpenSpec工作流已激活

## � 记忆系统规则

### 🔄 变更记录原则
- **重要变更必须记录**：所有重要的代码变更、设计决策、架构调整都必须记录到记忆系统
- **实时更新**：每次会话中的关键进展要及时同步到全局记忆
- **决策追踪**：记录决策的原因、背景和影响
- **上下文保持**：确保下次会话能完整恢复工作状态

### 📋 记录触发条件
- 新增/修改核心代码文件
- 重要架构或设计决策
- 项目目标或方向调整
- 技术栈变更
- 关键问题的解决方案
- 用户反馈和需求变更

### 🎯 记录质量标准
- **完整性**：包含足够的上下文信息
- **准确性**：记录真实的变更和决策
- **可追溯**：能够理解变更的来龙去脉
- **actionable**：为后续工作提供明确指导

## �📝 备注

用户希望建立持续的工作记忆，确保每次对话都能基于之前的上下文继续工作。
