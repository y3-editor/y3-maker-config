# Round 2 AI Prompt：装饰物识别（v3 — 纹理组驱动 + 精确定位）

> **本轮目标**：逐大陆标注装饰物（树丛、山脉）→ 识别桥梁 → 生成装饰物数据。
> **本轮产出**：decoration_input.json (由 AI 直接输出 + decoration_postprocess.py 后处理)
>
> **v3 核心变更**：
> - ❌ 不再有全局 `style` 字段，模型选择由脚本根据脚下纹理自动匹配
> - ✅ 树木使用 `tree_cluster`（fine_clusters 优先 + position+radius 精确控制）
> - ✅ 山脉使用 `mountain_chain`（from/to 连绵放置）

---

## AI 输入

1. **原始地图图片** — 全局视觉参考
2. **water_map.txt** — 精简水域字符地图（`W`=水域 `.`=陆地）
3. **continent_subregions.json** — CV 子区域分析结果（每个大陆的微簇分布、色差、可分离标记）
4. **subregion_preview.png** — 可视化预览图（大陆边界 + 高色差区域高亮）
5. **continent_crops/continent_<id>.png** — ⭐ 每个大陆的裁剪放大图（附九宫格网格线 + 方位标签），**Step 2.1 逐大陆标注时必须查看**

---

## Y3 空间常识（AI 必读）

> 这些常识帮助你理解 Y3 引擎中装饰物的**实际视觉效果**，避免标注参数与实际效果不匹配。

### 地图尺寸感知

- 典型地图为 65×65 格，每格 2 个世界单位
- 一个大陆通常占 10~25 格宽（地图的 15%~40%）
- 原图中一棵"圆团树"图案在地图上大约占 1~2 格
- 原图中一座"三角山"图案在地图上大约占 2~4 格

### 树木模型的实际大小

- Y3 的树木模型（scale=1.0）在游戏中只占约 **1 格**宽
- 原图上一个看起来有 "3~5 棵树的小丛" → 在 Y3 中需要 radius≈3 才能产生类似的视觉密度
- 原图上一片 "覆盖九宫格一格" 的森林 → 在 Y3 中大约需要 radius≈5~6
- 原图上一片 "覆盖大陆 1/3" 的大面积森林 → 在 Y3 中大约需要 radius≈8~12

### 山石模型的实际大小

- Y3 的山石模型默认很小（原始尺寸只有约 1~2 格），脚本会**自动放大**以覆盖合理区域
- 因此 mountain_chain 的 count 应当**如实反映原图中看到的山峰数量**，不用担心 "太密" —— 脚本会自动调整间距和大小
- 原图中连绵的大型山脉（5~8 座山峰排列成线）在 Y3 中会生成非常壮观的效果

### density 的实际效果

- `sparse`：每 3.5 格放一棵树。适合稀疏散落的零星植被
- `normal`：每 2 格放一棵树。适合普通密度的森林
- `dense`：每 1 格放一棵树。适合非常茂密的丛林
- **重要**：如果 radius 较小（≤3），配合 sparse 可能只能放 2~3 棵树，视觉上几乎看不出是"森林"

### 装饰物之间的空间关系

- **山比树大得多**：一座山峰（自动放大后）在游戏中约占 3~5 格宽，而一棵树只占约 1 格。山会遮挡/覆盖附近的树
- **避免山和树的方位重叠**：如果一个大陆的 northwest 已经标了 mountain_chain，就不要在同一个 northwest 再放 tree_cluster，否则树会被山压在下面看不见。应该把树放在相邻但不重合的方位
- **桥梁附近留空**：桥的两端各约 2~3 格范围内不应放置树木或山脉，否则模型会穿插桥体。如果桥在某大陆的 south，就不要在 south 放装饰物

### 水域边缘与地形边缘

- 脚本会自动过滤水域格子（不在水上放装饰物），AI 不需要担心
- 但 AI 标注时应注意：如果一个大陆的某个方位几乎全是水（比如半岛的尖端），在那里标注 tree_cluster 会因为采样点大量被水域过滤而导致 placed=0。应选择陆地面积充裕的方位

### 纹理与装饰物的自动匹配

- AI **不需要** 手动选择树和山的具体模型 —— 脚本会根据每个采样点脚下的纹理自动匹配
- 例如：沙漠纹理上自动放仙人掌/枯树，冰雪纹理上自动放松树，草地上自动放绿色阔叶树
- AI 只需要标注 "这里有树" / "这里有山脉"，不用操心风格匹配

---

## Step 2.0: CV 子区域分析（自动完成，无需 AI 参与）

> 由 `cv_subregion_analysis.py` 自动完成，产出 continent_subregions.json 和 continent_crops/。

---

## Step 2.1: 桥梁识别（优先！）

> ⚠️ **桥梁识别必须第一个做！** 在标注树木和山脉之前完成桥梁识别，确保注意力集中。

### 任务

从原始地图图片中识别**所有**桥梁位置。桥梁是连接不同大陆的关键结构。

### 桥梁特征

1. **跨越水域**：桥梁必须横跨水域区域（蓝色河流）
2. **连接两个大陆**：桥两端分别连接不同大陆的陆地
3. **视觉特征**：横跨河流的**短粗条状结构**，颜色为棕色/黄色/灰色
4. **典型位置**：河流较窄处、两块大陆距离最近处

### 工作流程

1. **先看原图**：找到所有跨水域的桥梁状结构
2. **逐座验证**：对每座桥，对照 `water_map.txt` 确认坐标 `(x, z)` **必须落在 `W` 格子上**
3. **如果坐标不在 `W` 上**：手动调整到最近的 `W` 格子（看 water_map.txt 找邻近的 W）
4. **yaw 推算**：观察桥梁连接方向：
   - 南北向连接 → `yaw: 0`
   - 东西向连接 → `yaw: 90`
   - 对角线 → `yaw: 45` 或 `yaw: 135`

### 输出格式

```json
{
  "bridges": [
    { "x": 30, "z": 15, "yaw": 90, "note": "连接大陆2和大陆3的木桥" }
  ]
}
```

> ⚠️ **坐标精度是桥梁的生命线！** 每一座桥都必须逐个对照 water_map.txt 验证 `(x, z)` 确实是 `W`。
> 如果 water_map.txt 中 `(x, z)` 不是 `W`，**必须调整坐标**，不允许放一个不在水上的桥。

---

## Step 2.2: 逐大陆装饰物标注

### 任务

对 `continent_subregions.json` 中列出的每个大陆，逐个查看**大陆裁剪图**（`continent_crops/continent_<id>.png`），精确标注其内部的装饰物。

> ⚠️ **必须逐大陆查看裁剪图！** 裁剪图上有九宫格网格线和方位标签（NW/N/NE/W/C/E/SW/S/SE），比看整张大图能看清更多细节。

> 🌲 **树木优先原则**：大多数手绘地图中，树木远多于山脉。**先找树，后找山！** 如果一个大陆上有任何绿色/植被图案，都应该标注 tree_cluster。

### 工作流程

**对每个大陆，严格执行以下步骤：**

#### Step A: 查看大陆裁剪图 — 先找树木！

打开 `continent_crops/continent_<id>.png`，按优先级观察：
1. 🌲 **先找树木**：哪些区域有**绿色团状/圆形树丛图案** → 记录为 `tree_cluster`
2. 🏔 **再找山脉**：哪些区域有**三角形山峰图案**，山脉的走向如何 → 记录为 `mountain_chain`
3. **树丛大小**：数一数每个树丛大概覆盖几格宽 → 对应 `radius` 值
4. **山脉走向**：山峰从哪个方位延伸到哪个方位 → 对应 `from/to`

#### Step B: 检查可分离子区域（CV 辅助）

查看该大陆的 `subregions` 列表，找出 `separable: true` 的子区域。

对每个 separable 子区域：
1. 看其 `avg_rgb` 颜色 — 对照裁剪图判断它是什么
2. 判断语义类型：
   - **深绿/暗绿色** → 很可能是 🌲 **树林** → 记录 `fine_clusters`
   - **灰色/深灰色** → 很可能是 🏔 **山脉/岩石**
   - **白色/米白/浅色** → 🛤️ **道路**（忽略）
   - **与底色相近** → **阴影/光照变化**（忽略）
3. 如果判断为树林 → 记录其 `fine_ids` 到 `tree_cluster` 的 `fine_clusters` 字段

> 大部分 separable 子区域是道路/光照变化，**只标注确实是装饰物的子区域**。

#### Step C: 精确描述

**树丛 (tree_cluster)** — 两种定位方式选其一：

| 模式 | 何时使用 | 字段 |
|------|---------|------|
| fine_clusters | CV 成功分离出树人（有 separable 子区域） | `fine_clusters: [17, 20]` |
| position + radius | CV 没分离成功，AI 自己看裁剪图定位 | `position: "northeast"`, `radius: 4` |

**radius 参考标准（参照上方 "Y3 空间常识"）：**

| 原图中树丛的视觉面积 | radius | 配合 density | 预期效果 |
|---------------------|--------|-------------|---------|
| 2~3 棵零散的树 | 2~3 | sparse | 几棵散树 |
| 一小片树林（裁剪图中约占 1 格） | 3~4 | normal | 小丛林 |
| 明显的一片森林（裁剪图中约占 2~3 格） | 5~6 | normal | 中型森林 |
| 覆盖大陆 1/4~1/3 的大森林 | 8~12 | normal/dense | 大面积森林 |

> ⚠️ **radius 必须给一个合理的具体数字**，不要省略！参考裁剪图上的九宫格，估算树丛跨越了几格宽即可。

**山脉 (mountain_chain)** — 描述山脉的走向和数量：

| 字段 | 说明 |
|------|------|
| `from` | 山脉起点方位（九宫格） |
| `to` | 山脉终点方位（九宫格） |
| `count` | 山峰数量（看原图数几座山就填几） |

示例：

```
原图中山脉从大陆的北边延伸到东南方向，共 4 座山峰
→ {"from": "north", "to": "southeast", "count": 4}

原图中大陆西边有 2 座孤立的山
→ {"from": "west", "to": "west", "count": 2}
```

> ⚠️ **山峰规则**：from 和 to 可以相同（表示集中在一个区域）。count 要准确数清原图中有几座三角形山。

#### Step D: 自检（必须执行！）

完成所有大陆标注后，**再次逐大陆过一遍裁剪图**，检查：

**🌲 树木遗漏检查（最重要！）：**
1. ❌ 某个大陆上原图有明显绿色植被/树丛图案，但 decorations 中**没有 tree_cluster** → **必须补充！**
2. ❌ 整个地图的 tree_cluster 总数 < mountain_chain 总数 → **很可能遗漏了树木，回去逐大陆检查！**
3. ❌ 有大陆只有 mountain_chain 没有 tree_cluster → **检查原图，大部分大陆都应该有树**

**⭐ 树木覆盖率底线：至少 70% 的大陆应该有 tree_cluster（除非原图确实只有沙漠/岩石/雪原）**

**其他检查：**
4. ❌ 裁剪图中有明显的山峰但输出中没有对应条目 → **补充**
5. ❌ 输出中有条目但裁剪图中对应方位区域并没有装饰物 → **删除**
6. ❌ mountain_chain 和 tree_cluster 类型标反了 → **修正**
7. ❌ 所有树的 radius 都一样 → **检查应该有大小差异**
8. ❌ mountain_chain 的 from/to 不符合原图中山脉的走向 → **修正**

### 输出格式

**树丛条目（tree_cluster）：**
```json
{
  "type": "tree_cluster",
  "density": "normal",
  "fine_clusters": [17, 20],
  "position": null,
  "radius": null
}
```

```json
{
  "type": "tree_cluster",
  "density": "sparse",
  "fine_clusters": null,
  "position": "northeast",
  "radius": 3
}
```

**山脉条目（mountain_chain）：**
```json
{
  "type": "mountain_chain",
  "from": "northwest",
  "to": "east",
  "count": 4
}
```

**字段说明：**

| 字段 | 类型 | 适用 | 说明 |
|------|------|------|------|
| `type` | string | 通用 | `"tree_cluster"` 或 `"mountain_chain"` |
| `density` | string | **仅 tree_cluster** | `"sparse"` / `"normal"` / `"dense"` |
| `fine_clusters` | int[] 或 null | **仅 tree_cluster** | CV 微簇 ID，有值时 position/radius 被忽略 |
| `position` | string 或 null | **仅 tree_cluster** | 九宫格方位（仅 fine_clusters=null 时必填）|
| `radius` | int 或 null | **仅 tree_cluster** | 散布半径（格子数，参考 Y3 空间常识），仅 position 模式时必填 |
| `from` | string | **仅 mountain_chain** | 山脉起点方位 |
| `to` | string | **仅 mountain_chain** | 山脉终点方位 |
| `count` | int | **仅 mountain_chain** | 山峰数量（1~8） |

**方位关键词**（`position`、`from`、`to` 可选值）：

```
┌──────────┬──────────┬──────────┐
│ northwest│  north   │ northeast│
├──────────┼──────────┼──────────┤
│   west   │  center  │   east   │
├──────────┼──────────┼──────────┤
│ southwest│  south   │ southeast||
└──────────┴──────────┴──────────┘
+ "scattered" = 全大陆（仅 tree_cluster 的 position 可用）
```

---

## Step 2.3: 汇总输出 decoration_input.json

将所有结果合并为一个 JSON 文件：

```json
{
  "continents": {
    "2": {
      "decorations": [
        {
          "type": "tree_cluster",
          "density": "normal",
          "fine_clusters": [17, 20],
          "position": null,
          "radius": null
        },
        {
          "type": "tree_cluster",
          "density": "sparse",
          "fine_clusters": null,
          "position": "southwest",
          "radius": 3
        }
      ]
    },
    "3": {
      "decorations": [
        {
          "type": "tree_cluster",
          "density": "dense",
          "fine_clusters": null,
          "position": "northeast",
          "radius": 6
        },
        {
          "type": "mountain_chain",
          "from": "north",
          "to": "southeast",
          "count": 4
        }
      ]
    },
    "11": {
      "decorations": [
        {
          "type": "mountain_chain",
          "from": "west",
          "to": "west",
          "count": 2
        }
      ]
    }
  },
  "bridges": [
    { "x": 30, "z": 15, "yaw": 90 }
  ]
}
```

> ⚠️ **注意**：不再有 `style` 字段！模型选择由脚本根据纹理自动匹配。

保存为 `decoration_input.json`。

---

## Step 2.4: 调用后处理脚本（AI 执行）

```bash
python scripts/decoration_postprocess.py \
  decoration_input.json \
  water_mask_grid.npy \
  decoration_entities.json \
  --labels-fine labels_fine.npy \
  --continent-map continent_map_full.npy \
  --texture-grid texture_grid.csv
```

> 地图参数自动从同目录下的 `map_info.json` 读取，AI 无需传入。

脚本自动完成：
- **纹理组映射**：加载 texture_grid.csv + texture_group_catalog.json，每个采样点按脚下纹理选模型
- **tree_cluster**：fine_clusters 模式（mask 内泊松采样）或 position+radius 模式（圆形区域采样）
- **mountain_chain**：沿 from→to 线段均匀放置山峰，加法线偏移
- **向后兼容**：旧 tree/mountain 类型仍可处理
- 密度自适应 + 水域过滤 + 随机 yaw/scale
- 桥梁水域吸附 + yaw 自动推算
- 输出 `decoration_entities.json`

---

## Step 2.5: 统计自检

脚本会输出按纹理组的统计信息，检查：
1. 不同纹理区域是否使用了不同风格的模型
2. 路面/岩石组上是否正确跳过了装饰物
3. 总数量是否合理

> ⛔ **禁止 AI 自行编写脚本生成装饰物**，必须调用 `scripts/decoration_postprocess.py`

---

## ⛔ AI 禁令

| # | 禁止 | 正确做法 |
|---|------|----------|
| 1 | ⛔ 禁止修改 terrain_grid.csv | 地形数据在 Round 1 已完成 |
| 2 | ⛔ 禁止修改 texture_grid.csv | 纹理在 Round 1 已完成 |
| 3 | ⛔ 禁止输出 `style` 字段 | v3 不再使用全局风格，纹理组自动匹配 |
| 4 | ⛔ 禁止使用旧 `tree`/`mountain` 类型 | 使用新的 `tree_cluster`/`mountain_chain` |
| 5 | ⛔ 禁止 tree_cluster 省略 radius | position 模式下必须给具体 radius 值 |
| 6 | ⛔ 禁止遗漏原图中明显的装饰物 | 仔细看裁剪图，用 position 方位补充 |