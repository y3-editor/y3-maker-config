# Y3 编辑器 MCP 功能开发指南

> 基于 `import_editor_fbx_model` 扩展实战总结，覆盖全流程：需求→探查→设计→实施→验证。

---

## 一、开发流程总览

```
需求分析 → 能力探查 → 方案设计 → 实施 → 验证调优
```

---

## 二、能力探查（先确认可行性再动手）

### 2.1 定位工具入口

MCP 工具核心代码位于两个目录（必须保持同步）：

| 路径 | 说明 |
|------|------|
| `E:\map\src\Package\Script\Python\dm\editor\mcp\` | 主源，编辑器实际加载 |
| `E:\map\src\Server\server\engine\dm\editor\mcp\` | Server 副本，linter 自动同步 |

关键文件：
- **`tools.py`** — MCP schema 定义（`TOOLS` 列表）+ 参数校验与 dispatch
- **`handlers/resource_handlers.py`** — 资源类工具实现
- **`handlers/object_handlers.py`** — 物编类工具实现

### 2.2 追踪调用链

从 handler 反向搜索编辑器 GUI 已有的实现路径：

```
MCP handler
  → resource_window.hand_out_import_filesEx()
    → G.custom_res_mgr.loads()
      → model_resource.load_models()
        → engine command（异步）
          → res_call_back（回调）
            → import_end_cb（我们的回调入口）
```

**关键**：用 `grep_search` 追踪方法定义：

```bash
grep "hand_out_import_filesEx"  → 找到 res_import_member.py
grep "def load_models"          → 找到 model_modellib.py
grep "def on_confirm_import_model"  → 找到 fbx_sub_handle.py
```

### 2.3 找参照实现

编辑器 GUI 中已实现的功能就是"能力证据"。本次开发参照了 `ai_model_gen_dialog.py:1190-1203` 的 **silent import** 模式：

```python
# 标准套路：设置回调 + 静默导入（不弹 GUI 对话框）
import_para = ResImportParam()
import_para.import_end_cb = callback
import_para.silent_import = True
resource.param = import_para
resource_window.hand_out_import_filesEx(file_list, editor_type, group_key)
```

> **准则**：MCP 只是薄封装，**绝不发明新能力**。GUI 能做的，MCP 必能做。

---

## 三、方案设计

### 3.1 参数设计原则

| 原则 | 做法 |
|------|------|
| 参数最小化 | 复杂配置用 JSON 文件路径传递，避免 MCP schema 膨胀 |
| 向后兼容 | 新参数设为可选（`required` 不包含它） |
| 复用已有能力 | 调用 `G.custom_res_mgr.xxx` 系列方法，而非自己写 |

### 3.2 核心接口速查

```python
# 模型导入
G.custom_res_mgr.get_resource('custom_editor_model')
G.custom_res_mgr.get_model_import_mat_choose_list()
G.custom_res_mgr.custom_repository.get_model_material(model_keyid)

# 贴图
G.custom_res_mgr.import_material_texture(mat_index, layer_index, icon_path, key_id, tex_type)
# tex_type: ModelTextureType.TEX_D (tBaseMap) / TEX_M (tMixMap) / TEX_N (tNormalMap)

# 动画
G.custom_res_mgr.import_animation(anim_file, model_keyid, anim_name)
G.custom_res_mgr.model_resource.rename_anim(model_conf, old_name, new_name)

# 确认写入
G.custom_res_mgr.model_resource.on_confirm_import_model(...)
```

### 3.3 贴图类型与命名约定

| JSON key | ModelTextureType | 引擎纹理槽 |
|----------|-------------------|------------|
| `diffuse` | `tBaseMap` | 漫反射/基础色 |
| `metallic` | `tMixMap` | 金属度/粗糙度 |
| `normal` | `tNormalMap` | 法线贴图 |

材质名与 JSON mesh name 做**双向子串匹配**，附加**索引后备**避免完全失配。

---

## 四、实施规范

### 4.1 修改 `tools.py`

**Schema 定义**（在 `TOOLS` 列表中）：
```python
{
    "name": "import_editor_fbx_model",
    "description": "...支持通过 resource_map_json 批量导入贴图和动画。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "fbx_path": { ... },
            "resource_map_json": {
                "type": "string",
                "description": "可选。资源映射 JSON 文件绝对路径。",
            },
        },
        "required": ["fbx_path"],
    },
},
```

**Dispatch 逻辑**（在 `if name == 'import_editor_fbx_model':` 分支）：
```python
resource_map_json = args.get("resource_map_json", None)
Timer.addTimer(0.1, lambda: resource_handlers.import_editor_fbx_model(fbx_path, resource_map_json))
```

### 4.2 修改 `handlers/resource_handlers.py`

**必需 imports**：
```python
import json
import MType
from clients.consts.custom_res_const import ModelTextureType
from clients.custom_res.custom_repository import MaterialInfo, MaterialLayer
from clients.custom_res.handle.custom_resource_handle import ResImportParam
```

**函数结构**：
```python
def import_editor_fbx_model(fbx_path, resource_map_json=None):
    if resource_map_json:
        return _import_fbx_with_resource_map(...)
    # 原有逻辑不变

def _load_resource_map(json_path):       # JSON 解析
def _import_fbx_with_resource_map(...):  # silent import + 回调
```

### 4.3 缓存清理（关键！）

修改 `.py` 后**必须清理 `.pyc`**，否则重启仍加载旧字节码：

```cmd
del /q "E:\map\src\Package\Script\Python\dm\editor\mcp\__pycache__\*.pyc"
del /q "E:\map\src\Package\Script\Python\dm\editor\mcp\handlers\__pycache__\*.pyc"
del /q "E:\map\src\Server\server\engine\dm\editor\mcp\__pycache__\*.pyc"
del /q "E:\map\src\Server\server\engine\dm\editor\mcp\handlers\__pycache__\*.pyc"
```

### 4.4 语法预检查

写入后立即编译验证：
```cmd
py -3 -c "import py_compile; py_compile.compile(r'<绝对路径>', doraise=True)"
```

避免重启编辑器后才发现 SyntaxError 导致 MCP 全部不可用。

---

## 五、验证调优

### 5.1 分层验证

| 层 | 方法 | 注意事项 |
|----|------|----------|
| Schema 生效 | `search_tool("xxx")` | 有缓存，实际以调用返回为准 |
| 参数校验 | 传假路径触发 Error 分支 | 确认 dispatch 走了新路径 |
| 业务结果 | 检查磁盘产物 | 模型 → `custom/Char/{id}/` |
| 集成效果 | 编辑器内目视 | 确认模型不白模、动画可播放 |

### 5.2 日志与调试

| 方式 | 适用场景 |
|------|----------|
| `print()` | 同步代码打印，简单可靠 |
| 写文件 `open('debug.log', 'w')` | 异步回调调试，确认 callback 到达位置 |
| 检查产物 | 看 `custom/Char` 目录内容判断动画/贴图是否生成 |

> ❌ **避免 `G.logger.info(msg_format, key=val)`**：当 `msg_format` 已为格式化字符串且 `prefix` 等关键字参数无对应位置参数时，会触发 `IndexError: tuple index out of range`。

### 5.3 时序陷阱

```
MCP 调用 → Timer → handler 执行 → hand_out_import_filesEx（异步）
  → 引擎处理 FBX（耗时）
  → res_call_back（所有导入完成时）
  → import_end_cb（我们的回调）
  → 导入贴图 / 导入动画 / 重命名 / confirm
```

> **MCP 返回 ≠ 导入完成**。必须在 callback 内做后续操作，MCP 调用返回后立即检查磁盘会看到未完成状态。

### 5.4 异步回调可用模式

```python
def on_import_done(editor_type, id_list):
    model_id = id_list[0]
    model_keyid = model_data.get('model_id', model_id)

    # 1. 贴图 — import_material_texture（同步 TCP）
    for mat in materials:
        import_material_texture(mat_index, layer_index, full_path, model_keyid, tex_type)

    # 2. 动画 — import_animation（同步 TCP）
    for anim in anim_files:
        import_animation(anim_file, model_keyid, anim_name)

    # 3. 后处理 — rename_anim 等
    rename_anim(model_conf, old_name, new_name)

    # 4. 确认写入
    on_confirm_import_model(...)

    # 5. 日志
    print("imported: model %s" % model_id)
```

---

## 六、避坑清单

| 陷阱 | 现象 | 对策 |
|------|------|------|
| **缩进混乱** | linter 反复打破 tab/空格 | 复杂段用 `write` 整段重写，不用多次 `edit` |
| **`.pyc` 缓存** | 改代码重启无效 | 每次修改后清 `__pycache__` |
| **Logger 崩溃** | `IndexError` 导致整个 callback 中断 | 用 `print()` 或写文件，不用 `G.logger.info(...)` |
| **异步回调静默失败** | 不知道 callback 跑没跑 | 在回调起始和关键分支写文件日志 |
| **文本匹配失败** | 贴图/动画未绑定 | 双向子串匹配 + 索引后备兜底 |
| **语法错误全 MCP 不可用** | 所有调用 `fetch failed` | 改完立刻 `py_compile` 预检查 |
| **`write` 全文改写丢代码** | 误删无关函数 | `write` 前必须 `read_file` 完整内容 |

---

## 七、完整调用示例

```python
# 基础导入（向后兼容）
import_editor_fbx_model(fbx_path="D:/models/character.fbx")

# 带资源映射的批量导入
import_editor_fbx_model(
    fbx_path="C:/assets/model.fbx",
    resource_map_json="D:/config/resource_map.json"
)
```

### 资源映射 JSON 格式

```json
{
  "model_name": "模型名称",
  "base_path": "C:/assets/",
  "anim_path": "C:/assets/anim/",
  "model_file": "model.fbx",
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
        { "file": "idle.FBX", "variant": "默认待机" }
      ]
    }
  }
}
```

### 导入后操作

```
MCP 调用 → 自动完成模型+贴图+动画+重命名+confirm → 调用 save_editor 落盘
```

---

## 八、本次交付物

| 模块 | 变更 |
|------|------|
| `tools.py` | `import_editor_fbx_model` 增加 `resource_map_json` 可选参数 |
| `resource_handlers.py` | 新增 `_load_resource_map` / `_import_fbx_with_resource_map` |
| `SKILL.md` | §5.2 扩展为完整 JSON 驱动导入文档 + FAQ 更新 |

**新增能力**：单次 MCP 调用完成 FBX 模型 + 多 mesh 贴图（D/M/N）+ 多动画的批量导入，并自动重命名关键动画匹配默认 graph。

---

## 九、后续迭代方向

1. **动画重命名映射外置** — 目前硬编码 `idle→idle1`，放入 JSON 由用户配置
2. **返回结构化结果** — 目前返回文本，改为返回 `{model_id, anim_count, tex_count}`
3. **失败回滚** — 贴图/动画部分失败时清理已生成的 skeleton
4. **进度反馈** — 批量导入时通过日志或轮询告知进度
5. **纹理压缩选项** — 支持 `none_compression` / `no_mip` 等参数透传
