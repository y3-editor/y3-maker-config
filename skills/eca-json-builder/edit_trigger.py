# -*- coding: utf-8 -*-
"""Edit existing ECA triggers via DSL → full JSON rewrite.

Works for global triggers and all obj-edit containers (unit / ability / modifier / item / projectile).
Preserves trigger_id, deterministic element_ids. Always creates .bak backup.

Usage:
  py -3 edit_trigger.py dsl.json                    global trigger write
  py -3 edit_trigger.py dsl.json --dry-run          print to stdout
  py -3 edit_trigger.py dsl.json --unit <key>        unit trigger write (legacy, = --container unit)
  py -3 edit_trigger.py dsl.json --container ability --key <id>   ability trigger write
  py -3 edit_trigger.py dsl.json --container modifier --key <id>  modifier trigger write
  py -3 edit_trigger.py dsl.json --container item --key <id>      item trigger write
  py -3 edit_trigger.py dsl.json --container projectile --key <id> projectile trigger write
"""
from __future__ import annotations
import argparse, json, os, shutil, sys

# Reuse gen_trigger's build logic
SKILL_DIR = os.path.dirname(os.path.abspath(__file__))

# Import gen_trigger modules
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)
from gen_trigger import (
    load_index, build_trigger, find_project_root, update_index,
)


def backup_file(path):
    bak = path + ".bak"
    if os.path.isfile(path):
        shutil.copy2(path, bak)


def remove_from_index(out_dir, fname):
    idx_path = os.path.join(out_dir, "index.txt")
    if not os.path.isfile(idx_path):
        return
    with open(idx_path, "r", encoding="utf-8") as f:
        idx = json.load(f)
    if fname in idx:
        del idx[fname]
    with open(idx_path, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=4)


def edit_global_trigger(trigger_dict, map_name, project_root, dry_run):
    """Write a single trigger to global_trigger/ directory.
    Overwrites existing file if trigger_id matches. Renames if name changed.
    """
    out_dir = os.path.join(project_root, "maps", map_name, "global_trigger", "trigger")
    os.makedirs(out_dir, exist_ok=True)

    trigger_id = trigger_dict.get("trigger_id")
    new_name = trigger_dict.get("trigger_name", "")
    new_fname = new_name + ".json"
    new_path = os.path.join(out_dir, new_fname)

    # Check if a trigger with this ID already exists under a different name
    old_path = None
    old_fname = None
    for fname in os.listdir(out_dir):
        if not fname.endswith(".json"):
            continue
        fpath = os.path.join(out_dir, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if existing.get("trigger_id") == trigger_id:
                old_path = fpath
                old_fname = fname
                break
        except Exception:
            pass

    if dry_run:
        print(json.dumps(trigger_dict, ensure_ascii=False, indent=2))
        return new_name, None, None

    # Backup existing
    if old_path and os.path.isfile(old_path):
        backup_file(old_path)
    elif os.path.isfile(new_path):
        backup_file(new_path)

    # If old file exists and new name differs, remove old file + index entry
    if old_path and old_fname and old_fname != new_fname:
        os.remove(old_path)
        remove_from_index(out_dir, old_fname)

    # Write new
    with open(new_path, "w", encoding="utf-8") as f:
        json.dump(trigger_dict, f, ensure_ascii=False, indent=4)

    # Update index (add if not present)
    idx = update_index(out_dir, new_fname)
    return new_name, new_path, idx


CONTAINER_TYPES = {"unit", "ability", "modifier", "item", "projectile"}

def edit_obj_triggers(dsl, map_name, project_root, obj_key, dry_run, container="unit"):
    """Write triggers back to obj-edit JSON's trigger_dict.
    Supports unit/ability/modifier/item/projectile.
    Returns (results_list, 0) or (None, error_code).
    """
    obj_path = os.path.join(project_root, "maps", map_name, container, obj_key + ".json")

    if not os.path.isfile(obj_path):
        print(f"error: {container} file not found: {obj_path}")
        return None, 1

    backup_file(obj_path)

    with open(obj_path, "r", encoding="utf-8") as f:
        obj_data = json.load(f)

    idx_data = load_index()

    if dry_run:
        for spec in dsl.get("triggers", []):
            trig = build_trigger(spec, idx_data, spec.get("id", 0))
            print(json.dumps(trig, ensure_ascii=False, indent=2))
        return [], 0

    trigger_dict = obj_data.setdefault("trigger_dict", {})
    trigger_group_info = obj_data.setdefault("trigger_group_info", [])

    results = []
    for spec in dsl.get("triggers", []):
        tid = spec.get("id")
        if not tid:
            print("error: obj-edit triggers require explicit 'id' in DSL")
            return None, 1
        trig = build_trigger(spec, idx_data, tid)
        trig["group_id"] = spec.get("group_id", int(obj_key))
        trigger_dict[str(tid)] = trig
        results.append((spec.get("name", "?"), tid))

        # Update trigger_group_info
        found = False
        for tgi in trigger_group_info:
            if tgi.get("key") == int(obj_key):
                groups = tgi.setdefault("group", [])
                for g in groups:
                    if isinstance(g, dict) and g.get("__tuple__"):
                        items = g.get("items", [])
                        if len(items) >= 1 and items[0] == tid:
                            items[1] = spec.get("name", "")
                            found = True
                            break
                if not found:
                    groups.append({"__tuple__": True, "items": [tid, spec.get("name", "")]})
                    found = True
                break
        if not found:
            trigger_group_info.append({
                "_trigger_group_": True,
                "group": [{"__tuple__": True, "items": [tid, spec.get("name", "")]}],
                "key": int(obj_key),
                "name": str(obj_key),
            })

    with open(obj_path, "w", encoding="utf-8") as f:
        json.dump(obj_data, f, ensure_ascii=False, indent=2)
    return results, 0


def delete_global_trigger(name, map_name, project_root, dry_run):
    """Delete a global trigger by name (fuzzy). Returns (ok, msg)."""
    trigger_dir = os.path.join(project_root, "maps", map_name, "global_trigger", "trigger")
    if not os.path.isdir(trigger_dir):
        return False, f"trigger dir not found: {trigger_dir}"

    idx_path = os.path.join(trigger_dir, "index.txt")
    idx = {}
    if os.path.isfile(idx_path):
        with open(idx_path, "r", encoding="utf-8") as f:
            idx = json.load(f)

    # Exact filename match
    exact = os.path.join(trigger_dir, name + ".json")
    target_path = None
    target_fname = None

    if os.path.isfile(exact):
        target_path = exact
        target_fname = name + ".json"
    else:
        # index lookup
        if name in idx:
            target_path = os.path.join(trigger_dir, name)
            target_fname = name
        else:
            # Fuzzy by trigger_name content
            for fname in os.listdir(trigger_dir):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(trigger_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if name.lower() in data.get("trigger_name", "").lower():
                        target_path = fpath
                        target_fname = fname
                        break
                except Exception:
                    pass

    if not target_path:
        return False, f"trigger not found: {name} (map={map_name})"

    if dry_run:
        return True, f"(dry-run) would delete {target_fname}"

    backup_file(target_path)
    os.remove(target_path)
    if target_fname in idx:
        del idx[target_fname]
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, ensure_ascii=False, indent=4)
    return True, f"deleted {target_fname}"


def delete_obj_trigger(name, map_name, project_root, obj_key, dry_run, container="unit"):
    """Delete a trigger from obj-edit JSON by name (fuzzy). Returns (ok, msg)."""
    obj_path = os.path.join(project_root, "maps", map_name, container, obj_key + ".json")
    if not os.path.isfile(obj_path):
        return False, f"{container} file not found: {obj_path}"

    backup_file(obj_path)

    with open(obj_path, "r", encoding="utf-8") as f:
        obj_data = json.load(f)

    trigger_dict = obj_data.get("trigger_dict", {})
    found_tid = None
    for tid_str, trig in trigger_dict.items():
        if name.lower() in trig.get("trigger_name", "").lower():
            found_tid = tid_str
            break

    if found_tid is None:
        return False, f"trigger not found in {container} {obj_key}: {name}"

    if dry_run:
        return True, f"(dry-run) would delete trigger id={found_tid} from {container} {obj_key}"

    trig_name = trigger_dict[found_tid].get("trigger_name", "?")
    del trigger_dict[found_tid]

    # Clean trigger_group_info
    trigger_group_info = obj_data.get("trigger_group_info", [])
    found_tid_int = int(found_tid)
    for tgi in trigger_group_info:
        if tgi.get("key") == int(obj_key):
            groups = tgi.get("group", [])
            tgi["group"] = [g for g in groups
                           if not (isinstance(g, dict) and g.get("__tuple__")
                                   and len(g.get("items", [])) >= 1
                                   and g["items"][0] == found_tid_int)]

    with open(obj_path, "w", encoding="utf-8") as f:
        json.dump(obj_data, f, ensure_ascii=False, indent=2)
    return True, f"deleted [{container} {obj_key}] {trig_name} (id={found_tid})"


def main(argv=None):
    p = argparse.ArgumentParser(description="Edit ECA trigger via DSL")
    p.add_argument("dsl", nargs="?", help="path to DSL JSON file (required, unless --delete)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--unit", help="unit key (legacy, = --container unit --key)")
    p.add_argument("--container", default="unit", help="obj-edit container type: unit/ability/modifier/item/projectile")
    p.add_argument("--key", help="obj-edit key (unit_id / ability_id / ...)")
    p.add_argument("--root", default=None, help="project root (auto-detected)")
    p.add_argument("--delete", help="trigger name to delete")
    p.add_argument("--map", default="EntryMap", help="map name (default: EntryMap)")
    args = p.parse_args(argv)

    root = args.root or find_project_root()
    map_name = args.map

    obj_key = args.key or args.unit
    container = args.container if obj_key else "unit"
    if args.unit and not args.key:
        container = "unit"  # legacy --unit mode

    # --delete mode
    if args.delete:
        if obj_key:
            ok, msg = delete_obj_trigger(args.delete, map_name, root, obj_key, args.dry_run, container)
        else:
            ok, msg = delete_global_trigger(args.delete, map_name, root, args.dry_run)
        print(f"{'OK' if ok else 'error'}: {msg}")
        return 0 if ok else 1

    if not args.dsl:
        p.error("the following arguments are required: dsl (or use --delete)")

    with open(args.dsl, "r", encoding="utf-8") as f:
        dsl = json.load(f)

    # Obj-edit trigger mode
    if obj_key or dsl.get("unit"):
        key = obj_key or dsl.get("unit")
        results, rc = edit_obj_triggers(dsl, map_name, root, key, args.dry_run, container)
        if not args.dry_run and results:
            for name, tid in results:
                print(f"OK  [{container} {key}]  {name}  (id={tid})")
        return rc

    # Global trigger mode
    triggers = dsl.get("triggers", [])
    if not triggers:
        print("no triggers in DSL")
        return 1

    idx_data = load_index()
    results = []

    for spec in triggers:
        tid = spec.get("id")
        if not tid:
            print("error: global trigger '{}' missing 'id'. DSL must have explicit id for edit.".format(
                spec.get("name", "?")))
            return 1
        trig = build_trigger(spec, idx_data, tid)
        name, path, idx = edit_global_trigger(trig, map_name, root, args.dry_run)
        results.append((name, path, idx))

    if not args.dry_run:
        for name, path, idx in results:
            if path:
                print(f"OK [{idx}]  {name}  → {path}")
            else:
                print(f"OK (dry)  {name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
