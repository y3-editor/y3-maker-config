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

Run:
  py -3 gen_trigger.py <dsl.json>            # write to maps/<map>/global_trigger/trigger/
  py -3 gen_trigger.py <dsl.json> --dry-run  # print to stdout
"""
from __future__ import annotations
import argparse, json, os, sys

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
    "DAMAGE_TYPE": 100238,
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
    "CONDITION_LIST": 100023,
    "CUS_EVENT": 100008,
    "ABILITY_FLOAT_ATTRS": 100042,
    "ABILITY_INT_ATTRS": 100042,
    "EVENT_UNIT": 100006,
    "UNIT_TYPE": 100116,
    "BOOLEAN_OPERATOR": 100015,
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

def load_index():
    path = SLIM_PATH if os.path.isfile(SLIM_PATH) else INDEX_PATH
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def first_param_type(param_str):
    """ '[FLOAT,INTEGER]' / 'FLOAT,INTEGER' / 'VAR,VAR_LIST' / 'VAR,VAR,VAR_LIST' → first type """
    s = param_str.strip()
    if s.startswith("[") and s.endswith("]"):
        s = s[1:-1]
    for sep in (",", "/"):
        if sep in s:
            s = s.split(sep)[0].strip()
    return s


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
    t = first_param_type(type_name)
    if t in GENERIC_TYPES and value is not None and idx_data is not None:
        t = first_param_type(infer_type_from_value(value, idx_data))
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
    }
    if dsl_op and dsl_op.get("op_arg"):
        node["op_arg"] = []
        node["op_arg_enable"] = []
        for op_val in dsl_op["op_arg"]:
            node["op_arg"].append(build_arg(op_val, "VAR", idx_data, eid_gen))
            node["op_arg_enable"].append(True)
    return node


# Types that use arg_type=100030 (variable assignment target) for write operations
# instead of their direct type code
SIMPLE_VAR_TYPES = {"FLOAT", "INTEGER", "BOOLEAN", "STRING", "ANGLE"}


def build_arg(value, expected_type, idx_data, eid_gen):
    """Build a single arg node from DSL value."""
    # Custom trigger function (hex UUID) — handle before expected_type inference
    if isinstance(value, list) and len(value) >= 1 and isinstance(value[0], str):
        if _is_hex_uuid(value[0]) and value[0] not in idx_data:
            return _build_custom_func_arg(value, idx_data, eid_gen)

    arg_type = arg_type_id_for(expected_type, value, idx_data)

    # Variable reference: {"var": "unit", "type": "UNIT_ENTITY"}
    if isinstance(value, dict) and "var" in value:
        var_type = value.get("type", "UNIT_ENTITY")
        scope = value.get("scope", "local")
        override_sub_type = value.get("_sub_type")  # e.g. "VARIABLE"
        if override_sub_type:
            return {
                "arg_type": arg_type,
                "sub_type": override_sub_type,
                "args_list": [[var_type, value["var"], scope]],
            }
        # Simple types use arg_type=100030 with sub_type=1 for write-target context
        if var_type in SIMPLE_VAR_TYPES:
            return {
                "arg_type": 100030,
                "sub_type": 1,
                "args_list": [[var_type, value["var"], scope]],
            }
        return {
            "arg_type": arg_type,
            "sub_type": 11,
            "args_list": [[var_type, value["var"], scope]],
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
            sub_args.append(build_arg(sub_val, sub_type_name, idx_data, eid_gen))
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
                        node["op_arg"][i] = build_arg(op_val, "VAR", idx_data, eid_gen)
                        node["op_arg_enable"][i] = True
        return node

    # ACTION_LIST: nested action nodes
    if expected_type == "ACTION_LIST":
        if not isinstance(value, list):
            raise ValueError(f"ACTION_LIST expects list, got {type(value)}")
        nested = [build_action(a, idx_data, eid_gen) for a in value]
        return {
            "arg_type": arg_type,
            "sub_type": 1,
            "args_list": nested,
        }

    # Literal
    return {
        "arg_type": arg_type,
        "sub_type": 1,
        "args_list": [value],
    }


# ---------------------------------------------------------------------------
# Element builders
# ---------------------------------------------------------------------------

def eid_factory(trigger_id, start=2):
    counter = [start]
    def gen():
        v = trigger_id * 1000000 + counter[0]
        counter[0] += 1
        return v
    return gen


def build_event(spec, idx_data, eid_gen):
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


def build_condition(spec, idx_data, eid_gen):
    name = spec[0]
    if name not in idx_data:
        raise ValueError(f"unknown condition '{name}'")
    entry = idx_data[name]
    params = entry["p"]
    args = []
    for i, val in enumerate(spec[1:]):
        ft = params[i] if i < len(params) else "VAR"
        args.append(build_arg(val, ft, idx_data, eid_gen))
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


def build_action(spec, idx_data, eid_gen):
    if not isinstance(spec, list) or not spec:
        return {"action_type": "UNKNOWN", "element_id": eid_gen(), "enable": True, "bp": False, "args_list": []}
    name = spec[0]
    # Numeric action_type from custom actions (not in eca_index)
    if isinstance(name, int):
        node = {"action_type": name, "element_id": eid_gen(), "enable": True, "bp": False, "args_list": []}
        raw = list(spec[1:])
        for val in raw:
            node["args_list"].append(build_arg(val, "VAR", idx_data, eid_gen))
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
        args.append(build_arg(val, fallback_type, idx_data, eid_gen))
    node = {
        "action_type": name,
        "element_id": eid_gen(),
        "enable": True,
        "bp": extra.get("bp", False),
        "args_list": args,
    }
    if "call_rt_arg_idxes" in extra:
        node["call_rt_arg_idxes"] = extra["call_rt_arg_idxes"]
    op_params = entry.get("o", [])
    if op_params:
        node["op_arg"] = [None] * len(op_params)
        node["op_arg_enable"] = [False] * len(op_params)
    return node


# ---------------------------------------------------------------------------
# Trigger builder
# ---------------------------------------------------------------------------

def collect_variables(specs):
    """Walk all event/condition/action specs and collect LOCAL variable declarations.
    Global-scoped variables are skipped (declared in globaltriggervariable.json)."""
    vars_found = {}  # name -> type

    def walk(items):
        for item in items:
            if not isinstance(item, list) or not item:
                continue
            name = item[0]
            if name == "SET_VARIABLE" and len(item) >= 2:
                arg = item[1]
                if isinstance(arg, dict) and "var" in arg:
                    if arg.get("scope", "local") != "global":
                        vars_found[arg["var"]] = arg.get("type", "UNIT_ENTITY")
            for val in item[1:]:
                if isinstance(val, list) and val and isinstance(val[0], str):
                    walk(val)

    walk(specs.get("event", []))
    walk(specs.get("condition", []))
    walk(specs.get("action", []))

    return vars_found


def build_var_data(variables):
    """Build var_data from collected variables.
    var_data[0]: type -> {name -> 0}
    var_data[1]: name -> 0
    var_data[2]: ordered name list
    """
    by_type = {"NEW_TIMER": {}}
    by_name = {}
    names = []
    for name, vtype in variables.items():
        by_type.setdefault(vtype, {})[name] = 0
        by_name[name] = 0
        names.append(name)
    return [by_type, by_name, names]


def build_trigger(spec, idx_data, default_id):
    if "name" not in spec:
        raise ValueError("trigger spec missing 'name'")
    tid = spec.get("id", default_id)
    eid_gen = eid_factory(tid)
    variables = collect_variables(spec)
    return {
        "trigger_name": spec["name"],
        "trigger_id": tid,
        "p_trigger_id": None,
        "group_id": spec.get("group_id", 0),
        "enabled": spec.get("enabled", True),
        "valid": spec.get("valid", True),
        "call_enabled": spec.get("call_enabled", True),
        "event": [build_event(e, idx_data, eid_gen) for e in spec.get("event", [])],
        "condition": [build_condition(c, idx_data, eid_gen) for c in spec.get("condition", [])],
        "action": [build_action(a, idx_data, eid_gen) for a in spec.get("action", [])],
        "var_data": build_var_data(variables),
    }


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

def find_project_root():
    """Walk up from cwd looking for a 'maps' directory."""
    cur = os.getcwd()
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, "maps")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur: break
        cur = parent
    return os.getcwd()


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
    root = args.root or find_project_root()

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
        trig = build_trigger(t_spec, idx_data, t_spec["id"])
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
