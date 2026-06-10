# 与 `scene_merge_tool` 的差异说明

> 参考来源：`E:\projects\y3_map\tools\scene_merge_tool\main.py`

## 工具定位差异

| 维度 | scene_merge_tool | y3-terrain-template |
|---|---|---|
| 目标 | 美术 A 全场景同步到逻辑 B（一次性、整工程对拷） | 把任意关卡的「地编」打包入库 + 模板可重复应用到任意关卡 |
| 触发方式 | `MergeScene.bat` 双击 | Skill 编排（Agent 调用 Python + MCP） |
| 编辑器联动 | 无 | `save_editor` → `resize_terrain` → 文件覆盖 → `restart_editor` → `import_object_editor` |
| 装饰物物编打包方式 | 文件夹整目录拷贝 | **MCP `export_object_editor` / `import_object_editor` 走 zip** |
| 目录组织 | src/dst 两个 Y3 工程根 | 模板库 `library/<模板名>/` + 目标关卡 |

## 文件清单差异

`scene_merge_tool` 的 `FILES` 共 15 项，本 Skill 裁剪为 **8 文件 + 1 物编 zip**：

| 文件 / 条目 | scene_merge_tool | 本 Skill |
|---|---|---|
| `terrain.json` | ✅ 直拷 | ✅ 直拷 |
| `texture.json` | ✅ 直拷 | ✅ 直拷 |
| `terrainedit.json` | ✅ 直拷 | ✅ 直拷 |
| `foliage.json` | ✅ 直拷 | ✅ 直拷 |
| `texturefoliage.json` | ✅ 直拷 | ✅ 直拷 |
| `decorationdata.data` | ✅ 直拷 | ✅ 直拷 |
| `resourceobjectdata.data` | ✅ 直拷 | ✅ 直拷 |
| `grid.data` | （未明确） | ✅ 直拷 |
| `editor/folderinfo/folderinfo_editor_decoration.json` | ✅ 直拷 | 🔁 由 `editor_decoration.zip` 间接覆盖 |
| `editor_table/editordecoration/` | ✅ 整目录直拷 | 🔁 由 `editor_decoration.zip` 间接覆盖 |
| `decal.json` | ✅ | ❌ |
| `engineeffectdata.json` | ✅ | ❌ |
| `envtime.json` | ✅ | ❌ |
| `navimap.data` | ✅ | ❌ |
| `todtemplate.json` | ✅ | ❌ |
| `projectile.json` | ✅ | ❌ |
| `logicres.json`（合并） | ✅ 合并 master 部分 ID | ❌ **完全不动** |

## 行为差异

| 行为 | scene_merge_tool | 本 Skill |
|---|---|---|
| Python 版本 | Python 2（`unicode` / `iteritems` / `print` 语句） | Python 3 |
| 装饰物物编传输 | 文件 / 目录直拷 | **MCP zip 打包**（更贴近编辑器原生导入流程，自动刷新视图 + 自动 save） |
| Dry-run | ❌ | ✅ 默认；必须 `--apply` 才写入 |
| 备份 | ❌ | ✅ 默认到 `<target>/.terrain_template_backup/<时间戳>/` |
| 编辑器版本检查 | ❌ | ✅ `template_meta.json#editor_version` 比对，不一致默认拒绝 |
| 模板元信息 | ❌ | ✅ `template_meta.json` + `readme.md`（脚本固化模板） |
| 用户二次确认 | ❌ | ✅ Skill 强制要求展示 dry-run 后再询问 |
| `logicres.json` 合并 | ✅ 保留 master 部分 ID | ❌ 明确不做 |

## 复用了什么

- **思路**：地形 / 布局类文件走 Python 文件直拷。
- **文件清单交集**：上表 8 个直拷文件。

## 没有复用什么

- `_JsonObjHook` / `hint_tuples`（Y3 tuple-JSON 编码）：本 Skill 只做整文件复制，不解析 JSON 内容（仅 `terrain.json` 的尺寸字段除外，且按二进制头解析）。
- `replace_files_in_folder`（递归目录拷贝）：装饰物物编改走 MCP zip 流程，不再需要递归拷贝。
- `process_logic_res`（合并 `logicres.json`）：明确不复用。
- `MergeScene.bat`：本 Skill 走 Skill 流程，不需要 .bat 入口。
