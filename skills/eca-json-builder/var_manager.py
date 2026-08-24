# -*- coding: utf-8 -*-
"""
ECA variable manager — CRUD for global variables and unit group variables.

Subcommands:
  list   [--global] [--unit KEY]            List variables
  add    NAME TYPE [--global] [--unit KEY]  Add a variable
  remove NAME [--global] [--unit KEY]       Remove a variable
  show   NAME [--global] [--unit KEY]       Show variable detail

Types: UNIT_ENTITY, INTEGER, FLOAT, STRING, BOOLEAN, SFX_ENTITY,
       UNIT_NAME, ANGLE, POINT, UNIT_GROUP, PLAYER_GROUP, etc.

Examples:
  py -3 var_manager.py list --global
  py -3 var_manager.py add my_unit UNIT_ENTITY --global
  py -3 var_manager.py remove my_unit --global
  py -3 var_manager.py list --unit 100001
  py -3 var_manager.py add boss UNIT_ENTITY --unit 100001
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "..", ".."))
MAPS_DIR = os.path.join(PROJECT_ROOT, "maps")

# Default values per variable type (editor crashes on wrong type, e.g. setText(0))
_VAR_DEFAULTS = {
    "STRING": "",
    "BOOLEAN": False,
    "FLOAT": 0.0,
    "ANGLE": 0.0,
    "INTEGER": 0,
    "UNIT_ENTITY": 0,
    "UNIT_NAME": "",
    "UNIT_GROUP": 0,
    "PLAYER": 0,
    "PLAYER_GROUP": 0,
    "SFX_ENTITY": 0,
    "LINK_SFX_ENTITY": 0,
    "ABILITY": 0,
    "ABILITY_NAME": "",
    "MODIFIER": 0,
    "MODIFIER_ENTITY": 0,
    "ITEM_ENTITY": 0,
    "ITEM_NAME": "",
    "PROJECTILE": 0,
    "PROJECTILE_ENTITY": 0,
    "POINT": [0, 0],
    "RECTANGLE": 0,
    "ROUND_AREA": 0,
    "POLYGON": 0,
    "CURVED_PATH": 0,
    "TABLE": 0,
    "NEW_TIMER": 0,
    "DAMAGE_TYPE": 0,
    "UNIT_WRITE_ATTRIBUTE": 0,
    "DYNAMIC_TRIGGER_INSTANCE": 0,
    "UI_PREFAB_INSTANCE": 0,
    "STATE": 0,
}
# NEW_TIMER is auto-managed by engine, excluded from user-facing lists


def _default_for(vtype):
    return _VAR_DEFAULTS.get(vtype, 0)


def _find_config_dir():
    """Find codemaker config dir (.codemaker or .y3maker)."""
    for name in (".codemaker", ".y3maker"):
        d = os.path.join(PROJECT_ROOT, name)
        if os.path.isdir(d):
            return d
    return os.path.join(PROJECT_ROOT, ".codemaker")


def _get_maps():
    """List available map names."""
    if not os.path.isdir(MAPS_DIR):
        return []
    return [d for d in os.listdir(MAPS_DIR) if os.path.isdir(os.path.join(MAPS_DIR, d))]


def _find_map(map_name=None):
    """Resolve map name. Checks in _get_root()/maps/."""
    root = _get_root()
    maps_dir = os.path.join(root, "maps")
    maps = []
    if os.path.isdir(maps_dir):
        maps = [d for d in os.listdir(maps_dir) if os.path.isdir(os.path.join(maps_dir, d))]
    if map_name:
        if map_name in maps:
            return map_name
        print(f"Map '{map_name}' not found in {root}. Available: {maps}")
        sys.exit(1)
    if "EntryMap" in maps:
        return "EntryMap"
    if maps:
        return maps[0]
    print("No maps found.")
    sys.exit(1)


def _get_root(args=None):
    """Resolve project root: env Y3_PROJECT_ROOT > --root arg > auto-detect."""
    env = os.environ.get("Y3_PROJECT_ROOT")
    if env:
        return os.path.normpath(env)
    if args and getattr(args, "root", None):
        return os.path.normpath(args.root)
    # Auto-detect: parent of config dir
    here = SCRIPT_DIR
    for _ in range(6):
        parent = os.path.dirname(here)
        for tag in [".codemaker", ".y3maker"]:
            if os.path.isdir(os.path.join(parent, tag)):
                return parent
        if here == parent:
            break
        here = parent
    return PROJECT_ROOT


def _global_var_path(map_name, root=None):
    r = root or _get_root()
    return os.path.join(r, "maps", map_name, "project_trigger_var.json")


def _unit_var_path(map_name, unit_key, root=None):
    r = root or _get_root()
    return os.path.join(r, "maps", map_name, "unit", f"{unit_key}.json")


def _load_json(path):
    if not os.path.isfile(path):
        print(f"File not found: {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path, data):
    bak = path + ".bak"
    if os.path.isfile(path):
        with open(path, "r", encoding="utf-8") as f:
            original = f.read()
        with open(bak, "w", encoding="utf-8") as f:
            f.write(original)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
    print(f"Saved: {path}  (backup: {bak})")


# ---------------------------------------------------------------------------
# Global variable operations
# ---------------------------------------------------------------------------

def global_list(map_name, root=None):
    path = _global_var_path(map_name, root)
    if not os.path.isfile(path):
        print("(no project_trigger_var.json — project has no global variables)")
        return []
    data = _load_json(path)
    vdict = data.get("variable_dict", {})

    rows = []
    for vtype, names in sorted(vdict.items()):
        if vtype == "NEW_TIMER":
            continue
        for name in sorted(names.keys()):
            rows.append((name, vtype))
    if not rows:
        print("(no global variables)")
        return rows
    print(f"Global variables ({map_name}):")
    for name, vtype in rows:
        print(f"  {name:<20} {vtype}")
    return rows


def global_add(map_name, name, vtype, root=None):
    path = _global_var_path(map_name, root)
    if not os.path.isfile(path):
        data = {"variable_dict": {}, "variable_length_dict": {}, "variable_group_info": []}
    else:
        data = _load_json(path)

    vdict = data.setdefault("variable_dict", {})
    vgroup = data.setdefault("variable_group_info", [])
    vlen = data.setdefault("variable_length_dict", {})

    # Check duplicate
    for exist_type, exist_names in vdict.items():
        if name in exist_names:
            print(f"Variable '{name}' already exists (type={exist_type}).")
            sys.exit(1)

    # Add to variable_dict
    vdict.setdefault(vtype, {})[name] = _default_for(vtype)

    # Add to variable_group_info
    vgroup.append({"__tuple__": True, "items": [name, name]})

    # Add to variable_length_dict
    vlen[name] = 0

    _save_json(path, data)
    print(f"Added global variable: {name} ({vtype})")


def global_remove(map_name, name, root=None):
    path = _global_var_path(map_name, root)
    data = _load_json(path)

    vdict = data.get("variable_dict", {})
    vgroup = data.get("variable_group_info", [])
    vlen = data.get("variable_length_dict", {})

    # Find and remove from variable_dict
    found_type = None
    for vtype, names in vdict.items():
        if name in names:
            found_type = vtype
            del names[name]
            if not names:
                del vdict[vtype]
            break

    if found_type is None:
        print(f"Global variable '{name}' not found.")
        sys.exit(1)

    # Remove from variable_group_info
    data["variable_group_info"] = [
        g for g in vgroup
        if not (isinstance(g, dict) and g.get("__tuple__")
                and isinstance(g.get("items"), list)
                and len(g["items"]) > 0 and g["items"][0] == name)
    ]

    # Remove from variable_length_dict
    if name in vlen:
        del vlen[name]

    _save_json(path, data)
    print(f"Removed global variable: {name} (was {found_type})")


def global_show(map_name, name, root=None):
    path = _global_var_path(map_name, root)
    if not os.path.isfile(path):
        print("(no project_trigger_var.json)")
        return
    data = _load_json(path)

    vdict = data.get("variable_dict", {})
    for vtype, names in vdict.items():
        if name in names:
            print(f"Variable: {name}")
            print(f"  Type:   {vtype}")
            print(f"  Scope:  global")
            print(f"  Map:    {map_name}")
            # Check for usages across all triggers
            usages = _find_global_var_usages(map_name, name)
            if usages:
                print(f"  Used in triggers: {', '.join(usages)}")
            return
    print(f"Global variable '{name}' not found.")


def _find_global_var_usages(map_name, var_name):
    """Scan global triggers for references to a global variable."""
    import glob as _glob
    triggers_dir = os.path.join(MAPS_DIR, map_name, "global_trigger")
    if not os.path.isdir(triggers_dir):
        return []
    usages = []
    for fpath in _glob.glob(os.path.join(triggers_dir, "*.json")):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if _trigger_refs_var(data, var_name):
                trig_name = data.get("trigger_name", os.path.basename(fpath))
                usages.append(trig_name)
        except Exception:
            pass
    return usages


def _trigger_refs_var(trigger, var_name):
    """Recursively check if trigger JSON references var_name."""
    if isinstance(trigger, dict):
        if trigger.get("__tuple__") and isinstance(trigger.get("items"), list):
            items = trigger["items"]
            if len(items) >= 2 and items[1] == var_name:
                return True
        for v in trigger.values():
            if _trigger_refs_var(v, var_name):
                return True
    elif isinstance(trigger, list):
        for item in trigger:
            if _trigger_refs_var(item, var_name):
                return True
    return False


# ---------------------------------------------------------------------------
# Unit group variable operations
# ---------------------------------------------------------------------------

def _load_unit_data(map_name, unit_key):
    path = _unit_var_path(map_name, unit_key)
    return _load_json(path), path


def unit_list(map_name, unit_key):
    data, path = _load_unit_data(map_name, unit_key)

    # Top-level variable_dict (unit group variables)
    vdict = data.get("variable_dict", {})
    rows = []
    for vtype, names in sorted(vdict.items()):
        for name in sorted(names.keys()):
            rows.append((name, vtype, "unit_group"))

    # Local variables per trigger
    local_var = data.get("local_variable", {})
    for tid, tvar in local_var.items():
        tvdict = tvar.get("variable_dict", {})
        for vtype, names in tvdict.items():
            for name in sorted(names.keys()):
                rows.append((name, vtype, f"local(tid={tid})"))

    if not rows:
        print(f"(no variables in unit {unit_key})")
        return rows

    print(f"Variables in unit {unit_key} ({map_name}):")
    cur_scope = None
    for name, vtype, scope in rows:
        if scope != cur_scope:
            print(f"  [{scope}]")
            cur_scope = scope
        print(f"    {name:<20} {vtype}")
    return rows


def unit_add(map_name, unit_key, name, vtype):
    data, path = _load_unit_data(map_name, unit_key)

    vdict = data.setdefault("variable_dict", {})
    vgroup = data.setdefault("variable_group_info", [])
    vlen = data.setdefault("variable_length_dict", {})

    # Check duplicate in top-level variable_dict
    for exist_type, exist_names in vdict.items():
        if name in exist_names:
            print(f"Unit group variable '{name}' already exists (type={exist_type}).")
            sys.exit(1)

    vdict.setdefault(vtype, {})[name] = _default_for(vtype)
    vgroup.append({"__tuple__": True, "items": [name, name]})
    vlen[name] = 0

    _save_json(path, data)
    print(f"Added unit group variable: {name} ({vtype}) in unit {unit_key}")


def unit_remove(map_name, unit_key, name):
    data, path = _load_unit_data(map_name, unit_key)

    vdict = data.get("variable_dict", {})
    vgroup = data.get("variable_group_info", [])
    vlen = data.get("variable_length_dict", {})

    found_type = None
    for vtype, names in list(vdict.items()):
        if name in names:
            found_type = vtype
            del names[name]
            if not names:
                del vdict[vtype]
            break

    if found_type is None:
        print(f"Unit group variable '{name}' not found in unit {unit_key}.")
        sys.exit(1)

    data["variable_group_info"] = [
        g for g in vgroup
        if not (isinstance(g, dict) and g.get("__tuple__")
                and isinstance(g.get("items"), list)
                and len(g["items"]) > 0 and g["items"][0] == name)
    ]
    if name in vlen:
        del vlen[name]

    _save_json(path, data)
    print(f"Removed unit group variable: {name} (was {found_type}) from unit {unit_key}")


def unit_show(map_name, unit_key, name):
    data, _ = _load_unit_data(map_name, unit_key)

    # Check top-level
    vdict = data.get("variable_dict", {})
    for vtype, names in vdict.items():
        if name in names:
            print(f"Variable: {name}")
            print(f"  Type:   {vtype}")
            print(f"  Scope:  unit_group (unit {unit_key})")
            print(f"  Map:    {map_name}")
            return

    # Check per-trigger local
    local_var = data.get("local_variable", {})
    for tid, tvar in local_var.items():
        tvdict = tvar.get("variable_dict", {})
        for vtype, names in tvdict.items():
            if name in names:
                print(f"Variable: {name}")
                print(f"  Type:   {vtype}")
                print(f"  Scope:  local (trigger {tid})")
                print(f"  Map:    {map_name}")
                return

    print(f"Variable '{name}' not found in unit {unit_key}.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(
        description="ECA variable manager — CRUD global/unit variables"
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    # --- list ---
    p_list = sub.add_parser("list", help="list variables")
    p_list.add_argument("--map", help="map name (default: EntryMap)")
    p_list.add_argument("--global", dest="scope_global", action="store_true",
                        help="list global variables (default)")
    p_list.add_argument("--unit", help="unit key for unit group variables")

    # --- add ---
    p_add = sub.add_parser("add", help="add a variable")
    p_add.add_argument("name", help="variable name")
    p_add.add_argument("type", help="variable type (UNIT_ENTITY, INTEGER, ...)")
    p_add.add_argument("--map", help="map name (default: EntryMap)")
    p_add.add_argument("--global", dest="scope_global", action="store_true",
                       help="add to global variables (default)")
    p_add.add_argument("--unit", help="unit key for unit group variable")

    # --- remove ---
    p_rm = sub.add_parser("remove", help="remove a variable")
    p_rm.add_argument("name", help="variable name")
    p_rm.add_argument("--map", help="map name (default: EntryMap)")
    p_rm.add_argument("--global", dest="scope_global", action="store_true",
                      help="remove from global variables (default)")
    p_rm.add_argument("--unit", help="unit key for unit group variable")

    # --- show ---
    p_show = sub.add_parser("show", help="show variable detail")
    p_show.add_argument("name", help="variable name")
    p_show.add_argument("--map", help="map name (default: EntryMap)")
    p_show.add_argument("--global", dest="scope_global", action="store_true",
                        help="show global variable (default)")
    p_show.add_argument("--unit", help="unit key for unit group variable")

    args = p.parse_args(argv)
    map_name = _find_map(args.map)
    # Resolve root from env / --root arg
    root = _get_root(args)

    if args.cmd == "list":
        if args.unit:
            unit_list(map_name, args.unit)
        else:
            global_list(map_name, root)

    elif args.cmd == "add":
        if args.unit:
            unit_add(map_name, args.unit, args.name, args.type)
        else:
            global_add(map_name, args.name, args.type, root)

    elif args.cmd == "remove":
        if args.unit:
            unit_remove(map_name, args.unit, args.name)
        else:
            global_remove(map_name, args.name, root)

    elif args.cmd == "show":
        if args.unit:
            unit_show(map_name, args.unit, args.name)
        else:
            global_show(map_name, args.name, root)

    return 0


if __name__ == "__main__":
    sys.exit(main())
