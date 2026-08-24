# -*- coding: utf-8 -*-
"""Read ECA trigger JSON → compact DSL.

Usage:
  py -3 read_trigger.py <name>               fuzzy match in default map
  py -3 read_trigger.py <name> --map <map>
  py -3 read_trigger.py --all --map <map>    list all triggers (name + event summary)
  py -3 read_trigger.py <name> --out dsl.json
  py -3 read_trigger.py <name> --raw         output raw JSON
  py -3 read_trigger.py --unit <key> [name]  unit trigger mode
  py -3 read_trigger.py --path <json_file>   read specific file directly
"""
from __future__ import annotations
import argparse, json, os, sys, glob as glob_mod

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)
from gen_trigger import load_index, find_project_root

def _is_hex_uuid(s):
    """Check if string looks like a 32-char hex UUID (custom trigger function)."""
    return isinstance(s, str) and len(s) == 32 and all(c in '0123456789abcdef' for c in s)

# Known variable type names — used to distinguish plain-list var refs from func call lists
_KNOWN_VAR_TYPES = {
    "FLOAT", "INTEGER", "BOOLEAN", "STRING", "ANGLE", "POINT",
    "UNIT_ENTITY", "MODIFIER_ENTITY", "MODIFIER", "ABILITY",
    "PROJECTILE_ENTITY", "PROJECTILE", "ITEM_ENTITY", "ITEM_NAME",
    "SFX_ENTITY", "LINK_SFX_ENTITY", "NEW_TIMER", "TABLE",
    "DAMAGE_TYPE", "PLAYER", "PLAYER_GROUP", "UNIT_GROUP",
    "CURVED_PATH", "POLYGON", "RECTANGLE", "ROUND_AREA",
    "UNIT_NAME", "ABILITY_NAME", "UNIT_WRITE_ATTRIBUTE",
    "DYNAMIC_TRIGGER_INSTANCE", "UI_PREFAB_INSTANCE", "STATE",
    "VARIABLE",
}

# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------

def read_index_txt(map_name, root):
    idx_path = os.path.join(root, "maps", map_name, "global_trigger", "index.txt")
    if os.path.isfile(idx_path):
        with open(idx_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def list_trigger_files(map_name, root):
    trigger_dir = os.path.join(root, "maps", map_name, "global_trigger", "trigger")
    if not os.path.isdir(trigger_dir):
        return []
    return glob_mod.glob(os.path.join(trigger_dir, "*.json"))


def fuzzy_find(name, map_name, root):
    idx = read_index_txt(map_name, root)
    trigger_dir = os.path.join(root, "maps", map_name, "global_trigger", "trigger")
    # Exact filename match first
    exact = os.path.join(trigger_dir, name + ".json")
    if os.path.isfile(exact):
        return exact
    # index.txt lookup
    if name in idx:
        return os.path.join(trigger_dir, name)
    # Fuzzy: name in trigger_name content
    for fpath in list_trigger_files(map_name, root):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if name.lower() in data.get("trigger_name", "").lower():
                return fpath
        except Exception:
            pass
    # Fuzzy: name in filename
    for fpath in list_trigger_files(map_name, root):
        fname = os.path.basename(fpath)
        if name.lower() in fname.lower():
            return fpath
    return None


def load_trigger_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Reverse: JSON arg node → DSL value
# ---------------------------------------------------------------------------

def reverse_arg(arg_node, idx_data):
    """Convert a JSON arg node back to DSL value."""
    if not isinstance(arg_node, dict):
        return arg_node

    arg_type = arg_node.get("arg_type")
    sub_type = arg_node.get("sub_type")
    args_list = arg_node.get("args_list", [])
    op_arg = arg_node.get("op_arg")
    op_arg_enable = arg_node.get("op_arg_enable")

    # ACTION_LIST → nested action array
    if arg_type == 100022:
        if isinstance(args_list, list):
            return [reverse_action(a, idx_data) for a in args_list]
        return []

    # Variable tuple in args_list — two forms:
    #   A) {"__tuple__": true, "items": [type, name, scope]}
    #   B) [type, name, scope]  (plain list, no __tuple__ wrapper)
    if isinstance(args_list, list) and len(args_list) > 0:
        first = args_list[0]
        if isinstance(first, dict) and first.get("__tuple__"):
            items = first.get("items", [])
            if len(items) >= 3:
                return {"var": items[1], "type": items[0], "scope": items[2]}
            if len(items) >= 2:
                return {"var": items[1], "type": items[0]}
            return {"var": "", "type": ""}
        if isinstance(first, list) and len(first) >= 2 and isinstance(first[0], str):
            # Plain-list variable reference: ["TYPE", "name", "scope"]
            if first[0] in _KNOWN_VAR_TYPES or len(first[0]) < 20:
                scope = first[2] if len(first) >= 3 else "local"
                return {"var": first[1], "type": first[0], "scope": scope}

    # Also handle sub_type=1 where args_list[0] is plain list (simple var write target)
    if sub_type == 1 and isinstance(args_list, list) and len(args_list) > 0:
        if isinstance(args_list[0], list) and len(args_list[0]) >= 2:
            flat = args_list[0]
            return {"var": flat[1], "type": flat[0], "scope": flat[2] if len(flat) >= 3 else "local"}

    # Non-standard string sub_type that is not a function name (like "VARIABLE")
    # Pack it as a var reference with _sub_type metadata for round-trip
    if isinstance(sub_type, str) and not (sub_type in idx_data or _is_hex_uuid(sub_type)):
        if isinstance(args_list, list) and len(args_list) > 0:
            first = args_list[0]
            if isinstance(first, list) and len(first) >= 2 and isinstance(first[0], str):
                return {
                    "var": first[1], "type": first[0],
                    "scope": first[2] if len(first) >= 3 else "local",
                    "_sub_type": sub_type,
                }

    # Functional sub_type (string → nested function call) — includes hex UUIDs
    if isinstance(sub_type, str):
        result = [sub_type]
        for a in args_list:
            result.append(reverse_arg(a, idx_data))
        if op_arg and op_arg_enable:
            active_op = []
            for i, enabled in enumerate(op_arg_enable):
                if enabled and i < len(op_arg) and op_arg[i] is not None:
                    active_op.append(reverse_arg(op_arg[i], idx_data))
            if active_op:
                result.append({"op_arg": active_op})
        return result

    # Literal: sub_type=1 or other int
    if isinstance(args_list, list) and len(args_list) > 0:
        return args_list[0]
    return None


def _reverse_trigger_element(node, idx_data, name_key, items_key="args_list"):
    """Generic reverse for event/condition/action elements."""
    name = node.get(name_key, "")
    args = [reverse_arg(a, idx_data) for a in node.get(items_key, [])]
    return [name] + args


def reverse_event(node, idx_data):
    if not isinstance(node, dict):
        return node
    return _reverse_trigger_element(node, idx_data, "event_type")


def reverse_condition(node, idx_data):
    if not isinstance(node, dict):
        return node
    return _reverse_trigger_element(node, idx_data, "condition_type")


def reverse_action(node, idx_data):
    """Convert action JSON node to DSL list, preserving bp / call_rt_arg_idxes."""
    if not isinstance(node, dict):
        return node
    result = _reverse_trigger_element(node, idx_data, "action_type")
    extra = {}
    if node.get("bp", False):
        extra["bp"] = True
    call_idxes = node.get("call_rt_arg_idxes")
    if call_idxes:
        extra["call_rt_arg_idxes"] = call_idxes
    if extra:
        result.append(extra)
    return result


def reverse_var_data(var_data):
    """Reverse var_data field to DSL-friendly form.
    var_data[0]: {TYPE: {name: default, ...}}
    var_data[1]: {name: length}
    var_data[2]: [name, ...]
    """
    if not var_data or not isinstance(var_data, list) or len(var_data) < 3:
        return None
    return {
        "types": var_data[0] if isinstance(var_data[0], dict) else {},
        "lengths": var_data[1] if isinstance(var_data[1], dict) else {},
        "order": var_data[2] if isinstance(var_data[2], list) else [],
    }


def reverse_trigger(trigger_json, idx_data):
    """Convert a full trigger JSON to DSL spec dict, preserving all fields
    needed for round-trip fidelity."""
    spec = {
        "name": trigger_json.get("trigger_name", ""),
        "id": trigger_json.get("trigger_id"),
        "group_id": trigger_json.get("group_id", 0),
        "enabled": trigger_json.get("enabled", True),
        "event": [reverse_event(e, idx_data) for e in trigger_json.get("event", []) if isinstance(e, dict)],
        "condition": [reverse_condition(c, idx_data) for c in trigger_json.get("condition", []) if isinstance(c, dict)],
        "action": [reverse_action(a, idx_data) for a in trigger_json.get("action", []) if isinstance(a, dict)],
    }
    # Fields needed for round-trip fidelity
    for key in ("call_enabled", "valid"):
        spec[key] = trigger_json.get(key, True)
    pid = trigger_json.get("p_trigger_id")
    if pid is not None:
        spec["p_trigger_id"] = pid
    vd = reverse_var_data(trigger_json.get("var_data"))
    if vd:
        spec["var_data"] = vd
    for key in ("is_conf",):
        if key in trigger_json:
            spec[key] = trigger_json[key]
    sosa = trigger_json.get("sub_trigger_owner_set_var_action")
    if sosa is not None:
        spec["sub_trigger_owner_set_var_action"] = sosa
    return spec


def reverse_trigger_from_unit(unit_data, idx_data):
    """Convert obj-edit JSON trigger_dict to DSL specs.
    Works for unit / ability / modifier / item / projectile."""
    trigger_dict = unit_data.get("trigger_dict", {})
    specs = []
    for tid_str, trigger_json in trigger_dict.items():
        spec = reverse_trigger(trigger_json, idx_data)
        specs.append(spec)
    return specs


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def fmt_summary(spec):
    """Single-line summary: name + first event."""
    name = spec.get("name", "?")
    events = spec.get("event", [])
    if events:
        ev = events[0]
        ev_name = ev[0] if isinstance(ev, list) and ev else str(ev)
        return f"{name}  ← {ev_name}"
    return f"{name}  ← (empty event)"


def to_dsl(specs, map_name, unit_key=None):
    """Wrap trigger specs in DSL envelope."""
    dsl = {"map": map_name, "triggers": specs}
    if unit_key:
        dsl["unit"] = unit_key
    return dsl


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description="Read ECA trigger JSON → DSL")
    p.add_argument("name", nargs="?", help="trigger name or filename (fuzzy)")
    p.add_argument("--map", default="EntryMap", help="map name (default: EntryMap)")
    p.add_argument("--all", action="store_true", help="list all triggers summaries")
    p.add_argument("--raw", action="store_true", help="output raw JSON instead of DSL")
    p.add_argument("--out", help="save DSL to file")
    p.add_argument("--unit", help="unit key for unit trigger mode (legacy, = --container unit --key)")
    p.add_argument("--container", default="unit", help="obj-edit container type: unit/ability/modifier/item/projectile")
    p.add_argument("--key", help="obj-edit key (unit_id / ability_id / ...)")
    p.add_argument("--path", help="read specific JSON file directly")
    p.add_argument("--root", default=None, help="project root (auto-detected)")
    args = p.parse_args(argv)

    root = args.root or find_project_root()
    idx_data = load_index()
    map_name = args.map

    # --path mode: direct file
    if args.path:
        if not os.path.isfile(args.path):
            print(f"file not found: {args.path}")
            return 1
        data = load_trigger_json(args.path)
        if "trigger_dict" in data:
            specs = reverse_trigger_from_unit(data, idx_data)
            dsl = to_dsl(specs, map_name, "auto-detected")
        else:
            spec = reverse_trigger(data, idx_data)
            dsl = to_dsl([spec], map_name)
        if args.raw:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        elif args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(dsl, f, ensure_ascii=False, indent=2)
            path_str = os.path.abspath(args.out)
            print(f"DSL → {path_str} ({len(dsl['triggers'])} trigger(s))")
        else:
            print(json.dumps(dsl, ensure_ascii=False, indent=2))
        return 0

    # --unit mode (now unified: --container + --key)
    obj_key = args.key or args.unit
    container = args.container if obj_key else "unit"
    if args.unit and not args.key:
        container = "unit"  # legacy --unit mode
    if obj_key:
        obj_path = os.path.join(root, "maps", map_name, container, obj_key + ".json")
        if not os.path.isfile(obj_path):
            print(f"{container} file not found: {obj_path}")
            return 1
        obj_data = load_trigger_json(obj_path)
        specs = reverse_trigger_from_unit(obj_data, idx_data)
        if args.name:
            specs = [s for s in specs if args.name.lower() in s.get("name", "").lower()]
        if args.all or not args.name:
            obj_name = obj_data.get("name", obj_key) if container != "unit" else obj_data.get("unit_name", obj_key)
            print(f"# {container}: {obj_name} ({obj_key}) — {len(specs)} trigger(s)")
            for i, s in enumerate(specs):
                print(f"  [{i}] {fmt_summary(s)}")
        else:
            dsl = to_dsl(specs, map_name, obj_key)
            if args.out:
                with open(args.out, "w", encoding="utf-8") as f:
                    json.dump(dsl, f, ensure_ascii=False, indent=2)
                print(f"DSL → {os.path.abspath(args.out)} ({len(specs)} trigger(s))")
            else:
                print(json.dumps(dsl, ensure_ascii=False, indent=2))
        return 0

    # --all mode: list all global triggers
    if args.all:
        specs = []
        for fpath in list_trigger_files(map_name, root):
            try:
                data = load_trigger_json(fpath)
                spec = reverse_trigger(data, idx_data)
                specs.append(spec)
            except Exception as e:
                print(f"warn: skip {fpath}: {e}", file=sys.stderr)
        print(f"# Map: {map_name} — {len(specs)} trigger(s)")
        for i, s in enumerate(specs):
            print(f"  [{i}] {fmt_summary(s)}")
        return 0

    # --name mode
    if not args.name:
        p.print_help()
        return 1

    path = fuzzy_find(args.name, map_name, root)
    if not path:
        print(f"trigger not found: {args.name} (map={map_name})")
        return 1

    data = load_trigger_json(path)
    if args.raw:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    spec = reverse_trigger(data, idx_data)
    dsl = to_dsl([spec], map_name)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(dsl, f, ensure_ascii=False, indent=2)
        print(f"DSL → {os.path.abspath(args.out)}")
    else:
        print(json.dumps(dsl, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
