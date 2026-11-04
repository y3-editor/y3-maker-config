# -*- coding: utf-8 -*-
"""ECA 全局变量探针（workaround：MCP 目前没有原生变量读写工具）。

用法：
  py -3 probe_variables.py --list
  py -3 probe_variables.py --get 金币,波次,英雄
  py -3 probe_variables.py --set 某整数变量=100 --set 另一整数变量=3

原理：读取 globaltriggervariable.json 得到变量类型，再通过 y3helper.execute_lua
调用 GameAPI.get/set_trigger_variable_*。需要有已连接的游戏客户端。
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.abspath(os.path.join(HERE, "..", "..", "eca-json-builder"))
sys.path.insert(0, BUILDER_DIR)

import mcp_client  # noqa: E402


GETTERS = {
    "INTEGER": "integer",
    "FLOAT": "float",
    "ANGLE": "float",
    "STRING": "string",
    "BOOLEAN": "boolean",
    "PLAYER": "player",
    "UNIT_ENTITY": "unit_entity",
    "UNIT_GROUP": "unit_group",
    "MODIFIER_ENTITY": "modifier_entity",
    "NEW_TIMER": "new_timer",
}

SETTERS = {
    "INTEGER": "integer",
    "FLOAT": "float",
    "ANGLE": "float",
    "STRING": "string",
    "BOOLEAN": "boolean",
}


def load_variables(root: str, map_name: str) -> dict:
    path = os.path.join(root, "maps", map_name, "globaltriggervariable.json")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    result = {}
    for var_type, names in (data.get("variable_dict") or {}).items():
        if not isinstance(names, dict):
            continue
        for name in names:
            if name:
                result[name] = var_type
    return result


def lua_string(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def parse_literal(raw: str, var_type: str):
    if var_type == "BOOLEAN":
        return raw.lower() in ("1", "true", "yes", "on")
    if var_type in ("FLOAT", "ANGLE"):
        return float(raw)
    if var_type == "INTEGER":
        return int(raw)
    return raw


def main():
    ap = argparse.ArgumentParser(description="ECA 全局变量探针")
    ap.add_argument("--root", default=None)
    ap.add_argument("--map", dest="map_name", default="EntryMap")
    ap.add_argument("--list", action="store_true", help="只读变量清单")
    ap.add_argument("--get", default=None, help="逗号分隔的变量名")
    ap.add_argument("--set", action="append", default=[], help="name=value，可重复")
    args = ap.parse_args()

    root = os.path.abspath(args.root) if args.root else mcp_client.find_project_root(os.getcwd())
    variables = load_variables(root, args.map_name)

    if args.list:
        for name, var_type in sorted(variables.items(), key=lambda x: x[1] + ":" + x[0]):
            print(f"{var_type:18s} {name}")
        return 0

    if not args.get and not args.set:
        ap.print_help()
        return 0

    lines = ["local out = {}"]
    if args.get:
        for name in [x.strip() for x in args.get.split(",") if x.strip()]:
            var_type = variables.get(name)
            if not var_type:
                lines.append(f'table.insert(out, "{name}=<未声明>")')
                continue
            getter = to_lua_getter(var_type)
            lines.append(f'do local v=GameAPI.{getter}({lua_string(name)}); '
                         f'table.insert(out, "{name}="..tostring(v)) end')

    for item in args.set:
        if "=" not in item:
            raise SystemExit(f"--set 格式应为 name=value：{item}")
        name, raw = item.split("=", 1)
        name = name.strip()
        var_type = variables.get(name)
        if not var_type:
            raise SystemExit(f"未声明的全局变量：{name}")
        if var_type not in SETTERS:
            raise SystemExit(f"{name} 的类型 {var_type} 暂不支持 CLI 写入")
        value = parse_literal(raw.strip(), var_type)
        setter = f"set_trigger_variable_{SETTERS[var_type]}"
        value_lua = json.dumps(value, ensure_ascii=False) if not isinstance(value, bool) else ("true" if value else "false")
        lines.append(f'GameAPI.{setter}({lua_string(name)}, {value_lua})')
        lines.append(f'table.insert(out, "{name}="..tostring(GameAPI.{to_lua_getter(var_type)}({lua_string(name)})))')

    lines.append('return table.concat(out, "|")')
    # helper_client() 内部已经完成 initialize，不能再 connect 一次；
    # 重复 initialize 会让 y3-helper 返回 HTTP 400（实测）。
    client = mcp_client.helper_client(root)
    text, payload = client.call("execute_lua", {"code": "\n".join(lines)})
    out = payload.get("output") if isinstance(payload, dict) else None
    print(out if out is not None else text)
    return 0


def to_lua_getter(var_type: str) -> str:
    return f"get_trigger_variable_{GETTERS.get(var_type, 'integer')}"


if __name__ == "__main__":
    sys.exit(main())
