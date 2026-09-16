# -*- coding: utf-8 -*-
"""Generate Y3 global function JSON from a compact DSL.

DSL format:
{
  "map": "EntryMap",
  "functions": [
    {
      "name": "大厅服务 - 创建队伍",
      "id": 1263239224,
      "func_id": "a1377fd18bfb11f1b9d919bc08ffd172",
      "description": "设置玩家{player}的数据",
      "comment": "",
      "params": [{"name": "player", "type": "PLAYER", "required": true}],
      "returns": [{"name": "result", "type": "TABLE", "var": "t"}],
      "lua_bind": true
    }
  ]
}
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


ARG_TYPE_ID = {
    "FLOAT": 100000,
    "BOOLEAN": 100001,
    "INTEGER": 100002,
    "STRING": 100003,
    "POINT": 100004,
    "UNIT_ENTITY": 100006,
    "PROJECTILE_ENTITY": 100010,
    "TABLE": 100011,
    "ABILITY": 100014,
    "ITEM_ENTITY": 100021,
    "ACTION_LIST": 100022,
    "PLAYER": 100025,
    "UNIT_GROUP": 100026,
    "PROJECTILE": 100031,
    "POLYGON": 100035,
    "ABILITY_NAME": 100046,
    "MODIFIER_KEY": 100046,
    "SFX_KEY": 100066,
    "MODIFIER_ENTITY": 100076,
    "STATE": 100075,
    "UNIT_NAME": 100116,
    "ITEM_NAME": 100116,
    "SFX_ENTITY": 100148,
    "LINK_SFX_ENTITY": 100148,
    "DYNAMIC_TRIGGER_INSTANCE": 100178,
    "NEW_TIMER": 100181,
    "ANGLE": 100225,
    "UI_PREFAB_INSTANCE": 100301,
}

DEFAULTS_BY_TYPE = {
    "STRING": "",
    "BOOLEAN": False,
    "FLOAT": 0.0,
    "ANGLE": 0.0,
    "NEW_TIMER": -1,
    "TABLE": None,
}

VARIABLE_READ_SUBTYPE = {
    "FLOAT": 2,
    "BOOLEAN": "VARIABLE",
    "INTEGER": 6,
    "STRING": 2,
    "ANGLE": 2,
    "TABLE": "VARIABLE",
    "PLAYER": "VARIABLE",
}


def tuple_node(*items):
    return {"__tuple__": True, "items": list(items)}


def normalize_type(type_name):
    if not type_name:
        return "TABLE"
    return str(type_name).strip().upper()


def arg_type_id(type_name):
    normalized = normalize_type(type_name)
    if normalized not in ARG_TYPE_ID:
        raise ValueError(f"unsupported ECA type '{normalized}'")
    return ARG_TYPE_ID[normalized]


def stable_func_id(map_name, spec):
    # Function identity is shared across maps, matching editor-generated UI functions.
    seed = f"global_trigger/function/{spec['name']}"
    return uuid.uuid5(uuid.NAMESPACE_URL, seed).hex


def stable_trigger_id(map_name, spec):
    explicit = spec.get("id")
    if explicit is not None:
        return int(explicit)
    seed = f"global_trigger/function/{spec['name']}"
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % 2_000_000_000 + 1


def element_id_factory(trigger_id, start=2):
    counter = [start]

    def gen():
        value = trigger_id * 1000000 + counter[0]
        counter[0] += 1
        return value

    return gen


def variable_arg(name, type_name, *, sub_type=None):
    vtype = normalize_type(type_name)
    if sub_type is None:
        sub_type = VARIABLE_READ_SUBTYPE.get(vtype, 11)
    return {
        "arg_type": arg_type_id(vtype),
        "args_list": [tuple_node(vtype, name, "local")],
        "sub_type": sub_type,
    }


def assignment_target_arg(name, type_name):
    return {
        "arg_type": 100030,
        "args_list": [tuple_node(normalize_type(type_name), name, "local")],
        "sub_type": 1,
    }


def lua_code_arg(code):
    return {
        "arg_type": 100003,
        "args_list": [code],
        "sub_type": 1,
    }


def eval_lua_arg(name, return_type, params):
    args_expr = ", ".join(f"args[{i}]" for i in range(1, len(params) + 1))
    code = f"Bind['{name}']({args_expr})"
    op_arg = [None, None, None, None, None]
    op_arg_enable = [False, False, False, False, False]
    for i, param in enumerate(params[:5]):
        op_arg[i] = variable_arg(param["name"], param["type"])
        op_arg_enable[i] = True
    return {
        "arg_type": arg_type_id(return_type),
        "args_list": [lua_code_arg(code)],
        "op_arg": op_arg,
        "op_arg_enable": op_arg_enable,
        "sub_type": f"Eval_Lua_{normalize_type(return_type)}",
    }


def normalize_params(spec):
    params = []
    for raw in spec.get("params", []):
        if "name" not in raw:
            raise ValueError(f"function '{spec['name']}' has a param without name")
        params.append(
            {
                "name": raw["name"],
                "type": normalize_type(raw.get("type", "STRING")),
                "required": bool(raw.get("required", True)),
            }
        )
    return params


def normalize_description(spec, params):
    description = spec.get("description", spec.get("func_des", ""))
    missing = [param["name"] for param in params if f"{{{param['name']}}}" not in description]
    if missing:
        placeholders = ", ".join(f"{{{name}}}" for name in missing)
        raise ValueError(
            f"function '{spec['name']}' description is missing parameter placeholder(s): {placeholders}"
        )
    return description


def normalize_returns(spec):
    returns = []
    for raw in spec.get("returns", []):
        if "name" not in raw:
            raise ValueError(f"function '{spec['name']}' has a return without name")
        rtype = normalize_type(raw.get("type", "TABLE"))
        returns.append({"name": raw["name"], "type": rtype, "var": raw.get("var", raw["name"])})
    return returns


def build_var_data(params, returns):
    by_type = {"NEW_TIMER": {}}
    by_name = {}
    names = []

    def add_var(name, type_name):
        vtype = normalize_type(type_name)
        if name in by_name:
            return
        by_type.setdefault(vtype, {})[name] = DEFAULTS_BY_TYPE.get(vtype, 0)
        by_name[name] = 0
        names.append(name)

    for param in params:
        add_var(param["name"], param["type"])
    for ret in returns:
        add_var(ret["var"], ret["type"])
    return [by_type, by_name, names]


def build_lua_bind_actions(spec, params, returns, eid_gen):
    if not spec.get("lua_bind", False):
        return []
    if not returns:
        raise ValueError(f"function '{spec['name']}' has lua_bind but no returns")
    if len(params) > 5:
        raise ValueError(f"function '{spec['name']}' has {len(params)} params; Eval_Lua supports at most 5 op_arg slots")
    if len(returns) != 1:
        raise ValueError(f"function '{spec['name']}' lua_bind currently supports exactly one return")

    ret = returns[0]
    return [
        {
            "action_type": "SET_VARIABLE",
            "args_list": [
                assignment_target_arg(ret["var"], ret["type"]),
                eval_lua_arg(spec["name"], ret["type"], params),
            ],
            "bp": False,
            "element_id": eid_gen(),
            "enable": True,
        },
        {
            "action_type": 400342,
            "args_list": [variable_arg(ret["var"], ret["type"])],
            "bp": False,
            "element_id": eid_gen(),
            "enable": True,
        },
    ]


def build_function(spec, map_name):
    if "name" not in spec:
        raise ValueError("function spec missing 'name'")

    params = normalize_params(spec)
    returns = normalize_returns(spec)
    description = normalize_description(spec, params)
    trigger_id = stable_trigger_id(map_name, spec)
    eid_gen = element_id_factory(trigger_id)

    func_id = spec.get("func_id") or stable_func_id(map_name, spec)
    if not isinstance(func_id, str) or len(func_id) != 32 or any(c not in "0123456789abcdef" for c in func_id):
        raise ValueError(f"function '{spec['name']}' func_id must be 32 lowercase hex characters")

    function = {
        "action": build_lua_bind_actions(spec, params, returns, eid_gen),
        "call_enabled": bool(spec.get("call_enabled", True)),
        "condition": [],
        "enabled": bool(spec.get("enabled", True)),
        "event": [],
        "func_category": spec.get("func_category", "t_function"),
        "func_comment": spec.get("comment", spec.get("func_comment", "")),
        "func_des": description,
        "func_id": func_id,
        "func_name": spec["name"],
        "group_id": int(spec.get("group_id", 0)),
        "is_func": True,
        "is_official_func": bool(spec.get("is_official_func", False)),
        "p_trigger_id": spec.get("p_trigger_id"),
        "trigger_id": trigger_id,
        "trigger_name": spec["name"],
        "valid": bool(spec.get("valid", True)),
        "var_data": build_var_data(params, returns),
    }
    if params:
        function["func_param_list"] = [tuple_node(param["name"], param["required"]) for param in params]
    if returns:
        function["func_return"] = True
        function["func_rtv_name_list"] = [tuple_node(ret["name"], ret["type"]) for ret in returns]
    return function


def find_project_root():
    cur = os.getcwd()
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, "maps")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.getcwd()


def write_function(function, map_name, project_root):
    out_dir = os.path.join(project_root, "maps", map_name, "global_trigger", "function")
    os.makedirs(out_dir, exist_ok=True)
    fname = function["func_name"] + ".json"
    path = os.path.join(out_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(function, f, ensure_ascii=False, indent=4)
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


def load_dsl(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("dsl", help="path to DSL JSON file")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--root", default=None, help="project root; defaults to nearest parent with maps/")
    parser.add_argument("--map", dest="map_override", default=None, help="override DSL map name")
    args = parser.parse_args(argv)

    dsl = load_dsl(args.dsl)
    map_name = args.map_override or dsl.get("map", "EntryMap")
    specs = dsl.get("functions", [])
    if not specs:
        print("DSL contains no functions")
        return 1

    root = args.root or find_project_root()
    results = []
    for spec in specs:
        function = build_function(spec, map_name)
        if args.dry_run:
            print(json.dumps(function, ensure_ascii=False, indent=2))
            results.append((function["func_name"], None, None))
        else:
            path, fname, out_dir = write_function(function, map_name, root)
            idx = update_index(out_dir, fname)
            results.append((function["func_name"], path, idx))

    if not args.dry_run:
        for name, path, idx in results:
            print(f"OK [{idx}]  {name}  -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
