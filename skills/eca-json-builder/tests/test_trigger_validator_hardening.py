# -*- coding: utf-8 -*-
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))

import eca_json_helper


VALID_FUNC_ID = "0123456789abcdef0123456789abcdef"
MISSING_FUNC_ID = "fedcba9876543210fedcba9876543210"


def trigger(action=None, event=None, sub_trigger=None):
    data = {
        "trigger_name": "validator test",
        "trigger_id": 2000000001,
        "p_trigger_id": None,
        "group_id": 0,
        "enabled": True,
        "valid": True,
        "call_enabled": True,
        "event": event or [],
        "condition": [],
        "action": action or [],
        "var_data": [{}, {}, []],
    }
    if sub_trigger is not None:
        data["sub_trigger"] = sub_trigger
    return data


def function_instance(func_id=VALID_FUNC_ID):
    return {
        "trigger_name": "call target",
        "trigger_id": 2000000002,
        "event": [],
        "condition": [],
        "action": [],
        "var_data": [{}, {}, []],
        "is_func": True,
        "func_id": func_id,
        "func_name": "call target",
        "func_category": "t_function",
        "is_official_func": False,
        "func_return": False,
        "func_rtv_name_list": [],
    }


def call_action(func_id=VALID_FUNC_ID):
    return {
        "action_type": "CALL_TRIGGER_FUNC",
        "args_list": [
            {
                "arg_type": 100177,
                "sub_type": func_id,
                "args_list": [],
                "op_arg": [],
                "op_arg_enable": [],
            }
        ],
        "bp": False,
        "element_id": 2000000001000001,
        "enable": True,
    }


def custom_event(event_id):
    return {
        "event_type": "RECEIVE_CUSTOM_EVENT",
        "element_id": 2000000001000001,
        "enable": True,
        "args_list": [
            {
                "arg_type": 100238,
                "sub_type": 1,
                "args_list": [event_id],
            }
        ],
    }


def table_arg(sub_type, args_list):
    return {
        "arg_type": 100011,
        "sub_type": sub_type,
        "args_list": args_list,
    }


def validate_file(path):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = eca_json_helper.cmd_validate(SimpleNamespace(file=str(path), kind=None))
    return rc, out.getvalue()


class TriggerValidatorHardeningTests(unittest.TestCase):
    def test_receive_custom_event_requires_integer_event_id(self):
        errors = []
        eca_json_helper._validate_trigger_element(
            trigger(event=[custom_event("1876423410")]),
            "$",
            errors,
            {},
        )

        self.assertIn("RECEIVE_CUSTOM_EVENT event id must be int", "\n".join(errors))

    def test_call_trigger_func_resolves_against_map_function_json(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root) / "maps" / "EntryMap" / "global_trigger"
            function_dir = base / "function"
            trigger_dir = base / "trigger"
            function_dir.mkdir(parents=True)
            trigger_dir.mkdir(parents=True)
            (function_dir / "target.json").write_text(
                json.dumps(function_instance(), ensure_ascii=False),
                encoding="utf-8",
            )
            trigger_path = trigger_dir / "caller.json"
            trigger_path.write_text(
                json.dumps(trigger(action=[call_action()]), ensure_ascii=False),
                encoding="utf-8",
            )

            rc, output = validate_file(trigger_path)

        self.assertEqual(rc, 0, output)

    def test_call_trigger_func_rejects_unknown_map_function_id(self):
        with tempfile.TemporaryDirectory() as root:
            base = Path(root) / "maps" / "EntryMap" / "global_trigger"
            function_dir = base / "function"
            trigger_dir = base / "trigger"
            function_dir.mkdir(parents=True)
            trigger_dir.mkdir(parents=True)
            (function_dir / "target.json").write_text(
                json.dumps(function_instance(), ensure_ascii=False),
                encoding="utf-8",
            )
            trigger_path = trigger_dir / "caller.json"
            trigger_path.write_text(
                json.dumps(trigger(action=[call_action(MISSING_FUNC_ID)]), ensure_ascii=False),
                encoding="utf-8",
            )

            rc, output = validate_file(trigger_path)

        self.assertEqual(rc, 1)
        self.assertIn("func_id not found in map function JSON", output)

    def test_call_trigger_func_rejects_invalid_top_level_func_id(self):
        action = call_action()
        action["func_id"] = "not-a-func-id"
        errors = []
        eca_json_helper._validate_trigger_element(trigger(action=[action]), "$", errors, {})

        self.assertIn("CALL_TRIGGER_FUNC expects 32 lowercase hex func_id string", "\n".join(errors))

    def test_dynamic_sub_trigger_registration_cannot_be_dangling(self):
        errors = []
        eca_json_helper._validate_trigger_element(
            trigger(action=[2000000003], sub_trigger={"2000000002": trigger()}),
            "$",
            errors,
            {},
        )

        self.assertIn("sub_trigger reference not found: 2000000003", "\n".join(errors))

    def test_table_literal_json_object_is_rejected(self):
        errors = []
        eca_json_helper._validate_trigger_element(
            table_arg(1, [{"level_id": "your_level_id", "game_mode": 20001}]),
            "$",
            errors,
            {},
        )

        self.assertIn("TABLE literal JSON object/list is not editor-compatible", "\n".join(errors))

    def test_table_literal_json_list_is_rejected(self):
        errors = []
        eca_json_helper._validate_trigger_element(
            table_arg(1, [[{"aid": 10001}, {"aid": 10002}]]),
            "$",
            errors,
            {},
        )

        self.assertIn("TABLE literal JSON object/list is not editor-compatible", "\n".join(errors))

    def test_legal_table_variable_and_constructors_are_allowed(self):
        cases = [
            table_arg("VARIABLE", [{"__tuple__": True, "items": ["TABLE", "t", "local"]}]),
            table_arg("VARIABLE", [["TABLE", "UI_Manager"]]),
            table_arg("GET_NEW_TABLE", []),
            table_arg(
                "GET_CUS_EVENT_PARAM",
                [{"arg_type": 100240, "sub_type": 1, "args_list": ["回调数据"]}],
            ),
            table_arg(
                "Eval_Lua_TABLE",
                [{"arg_type": 100003, "sub_type": 1, "args_list": ["return {}"]}],
            ),
        ]

        for case in cases:
            with self.subTest(sub_type=case["sub_type"]):
                errors = []
                eca_json_helper._validate_trigger_element(case, "$", errors, {})
                self.assertNotIn("TABLE literal JSON object/list", "\n".join(errors))

    def test_enabled_optional_argument_cannot_be_null(self):
        broken = table_arg(
            "Eval_Lua_TABLE",
            [{"arg_type": 100003, "sub_type": 1, "args_list": ["return {}"]}],
        )
        broken["op_arg"] = [None]
        broken["op_arg_enable"] = [True]
        errors = []

        eca_json_helper._validate_trigger_element(broken, "$", errors, {})

        self.assertIn(
            "$.op_arg[0]: enabled optional argument must not be null",
            "\n".join(errors),
        )

    def test_call_trigger_func_table_return_variable_is_allowed(self):
        action = call_action()
        action["args_list"].append(
            table_arg("VARIABLE", [{"__tuple__": True, "items": ["TABLE", "result", "local"]}])
        )
        errors = []
        eca_json_helper._validate_trigger_element(trigger(action=[action]), "$", errors, {})

        self.assertNotIn("TABLE literal JSON object/list", "\n".join(errors))


if __name__ == "__main__":
    unittest.main()
