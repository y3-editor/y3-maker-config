# -*- coding: utf-8 -*-
"""Y3 project-level custom events CRUD.

File: project_custom_event.json
  {"conf": {}, "group_info": []}

Usage:
  py -3 project_event.py list <project_root>
  py -3 project_event.py read <project_root> [--id EVENT_ID]
"""
import argparse, json, os, sys

DEFAULT_PATH = "project_custom_event.json"

def _resolve(root, path=None):
    return os.path.join(root, path or DEFAULT_PATH)

def read_events(root, path=None):
    fp = _resolve(root, path)
    if os.path.isfile(fp):
        with open(fp, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"conf": {}, "group_info": []}

def write_events(root, data, path=None):
    fp = _resolve(root, path)
    with open(fp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main(argv=None):
    p = argparse.ArgumentParser(description="Y3 project custom events CRUD")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list")

    rp = sub.add_parser("read")
    rp.add_argument("--id", type=int)

    p.add_argument("root", help="project root dir (parent of project_custom_event.json)")
    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 0

    data = read_events(args.root)

    if args.cmd == "list":
        conf = data.get("conf", {})
        groups = data.get("group_info", [])
        print(f"# custom events: {len(conf)} event(s), {len(groups)} group(s)")
        for k, v in conf.items():
            print(f"  event_id={k}  name={v.get('name','?')}  type={v.get('type','?')}")
        for g in groups:
            print(f"  group: {g.get('name','?')}  key={g.get('key','?')}")
        return 0

    if args.cmd == "read":
        if args.id:
            ev = data.get("conf", {}).get(str(args.id))
            if ev:
                print(json.dumps(ev, ensure_ascii=False, indent=2))
            else:
                print(f"event id={args.id} not found")
                return 1
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
