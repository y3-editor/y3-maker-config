# -*- coding: utf-8 -*-
"""Y3 ECA table data (tables/*.json) reader/writer.

Format:
  {"column_width": {"0": 171}, "table_data": {"data": [["Key","Type","Value","Des"], [...], ...]}}

Usage:
  py -3 table_reader.py list <json_file>
  py -3 table_reader.py read <json_file> [--key KEY] [--row N]
  py -3 table_reader.py find <json_file> --key KEY
"""
import argparse, json, os, sys


def read_table(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_table(path, data):
    bak = path + ".bak"
    if os.path.isfile(path):
        import shutil; shutil.copy2(path, bak)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_rows(table_data):
    data = table_data.get("table_data", {}).get("data", [])
    if not data or len(data) < 1:
        return [], []
    headers = data[0]
    rows = []
    for r in data[1:]:
        d = {headers[j]: r[j] for j in range(min(len(headers), len(r)))}
        rows.append(d)
    return headers, rows

def detect_key_column(data):
    """Auto-detect key column from header row (case-insensitive)."""
    headers = data.get("table_data", {}).get("data", [None])
    if not headers or len(headers) == 0:
        return "Key"
    h0 = headers[0] if isinstance(headers[0], list) else []
    for candidate in ["Key", "key", "ID", "id", "Name"]:
        for h in h0:
            if isinstance(h, str) and h.lower() == candidate.lower():
                return h
    return h0[0] if h0 else "Key"

def find_row(table_data, key_column=None, key_value=None):
    if key_column is None:
        key_column = detect_key_column(table_data)
    _, rows = get_rows(table_data)
    for i, r in enumerate(rows):
        if str(r.get(key_column, "")) == str(key_value):
            return i, r
    return None, None

def upsert_row(table_data, row_dict, key_column=None):
    if key_column is None:
        key_column = detect_key_column(table_data)
    data = table_data.setdefault("table_data", {}).setdefault("data", [])
    if not data:
        data.append([key_column])
    headers = data[0]
    key_val = row_dict.get(key_column)
    for i in range(1, len(data)):
        r = data[i]
        ki = headers.index(key_column) if key_column in headers else 0
        if ki < len(r) and str(r[ki]) == str(key_val):
            for h, v in row_dict.items():
                if h not in headers:
                    headers.append(h)
                hi = headers.index(h)
                while len(r) <= hi:
                    r.append(None)
                r[hi] = v
            return i - 1, False
    for h in row_dict:
        if h not in headers:
            headers.append(h)
    new_row = [None] * len(headers)
    for h, v in row_dict.items():
        new_row[headers.index(h)] = v
    data.append(new_row)
    return len(data) - 2, True

def delete_row(table_data, key_column=None, key_value=None):
    if key_column is None:
        key_column = detect_key_column(table_data)
    data = table_data.get("table_data", {}).get("data", [])
    headers = data[0] if data else []
    ki = headers.index(key_column) if key_column in headers else 0
    for i in range(1, len(data)):
        r = data[i]
        if ki < len(r) and str(r[ki]) == str(key_val):
            removed = {headers[j]: r[j] for j in range(min(len(headers), len(r)))}
            del data[i]
            return 1, removed
    return 0, None

# --- Plugin table_editor_resource (keyed: {table_name: table_data}) ---
def read_plugin_table(plugin_dir, table_name=None):
    data_path = os.path.join(plugin_dir, "game_play", "table_editor_resource", "table_editor_data")
    if not os.path.isfile(data_path):
        return {}
    data = read_table(data_path)
    return data.get(table_name, {}) if table_name else data

def write_plugin_table(plugin_dir, table_name, table_data):
    data_path = os.path.join(plugin_dir, "game_play", "table_editor_resource", "table_editor_data")
    data = read_table(data_path) if os.path.isfile(data_path) else {}
    data[table_name] = table_data
    write_table(data_path, data)

# --- CLI ---
def main(argv=None):
    p = argparse.ArgumentParser(description="Y3 ECA Table reader/writer")
    sub = p.add_subparsers(dest="cmd")

    sp_list = sub.add_parser("list")
    sp_list.add_argument("path")

    sp_read = sub.add_parser("read")
    sp_read.add_argument("path")
    sp_read.add_argument("--key")
    sp_read.add_argument("--row", type=int)

    sp_find = sub.add_parser("find")
    sp_find.add_argument("path")
    sp_find.add_argument("--key", required=True)

    args = p.parse_args(argv)
    if not args.cmd:
        p.print_help()
        return 0

    if args.cmd == "list":
        if os.path.isfile(args.path):
            t = read_table(args.path)
            h, rows = get_rows(t)
            print(f"# {os.path.basename(args.path)}: cols={h} rows={len(rows)}")
            for i, r in enumerate(rows):
                k = r.get('Key', r.get(list(r.keys())[0] if r else '?'))
                print(f"  [{i}] {k}")
        elif os.path.isdir(args.path):
            for fn in sorted(os.listdir(args.path)):
                if fn.endswith('.json'):
                    fp = os.path.join(args.path, fn)
                    t = read_table(fp)
                    h, rows = get_rows(t)
                    print(f"# {fn}: cols={len(h)} rows={len(rows)}")
        return 0

    if args.cmd == "read":
        t = read_table(args.path)
        if args.key:
            idx, row = find_row(t, key_value=args.key)
            if row:
                print(json.dumps(row, ensure_ascii=False, indent=2))
            else:
                print(f"key '{args.key}' not found")
                return 1
        elif args.row is not None:
            _, rows = get_rows(t)
            if 0 <= args.row < len(rows):
                print(json.dumps(rows[args.row], ensure_ascii=False, indent=2))
            else:
                print(f"row {args.row} out of range (0-{len(rows)-1})")
        else:
            print(json.dumps(t, ensure_ascii=False, indent=2))
        return 0

    if args.cmd == "find":
        t = read_table(args.path)
        idx, row = find_row(t, key_value=args.key)
        if row:
            print(json.dumps(row, ensure_ascii=False, indent=2))
        else:
            print(f"key '{args.key}' not found")
            return 1
        return 0

    return 0

if __name__ == "__main__":
    sys.exit(main())
