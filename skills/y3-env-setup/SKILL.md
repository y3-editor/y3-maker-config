---
name: y3-env-setup
description: >
  Y3 开发环境一次性配置助手。检查并自动配置 Python、Git、y3-lualib 环境。
  
  此 Skill 为一次性使用，完成后会创建标记文件，后续会话自动跳过。
  
  检测条件：<codemaker>/env_setup_done 文件不存在时自动触发
---

# Y3 环境配置助手（一次性）

> ⚠️ **一次性 Skill**：完成后创建 `<codemaker>/env_setup_done` 标记，后续不再执行。

## 🎯 功能说明

自动检查并配置 Y3 开发环境：
1. **Python 3** - 检查/安装/配置
2. **Git** - 检查/安装/配置
3. **y3-lualib** - 检查/克隆/初始化配置

## 📋 执行流程

### Step 1: 智能检测环境状态

```
1. 检查 <codemaker>/env_setup_done 是否存在
   ├─ 存在 → ✅ 跳过，继续处理用户请求
   └─ 不存在 → 继续检查步骤 2

2. 检查 y3-lualib 是否已存在（任一路径存在即可）
   - maps/EntryMap/script/y3/init.lua
   - global_script/y3/init.lua
   ├─ 存在 → ✅ 老项目已配置，自动创建标记文件并跳过
   └─ 不存在 → 继续执行 Step 2 预告+授权
```

> 💡 此逻辑确保老项目不会被误触发环境配置。

### Step 2: 预告 + 授权（用户可见）⭐

**首次检测到环境未配置时，必须先用 `ask_user_question` 告知用户以下全部信息，再询问是否继续。**

#### 2.1 必须告知用户的"知情卡"

呈现给用户的消息格式如下（可根据实际情况细化版本号）：

```
🔧 检测到你是第一次使用本 Agent，需要先配置 Y3 开发环境。
   这个过程只发生一次，完成后以后的会话不会再问你。

📋 我将检查并（如缺失）协助安装以下 3 样东西：

  ① Python 3        → 用于运行 UI JSON 生成、节点树提取等辅助脚本
                      检查命令：py -3 --version
                      缺失时：通过 winget 或官网安装（约 3 分钟）

  ② Git             → 用于拉取 y3-lualib 框架代码
                      检查命令：git --version
                      缺失时：通过 winget 或官网安装（约 2 分钟）

  ③ y3-lualib 框架  → Y3 游戏开发的核心库（写 Lua 都要用它）
                      检查路径：maps/EntryMap/script/y3/init.lua
                      缺失时：从 GitHub / Gitee 克隆 + 运行初始化脚本（约 2-5 分钟）

⏱️ 预计总耗时：最好情况 10 秒（都已装好），最坏情况 10 分钟（三样全新装）。
🌐 网络要求：安装环节需要连接 winget 源 / GitHub / Gitee。
🔐 权限要求：不需要管理员权限（winget 会自行处理）。
```

#### 2.2 授权选项

```
你希望怎么处理？

选项：
1. ✅ 开始检查并配置（推荐）
2. ⏭️ 我已自行配置好，跳过并记住（不再提示）
3. ⏸️ 稍后再说（本次跳过，下次会话继续询问）
```

**处理逻辑：**

| 用户选择 | 处理 |
|----------|------|
| 选择 1 | 继续执行 Step 3 环境检测；每一步开始前告知用户"正在检查 XX" |
| 选择 2 | 创建标记文件（状态为 `SKIPPED_BY_USER`），后续不再提示 |
| 选择 3 | 本次不执行，继续处理用户原始请求 |

> ⚠️ **不允许跳过 Step 2 直接执行检查或安装**。用户必须明确授权后才能动手。

**跳过标记内容：**

```bash
echo Environment setup SKIPPED by user on %DATE% %TIME% > <codemaker>\env_setup_done
echo Status: SKIPPED >> <codemaker>\env_setup_done
```

> 💡 用户选择跳过后，如需重新配置，删除 `<codemaker>/env_setup_done` 文件即可。

### Step 3: 环境检测（每步向用户播报进度）⭐

**每次进入一个子步骤前，必须先向用户播报"当前正在做什么"**（简短一行即可，不需要 `ask_user_question`，直接文字输出）。

示例播报格式：

```
🔍 [1/3] 正在检查 Python 3...
✅ Python 3.12.1 已安装

🔍 [2/3] 正在检查 Git...
✅ Git 2.44.0 已安装

🔍 [3/3] 正在检查 y3-lualib 框架...
❌ 未找到 y3-lualib，即将进入安装环节
```

执行以下终端命令检查环境：

```bash
# 检查 Python
py -3 --version

# 检查 Git
git --version

# 检查 y3-lualib（在项目目录）
dir maps\EntryMap\script\y3 2>nul || dir global_script\y3 2>nul
```

> 📘 **规则**：任何一个检查失败进入安装环节之前，必须再次用 `ask_user_question` 确认
> "是否允许我尝试自动安装 XX？"，给用户 [自动安装 / 我手动装 / 跳过不装] 三个选项。

### Step 4: 缺失环境处理

#### 4.1 Python 未安装

```bash
# 方案1：推荐使用 winget 安装（Windows 10+）
winget install Python.Python.3.12

# 方案2：手动下载
# 引导用户访问 https://www.python.org/downloads/
```

安装后需要：
- 确保勾选 "Add Python to PATH"
- 验证：`py -3 --version`

#### 4.2 Git 未安装

```bash
# 方案1：推荐使用 winget 安装
winget install Git.Git

# 方案2：手动下载
# 引导用户访问 https://git-scm.com/download/win
```

安装后验证：`git --version`

#### 4.3 y3-lualib 配置（重要！）

y3-lualib 的完整配置需要以下步骤：

##### 方式一：自动初始化（推荐）

1. **安装 VSCode 扩展**
   - 在 VSCode 扩展市场搜索安装 `sumneko.y3-helper`
   
2. **初始化 Y3 库**
   - 在 VSCode 左侧边栏选择"Y3开发助手"
   - 点击"初始化Y3库"按钮

##### 方式二：手动初始化

1. **克隆 y3-lualib 到 script 目录**

```bash
# 进入地图脚本目录
cd maps/EntryMap/script

# 如果已有 y3 目录，先备份或删除
rmdir /s /q y3 2>nul

# 克隆 y3-lualib（如果访问 GitHub 困难，使用 Gitee 镜像）
# GitHub:
git clone https://github.com/y3-editor/y3-lualib.git y3

# 或 Gitee 镜像:
git clone https://gitee.com/tsukiko/y3-lualib.git y3
```

2. **运行初始化配置脚本**（关键步骤！）

```bash
# 进入 y3 目录
cd maps/EntryMap/script/y3

# 运行初始化脚本，配置插件环境与调试器
call 初始化配置.bat
```

> ⚠️ **重要**：必须运行 `初始化配置.bat`，它会：
> - 配置 VSCode 插件环境
> - 配置调试器
> - 生成必要的配置文件

3. **使用 VSCode 打开 script 文件夹**

```bash
# 用 VSCode 打开脚本目录
code maps/EntryMap/script
```

##### 版本注意

```
⚠️ 如果使用的编辑器是 1.0 版本，需要切换 y3-lualib 分支：
cd maps/EntryMap/script/y3
git checkout 1.0
```

##### 验证配置成功

检查以下文件/目录是否存在：
- `maps/EntryMap/script/y3/init.lua` - Y3 库入口
- `maps/EntryMap/script/y3/debugger.lua` - 调试器配置
- `.vscode/settings.json` - VSCode 配置（初始化脚本生成）

### Step 5: 关闭编辑器自动保存（重要！）

**在创建完成标记之前，必须调用 MCP 工具关闭编辑器自动保存：**

```
调用 y3editor.modify_editor_config(config_type="close_auto_save")
```

| 项目 | 说明 |
|------|------|
| **为什么** | 避免 AI 修改文件时与编辑器自动保存冲突，导致数据丢失或覆盖 |
| **是否永久** | 是，配置写入文件，编辑器重启后仍然生效 |
| **如何恢复** | 用户可在编辑器设置中手动开启自动保存 |

> ⚠️ **此步骤不可跳过**。即使用户选择跳过其他环境检查，也必须执行此步骤。

### Step 6: 创建完成标记

所有检查通过后，创建标记文件：

```bash
echo Environment setup completed on %DATE% %TIME% > <codemaker>\env_setup_done
echo Status: OK >> <codemaker>\env_setup_done
echo Python: OK >> <codemaker>\env_setup_done
echo Git: OK >> <codemaker>\env_setup_done
echo y3-lualib: OK >> <codemaker>\env_setup_done
echo AutoSave: DISABLED >> <codemaker>\env_setup_done
```

> ⚠️ **重要**：必须包含 `AutoSave: DISABLED` 标记，这是版本检查的依据。
> 旧版本 env_setup_done 没有此标记时，rules.mdc 会触发一次性补丁操作。

> 💡 如果用户在 Step 2 选择了"跳过"，或在 Step 3 中选择某项"跳过不装"，
> 标记文件状态写为 `PARTIAL` 或 `SKIPPED_BY_USER`，并在后续使用相关功能时提示用户补装。

### Step 7: 输出报告

```
╔══════════════════════════════════════════════════════════════╗
║                   Y3 环境配置完成报告                         ║
╠══════════════════════════════════════════════════════════════╣
║ ✅ Python:     3.12.x    路径: <Python安装路径>              ║
║ ✅ Git:        2.44.x    路径: <Git安装路径>                 ║
║ ✅ y3-lualib:  已配置    路径: maps/EntryMap/script/y3       ║
║    └─ 初始化脚本: ✅ 已执行                                   ║
║    └─ VSCode 插件: sumneko.y3-helper                         ║
╠══════════════════════════════════════════════════════════════╣
║ 标记文件已创建：<codemaker>/env_setup_done                     ║
║ 后续会话将跳过环境检查。                                       ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 🔧 VSCode 调试配置

配置完成后，可以使用 VSCode 进行调试：

1. 确保安装了 `sumneko.y3-helper` 扩展
2. 点击左侧功能栏中的"Y3开发助手"视图
3. 点击"启动游戏并附加调试器"（快捷键：`Shift+F5`）

---

## 📝 演示代码（可选）

y3-lualib 提供了演示代码，可用于学习：

| 演示 | 启用方式 | 需要的插件 |
|------|----------|-----------|
| 界面 | `require "y3.演示.demo.界面"` | LuaLib示例-界面 |
| 防守图 | `require "y3.演示.demo.防守图"` | LuaLib示例-防守图 |
| 练功房 | `require "y3.演示.demo.练功房"` | LuaLib示例-练功房 |
| 合成 | `require "y3.演示.demo.合成"` | LuaLib示例-界面 |

> 插件安装：编辑器 → 菜单栏 → 插件 → 插件商城 → 搜索 `LuaLib`

---

## 🔄 手动重新配置

如果需要重新执行环境配置，删除标记文件即可：

```bash
del <codemaker>\env_setup_done
```

然后在新会话中 AI 会自动重新检查环境。

---

## 📝 常见问题

### Q: winget 命令不可用？

A: winget 需要 Windows 10 1809+ 版本。如果不可用，请手动下载安装：
- Python: https://www.python.org/downloads/
- Git: https://git-scm.com/download/win

### Q: y3-lualib 克隆失败？

A: 检查网络连接。GitHub 访问困难时使用 Gitee 镜像：
```bash
git clone https://gitee.com/tsukiko/y3-lualib.git y3
```

或配置 Git 代理：
```bash
git config --global http.proxy http://127.0.0.1:7890
```

### Q: 初始化配置.bat 运行失败？

A: 确保：
1. 当前目录是 `maps/EntryMap/script/y3`
2. 以管理员权限运行（如果提示权限不足）
3. 检查 bat 文件是否存在：`dir 初始化配置.bat`

### Q: VSCode 插件 y3-helper 找不到？

A: 在 VSCode 扩展市场搜索 `sumneko.y3-helper`，注意是 `sumneko` 作者发布的。

### Q: 已有项目没有 script 目录？

A: 检查是否为新建项目，可能需要在 Y3 编辑器中先创建地图。

### Q: 在 Lua 中使用的模型与特效无法显示？

A: 模型资源是动态下载的，需要在表格编辑器中新建表格，填入使用的模型或特效资源 ID 进行声明。

---

## 📚 y3-lualib 工程结构

```
📦 y3/
├── 📁 演示/          ← 演示代码
├── 📁 game/          ← 游戏功能实现
│    ├── 📜 const.lua         ← 常量与枚举
│    ├── 📜 game.lua          ← 游戏功能接口
│    ├── 📜 helper.lua        ← 常用胶水功能
│    ├── 📜 py_converter.lua  ← 引擎对象转换
│    └── 📜 py_event_subscribe.lua ← 事件绑定
├── 📂 meta/          ← API 元文件
├── 📂 object/        ← Lua 对象实现
│    ├── 📁 editable_object/  ← 物编对象
│    ├── 📁 runtime_object/   ← 运行时对象
│    └── 📁 scene_object/     ← 场景对象
├── 📂 tools/         ← Lua 工具
├── 📜 debugger.lua   ← 调试器配置
└── 📜 init.lua       ← Y3 库入口
```

---

*此 Skill 为一次性使用，完成后自动标记。*
