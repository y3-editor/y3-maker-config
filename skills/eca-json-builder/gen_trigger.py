# -*- coding: utf-8 -*-
"""ECA trigger generator — read compact DSL, emit full trigger JSON + update index.txt.

DSL format (JSON, can have multiple triggers in one file):
{
  "map": "EntryMap",                  # optional, default EntryMap
  "triggers": [
    {
      "name": "游戏初始化欢迎",
      "id": 1718000001,               # optional, auto-generated if omitted
      "event": ["INIT_FINISHED"],
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

ARG_TYPE_ID = {
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
    "PROJECTILE_ENTITY": 100010,
    "PROJECTILE": 100031,
    "NEW_TIMER": 100181,
    "DAMAGE_TYPE": 100064,
    "ABILITY_NAME": 100046,   # shares same ID as MODIFIER_KEY
    "ITEM_ENTITY": 100021,
    "ITEM_NAME": 100116,       # shares with UNIT_NAME
    "LINK_SFX_ENTITY": 100148, # shares with SFX_ENTITY
    "PLAYER_GROUP": 100026,    # shares with UNIT_GROUP
    "CURVED_PATH": 100182,
    "POLYGON": 100035,
    "ROUND_AREA": 100064,
    "UNIT_WRITE_ATTRIBUTE": 100077,
    "DYNAMIC_TRIGGER_INSTANCE": 100178,
    "UI_PREFAB_INSTANCE": 100301,
    "MODIFIER": 100046,
    "VARIABLE": 100077,
    "CONDITION_LIST": 100021,
    "CUS_EVENT": 100238,
    "CUS_PARAM": 100240,
    "ABILITY_FLOAT_ATTRS": 100042,
    "ABILITY_INT_ATTRS": 100042,
    "EVENT_UNIT": 100006,
    "UNIT_TYPE": 100116,
    "BOOLEAN_OPERATOR": 100035,
    "ABILITY_CAST_TYPE": 100042,
    "ABILITY_TYPE": 100014,
    "ABILITY_EVENT": 100008,
    "MODIFIER_EVENT": 100008,
    "MODIFIER_EFFECT_TYPE": 100042,
    "ATTR_ELEMENT": 100042,
    "ATTR_ELEMENT_READ": 100042,
    "FLOAT_ARITHMETIC_OPERATOR": 100017,
    "ROLE_RES_KEY": 100003,
    "TABLE_VAR": 100011,
    "SECTOR_SHAPE": 100009,
    "RECTANGLE_SHAPE": 100009,
    "ANNULAR_SHAPE": 100009,
    "CIRCULAR_SHAPE": 100009,
    "VAR": 100000,
    "VAR_LIST": 100022,
}

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


def arg_type_id_for(type_name, value=None, idx_data=None):
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
    # Graceful: allocate a base arg_type based on what we've seen
    # This prevents crashes for unknown types during bulk processing
    sys.stderr.write(f"[WARN] unknown arg_type '{type_name}' resolved to '{t}'. Using 100004 (POINT) fallback.\n")
    return 100004


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

VARIABLE_READ_SUBTYPE = {
    "FLOAT": 2,
    "BOOLEAN": 2,
    "INTEGER": 6,
    "STRING": 2,
    "ANGLE": 2,
    "TABLE": "VARIABLE",
    "PLAYER": "VARIABLE",
}


def _variable_tuple(var_type, name, scope, use_tuple=True):
    items = [var_type, name, scope]
    if use_tuple:
        return {"__tuple__": True, "items": items}
    return items


def build_variable_arg(value, expected_type, idx_data, write_target=False):
    """Build a global-trigger variable reference using editor-compatible tuples."""
    var_type = value.get("type", first_param_type(expected_type))
    if var_type in GENERIC_TYPES or var_type not in ARG_TYPE_ID:
        var_type = value.get("type", "UNIT_ENTITY")
    scope = value.get("scope", "local")
    use_tuple = value.get("tuple", True)
    ref = _variable_tuple(var_type, value["var"], scope, use_tuple)

    if write_target or value.get("write", False):
        return {
            "arg_type": 100030,
            "sub_type": 1,
            "args_list": [ref],
        }

    override_sub_type = value.get("sub_type", value.get("_sub_type"))
    sub_type = override_sub_type
    if sub_type is None:
        sub_type = VARIABLE_READ_SUBTYPE.get(var_type, 11)
    return {
        "arg_type": ARG_TYPE_ID.get(var_type, arg_type_id_for(expected_type, value, idx_data)),
        "sub_type": sub_type,
        "args_list": [ref],
    }


def build_arg(value, expected_type, idx_data, eid_gen, sub_trigger_refs=None):
    """Build a single arg node from DSL value."""
    # Custom trigger function (hex UUID) — handle before expected_type inference
    if isinstance(value, list) and len(value) >= 1 and isinstance(value[0], str):
        if _is_hex_uuid(value[0]) and value[0] not in idx_data:
            return _build_custom_func_arg(value, idx_data, eid_gen)

    arg_type = arg_type_id_for(expected_type, value, idx_data)

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
        func_def = idx_data[func_name]
        raw_args = list(value[1:])
        dsl_op = None
        # Extract trailing op_arg dict from DSL
        if raw_args and isinstance(raw_args[-1], dict) and "op_arg" in raw_args[-1] and len(raw_args[-1]) == 1:
            dsl_op = raw_args.pop()
        sub_args = []
        for i, sub_val in enumerate(raw_args):
            sub_type_name = func_def["p"][i] if i < len(func_def["p"]) else "STRING"
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
                if i < len(node["op_arg"]):
                    if isinstance(op_val, list) and op_val and isinstance(op_val[0], str) and op_val[0] in idx_data:
                        node["op_arg"][i] = build_arg(op_val, "VAR", idx_data, eid_gen, sub_trigger_refs)
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
        return {"event_type": "UNKNOWN", "element_id": eid_gen(), "enable": True, "args_list": []}
    name = spec[0]
    if name not in idx_data:
        raise ValueError(f"unknown event '{name}'")
    entry = idx_data[name]
    params = entry["p"]
    args = []
    for i, val in enumerate(spec[1:]):
        ft = params[i] if i < len(params) else "VAR"
        if name == "RECEIVE_CUSTOM_EVENT" and first_param_type(ft) == "CUS_EVENT":
            val = resolve_custom_event_value(val, custom_event_ids)
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
    args = []
    for i, val in enumerate(raw):
        fallback_type = params[i] if i < len(params) else "VAR"
        if name == "SET_VARIABLE" and i == 0 and isinstance(val, dict) and "var" in val:
            args.append(build_variable_arg(val, fallback_type, idx_data, write_target=True))
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
    }
    for name, vtype in variables.items():
        by_type.setdefault(vtype, {})[name] = defaults.get(vtype, 0)
        by_name[name] = 0
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
    for child_spec in spec.get("sub_triggers", []):
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


def build_trigger(spec, idx_data, default_id, parent_id=None, is_sub_trigger=False, custom_event_ids=None):
    if "name" not in spec:
        raise ValueError("trigger spec missing 'name'")
    tid = spec.get("id", default_id)
    spec["id"] = tid
    eid_gen = eid_factory(tid)
    sub_trigger_refs = prepare_sub_trigger_refs(spec, tid)
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
    sub_triggers = build_sub_trigger_tree(spec, idx_data, tid, custom_event_ids)
    if str(tid) in sub_triggers:
        raise ValueError(f"sub_trigger id conflicts with parent trigger id: {tid}")
    if sub_triggers:
        trigger["sub_trigger"] = sub_triggers
    return trigger


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
