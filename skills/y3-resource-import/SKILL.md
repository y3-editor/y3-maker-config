---
name: y3-resource-import
description: |
  Y3 编辑器资源导入助手。覆盖官方资源查询、下载到本地工程、本地文件导入编辑器三大场景。

  支持 4 类资源：模型、特效、图标、声音，以及物编批量导入。
  核心 MCP 工具矩阵：
  - 查询：get_official_editor_*（按 ID 查详情 / 素材联想配套）
  - 下载：download_editor_*_resource（批量下载官方资源到本地）
  - 导入：import_editor_icon / import_editor_fbx_model / import_mdx / import_object_editor

  ALWAYS use this skill when user mentions:
  导入资源、下载模型、下载特效、下载图标、下载声音、导入模型、导入图标、导入物编、
  查询官方资源、官方模型、官方特效、官方图标、官方声音、资源下载、素材下载、
  import resource、download model、download effect、download icon、download sound。
---

# y3-resource-import

Y3 编辑器资源导入全流程：**查询官方库 → 下载到本地 → 导入自定义文件**。

## 1. MCP 工具速查

### 查询类（仅读，无副作用）

| 工具 | 参数 | 说明 |
|------|------|------|
| `get_official_editor_model` | `ID: int` | 按 ID 查官方模型详情（名称/类型/标签） |
| `get_official_editor_effect` | `ID: int` | 按 ID 查官方特效详情 |
| `get_official_editor_icon` | `ID: int` | 按 ID 查官方图标详情 |
| `get_official_editor_sound` | `ID: int` | 按 ID 查官方声音详情 |
| `get_official_resource_associate_match` | `ID: int`, `resource_type: "模型"/"声音"/"特效"/"图标"` | 按 ID + 类型查素材联想与配套资源 |

### 下载类（官方库 → 本地工程）

| 工具 | 参数 | 说明 |
|------|------|------|
| `download_editor_model_resource` | `editor_model_id_list: int[]` | 批量下载官方模型 |
| `download_editor_effect_resource` | `editor_effect_id_list: int[]` | 批量下载官方特效 |
| `download_editor_icon_resource` | `editor_icon_id_list: int[]` | 批量下载官方图标 |
| `download_editor_sound_resource` | `editor_sound_id_list: int[]` | 批量下载官方声音 |

### 导入类（本地文件 → 编辑器）

| 工具 | 参数 | 说明 |
|------|------|------|
| `import_editor_icon` | `image_path: str` | 本地图片 → 编辑器图标。支持 png/jpg/tga/bmp/dds/webp |
| `import_editor_fbx_model` | `fbx_path: str`, `resource_map_json?: str` | 本地 FBX → 编辑器模型。可选传入 resource_map_json 自动绑定贴图和动画 |
| `import_mdx` | `mdx_path: str`, `war3_path: str` | 本地 MDX + War3 资源库路径 → 编辑器模型 |
| `import_object_editor` | `zip_path: str` | ZIP 物编批量导入（含单位/技能/Buff/物品/投射物） |

> ⚠️ **所有路径参数必须使用绝对路径**（如 `D:/assets/model.fbx`）。

## 2. 核心工作流

```
用户需求
  ├─ "查某个官方模型/特效/图标/声音"
  │     └→ §3 查询流程
  ├─ "下载官方资源"
  │     └→ §4 下载流程
  ├─ "导入本地模型 (FBX + 贴图 + 动画)"
  │     └→ §2.1 先构建 resource_map JSON → §5 导入流程
  └─ "我想找配套资源 / 素材联想"
        └→ §6 配套查询
```

### 2.1 构建 resource_map JSON（导入前强制）

**任何 FBX 模型导入前，必须先生成 `resource_map.json`**，包含三类信息：

```json
{
  "model_file": "xxx_combined.fbx",
  "meshes": [
    {
      "name": "mesh_01",
      "textures": {
        "diffuse":  "xxx_01_d.tga",
        "metallic": "xxx_01_m.tga",
        "normal":   "xxx_01_n.tga"
      }
    }
  ],
  "animations": [
    { "file": "anim/attack.FBX",  "type": "attack" },
    { "file": "anim/idle.FBX",    "type": "idle" },
    { "file": "anim/run.FBX",     "type": "run" }
  ]
}
```

| 字段 | 必需 | 说明 |
|------|------|------|
| `model_file` | ✅ | FBX 文件名（不含目录） |
| `meshes` | ✅ | 子网格列表，每个绑定 D/M/N 贴图三元组 |
| `animations` | ❌ | 动画文件列表，可选 |
| `animations[].type` | ❌ | 动画类型标签（idle/run/attack/cast/death/spawn） |

**流程**：
```
1. list_files_recursive 扫描用户指定目录
2. 识别 FBX 模型、TGA 贴图（D/M/N 后缀）、动画 FBX
3. 按 _01/_02 后缀分组 mesh，按文件名分类动画
4. 写入 .codemaker/skills/y3-resource-import/temp/<name>_resource_map.json
5. ⚠️ ask_user_question 展示 meshes + animations 清单，确认后进入 §5
```

**约定**：
- 贴图后缀 `_d` = Diffuse, `_m` = Metallic, `_n` = Normal
- `_01` / `_02` 表示同一模型内不同子网格
- 动画按文件名分类 (attack/run/idle/cast...)

### 2.2 动画命名规则（图匹配 graph）

**编辑器预设 graph 只识别 3 个标准动画名：**

| 标准名 | 用途 | FBX 常见别名（自动改名） |
|--------|------|------------------------|
| `walk` | 移动 | run, run_anim, run1, move, running |
| `die` | 死亡 | death, death1, dead, dying |
| `idle1` | 待机 | idle, idle_anim, stand, stand1 |

> ⚠️ **variant 必须直接用标准名（`idle1`、`walk`、`die`）**，不要依赖代码改名。其他动画（attack 等）保持原名通过物编引用。

## 3. 查询流程（查官方资源详情）

### 触发词
"查一下模型 1001" / "这个特效是什么" / "官方图标 2001 详情"

### 流程

```
1. 确认资源类型 + ID
2. 调用对应 get_official_editor_* 查询详情
3. 输出结果（名称 / 类型 / 标签）
4. 询问是否需要下载（→ §4）或查配套资源（→ §6）
```

### 示例

```
用户: 查一下官方模型 1001

AI:
  1. 调用 get_official_editor_model(ID=1001)
  2. 输出: 模型 1001 — 名称: "xxx", 类型: "单位模型", 标签: ["建筑", "中世纪"]
  3. 询问: 需要下载这个模型吗？还是查一下配套资源？
```

## 4. 下载流程（官方资源 → 本地工程）

### 触发词
"下载模型 1001,1002,1003" / "下载这几个特效" / "帮我把这些图标下到工程里"

### 流程

```
1. 收集资源 ID 列表（用户提供 或 来自 §3 查询结果）
2. ⚠️ 必须先用 ask_user_question 确认：
   - 资源类型 + ID 列表 + 数量
   - 下载是异步操作，确认后不可撤销
3. 调用 download_editor_*_resource 批量下载
4. 等待下载完成（无需手动确认，工具自带同步等待）
5. 调用 y3editor.save_editor 保存工程
```

### 卡点 prompt

```
确认下载以下 <N> 个<资源类型>到当前工程？

  ID 列表: <id1>, <id2>, <id3> ...

  [ ] 确认下载
  [ ] 取消
```

### 注意事项

| 项目 | 说明 |
|------|------|
| 批量 | 单次最多传多少由 MCP 决定，大批量建议分批 |
| 重复下载 | 已下载的 ID 重复下载会覆盖，通常无副作用 |
| 保存 | 下载完成后必须 `save_editor`，否则 GMP 未落盘 |

## 5. 导入流程（本地文件 → 编辑器）

### 5.1 导入图标（import_editor_icon）

```
触发: "把这张图导入为图标" / "导入 icon"
参数: image_path — 本地图片绝对路径
支持: png / jpg / tga / bmp / dds / webp
```

流程：
```
1. 确认图片路径存在（read_file 试探）
2. 调用 import_editor_icon(image_path="D:/xxx/icon.png")
3. 等待导入完成 → save_editor
```

### 5.2 导入 FBX 模型（import_editor_fbx_model）

```
触发: "导入这个 FBX 模型" / "把 xxx.fbx 导入编辑器"
参数:
  - fbx_path — FBX 文件绝对路径（必填）
  - resource_map_json — 资源映射 JSON 绝对路径（强烈建议，绑定贴图和动画）
```

#### ⚠️ 强制流程：先建 JSON → 确认 → 导入

```
1. 执行 §2.1 流程，构建 resource_map.json
2. ask_user_question 展示 meshes + animations 清单，用户确认
3. 调用 import_editor_fbx_model(
       fbx_path="D:/xxx/model.fbx",
       resource_map_json="D:/xxx/resource_map.json"
     )
4. 后台异步执行，完成后自动保存：
   a. 静默导入主体 FBX
   b. 按 mesh name 子串匹配材质，逐层替换贴图
   c. 逐文件导入动画（idle→idle1, run→walk, death→die 自动重命名）
   d. on_confirm_import_model 确认并写盘
```

> ❌ **禁止跳过 JSON 步骤直接导入。** 没有 resource_map_json 会导致贴图和动画丢失。

#### 资源映射 JSON 格式

```json
{
  "model_name": "模型显示名称",
  "base_path": "模型及贴图所在目录",
  "anim_path": "动画文件所在目录（可选，默认同 base_path）",
  "model_file": "主体模型文件名",
  "meshes": [
    {
      "name": "mesh_01",
      "textures": {
        "diffuse":  "tex_01_d.tga",
        "metallic": "tex_01_m.tga",
        "normal":   "tex_01_n.tga"
      }
    }
  ],
  "animations": {
    "idle": {
      "desc": "待机",
      "files": [
        { "file": "idle.FBX", "variant": "默认待机" },
        { "file": "idle_alt.FBX", "variant": "特殊待机" }
      ]
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| `model_name` | 编辑器内显示的模型名称 |
| `base_path` | 贴图文件路径的基准目录 |
| `anim_path` | 动画 FBX 文件路径，未填则用 base_path |
| `meshes[].name` | 用于材质子串匹配，需与 FBX 内材质名对应 |
| `meshes[].textures.diffuse` | 漫反射贴图 (-d) → tBaseMap |
| `meshes[].textures.metallic` | 金属度贴图 (-m) → tMixMap |
| `meshes[].textures.normal` | 法线贴图 (-n) → tNormalMap |
| `animations.*.files[].file` | 动画 FBX 文件名，路径 = anim_path + file |
| `animations.*.files[].variant` | 动画在编辑器中的显示名称 |

> ⚠️ `meshes[].name` 与 FBX 内材质名做子串匹配（如 mesh_01 匹配 Material_01）。贴图文件名包含对应 mesh 标记（如 `_01_`）即可正确匹配。

### 5.3 导入 MDX 模型（import_mdx）

```
触发: "导入 War3 MDX 模型" / "把 xxx.mdx 转成编辑器模型"
参数:
  - mdx_path — MDX 文件绝对路径
  - war3_path — War3 基础资源仓库路径（如 "e:/war3"）
```

流程：
```
1. 确认 MDX 路径存在
2. 确认 War3 资源路径（如用户未提供，必须询问）
3. 调用 import_mdx(mdx_path="...", war3_path="...")
4. 等待导入完成 → save_editor
```

> ⚠️ MDX 导入依赖 War3 贴图资源，war3_path 不正确会导致贴图缺失。

### 5.4 导入物编 ZIP（import_object_editor）

```
触发: "导入物编包" / "把这个物编 ZIP 导入工程"
参数: zip_path — ZIP 文件绝对路径
```

**⚠️ 强制串行约束（同 import_ui，见 mcp-rules.mdc）：**

```
1. y3editor.import_object_editor(zip_path="D:/xxx/editor_export.zip")
   ↓
2. ⛔ 暂停所有 MCP 调用，使用 ask_user_question 询问：
   "已请求导入物编 ZIP，请在 Y3 编辑器中确认导入完成后回复"
   options:
     - "已完成，继续"
     - "导入失败 / 编辑器报错"
   ↓
3. 等待用户明确回复
   ├─ 已完成 → y3editor.save_editor
   └─ 失败   → 中止，输出错误
```

> ⚠️ import_object_editor 是异步协程，**必须等用户手动确认**后再 save_editor。禁止用 Sleep 替代用户确认。

## 6. 配套查询（素材联想）

### 触发词 "查一下模型 1001 的配套资源"

### 流程

```
1. 确认资源 ID + 类型
2. 调用 get_official_resource_associate_match(ID=1001, resource_type="模型")
3. 输出配套资源清单（关联模型/特效/图标/声音的 ID + 名称）
4. 询问是否需要下载配套资源
```

## 7. 完整资源替换工作流（综合场景）

当用户说要"替换某个单位的模型/特效/图标/声音"时：

```
1. 查目标单位当前使用的资源 ID（get_editor_unit_custom_data）
2. 查新资源 ID（get_official_editor_* 或用户提供）
3. 若新资源未下载 → §4 下载流程
4. 修改物编字段指向新资源 ID（y3-obj-edit 的 modify 脚本）
5. hotfix_object_editor → 等 3s → save_editor
```

> 物编修改部分委托给 `y3-obj-edit` skill，本 skill 仅负责步骤 2-3。

## 8. 安全规则

| 规则 | 说明 |
|------|------|
| **绝对路径** | 所有文件路径必须绝对路径，禁止相对路径 |
| **下载前确认** | 下载操作前必须 `ask_user_question` 确认 ID 列表 |
| **导入后保存** | 所有 import 操作完成后必须 `save_editor` |
| **物编导入串行** | `import_object_editor` 后必须等用户手动确认，不可连发 |
| **路径校验** | import_editor_* 调用前先确认文件存在 |
| **不臆造 ID** | 官方资源 ID 必须来自 get_official_* 查询或用户提供，禁止猜测 |

## 9. 与其他 Skill 的关系

| 场景 | 本 skill | 委托 skill |
|------|---------|-----------|
| 查询/下载/导入资源 | ✅ 全部 | — |
| 修改物编指向新资源 | 仅查询/下载资源 ID | `y3-obj-edit` 负责修改物编字段 |
| 物编 ZIP 完整替换 | 仅导入 ZIP | `y3-obj-edit` 负责导出 ZIP |
| 地形模板导入（含资源摆件） | — | `y3-terrain-template` |
| UI 导入 .upui | — | `y3-ui-pipeline`（`import_ui`） |

## 10. 常见问题

### Q: 下载的模型在哪里能看到？

A: 下载后模型进入编辑器资源库，可在物编中引用（单位 `model` 字段等），也可通过 `y3-editor` MCP 的 `get_official_editor_model` 验证。

### Q: 导入的图标/模型 ID 是什么？

A: import_editor_* 导入后编辑器自动分配 ID，可在编辑器资源管理器中查看。目前 MCP 无直接返回 ID 的能力，建议导入后让用户在编辑器中确认。

### Q: 如何批量导入模型的贴图和动画？

A: 使用 `resource_map_json` 参数，传入资源映射 JSON 文件。编辑器会按配置自动将贴图替换到对应材质层、导入动画文件并绑定。详见 §5.2 扩展流程。

### Q: MDX 导入报错 / 贴图丢失？

A: 检查 `war3_path` 是否正确指向 War3 安装目录（含 `war3.mpq` 或解包后的贴图目录）。贴图路径大小写敏感时也可能导致丢失。

### Q: 下载/导入需要多长时间？

A: 取决于资源大小和网络。小图标秒级，大型模型/特效可能数秒到数十秒。下载工具自带同步等待，导入工具需用户确认异步完成。

---

*最后更新: 2026-07-28*
