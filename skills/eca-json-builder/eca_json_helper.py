# -*- coding: utf-8 -*-
r"""
ECA JSON helper.

Subcommands:
  template <kind>            Emit empty template (json) for a kind.
  validate <file> [--kind K] Validate ECA JSON structure.
  merge <manual> <auto>      Merge manual fix into auto mapper (dict.update + OpConf append).
  normalize-desc <str>       Normalize describe-format string.
  lookup <eca_name>          Resolve eca_name via eca_index.json (prefer lookup.py).

Stdlib only. Run: py -3 .codemaker\tools\eca_json_helper.py <subcmd> ...
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TEMPLATES = {
    # --- readable_eca manual-fix entries (key -> set/list of eca_name) ---
    "action": {
        "在<#0>的<#1>添加<#2>": ["EXAMPLE_ECA_NAME"],
    },
    "condition": {
        "<#0>等于<#1>": ["EXAMPLE_COND_NAME"],
    },
    "event": {
        "单位<#0>死亡": ["EXAMPLE_EVENT_NAME"],
    },
    "arg": {
        "玩家组": ["PLAYER_GROUP", 1],
    },
    "sub_type": {
        "<#0>的所有者": ["UNIT_OWNER"],
    },
    "sub_type_prefab": {
        "BUFF_TYPE": {"普通": 1, "光环": 2},
    },
    "op_conf": {
        "action_type": {
            "在<#0>的<#1>添加<#2>": [
                {
                    "eca_name": "EXAMPLE_ECA_NAME",
                    "base_desc": "在{#0}的{#1}添加{#2}",
                    "arg_len": 3,
                    "args_typs": [],
                    "args_desc": ["索引为<$0>", "技能等级为<$1>", "创建参数表<$2>"],
                }
            ]
        },
        "sub_type": {},
    },
    "func_conf": {
        "EXAMPLE_FUNC": {
            "func_id": "FUNC_ID_STRING",
            "func_name": "EXAMPLE_FUNC",
            "func_desc": "示例函数描述",
            "func_params_list": [["param1", True], ["param2", False]],
            "func_rtv_name_list": [["ret1", "INTEGER"]],
            "real_param_index": [0],
        }
    },
    "config": {
        "action_type": True,
        "condition_type": True,
        "event_type": True,
        "arg_type": True,
        "sub_type": True,
        "sub_type_prefab": True,
        "op_conf": {"action_type": True, "sub_type": True},
        "func_dict": True,
    },

    # --- project custom_eca entry (dict keyed by eca_name) ---
    "custom_eca": {
        "MY_CUSTOM_ECA": {
            "key": "MY_CUSTOM_ECA",
            "type": ["ACTION"],
            "sub_type": "t_plugin",
            "param": ["UNIT", "INTEGER"],
            "op_param": [],
            "info": ["#default", "0", "BOOLEAN[1]"],
            "auto_type": "expr_common_action",
            "auto_param": "GameAPI:my_api",
            "lua": ["y3.game.my_api({#0}, {#1})"],
            "index": 0,
            "flags": 2147483647
        }
    },

    # --- runtime trigger instance (完整触发器) ---
    "trigger_instance": {
        "trigger_name": "新建触发器",
        "trigger_id": 1635176449,
        "p_trigger_id": None,
        "group_id": 0,
        "enabled": True,
        "valid": True,
        "call_enabled": True,
        "event": [
            {
                "event_type": "INIT_FINISHED",
                "element_id": 1635176449000002,
                "enable": True,
                "args_list": []
            }
        ],
        "condition": [],
        "action": [
            {
                "action_type": "PRINT_MESSAGE_ACTION_TO_DIALOG",
                "element_id": 1635176449000005,
                "enable": True,
                "bp": False,
                "args_list": [
                    {"arg_type": 100175, "sub_type": 1, "args_list": [3]},
                    {"arg_type": 100003, "sub_type": 1, "args_list": ["消息内容"]}
                ]
            }
        ],
        "var_data": [{}, {}, []]
    },

    # --- trigger element (单节点) ---
    "trigger_event": {
        "event_type": "EVENT_NAME",
        "args_list": [],
        "element_id": 0,
        "enable": True,
    },
    "trigger_condition": {
        "condition_type": "COND_NAME",
        "args_list": [],
        "element_id": 0,
        "enable": True,
    },
    "trigger_action": {
        "action_type": "ACTION_NAME",
        "args_list": [],
        "op_arg": [],
        "op_arg_enable": [],
        "element_id": 0,
        "enable": True,
        "bp": False,
    },
    "trigger_arg": {
        "arg_type": 100003,
        "sub_type": 1,
        "args_list": [],
        "op_arg": [],
        "op_arg_enable": [],
    },
}


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------

REQUIRED = {
    "trigger_instance": {
        "trigger_name": str, "trigger_id": int,
        "event": list, "condition": list, "action": list,
    },
    "trigger_event": {"event_type": str, "args_list": list},
    "trigger_condition": {"condition_type": str, "args_list": list},
    "trigger_action": {"action_type": str, "args_list": list},
    "trigger_arg": {"arg_type": (int, str), "sub_type": (int, str), "args_list": list},
    "op_conf_entry": {
        "eca_name": str,
        "base_desc": str,
        "arg_len": int,
        "args_typs": list,
        "args_desc": list,
    },
    "func_conf_entry": {
        "func_id": str,
        "func_name": str,
        "func_desc": str,
        "func_params_list": list,
        "func_rtv_name_list": list,
        "real_param_index": list,
    },
    "custom_eca_entry": {"type": list},
}


def _detect_kind(data):
    if isinstance(data, dict):
        if "trigger_name" in data and "event" in data:
            return "trigger_instance"
        if "action_type" in data:
            return "trigger_action"
        if "condition_type" in data:
            return "trigger_condition"
        if "event_type" in data:
            return "trigger_event"
        if "arg_type" in data and "sub_type" in data:
            return "trigger_arg"
        # mapper file (top-level): keys are descriptions -> list/set
        return "mapper"
    return "unknown"


def _check_required(obj, schema, path, errors):
    for key, expected in schema.items():
        if key not in obj:
            errors.append(f"{path}: missing key '{key}'")
            continue
        val = obj[key]
        ok = isinstance(val, expected) if not isinstance(expected, tuple) else isinstance(val, expected)
        if not ok:
            errors.append(
                f"{path}.{key}: expect {expected}, got {type(val).__name__}"
            )


def _validate_trigger_element(node, path, errors):
    if not isinstance(node, dict):
        return
    kind = _detect_kind(node)
    if kind == "trigger_instance":
        _check_required(node, REQUIRED["trigger_instance"], path, errors)
        for i, ev in enumerate(node.get("event", [])):
            _validate_trigger_element(ev, f"{path}.event[{i}]", errors)
        for i, cond in enumerate(node.get("condition", [])):
            _validate_trigger_element(cond, f"{path}.condition[{i}]", errors)
        for i, act in enumerate(node.get("action", [])):
            _validate_trigger_element(act, f"{path}.action[{i}]", errors)
    elif kind == "trigger_action":
        _check_required(node, REQUIRED["trigger_action"], path, errors)
        for i, a in enumerate(node.get("args_list", [])):
            _validate_trigger_element(a, f"{path}.args_list[{i}]", errors)
        for i, a in enumerate(node.get("op_arg", []) or []):
            _validate_trigger_element(a, f"{path}.op_arg[{i}]", errors)
    elif kind == "trigger_condition":
        _check_required(node, REQUIRED["trigger_condition"], path, errors)
        for i, a in enumerate(node.get("args_list", [])):
            _validate_trigger_element(a, f"{path}.args_list[{i}]", errors)
    elif kind == "trigger_event":
        _check_required(node, REQUIRED["trigger_event"], path, errors)
        for i, a in enumerate(node.get("args_list", [])):
            _validate_trigger_element(a, f"{path}.args_list[{i}]", errors)
    elif kind == "trigger_arg":
        _check_required(node, REQUIRED["trigger_arg"], path, errors)
        if not isinstance(node.get("arg_type"), (int, str)):
            errors.append(f"{path}.arg_type: expect int|str")
        if not isinstance(node.get("sub_type"), (int, str)):
            errors.append(f"{path}.sub_type: expect int|str")
        for i, a in enumerate(node.get("args_list", [])):
            _validate_trigger_element(a, f"{path}.args_list[{i}]", errors)
        for i, a in enumerate(node.get("op_arg", []) or []):
            _validate_trigger_element(a, f"{path}.op_arg[{i}]", errors)


def _validate_op_conf(data, errors):
    if not isinstance(data, dict):
        errors.append("op_conf root: expect dict")
        return
    for top in ("action_type", "sub_type"):
        sub = data.get(top, {})
        if not isinstance(sub, dict):
            errors.append(f"op_conf.{top}: expect dict")
            continue
        for base_desc, entries in sub.items():
            if not isinstance(entries, list):
                errors.append(f"op_conf.{top}['{base_desc}']: expect list")
                continue
            for i, e in enumerate(entries):
                _check_required(e, REQUIRED["op_conf_entry"], f"op_conf.{top}['{base_desc}'][{i}]", errors)


def _validate_func_dict(data, errors):
    if not isinstance(data, dict):
        errors.append("func_dict root: expect dict")
        return
    for k, v in data.items():
        _check_required(v, REQUIRED["func_conf_entry"], f"func_dict['{k}']", errors)


def _validate_custom_eca(data, errors):
    if not isinstance(data, dict):
        errors.append("custom_eca root: expect dict")
        return
    valid_types = {"ACTION", "COND", "EVENT", "VAR_TYPE"}
    for k, v in data.items():
        path = f"custom_eca['{k}']"
        if not isinstance(v, dict):
            errors.append(f"{path}: expect dict"); continue
        _check_required(v, REQUIRED["custom_eca_entry"], path, errors)
        types = v.get("type", [])
        if isinstance(types, list):
            for t in types:
                # ACTION/COND/EVENT/VAR_TYPE/<arg type name>/<event suffix>
                if not isinstance(t, str):
                    errors.append(f"{path}.type contains non-str")
        if "auto_type" in v and v["auto_type"] not in (
            "eatrigger_common", "eatrigger_common_2",
            "expr_common", "expr_common_action", "expr_common_arg",
            "expr_common_get_value", "expr_common_arg_get_value",
        ):
            errors.append(f"{path}.auto_type: unknown '{v['auto_type']}'")


def _validate_mapper(data, name, errors):
    """Top-level mapper file: keys are descriptions -> list/set of eca_name."""
    if not isinstance(data, dict):
        errors.append(f"{name}: expect dict at root"); return
    for desc, names in data.items():
        if not isinstance(desc, str):
            errors.append(f"{name}: non-str key '{desc!r}'")
        if not isinstance(names, (list, set)):
            errors.append(f"{name}['{desc}']: value must be list (set serialized as list)")


def cmd_template(args):
    if args.kind not in TEMPLATES:
        print("unknown kind. valid:", ", ".join(sorted(TEMPLATES)))
        return 2
    sys.stdout.write(json.dumps(TEMPLATES[args.kind], ensure_ascii=False, indent=2))
    sys.stdout.write("\n")
    return 0


def cmd_validate(args):
    with open(args.file, "r", encoding="utf-8") as f:
        data = json.load(f)
    errors = []
    kind = args.kind or _guess_file_kind(args.file, data)
    if kind == "trigger_instance":
        _validate_trigger_element(data, "$", errors)
    elif kind == "trigger_element":
        _validate_trigger_element(data, "$", errors)
    elif kind == "op_conf":
        _validate_op_conf(data, errors)
    elif kind == "func_dict":
        _validate_func_dict(data, errors)
    elif kind == "custom_eca":
        _validate_custom_eca(data, errors)
    elif kind == "mapper":
        _validate_mapper(data, os.path.basename(args.file), errors)
    else:
        errors.append(f"unknown kind '{kind}'")
    if errors:
        for e in errors:
            print(e)
        return 1
    print(f"OK ({kind})")
    return 0


def _guess_file_kind(path, data):
    base = os.path.basename(path).lower()
    if base.startswith("op_conf"):
        return "op_conf"
    if base in ("func_dict.json",):
        return "func_dict"
    if base in ("custom_eca.json",):
        return "custom_eca"
    if base in ("action_type.json", "condition_type.json", "event_type.json",
               "arg_type.json", "sub_type.json", "sub_type_prefab.json"):
        return "mapper"
    if isinstance(data, dict):
        if "trigger_name" in data and "event" in data:
            return "trigger_instance"
        if (
            "action_type" in data or "condition_type" in data
            or "event_type" in data or "arg_type" in data
        ):
            return "trigger_element"
    return "unknown"


# ---------------------------------------------------------------------------
# Merge (mimic merge_manual_fix in eca_conf_mgr.py)
# ---------------------------------------------------------------------------

def cmd_merge(args):
    """Merge manual JSON into auto JSON.
    - Plain mapper files (action_type / condition_type / ...): manual.update(auto reversed)
      i.e. manual entries OVERRIDE auto entries.
    - op_conf files: append manual entries grouped by base_desc.
    """
    with open(args.manual, "r", encoding="utf-8") as f:
        manual = json.load(f)
    with open(args.auto, "r", encoding="utf-8") as f:
        auto = json.load(f)
    base = os.path.basename(args.manual).lower()
    if base.startswith("op_conf"):
        # auto: { base_desc: [entry, ...] }
        for base_desc, entries in manual.items():
            auto.setdefault(base_desc, []).extend(entries)
    else:
        # mapper: dict.update overlays manual onto auto (manual takes precedence)
        merged = dict(auto)
        merged.update(manual)
        auto = merged
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(auto, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"merged -> {args.out}")
    return 0


# ---------------------------------------------------------------------------
# Normalize describe format
# ---------------------------------------------------------------------------

def normalize_describe(s: str) -> str:
    s = re.sub(r"{#(\d+)[^}]*}", r"{#\1}", s)  # {#0 类型} -> {#0}
    s = s.replace("\xa0", "").replace(" ", "")
    s = s.replace("，", ",").replace("：", ":")
    return s


def cmd_normalize(args):
    sys.stdout.write(normalize_describe(args.text))
    sys.stdout.write("\n")
    return 0


# ---------------------------------------------------------------------------
# Lookup eca_name in trigger_new.py
# ---------------------------------------------------------------------------

DEFAULT_TRIGGER_NEW = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "engine", "dm", "commons", "datas", "trigger_new.py",
)


def _load_trigger_new(path):
    if not os.path.isfile(path):
        return None
    src = open(path, "r", encoding="utf-8").read()
    ns = {}
    code = compile(src, path, "exec")
    exec(code, ns)
    return ns.get("data", {})


def cmd_lookup(args):
    path = args.path or DEFAULT_TRIGGER_NEW
    data = _load_trigger_new(path)
    if data is None:
        print(f"lookup 需要 eca_index.json，未找到: {path}（直接用 lookup.py 即可，无需 engine）")
        return 2
    if args.eca_name not in data:
        print(f"not found: {args.eca_name}")
        return 1
    sys.stdout.write(json.dumps(
        data[args.eca_name], ensure_ascii=False, indent=2, default=str
    ))
    sys.stdout.write("\n")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    p = argparse.ArgumentParser(description="ECA JSON helper")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_t = sub.add_parser("template", help="emit template")
    p_t.add_argument("kind", choices=sorted(TEMPLATES))
    p_t.set_defaults(func=cmd_template)

    p_v = sub.add_parser("validate", help="validate JSON file")
    p_v.add_argument("file")
    p_v.add_argument(
        "--kind",
        choices=("trigger_instance", "trigger_element", "op_conf", "func_dict", "custom_eca", "mapper"),
    )
    p_v.set_defaults(func=cmd_validate)

    p_m = sub.add_parser("merge", help="merge manual fix into auto mapper")
    p_m.add_argument("manual")
    p_m.add_argument("auto")
    p_m.add_argument("out")
    p_m.set_defaults(func=cmd_merge)

    p_n = sub.add_parser("normalize-desc", help="normalize describe-format string")
    p_n.add_argument("text")
    p_n.set_defaults(func=cmd_normalize)

    p_l = sub.add_parser("lookup", help="lookup eca_name in trigger_new.py")
    p_l.add_argument("eca_name")
    p_l.add_argument("--path", help="path to trigger_new.py")
    p_l.set_defaults(func=cmd_lookup)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
