# ECA 配方速查（按功能）

> `y3-eca-pipeline` 的下沉参考：**只写某类逻辑时**才读对应小节。
> 这里只给"用哪个动作 + 一条最容易踩的坑"，字段级写法查
> `../eca-json-builder/eca-json-builder.md`，陷阱细节查 `../eca-json-builder/runtime_pitfalls.md`。

## 1. 定时器 · 循环 · 轮询

| 目的 | 动作 | 坑 |
|------|------|----|
| 延时一次 | `RUN_ONCE_TIMER_NO_SAVE(秒, 动作列表)` | 动作列表里可以放嵌套 `IF`（实测会执行） |
| 定时 N 次 | `RUN_COUNT_TIMER(计时器变量, 秒, 次数, bool, 动作列表)` | 需要句柄才能注销时用它；`_NO_SAVE` 版没有句柄 |
| 无限轮询 | `RUN_LOOP_TIMER(计时器变量, 秒, false, 动作列表)` | 结算类轮询用它，配合结算标志变量 |
| 注销定时器 | `DELETE_TIMER(计时器变量)` | 先判 `IS_TIMER_VALID` 再删 |

**最贵的坑**：`SET_VARIABLE <NEW_TIMER 变量> = 0` 会让整条触发器 `valid=false`（计时器初值交给变量默认值）。

**什么时候必须用轮询**：事件触发瞬间世界状态还没更新时。典型是 `ET_UNIT_DIE` ——
死亡单位仍在单位组里，事件内直接判"数量为 0"永远不成立，必须"事件写快照 + 轮询复查"。

## 2. 单位创建与命令

```jsonc
// 创建并拿句柄（比依赖 LAST_CREATE_UNIT 稳）
["SET_VARIABLE", {"var": "本波怪", "type": "UNIT_ENTITY"},
 ["CREATE_UNIT", 200101, ["RECTANGLE_RANDOM_POINT", 10005], 0.0, 31]],
// 逐只下令（群体命令实测无效）
["UNIT_RELEASE_COMMAND", {"var": "本波怪", "type": "UNIT_ENTITY"},
 ["UNIT_COMMAND_ATTACK_MOVE", 10003]]
```

| 目的 | 动作 | 坑 |
|------|------|----|
| 创建单位 | `CREATE_UNIT(UNIT_NAME, POINT, ANGLE, PLAYER)` | 第 4 参可传玩家编号；返回单位实体 |
| 攻击移动 / 移动 / 攻击目标 | `UNIT_RELEASE_COMMAND(单位, UNIT_COMMAND_*)` | **群体命令 `API_RELEASE_UNIT_GROUP_COMMAND` 实测零效果** |
| 随机点 | `RECTANGLE_RANDOM_POINT(矩形)` / `ROUND_AREA_RANDOM_POINT(圆形)` | 逻辑资源直接传 res_id 整数 |
| 复活 | `REVIVE(单位, POINT)` | 复活会打断镜头跟随，需要重新锁 |
| 计数 | `GET_COUNT(单位组)` / `UNIT_NAME_NUM_IN_GROUP(单位组, 单位类型)` | 见 §1 的时序坑 |
| 等级 / 经验 | `GET_UNIT_LEVEL` / `UNIT_CUR_EXP` / `UNIT_ADD_EXP` | — |
| 玩家单位组 | `PLAYER_UNIT_GROUP(玩家)` | 中立敌对 = 31，中立友好 = 32 |

**远处怪物不主动扑过来**：`alarm_range`（警戒索敌，模板默认约 8 米）不够大；要么调物编，要么显式下令。

## 3. UI：显隐 · 绑定 · 点击

| 目的 | 动作 | 坑 |
|------|------|----|
| 整页显隐 | `SET_UI_COMP_VISIBLE(玩家/玩家组, bool, 控件uid)` | 画板控件按 **uid** 寻址 |
| 文本 / 图片 | `SET_UI_COMP_TEXT` / `SET_UI_COMP_IMAGE` | 属性名如 `text_bind`；图片是 IMAGE_KEY |
| 进度条 | `SET_UI_COMP_BIND_ATTR(玩家, 控件, "current_value_bind"/"max_value_bind", "hp_cur"/"hp_max")` + `UI_COMP_BIND_UNIT` | 先绑属性再绑单位 |
| 文本自动跟随全局变量 | `SET_UI_COMP_BIND_VAR(玩家, 控件, "text_bind", "全局变量名")` | 第 4 参是**变量名字符串** |
| 点击 | 控件 `event_list` 具名事件 + 子触发器 `TRIGGER_COMPONENT_EVENT`（**普通字符串字面量**） | 画板要用 `data-event` 声明；运行时注册那条通道实测不生效 |
| 动态生成 UI 事件 | 父触发器 `INIT_FINISHED` + 裸整数注册子触发器 | 事件参数别用 `STR_TO_UI_EVENT` 去配设计期事件名 |
| 血条 / 蓝条 | `SET_UI_COMP_BIND_ATTR(玩家, 控件, "current_value_bind"/"max_value_bind", "hp_cur"/"hp_max")` + `UI_COMP_BIND_UNIT(玩家, 控件, 单位)` | 先绑属性、再绑单位；绑定是引擎侧自动刷新，不需要定时器补刷 |
| 技能栏（官方组件 type:17） | `BIND_SKILL_ON_UI_COMP(玩家, ["UNIT_ABILITY", 单位, 3, 槽位], 控件uid)` | `ABILITY_TYPE`：`隐藏`=0 / `普通`=1 / `命令`=2 / **`英雄`=3**；槽位是英雄技能第 1~N 格 |
| 物品栏（官方组件 type:20） | `SET_UI_COMP_UNIT_EQUIP_SLOT(玩家, 控件uid, 单位, <SLOT_TYPE>, 序号)` | `SlotType`：**PKG=0 背包栏** / BAR=1 物品栏；序号从 1 开始 |
| 画板控件寻址 | 路径 = `画板名.<根 layout 名>.<中间 layout>.<控件名>` | **中间的 layout 层不能省**（漏了会报「UI 不存在」）；控件名是契约、uid 从画板 JSON 读回 |
| 重生成画板 | `html_to_y3_ui.py` 默认按名称路径复用旧 uid | 即使 uid 稳定，新增/删除控件后仍要重跑 `make_global_dsl.py` → `gen_trigger.py` → `load_eca.py`，并跑 `audit_triggers.py` 校验 uid 引用 |
| 官方 `GameHUD` | 根节点 `visible=false`，保留文件 | 用 `y3-ui-pipeline/scripts/hide_gamehud.py` 或手动改 JSON；改完 `hotfix_ui_editor` → 等 3 秒 → `save_editor` |
| 深色 HUD 底板 | `data-preset="dark-bg"` | `panel-bg` 实际偏金色/棕色，不要拿它当深色底板 |

**UI 点击无法自动验证**时，如实登记为人工用例，并把"该动作本身"用探针/对照实验单独取证。

> ⚠️ **官方复合组件（type:17 技能栏 / type:20 物品栏）取不到中心点**（`y3runtime.get_ui_center_by_path` 超时），
> 也无法用触摸注入驱动 —— 这类 UI 一律登记为人工用例，别在自动化里空转。

## 4. 胜负结算

```jsonc
["END_GAME_FOR_ROLE", <PLAYER>, "victory" | "defeat", 1, false, 0, false]
```

| 要点 | 说明 |
|------|------|
| **6 个参数必须填满** | 否则 `valid=false` |
| `WIN_OR_LOSE` | 字符串 `"victory"` / `"defeat"`（实测有效，会弹引擎官方结算界面） |
| 只结算一次 | 用一个整数状态标志（INTEGER 0/1），别用 BOOLEAN（未验证成功） |
| 官方结算会挡自定义面板 | 方案 A 弹模态，自定义"重新开始"按钮不可点 → 两者取舍要跟用户确认 |
| **退出游戏** | `EXIT_GAME` 在本地单机测试环境无可见效果 | 改用 `ROLE_FORCE_QUIT(1, "玩家主动退出")`；实测可立即停止进程 |

## 5. 条件与数值

| 目的 | 写法 | 坑 |
|------|------|----|
| 组合条件 | `AND([条件...])` / `OR([条件...])` | 条件列表是一层数组 |
| 整数比较 | `INTEGER_COMPARE(a, ">=", b)` | 两侧都是整数就用它；`FLOAT_COMPARE` 混用 INTEGER 实参**静默不成立** |
| 字符串比较 | `STRING_COMPARE(串, "==", "字面量")` | 取控件名用 `GET_UI_COMP_NAME(玩家, 控件)` |
| 单位比较 | `UNIT_COMPARE(a, "==", b)` | 空单位用 `NONE_UNIT` |
| 类型存在性 | `TYPE_IS_EXIST(实体)` | 删除/复活前先判 |
| 自增自减 | `MATH_OPERATION(x, "+"/"-", n)` | 运算符是字符串；写进 INTEGER 变量时 arg_type 会被钉成 INTEGER |
| 数值转字符串 | `STR_JOIN`（2 位置 + 8 段 `op_arg`）+ `INT_TO_STR` | `VALUE_TO_STR` 不可用；`FLOAT_TO_STR` 想保留 0 位小数要写 `{"op_arg":[0]}` |

## 6. 常用事件

| 事件 | 用途 | 注意 |
|------|------|------|
| `INIT_FINISHED`（t_system） | 初始化、注册子触发器 | **不能**用 `TRIGGER_PLAYER`；玩家入口用下面两个 |
| `ANY_ROLE_JOIN_GAME`（t_player） | 玩家进入 | 可用 `TRIGGER_PLAYER` |
| `GENERIC_UNIT_EVENT` + `ET_UNIT_DIE` | 击杀奖励 / 死亡处理 / 胜负判定 | 参数 `sub_type` 写事件名字符串；`TRIGGER_PLAYER` 不可用，改用 `OWNER_PLAYER(单位)` |
| `TRIGGER_COMPONENT_EVENT` | UI 具名事件 | 必须是子触发器 |

## 7. 玩家侧数值：优先玩家属性，退化用全局变量

`ROLE_CHANGE_RES` / `GET_ROLE_RES` / `SET_UI_COMP_BIND_PLAYER_PROP` 需要 `ROLE_RES_KEY`（玩家属性）。
工程若没有对应属性键（`attr.json` 无脚本入口、又不能手写），退化方案是 **ECA 全局变量**：

| 需求 | 玩家属性方案 | 全局变量方案 |
|------|-------------|-------------|
| 加金币 | `ROLE_CHANGE_RES(玩家, <金币键>, n)` | `SET_VARIABLE 金币 = MATH_OPERATION(金币, "+", n)` |
| 读金币 | `GET_ROLE_RES(玩家, <金币键>)` | 直接读变量 |
| HUD 金币栏 | `SET_UI_COMP_BIND_PLAYER_PROP` | `SET_UI_COMP_BIND_VAR(…, "金币")` |

> 全局变量方案**单人对局可用，多人会串号**；多人化前必须先补玩家属性定义。

## 8. 表现层：特效 · 跳字 · 镜头 · 中央提示

| 目的 | 动作 | 写法要点 |
|------|------|----------|
| 单位身上放特效 | `CREATE_SFX_ON_UNIT(特效Key, 单位, "origin", false, false)` | 挂接点用 `"origin"`；要传缩放/时长必须写成**赋值形式**（见下） |
| 点上放特效（AOE 圆心） | `CREATE_SFX_ON_POINT(特效Key, 点)` | AOE 用放大版当「范围提示」 |
| 伤害跳字 | `APPLY_DAMAGE` 第 6 个位置参数 = `true` | 具名 DSL 里键名是 `crit`，但槽位语义是「是否跳字」 |
| 治疗/其他跳字 | `CREATE_HARM_TEXT_NEW(点, 类型, "文本", 玩家组)` | 类型是枚举，取值查「主界面-细节-美术效果-跳字管理」 |
| 镜头震动 | `NEW_CAMERA_SHAKE(玩家, 幅度, 次数, 时长, 模式)` | 另有 `_WITH_DECAY`(带衰减)/`_XY`/`_Z`；模式 7=三轴、3=水平+垂直。**技能触发器里没有 `TRIGGER_PLAYER`，用 `OWNER_PLAYER(施法者)`** |
| 屏幕中央提示 | `DISPLAY_TO_ROLE_GROUP_TEXT_TIME(玩家, "文本", 秒, false)` | Boss 出场警告、技能名提示 |
| 音效 | `PLAY_SOUND_FOR_PLAYER(玩家, 音效Key, false)` / `PLAY_3D_SOUND_FOR_PLAYER(...)` | 音效资源需先下载 |

> ⚠️ **动作位不能带 `op_arg`**：要给动作传可选参数（`ADD_MODIFIER` 的时长、`CREATE_SFX_ON_*` 的缩放/时长）
> 必须写成赋值形式 —— `SET_VARIABLE <SFX_ENTITY/MODIFIER_ENTITY 全局变量> = [动作, …, {"op_arg":[…]}]`。
> 需要一个新的全局变量来承接；这个变量可以和其它改动攒在同一批、一次重启装进去（见 SKILL.md §1.1）。
>
> ⚠️ **表现层动作不影响逻辑，但会拖慢每一轮验证**：特效/镜头无法用截图自动判定，
> 别为了「看一眼特效」反复重启；先把逻辑验通，表现层最后一起加。

## 9. 复位 / 重开局：清场会触发死亡事件

「重新开始」时用 `KILL_UNIT` 清场，会**逐只触发「单位死亡」链路**（击杀奖励、掉落、胜负判定），
于是出现「越清越富」（金币被重新累加）、甚至当场误判胜负。正确顺序：

```
① 先复位流程状态（波次=0、结算标志=1、主控单位=NONE_UNIT）
② 再清场（IS_TIMER_VALID 守卫 + DELETE_TIMER 放末尾；PICK_UNIT_DO_ACTION + KILL_UNIT）
③ 最后复位统计（金币=0、击杀数=0、结算标志=0）
```

另外：跨局要能取消的循环/计数计时器必须用**带句柄版** `RUN_COUNT_TIMER(<NEW_TIMER 全局变量>, …)`，
`_NO_SAVE` 版没有句柄、「重新开始」注销不掉，会出现「上一局的计时器继续给新一局刷波次」。

波次计数要加**上限守卫**（`IF 波次 < 总波数 THEN +1`），否则计时器多跑的几下会把计数顶到总波数以上。

## 10. 批量验证技能触发器（可复用套路）

想一次验完多个技能，**不要反复重开游戏选英雄** —— 用 Lua 造可控测试单位：

```lua
-- ① 造测试单位：远离出怪点；关掉普攻与回血，避免污染读数
local u = y3.unit.create_unit(y3.player(1), <单位Key>, y3.point.create(-7600, 0, 0), 0)
u:set_attr('攻击间隔', 100, '基础')
u:set_attr('生命恢复', 0, '基础')
-- ② 挂技能：槽位用 AbilityIndex，被占用会返回 nil（自带 4 技能的英雄占 3~6，测试技能放 7 号起）
local ab = u:add_ability(3, <技能Key>, 7, 1)
-- ③ 目标也要静音：set_attr('攻击间隔', 100) + set_attr('alarm_range', 0)
-- ④ 采样：施法同一帧排定，卡在 ABILITY_SP_END 之后（前摇+后摇约 0.7s）
u:cast(ab, target)
y3.ctimer.wait(1.2, function() _G.__r = { hp = target:get_hp(), mp = u:get_mp() } end)
```

**判据三件套**（缺一条就会误判「触发器坏了」）：

| 判据 | 为什么必须看 |
|------|-------------|
| `unit:is_alive()` | 单位死了 `cast()` 照样返回成功、什么都不发生 |
| 施法后蓝量（或 CD）变化 | 证明**这次真的放出去了**；只看 `pcall` 返回值会被骗 |
| 效果值（血量/属性/buff 数） | 真正的结论 |

**方向类技能要摆对照组**：在施法方向的正前方与正后方各放一只，前方掉血、后方不掉血才算「方向生效」。

> 施法能力限制见 `../eca-json-builder/runtime_pitfalls.md §10.1`（方向类 1/2 与取点类 3 无法脚本施法）。

## 11. 属性类 Buff：ADD_ATTR

`ADD_ATTR(单位, 属性层, 属性键, 数值)`：

- **属性键必须用英文键**：`attack_phy` / `defense_phy` / `attack_speed` / `ori_speed` / `vampire_phy` / `critical_chance` 等。
- **属性层必须用字符串**：`ATTR_BASE` / `ATTR_BONUS` / `ATTR_BASE_RATIO` / `ATTR_BONUS_RATIO` / `ATTR_ALL_RATIO`。
- 中文属性名、中文属性层、把属性层写成整数，都会让触发器 `valid=false`（实测）。

```jsonc
// 护甲 +50%，持续 5 秒
["ADD_ATTR", ["ABILITY_OWNER"], "ATTR_BASE_RATIO", "defense_phy", 50.0],
["RUN_ONCE_TIMER_NO_SAVE", 5.0, [
  ["ADD_ATTR", ["ABILITY_OWNER"], "ATTR_BASE_RATIO", "defense_phy", -50.0]
]]
```

百分比类属性（攻速、移速、吸血、暴击率）优先用 `ATTR_*_RATIO` 或 `ATTR_BONUS`，不要把所有属性都当平值。

## 12. ADD_MODIFIER 的持续时间

动作位不能直接带 `op_arg`。要传持续时间，用变量接收返回值：

```jsonc
["SET_VARIABLE",
 {"var": "当前Buff", "type": "MODIFIER_ENTITY", "scope": "global"},
 ["ADD_MODIFIER", ["ABILITY_OWNER"], 300003,
  {"op_arg": [null, null, 5.0]}]]
```

`op_arg` 顺序：来源单位、关联技能、持续时间、循环周期、层数、创建参数表。

## 13. 技能按钮 QWER 快捷键

```jsonc
["SET_BTN_SMART_CAST_SHORT_CUT", 1, "skill_q控件uid", 16], // Q
["SET_BTN_SMART_CAST_SHORT_CUT", 1, "skill_w控件uid", 17], // W
["SET_BTN_SMART_CAST_SHORT_CUT", 1, "skill_e控件uid", 18], // E
["SET_BTN_SMART_CAST_SHORT_CUT", 1, "skill_r控件uid", 19], // R
["SET_SMART_CAST_WITH_POINTER", 1, true]
```

键值来自 `y3.const.KeyboardKey`：`Q=16`、`W=17`、`E=18`、`R=19`。
该动作只对 **type:17 技能按钮** 生效，且要先 `BIND_SKILL_ON_UI_COMP` 绑定技能。

> 自动化环境里的合成键盘事件可能送不进游戏客户端；动作落盘不等于真实按键已验收，交付时要人工按一次。

## 14. 运行时调整 UI 坐标

已有正式画板直接改 `maps/<map>/ui/*.json` 的 `pos_data` 后，`hotfix_ui_editor` + `save_editor`
可能仍被编辑器旧内存写回（实测）。需要稳定生效时，用 ECA 在开战时定位：

```jsonc
["SET_UI_COMP_POSITION_NO_TRANS", 1, "控件uid", 1506.0, 68.0]
```

注意：参数是 **Y3 坐标（左下角原点）**，不是 HTML 的左上角坐标。徽标、装备栏、退出按钮
这类需要适配窗口的边缘控件，优先用运行时定位，并给右侧/底部留出安全边距。

## 15. 掉落与自动拾取

```jsonc
// 在死亡点创建物品，先拿到物品实体
["SET_VARIABLE",
 {"var": "当前物品", "type": "ITEM_ENTITY", "scope": "global"},
 ["CREATE_ITEM", ["UNIT_ENTITY_POINT", ["KILLED_UNIT"]], 500003, 1]],
// 让英雄去拾取（拾取后进入 BAR 物品栏，4 格 UI 绑定 BAR 第 1~4 格）
["UNIT_RELEASE_COMMAND",
 {"var": "英雄", "type": "UNIT_ENTITY", "scope": "global"},
 ["UNIT_COMMAND_PICK_ITEM",
  {"var": "当前物品", "type": "ITEM_ENTITY", "scope": "global"}]]
```

概率掉落用 `INTEGER_COMPARE(RANDOM_INT(1,100), "<=", 概率)` 包住创建动作。

## 16. 模型 ID、头像 ID、图标 ID

- `y3_obj_edit.py -create` 单位第 4 段是**模型 ID**，第 5 段是**头像 ID**。
- UI 的 `data-image` / 控件 `image` 要用**头像或图标 ID**，不能填模型 ID；填错通常表现为空白图。
- 技能 `ability_icon`、物品 `icon`、Buff `modifier_icon` 都使用图标资源 ID。
- 资源选型参考 `y3-obj-edit/excels/resources.csv` 的列含义，不要把模型列和头像列混用。



