# -*- coding: utf-8 -*-
"""Standalone ECA lookup — reads bundled eca_index.json. No engine dependency.

Usage:
  py -3 lookup.py <name>            full JSON (title/desc/lua/api)
  py -3 lookup.py <name> --brief    one-line: type | sub_type | param | op_param
  py -3 lookup.py <name1> <name2> ... --brief   batch mode
  py -3 lookup.py --global-events   list events for global triggers
"""
import json, os, sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

INDEX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eca_index.json")

def _load():
    with open(INDEX, "r", encoding="utf-8") as f:
        return json.load(f)

def lookup(name, data=None):
    data = data or _load()
    if name not in data:
        return None
    entry = data[name]
    return {
        "title": entry.get("title", ""),
        "desc": entry.get("desc", entry.get("cont", "")),
        "sub_type": entry["s"],
        "type": entry["t"],
        "param": entry["p"],
        "op_param": entry["o"],
        "lua": entry.get("lua", ""),
        "api": entry.get("api", ""),
    }

def lookup_brief(name, data=None):
    data = data or _load()
    if name not in data:
        return None
    e = data[name]
    return {"t": e["t"], "s": e["s"], "p": e["p"], "o": e["o"]}

def fmt_brief(name, b):
    types = "/".join(b["t"])
    params = ",".join(b["p"]) if b["p"] else "-"
    op = ",".join(b["o"]) if b["o"] else "-"
    return f"{name}\t{types}\t{b['s']}\tparam:{params}\top:{op}"

def lookup_global_events():
    data = _load()
    result = {}
    for k, v in data.items():
        if v["s"] in ("t_system", "t_player", "t_ui") and "EVENT" in v["t"]:
            result[k] = {"sub_type": v["s"], "param": v["p"], "op_param": v["o"]}
    return result

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(1)

    if args[0] == "--global-events":
        events = lookup_global_events()
        for name, info in sorted(events.items()):
            params = ", ".join(info["param"]) if info["param"] else "无"
            print(f"{name} ({info['sub_type']})  args: {params}")
        sys.exit(0)

    brief = "--brief" in args
    names = [a for a in args if not a.startswith("--")]
    if not names:
        print("error: provide at least one ECA name"); sys.exit(1)

    data = _load()
    rc = 0
    for name in names:
        if brief:
            b = lookup_brief(name, data)
            if b is None:
                print(f"{name}\tNOT_FOUND"); rc = 1
            else:
                print(fmt_brief(name, b))
        else:
            r = lookup(name, data)
            if r is None:
                print(f"not found: {name}"); rc = 1
            else:
                json.dump(r, sys.stdout, ensure_ascii=False, indent=2)
                sys.stdout.write("\n")
    sys.exit(rc)
