---
name: y3-terrain-template
description: |
  Y3 地编模板导出 / 导入工具集。把任意 Y3 关卡的「地形 + 装饰物 + 资源摆件」打包入库，或把库中模板还原到目标关卡。

  ALWAYS use this skill when user mentions: 导出地编、保存地编模板、打包地编、地编模板、地编入库、
  导入地编、应用地编模板、还原地编、套用地形模板、复制地形到其它关卡、地编复用。

  This skill packages and applies terrain art assets (terrain, texture, foliage, decorations, resource objects)
  between Y3 maps via Python scripts + MCP calls (save_editor / resize_terrain / restart_editor /
  export_object_editor / import_object_editor).
  It does NOT generate terrain (use y3-gen-terrain-from-image), and does NOT touch logic, Lua, UI, or non-decoration object data.
---

# y3-terrain-template

Y3 地编模板的「打包 / 还原」Skill。

## 0. 单一职责边界（强约束）

本 Skill **只做**「把一个关卡的地编原样搬到另一个关卡」。

| 维度 | 是否做 | 备注 |
|---|---|---|
| 地形几何 / 纹理 / 植被 整体覆盖 | ✅ | 8 文件清单，见 `references/file_manifest.md` |
| 装饰物布局 / 资源摆件布局 整体覆盖 | ✅ | `decorationdata.data` + `resourceobjectdata.data` |
| 装饰物**物编数据**（含编辑器分组） | ✅ | 通过 MCP `export_object_editor` / `import_object_editor` 走 zip 打包 |
| 碰撞信息（`grid.data`）整体覆盖 | ✅ | 与装饰物 / 地形布局严格对齐，不可单独裁剪 |
| 地形**生成**（图 → 地形） | ❌ | 用 `y3-gen-terrain-from-image` |
| 物编（除装饰物外） / Lua / UI / `logicres.json` / 寻路 / 特效 | ❌ | **禁区**，见第 6 节 |
| 区域偏移 / 子区域裁剪 / 局部融合 | ❌ | 本期仅整图覆盖，见第 7 节 |
| 自动回滚 | ❌ | 由备份目录兜底，用户责任手工回滚 |

## 1. 核心流程框图

```
┌──────────────────────────────────────────────────────────────────────┐
│   导出（编辑器需开着源关卡）                                         │
├──────────────────────────────────────────────────────────────────────┤
│   Step 1  MCP export_object_editor → editor_decoration.zip           │
│           （object_types=["editor_decoration"], 输出到临时目录）     │
│   Step 2  python export_terrain_template.py --decoration-zip <...>   │
│           ├─ 校验 8 文件 + 校验 zip 合法                             │
│           ├─ 解析 terrain.json 尺寸                                  │
│           ├─ 复制 8 文件 + 拷入 zip → library/<模板名>/              │
│           └─ 写 template_meta.json + readme.md                       │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│   导入（4 MCP + 1 Python，编辑器需开着目标关卡）                     │
├──────────────────────────────────────────────────────────────────────┤
│   1. 读模板 template_meta.json → 取尺寸 (w, h)                       │
│   2. MCP save_editor             ← 保护用户未保存改动                 │
│   3. MCP resize_terrain(w, h)    ← 调整目标关卡尺寸                   │
│   4. MCP import_object_editor(zip_path=…/editor_decoration.zip)       │
│      ← 应用装饰物物编（含自动 save_editor + 物编视图刷新）            │
│      ← 必须先于文件覆盖；否则其内部 save 会反向覆盖磁盘上的新 8 文件   │
│   5. import_terrain_template.py --apply  ← 备份 + 覆盖 8 文件         │
│   6. MCP restart_editor(save_before_restart=false)                    │
│      ← 一次性重启：加载新地形 + 使已有装饰物实例按新物编重渲染        │
│      ← ⚠️ 必须传 save_before_restart=false，否则 restart 默认会先     │
│         save_editor，把内存里的旧 8 文件写回磁盘，反向覆盖 Step 5      │
│                                                                       │
│   ⚠️ 步骤 2 ~ 步骤 6 之间，用户禁止操作编辑器                        │
└──────────────────────────────────────────────────────────────────────┘
```

## 2. 导出工作流

### 2.1 触发场景

用户说「导出地编 / 把这张图的地形保存成模板 / 打包地编」等。

### 2.2 强制 2 步顺序

> ⚠️ 编辑器必须打开**源关卡**；MCP `export_object_editor` 作用在当前打开的地图。

**Step 1 — MCP 产物准备（先于 Python 脚本）**

```
y3editor.export_object_editor(
  output_path     = "<工程根>/.codemaker/skills/y3-terrain-template/library/.export_staging/<模板名>",
  object_types    = ["editor_decoration"],
  output_filename = "editor_decoration.zip",
  include_dependencies = true,
  split_sheet     = true
)
```

> 输出目录建议放在 skill 自有的 `.export_staging/<模板名>/` 下，导出成功后 Skill 应清理该 staging 目录。

**Step 2 — Python 脚本组包**

```bash
python .codemaker/skills/y3-terrain-template/scripts/export_terrain_template.py \
  --map-dir         "<工程根>/maps/<关卡名>" \
  --name            "<kebab-case 模板名>" \
  --description     "<人读说明，写入 readme>" \
  --decoration-zip  "<上一步 MCP 产出的 editor_decoration.zip 绝对路径>" \
  [--force]   # 模板已存在时覆盖
```

### 2.3 stdout 协议

成功：
```json
{"status":"ok","name":"forest-arena-01","size":[256,256],"path":".../library/forest-arena-01","file_count":9}
```

失败：
```json
{"status":"error","reason":"missing required entries: decorationdata.data, ..."}
```
失败时脚本 **会自动清理半成品** `library/<name>/`，无需手工善后。

### 2.4 错误处理指引

| stdout reason 关键词 | 处理 |
|---|---|
| `missing required entries in source map` | 源关卡不是完整 Y3 关卡，或文件被外部删除；告知用户检查关卡完整性 |
| `--decoration-zip not found` | 用户未先跑 MCP `export_object_editor`，或路径错；重新跑 Step 1 |
| `--decoration-zip is not a valid zip archive` | MCP 产出异常或文件被破坏；重新跑 Step 1，保留编辑器日志 |
| `template already exists` | 模板名冲突；询问用户是否 `--force` 覆盖、或换名字 |
| `terrain size unknown` | `terrain.json` 尺寸无法解析；记录到 `python-issues/`，并升级 `_common.read_terrain_size` |
| `invalid name` / `template name must be kebab-case` | 模板名非 kebab-case；告知规则后让用户重命名 |

## 3. 导入工作流

### 3.1 触发场景

用户说「导入地编 / 把 forest-01 模板套到这关 / 还原地编」等。

### 3.2 强制 6 步顺序

> ⚠️ **红字警告**：步骤 2 ~ 步骤 6 之间，**用户禁止操作编辑器**。
> 期间编辑器内的任何手动改动会被步骤 6 重启吞掉，或被步骤 4 内部 save 反向覆盖步骤 5 写入的文件。

```
Step 1  读模板 template_meta.json → 取 (w, h)、读 dry-run 输出的 decoration_zip
Step 2  MCP y3editor.save_editor                     # 保护未保存改动
Step 3  MCP y3editor.resize_terrain(w, h)            # 尺寸先匹配
Step 4  MCP y3editor.import_object_editor(zip_path)  # 先导入装饰物物编（自动 save 物编视图）
Step 5  python import_terrain_template.py --apply    # 备份 + 覆盖 8 个文件
Step 6  MCP y3editor.restart_editor(save_before_restart=false)
                                                      # 一次性重启：加载新地形并使已有装饰物实例按新物编重渲染
                                                      # ⚠️ 必须传 save_before_restart=false（默认 true 会先 save，反向覆盖 Step 5 写盘的新 8 文件）
```

> `zip_path` 取自 dry-run stdout 的 `decoration_zip` 字段（也即模板目录下的 `editor_decoration.zip` 绝对路径）。
>
> 💡 **为什么先 import_object_editor 再覆盖文件**：`import_object_editor` 内部会自动 `save_editor`，把编辑器内存里的 8 文件写回磁盘。若先覆盖文件再调它，会**反向覆盖**磁盘上刚导入的新地形。把文件覆盖（Step 5）放到最后，可彻底规避这个反向覆盖陷阱，并把两次 restart 合并为一次。
>
> 💡 **为什么 Step 6 必须传 `save_before_restart=false`**：`restart_editor` 默认 `save_before_restart=true`，重启前会先调 `save_editor`，把编辑器内存里仍是旧地形的 8 文件写回磁盘，**反向覆盖** Step 5 才写入的新文件。传 `false` 让它直接结束进程、重启时从磁盘加载新文件。
>
> 💡 **为什么 Step 6 restart 必要**：Step 5 只写盘没让编辑器加载；同时 Step 4 仅刷新「物编视图」，地图视图里已存在的装饰物实例不会立刻按新物编重新渲染（模型 / 图标 / 属性等）。最后这次 restart 一并解决两件事。

### 3.3 调用模板

**dry-run（默认，必须先跑）**：
```bash
python .codemaker/skills/y3-terrain-template/scripts/import_terrain_template.py \
  --template "<模板名>" \
  --target-map-dir "<工程根>/maps/<关卡名>"
```

**apply（用户确认后才能跑）**：
```bash
python .codemaker/skills/y3-terrain-template/scripts/import_terrain_template.py \
  --template "<模板名>" \
  --target-map-dir "<工程根>/maps/<关卡名>" \
  --apply \
  [--no-backup]        # 不推荐
  [--ignore-version]   # 编辑器版本不一致时强行放行
```

### 3.4 stdout 协议

```json
{
  "status": "ok" | "dry-run" | "error",
  "files": ["terrain.json", ...],            // 8 文件
  "decoration_zip": "<模板目录下 editor_decoration.zip 绝对路径>",
  "backup_dir": "<absolute path or null>",
  "warnings": ["editor version mismatch ignored", ...],   // 可选
  "reason": "<仅 error 时存在>"
}
```

失败时若 `backup_dir` 已存在，**脚本仍会输出 `backup_dir` 路径**，便于用户手工回滚。
`decoration_zip` 在 error 阶段也会回填，便于 Skill 仍可手动追加 MCP `import_object_editor` 步骤。

## 4. 用户二次确认护栏（强制）

在 `--apply` 之前 Skill **必须**完成以下流程，**不得静默执行**：

```
1. 跑一次 dry-run（不带 --apply）
2. 把以下信息呈现给用户：
   - 模板名 / 模板说明 / 模板尺寸
   - 目标关卡路径
   - 即将被覆盖的 8 文件清单（来自 dry-run 的 files）
   - 即将通过 MCP import_object_editor 覆盖装饰物物编（zip 路径）
   - 默认会创建的备份目录路径（template-backup/<时间戳>/）
   - 风险提示：「装饰物物编 / 资源摆件将被整体覆盖；
                 如目标关卡有针对装饰物 ID 的脚本引用，
                 导入后引用将失效。建议导入前 git commit。」
3. 询问用户：「确认导入？」
4. 用户明确同意 → 进入第 3 节的 6 步顺序
   用户未明确同意 → 停留在 dry-run，不调 resize_terrain，不调 restart_editor，不调 import_object_editor
```

> 💡 **例外**：用户明确说「不用确认 / 直接做 / yolo」可跳过询问，但 dry-run 仍要先跑（用于日志）。

## 5. 模板库与文件契约

详见 `references/file_manifest.md`。**速查**：

- 模板库根：`.codemaker/skills/y3-terrain-template/library/<模板名>/`
- 模板必含 **8 文件 + 1 zip** + `template_meta.json` + `readme.md`
  - 8 文件：`terrain.json`、`texture.json`、`terrainedit.json`、`foliage.json`、`texturefoliage.json`、`decorationdata.data`、`resourceobjectdata.data`、`grid.data`
  - 1 zip：`editor_decoration.zip`（MCP 产物，含装饰物物编 + 装饰物 folderinfo）
- 模板 MUST NOT 包含 `logicres.json` 等禁区文件
- `template_meta.json#format_version` 当前为 `2`（v1 = 直拷目录树形式，已废弃，不再支持导入）

## 6. 禁区清单（Skill MUST NOT 修改）

无论导出还是导入，本 Skill **永不**修改以下任何资产：

| 类别 | 路径 / 文件 | 理由 |
|---|---|---|
| 逻辑资源 | `logicres.json` | 跨工程合并会污染 ID 表 |
| 物编（除装饰物） | 任何 `editor_decoration` 之外的物编类型（unit / ability / modifier / projectile / item / destructible / technology / sound / store） | 物编是独立 Skill 的职责（`y3-obj-edit`） |
| Lua 代码 | `global_script/`、`script/` | 由 `y3-lua-pipeline` 管 |
| UI | 任何 UI JSON | 由 `y3-ui-pipeline` 管 |
| 寻路 | `navimap.data` | 运行时可重建 |
| 特效 / 投射物 / 环境 | `engineeffectdata.json`、`projectile.json`、`envtime.json`、`todtemplate.json` | 属逻辑层 |
| 贴花 | `decal.json` | 本期不含 |

> 验收方法：导入完成后对目标关卡的禁区文件做 hash 比对，必须与导入前完全一致。
> 注：`import_object_editor` 严格限定 `object_types=["editor_decoration"]` 通过模板 zip 中的范围保证，不会牵涉其它物编类型。

## 7. 不在本期范围

| 能力 | 状态 | 备注 |
|---|---|---|
| 子区域裁剪 / 坐标偏移 / 局部融合 | ❌ 不做 | 本期仅整图覆盖；用户请求局部覆盖时明确拒绝 |
| 模板版本管理（hash / diff / history） | ❌ 不做 | YAGNI；用户用 git 管理模板库 |
| 自动回滚 | ❌ 不做 | 由 `.terrain_template_backup/<时间戳>/` 兜底，用户手工恢复 |
| 装饰物 ID 引用前置扫描 | ❌ 不做 | 由 readme 警示 + 备份兜底；未来增强 |
| 缩略图 / 截图随模板存储 | ❌ 不做 | 未来增强（可接 MCP `capture_screenshot`） |
| 跨编辑器版本兼容 | ❌ 不保证 | 模板写入版本号，导入时严格匹配；不一致需 `--ignore-version` 强行放行 |
| v1（目录树）模板兼容导入 | ❌ 不做 | 旧模板需重新走「Step 1 MCP + Step 2 脚本」重新导出 |

## 8. 与其它 Skill 的边界

| 需求 | 该用什么 Skill |
|---|---|
| 从图片生成地形 | `y3-gen-terrain-from-image` |
| 把现成地形从 A 关卡搬到 B 关卡 | **本 Skill** |
| 在编辑器内手动刷地形 / 笔刷 | 直接用编辑器，或调单个 `terrain_*` MCP |
| 写 Lua / 写 UI / 改物编（非装饰物） | `y3-lua-pipeline` / `y3-ui-pipeline` / `y3-obj-edit` |

## 9. 参考资料

- `references/file_manifest.md` — 8 文件 + 1 zip 权威清单
- `references/scene_merge_tool_diff.md` — 与原参考工具 `scene_merge_tool` 的差异
