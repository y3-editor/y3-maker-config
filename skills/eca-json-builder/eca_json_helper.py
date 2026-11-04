# -*- coding: utf-8 -*-
r"""
ECA JSON helper.

Subcommands:
  template <kind>            Emit empty template (json) for a kind.
  validate <file> [--kind K] Validate ECA JSON structure.
  merge <manual> <auto>      Merge manual fix into auto mapper (dict.update + OpConf append).
  normalize-desc <str>       Normalize describe-format string.
  lookup <eca_name>          Resolve eca_name via eca_index.json (prefer lookup.py).

Stdlib only. Run: py -3 .codemaker\skills\eca-json-builder\eca_json_helper.py <subcmd> ...
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

    # --- project ECA function instance (global_trigger/function/*.json) ---
    "function_instance": {
        "action": [
            {
                "action_type": "SET_VARIABLE",
                "args_list": [
                    {
                        "arg_type": 100030,
                        "sub_type": 1,
                        "args_list": [
                            {"__tuple__": True, "items": ["TABLE", "result", "local"]}
                        ],
                    },
                    {
                        "arg_type": 100011,
                        "sub_type": "Eval_Lua_TABLE",
                        "args_list": [
                            {"arg_type": 100003, "sub_type": 1, "args_list": ["Bind['示例函数']()"]}
                        ],
                        "op_arg": [None, None, None, None, None],
                        "op_arg_enable": [False, False, False, False, False],
                    },
                ],
                "bp": False,
                "element_id": 1635176449000002,
                "enable": True,
            },
            {
                "action_type": 400342,
                "args_list": [
                    {
                        "arg_type": 100011,
                        "sub_type": "VARIABLE",
                        "args_list": [
                            {"__tuple__": True, "items": ["TABLE", "result", "local"]}
                        ],
                    }
                ],
                "bp": False,
                "element_id": 1635176449000003,
                "enable": True,
            },
        ],
        "call_enabled": True,
        "condition": [],
        "enabled": True,
        "event": [],
        "func_category": "t_function",
        "func_comment": "",
        "func_des": "示例函数描述",
        "func_id": "0123456789abcdef0123456789abcdef",
        "func_name": "示例函数",
        "func_return": True,
        "func_rtv_name_list": [
            {"__tuple__": True, "items": ["result", "TABLE"]}
        ],
        "group_id": 0,
        "is_func": True,
        "is_official_func": False,
        "p_trigger_id": None,
        "trigger_id": 1635176449,
        "trigger_name": "示例函数",
        "valid": True,
        "var_data": [
            {"NEW_TIMER": {}, "TABLE": {"result": None}},
            {"result": 0},
            ["result"],
        ],
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
    "function_instance": {
        "trigger_name": str, "trigger_id": int,
        "event": list, "condition": list, "action": list, "var_data": list,
        "is_func": bool, "func_id": str, "func_name": str,
        "func_category": str, "is_official_func": bool,
    },
    "trigger_action": {"action_type": (str, int), "args_list": list},
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
        if data.get("is_func") is True:
            return "function_instance"
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


def _is_func_id(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{32}", value) is not None


def _infer_function_dir(file_path):
    parts = os.path.normpath(os.path.abspath(file_path)).split(os.sep)
    tail = ["global_trigger", "trigger"]
    for i in range(len(parts) - len(tail) + 1):
        if parts[i:i + len(tail)] == tail:
            return os.sep.join(parts[:i] + ["global_trigger", "function"])
    return None


def _load_map_function_ids(function_dir):
    if not function_dir or not os.path.isdir(function_dir):
        return None
    ids = set()
    for root, _, files in os.walk(function_dir):
        for name in files:
            if not name.lower().endswith(".json"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            func_id = data.get("func_id") if isinstance(data, dict) else None
            if _is_func_id(func_id):
                ids.add(func_id)
    return ids


def _collect_sub_trigger_ids(node, errors):
    sub = node.get("sub_trigger", {})
    if sub in (None, {}):
        return set()
    if not isinstance(sub, dict):
        errors.append("$.sub_trigger: expect dict")
        return set()
    ids = set()
    for key, child in sub.items():
        try:
            tid = int(key)
        except (TypeError, ValueError):
            errors.append(f"$.sub_trigger[{key!r}]: key must be integer string")
            continue
        if tid in ids:
            errors.append(f"$.sub_trigger[{key!r}]: duplicate sub_trigger id")
        ids.add(tid)
        if isinstance(child, dict):
            child_tid = child.get("trigger_id")
            if child_tid is not None and child_tid != tid:
                errors.append(f"$.sub_trigger[{key!r}].trigger_id: must match sub_trigger key")
    return ids


def _validate_custom_event_arg(node, path, errors):
    if node.get("event_type") != "RECEIVE_CUSTOM_EVENT":
        return
    args = node.get("args_list", [])
    if not args:
        errors.append(f"{path}.args_list[0]: RECEIVE_CUSTOM_EVENT requires CUS_EVENT arg")
        return
    arg = args[0]
    if not isinstance(arg, dict):
        errors.append(f"{path}.args_list[0]: expect trigger_arg for CUS_EVENT")
        return
    if arg.get("arg_type") != 100238:
        errors.append(f"{path}.args_list[0].arg_type: RECEIVE_CUSTOM_EVENT expects 100238")
    values = arg.get("args_list", [])
    if not values:
        errors.append(f"{path}.args_list[0].args_list[0]: RECEIVE_CUSTOM_EVENT requires event id")
        return
    if type(values[0]) is not int:
        errors.append(f"{path}.args_list[0].args_list[0]: RECEIVE_CUSTOM_EVENT event id must be int")


def _validate_call_trigger_func(node, path, errors, ctx):
    if node.get("action_type") != "CALL_TRIGGER_FUNC":
        return
    args = node.get("args_list", [])
    if not args or not isinstance(args[0], dict):
        errors.append(f"{path}.args_list[0]: CALL_TRIGGER_FUNC requires function arg")
        return
    func_arg = args[0]
    func_id = func_arg.get("sub_type")
    if not _is_func_id(func_id):
        errors.append(f"{path}.args_list[0].sub_type: CALL_TRIGGER_FUNC expects 32 lowercase hex func_id string")
        return
    top_func_id = node.get("func_id")
    if top_func_id is not None and not _is_func_id(top_func_id):
        errors.append(f"{path}.func_id: CALL_TRIGGER_FUNC expects 32 lowercase hex func_id string")
    if not isinstance(func_arg.get("sub_type"), str):
        errors.append(f"{path}.args_list[0].sub_type: CALL_TRIGGER_FUNC expects string sub_type")
    known = ctx.get("function_ids") if ctx else None
    if known is not None and func_id not in known:
        errors.append(f"{path}.args_list[0].sub_type: func_id not found in map function JSON: {func_id}")


def _is_plain_json_table_literal(value):
    if isinstance(value, list):
        return True
    if not isinstance(value, dict):
        return False
    if value.get("__tuple__") is True:
        return False
    eca_keys = {"arg_type", "action_type", "condition_type", "event_type"}
    return not any(key in value for key in eca_keys)


def _validate_table_literal_arg(node, path, errors):
    if node.get("arg_type") != 100011 or node.get("sub_type") != 1:
        return
    for i, value in enumerate(node.get("args_list", [])):
        if _is_plain_json_table_literal(value):
            errors.append(
                f"{path}.args_list[{i}]: TABLE literal JSON object/list is not editor-compatible; "
                "build a TABLE variable with GET_NEW_TABLE/SET_TABLE_VALUE or use a TABLE-returning sub_type"
            )


def _validate_optional_args(node, path, errors):
    op_args = node.get("op_arg")
    enabled = node.get("op_arg_enable")
    if op_args is None and enabled is None:
        return
    if not isinstance(op_args, list):
        errors.append(f"{path}.op_arg: expect list")
        return
    if not isinstance(enabled, list):
        errors.append(f"{path}.op_arg_enable: expect list")
        return
    if len(op_args) != len(enabled):
        errors.append(f"{path}: op_arg and op_arg_enable lengths must match")
    for i, is_enabled in enumerate(enabled):
        if type(is_enabled) is not bool:
            errors.append(f"{path}.op_arg_enable[{i}]: expect bool")
        elif is_enabled and (i >= len(op_args) or op_args[i] is None):
            errors.append(f"{path}.op_arg[{i}]: enabled optional argument must not be null")


def _validate_trigger_element(node, path, errors, ctx=None):
    if not isinstance(node, dict):
        return
    kind = _detect_kind(node)
    if kind == "function_instance":
        _check_required(node, REQUIRED["function_instance"], path, errors)
        if node.get("event"):
            errors.append(f"{path}.event: ECA function must not declare events")
        func_id = node.get("func_id")
        if isinstance(func_id, str) and not re.fullmatch(r"[0-9a-f]{32}", func_id):
            errors.append(f"{path}.func_id: expect 32 lowercase hex characters")
        if node.get("func_name") != node.get("trigger_name"):
            errors.append(f"{path}: func_name and trigger_name must match")
        returns = node.get("func_rtv_name_list", [])
        if bool(returns) != bool(node.get("func_return", False)):
            errors.append(f"{path}: func_return must match func_rtv_name_list")
        if len(node.get("var_data", [])) != 3:
            errors.append(f"{path}.var_data: expect [by_type, by_name, ordered_names]")
        for i, act in enumerate(node.get("action", [])):
            _validate_trigger_element(act, f"{path}.action[{i}]", errors, ctx)
    elif kind == "trigger_instance":
        _check_required(node, REQUIRED["trigger_instance"], path, errors)
        if path == "$":
            if ctx is None:
                ctx = {}
            ctx.setdefault("sub_trigger_ids", _collect_sub_trigger_ids(node, errors))
        for i, ev in enumerate(node.get("event", [])):
            _validate_trigger_element(ev, f"{path}.event[{i}]", errors, ctx)
        for i, cond in enumerate(node.get("condition", [])):
            _validate_trigger_element(cond, f"{path}.condition[{i}]", errors, ctx)
        for i, act in enumerate(node.get("action", [])):
            if type(act) is int:
                refs = ctx.get("sub_trigger_ids", set()) if ctx else set()
                if act not in refs:
                    errors.append(f"{path}.action[{i}]: sub_trigger reference not found: {act}")
            _validate_trigger_element(act, f"{path}.action[{i}]", errors, ctx)
        sub = node.get("sub_trigger", {})
        if isinstance(sub, dict):
            for key, child in sub.items():
                if isinstance(child, dict):
                    parent_id = child.get("p_trigger_id")
                    if parent_id is not None and parent_id != node.get("trigger_id"):
                        refs = ctx.get("sub_trigger_ids", set()) if ctx else set()
                        if parent_id not in refs:
                            errors.append(f"{path}.sub_trigger[{key!r}].p_trigger_id: parent trigger not found")
                    _validate_trigger_element(child, f"{path}.sub_trigger[{key!r}]", errors, ctx)
                else:
                    errors.append(f"{path}.sub_trigger[{key!r}]: expect trigger instance")
    elif kind == "trigger_action":
        _check_required(node, REQUIRED["trigger_action"], path, errors)
        _validate_call_trigger_func(node, path, errors, ctx)
        _validate_optional_args(node, path, errors)
        for i, a in enumerate(node.get("args_list", [])):
            _validate_trigger_element(a, f"{path}.args_list[{i}]", errors, ctx)
        for i, a in enumerate(node.get("op_arg", []) or []):
            _validate_trigger_element(a, f"{path}.op_arg[{i}]", errors, ctx)
    elif kind == "trigger_condition":
        _check_required(node, REQUIRED["trigger_condition"], path, errors)
        for i, a in enumerate(node.get("args_list", [])):
            _validate_trigger_element(a, f"{path}.args_list[{i}]", errors, ctx)
    elif kind == "trigger_event":
        _check_required(node, REQUIRED["trigger_event"], path, errors)
        _validate_custom_event_arg(node, path, errors)
        for i, a in enumerate(node.get("args_list", [])):
            _validate_trigger_element(a, f"{path}.args_list[{i}]", errors, ctx)
    elif kind == "trigger_arg":
        _check_required(node, REQUIRED["trigger_arg"], path, errors)
        if not isinstance(node.get("arg_type"), (int, str)):
            errors.append(f"{path}.arg_type: expect int|str")
        if not isinstance(node.get("sub_type"), (int, str)):
            errors.append(f"{path}.sub_type: expect int|str")
        _validate_table_literal_arg(node, path, errors)
        _validate_optional_args(node, path, errors)
        for i, a in enumerate(node.get("args_list", [])):
            _validate_trigger_element(a, f"{path}.args_list[{i}]", errors, ctx)
        for i, a in enumerate(node.get("op_arg", []) or []):
            _validate_trigger_element(a, f"{path}.op_arg[{i}]", errors, ctx)


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
    warnings = []
    kind = args.kind or _guess_file_kind(args.file, data)
    ctx = {"function_ids": _load_map_function_ids(_infer_function_dir(args.file))}
    if kind in ("trigger_instance", "function_instance"):
        _validate_trigger_element(data, "$", errors, ctx)
    elif kind == "trigger_element":
        _validate_trigger_element(data, "$", errors, ctx)
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
    if kind in ("trigger_instance", "function_instance", "trigger_element"):
        _lint_editor_rejected_encodings(data, "$", errors, warnings, args.file)
    if warnings:
        for w in warnings:
            print(f"[WARN] {w}")
    if errors:
        for e in errors:
            print(e)
        return 1
    print(f"OK ({kind})")
    return 0


# ---------------------------------------------------------------------------
# Lint: 编辑器会「静默清成 null」或标红的写法（均已实测）
# ---------------------------------------------------------------------------

# 全局变量读取的 sub_type（实测：写错会被编辑器清成 null）
def _build_global_read_subtype():
    """读取变量 sub_type 优先用源码派生表，避免手写表与生成器漂移。

    背景（实测）：`eca_source_data.json` 里 UNIT_GROUP 的
    variable_subtype 是 14，而旧手写表写的是 11。生成器按源码写出 14，
    审计却按手写表报错，形成假红。这里改为以源码派生表为准。
    """
    fallback = {
        "FLOAT": 2, "ANGLE": 2, "STRING": 2, "INTEGER": 6, "UNIT_ENTITY": 11,
        "UNIT_GROUP": 11,
        "BOOLEAN": "VARIABLE", "PLAYER": "VARIABLE",
        "NEW_TIMER": "VARIABLE", "TABLE": "VARIABLE",
    }
    src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eca_source_data.json")
    try:
        with open(src_path, "r", encoding="utf-8") as fh:
            src = json.load(fh)
        for var_type, sub_type in (src.get("variable_subtype") or {}).items():
            if isinstance(sub_type, (int, str)):
                fallback[var_type] = sub_type
    except (OSError, ValueError):
        pass
    return fallback


_GLOBAL_READ_SUBTYPE = _build_global_read_subtype()
# 参数类型 == 事件名的「包装类事件」，其参数 sub_type 必须写成事件名本身
_WRAPPER_EVENTS = {"GENERIC_UNIT_EVENT"}
_ENTITY_VAR_TYPES = {"UNIT_ENTITY": "NONE_UNIT", "UNIT_GROUP": "NONE_UNIT_GROUP"}
# 变量类型 -> arg_type id（用于校验 SET_VARIABLE 值参数是否与目标变量类型一致）
_VAR_TYPE_ARG_ID = {
    "FLOAT": 100000, "BOOLEAN": 100001, "INTEGER": 100002, "STRING": 100003,
    "POINT": 100004, "UNIT_ENTITY": 100006, "TABLE": 100011, "PLAYER": 100025,
    "UNIT_GROUP": 100026, "UNIT_NAME": 100116, "NEW_TIMER": 100181,
    "ANGLE": 100225, "UI_COMP": 100070, "UI_PREFAB_INSTANCE": 1001558,
}

_UI_INDEX_CACHE = {}


def _ui_index(anchor):
    """按触发器文件路径定位同地图的 maps/<map>/ui/*.json，建 uid -> 子节点数 索引。"""
    if not anchor:
        return {}
    parts = os.path.abspath(anchor).replace("\\", "/").split("/")
    if "maps" not in parts:
        return {}
    pos = parts.index("maps")
    if pos + 1 >= len(parts):
        return {}
    root = "/".join(parts[:pos])
    map_name = parts[pos + 1]
    key = (root, map_name)
    if key in _UI_INDEX_CACHE:
        return _UI_INDEX_CACHE[key]
    table = {}
    ui_dir = os.path.join(root, "maps", map_name, "ui")
    if os.path.isdir(ui_dir):
        for fname in sorted(os.listdir(ui_dir)):
            if not fname.endswith(".json"):
                continue
            try:
                with open(os.path.join(ui_dir, fname), "r", encoding="utf-8") as f:
                    stack = [json.load(f)]
            except (ValueError, OSError):
                continue
            while stack:
                node = stack.pop()
                if not isinstance(node, dict):
                    continue
                uid = node.get("uid")
                if uid:
                    table[uid] = len(node.get("children") or [])
                stack.extend(node.get("children") or [])
    _UI_INDEX_CACHE[key] = table
    return table


def _tuple_items(node):
    if isinstance(node, dict) and node.get("__tuple__") and isinstance(node.get("items"), list):
        return node["items"]
    return None


# ---------------------------------------------------------------------------
# diff：生成结果 vs 编辑器保存后（产品化「回读比对」验证法）
# ---------------------------------------------------------------------------

def _strip_eids(node):
    if isinstance(node, dict):
        return {k: _strip_eids(v) for k, v in node.items() if k != "element_id"}
    if isinstance(node, list):
        return [_strip_eids(v) for v in node]
    return node


def _diff_nodes(expected, actual, path, out, limit=200):
    if len(out) >= limit:
        return
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                out.append(f"{path}.{key}: 编辑器新增 {json.dumps(actual[key], ensure_ascii=False)[:140]}")
            elif key not in actual:
                out.append(f"{path}.{key}: 编辑器删除（生成时是 {json.dumps(expected[key], ensure_ascii=False)[:140]}）")
            else:
                _diff_nodes(expected[key], actual[key], f"{path}.{key}", out, limit)
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            out.append(f"{path}: 数量不同 生成 {len(expected)} / 编辑器 {len(actual)}")
        for i in range(min(len(expected), len(actual))):
            _diff_nodes(expected[i], actual[i], f"{path}[{i}]", out, limit)
    elif expected != actual:
        out.append(
            f"{path}: 生成 {json.dumps(expected, ensure_ascii=False)[:140]}"
            f" → 编辑器 {json.dumps(actual, ensure_ascii=False)[:140]}"
        )


def _collect_subs(node, out):
    if isinstance(node, dict):
        if isinstance(node.get("sub_trigger"), dict):
            out.update(node["sub_trigger"])
        for value in node.values():
            _collect_subs(value, out)
    elif isinstance(node, list):
        for value in node:
            _collect_subs(value, out)


def cmd_diff(args):
    """比对「生成结果」与「编辑器保存后的文件」，列出被编辑器改写/清空的节点。

    编辑器不认识的写法不会报错，而是保存时把参数清成 null；因此回读比对是唯一可靠的验收手段。
    忽略 element_id（每次重建）与键序（编辑器会重排）。
    """
    with open(args.expected, "r", encoding="utf-8") as f:
        expected = json.load(f)
    with open(args.actual, "r", encoding="utf-8") as f:
        actual = json.load(f)

    problems = []
    exp_clean, act_clean = _strip_eids(expected), _strip_eids(actual)
    if json.dumps(exp_clean, ensure_ascii=False, sort_keys=True) != \
       json.dumps(act_clean, ensure_ascii=False, sort_keys=True):
        _diff_nodes(exp_clean, act_clean, "$", problems)

    exp_subs, act_subs = {}, {}
    _collect_subs(expected, exp_subs)
    _collect_subs(actual, act_subs)
    for sid, sub in exp_subs.items():
        label = f"sub_trigger[{sid}] {sub.get('trigger_name')}"
        if sid not in act_subs:
            problems.append(f"{label}: 编辑器保存后丢失")
            continue
        if json.dumps(_strip_eids(sub), ensure_ascii=False, sort_keys=True) != \
           json.dumps(_strip_eids(act_subs[sid]), ensure_ascii=False, sort_keys=True):
            _diff_nodes(_strip_eids(sub), _strip_eids(act_subs[sid]), label, problems)
    for sid in act_subs:
        if sid not in exp_subs:
            problems.append(f"sub_trigger[{sid}]: 编辑器多出来的子触发器 {act_subs[sid].get('trigger_name')}")

    if problems:
        print(f"发现 {len(problems)} 处被编辑器改写/清空：")
        for item in problems:
            print(f"  {item}")
        return 1
    print("OK：编辑器保存后与生成结果一致（写法被接受）")
    return 0


def cmd_scan(args):
    """扫描触发器目录：索引一致性 + 哪些文件含 sub_trigger（决定加载方式）+ 写法 lint。"""
    directory = args.directory
    files = sorted(f for f in os.listdir(directory) if f.endswith(".json"))
    index_path = os.path.join(directory, "index.txt")
    index = {}
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)

    print(f"目录: {directory}")
    print(f"触发器文件 {len(files)} 个；index.txt 条目 {len(index)} 个")

    missing = [f for f in files if f not in index]
    orphan = [k for k in index if k not in files and not k.endswith(".folder")]
    if missing:
        print(f"  [WARN] 未登记到 index.txt: {', '.join(missing)}")
    if orphan:
        print(f"  [WARN] index.txt 有但文件不存在: {', '.join(orphan)}")

    need_restart = []
    importable = []
    for name in files:
        path = os.path.join(directory, name)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        errors, warnings = [], []
        _lint_editor_rejected_encodings(data, "$", errors, warnings, path)
        subs = {}
        _collect_subs(data, subs)
        if subs:
            need_restart.append(name)
            load_hint = (
                f"含 {len(subs)} 个子触发器 → 可用 import_eca 加载（实测新建/覆盖均保留），"
                f"加载后务必用 diff 校验子触发器未被丢弃"
            )
        else:
            importable.append(name)
            load_hint = "可用 import_eca 串行加载"
        flag = "OK" if not errors and not warnings else "问题"
        print(f"  - {name}: {flag}；{load_hint}")
        for e in errors:
            print(f"      [ERROR] {e}")
        for w in warnings:
            print(f"      [WARN] {w}")

    if need_restart:
        print("  含子触发器的文件（import_eca 可用，但要用 diff 复查）:", ", ".join(need_restart))
    if importable:
        print("  可用 import_eca 的文件:", ", ".join(importable))
    return 0


def _lint_editor_rejected_encodings(node, path, errors, warnings, anchor=None):
    if isinstance(node, list):
        for i, value in enumerate(node):
            _lint_editor_rejected_encodings(value, f"{path}[{i}]", errors, warnings, anchor)
        return
    if not isinstance(node, dict):
        return

    items = _tuple_items(node)
    if items is not None and len(items) == 3 and items[2] == "global":
        errors.append(f"{path}: 全局变量引用不能带 scope，应为 2 元组 [类型, 名字]")

    args = node.get("args_list")
    if isinstance(args, list) and len(args) == 1:
        ref = _tuple_items(args[0]) if isinstance(args[0], dict) else None
        if ref is not None and len(ref) == 2 and isinstance(ref[1], str) and ref[0] in _GLOBAL_READ_SUBTYPE:
            sub = node.get("sub_type")
            if node.get("arg_type") == 100030:
                if sub != 1:
                    errors.append(f"{path}: 全局变量写入 sub_type 应为 1，实际 {sub!r}")
            else:
                want = _GLOBAL_READ_SUBTYPE[ref[0]]
                if sub != want:
                    errors.append(
                        f"{path}: 全局变量 '{ref[1]}'({ref[0]}) 读取 sub_type 应为 {want!r}，"
                        f"实际 {sub!r}（编辑器会清成 null）"
                    )

    event_type = node.get("event_type")
    if event_type in _WRAPPER_EVENTS:
        first = (args or [None])[0]
        if not (isinstance(first, dict) and first.get("sub_type") == event_type):
            errors.append(
                f"{path}: 包装事件 {event_type} 的第一个参数 sub_type 必须写成 {event_type!r}"
                f"（写整数会被编辑器清成 null，触发器静默失效）"
            )
    if event_type == "TRIGGER_COMPONENT_EVENT":
        first = (args or [None])[0]
        # ⚠️ 修正：本条规则原先**方向反了**。
        # 实测证据（runtime_pitfalls.md §1）：能被 ECA 收到的只有一条通道 ——
        # 画板控件 `event_list` 里登记的**设计期具名事件** + 子触发器事件参数写
        # **普通字符串字面量**（`{"arg_type":100067,"sub_type":1,"args_list":["bag"]}`）。
        # 工程自带官方画板 GameHUD 的 `bag` / `focus_btn_click` 就是这么接的。
        # 而 `CREATE_UI_COMP_EVENT_EX_EX` + `["STR_TO_UI_EVENT","事件名"]` 的运行期注册通道
        # 虽然能通过编辑器保存、diff 全绿，**运行时收不到事件**（用官方按钮做对照实测）。
        # 因此这里只对「包装类写法含糊」的情况给出提示，不再建议改用 STR_TO_UI_EVENT。
        if isinstance(first, dict) and first.get("sub_type") == 1:
            name = (first.get("args_list") or [None])[0]
            if not isinstance(name, str):
                warnings.append(
                    f"{path}: UI 事件参数不是字符串字面量（收到 {name!r}）；"
                    f"应为 arg_type=100067 / sub_type=1 / args_list=[事件名的字符串]"
                )

    if node.get("action_type") == "SET_VARIABLE" and isinstance(args, list) and len(args) == 2:
        target_items = None
        if isinstance(args[0], dict) and args[0].get("arg_type") == 100030:
            inner = args[0].get("args_list") or [None]
            target_items = _tuple_items(inner[0])
        if target_items:
            vtype = target_items[0]
            value = args[1]
            if vtype in _ENTITY_VAR_TYPES and isinstance(value, dict) and value.get("sub_type") == 1:
                literal = (value.get("args_list") or [None])[0]
                if literal in (0, 0.0):
                    errors.append(
                        f"{path}: {vtype} 变量赋空请用 {_ENTITY_VAR_TYPES[vtype]}，"
                        f"字面量 0 会被编辑器清成 null"
                    )
            # 值参数 arg_type 必须与目标变量类型一致，否则保存时被清成 null
            # （实测：MATH_OPERATION 写进 INTEGER 变量时 arg_type 用了 100000 被清空）
            want_id = _VAR_TYPE_ARG_ID.get(vtype)
            got_id = value.get("arg_type") if isinstance(value, dict) else None
            if want_id is not None and got_id is not None and got_id != want_id:
                errors.append(
                    f"{path}: SET_VARIABLE 值参数 arg_type 应为 {want_id}({vtype})，实际 {got_id}"
                    f"（与目标变量类型不一致会被编辑器清成 null）"
                )

    # MATH_OPERATION 的运算符枚举是 ARITHMETIC_OPERATOR(100016)，
    # 不是 FLOAT_ARITHMETIC_OPERATOR(100017)（工程内编辑器样本 + 探针实测）
    if node.get("sub_type") == "MATH_OPERATION":
        op = (args or [None, None])[1] if isinstance(args, list) and len(args) > 1 else None
        if isinstance(op, dict) and op.get("arg_type") != 100016:
            errors.append(
                f"{path}: MATH_OPERATION 的运算符 arg_type 应为 100016(ARITHMETIC_OPERATOR)，"
                f"实际 {op.get('arg_type')}"
            )

    # UNIT_TYPE_COMPARE 的字面量必须是 UNIT_NAME(100116)：写 100010 不报错，但触发器 valid=false
    # （探针实测：S1/S2/S4 无效，T1/T2 有效）
    if node.get("condition_type") == "UNIT_TYPE_COMPARE" and isinstance(args, list) and len(args) == 3:
        literal = args[2]
        if isinstance(literal, dict) and literal.get("sub_type") == 1:
            if literal.get("arg_type") != 100116:
                errors.append(
                    f"{path}: UNIT_TYPE_COMPARE 的字面量 arg_type 应为 100116(UNIT_NAME)，"
                    f"实际 {literal.get('arg_type')}（写 100010 会让触发器 valid=false）"
                )

    # IF 不能嵌在 ELSE 的动作列表里：编辑器保存时会整体丢弃该嵌套 IF（实测）
    if node.get("action_type") == "IF_THEN_ELSE" and isinstance(args, list) and len(args) == 3:
        else_branch = args[2]
        nested = else_branch.get("args_list") if isinstance(else_branch, dict) else None
        if isinstance(nested, list):
            for action in nested:
                if isinstance(action, dict) and action.get("action_type") == "IF_THEN_ELSE":
                    errors.append(
                        f"{path}: IF_THEN_ELSE 不能嵌在 ELSE 分支里（编辑器保存时会整体丢弃）；"
                        f"请平铺成同层级多个 IF_THEN_ELSE"
                    )
                    break

    # ITER_UI_COMP_DO 遍历的是「该控件的子节点」；用在无子节点控件上会静默不执行
    if node.get("action_type") == "ITER_UI_COMP_DO" and isinstance(args, list) and len(args) >= 2:
        target = args[1]
        if isinstance(target, dict) and target.get("sub_type") == 1:
            uid = (target.get("args_list") or [None])[0]
            if isinstance(uid, str):
                child_count = _ui_index(anchor).get(uid)
                if child_count == 0:
                    errors.append(
                        f"{path}: ITER_UI_COMP_DO 的目标控件（uid {uid}）没有子节点，遍历为空 → "
                        f"内部动作一条都不会执行（实测）"
                    )

    for key, value in node.items():
        _lint_editor_rejected_encodings(value, f"{path}.{key}", errors, warnings, anchor)


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
        if data.get("is_func") is True:
            return "function_instance"
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
        choices=("trigger_instance", "function_instance", "trigger_element", "op_conf", "func_dict", "custom_eca", "mapper"),
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

    p_d = sub.add_parser(
        "diff",
        help="比对生成结果与编辑器保存后的文件（产品化「回读比对」：编辑器不认的写法会被清成 null）",
    )
    p_d.add_argument("expected", help="生成的 JSON（gen_trigger.py --dry-run 的输出或生成时的文件副本）")
    p_d.add_argument("actual", help="编辑器 save_editor 之后回读的 JSON")
    p_d.set_defaults(func=cmd_diff)

    p_s = sub.add_parser(
        "scan",
        help="扫描触发器目录：index 一致性 / 哪些文件含 sub_trigger（决定加载方式）/ 写法 lint",
    )
    p_s.add_argument("directory", help="maps/<地图>/global_trigger/trigger 目录")
    p_s.set_defaults(func=cmd_scan)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
