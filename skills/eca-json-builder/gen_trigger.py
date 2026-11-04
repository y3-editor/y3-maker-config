# -*- coding: utf-8 -*-
"""ECA trigger generator — read compact DSL, emit full trigger JSON + update index.txt.

DSL format (JSON, can have multiple triggers in one file):
{
  "map": "EntryMap",                  # optional, default EntryMap
  "triggers": [
    {
      "name": "游戏初始化欢迎",
      "id": 1718000001,               # optional, auto-generated if omitted
      # ⚠️ event 是「事件列表的列表」：每个事件自身是一个数组 [事件名, *args]。
      #    写成一维数组 ["INIT_FINISHED"] 会生成 event_type: UNKNOWN（生成器现在会直接报错拦下）。
      "event": [["INIT_FINISHED"]],
      "condition": [],
      "action": [
        ["PRINT_MESSAGE_ACTION_TO_DIALOG", 3, "欢迎来到游戏！"]
      ]
    }
  ]
}

Each event/action/condition is a list: [eca_name, *args].
Args are inferred from eca_index.json `param` field:
  - INTEGER/FLOAT/STRING/BOOLEAN literals → sub_type=1
  - Nested list [func_name, *sub_args] → sub_type=func_name (functional sub_type)
  - {"var": "name", "type": "UNIT_ENTITY"} → variable reference

Custom ECA functions use a structured action so return targets remain explicit:
  {"call_function": {
    "func_id": "32-char-hex-id",
    "args": [{"type": "INTEGER", "value": 1000}],
    "returns": [{"var": "result", "type": "TABLE"}]
  }}

Run:
  py -3 gen_trigger.py <dsl.json>            # write to maps/<map>/global_trigger/trigger/
  py -3 gen_trigger.py <dsl.json> --dry-run  # print to stdout
"""
from __future__ import annotations
import argparse, json, os, sys
import zlib

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(SKILL_DIR, "eca_index.json")

# ---------------------------------------------------------------------------
# arg_type ID 映射（来自 skill 文档）
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 参数类型数据：源码派生（`eca_source_data.json`，由 sync_from_source.py 生成）
#
# `eca_index.json` 只记录参数类型的**名字**，没有 arg_type ID；而 ID 写错时编辑器不报错，
# 只在 save_editor 时把参数清成 null 或让触发器 valid=false。下面这份手写表曾是唯一来源，
# 只覆盖 71/311 个类型；现在改为「源码派生表打底 + 本表覆盖」：
#   - 派生表由 `sync_from_source.py` 从编辑器源码生成（330 个类型，覆盖 303/311）
#   - 本表保留为**带证据的覆盖层**；与派生值不一致时会打警告，提示去核对
# 源码换版本后请重跑 `py -3 sync_from_source.py --src <engine>`，再用 verify_trigger 抽验。
# ---------------------------------------------------------------------------

_SOURCE_DATA = None


def load_source_data():
    """读取随 skill 分发的源码派生数据 `eca_source_data.json`。

    分发形态说明（重要）：
      - `eca_source_data.json` 是**随 skill 分发的静态数据**，由维护者用
        `sync_from_source.py` 从编辑器源码派生一次。**使用者不需要编辑器源码。**
      - 文件缺失时退回内置手写表（条目少得多），此时遇到未覆盖的类型会**直接报错**并给出取证步骤，
        不会静默生成损坏节点。使用者可用 `harvest_from_project.py` 用手头工程自我校验/补全。
    """
    global _SOURCE_DATA
    if _SOURCE_DATA is not None:
        return _SOURCE_DATA
    path = os.path.join(SKILL_DIR, "eca_source_data.json")
    if not os.path.isfile(path):
        sys.stderr.write(
            f"[WARN] 未找到源码派生数据 {path}\n"
            f"       将退回内置手写表（{len(_HAND_ARG_TYPE_ID)} 个类型，远少于派生数据的 300+）。\n"
            f"       影响：未覆盖的类型会直接报错拦截（安全，但会挡住部分动作）。\n"
            f"       使用者可运行 `harvest_from_project.py --project <工程根>` 用手头工程的\n"
            f"       编辑器样本自我校验并补全；维护者请运行 `sync_from_source.py --src <engine>` 重新派生。\n"
        )
        _SOURCE_DATA = {}
        return _SOURCE_DATA
    with open(path, "r", encoding="utf-8") as f:
        _SOURCE_DATA = json.load(f)
    return _SOURCE_DATA


_HAND_ARG_TYPE_ID = {
    "FLOAT": 100000,
    "BOOLEAN": 100001,
    "INTEGER": 100002,
    "STRING": 100003,
    "POINT": 100004,
    "UNIT_ENTITY": 100006,
    "GENERIC_UNIT_EVENT": 100008,
    "RECTANGLE": 100009,
    "TABLE": 100011,
    "COMPARISON_OPERATOR": 100015,
    "ACTION_LIST": 100022,
    "PLAYER": 100025,
    "UNIT_GROUP": 100026,
    "MODIFIER_KEY": 100046,
    "SFX_KEY": 100066,
    "STATE": 100075,
    "UNIT_NAME": 100116,
    "SFX_ENTITY": 100148,
    "DIALOG_DEBUG_TYPE": 100175,
    "ANGLE": 100225,
    "KEYBOARD_KEY": 200220,
    "MOUSE_KEY_WITHOUT_MIDDLE": 200224,
    # Extended types discovered from DM32 real-world usage
    "MODIFIER_ENTITY": 100076,
    "ABILITY": 100014,
    "PROJECTILE_ENTITY": 100077,  # 源码派生校正
    "PROJECTILE": 100062,  # 源码派生校正
    "NEW_TIMER": 100181,
    "DAMAGE_TYPE": 100064,
    "ABILITY_NAME": 100039,   # shares same ID as MODIFIER_KEY
    "ITEM_ENTITY": 100031,  # 源码派生校正
    "ITEM_NAME": 100032,       # shares with UNIT_NAME
    "LINK_SFX_ENTITY": 100202, # shares with SFX_ENTITY
    "PLAYER_GROUP": 100027,    # shares with UNIT_GROUP
    "CURVED_PATH": 100222,  # 源码派生校正
    "POLYGON": 100150,  # 源码派生校正
    "ROUND_AREA": 100023,  # 源码派生校正
    "UNIT_WRITE_ATTRIBUTE": 100077,
    "DYNAMIC_TRIGGER_INSTANCE": 100178,
    "UI_PREFAB_INSTANCE": 1001558,  # 源码派生校正
    "MODIFIER": 100046,
    "VARIABLE": 100077,
    "CONDITION_LIST": 100021,
    "CUS_EVENT": 100238,
    "CUS_PARAM": 100240,
    "ABILITY_FLOAT_ATTRS": 100078,  # 源码派生校正
    "ABILITY_INT_ATTRS": 100079,
    # GET_UNIT_ATTR 的取值口径 / 属性名（编辑器样本：global_trigger/function/ui/Refresh Unit Attribute.json）
    "ATTR_ELEMENT": 100301,
    "ATTR_ELEMENT_READ": 100301,
    "UNIT_WRITE_ATTRIBUTE": 100042,
    "EVENT_UNIT": 100007,
    # GET_UNIT_TYPE 的返回节点用 100010（编辑器自带样本：
    # global_trigger/trigger/UI/Init Update.json 的 UNIT_TYPE_COMPARE 节点）。
    # ⚠️ 实测（探针）：UNIT_TYPE_COMPARE 的**字面量**参数必须写成
    # arg_type 100116（UNIT_NAME），写 100010 时编辑器会把触发器标成 valid=false。
    "UNIT_TYPE": 100010,
    "BOOLEAN_OPERATOR": 100035,
    # 整数四则运算的运算符枚举（与 FLOAT_ARITHMETIC_OPERATOR=100017 不同）
    # 编辑器样本：global_trigger/trigger/UI/Init Update.json 的 MATH_OPERATION 节点
    "ARITHMETIC_OPERATOR": 100016,
    # 结束游戏枚举：y3/game/game.lua:end_player_game 传的是 'victory'/'defeat' 字符串
    "WIN_OR_LOSE": 100047,  # 源码派生校正
    "ON_OR_OFF": 100048,  # 源码派生校正
    "ABILITY_CAST_TYPE": 100219,  # 源码派生校正
    "ABILITY_TYPE": 100182,  # 源码派生校正
    "ABILITY_EVENT": 100128,  # 源码派生校正
    "MODIFIER_EVENT": 100129,  # 源码派生校正
    "MODIFIER_EFFECT_TYPE": 100174,  # 源码派生校正
    "ATTR_ELEMENT": 100300,  # 源码派生校正
    "ATTR_ELEMENT_READ": 100301,  # 源码派生校正
    "FLOAT_ARITHMETIC_OPERATOR": 100017,
    # ROLE_RES_KEY 的字面量 arg_type 是 100037（不是 STRING 的 100003）。
    # 证据：编辑器自带样本 maps/EntryMap/global_trigger/function/ui/Refresh Tooltip.json
    # 中 3 处 "official_res_1" 均写作 {"arg_type": 100037, "sub_type": 1, "args_list": ["official_res_1"]}。
    # 实测：写成 100003 时编辑器在 save_editor 会把该参数清成 null。
    "ROLE_RES_KEY": 100037,
    "TABLE_VAR": 100011,
    "SECTOR_SHAPE": 100059,  # 源码派生校正
    "RECTANGLE_SHAPE": 100060,  # 源码派生校正
    "ANNULAR_SHAPE": 100061,  # 源码派生校正
    "CIRCULAR_SHAPE": 100211,  # 源码派生校正
    "VAR": 100030,  # 源码派生校正
    "VAR_LIST": 100028,
    # UI arg_type IDs verified against editor-saved triggers in this project
    # (maps/EntryMap/global_trigger/trigger/UI/*.json, global_trigger/function/ui/*.json)
    "UI_COMP": 100070,
    "UI_EVENT": 100067,
    "UI_COMP_ATTR": 1001555,
    "UI_COMP_EVENT_TYPE": 100072,
    "UNIT_ATTRIBUTES": 100041,
}


def _build_arg_type_id():
    """合并「源码派生表」与「手写兜底表」。

    优先级：**源码派生 > 手写**。理由（实测）：手写表里相当一批类型是早期
    文档里的「共享 ID」猜测（例如 `WIN_OR_LOSE` 猜成 STRING 的 100003、
    `ITEM_ENTITY` 猜成 100021），与源码冲突的 29 项里绝大多数是手写值错。
    源码派生值直接来自 `GameTriggerArgType = reg_arg(..., const_name.X, ...)`，是唯一权威。
    手写表仅用于源码没覆盖的类型（并集伪类型等），冲突项一律打警告以便复核。
    """
    src = load_source_data()
    generated = dict(src.get("arg_type_ids") or {})
    merged = dict(_HAND_ARG_TYPE_ID)
    conflicts = []
    for name, gen_value in generated.items():
        hand_value = _HAND_ARG_TYPE_ID.get(name)
        if hand_value is not None and hand_value != gen_value:
            conflicts.append((name, hand_value, gen_value))
        merged[name] = gen_value
    if conflicts:
        for name, hand, gen in conflicts:
            sys.stderr.write(
                f"[WARN] ARG_TYPE_ID 冲突：'{name}' 手写={hand} 源码派生={gen}；"
                f"已按**源码派生**值生成。请复核（若源码版本与编辑器不一致，以编辑器抽验为准）\n")
        sys.stderr.write(
            f"[WARN] 共 {len(conflicts)} 项手写值与源码不一致（本条仅提示一次）。"
            f"手写表已退化为「源码未覆盖类型的兜底」，冲突项由源码优先。\n")
    return merged, generated


ARG_TYPE_ID, _SOURCE_ARG_TYPE_ID = _build_arg_type_id()


# 生成器自身会写入的非静态 sub_type（编辑器侧由运行时注册，静态表里查不到）
_SUBTYPE_WARN_ALLOWLIST = {"NONE_UNIT", "NONE_UNIT_GROUP"}


def check_sub_type_declared(func_name, expected_type):
    """提示函数式 sub_type 是否偏离该类型在源码里声明的取值（**告警**，不阻断）。

    依据：`sync_from_source.py` 从 `args/*.py` 派生的静态 sub_type 表。
    ⚠️ 该表**天生不完整**：一部分 sub_type 由运行时动态注册
    （例：`args_utils.py` 里 `TriggerKv.register_has_kv_arg` 生成的 `*_KV` 系列、
    `register_get_all_kv_arg` 生成的 `GET_*_KV`），静态解析看不到，因此这里只能告警。

    仍然值得保留：sub_type 拼错或张冠李戴时编辑器同样不报错——要么清成 null，要么让
    触发器 `valid=false`（实测：`TRIGGER_PLAYER` 用在物编事件里即属此类，最难排查）。
    """
    src = load_source_data()
    if not src:
        return
    choices = param_type_choices(expected_type)
    if len(choices) != 1 or func_name in _SUBTYPE_WARN_ALLOWLIST:
        return
    table = ((src.get("arg_types") or {}).get(choices[0]) or {}).get("sub_types") or {}
    if not table or func_name in table:
        return
    sys.stderr.write(
        f"[WARN] sub_type '{func_name}' 不在类型 {choices[0]} 的静态声明表里"
        f"（该表共 {len(table)} 项）。\n"
        f"       可能是：① 拼写/张冠李戴（编辑器不报错，保存时会清成 null 或让触发器 valid=false）；"
        f"② 运行时动态注册的 sub_type（如 *_KV 系列），属正常。\n"
        f"       请用 verify_trigger.py 回读确认。该类型静态表：{sorted(table)[:20]}"
        f"{' ...' if len(table) > 20 else ''}\n"
    )


# ---------------------------------------------------------------------------
# 上下文参数类型覆盖表（新增）
#
# 同一个类型名在不同位置可能需要**不同的 arg_type**：全局 name→id 映射不够，
# 写错不会报错、只在保存时被编辑器清成 null 或把触发器判成 valid=false。
# 键为 (动作/条件/函数名, 参数下标)，值为强制使用的类型名。
#
# 每条都必须能追溯到证据（工程内编辑器样本 / 探针实测），不要凭推理添加。
# ---------------------------------------------------------------------------
PARAM_TYPE_OVERRIDE = {
    # 探针实测（探针 D/H/I/J/S1/S2/S4/T1/T2）：
    # 字面量写 100010 会让整个触发器 valid=false（内容不丢、不报错）；写 100116 正常。
    ("UNIT_TYPE_COMPARE", 2): "UNIT_NAME",
    # GET_UNIT_TYPE 的返回节点仍是 100010（工程内编辑器样本：
    # global_trigger/trigger/UI/Init Update.json 的 UNIT_TYPE_COMPARE）
    ("GET_UNIT_TYPE", 0): "UNIT_TYPE",
    # 整数四则运算的运算符枚举（工程内样本同上：MATH_OPERATION 节点）
    ("MATH_OPERATION", 1): "ARITHMETIC_OPERATOR",
}


# ---------------------------------------------------------------------------
# 画板节点登记表（生成期校验：ITER_UI_COMP_DO 用在无子节点控件上会静默失效）
# ---------------------------------------------------------------------------

_UI_NODE_CHILDREN = {}


def load_ui_nodes(project_root, map_name):
    """读取 maps/<map>/ui/*.json，登记 控件 uid -> 子节点数量。"""
    _UI_NODE_CHILDREN.clear()
    ui_dir = os.path.join(project_root, "maps", map_name, "ui")
    if not os.path.isdir(ui_dir):
        return

    def walk(node):
        uid = node.get("uid")
        if uid:
            _UI_NODE_CHILDREN[uid] = len(node.get("children") or [])
        for child in node.get("children") or []:
            walk(child)

    for fname in sorted(os.listdir(ui_dir)):
        if not fname.endswith(".json"):
            continue
        try:
            with open(os.path.join(ui_dir, fname), "r", encoding="utf-8") as f:
                walk(json.load(f))
        except (ValueError, OSError):
            continue


# ---------------------------------------------------------------------------
# 全局变量登记表（生成期校验：引用不存在的全局变量会被编辑器标红）
# ---------------------------------------------------------------------------

_GLOBAL_VARS = {}
_GLOBAL_VARS_STATE = {"loaded": False, "path": None, "missing_refs": set()}


def load_global_vars(project_root, map_name):
    """读取 maps/<map>/globaltriggervariable.json，登记 变量名 -> 类型。"""
    _GLOBAL_VARS.clear()
    path = os.path.join(project_root, "maps", map_name, "globaltriggervariable.json")
    _GLOBAL_VARS_STATE["path"] = path
    if not os.path.isfile(path):
        _GLOBAL_VARS_STATE["loaded"] = False
        print(f"[WARN] 找不到全局变量文件，跳过引用校验：{path}", file=sys.stderr)
        return
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    for vtype, names in (data.get("variable_dict") or {}).items():
        for vname in names:
            _GLOBAL_VARS[vname] = vtype
    _GLOBAL_VARS_STATE["loaded"] = True


def global_var_type(name):
    """返回全局变量类型；未登记返回 None。"""
    return _GLOBAL_VARS.get(name)


def check_global_var(name, where):
    if not _GLOBAL_VARS_STATE["loaded"]:
        return
    if name in _GLOBAL_VARS:
        return
    _GLOBAL_VARS_STATE["missing_refs"].add(name)
    raise ValueError(
        f"{where}: 引用了未声明的全局变量 '{name}'。"
        f"先用 var_manager.py add '{name}' <类型> --map <地图> 声明，"
        f"并在触发器生成前 restart_editor(save_before_restart=false) 让编辑器读到它。"
        f"（变量文件：{_GLOBAL_VARS_STATE['path']}）"
    )

# ---------------------------------------------------------------------------
# Index loader
# ---------------------------------------------------------------------------

SLIM_PATH = os.path.join(SKILL_DIR, "eca_index_slim.json")

BUILTIN_INDEX_PATCH = {
    "IF_THEN_ELSE": {"p": ["CONDITION_LIST", "ACTION_LIST", "ACTION_LIST"], "t": ["ACTION"], "s": "t_base", "o": []},
    "STRING_COMPARE": {"p": ["STRING", "BOOLEAN_OPERATOR", "STRING"], "t": ["COND", "BOOLEAN"], "s": "t_base", "o": []},
    "GET_STRING_TABLE_VAR_1D": {"p": ["TABLE", "STRING"], "t": ["STRING"], "s": "t_table", "o": []},
    "GET_NEW_TABLE": {"p": [], "t": ["TABLE"], "s": "t_table", "o": []},
    "SET_TABLE_VALUE_1D": {"p": ["TABLE", "[INTEGER,STRING]", "TABLE_VAR"], "t": ["ACTION"], "s": "t_table", "o": []},
    "UNREG_TRIGGER": {"p": ["DYNAMIC_TRIGGER_INSTANCE"], "t": ["ACTION"], "s": "t_base", "o": []},
    "CURRENT_DYNAMIC_TRIGGER_INSTANCE": {"p": [], "t": ["DYNAMIC_TRIGGER_INSTANCE"], "s": "t_base", "o": []},
}

def load_index():
    path = SLIM_PATH if os.path.isfile(SLIM_PATH) else INDEX_PATH
    with open(path, "r", encoding="utf-8") as f:
        idx_data = json.load(f)
    for name, entry in BUILTIN_INDEX_PATCH.items():
        idx_data.setdefault(name, entry)
    return idx_data


# ---------------------------------------------------------------------------
# 参数形状守卫
#
# 背景（实测两次踩坑）：ECA 动作的参数**写错位置或写错个数**时，编辑器既不报错也不飘红，
# 触发器照样 valid=true，只是运行时行为完全相反或零效果 —— 属于最难排查的一类。
#   ① `APPLY_DAMAGE` 两槽静态类型相同、写反 = 伤害全落在施法者身上（见 KEYWORD_ONLY_ACTIONS）。
#   ② `SET_UI_COMP_BIND_ATTR` 只有 4 个位置参数，多传的第 5 个被当成 STRING 悄悄吞掉。
# 这一节把这两类问题挡在生成期。
# ---------------------------------------------------------------------------

_CONT_CACHE = None


def _load_cont_map():
    """按需加载 `eca_index.json` 里的 `cont`（渲染官方签名用）。

    `eca_index_slim.json`（默认索引）里没有 `cont`，只有 `p`/`t`/`s`/`o`，
    所以这里单独按需读一次全量索引并缓存，不影响常规生成速度。
    """
    global _CONT_CACHE
    if _CONT_CACHE is None:
        _CONT_CACHE = {}
        try:
            with open(INDEX_PATH, "r", encoding="utf-8") as f:
                full = json.load(f)
            for key, entry in full.items():
                cont = entry.get("cont") if isinstance(entry, dict) else None
                if cont:
                    _CONT_CACHE[key] = cont
        except (OSError, ValueError):
            pass
    return _CONT_CACHE


def describe_action(name, idx_data):
    """把动作的官方签名渲染成人类可读串（报错信息 / 评审时直接看）。

    `cont` 里的 `{#n}` 就是 `args_list` 的下标 —— 这是判断参数顺序的**唯一一手依据**，
    不要凭文档里的二手转写或记忆推断。
    """
    entry = idx_data.get(name) or {}
    lines = [f"    {name} 的参数位（位置 → 类型）："]
    for i, p in enumerate(entry.get("p") or []):
        lines.append(f"        [{i}] {p}")
    optional = entry.get("o") or []
    if optional:
        lines.append(f"        可选参数（写进 op_arg）：{optional}")
    cont = _load_cont_map().get(name)
    if cont:
        lines.append(f"    官方签名（cont，{{#n}} = 第 n 个参数）：{cont}")
    return "\n".join(lines)


# 「槽位语义易错」的动作：这些动作里多个参数的**静态类型完全相同**（无法靠类型校验发现），
# 位置写法下写反了编辑器不报错、触发器 valid=true，但运行时行为相反。
# 对这些动作 DSL **禁止位置写法**，必须具名传参。
# 键顺序必须与 eca_index 的 `p` 一致；键名取自 `cont` 的槽位含义。
# 单条父触发器可安全注册的子触发器条数上限（实测经验值，见 build_sub_trigger_tree）
MAX_SUB_TRIGGERS_PER_PARENT = 6

KEYWORD_ONLY_ACTIONS = {
    # p = [UNIT_ENTITY, ABILITY, [UNIT_ENTITY,ITEM_ENTITY,DESTRUCTIBLE_ENTITY], DAMAGE_TYPE,
    #      [FLOAT,INTEGER], BOOLEAN]
    # cont = 对{#2}造成{#3}类型的{#4}伤害，{#5}跳字，伤害所属{#0}所属{#1}
    # 第 0 槽与第 2 槽都是单位 → 类型校验抓不到，必须具名。
    "APPLY_DAMAGE": ("source", "ability", "target", "damage_type", "value", "crit"),
}


def first_param_type(param_str):
    """ '[FLOAT,INTEGER]' / 'FLOAT,INTEGER' / 'VAR,VAR_LIST' / 'VAR,VAR,VAR_LIST' → first type """
    s = param_str.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    for sep in (",", "/"):
        if sep in s:
            s = s.split(sep)[0].strip()
    return s


def param_type_choices(param_str):
    """Return all type alternatives from '[INTEGER,STRING]' / 'FLOAT,INTEGER'."""
    s = param_str.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    for sep in (",", "/"):
        if sep in s:
            return [part.strip() for part in s.split(sep) if part.strip()]
    return [s]


# Generic types whose actual arg_type must be inferred from the value
GENERIC_TYPES = {"VAR", "VAR_LIST", "COMPARABLE_VAR"}

# 实体类变量「赋空」必须用官方求值，直接写字面量 0 会被编辑器在保存时清成 null
# （实测：SET_VARIABLE <UNIT_ENTITY变量> = 0 → 保存后变成 null）。
NONE_VALUE_EXPR = {
    "UNIT_ENTITY": "NONE_UNIT",
    "UNIT_GROUP": "NONE_UNIT_GROUP",
}


def infer_type_from_value(value, idx_data):
    """When param is generic (VAR/VAR_LIST), infer arg_type from the value."""
    if isinstance(value, dict) and "type" in value:
        return value["type"]
    if isinstance(value, list) and len(value) >= 1 and isinstance(value[0], str) and value[0] in idx_data:
        # functional sub_type — use return type of that function
        ret_types = idx_data[value[0]]["t"]
        for t in ret_types:
            if t not in ("ACTION", "EVENT", "COND", "BOOLEAN"):
                return t
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "FLOAT"
    if isinstance(value, str):
        return "STRING"
    return "STRING"


def arg_type_id_for(type_name, value=None, idx_data=None, override=None):
    # 已取证的显式覆盖：跳过查表与推断（见 build_arg 的 {"typed_id": N, "value": ...}）。
    if override is not None:
        return int(override)
    choices = param_type_choices(type_name)
    t = choices[0]
    if value is not None and idx_data is not None:
        inferred = first_param_type(infer_type_from_value(value, idx_data))
        if len(choices) > 1 and inferred in choices:
            t = inferred
        elif t == "TABLE_VAR":
            t = inferred
        elif t in GENERIC_TYPES:
            t = inferred
    # VAR itself may be another generic resolution needed
    if t in GENERIC_TYPES:
        # Ultimate fallback: use value dict's "type" field if var ref
        if isinstance(value, dict) and "type" in value:
            t = value["type"]
        else:
            t = "UNIT_ENTITY"  # bare fallback
    if t in ARG_TYPE_ID:
        return ARG_TYPE_ID[t]
    # 未登记的参数类型必须直接报错，不能静默退化。
    # 证据（实测）：arg_type 写错时编辑器**不报错**，而是在 save_editor 时
    # 把参数清成 null（`ROLE_RES_KEY` 写成 100003 即如此），或把整条触发器标成 valid=false
    # （`UNIT_TYPE_COMPARE` 字面量写成 100010）。因此「兜底成 100004(POINT)」只会生成
    # 一个必然损坏的节点，比直接失败更糟。
    raise ValueError(
        f"参数类型 '{type_name}'（解析为 '{t}'）未登记在 ARG_TYPE_ID 中，拒绝生成。\n"
        f"  该类型的 arg_type ID 请先取证再补登记，不要猜：\n"
        f"    1) 在工程内搜索编辑器自带样本（如 global_trigger/**/*.json）中同名字面量的 arg_type；\n"
        f"    2) 或用探针触发器实测候选值（import_eca → save_editor → 回读看是否被清成 null / valid 是否翻转）；\n"
        f"    3) 把结果补进 gen_trigger.py 的 ARG_TYPE_ID，并在注释里写明证据来源与日期。\n"
        f"  参考先例：ROLE_RES_KEY = 100037（证据：global_trigger/function/ui/Refresh Tooltip.json）。"
    )


# ---------------------------------------------------------------------------
# Arg builder
# ---------------------------------------------------------------------------

def _is_hex_uuid(s):
    """Check if string looks like a 32-char hex UUID (custom trigger function)."""
    return len(s) == 32 and all(c in '0123456789abcdef' for c in s)


def _build_custom_func_arg(value, idx_data, eid_gen):
    """Build arg for a custom function (hex UUID not in idx_data).
    Preserves sub_type string for round-trip fidelity."""
    func_name = value[0]
    raw_args = list(value[1:])
    dsl_op = None
    if raw_args and isinstance(raw_args[-1], dict) and "op_arg" in raw_args[-1] and len(raw_args[-1]) == 1:
        dsl_op = raw_args.pop()
    sub_args = [build_arg(a, "VAR", idx_data, eid_gen) for a in raw_args]
    node = {
        "arg_type": 100177,
        "sub_type": func_name,
        "args_list": sub_args,
        "op_arg": [],
        "op_arg_enable": [],
    }
    if dsl_op and dsl_op.get("op_arg"):
        for op_val in dsl_op["op_arg"]:
            node["op_arg"].append(build_arg(op_val, "VAR", idx_data, eid_gen))
            node["op_arg_enable"].append(True)
    return node


# Types that use arg_type=100030 (variable assignment target) for write operations
# instead of their direct type code
SIMPLE_VAR_TYPES = {"FLOAT", "INTEGER", "BOOLEAN", "STRING", "ANGLE"}

# 变量读取 sub_type：以源码派生表打底（各类型在 args/*.py 里自己声明的 `VARIABLE = <值>`），
# 再用手工实测值覆盖。注意源码只给一个 `VARIABLE` 值（按局部变量口径），
# 而全局变量的读取 sub_type 与局部不同（下表的 GLOBAL_* 覆盖即为实测差异）。
VARIABLE_READ_SUBTYPE = {
    **(load_source_data().get("variable_subtype") or {}),
    "FLOAT": 2,
    "BOOLEAN": 2,
    "INTEGER": 6,
    "STRING": 2,
    "ANGLE": 2,
    "TABLE": "VARIABLE",
    "PLAYER": "VARIABLE",
}

# 全局变量的读取 sub_type 与局部变量不同（实测：BOOLEAN / NEW_TIMER 也必须写 "VARIABLE"，
# 写整数会被编辑器清成 null）。
# 判定方式：构造探针触发器 → import_eca → save_editor → 回读，被清成 null 的写法即不合法。
GLOBAL_VARIABLE_READ_SUBTYPE = {
    **VARIABLE_READ_SUBTYPE,
    "BOOLEAN": "VARIABLE",
    "NEW_TIMER": "VARIABLE",
}


def _variable_tuple(var_type, name, scope, use_tuple=True):
    # 全局变量的 tuple 只有 [类型, 名字] 两个元素（编辑器自带样本：
    # global_trigger/trigger/UI/Init Data.json 里的 GLOBAL_BAG_MAX_NUM / UI_Manager）；
    # 只有局部变量才带第三个 scope 标记 "local"，多写 scope 会被判为「无效的变量」。
    items = [var_type, name] if scope == "global" else [var_type, name, scope]
    if use_tuple:
        return {"__tuple__": True, "items": items}
    return items


def build_variable_arg(value, expected_type, idx_data, write_target=False):
    """Build a global-trigger variable reference using editor-compatible tuples."""
    var_type = value.get("type", first_param_type(expected_type))
    if var_type in GENERIC_TYPES or var_type not in ARG_TYPE_ID:
        var_type = value.get("type", "UNIT_ENTITY")
    var_name = value["var"]
    scope = value.get("scope")
    if scope is None:
        # 变量名已在全局变量表里声明时，默认按全局变量引用。
        # 背景（实测）：省略 scope 会被当成局部变量并生成 3 元组，
        # 表现为「引用不存在的局部变量 / valid=false」。
        # 需要在函数/触发器里故意遮蔽同名全局变量时，显式写 "scope": "local"。
        scope = "global" if global_var_type(var_name) else "local"
    if scope == "global":
        # 引用未声明的全局变量 → 编辑器直接标红「无效的变量」，这里提前拦下
        check_global_var(var_name, "变量引用")
        declared = global_var_type(var_name)
        if declared and declared != var_type:
            print(f"[WARN] 全局变量 '{var_name}' 声明为 {declared}，引用写成 {var_type}；"
                  f"已按声明类型改写（类型不符会被编辑器判为无效变量）", file=sys.stderr)
            var_type = declared
        if var_type == "UNIT_NAME" and not (write_target or value.get("write", False)):
            print(f"[WARN] 全局 UNIT_NAME 变量 '{var_name}' 的**读取**在 260616 版本会被编辑器清成 null"
                  f"（实测）；建议改存 INTEGER 编号 + 字面量分支", file=sys.stderr)
    use_tuple = value.get("tuple", True)
    ref = _variable_tuple(var_type, var_name, scope, use_tuple)

    if write_target or value.get("write", False):
        return {
            "arg_type": 100030,
            "sub_type": 1,
            "args_list": [ref],
        }

    override_sub_type = value.get("sub_type", value.get("_sub_type"))
    sub_type = override_sub_type
    if sub_type is None:
        table = GLOBAL_VARIABLE_READ_SUBTYPE if scope == "global" else VARIABLE_READ_SUBTYPE
        sub_type = table.get(var_type, 11)
    return {
        "arg_type": ARG_TYPE_ID.get(var_type, arg_type_id_for(expected_type, value, idx_data)),
        "sub_type": sub_type,
        "args_list": [ref],
    }


def build_arg(value, expected_type, idx_data, eid_gen, sub_trigger_refs=None, arg_type_override=None):
    """Build a single arg node from DSL value."""
    # Forced-type arg: {"typed": "UNIT_NAME", "value": 100001}
    # 编辑器要求 SET_VARIABLE 的值参数 arg_type 与目标变量类型一致
    # （例：把 ARITHMETIC_OPERATION 写进 INTEGER 变量时必须标 100002，
    #  否则保存时该参数被清成 null；把单位 Key 写进 UNIT_NAME 变量时标 100116）。
    if isinstance(value, dict) and "typed" in value and "value" in value:
        forced = value["typed"]
        node = build_arg(value["value"], forced, idx_data, eid_gen, sub_trigger_refs)
        node["arg_type"] = arg_type_id_for(forced, None, None)
        return node
    # 已取证但暂不想改共享表的类型：{"typed_id": <int>, "value": ...}
    # 背景：eca_index.json 里共 311 种参数类型名，ARG_TYPE_ID 只登记了 71 个；
    # 未登记类型现在会直接报错（避免静默生成损坏节点）。若你已在编辑器侧取到正确 id，
    # 可用本写法就地传入；取证后仍应补登记到 ARG_TYPE_ID 并写明证据来源与日期。
    if isinstance(value, dict) and "typed_id" in value and "value" in value:
        sys.stderr.write(
            f"[WARN] 用 typed_id={value['typed_id']} 强制指定 arg_type（绕过 ARG_TYPE_ID）。"
            f"请把该类型的取证结果补登记到 gen_trigger.py 的 ARG_TYPE_ID，"
            f"并在注释里写明证据来源与日期。\n"
        )
        return build_arg(value["value"], expected_type, idx_data, eid_gen, sub_trigger_refs,
                         arg_type_override=value["typed_id"])
    # Custom trigger function (hex UUID) — handle before expected_type inference
    if isinstance(value, list) and len(value) >= 1 and isinstance(value[0], str):
        if _is_hex_uuid(value[0]) and value[0] not in idx_data:
            return _build_custom_func_arg(value, idx_data, eid_gen)

    arg_type = arg_type_id_for(expected_type, value, idx_data, override=arg_type_override)

    # Variable reference: {"var": "unit", "type": "UNIT_ENTITY"}
    if isinstance(value, dict) and "var" in value:
        return build_variable_arg(value, expected_type, idx_data)

    # CONDITION_LIST: nested condition nodes
    if expected_type == "CONDITION_LIST":
        if not isinstance(value, list):
            raise ValueError(f"CONDITION_LIST expects list, got {type(value)}")
        nested = [build_condition(c, idx_data, eid_gen, sub_trigger_refs) for c in value]
        return {
            "arg_type": arg_type,
            "sub_type": 1,
            "args_list": nested,
        }

    # Functional sub_type: ["FUNC_NAME", arg1, arg2, ..., OP_ARG_DICT?]
    if isinstance(value, list) and len(value) >= 1 and isinstance(value[0], str) and value[0] in idx_data:
        func_name = value[0]
        check_sub_type_declared(func_name, expected_type)
        func_def = idx_data[func_name]
        raw_args = list(value[1:])
        # 读属性名的坑（实测）：GET_UNIT_ATTR 第 3 槽用的是**可写属性枚举**，
        # 里面没有 hp_cur / mp_cur。写了这两个之一，编辑器会把参数清成 null 并把
        # **整条触发器**标成 valid=false（症状：功能静默无效、参数表面还在）。
        # 读"当前值"必须用专用取值函数。证据：一个进度条刷新触发器因此整条作废一整个阶段。
        if func_name == "GET_UNIT_ATTR" and len(raw_args) >= 3 and isinstance(raw_args[2], str):
            bad = raw_args[2]
            fix = {"hp_cur": "GET_HP_CUR", "mp_cur": "GET_MP_CUR"}.get(bad)
            if fix:
                raise ValueError(
                    f"GET_UNIT_ATTR 不能读 '{bad}'：该枚举只有可写属性"
                    f"（hp_max / mp_max 可以，'当前值'不行）。读当前生命 / 魔法请改用"
                    f" ['{fix}', <单位>] —— 否则编辑器会把整条触发器判成 valid=false（实测）。"
                )
        dsl_op = None
        # Extract trailing op_arg dict from DSL
        if raw_args and isinstance(raw_args[-1], dict) and "op_arg" in raw_args[-1] and len(raw_args[-1]) == 1:
            dsl_op = raw_args.pop()
        sub_args = []
        # 位置参数超限必须报错，引导改用 op_arg。
        # 证据（实测）：STR_JOIN 传入 3 个位置参数时，编辑器 save_editor 后
        # args_list 只剩 2 个（往返 diff 报「生成 3 / 编辑器 2」），第 3 段被静默丢弃。
        # 该动作实际声明 p=[STRING,STRING] + o=[STRING x8]，第 3~10 段应写进 op_arg。
        n_pos = len(func_def["p"])
        n_opt = len(func_def.get("o") or [])
        # 少传同样要报错：缺的位置参数会让后面的参数整体前移（参数错位），
        # 编辑器不报错，运行时的行为却完全变了（实测踩过 APPLY_DAMAGE 那类坑）。
        if len(raw_args) < n_pos:
            raise ValueError(
                f"{func_name}: 只传了 {len(raw_args)} 个位置参数，但该动作声明了 {n_pos} 个"
                f"（{'、'.join(func_def['p'])}），后面的参数会整体前移造成错位。\n"
                + describe_action(func_name, idx_data)
            )
        for i, sub_val in enumerate(raw_args):
            if i >= n_pos:
                if n_opt:
                    raise ValueError(
                        f"{func_name}: 传入 {len(raw_args)} 个位置参数，但该动作只声明 {n_pos} 个位置参数"
                        f"（另有 {n_opt} 个可选参数）。第 {i + 1} 段及以后请改写成 "
                        f'["{func_name}", <前 {n_pos} 段...>, {{"op_arg": [...]}}]，'
                        f"可选参数按顺序对应 op_arg[0..{n_opt - 1}]（不用的槽位写 null）。"
                    )
                raise ValueError(
                    f"{func_name}: 传入 {len(raw_args)} 个位置参数，超过该动作声明的 {n_pos} 个，"
                    f"多余参数会被编辑器静默丢弃。"
                )
            sub_type_name = func_def["p"][i]
            sub_type_name = PARAM_TYPE_OVERRIDE.get((func_name, i), sub_type_name)
            sub_args.append(build_arg(sub_val, sub_type_name, idx_data, eid_gen, sub_trigger_refs))
        node = {
            "arg_type": arg_type,
            "sub_type": func_name,
            "args_list": sub_args,
        }
        op_params = func_def.get("o", [])
        if op_params:
            node["op_arg"] = [None] * len(op_params)
            node["op_arg_enable"] = [False] * len(op_params)
        # Apply DSL op_arg fill
        if dsl_op and dsl_op.get("op_arg"):
            if not op_params:
                node["op_arg"] = []
                node["op_arg_enable"] = []
            for i, op_val in enumerate(dsl_op["op_arg"]):
                if i >= len(node["op_arg"]):
                    break
                if op_val is None:
                    continue
                if isinstance(op_val, list) and op_val and isinstance(op_val[0], str) and op_val[0] in idx_data:
                    node["op_arg"][i] = build_arg(op_val, "VAR", idx_data, eid_gen, sub_trigger_refs)
                else:
                    # 字面量可选参数（如 STR_JOIN 的第 3~10 段拼接）也要能填。
                    # 旧实现只接受「嵌套函数调用」，字面量会被静默忽略，导致
                    # `["STR_JOIN","A","B",{"op_arg":["C"]}]` 生成出只拼 2 段的节点。
                    # 按该动作声明的可选参数类型（func_def["o"][i]）构造。
                    op_type = op_params[i] if i < len(op_params) else "VAR"
                    node["op_arg"][i] = build_arg(op_val, op_type, idx_data, eid_gen, sub_trigger_refs)
                node["op_arg_enable"][i] = True
        return node

    # ACTION_LIST: nested action nodes
    if expected_type == "ACTION_LIST":
        if not isinstance(value, list):
            raise ValueError(f"ACTION_LIST expects list, got {type(value)}")
        nested = []
        for action in value:
            built = build_action(action, idx_data, eid_gen, sub_trigger_refs)
            if isinstance(built, list):
                nested.extend(built)
            else:
                nested.append(built)
        return {
            "arg_type": arg_type,
            "sub_type": 1,
            "args_list": nested,
        }

    if isinstance(value, dict):
        raise ValueError(
            "dict literal cannot be serialized as an ECA argument directly; "
            "use a variable reference or a call_function TABLE literal"
        )
    if isinstance(value, list):
        raise ValueError(
            "list literal cannot be serialized as an ECA argument directly; "
            "use a supported ECA function expression or a variable reference"
        )

    # Literal
    return {
        "arg_type": arg_type,
        "sub_type": 1,
        "args_list": [value],
    }


def load_custom_event_name_map(project_root, map_name):
    path = os.path.join(project_root, "maps", map_name, "customevent.json")
    if not os.path.isfile(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    names = {}
    for item in data.get("group_info", []):
        if isinstance(item, dict) and item.get("__tuple__") and isinstance(item.get("items"), list):
            values = item["items"]
        elif isinstance(item, list):
            values = item
        else:
            continue
        if len(values) < 2:
            continue
        event_id, event_name = values[0], values[1]
        if not isinstance(event_id, int) or not isinstance(event_name, str):
            continue
        names.setdefault(event_name, set()).add(event_id)
    return {name: sorted(ids) for name, ids in names.items()}


def resolve_custom_event_value(value, custom_event_ids):
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if not isinstance(value, str):
        return value
    if custom_event_ids is None:
        raise ValueError(f"custom event name requires map customevent.json: {value!r}")
    matches = custom_event_ids.get(value, [])
    if not matches:
        raise ValueError(f"unknown custom event name: {value!r}")
    if len(matches) > 1:
        raise ValueError(f"ambiguous custom event name: {value!r} -> {matches}")
    return matches[0]


# ---------------------------------------------------------------------------
# Element builders
# ---------------------------------------------------------------------------

def eid_factory(trigger_id, start=1):
    counter = [start]
    def gen():
        v = trigger_id * 1000000 + counter[0]
        counter[0] += 1
        return v
    return gen


def build_event(spec, idx_data, eid_gen, custom_event_ids=None):
    if not isinstance(spec, list) or not spec:
        raise ValueError(
            "event 写法不对：必须是「事件列表的列表」，即 "
            '{"event": [["INIT_FINISHED"]]}，'
            '而写成 {"event": ["INIT_FINISHED"]} 会生成 event_type: UNKNOWN '
            "（编辑器不报错、触发器静默不触发）。\n"
            f"  实际收到: {spec!r}"
        )
    name = spec[0]
    if name not in idx_data:
        raise ValueError(f"unknown event '{name}'")
    entry = idx_data[name]
    params = entry["p"]
    args = []
    for i, val in enumerate(spec[1:]):
        ft = params[i] if i < len(params) else "VAR"
        ft = PARAM_TYPE_OVERRIDE.get((name, i), ft)
        if name == "RECEIVE_CUSTOM_EVENT" and first_param_type(ft) == "CUS_EVENT":
            val = resolve_custom_event_value(val, custom_event_ids)
        if ft == name:
            # 包装类事件（如 GENERIC_UNIT_EVENT 的 "任意单位事件" 参数）编辑器要求
            # sub_type 写成事件名本身，写成整数 1 会在保存时被清成 null。
            # 参考工程内编辑器保存的样本：
            # maps/EntryMap/global_trigger/trigger/UI/Init Update.json
            #
            # ⚠️ 实测：这里的事件名必须是**标量字符串**。
            #   DSL ✅ ["GENERIC_UNIT_EVENT", "ET_UNIT_DIE"]          -> args_list: ["ET_UNIT_DIE"]
            #   DSL ❌ ["GENERIC_UNIT_EVENT", ["ET_UNIT_DIE"]]        -> args_list: [["ET_UNIT_DIE"]]
            #   写成数组时：--dry-run / import_eca / 往返 diff / audit_triggers 全绿，
            #   但编辑器 save 时走 check_prefab_name → `['ET_UNIT_DIE'] in <set>`
            #   → TypeError: cannot use 'list' as a set element
            #   → **整个保存失败并把编辑器会话搞脏**（不是单个触发器失效）。
            #   注意：build_arg 里那条「list literal cannot be serialized」的守卫
            #   在这个分支之前被短路了，所以必须在这里单独拦。
            if not isinstance(val, str):
                raise ValueError(
                    f'{name}: 包装类事件的事件名必须以**字符串**传入 DSL，不要写成数组。\n'
                    f'  ❌ ["{name}", {val!r}]\n'
                    f'  ✅ ["{name}", "ET_UNIT_DIE"]\n'
                    f'  数组会生成 args_list: [[...]]：导入看似成功、往返 diff 也一致，\n'
                    f'  但编辑器保存时会抛 TypeError: unhashable type: list（整次保存失败、'
                    f'编辑器会话变脏）。'
                )
            args.append({
                "arg_type": ARG_TYPE_ID.get(ft, 100008),
                "sub_type": name,
                "args_list": [val],
            })
        else:
            args.append(build_arg(val, ft, idx_data, eid_gen))
    node = {
        "event_type": name,
        "element_id": eid_gen(),
        "enable": True,
        "args_list": args,
    }
    op_params = entry.get("o", [])
    if op_params:
        node["op_arg"] = [None] * len(op_params)
        node["op_arg_enable"] = [False] * len(op_params)
    return node


def build_condition(spec, idx_data, eid_gen, sub_trigger_refs=None):
    name = spec[0]
    if name not in idx_data:
        raise ValueError(f"unknown condition '{name}'")
    entry = idx_data[name]
    params = entry["p"]
    args = []
    for i, val in enumerate(spec[1:]):
        ft = params[i] if i < len(params) else "VAR"
        ft = PARAM_TYPE_OVERRIDE.get((name, i), ft)
        args.append(build_arg(val, ft, idx_data, eid_gen, sub_trigger_refs))
    node = {
        "condition_type": name,
        "element_id": eid_gen(),
        "enable": True,
        "args_list": args,
    }
    op_params = entry.get("o", [])
    if op_params:
        node["op_arg"] = [None] * len(op_params)
        node["op_arg_enable"] = [False] * len(op_params)
    return node


def _is_table_literal_arg(spec):
    return (
        isinstance(spec, dict)
        and spec.get("type") == "TABLE"
        and isinstance(spec.get("value"), dict)
    )


def _table_temp_var_name(func_id, arg_index, optional=False):
    kind = "op" if optional else "arg"
    return f"__table_{func_id[:8]}_{kind}_{arg_index + 1}"


def _build_table_literal_actions(var_name, values, idx_data, eid_gen):
    actions = [
        build_action(
            ["SET_VARIABLE", {"var": var_name, "type": "TABLE"}, ["GET_NEW_TABLE"]],
            idx_data,
            eid_gen,
        )
    ]
    for key, value in values.items():
        if isinstance(value, (dict, list)):
            raise ValueError(
                "nested TABLE literal is not supported; "
                "use a predeclared TABLE variable or simplify the DSL"
            )
        actions.append(
            build_action(
                ["SET_TABLE_VALUE_1D", {"var": var_name, "type": "TABLE"}, key, value],
                idx_data,
                eid_gen,
            )
        )
    return actions


def _build_typed_call_arg(spec, idx_data, eid_gen):
    if isinstance(spec, dict) and "value" in spec and "type" in spec:
        if spec["type"] == "TABLE" and isinstance(spec["value"], (dict, list)):
            raise ValueError("TABLE literal must be expanded before building CALL_TRIGGER_FUNC")
        return build_arg(spec["value"], spec["type"], idx_data, eid_gen)
    if isinstance(spec, dict) and "var" in spec and "type" in spec:
        return build_arg(spec, spec["type"], idx_data, eid_gen)
    return build_arg(spec, "VAR", idx_data, eid_gen)


def build_function_call(spec, idx_data, eid_gen):
    """Build CALL_TRIGGER_FUNC with typed inputs and explicit return targets."""
    call = spec.get("call_function", spec)
    func_id = call.get("func_id", call.get("id"))
    if not isinstance(func_id, str) or not _is_hex_uuid(func_id):
        raise ValueError("call_function.func_id must be a 32-character lowercase hex id")

    prelude_actions = []
    input_args = []
    for i, value in enumerate(call.get("args", [])):
        if _is_table_literal_arg(value):
            var_name = _table_temp_var_name(func_id, i)
            prelude_actions.extend(_build_table_literal_actions(var_name, value["value"], idx_data, eid_gen))
            input_args.append(build_arg({"var": var_name, "type": "TABLE"}, "TABLE", idx_data, eid_gen))
        else:
            input_args.append(_build_typed_call_arg(value, idx_data, eid_gen))

    call_arg = {
        "arg_type": 100177,
        "sub_type": func_id,
        "args_list": input_args,
        "op_arg": [],
        "op_arg_enable": [],
    }
    for i, value in enumerate(call.get("optional_args", [])):
        if value is None:
            call_arg["op_arg"].append(None)
            call_arg["op_arg_enable"].append(False)
        elif _is_table_literal_arg(value):
            var_name = _table_temp_var_name(func_id, i, optional=True)
            prelude_actions.extend(_build_table_literal_actions(var_name, value["value"], idx_data, eid_gen))
            call_arg["op_arg"].append(build_arg({"var": var_name, "type": "TABLE"}, "TABLE", idx_data, eid_gen))
            call_arg["op_arg_enable"].append(True)
        else:
            call_arg["op_arg"].append(_build_typed_call_arg(value, idx_data, eid_gen))
            call_arg["op_arg_enable"].append(True)

    output_args = []
    for target in call.get("returns", []):
        if not isinstance(target, dict) or "var" not in target or "type" not in target:
            raise ValueError("call_function.returns entries require 'var' and 'type'")
        output_args.append(build_variable_arg(target, target["type"], idx_data, write_target=False))

    call_action = {
        "action_type": "CALL_TRIGGER_FUNC",
        "args_list": [call_arg, *output_args],
        "bp": call.get("bp", False),
        "call_rt_arg_idxes": list(range(len(output_args))),
        "element_id": eid_gen(),
        "enable": call.get("enable", True),
    }
    if prelude_actions:
        return [*prelude_actions, call_action]
    return call_action


def resolve_sub_trigger_ref(ref, sub_trigger_refs):
    if sub_trigger_refs is None:
        raise ValueError("register_sub_trigger is only valid inside build_trigger")
    key = ref
    if isinstance(ref, str) and ref.isdigit():
        key = int(ref)
    if key not in sub_trigger_refs:
        raise ValueError(f"unknown sub_trigger reference: {ref!r}")
    return sub_trigger_refs[key]


def build_action(spec, idx_data, eid_gen, sub_trigger_refs=None):
    if isinstance(spec, dict) and "call_function" in spec:
        return build_function_call(spec, idx_data, eid_gen)
    if isinstance(spec, dict) and "register_sub_trigger" in spec:
        return resolve_sub_trigger_ref(spec["register_sub_trigger"], sub_trigger_refs)
    if not isinstance(spec, list) or not spec:
        return {"action_type": "UNKNOWN", "element_id": eid_gen(), "enable": True, "bp": False, "args_list": []}
    name = spec[0]
    # Numeric action_type from custom actions (not in eca_index)
    if isinstance(name, int):
        node = {"action_type": name, "element_id": eid_gen(), "enable": True, "bp": False, "args_list": []}
        raw = list(spec[1:])
        for val in raw:
            node["args_list"].append(build_arg(val, "VAR", idx_data, eid_gen, sub_trigger_refs))
        return node
    if name not in idx_data:
        raise ValueError(f"unknown action '{name}'")
    entry = idx_data[name]
    params = entry["p"]
    raw = list(spec[1:])
    # 参数形状守卫 ①：易错动作禁止位置写法，必须具名（键顺序按定义展开）
    named_keys = KEYWORD_ONLY_ACTIONS.get(name)
    if named_keys:
        # 判据：唯一一个参数、是 dict、且**至少一个键命中槽位名**。
        # 不能只看「是 dict」——变量引用 {'var':..,'type':..} 也是 dict，但它一个槽位名都不命中。
        is_named = (len(raw) == 1 and isinstance(raw[0], dict)
                    and bool(set(raw[0]) & set(named_keys)))
        if not is_named:
            raise ValueError(
                f"动作 '{name}' 必须具名传参，禁止位置写法：\n"
                f"    ['{name}', {{{', '.join(repr(k) + ': ...' for k in named_keys)}}}]\n"
                f"    原因：该动作的多个参数静态类型相同（位置写反了编辑器不报错、\n"
                f"    触发器仍是 valid=true，但运行时行为相反 —— 实测踩过）。\n"
                + describe_action(name, idx_data)
            )
        missing = [k for k in named_keys if k not in raw[0]]
        unknown = [k for k in raw[0] if k not in named_keys]
        if missing or unknown:
            raise ValueError(
                f"动作 '{name}' 的具名参数不匹配："
                f"缺少 {missing or '无'}，多余 {unknown or '无'}。\n"
                + describe_action(name, idx_data)
            )
        raw = [raw[0][k] for k in named_keys]
    # 动作位不支持可选参数：末尾直接写 {'op_arg': ...} 只会被当成多出来的位置参数。
    # 需要可选参数时改写成赋值形式（嵌套在别的参数的表达式里），见 eca-json-builder.md。
    if raw and isinstance(raw[-1], dict) and "op_arg" in raw[-1]:
        raise ValueError(
            f"动作 '{name}' 末尾不能直接写 {{'op_arg': ...}}：**动作位不支持可选参数**。\n"
            f"    可选参数只能写在函数式参数位（嵌套在别的参数的表达式里），例如：\n"
            f"        ['SET_VARIABLE', {{'var': '<变量>', 'type': '<类型>', 'scope': 'global'}},\n"
            f"         ['{name}', <位置参数...>, {{'op_arg': [...]}}]]\n"
            + describe_action(name, idx_data)
        )
    extra = {}
    # Only extract trailing dicts that have known-only-extra keys (never variable refs)
    while raw and isinstance(raw[-1], dict):
        d = raw[-1]
        is_var = "var" in d and "type" in d
        is_op = "op_arg" in d
        is_extra = "bp" in d or "call_rt_arg_idxes" in d
        if is_var or is_op:
            break
        if is_extra:
            extra.update(raw.pop())
        else:
            break
    # 参数形状守卫 ②：位置参数个数必须与定义一致（少传/多传都会被编辑器静默吞掉）
    if len(raw) != len(params):
        raise ValueError(
            f"动作 '{name}' 的位置参数个数不对：DSL 给了 {len(raw)} 个，定义要求 {len(params)} 个。\n"
            + describe_action(name, idx_data)
            + "\n    可选参数请放进末尾的 {'op_arg': [...], 'op_arg_enable': [...]}，不要位置传入。"
        )
    args = []
    # SET_VARIABLE：值参数 arg_type 必须与**目标变量类型**一致，否则保存时被清成 null
    # （实测：把 MATH_OPERATION 写进 INTEGER 变量，arg_type 用表达式自身的
    #  FLOAT(100000) 会被清空；改成 100002 后正常）。这里由目标类型反推。
    set_target_type = None
    if name == "SET_VARIABLE" and raw and isinstance(raw[0], dict) and "var" in raw[0]:
        set_target_type = raw[0].get("type") or first_param_type(params[0] if params else "VAR")
    # 编辑器保存时会**整体丢弃** ELSE 分支里的嵌套 IF（实测）→ 生成期直接拦下
    if name == "IF_THEN_ELSE" and len(raw) >= 3 and isinstance(raw[2], list):
        for branch in raw[2]:
            if isinstance(branch, list) and branch and branch[0] == "IF_THEN_ELSE":
                raise ValueError(
                    "IF_THEN_ELSE 不能嵌在 ELSE 分支的动作列表里：编辑器保存时会整体丢弃该嵌套 IF"
                    "（实测）。请平铺成同层级多个 IF_THEN_ELSE，或把嵌套 IF 放进 THEN 分支。"
                )
    # ITER_UI_COMP_DO 的语义是「遍历该控件的**子节点**」；用在无子节点的控件上会静默不注册
    if name == "ITER_UI_COMP_DO" and len(raw) >= 2 and isinstance(raw[1], str):
        target_uid = raw[1]
        if target_uid in _UI_NODE_CHILDREN:
            if _UI_NODE_CHILDREN[target_uid] == 0:
                raise ValueError(
                    f"ITER_UI_COMP_DO('{target_uid}') 的目标控件没有子节点，遍历为空 → 内部动作一条都不会执行"
                    f"（实测：按钮事件因此一个都没注册上）。"
                    f"直接把控件 uid 交给 CREATE_UI_COMP_EVENT_EX_EX。"
                )
        else:
            print(f"[WARN] ITER_UI_COMP_DO 的目标 uid 不在画板 JSON 中：{target_uid}（无法校验子节点）",
                  file=sys.stderr)
    for i, val in enumerate(raw):
        fallback_type = params[i] if i < len(params) else "VAR"
        fallback_type = PARAM_TYPE_OVERRIDE.get((name, i), fallback_type)
        if name == "SET_VARIABLE" and i == 1 and set_target_type:
            fallback_type = set_target_type
        if name == "SET_VARIABLE" and i == 0 and isinstance(val, dict) and "var" in val:
            args.append(build_variable_arg(val, fallback_type, idx_data, write_target=True))
        elif name == "SET_VARIABLE" and i == 1 and isinstance(val, (int, float)) and not isinstance(val, bool) and val == 0:
            target = raw[0] if raw and isinstance(raw[0], dict) else {}
            none_expr = NONE_VALUE_EXPR.get(target.get("type"))
            if none_expr:
                sys.stderr.write(
                    f"[INFO] SET_VARIABLE '{target.get('var')}' ({target.get('type')}) 赋 0 "
                    f"→ 改写为 {none_expr}（字面量 0 会被编辑器清成 null）\n"
                )
                args.append(build_arg([none_expr], fallback_type, idx_data, eid_gen, sub_trigger_refs))
            else:
                args.append(build_arg(val, fallback_type, idx_data, eid_gen, sub_trigger_refs))
        else:
            args.append(build_arg(val, fallback_type, idx_data, eid_gen, sub_trigger_refs))
    node = {
        "action_type": name,
        "element_id": eid_gen(),
        "enable": True,
        "bp": extra.get("bp", False),
        "args_list": args,
    }
    if name == "IF_THEN_ELSE":
        # Editor-authored IF nodes always carry this branch-layout marker.
        node["fake_op"] = [2]
    # 定时器动作必须带 local_var，否则编辑器保存时报错 → 保存失败并把地图目录清空。
    # 依据（实测）：编辑器自己写出的定时器动作全部带该字段
    #   RUN_LOOP_TIMER 7/7、RUN_LOOP_TIMER_NO_SAVE 2/2、RUN_ONCE_TIMER 1/1
    #   （DELETE_TIMER 不带，故排除）；`eca-json-builder.md` 也写明
    #   「RUN_ONCE_TIMER_NO_SAVE 必须带 local_var，否则编辑器报错」。
    if name.startswith("RUN_") and "TIMER" in name:
        node["local_var"] = {"__tuple__": True, "items": [{}, {}]}
    if "call_rt_arg_idxes" in extra:
        node["call_rt_arg_idxes"] = extra["call_rt_arg_idxes"]
    op_params = entry.get("o", [])
    if op_params:
        node["op_arg"] = [None] * len(op_params)
        node["op_arg_enable"] = [False] * len(op_params)
    return node


def build_action_list(actions, idx_data, eid_gen, sub_trigger_refs=None):
    built_actions = []
    for action in actions:
        built = build_action(action, idx_data, eid_gen, sub_trigger_refs)
        if isinstance(built, list):
            built_actions.extend(built)
        else:
            built_actions.append(built)
    return built_actions


# ---------------------------------------------------------------------------
# Trigger builder
# ---------------------------------------------------------------------------

def collect_variables(specs, include_sub_triggers=False, collect_reads=True):
    """Walk all event/condition/action specs and collect LOCAL variable declarations.
    Global-scoped variables are skipped (declared in globaltriggervariable.json)."""
    vars_found = {}  # name -> type

    def collect_var(value):
        if isinstance(value, dict) and "var" in value and value.get("scope", "local") != "global":
            vars_found[value["var"]] = value.get("type", "UNIT_ENTITY")

    def collect_call_function(action, read_ok=True):
        call = action["call_function"]
        func_id = call.get("func_id", call.get("id", ""))
        for i, value in enumerate(call.get("args", [])):
            if _is_table_literal_arg(value):
                vars_found[_table_temp_var_name(func_id, i)] = "TABLE"
            walk(value, read_ok)
        for i, value in enumerate(call.get("optional_args", [])):
            if _is_table_literal_arg(value):
                vars_found[_table_temp_var_name(func_id, i, optional=True)] = "TABLE"
            walk(value, read_ok)
        for target in call.get("returns", []):
            collect_var(target)

    def walk(value, read_ok=True):
        if isinstance(value, dict):
            if "call_function" in value:
                collect_call_function(value, read_ok)
                return
            if "var" in value:
                if read_ok or value.get("declare", False):
                    collect_var(value)
                return
            for child in value.values():
                walk(child, read_ok)
        elif isinstance(value, list):
            for child in value:
                walk(child, read_ok)

    def walk_action(action, read_ok=True):
        if isinstance(action, dict) and "register_sub_trigger" in action:
            return
        if isinstance(action, dict) and "call_function" in action:
            collect_call_function(action, read_ok)
            return
        if isinstance(action, list) and action:
            if action[0] == "SET_VARIABLE" and len(action) > 1:
                collect_var(action[1])
                for child in action[2:]:
                    walk(child, read_ok)
            else:
                walk(action, read_ok)
            return
        walk(action, read_ok)

    walk(specs.get("event", []))
    walk(specs.get("condition", []))
    for action in specs.get("action", []):
        walk_action(action, collect_reads)
    if include_sub_triggers:
        for child in specs.get("sub_triggers", []):
            vars_found.update(collect_variables(child, include_sub_triggers=True, collect_reads=True))

    return vars_found


def build_var_data(variables):
    """Build var_data from collected variables.
    var_data[0]: type -> {name -> 0}
    var_data[1]: name -> 0
    var_data[2]: ordered name list
    """
    by_type = {}
    by_name = {}
    names = []
    defaults = {
        "STRING": "",
        "BOOLEAN": False,
        "FLOAT": 0.0,
        "ANGLE": 0.0,
        "TABLE": None,
        # POINT 必须给 3 个分量：编辑器 commons.black_box.meta.EType.FPoint.to_value()
        # 会执行 (float(val[0]), float(val[1]), float(val[2]))，默认值给整数 0 会抛
        # "TypeError: 'int' object is not subscriptable"，整次 save 中断并把地图目录写空。
        # 实测：栈里就是 <local <变量名> = 0> → EType.FPoint.to_value。
        "POINT": [0, 0, 0],
    }
    for name, vtype in variables.items():
        default = defaults.get(vtype, 0)
        by_type.setdefault(vtype, {})[name] = default
        by_name[name] = 0 if vtype != "POINT" else default
        names.append(name)
    return [by_type, by_name, names]


def stable_sub_trigger_id(parent_id, name, used_ids):
    seed = f"{parent_id}:{name}".encode("utf-8")
    tid = 10000000 + (zlib.crc32(seed) % 900000000)
    while tid in used_ids:
        tid += 1
    return tid


def prepare_sub_trigger_refs(spec, parent_id):
    refs = {}
    used_ids = {parent_id}
    for child in spec.get("sub_triggers", []):
        if "name" not in child:
            raise ValueError("sub_trigger spec missing 'name'")
        if "id" not in child:
            child["id"] = stable_sub_trigger_id(parent_id, child["name"], used_ids)
        tid = child["id"]
        if tid in used_ids or tid in refs:
            raise ValueError(f"duplicate sub_trigger id: {tid}")
        if child["name"] in refs:
            raise ValueError(f"duplicate sub_trigger name: {child['name']}")
        refs[child["name"]] = tid
        refs[tid] = tid
        refs[str(tid)] = tid
        used_ids.add(tid)
    return refs


def build_sub_trigger_tree(spec, idx_data, parent_id, custom_event_ids=None):
    result = {}
    children = spec.get("sub_triggers", [])
    # 实测：一条父触发器注册的子触发器多了以后，**注册顺序靠后的那几条
    # 收不到控件事件**（10 条时后 3 条全哑；把这几条前移到列表最前，立刻恢复）。
    # 这里只告警不报错（老工程可能已经在用），但建议按画板 / 功能拆成多条父触发器。
    if len(children) > MAX_SUB_TRIGGERS_PER_PARENT:
        sys.stderr.write(
            f"[WARN] 父触发器 '{spec.get('name')}' 注册了 {len(children)} 条子触发器"
            f"（建议 <= {MAX_SUB_TRIGGERS_PER_PARENT}）。实测：注册项多了以后排在后面的"
            f"子触发器收不到控件事件（10 条时后 3 条全哑，前移后立刻恢复）。"
            f"建议按画板 / 功能拆成多条父触发器，或把关键子触发器放在注册列表前面。\n"
        )
    for child_spec in children:
        child = build_trigger(child_spec, idx_data, child_spec["id"], parent_id=parent_id, is_sub_trigger=True, custom_event_ids=custom_event_ids)
        descendants = child.pop("sub_trigger", {})
        child_key = str(child["trigger_id"])
        if child_key in result:
            raise ValueError(f"duplicate sub_trigger id: {child['trigger_id']}")
        result[child_key] = child
        for desc_key, desc in descendants.items():
            if desc_key in result:
                raise ValueError(f"duplicate sub_trigger id: {desc_key}")
            result[desc_key] = desc
    return result


def _guard_runtime_pitfalls(trigger: dict, spec: dict) -> None:
    """拦截已知会静默失效的写法（不是结构问题，编辑器仍会返回 success）。"""
    dumped = json.dumps(trigger, ensure_ascii=False)
    events = spec.get("event", [])
    born = any(
        isinstance(e, list) and len(e) >= 2
        and e[0] == "GENERIC_UNIT_EVENT" and e[1] == "ET_UNIT_BORN"
        for e in events
    )
    if born and '"KILLED_UNIT"' in dumped:
        raise ValueError(
            "GENERIC_UNIT_EVENT + ET_UNIT_BORN 里不能用 KILLED_UNIT："
            "实测保存后整条触发器 valid=false。出生事件取单位请改用 "
            '["GET_UNIT_FROM_EVENT"]。'
        )
    if '"GROUP_ADD_UNIT"' in dumped:
        print(
            "[WARN] 检测到 GROUP_ADD_UNIT：实测写入全局 UNIT_GROUP 变量后运行时读回为 0。"
            "优先改用 PLAYER_UNIT_GROUP / UNIT_TYPE_UNIT_GROUP 等内置单位组；"
            "必须维护自定义组时请先做运行时探针确认。",
            file=sys.stderr,
        )


def build_trigger(spec, idx_data, default_id, parent_id=None, is_sub_trigger=False, custom_event_ids=None):
    if "name" not in spec:
        raise ValueError("trigger spec missing 'name'")
    tid = spec.get("id", default_id)
    spec["id"] = tid
    eid_gen = eid_factory(tid)
    sub_trigger_refs = prepare_sub_trigger_refs(spec, tid)
    # `event` 必须是「事件列表的列表」：写成一维数组时会生成 event_type: UNKNOWN
    # （编辑器不报错、触发器静默不触发），所以在这里前置拦下并给出正确写法。
    _ev = spec.get("event", [])
    for _i, _e in enumerate(_ev):
        if not isinstance(_e, list) or not _e:
            raise ValueError(
                f"触发器 '{spec.get('name')}' 的 event[{_i}] 写法不对：{_e!r}\n"
                f'  正确写法: "event": [["INIT_FINISHED"]]  （事件列表的列表，每个事件自身是 [事件名, *args]）\n'
                f'  写成一维数组会生成 event_type: UNKNOWN —— 编辑器不报错，但触发器永远不触发。'
            )
    variables = collect_variables(
        spec,
        include_sub_triggers=not is_sub_trigger,
        collect_reads=not is_sub_trigger,
    )
    trigger = {
        "trigger_name": spec["name"],
        "trigger_id": tid,
        "p_trigger_id": parent_id,
        "group_id": spec.get("group_id", 0),
        "enabled": spec.get("enabled", not is_sub_trigger),
        "valid": spec.get("valid", True),
        "call_enabled": spec.get("call_enabled", True),
        "event": [build_event(e, idx_data, eid_gen, custom_event_ids) for e in spec.get("event", [])],
        "condition": [build_condition(c, idx_data, eid_gen, sub_trigger_refs) for c in spec.get("condition", [])],
        "action": build_action_list(spec.get("action", []), idx_data, eid_gen, sub_trigger_refs),
        "var_data": build_var_data(variables),
    }
    if is_sub_trigger:
        trigger["is_conf"] = spec.get("is_conf", True)
    lint_trigger_player(trigger, idx_data)
    _guard_runtime_pitfalls(trigger, spec)
    if len(spec.get("sub_triggers", [])) > 6:
        print(
            f"[WARN] 触发器 '{spec.get('name')}' 注册了 {len(spec.get('sub_triggers', []))} 个子触发器："
            "实测单父触发器超过 6 条时，排在后面的子触发器收不到控件事件。请拆成多个父触发器。",
            file=sys.stderr,
        )
    sub_triggers = build_sub_trigger_tree(spec, idx_data, tid, custom_event_ids)
    if str(tid) in sub_triggers:
        raise ValueError(f"sub_trigger id conflicts with parent trigger id: {tid}")
    if sub_triggers:
        trigger["sub_trigger"] = sub_triggers
    return trigger


# ---------------------------------------------------------------------------
# 语义守卫：TRIGGER_PLAYER 在物编事件触发器里非法
# ---------------------------------------------------------------------------

# TRIGGER_PLAYER 能否使用，本质取决于「该事件是否提供 ROLE_ID」。
# 依据（源码 GameTriggerRoleArg.py）：`TRIGGER_PLAYER` 的表达式是
#   EAGetValue(EParams.ROLE_ID) → GameAPI:get_role_by_role_id(...)
# 即它读的是**事件参数 ROLE_ID**；事件不提供该参数时就用不了。
#
# 事件→ROLE_ID 的映射不在 black_box 这一层声明（只在引擎侧），无法自动派生，
# 因此这里用实测过的白名单：
#   - t_player  `ANY_ROLE_JOIN_GAME`            → 可用（多条触发器实测 valid=true）
#   - t_ui      `TRIGGER_COMPONENT_EVENT` 子触发器 → 可用（同上）
#   - t_click   键盘/鼠标事件（同类玩家输入事件）
#   - t_system  `INIT_FINISHED`                  → **不可用**（实测：
#       同一动作改用具体玩家字面量后 valid 由 false 变 true）
#   - 物编事件（t_unit/t_ability/…）              → 不可用（实测）
_TRIGGER_PLAYER_OK_SUBTYPES = ("t_player", "t_ui", "t_click")
_UNIT_FAMILY_PREFIXES = ("t_unit", "t_ability", "t_item", "t_modifier",
                         "t_projectile", "t_destructible", "t_physics")


def lint_trigger_player(trigger, idx_data):
    """物编事件触发器里出现 TRIGGER_PLAYER 时直接报错。

    证据（实测）：事件为 `GENERIC_UNIT_EVENT`(s=t_unit) 的两条触发器持续
    `valid=false`，而往返 diff 显示**所有参数都完好**（既没被清成 null、编辑器也不报错），
    因此极难定位；把 TRIGGER_PLAYER 换成 OWNER_PLAYER(单位) 后立即恢复 valid=true。
    """
    sub_types = set()
    for ev in trigger.get("event") or []:
        entry = idx_data.get(ev.get("event_type")) or {}
        sub_types.add(entry.get("s") or "")
    if not sub_types:
        return
    # 已实测「用不了 TRIGGER_PLAYER」的类别：物编事件家族 + t_system（如 INIT_FINISHED）。
    bad = sorted(s for s in sub_types
                 if str(s).startswith(_UNIT_FAMILY_PREFIXES) or s == "t_system")
    unknown = sorted(s for s in sub_types
                     if s not in _TRIGGER_PLAYER_OK_SUBTYPES and s not in bad)
    if not bad and not unknown:
        return  # 全部事件都在已验证可用的类别里

    hits = []

    def walk(node):
        if isinstance(node, dict):
            if node.get("sub_type") == "TRIGGER_PLAYER":
                hits.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(trigger.get("action") or [])
    walk(trigger.get("condition") or [])
    if not hits:
        return
    detail = (f"事件类别 {bad} 已实测拿不到 ROLE_ID" if bad
              else f"事件类别 {unknown} 尚未验证是否提供 ROLE_ID")
    raise ValueError(
        f"触发器 '{trigger.get('trigger_name')}' 用了 TRIGGER_PLAYER（触发玩家），但"
        f"该事件类别不支持：{detail}。\n"
        f"  依据（源码 GameTriggerRoleArg.py）：TRIGGER_PLAYER 读的是事件参数 ROLE_ID，"
        f"事件不提供该参数时就用不了。\n"
        f"  后果：整条触发器被编辑器标成 valid=false，且参数完好、不报错，极难排查"
        f"（实测 t_unit / t_system）。\n"
        f"  请改用 OWNER_PLAYER(<单位>) 、具体玩家或 GET_CLIENT_ROLE；命中 {len(hits)} 处。"
    )


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def write_trigger(trigger, map_name, project_root):
    out_dir = os.path.join(project_root, "maps", map_name, "global_trigger", "trigger")
    os.makedirs(out_dir, exist_ok=True)
    fname = trigger["trigger_name"] + ".json"
    path = os.path.join(out_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(trigger, f, ensure_ascii=False, indent=4)
    return path, fname, out_dir


def update_index(out_dir, fname):
    idx_path = os.path.join(out_dir, "index.txt")
    if os.path.isfile(idx_path):
        with open(idx_path, "r", encoding="utf-8") as f:
            idx = json.load(f)
    else:
        idx = {}
    if fname not in idx:
        idx[fname] = max(idx.values(), default=-1) + 1
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=4)
    return idx[fname]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def find_project_root(start=None):
    """Walk up from a path looking for a project 'maps' directory."""
    cur = os.path.abspath(start or os.getcwd())
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    while True:
        if os.path.isdir(os.path.join(cur, "maps")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("dsl", help="path to DSL JSON file")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--root", default=None, help="project root (auto-detected)")
    args = p.parse_args(argv)

    with open(args.dsl, "r", encoding="utf-8") as f:
        dsl = json.load(f)

    map_name = dsl.get("map", "EntryMap")
    triggers = dsl.get("triggers", [])
    if not triggers:
        print("DSL contains no triggers")
        return 1

    idx_data = load_index()
    if args.root:
        root = os.path.abspath(args.root)
        if not os.path.isdir(os.path.join(root, "maps")):
            raise ValueError(f"project root has no maps directory: {root}")
    else:
        root = find_project_root(args.dsl) or find_project_root()
        if root is None:
            raise ValueError("project root not found; pass --root")
    custom_event_ids = load_custom_event_name_map(root, map_name)
    # 生成期校验所需的项目数据（全局变量表 / 画板节点表）
    load_global_vars(root, map_name)
    load_ui_nodes(root, map_name)

    # auto-id seed: 1718000001 + N
    base_id = 1718000001
    used_ids = {t.get("id") for t in triggers if t.get("id")}
    auto_id = base_id
    while auto_id in used_ids:
        auto_id += 1

    results = []
    for t_spec in triggers:
        if "id" not in t_spec:
            t_spec["id"] = auto_id
            auto_id += 1
            while auto_id in used_ids:
                auto_id += 1
        trig = build_trigger(t_spec, idx_data, t_spec["id"], custom_event_ids=custom_event_ids)
        if args.dry_run:
            print(json.dumps(trig, ensure_ascii=False, indent=2))
            results.append((trig["trigger_name"], None, None))
        else:
            path, fname, out_dir = write_trigger(trig, map_name, root)
            idx = update_index(out_dir, fname)
            results.append((trig["trigger_name"], path, idx))

    if not args.dry_run:
        for name, path, idx in results:
            print(f"OK [{idx}]  {name}  -> {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
