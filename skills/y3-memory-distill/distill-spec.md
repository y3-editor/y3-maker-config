# Y3 Memory Distill — Spec

> 状态：Draft v0.1（待评审）
> 用途：定义 "把 memory 反哺到 skill / knowledge / rules" 的标准流程
> 范围：纯流程规范，不含脚本实现

---

## 1. 概念

**Memory Distill** = 周期性把 `memory/` 中沉淀的会话报告、错题、决策记录，**蒸馏**为对 skill / knowledge / rules 的结构化更新提案，并在用户审阅后回填。

> 一句话：**让记忆从「写完就睡」变成「定期反哺」。**

### 1.1 三层数据流

```
[ 工作记忆 ]                [ 蒸馏层 ]                [ 长期知识 ]
sessions/*/report.md  ──►   distill-report.md  ──►   skills/*/SKILL.md
lua-issues/*.md                  (diff 提案)         skills/*/references/
Memory.md                                            knowledge/
                                                     rules/*.mdc
```

- **工作记忆**：单次会话的临时产物，量大、噪声多、未经验证
- **蒸馏层**：聚类、去重、分桶后的候选改动（diff 提案）
- **长期知识**：经用户审阅后落盘的稳定规则、API 白名单、知识条目

### 1.2 输入 / 输出

| 输入 | 来源 |
|------|------|
| 会话报告 | `memory/sessions/session-*/report.md` |
| Lua 错题 | `memory/lua-issues/api_issues.md` + `trace_issues.md` |
| 全局决策 | `memory/Memory.md` |
| 沙盒中间产物 | `memory/sandbox/` |

| 输出 | 落点 |
|------|------|
| 关键词索引 | `memory/sessions/INDEX.md` |
| 蒸馏报告 | `memory/distill/distill-YYYYMMDD.md` |
| skill 反哺 | `skills/<x>/SKILL.md` / `references/*.md` |
| 知识库反哺 | `knowledge/<topic>/*.md` |
| 规则反哺 | `rules/*.mdc`（仅 hard rules） |
| 归档 | `memory/sessions/_archive/`（已蒸馏 + >180 天） |

---

## 2. 流程（5 步）

### Step 1 — 扫描 & 分类

遍历全部 memory 来源，为每条记录打标签：

| 维度 | 取值 |
|------|------|
| `topic` | `lua-api` / `lua-trace` / `ui-gen` / `obj-edit` / `terrain` / `eca` / `template` / `auto-test` / `spec-flow` |
| `severity` | `bug` / `pitfall` / `enhancement` / `decision` |
| `recurrence` | 同主题在多少个 session 出现 |
| `age` | 距今天数 |
| `bound_skill` | 关联到哪个 skill（可多个） |

### Step 2 — 聚类找模式

只有满足以下条件的记录才进入候选：

| 触发模式 | 候选去向 |
|----------|----------|
| 同 API 错误 ≥ 2 个 session | 候选写入对应 skill 的 `references/api_errors.md` 或专项 md |
| 同主题陷阱 ≥ 3 个 session | 候选写入 `knowledge/<topic>/` |
| 跨项目复现的引擎 quirk | 候选升级到 `rules/api-safety.mdc` |
| 单 session 但 severity=bug 且方案稳定 | 候选写入 `references/`（不进 rules） |
| `Memory.md` 单条 > 180 天且未被引用 | 候选归档 |

> ⚠️ **不做的事**：单次出现的低危项目不蒸馏，避免规则膨胀。

### Step 3 — 生成 Diff 提案

蒸馏报告 `distill-YYYYMMDD.md` 必须包含：

```markdown
## 候选 #N
- 来源 sessions: [list]
- 聚类主题: <topic>
- 出现次数: M
- 提议落点: <file_path>
- 提议 diff:
  ```diff
  + 新增条目内容
  ```
- 用户决策: [ accept / reject / defer ]
- 备注:
```

**强制约束**：
- 每条候选必须给出 `file_path` 和可直接 apply 的 diff
- 跨多文件的候选必须拆分为多条
- accept 后 skill / knowledge 的改动必须可追溯回 session

### Step 4 — 用户审阅

- 输出 `distill-YYYYMMDD.md` 给用户
- 用户逐条标记 `accept` / `reject` / `defer`
- AI 不得自动 accept，**必须**等用户确认
- `defer` 项保留到下次蒸馏，连续 defer 3 次自动转 reject 并记录原因

### Step 5 — 应用 & 归档

| 状态 | 动作 |
|------|------|
| accept | 按 diff 写入目标文件；在源 session 标记 `[distilled→<target>]` |
| reject | 在源 session 标记 `[distill-rejected]` 并记录原因 |
| defer | 留到下次 |

**归档规则**：
- session age > 180d 且 100% 蒸馏 → 移到 `memory/sessions/_archive/`
- `Memory.md` age > 180d 条目 → 移到 `Memory.archive.md`，仅保留摘要链接

---

## 3. 触发条件

| 信号 | 动作 |
|------|------|
| 用户主动调用 `y3-memory-distill` | 立即执行完整流程 |
| `sessions/` 数量 ≥ 50 | 开局自检时建议运行 |
| 距上次 distill ≥ 30 天 | 开局自检时建议运行 |
| 同关键词在 ≥ 3 session 出现 | 即时建议（不强制） |
| 某 skill 的错题 ≥ 10 条同类 | 即时建议针对该 skill 的局部蒸馏 |

> 自检入口：`memory/distill/.last_run` 文件记录上次运行时间戳。

---

## 4. 与 11 个现有 Skill 的反哺映射

| Skill | 主要输入信号 | 反哺落点 |
|-------|------------|---------|
| **y3-lua-pipeline** | `lua-issues/api_issues.md`、`trace_issues.md` | `references/api_errors.md`、`references/<api>.md`（unit/ability/buff/...） |
| **y3-lua-review** | 高频未捕获的 review 漏检（来自 sessions） | review 检查清单 + 白名单同步 |
| **y3-ui-pipeline** | UI 路径、节点查找、prefab 相关错题 | `references/y3-ui-*.md`、`SKILL.md` 速查表 |
| **y3-ui-generator** | HTML→JSON 转换坑（GridView/ScrollView 行列、prefab 子节点） | `widget_template_config.md`、识别关键字表 |
| **y3-obj-edit** | 物编 JSON tuple 格式、字段陷阱 | `SKILL.md` 字段速查、模板示例 |
| **y3-game-spec** | 跨阶段冲突、可行性红线遗漏、执行案漏项 | `feasibility-redlines.md`、`phase-2-execution.md` 附录 K |
| **y3-auto-test** | UI 触发失败、断言缺失、热更时序 | `SKILL.md` 测试纪律、官方组件交互模板 |
| **y3-gen-terrain-from-image** | CV 子区域、装饰物匹配错位、纹理组映射 | `SKILL.md` Round2 工作流、`texture_group_catalog.json` |
| **y3-terrain-template** | 地编模板导入失败、resize 时序 | `SKILL.md` 流程节点 |
| **y3-template-export** | A/B/C/D 等级判定争议、Adapter 接口缺漏 | `templates/ReadMe.md`、`SKILL.md` §3 等级机制 |
| **y3-env-setup** | 环境配置异常（Python/Git/y3-lualib 探测） | `SKILL.md` 检测分支表 |

> 跨 skill 共性问题（如"先热更再保存"）→ 反哺 `rules/mcp-rules.mdc` 而非单个 skill。

### 4.1 知识库反哺映射

| 知识目录 | 信号来源 |
|----------|---------|
| `knowledge/核心系统/` | y3-game-spec、y3-lua-pipeline 中跨项目复现的引擎能力 |
| `knowledge/UI系统/` | y3-ui-pipeline、y3-auto-test 的 UI 路径与官方组件经验 |
| `knowledge/物编系统/` | y3-obj-edit、y3-game-spec Phase 1 的物编陷阱 |
| `knowledge/实战工程参考/` | 已完工项目的端到端总结（塔防 / 生存 / RPG / DM32 ECA） |

---

## 5. 强制纪律

1. **单向流动**：memory → skill / knowledge / rules，禁止反向
2. **必须经用户审阅**：AI 不得自动 accept 任何 diff
3. **可追溯**：所有反哺改动必须能回溯到至少 1 个 session 报告
4. **不污染 rules**：仅"跨项目复现 ≥ 2 次的硬性引擎 quirk"才允许进 `rules/`
5. **不爆炸 references**：单文件超过 500 行触发拆分提示，禁止无脑追加
6. **归档不删除**：所有 archive 操作只移动不删，可恢复

---

## 6. 验收标准

一次蒸馏被认为成功，需满足：

- [ ] 生成了 `distill-YYYYMMDD.md` 报告
- [ ] 至少识别出 1 条 ≥3 复现的候选
- [ ] 所有 accept 候选已落地，diff 可在 git 历史中追溯
- [ ] 涉及的 session 已标记 `[distilled→...]`
- [ ] `INDEX.md` 已同步更新关键词索引
- [ ] 蒸馏报告保留在 `memory/distill/`，作为审计记录

---

## 7. 非目标（明确不做）

- ❌ 不做语义级聚类（无嵌入向量），仅靠关键词 + 主题标签
- ❌ 不自动改 Lua 业务代码，只改 skill / knowledge / rules / references
- ❌ 不替代 `y3-lua-review`，只补充其规则库
- ❌ 不做实时蒸馏，仅周期性触发

---

## 8. 后续路线（非本 spec 范围）

| 阶段 | 内容 |
|------|------|
| v0.1 | 本 spec（仅文档） |
| v0.2 | 最小实现：`INDEX.md` 生成器 + `api_issues.md` 聚类脚本 |
| v0.3 | 完整 skill：`SKILL.md` + `scripts/distill.py` |
| v0.4 | 与 `y3-lua-review` 联动：lint 时引用蒸馏后的白名单 |

---

*最后更新：2026-06-15*
