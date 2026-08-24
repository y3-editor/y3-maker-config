# -*- coding: utf-8 -*-
"""Plugin ECA function library & trigger data reader/writer.

Handles two Y3 plugin JSON formats:
  func_lib_data   — custom function definitions (no events, call_enabled=true)
  trigger_data    — trigger-driven logic grouped in folders

Both share: trigger_folder_info + serialized_data double-wrapped format.

Usage:
  py -3 plugin_eca.py list <plugin_dir> [--trigger]
  py -3 plugin_eca.py read <plugin_dir> [--id TRIGID] [--trigger]
  py -3 plugin_eca.py dsl <plugin_dir> --id TRIGID [--trigger]

JSON path: plugins/<uuid>/game_play/func_lib_data  or  trigger_data

Format:
  {
    "trigger_folder_info": [tree_of {"_trigger_group_":true, "group":[node,...], "key":"uuid" ...}],
    "serialized_data": [
      [  # per top-folder, parallel to trigger_folder_info[0], trigger_folder_info[1]...
        TRIGGER_JSON or [TRIGGER_JSON, ...]  # per child in folder.group
      ]
    ]
  }
"""
import argparse, json, os, sys

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)
from gen_trigger import load_index
from read_trigger import reverse_trigger


def read_plugin_data(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def write_plugin_data(path, data):
    bak = path + ".bak"
    if os.path.isfile(path):
        import shutil
        shutil.copy2(path, bak)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def resolve_plugin_paths(plugin_dir):
    gp = os.path.join(plugin_dir, "game_play")
    return os.path.join(gp, "func_lib_data"), os.path.join(gp, "trigger_data")


def _flatten_triggers(folder_info, serialized_data):
    """Walk trigger_folder_info + serialized_data in parallel.
    Yields (folder_path, trigger_json_or_None, trigger_id, trigger_name).
    """
    fi = folder_info
    sd = serialized_data

    # sd shape: [[...per-top-folder...]]
    if isinstance(sd, list) and len(sd) == 1:
        sd = sd[0]

    for top_idx, top_node in enumerate(fi):
        if not isinstance(top_node, dict) or not top_node.get("_trigger_group_"):
            continue
        top_name = top_node.get("name", "?")
        top_children = top_node.get("group", [])
        # per-top-folder slice
        if isinstance(sd, list) and top_idx < len(sd):
            top_sd = sd[top_idx]
        else:
            top_sd = {}

        for sub_idx, child in enumerate(top_children):
            if isinstance(child, dict) and child.get("_trigger_group_"):
                sub_name = child.get("name", "?")
                grand = child.get("group", [])
                # per-sub-folder slice
                if isinstance(top_sd, list) and sub_idx < len(top_sd):
                    sub_sd = top_sd[sub_idx]
                else:
                    sub_sd = top_sd if isinstance(top_sd, dict) else {}

                for trig_idx, gchild in enumerate(grand):
                    if isinstance(gchild, list) and len(gchild) >= 2:
                        tid = gchild[0]
                        tname = gchild[1]
                        tj = None
                        if isinstance(sub_sd, dict) and "trigger_id" in sub_sd:
                            tj = sub_sd
                        elif isinstance(sub_sd, list) and trig_idx < len(sub_sd):
                            tj = sub_sd[trig_idx]
                        yield ([top_name, sub_name], tj, tid, tname)

            elif isinstance(child, list) and len(child) >= 2:
                tid = child[0]
                tname = child[1]
                if isinstance(top_sd, dict) and "trigger_id" in top_sd:
                    tj = top_sd
                elif isinstance(top_sd, list) and sub_idx < len(top_sd):
                    tj = top_sd[sub_idx]
                else:
                    tj = None
                yield ([top_name], tj, tid, tname)


def list_triggers(plugin_data):
    results = []
    fi = plugin_data.get("trigger_folder_info", [])
    sd = plugin_data.get("serialized_data", [])
    for path, _, tid, tname in _flatten_triggers(fi, sd):
        results.append(("/".join(path), tid, tname))
    return results


def find_trigger(plugin_data, trigger_id=None, trigger_name=None):
    fi = plugin_data.get("trigger_folder_info", [])
    sd = plugin_data.get("serialized_data", [])
    for path, tj, tid, tname in _flatten_triggers(fi, sd):
        if trigger_id is not None and tid == trigger_id:
            return (path, tj, tid, tname)
        if trigger_name and trigger_name.lower() in str(tname).lower():
            return (path, tj, tid, tname)
    return None


def write_trigger(plugin_data, trigger_id, new_trigger_json, new_name=None):
    """Update trigger by id in-place. Returns True if found+updated."""
    fi = plugin_data.setdefault("trigger_folder_info", [])
    sd = plugin_data.setdefault("serialized_data", [])
    if not sd:
        sd.append([])
    if isinstance(sd, list) and len(sd) == 1 and isinstance(sd[0], list):
        outer = sd[0]
    else:
        outer = sd

    for top_idx, top_node in enumerate(fi):
        if not isinstance(top_node, dict) or not top_node.get("_trigger_group_"):
            continue
        top_children = top_node.get("group", [])
        top_sd = outer[top_idx] if top_idx < len(outer) else {}

        for sub_idx, child in enumerate(top_children):
            if isinstance(child, dict) and child.get("_trigger_group_"):
                grand = child.get("group", [])
                sub_sd = top_sd[sub_idx] if isinstance(top_sd, list) and sub_idx < len(top_sd) else top_sd
                for trig_idx, gchild in enumerate(grand):
                    if isinstance(gchild, list) and gchild[0] == trigger_id:
                        if isinstance(sub_sd, list) and trig_idx < len(sub_sd):
                            sub_sd[trig_idx] = new_trigger_json
                        elif isinstance(sub_sd, dict):
                            top_sd[sub_idx] = new_trigger_json
                        if new_name:
                            gchild[1] = new_name
                        return True
                continue
            if isinstance(child, list) and child[0] == trigger_id:
                if isinstance(top_sd, list) and sub_idx < len(top_sd):
                    top_sd[sub_idx] = new_trigger_json
                elif isinstance(top_sd, dict):
                    outer[top_idx] = new_trigger_json
                if new_name:
                    child[1] = new_name
                return True
    return False


def insert_trigger(plugin_data, trigger_id, new_trigger_json, trigger_name,
                   folder_path=None, top_folder_name="新建函数库", sub_folder_name="新建函数"):
    """Insert a new trigger into folder tree + serialized_data.
    If folder_path is None, uses top_folder_name/sub_folder_name to find or create folders.
    Returns trigger_name."""
    fi = plugin_data.setdefault("trigger_folder_info", [])
    sd = plugin_data.setdefault("serialized_data", [])
    if not sd:
        sd.append([])
    if isinstance(sd, list) and len(sd) == 1 and isinstance(sd[0], list):
        outer = sd[0]
    else:
        outer = sd

    # Ensure top-folder exists
    target_top_idx = None
    for i, node in enumerate(fi):
        if isinstance(node, dict) and node.get("name") == top_folder_name:
            target_top_idx = i
            break
    if target_top_idx is None:
        target_top_idx = len(fi)
        fi.append({
            "_trigger_group_": True,
            "group": [],
            "is_sub_folder": False,
            "key": f"auto_{trigger_id}",
            "name": top_folder_name,
        })
        if target_top_idx >= len(outer):
            outer.append([])
    top_sd = outer[target_top_idx] if target_top_idx < len(outer) else []
    if not isinstance(top_sd, list):
        top_sd = []
        outer[target_top_idx] = top_sd
    top_children = fi[target_top_idx]["group"]

    # Ensure sub-folder exists
    target_sub_idx = None
    for i, child in enumerate(top_children):
        if isinstance(child, dict) and child.get("name") == sub_folder_name:
            target_sub_idx = i
            break
    if target_sub_idx is None:
        target_sub_idx = len(top_children)
        top_children.append({
            "_trigger_group_": True,
            "group": [],
            "is_sub_folder": True,
            "key": f"auto_sub_{trigger_id}",
            "name": sub_folder_name,
        })
        if target_sub_idx >= len(top_sd):
            top_sd.append([])
    sub_sd = top_sd[target_sub_idx] if target_sub_idx < len(top_sd) else []
    if not isinstance(sub_sd, list):
        sub_sd = []
        top_sd[target_sub_idx] = sub_sd
    sub_children = top_children[target_sub_idx]["group"]

    # Add trigger entry
    sub_children.append([trigger_id, trigger_name])
    sub_sd.append(new_trigger_json)
    return trigger_name


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description="Plugin ECA func_lib / trigger data reader")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list")
    rp = sub.add_parser("read")
    rp.add_argument("--id", type=int)
    dp = sub.add_parser("dsl")
    dp.add_argument("--id", type=int, required=True)

    p.add_argument("plugin_dir")
    p.add_argument("--trigger", dest="use_trigger", action="store_true", help="Use trigger_data instead of func_lib_data")
    args = p.parse_args(argv)

    fl, td = resolve_plugin_paths(args.plugin_dir)
    data_path = td if args.use_trigger else fl
    if not os.path.isfile(data_path):
        print(f"error: not found: {data_path}")
        return 1

    data = read_plugin_data(data_path)
    idx = load_index()

    if args.cmd == "list":
        items = list_triggers(data)
        label = "trigger_data" if args.use_trigger else "func_lib_data"
        print(f"# {label} — {len(items)} trigger(s)")
        for folder, tid, tname in items:
            print(f"  [{folder}]  {tid}  {tname}")
        return 0

    if args.cmd == "read":
        if args.id:
            result = find_trigger(data, trigger_id=args.id)
            if result:
                print(json.dumps(result[1], ensure_ascii=False, indent=2))
            else:
                print(f"trigger id={args.id} not found")
                return 1
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "dsl":
        result = find_trigger(data, trigger_id=args.id)
        if not result:
            print(f"trigger id={args.id} not found")
            return 1
        _, trig_json, tid, tname = result
        spec = reverse_trigger(trig_json, idx) if trig_json else {}
        dsl = {"name": tname, "id": tid, "trigger": spec}
        print(json.dumps(dsl, ensure_ascii=False, indent=2))
        return 0

    p.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
