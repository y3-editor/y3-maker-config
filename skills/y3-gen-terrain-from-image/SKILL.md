---
name: y3-gen-terrain-from-image
description: 从 2D 平面地图图片生成 Y3 编辑器地形。当用户上传一张或多张地图图片（手绘草图、规划图、战略地图等）并希望在 Y3 编辑器中还原这张地图的地形时使用。触发词：从图片生成地形、图片转地形、上传地图图片生成地形、根据图片刷地形、图片生成地图。
---

# Y3 地形图片生成（y3-gen-terrain-from-image）— 精简两轮版

将用户提供的 2D 平面地图图片通过 **两轮读图 → CV + AI 协作 → 生成 CSV → MCP 写入** 流程，还原为 Y3 编辑器中的真实地形。

## 🔄 两轮架构总览

```
原图 ──┬── Round 1: 水域 + 大陆连通分割 + 纹理
       │     ├─ cv_cluster.py (K=15) → 粗聚类
       │     ├─ cv_cluster_analysis.py (K=50) → 增强水域识别
       │     ├─ AI 标水域
       │     ├─ cv_continent_split.py → 大陆分割
       │     ├─ AI 分配纹理
       │     └─ 产出: terrain_grid.csv(final) + texture_grid.csv(final)
       │            water_mask + continent_map
       │
       └── Round 2: 装饰物识别 (v2 混合定位)
             ├─ cv_subregion_analysis.py → 大陆子区域分析
             ├─ AI 逐大陆标注 (fine_clusters / position)
             ├─ decoration_postprocess.py → mask/方位采样
             └─ 产出: decoration_entities.json(final)

最终 → mcp_batch_writer.py → Y3 编辑器
```

### CSV 产出表

| 文件 | Round 1 (final) | Round 2 (final) |
|------|----------------|-----------------|
| terrain_grid.csv | 水域(deep_water)+陆地(ground,h=0) | 不变 |
| texture_grid.csv | 大陆纹理 | 不变 |
| decoration_grid.csv | 不存在 | 桥梁+树木 |

### Mask 体系

| Mask 文件 | 分辨率 | 类型 | 产出轮次 |
|-----------|--------|------|----------|
| water_mask_full.npy | 原图 | bool | Round 1 |
| water_mask_grid.npy | 网格 | bool | Round 1 |
| continent_map_full.npy | 原图 | int32 | Round 1 |
| continent_map_grid.npy | 网格 | int32 | Round 1 |

---

## 🧠 Y3 地形常识（AI 必须遵守）

| # | 常识 | 说明 |
|---|------|------|
| 1 | **AI 看 RGB 判断颜色** | palette.json 中有 `rgb` 字段，AI **必须**使用 `rgb` 字段判断颜色，**禁止**自行从 `bgr` 字段转换 |
| 2 | **CV 只做特征聚类** | CV 做颜色/明度等特征聚类，但不做任何语义判断（不标注水/陆地），所有语义判断由 AI 完成 |
| 3 | **cliff_tex_id 全部默认 0** | 本精简版不做高度映射，无悬崖，cliff_tex_id 统一为 0 |

---

## ⛔ 全局禁令（最高优先级）

| # | 禁令 | 正确做法 |
|---|------|----------|
| 1 | ⛔ **禁止 AI 输出坐标/锚点/多边形** | AI 只定义语义，空间定位由 CV 完成 |
| 2 | ⛔ **禁止 AI 描述区域边界** | 不写"x:10~50, z:20~80"、"左岸锚点"等 |
| 3 | ⛔ **禁止跳过 CV 聚类直接生成 CSV** | 必须先运行对应轮次的 CV 脚本 |
| 4 | ⛔ **禁止跳过 CSV 直接调 MCP** | 必须读 CSV 逐格调 MCP |
| 5 | ⛔ **禁止临时编写 Python 脚本** | 使用 `scripts/` 目录下现有脚本 |
| 6 | ⛔ **禁止跳过用户确认直接生成** | 每轮的 AI 语义分配都需用户确认 |
| 7 | ⛔ **禁止猜测地图尺寸** | 必须从 get_map_info 获取 |
| 8 | ⛔ **禁止跳过 CV 依赖检测** | 没有 opencv/numpy 就不能继续 |
| 9 | ⛔ **MCP 连接失败时禁止继续任何后续步骤** | 必须提示用户连接 y3editor MCP 后重试，不得降级、不得读脚本猜测、不得用 read_map_size.py 替代 |

---

## Stage 0：前置检查

### 0.1 MCP 探活 + 获取地图信息

调用 `get_map_info`（无参数），返回 JSON 包含 `project_path`、`map_name`、`map_path`、`width`、`height`。

**必须将返回的 JSON 保存到 `<output_dir>/map_info.json`**，后续脚本会自动从此文件读取地图尺寸，**AI 不再需要手动传入 width/height 参数**。

```python
import json
map_info = {...}  # get_map_info 返回内容
with open("<output_dir>/map_info.json", "w") as f:
    json.dump(map_info, f, indent=2)
```

若调用失败（MCP 未连接、返回错误、超时等任何异常），**必须立即终止整个流程，禁止继续任何后续步骤**。输出以下提示并等待用户响应：
```
⚠️ 无法连接到 Y3 Editor MCP Server，流程已终止！
请检查：
1. Y3 编辑器是否已打开？
2. y3editor MCP Server 是否已连接？（检查 CodeMaker MCP 面板）
3. 目标地图是否已加载？
确认后告诉我"重新检查"。
```

> 🔴 **严禁降级处理**：不得尝试从 `read_map_size.py`、`terrain.json`、历史缓存或任何其他来源获取地图尺寸。
> `get_map_info` 是获取地图信息的 **唯一合法来源**，连接失败就是失败，没有 Plan B。

### 0.2 CV 依赖检测（静默自动安装）

运行：
```bash
python scripts/check_cv_deps.py
```

脚本会自动检测并在缺失时静默安装依赖，**无需用户介入**。

| 结果 | 处理 |
|------|------|
| `{"status": "ok", ...}` | ✅ **静默继续**，不输出任何信息给用户 |
| `{"status": "missing", "install_failed": true, ...}` | ⚠️ 提示用户："自动安装 `<missing>` 失败，请手动执行 `pip install <missing>` 后告诉我'重新检查'。" |

### 0.3 接收图片

> "请提供地图图片的 **文件路径**（支持 PNG/JPG/WEBP）。图片边界应与地图边界 1:1 对应。
> 你可以直接发送路径，也可以上传图片时附带文件路径。"

**处理逻辑**：
| 情况 | AI 行为 |
|------|---------|
| 用户提供了文件路径（不管有没有同时上传图片） | ✅ 直接使用该路径作为 `<image_path>` |
| 用户只上传了图片，没给路径 | AI 先确认"我看到了你的地图（简述内容）"，然后提示："不过 CV 脚本需要读取磁盘文件才能处理。请告诉我这张图片在磁盘上的路径，或将它保存到 `<skill_dir>/output/input_map.png` 后告诉我。" |

记录 `<image_path>`。

### 0.4 创建工作输出目录

所有轮次的中间文件和最终 CSV **统一输出到** `<skill_dir>/output/` 目录：

```
<dir> = .codemaker/skills/y3-gen-terrain-from-image/output/
```

后续所有脚本的 `--output-dir` 参数统一使用此路径。

> ⚠️ AI **禁止**自行选择其他工作目录（如 `terrain_gen_work/`），必须使用 `<skill_dir>/output/`。

---

## Round 1：水域 + 大陆连通分割 + 纹理

> **目标**：剥离水域，识别大陆连通区域，为每个大陆分配基础纹理。
> **AI Prompt 模板**：`templates/round1_water_continent_prompt.md`

### Step 1.1：CV 色相聚类

```bash
python scripts/cv_cluster.py <image_path> --k 15 --output-dir <dir>
```

输出：
- `cluster_preview.png` — 像素分辨率预览图
- `palette.json` — 每簇 RGB/BGR/HSV + 占比
- `labels.npy` — 高分辨率聚类标签矩阵
- `centers_bgr.npy` — 簇中心 BGR

### Step 1.1b：双重聚类交叉分析（增强水域识别）

在粗聚类(K=15)基础上，新增细聚类(K=50)并做交叉分析，为每个粗簇补充内部纹理复杂度、颜色统计、空间形态等多维特征，帮助 AI 精确区分水域与深色陆地。

```bash
python scripts/cv_cluster_analysis.py <dir>/cropped.png \
  --labels-coarse <dir>/labels.npy \
  --palette <dir>/palette.json \
  --k-fine 50 \
  --output-dir <dir>
```

输出：
- `labels_fine.npy` — K=50 细聚类标签矩阵
- `palette_enhanced.json` — 增强色板（palette.json 超集），每个簇新增：
  - `internal_complexity`: 内部微簇数量、Shannon 熵、主导微簇占比、Top-5 微簇明细(含 RGB)
  - `color_stats`: RGB 标准差、RGB 极差、Laplacian 方差（纹理能量）
  - `spatial_shape`: 紧凑度、长宽比、连通区域数、最大区域占比
  - `border_neighbors`: 边界接触的其他簇 ID 列表

### Step 1.2：AI 标注水域簇

AI 看 `cluster_preview.png` + `palette_enhanced.json`（**使用 `rgb` 字段判断颜色，使用 `internal_complexity` / `color_stats` / `spatial_shape` 辅助判断水域**）+ 原图：

1. 判断哪些簇是水体（蓝色水域、蓝绿色湖泊等）
2. 以表格展示所有簇，标记水域簇，**包含 fine_count、dom_ratio、rgb_std 列**

| 簇 ID | RGB | 占比 | fine_count | dom_ratio | rgb_std | 判断 |
|--------|-----|------|-----------|-----------|---------|------|
| 5 | [30, 80, 120] | 14.6% | 3 | 0.72 | 8.5 | ✅ 水域 |
| 1 | [25, 70, 100] | 4.2% | 2 | 0.81 | 6.2 | ✅ 水域 |
| 8 | [100, 130, 90] | 17.8% | 9 | 0.28 | 31.2 | 陆地 |
| ... | ... | ... | ... | ... | ... | ... |

展示后直接记录 `water_cluster_ids` 列表（如 `[5, 1, 11]`），**无需询问用户确认，直接继续**。

### Step 1.3：CV 大陆连通分割

```bash
python scripts/cv_continent_split.py <dir>/labels.npy --water-clusters 5,1,11 --image <dir>/cropped.png --output-dir <dir>
```

> 🔴 **`--image` 必须传 `cropped.png`（裁剪后的图片），不能传原始图片！**
> `labels.npy` 是基于裁剪后图片聚类的，两者尺寸必须对应。

输入：`labels.npy` + 水域簇 ID 列表 + 裁剪后图片路径（`--image`，推荐传入） + 地图尺寸
处理：
1. 在原图 labels 上将水域簇像素标记为 mask
2. 对非水域像素用 `cv2.connectedComponents` 做连通分割
3. 桥梁碎片过滤
4. 下采样 water_mask 和 continent_map 到网格分辨率

输出：
- `water_mask_full.npy` / `water_mask_grid.npy` — 水域 mask
- `continent_map_full.npy` / `continent_map_grid.npy` — 大陆编号图（0=水域, 1~N=大陆）
- `continent_summary.json` — 各大陆面积、bbox、avg_rgb（传入 `--image` 时含平均 RGB）
- `continent_preview.png` — 大陆分区可视化（不同颜色）

### Step 1.4：纹理分组 + AI 分配纹理（两步法）

#### Step 1.4a：运行脚本自动分组（确定性）

```bash
python scripts/gen_round1_csv.py \
  --water-mask <dir>/water_mask_grid.npy \
  --continent-map <dir>/continent_map_grid.npy \
  --output-dir <dir> \
  --group-only
```

脚本自动完成：
- 读取 `continent_summary.json` 的 `avg_rgb`
- 用 Union-Find 将 RGB 欧氏距离 < 30 的大陆归为同一**纹理组**
- 面积 ≤ 5 的碎片大陆不参与分组（后续自动继承邻近大陆纹理）
- 输出 `texture_groups.json`（含每组的大陆列表、加权 avg_rgb、面积）

> ⛔ **禁止 AI 自己写分组脚本或手动计算距离**，必须调用上述脚本

#### Step 1.4b：AI 按组分配纹理

AI 看 `texture_groups.json` + 原图 + `references/texture-color-map.md`，**为每个 Group 分配一个纹理 ID**：

1. 每个 Group 只需分配 1 个纹理 ID（组内所有大陆共享）
2. 参考 Group 的 `avg_rgb` 在 `texture-color-map.md` 中找最接近的颜色
3. cliff_tex_id 统一使用默认值 0

输出 JSON 格式（key = group_id）：
```json
{
  "1": {"texture_id": 194, "label": "浅灰绿草地"},
  "2": {"texture_id": 109, "label": "灰绿冬草"},
  "3": {"texture_id": 147, "label": "暖棕草地"}
}
```

展示后**无需询问用户确认，直接继续**。

### Step 1.4c：纹理面板确保（自动）

AI 收集 Step 1.4b 中分配的所有纹理 ID，调用 MCP 接口 `ensure_terrain_textures` 自动将缺失纹理添加到编辑器面板：

```
调用 ensure_terrain_textures(texture_ids=[194, 109, ...])
```

**根据返回结果处理**：

| 字段 | 处理 |
|------|------|
| `added` 非空 | ✅ 纹理已自动添加到面板，继续 |
| `failed` 非空 | ⚠️ 面板已满（32个上限），将 failed 中的纹理替换为 `current` 列表中最接近的已有纹理，更新 Step 1.4 的纹理分配 JSON |
| `not_downloaded` 非空 | ⚠️ 提示用户手动下载对应纹理或选择替代纹理 |
| 所有字段正常 | ✅ 直接继续生成 CSV |

> ⚠️ **必须在生成 CSV 之前完成此步骤**，否则 MCP 写入纹理时可能静默失败。

### Step 1.5：水域后处理（自动）

在生成 CSV 之前，运行水域后处理脚本，检测并填回被陆地完全包围的孤立水域：

```bash
python scripts/water_postprocess.py <dir>/water_mask_grid.npy
```

脚本自动完成：
- 连通区分析：检测所有水域连通区是否触碰地图四边
- 被陆地完全包围的水域区域 → 自动填回陆地
- 原地覆盖 `water_mask_grid.npy`
- 输出修复报告（填了几个区域、几格）

> 此步骤为纯几何判定，100% 确定性，零 token 消耗。

### Step 1.6：调用脚本生成 terrain_grid.csv(final) + texture_grid.csv(final)

使用 `--group-texture-config`（推荐，配合 Step 1.4 的组分配）：

```bash
python scripts/gen_round1_csv.py \
  --water-mask <dir>/water_mask_grid.npy \
  --continent-map <dir>/continent_map_grid.npy \
  --group-texture-config '{"1": 194, "2": 109, "3": 147}' \
  --output-dir <dir>
```

> key = Step 1.4b 输出的 group_id，value = 纹理 ID

脚本自动完成：
- 按组展开纹理到所有大陆（同组同纹理）
- 碎片大陆 → 自动继承最近大陆纹理
- **terrain_grid.csv(final)**：水域格→`deep_water,0,0`，陆地格→`ground,0,0`
- **texture_grid.csv(final)**：水域格→`0`，陆地格→对应纹理 ID
- 最终输出纹理种类统计

> ⛔ **禁止 AI 自行编写脚本生成 CSV**，必须调用 `scripts/gen_round1_csv.py`
> ⛔ **禁止跳过 Step 1.4a 的 `--group-only` 分组步骤**，直接用 `--texture-config` 按大陆分配

---

## Round 2：装饰物识别（v3 — 纹理组驱动 + 精确定位）

> **目标**：CV 子区域分析 → AI 逐大陆标注装饰物 + 识别桥梁 → 纹理组匹配模型 → 后处理生成装饰物实体。
> **AI Prompt 模板**：`templates/round2_decoration_prompt.md`
>
> **v3 核心变更**：废弃全局 `style`，改为纹理组驱动模型选择；新增 `tree_cluster`（精确半径）和 `mountain_chain`（连绵山脉）。

### Step 2.0：前置准备（自动化脚本）

#### 2.0.1 生成水域字符地图

```bash
python scripts/gen_water_map.py terrain_grid.csv water_map.txt
```

产出 `water_map.txt`（W=水域 .=陆地 的字符矩阵），AI 在桥梁识别时参考。

#### 2.0.2 CV 大陆子区域分析

```bash
python scripts/cv_subregion_analysis.py \
  <dir>/labels_fine.npy \
  <dir>/continent_map_full.npy \
  <dir>/cropped.png \
  <dir>/water_mask_full.npy \
  <dir>
```

产出：
- `continent_subregions.json` — 每个大陆内部微簇分布（含色差、可分离标记）
- `subregion_preview.png` — 可视化预览图
- `continent_crops/continent_<id>.png` — ⭐ 每个大陆的裁剪放大图（附九宫格网格 + 方位标签）

### Step 2.1：桥梁识别（优先！）

AI 先看原图识别所有桥梁，逐座对照 `water_map.txt` 验证坐标必须落在 `W` 格子上。
桥梁识别必须在装饰物标注之前完成。

### Step 2.2：AI 逐大陆标注装饰物（树木优先）

AI 看原图 + 大陆裁剪图 + `continent_subregions.json`，按照 `templates/round2_decoration_prompt.md` 对每个大陆标注装饰物。

**🌲 树木优先原则**：先找树，后找山。至少 70% 的大陆应标注 tree_cluster。

**两种新类型**：
- **`tree_cluster`**：树丛精确定位。fine_clusters（CV mask 优先）+ position+radius（圆形区域兜底）
- **`mountain_chain`**：连绵山脉。from/to（起止方位）+ count（山峰数量），脚本沿线均匀放置

> ❌ 不再有 `style` 字段，模型选择由脚本根据脚下纹理自动匹配。

输出 JSON（保存为 `decoration_input.json`）：
```json
{
  "continents": {
    "2": {
      "decorations": [
        {"type": "tree_cluster", "density": "normal", "fine_clusters": [17, 20], "position": null, "radius": null},
        {"type": "tree_cluster", "density": "sparse", "fine_clusters": null, "position": "southwest", "radius": 3},
        {"type": "mountain_chain", "from": "northwest", "to": "east", "count": 3}
      ]
    }
  },
  "bridges": [{"x": 33, "z": 10, "yaw": 90}]
}
```

### Step 2.3：纹理组映射（脚本自动完成）

脚本内部加载 `texture_grid.csv` + `references/texture_group_catalog.json`，构建纹理 ID → 纹理组反查表。每个采样点根据脚下纹理自动匹配模型池（草地配绿树，沙漠配枯树/仙人掌，冰雪配松树等）。

### Step 2.4：采样 + 模型分配（脚本自动完成）

- **tree_cluster**：fine_clusters 模式（mask 内泊松采样）或 position+radius 模式（圆形区域采样）
- **mountain_chain**：沿 from→to 线段均匀取点，加 ±1~2 格法线偏移
- 每个采样点按脚下纹理组选模型 + 自动 scale

### Step 2.5：调用后处理脚本生成装饰物实体

```bash
python scripts/decoration_postprocess.py \
  <dir>/decoration_input.json \
  <dir>/water_mask_grid.npy \
  <dir>/decoration_entities.json \
  --labels-fine <dir>/labels_fine.npy \
  --continent-map <dir>/continent_map_full.npy \
  --texture-grid <dir>/texture_grid.csv
```

> 地图尺寸自动从 `<dir>/map_info.json` 读取。
> `--texture-grid` 可选，不提供时所有采样点使用 grassland fallback 模型。

输出 `decoration_entities.json`，可直接传给 `entity_create_block` MCP 调用。

### Step 2.6：统计自检

脚本输出按纹理组的分布统计，检查不同纹理区域的模型是否匹配。

> ⛔ **禁止 AI 自行编写脚本生成装饰物**，必须调用 `scripts/decoration_postprocess.py`

---

## Stage 5：MCP 批量写入

> **核心原则**：AI 通过 **循环调用** `mcp_batch_writer.py --single-batch 1` 完成地形+纹理写入。
> ⛔ **禁止跳过 CSV 直接凭记忆调 MCP。禁止 AI 逐块调用 use_mcp_tool。**
> ⛔ **禁止 AI 在循环写入期间做任何其他操作（不调 use_mcp_tool、不编写脚本、不修改文件）。**
> ⛔ **禁止 AI 以"脚本卡住"为由自行中断或换方案。每次调用最多等待 ~30 秒。**
> ⛔ **禁止 AI 修改 `--single-batch` 参数值。必须始终为 1，不得改为 10/50 或其他值。**
> ⛔ **禁止 AI 在命令后面加管道（`| findstr` / `| grep`）或用 `for /L` 循环包裹命令。**
>
> 💡 **设计说明**：`--single-batch 1` 每次执行 100 格、约 5 秒返回。这个频率是刻意设计的——
> 让 AI 保持调用心跳，防止长时间无响应导致超时断连。不要试图"优化"这个参数。

### 5.1 单批循环模式（默认）

AI **必须**使用 `--single-batch 1` 模式循环调用脚本。每次调用执行 1 批（100 格），约 5 秒后返回。
**参数 `1` 不可更改**——这是保持 AI 调用心跳的关键设计，不是性能瓶颈。

**循环模板（AI 严格按此执行）：**

```
重复执行以下步骤，直到 BATCH_RESULT 的 status == "all_done"：

1. 执行命令:
   python scripts/mcp_batch_writer.py \
     --terrain-csv <dir>/terrain_grid.csv \
     --texture-csv <dir>/texture_grid.csv \
     --single-batch 1

2. 查看 stdout 最后一行的 BATCH_RESULT:
   - status == "in_progress" → 打印进度，继续步骤 1
   - status == "pass_complete" → 打印已完成的 pass，继续步骤 1
   - status == "all_done" → 退出循环，进入 5.3 装饰物写入
   - 命令执行失败（非零退出码）→ 报错停止，等待用户指令

3. ⛔ 禁止在步骤 1 和步骤 2 之间做任何其他操作
```

**BATCH_RESULT 输出格式**（脚本 stdout 最后一行）：

| status | 含义 | AI 行为 |
|--------|------|---------|
| `in_progress` | 当前 pass 未完成 | 继续调用 |
| `pass_complete` | 当前 pass 完成，还有下一个 | 继续调用 |
| `all_done` | 全部写入完成 | 退出循环 |

脚本内部写入顺序（严格不可调换）：
- **Pass 1: Crack** — 裂缝（精简版中无 crack 数据，自动跳过）
- **Pass 2: Ground Height** — 地形高度（精简版中全 h=0，自动跳过）
- **Pass 3: Water** — deep_water 写入
- **Pass 4: Slope** — 斜坡（精简版中无 slope 数据，自动跳过）
- **Pass 5: Texture** — 纹理统一刷

> ⚠️ **所有地形 MCP 接口只需传 `cliff_tex_id`**，引擎内部自动查表获取 cliff_type/cliff_mat/cliff_texture 三件套。
> ⚠️ **不要传 cliff_mat / cliff_type / cliff_texture / mesh_type**，这些参数已移除。

### 5.2 可选参数

| 参数 | 说明 |
|------|------|
| `--single-batch [N]` | 单批模式，每次执行 N 批后退出（默认 1，即 100 格/次） |
| `--dry-run` | 只解析 CSV 并输出统计，不实际写入 |
| `--restart` | 忽略进度文件，从头开始 |
| `--url <url>` | 覆盖 MCP Server URL |
| `--timeout <s>` | MCP 调用超时秒数（默认 300） |

> 💡 **备选全量模式**：不传 `--single-batch` 时脚本一口气执行所有 Pass（用户手动运行时使用，AI 不应使用此模式）。

### 5.3 装饰物写入（AI 调用 MCP）— ⛔ 必须执行，禁止跳过

> **⛔ 装饰物写入是 Stage 5 的必要组成部分，不是可选步骤。**
> 当 `decoration_entities.json` 存在且非空时，AI **必须**在地形+纹理写入完成（`all_done`）后立即执行装饰物写入。
> 禁止输出"JSON 已生成，可后续写入"然后停止。

**执行流程（AI 严格按此执行）：**

直接调用 `mcp_entity_writer.py` 脚本，它会自动读取 JSON、下载模型、分批调用 MCP：

```bash
python scripts/mcp_entity_writer.py <dir>/decoration_entities.json --download-models
```

脚本自动完成：
- 读取 `decoration_entities.json`（由 `decoration_postprocess.py` 生成的 entity list）
- 收集所有 `model_id`，自动调用 `download_editor_model_resource` 下载模型资源
- 分批调用 `entity_create_block`（默认每批 50 个，间隔 1 秒）
- 输出统计和 `ENTITY_RESULT` JSON

> ⚠️ **禁止 AI 手动复制 JSON 到 use_mcp_tool 参数**。必须使用脚本。
> ⚠️ 如需调整批次大小：`--batch-size 30`；调整延迟：`--delay 2.0`
> ⚠️ 先 dry-run 确认：`--dry-run`（只读取统计，不实际写入）

**entity 字段说明：**
```json
{
  "type": 16777216,
  "pos": [world_x, 0, world_z],
  "model_id": 201669,
  "yaw": 90,
  "pitch": 0,
  "roll": 0,
  "scale": [2.5, 2.5, 2.5],
  "stick_to_ground": true
}
```

> ⚠️ **type 必须是 `16777216`**（2^24 = RESOURCE_MODEL），不是 16！
> ⚠️ **旋转使用 yaw/pitch/roll 独立字段**，不是 rotation 数组！
> ⚠️ **不要自己生成 entity JSON**，必须使用 `decoration_postprocess.py` 脚本的输出！

**植被类装饰物** → 使用 `terrain_vegetation_draw_block`（⚠️ 植被坐标系与地形格点不同）

### 5.4 输出完成摘要

```
✅ 地形写入完成
  - 总格子数：16384
  - ground: 8200 格 | deep_water: 3100 格
  - 纹理覆盖：12000 格
  - 装饰物：桥梁 2 个, 树木 30 个
```

---

## 文件结构

```
y3-gen-terrain-from-image/
├── SKILL.md                                ← 本文件（精简两轮版）
├── output/                                 ← ⭐ 统一工作输出目录
│   ├── cropped.png                         ← Round 1: 裁剪后原图
│   ├── cluster_preview.png                 ← Round 1: 聚类预览
│   ├── cluster_preview_labeled.png         ← Round 1: 带簇 ID 标注预览
│   ├── palette.json / palette.png          ← Round 1: 色板
│   ├── palette_enhanced.json               ← Round 1: 增强色板
│   ├── labels.npy / centers_bgr.npy        ← Round 1: 聚类结果
│   ├── labels_fine.npy                     ← Round 1: K=50 细聚类标签
│   ├── water_mask_full.npy / *_grid.npy    ← Round 1: 水域 mask
│   ├── continent_map_full.npy / *_grid.npy ← Round 1: 大陆编号图
│   ├── terrain_grid.csv                    ← Round 1 final
│   ├── texture_grid.csv                    ← Round 1 final
│   ├── water_map.txt                       ← Round 2: 精简水域字符地图（W=水/.=陆）
│   ├── continent_subregions.json           ← Round 2: CV 大陆子区域分析结果
│   ├── subregion_preview.png               ← Round 2: 子区域可视化预览
│   ├── decoration_input.json               ← Round 2: AI 装饰物标注（v2 混合定位格式）
│   └── decoration_entities.json            ← Round 2 final (由 decoration_postprocess.py 生成)
├── templates/
│   ├── round1_water_continent_prompt.md    ← Round 1 AI prompt
│   └── round2_decoration_prompt.md         ← Round 2 AI prompt
├── scripts/
│   ├── check_cv_deps.py                    ← CV 依赖检测
│   ├── cv_cluster.py                       ← ⭐ Round 1: 色相 K-means 聚类
│   ├── cv_cluster_analysis.py              ← ⭐ Round 1: 双重聚类交叉分析
│   ├── cv_downsample.py                    ← ⭐ Round 1: 加权下采样
│   ├── cv_continent_split.py               ← ⭐ Round 1: 大陆连通分割
│   ├── gen_round1_csv.py                   ← ⭐ Round 1: 生成 terrain + texture CSV
│   ├── water_postprocess.py                ← ⭐ Round 1: 水域后处理（填回孤立水域）
│   ├── cv_subregion_analysis.py            ← ⭐ Round 2: 大陆内部子区域分析（CV辅助定位）
│   ├── decoration_postprocess.py           ← ⭐ Round 2: 装饰物后处理 v2（mask+方位采样+密度）
│   ├── gen_water_map.py                    ← ⭐ Round 2: 生成精简水域字符地图（供AI定位水域）
│   ├── gen_round4_csv.py                   ← Round 2: 生成 decoration CSV (legacy)
│   ├── mcp_batch_writer.py                 ← ⭐ 批量 MCP 写入
│   ├── mcp_utils.py                        ← MCP 工具函数
│   └── read_map_size.py                    ← 读取 terrain.json 尺寸
└── references/
    ├── terrain-mcp-api.md                  ← MCP 接口速查
    ├── terrain-adjacency-rules.md          ← Y3 地形邻格约束规则
    ├── y3-terrain-basics.md                ← Y3 引擎地形常识
    ├── texture-ids.md                      ← 170 种纹理映射表
    ├── texture-color-map.md                ← 纹理颜色映射表（含实际渲染 RGB + 材质特征）
    ├── decoration_catalog.json             ← 风格化装饰物模型目录（7种风格）
    └── decoration-model-ids.md             ← 装饰物/植被 ID 映射表
```

---

## MCP 接口速查

完整清单见 `references/terrain-mcp-api.md`。

| MCP Tool | 用途 | 使用阶段 |
|----------|------|----------|
| `get_map_info` | 探活 + 地图尺寸 | Stage 0 |
| `terrain_set_deep_water_block` | 深水 | Stage 5 Pass 3 |
| `terrain_draw_texture_block` | 纹理 | Stage 5 Pass 5 |
| `terrain_vegetation_draw_block` | 植被 | Stage 5.3 |
| `entity_create_block` | 装饰物（桥梁/树木） | Stage 5.3 |
| `ensure_terrain_textures` | 纹理面板管理 | Step 1.4b |

---

## 注意事项

- **图片与地图 1:1 对应**：图片边界 = 地图边界，图片左上角 = 格点 (0,0)
- **大地图耗时**：128×128 约 170 次/Pass，CV 分割约 5-10 秒
- **MCP 调用中断恢复**：CSV 已持久化，中断后可从 CSV 重新开始写入
- **植被坐标系**：与地形坐标系不同，`terrain_vegetation_draw_block` 内部已处理
- **CV 依赖**：需要 `opencv-python` + `numpy`，约 45MB，通过 pip 安装
- **每轮交互**：两轮共约 3~4 次 AI-用户交互