# 地编模板必含条目清单

> 导出 / 导入脚本必须以本表为唯一权威。
> 本 Skill 当前为 **format_version = 2**：装饰物物编通过 MCP `export_object_editor` / `import_object_editor` 走 zip 打包，不再直接复制 `editor_table/editordecoration/` 目录树。

## 必含条目（强制、不可缺、不可选）

### 8 个文件直拷条目（地形 / 纹理 / 植被 / 布局 / 碰撞）

| # | 相对路径 | 类型 | 说明 |
|---|---|---|---|
| 1 | `terrain.json` | file | 地形几何（高度图、悬崖、地块基础类型） |
| 2 | `texture.json` | file | 地面纹理层（贴图映射、各层权重） |
| 3 | `terrainedit.json` | file | 地形编辑历史（撤销信息） |
| 4 | `foliage.json` | file | 植被（草、树等） |
| 5 | `texturefoliage.json` | file | 纹理植被混合数据 |
| 6 | `decorationdata.data` | file | 装饰物**布局**数据（每个实例摆放位置 / 旋转 / 缩放） |
| 7 | `resourceobjectdata.data` | file | 资源摆件数据 |
| 8 | `grid.data` | file | 碰撞格子信息（地形碰撞 / 通行性，与装饰物布局对齐） |

### 1 个物编 zip 条目（装饰物物编数据 + 编辑器分组）

| # | 相对路径（仅模板内） | 类型 | 说明 |
|---|---|---|---|
| 9 | `editor_decoration.zip` | zip | 由 MCP `export_object_editor(object_types=["editor_decoration"])` 产出，包含装饰物物编 JSON 表（原 `editor_table/editordecoration/`）以及装饰物 folderinfo（原 `editor/folderinfo/folderinfo_editor_decoration.json`）。导入时通过 MCP `import_object_editor(zip_path=...)` 应用到目标关卡 |

> ⚠️ `editor_decoration.zip` **只存在于模板目录**，永远不应出现在 Y3 关卡目录中；它的内容是被 MCP 解压回关卡的。

## 禁止纳入清单（导入脚本检测到将报错「模板被污染」）

| 文件 | 不纳入理由 |
|---|---|
| `logicres.json` | 逻辑资源 ID 表，跨工程合并会污染目标关卡逻辑层 |
| `navimap.data` | 寻路网格，由地形重新计算即可 |
| `engineeffectdata.json` | 引擎特效，属逻辑层 |
| `envtime.json` | 环境时间设置，与地编正交 |
| `todtemplate.json` | 昼夜循环模板 |
| `projectile.json` | 投射物，属逻辑层 |
| `decal.json` | 地面贴花，本期不含 |

## 模板内固定附件

| 文件 | 说明 |
|---|---|
| `template_meta.json` | 模板元信息（name / size / editor_version / format_version=2 / files / decoration_bundle） |
| `readme.md` | 人读说明 + 风险提示 |

## 备注

- 8 个直拷文件保留与 Y3 关卡相同的相对路径结构（不扁平化），便于导入时按相对路径直接覆盖。
- `editor_decoration.zip` 是 MCP 产物，**不要**手动解开/重打包；如需修改装饰物物编，请通过 `y3-obj-edit` 在源关卡中编辑后重新导出整个模板。
- 文件清单变更必须先改 spec，再改本文件，再改脚本中的 `_common.py` 常量。
