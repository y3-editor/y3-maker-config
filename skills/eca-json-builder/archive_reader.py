# -*- coding: utf-8 -*-
"""Y3 project archive reader/writer.

Files: maps/<map>/archive/{archive.json, archive_storage.json, mapscore.json}

Usage:
  py -3 archive_reader.py list <project_root> --map <map>
  py -3 archive_reader.py read <project_root> --map <map> [--slot SLOT] [--storage] [--score]
"""
import argparse, json, os, sys


def read_json(path):
    if os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def archive_dir(root, map_name):
    return os.path.join(root, "maps", map_name, "archive")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("root")
    p.add_argument("--map", default="EntryMap")
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("list")
    rp = sub.add_parser("read")
    rp.add_argument("--slot")
    rp.add_argument("--storage", action="store_true")
    rp.add_argument("--score", action="store_true")
    args = p.parse_args()
    if not args.cmd:
        p.print_help()
        return 0

    adir = archive_dir(args.root, args.map)
    if not os.path.isdir(adir):
        print(f"archive dir not found: {adir}")
        return 1

    if args.cmd == "list":
        for fn in sorted(os.listdir(adir)):
            fp = os.path.join(adir, fn)
            if not os.path.isfile(fp):
                continue
            d = read_json(fp)
            if fn == "archive.json":
                slots = d.get("archive_slots", {})
                print(f"# {fn}: {len(slots)} slot(s)")
                for k, v in slots.items():
                    val = str(v.get("value", ""))[:40]
                    print(f"  slot {k}: name={v.get('name')}  type={v.get('type')}  value={val}")
            elif fn == "archive_storage.json":
                keys = list(d.keys())
                print(f"# {fn}: {len(keys)} key(s)  [{', '.join(keys[:10])}...]")
            elif fn == "mapscore.json":
                print(f"# {fn}: exists")
            else:
                print(f"# {fn}: exists")
        return 0

    if args.cmd == "read":
        if args.score:
            fp = os.path.join(adir, "mapscore.json")
            data = read_json(fp)
        elif args.storage:
            fp = os.path.join(adir, "archive_storage.json")
            data = read_json(fp)
            if args.slot and args.slot in data:
                data = data[args.slot]
            elif args.slot:
                print(f"slot '{args.slot}' not found")
                return 1
        else:
            fp = os.path.join(adir, "archive.json")
            data = read_json(fp)
            if args.slot:
                slot = data.get("archive_slots", {}).get(args.slot)
                if slot:
                    data = slot
                else:
                    print(f"slot '{args.slot}' not found")
                    return 1
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
