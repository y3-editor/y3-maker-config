---
name: sync-y3maker-to-lualib
description: >
  将 y3-maker-config 中与 Lua 开发相关的知识库、规则与通用技能单向整理并同步到 y3-lualib/doc/ 目录。
  仅用于双仓维护者执行或更新从 y3-maker-config 到 y3-lualib 的同步与校验；
  不用于把 .y3maker/ 迁移到地图项目的 .claude/ 或 .codex/ 目录。
---

# 同步 y3-maker-config Lua 资产到 y3-lualib

本技能用于将 `y3-maker-config`（唯一主源）中 **Lua 直接相关或 Lua 开发流程所需** 的知识库、规则与技能，单向整理并同步到 `y3-lualib/doc/`。

## 1. 定位与准入原则

- **唯一主源**：所有同步内容的编写、脱敏与修复均先在 `y3-maker-config` 完成，再同步至 `y3-lualib/doc/`，不在目标仓反向改动同步目录。
- **准入标准**（详情以 `references/scope.json` 为准）：
  - **纳入 `knowledge/`**：除纯 ECA 文档（`核心系统/12-ECA系统.md`）外的全部知识库；同步 `knowledge/README.md` 时剔除指向被排除文档的索引行。
  - **纳入 `rules/`**：Lua 开发与 Lua 交付流程直接依赖的规则（`api-safety.mdc`、`ui-rules.mdc`、`mcp-rules.mdc`、`auto-test.mdc`、`doc-consistency.mdc`），排除套件总控与记忆规则（`rules.mdc`、`memory.mdc`）。
  - **纳入 `skills/`**：Lua 与云脚本编码/审查技能（`y3-cloud-script`、`y3-lua-pipeline`、`y3-lua-review`）以及 Lua 全流程配合技能（`y3-ui-pipeline`、`y3-ui-generator`、`y3-obj-edit`、`y3-auto-test`、`y3-game-spec`、`y3-resource-import`），排除其内部样例/缓存/ECA 路线图（`y3-game-spec/roadmaps/*-ECA-基准版.md`、`y3-resource-import/temp/**`、`y3-auto-test/.queue/**`、`__pycache__`、`*.pyc`）。
  - **排除目录与技能**：`memory/`、`templates/`、`tools/` 以及纯 ECA、纯地形/地编与套件内部维护技能（`y3-eca-pipeline`、`eca-json-builder`、`y3-gen-terrain-from-image`、`y3-terrain-template`、`y3-env-setup`、`y3-template-export`、`y3-memory-distill`）。
- **结构同构**：在 `y3-lualib/doc/` 下完全保留 `y3-maker-config` 原目录结构与文件命名（`doc/knowledge/`、`doc/rules/`、`doc/skills/<skill>/`）。

## 2. 原生资产与本地状态护栏

1. **严禁覆写或删除 `y3-lualib/doc/` 原生资产**：
   - `doc/API.md`、`doc/API/`、`doc/Lua虚拟机.md`
   - `doc/AGENTS.md`
   - `doc/skills/y3-lib/`、`doc/skills/y3-lua-vm/`
2. **严禁触碰本地非任务资产**：提交时禁止 `git add -A` 或 `git add .`，必须显式 `git add` 变更路径，绝不暂存未追踪的 `CODING_STANDARDS.md`，也绝不切换或修改 `wip/save-data` 等无关分支。
3. **Python 命令**：在 Windows 环境下统一使用 `py -3` 调用脚本，避免误触发 Python 2.7。

## 3. 标准 5 步同步流程

### Step 1：核查双仓基线与分支
- 确认 `y3-maker-config` 与 `y3-lualib` 工作区干净（仅允许未追踪的 `CODING_STANDARDS.md`），并各自基于最新 `main` 切出新分支。

### Step 2：Dry-Run 盘点差异与源仓新增项
运行：

```bash
py -3 .agents/skills/sync-y3maker-to-lualib/scripts/sync_and_verify.py \
  --source <y3-maker-config路径> \
  --target <y3-lualib路径> \
  --dry-run
```

检查输出中的两部分信息：
- 待新增 / 更新 / 清理的托管文件清单；
- **未分类项提示（Unclassified）**：若 `y3-maker-config/skills/` 或 `rules/` 新增了目录/文件（既不在白名单也不在 `known_excluded_*` 中），先依据第 1 节准入原则判断是否应纳入，向维护者确认后更新 `references/scope.json`（纳入或补充到已知排除列表）。

### Step 3：源头脱敏与坏链审查
- 若新增或改动文档中命中敏感内部项目代号（`DM42`、`DM32`、`爆战兄弟`、`射手大师`、`test321321`、`svn-dm58`、本机绝对路径等）或引用了不存在的本地文件，**先在 `y3-maker-config` 源仓修复**再执行同步。
- 不要对同步副本正文做全文正则魔改或段落裁剪；与排除项相关的仅在 `references/scope.json` 通过 `readme_strip_patterns` 处理 `knowledge/README.md` 索引行，并在 `y3-lualib/doc/AGENTS.md` 中说明未纳入项约定。

### Step 4：执行同步与全量门禁校验
运行 `--apply`（会在写盘完成后自动执行全部 `--verify-only` 检查）：

```bash
py -3 .agents/skills/sync-y3maker-to-lualib/scripts/sync_and_verify.py \
  --source <y3-maker-config路径> \
  --target <y3-lualib路径> \
  --apply
```

若仅需复检已有目标仓状态，可运行：

```bash
py -3 .agents/skills/sync-y3maker-to-lualib/scripts/sync_and_verify.py \
  --source <y3-maker-config路径> \
  --target <y3-lualib路径> \
  --verify-only
```

### Step 5：复核 `doc/AGENTS.md` 与提交 PR
1. 若本次增删了托管技能、规则或知识库大类，检查并同步更新 `y3-lualib/doc/AGENTS.md` 的目录地图与技能分工表。
2. 在 `y3-lualib` 检查 `git diff -- doc/skills/y3-lib doc/skills/y3-lua-vm doc/API.md doc/API doc/Lua虚拟机.md`，确认原生资产未被脚本修改。
3. 先提交并推送 `y3-maker-config`（如含源仓修复或 `scope.json` 更新），再在 `y3-lualib` 显式 `git add` 变更目录并推送到个人 fork（`origin`）向 `y3-editor/y3-lualib`（`upstream`）`main` 创建 PR。
