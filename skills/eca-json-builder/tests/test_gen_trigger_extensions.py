# -*- coding: utf-8 -*-
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))

import gen_trigger


class TriggerExtensionTests(unittest.TestCase):
    def test_custom_event_uses_project_event_types(self):
        index = {
            "RECEIVE_CUSTOM_EVENT": {"p": ["CUS_EVENT"], "o": []},
        }
        event = gen_trigger.build_event(
            ["RECEIVE_CUSTOM_EVENT", 1876423410],
            index,
            gen_trigger.eid_factory(100),
        )
        self.assertEqual(event["args_list"][0]["arg_type"], 100238)

    def test_custom_event_name_resolves_from_map_customevent(self):
        index = {
            "RECEIVE_CUSTOM_EVENT": {"p": ["CUS_EVENT"], "o": []},
        }
        with tempfile.TemporaryDirectory() as root:
            event_dir = Path(root) / "maps" / "EntryMap"
            event_dir.mkdir(parents=True)
            (event_dir / "customevent.json").write_text(
                json.dumps(
                    {
                        "conf": {"1876423410": [["payload", 100011]]},
                        "group_info": [
                            {"__tuple__": True, "items": [1876423410, "LobbyDone"]},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            event_ids = gen_trigger.load_custom_event_name_map(root, "EntryMap")

        event = gen_trigger.build_event(
            ["RECEIVE_CUSTOM_EVENT", "LobbyDone"],
            index,
            gen_trigger.eid_factory(100),
            event_ids,
        )

        self.assertEqual(event["args_list"][0]["arg_type"], 100238)
        self.assertEqual(event["args_list"][0]["args_list"], [1876423410])

    def test_custom_event_integer_is_kept_without_lookup(self):
        index = {
            "RECEIVE_CUSTOM_EVENT": {"p": ["CUS_EVENT"], "o": []},
        }
        event = gen_trigger.build_event(
            ["RECEIVE_CUSTOM_EVENT", 1876423410],
            index,
            gen_trigger.eid_factory(100),
            custom_event_ids={},
        )
        self.assertEqual(event["args_list"][0]["args_list"], [1876423410])

    def test_custom_event_name_rejects_missing_and_ambiguous(self):
        index = {
            "RECEIVE_CUSTOM_EVENT": {"p": ["CUS_EVENT"], "o": []},
        }
        with self.assertRaisesRegex(ValueError, "unknown custom event name"):
            gen_trigger.build_event(
                ["RECEIVE_CUSTOM_EVENT", "Missing"],
                index,
                gen_trigger.eid_factory(100),
                custom_event_ids={},
            )
        with self.assertRaisesRegex(ValueError, "ambiguous custom event name"):
            gen_trigger.build_event(
                ["RECEIVE_CUSTOM_EVENT", "Duplicate"],
                index,
                gen_trigger.eid_factory(100),
                custom_event_ids={"Duplicate": [1, 2]},
            )

    def test_custom_event_payload_parameter_uses_cus_param_type(self):
        index = {
            "GET_CUS_EVENT_PARAM": {
                "p": ["CUS_PARAM"],
                "o": [],
                "t": ["VAR_TYPE"],
            },
        }
        arg = gen_trigger.build_arg(
            ["GET_CUS_EVENT_PARAM", "回调数据"],
            "TABLE",
            index,
            gen_trigger.eid_factory(100),
        )
        self.assertEqual(arg["arg_type"], 100011)
        self.assertEqual(arg["sub_type"], "GET_CUS_EVENT_PARAM")
        self.assertEqual(arg["args_list"][0]["arg_type"], 100240)

    def test_function_call_captures_table_return_and_declares_local(self):
        index = {
            "KEYBOARD_KEY_DOWN_EVENT": {"p": ["KEYBOARD_KEY"], "o": []},
            "DUMP_TABLE": {"p": ["TABLE"], "o": []},
        }
        spec = {
            "name": "大厅服务函数调用测试",
            "id": 1900000001,
            "event": [["KEYBOARD_KEY_DOWN_EVENT", 33]],
            "action": [
                {
                    "call_function": {
                        "func_id": "a1377fd18bfb11f1b9d919bc08ffd172",
                        "args": [],
                        "returns": [{"var": "立即结果", "type": "TABLE"}],
                    }
                },
                ["DUMP_TABLE", {"var": "立即结果", "type": "TABLE"}],
            ],
        }
        trigger = gen_trigger.build_trigger(spec, index, spec["id"])
        call = trigger["action"][0]
        self.assertEqual(call["action_type"], "CALL_TRIGGER_FUNC")
        self.assertEqual(call["call_rt_arg_idxes"], [0])
        self.assertEqual(call["args_list"][0]["op_arg"], [])
        self.assertEqual(call["args_list"][1]["sub_type"], "VARIABLE")
        self.assertEqual(
            call["args_list"][1]["args_list"][0]["items"],
            ["TABLE", "立即结果", "local"],
        )
        self.assertIsNone(trigger["var_data"][0]["TABLE"]["立即结果"])
        self.assertEqual(trigger["var_data"][2], ["立即结果"])

    def test_typed_function_argument_is_serialized(self):
        action = gen_trigger.build_function_call(
            {
                "call_function": {
                    "func_id": "0123456789abcdef0123456789abcdef",
                    "args": [{"type": "INTEGER", "value": 1000}],
                    "returns": [],
                }
            },
            {},
            gen_trigger.eid_factory(100),
        )
        arg = action["args_list"][0]["args_list"][0]
        self.assertEqual(arg, {"arg_type": 100002, "sub_type": 1, "args_list": [1000]})

    def test_union_and_table_var_arguments_infer_from_actual_value(self):
        index = {
            "SET_TABLE_VALUE_1D": {"p": ["TABLE", "[INTEGER,STRING]", "TABLE_VAR"], "t": ["ACTION"], "o": []},
        }
        action = gen_trigger.build_action(
            ["SET_TABLE_VALUE_1D", {"var": "参数表", "type": "TABLE"}, "level_id", "LevelA"],
            index,
            gen_trigger.eid_factory(100),
        )

        self.assertEqual(action["args_list"][1], {"arg_type": 100003, "sub_type": 1, "args_list": ["level_id"]})
        self.assertEqual(action["args_list"][2], {"arg_type": 100003, "sub_type": 1, "args_list": ["LevelA"]})

        action = gen_trigger.build_action(
            ["SET_TABLE_VALUE_1D", {"var": "参数表", "type": "TABLE"}, 1, 1001],
            index,
            gen_trigger.eid_factory(100),
        )
        self.assertEqual(action["args_list"][1], {"arg_type": 100002, "sub_type": 1, "args_list": [1]})
        self.assertEqual(action["args_list"][2], {"arg_type": 100002, "sub_type": 1, "args_list": [1001]})

        action = gen_trigger.build_action(
            ["SET_TABLE_VALUE_1D", {"var": "参数表", "type": "TABLE"}, "child", {"var": "子表", "type": "TABLE"}],
            index,
            gen_trigger.eid_factory(100),
        )
        self.assertEqual(action["args_list"][2]["arg_type"], 100011)
        self.assertEqual(action["args_list"][2]["sub_type"], "VARIABLE")
        self.assertEqual(action["args_list"][2]["args_list"][0]["items"], ["TABLE", "子表", "local"])

    def test_function_call_table_literal_is_lowered_to_editor_table_actions(self):
        index = {
            "KEYBOARD_KEY_DOWN_EVENT": {"p": ["KEYBOARD_KEY"], "o": []},
            "SET_VARIABLE": {"p": ["TABLE", "TABLE"], "t": ["ACTION"], "o": []},
            "GET_NEW_TABLE": {"p": [], "t": ["TABLE"], "o": []},
            "SET_TABLE_VALUE_1D": {"p": ["TABLE", "[INTEGER,STRING]", "TABLE_VAR"], "t": ["ACTION"], "o": []},
        }
        func_id = "0123456789abcdef0123456789abcdef"
        spec = {
            "name": "表参数调用测试",
            "id": 2000000200,
            "event": [["KEYBOARD_KEY_DOWN_EVENT", 33]],
            "action": [
                {
                    "call_function": {
                        "func_id": func_id,
                        "args": [
                            {
                                "type": "TABLE",
                                "value": {
                                    "level_id": "LevelA",
                                    "game_mode": 1001,
                                    "enabled": True,
                                },
                            }
                        ],
                        "returns": [{"var": "立即结果", "type": "TABLE"}],
                    }
                }
            ],
        }

        trigger = gen_trigger.build_trigger(spec, index, spec["id"])
        actions = trigger["action"]

        self.assertEqual([action["action_type"] for action in actions], [
            "SET_VARIABLE",
            "SET_TABLE_VALUE_1D",
            "SET_TABLE_VALUE_1D",
            "SET_TABLE_VALUE_1D",
            "CALL_TRIGGER_FUNC",
        ])
        temp_name = "__table_01234567_arg_1"
        self.assertIn(temp_name, trigger["var_data"][0]["TABLE"])
        self.assertIsNone(trigger["var_data"][0]["TABLE"][temp_name])
        self.assertIn("立即结果", trigger["var_data"][0]["TABLE"])
        self.assertEqual(actions[0]["args_list"][0]["args_list"][0]["items"], ["TABLE", temp_name, "local"])
        self.assertEqual(actions[0]["args_list"][1]["sub_type"], "GET_NEW_TABLE")
        self.assertEqual(actions[1]["args_list"][1], {"arg_type": 100003, "sub_type": 1, "args_list": ["level_id"]})
        self.assertEqual(actions[1]["args_list"][2], {"arg_type": 100003, "sub_type": 1, "args_list": ["LevelA"]})
        self.assertEqual(actions[2]["args_list"][2], {"arg_type": 100002, "sub_type": 1, "args_list": [1001]})
        self.assertEqual(actions[3]["args_list"][2], {"arg_type": 100001, "sub_type": 1, "args_list": [True]})
        call_table_arg = actions[4]["args_list"][0]["args_list"][0]
        self.assertEqual(call_table_arg["arg_type"], 100011)
        self.assertEqual(call_table_arg["sub_type"], "VARIABLE")
        self.assertEqual(call_table_arg["args_list"][0]["items"], ["TABLE", temp_name, "local"])
        dumped = json.dumps(trigger, ensure_ascii=False)
        self.assertNotIn('"args_list": [{"level_id"', dumped)

    def test_nested_function_call_table_literal_declares_temp_table_in_parent_var_data(self):
        index = {
            "KEYBOARD_KEY_DOWN_EVENT": {"p": ["KEYBOARD_KEY"], "o": []},
            "IF_THEN_ELSE": {"p": ["CONDITION_LIST", "ACTION_LIST", "ACTION_LIST"], "t": ["ACTION"], "o": []},
            "STRING_COMPARE": {"p": ["STRING", "BOOLEAN_OPERATOR", "STRING"], "t": ["COND", "BOOLEAN"], "o": []},
            "SET_VARIABLE": {"p": ["TABLE", "TABLE"], "t": ["ACTION"], "o": []},
            "GET_NEW_TABLE": {"p": [], "t": ["TABLE"], "o": []},
            "SET_TABLE_VALUE_1D": {"p": ["TABLE", "[INTEGER,STRING]", "TABLE_VAR"], "t": ["ACTION"], "o": []},
        }
        func_id = "89abcdef0123456789abcdef01234567"
        spec = {
            "name": "nested-call-table-literal",
            "id": 2000000201,
            "event": [["KEYBOARD_KEY_DOWN_EVENT", 33]],
            "action": [
                [
                    "IF_THEN_ELSE",
                    [["STRING_COMPARE", "a", "==", "a"]],
                    [
                        {
                            "call_function": {
                                "func_id": func_id,
                                "args": [
                                    {
                                        "type": "TABLE",
                                        "value": {
                                            "level_id": "LevelA",
                                            "game_mode": 1001,
                                        },
                                    }
                                ],
                                "returns": [{"var": "nested_result", "type": "TABLE"}],
                            }
                        }
                    ],
                    [],
                ]
            ],
        }

        trigger = gen_trigger.build_trigger(spec, index, spec["id"])
        temp_name = "__table_89abcdef_arg_1"

        self.assertIn(temp_name, trigger["var_data"][0]["TABLE"])
        self.assertIsNone(trigger["var_data"][0]["TABLE"][temp_name])
        self.assertIn("nested_result", trigger["var_data"][0]["TABLE"])
        then_actions = trigger["action"][0]["args_list"][1]["args_list"]
        self.assertEqual([action["action_type"] for action in then_actions], [
            "SET_VARIABLE",
            "SET_TABLE_VALUE_1D",
            "SET_TABLE_VALUE_1D",
            "CALL_TRIGGER_FUNC",
        ])
        call_table_arg = then_actions[3]["args_list"][0]["args_list"][0]
        self.assertEqual(call_table_arg["arg_type"], 100011)
        self.assertEqual(call_table_arg["sub_type"], "VARIABLE")
        self.assertEqual(call_table_arg["args_list"][0]["items"], ["TABLE", temp_name, "local"])
        dumped = json.dumps(trigger, ensure_ascii=False)
        self.assertNotIn('"args_list": [{"level_id"', dumped)

    def test_insert_table_value_can_take_table_variable_value(self):
        index = {
            "INSERT_TABLE_VALUE": {"p": ["TABLE", "TABLE_VAR"], "t": ["ACTION"], "o": []},
        }
        action = gen_trigger.build_action(
            ["INSERT_TABLE_VALUE", {"var": "列表", "type": "TABLE"}, {"var": "子表", "type": "TABLE"}],
            index,
            gen_trigger.eid_factory(100),
        )

        self.assertEqual(action["args_list"][1]["arg_type"], 100011)
        self.assertEqual(action["args_list"][1]["sub_type"], "VARIABLE")
        self.assertEqual(action["args_list"][1]["args_list"][0]["items"], ["TABLE", "子表", "local"])

    def test_nested_table_literal_is_rejected_with_clear_error(self):
        index = {
            "SET_VARIABLE": {"p": ["TABLE", "TABLE"], "t": ["ACTION"], "o": []},
            "GET_NEW_TABLE": {"p": [], "t": ["TABLE"], "o": []},
            "SET_TABLE_VALUE_1D": {"p": ["TABLE", "[INTEGER,STRING]", "TABLE_VAR"], "t": ["ACTION"], "o": []},
        }
        with self.assertRaisesRegex(ValueError, "nested TABLE literal is not supported"):
            gen_trigger.build_function_call(
                {
                    "call_function": {
                        "func_id": "0123456789abcdef0123456789abcdef",
                        "args": [{"type": "TABLE", "value": {"players": [{"aid": 1}]}}],
                        "returns": [],
                    }
                },
                index,
                gen_trigger.eid_factory(100),
            )

    def test_raw_dict_and_list_literals_are_not_serialized_as_table_literal(self):
        with self.assertRaisesRegex(ValueError, "dict literal cannot be serialized"):
            gen_trigger.build_arg({"level_id": "LevelA"}, "TABLE", {}, gen_trigger.eid_factory(100))
        with self.assertRaisesRegex(ValueError, "list literal cannot be serialized"):
            gen_trigger.build_arg([{"aid": 1}], "TABLE", {}, gen_trigger.eid_factory(100))

    def test_sub_triggers_are_flattened_and_register_refs_are_bare_ids(self):
        index = {
            "INIT_FINISHED": {"p": [], "o": []},
            "KEYBOARD_KEY_DOWN_EVENT": {"p": ["KEYBOARD_KEY"], "o": []},
            "PRINT_MESSAGE_ACTION_TO_DIALOG": {"p": ["DIALOG_DEBUG_TYPE", "STRING"], "o": []},
            "DUMP_TABLE": {"p": ["TABLE"], "o": []},
        }
        spec = {
            "name": "父触发",
            "id": 2000000001,
            "event": [["INIT_FINISHED"]],
            "action": [{"register_sub_trigger": "按键子触发"}],
            "sub_triggers": [
                {
                    "name": "按键子触发",
                    "id": 2000000002,
                    "event": [["KEYBOARD_KEY_DOWN_EVENT", 18]],
                    "action": [
                        ["DUMP_TABLE", {"var": "立即结果", "type": "TABLE"}],
                        {"register_sub_trigger": "二级子触发"},
                    ],
                    "sub_triggers": [
                        {
                            "name": "二级子触发",
                            "id": 2000000003,
                            "event": [["KEYBOARD_KEY_DOWN_EVENT", 19]],
                            "action": [["PRINT_MESSAGE_ACTION_TO_DIALOG", 3, "done"]],
                        }
                    ],
                }
            ],
        }

        trigger = gen_trigger.build_trigger(spec, index, spec["id"])

        self.assertEqual(trigger["action"], [2000000002])
        self.assertEqual(set(trigger["sub_trigger"]), {"2000000002", "2000000003"})
        child = trigger["sub_trigger"]["2000000002"]
        grandchild = trigger["sub_trigger"]["2000000003"]
        self.assertFalse(child["enabled"])
        self.assertTrue(child["is_conf"])
        self.assertEqual(child["p_trigger_id"], 2000000001)
        self.assertEqual(child["action"][1], 2000000003)
        self.assertEqual(grandchild["p_trigger_id"], 2000000002)
        self.assertIn("立即结果", trigger["var_data"][0]["TABLE"])
        self.assertEqual(child["var_data"], [{}, {}, []])

    def test_register_sub_trigger_rejects_unknown_and_duplicate_refs(self):
        index = {
            "INIT_FINISHED": {"p": [], "o": []},
        }
        unknown = {
            "name": "父触发",
            "id": 2000000001,
            "event": [["INIT_FINISHED"]],
            "action": [{"register_sub_trigger": "不存在"}],
            "sub_triggers": [{"name": "子触发", "id": 2000000002}],
        }
        with self.assertRaisesRegex(ValueError, "unknown sub_trigger"):
            gen_trigger.build_trigger(unknown, index, unknown["id"])

        duplicate = {
            "name": "父触发",
            "id": 2000000001,
            "event": [["INIT_FINISHED"]],
            "action": [{"register_sub_trigger": "子触发"}],
            "sub_triggers": [
                {"name": "子触发", "id": 2000000002},
                {"name": "子触发", "id": 2000000003},
            ],
        }
        with self.assertRaisesRegex(ValueError, "duplicate sub_trigger name"):
            gen_trigger.build_trigger(duplicate, index, duplicate["id"])

    def test_descendant_id_cannot_reuse_root_trigger_id(self):
        index = {"INIT_FINISHED": {"p": [], "o": []}}
        spec = {
            "name": "父触发",
            "id": 2000000001,
            "event": [["INIT_FINISHED"]],
            "sub_triggers": [
                {
                    "name": "子触发",
                    "id": 2000000002,
                    "sub_triggers": [
                        {"name": "错误孙触发", "id": 2000000001}
                    ],
                }
            ],
        }
        with self.assertRaisesRegex(ValueError, "conflicts with parent trigger id"):
            gen_trigger.build_trigger(spec, index, spec["id"])

    def test_omitted_sub_trigger_id_is_stable_by_parent_and_name(self):
        index = {
            "INIT_FINISHED": {"p": [], "o": []},
        }
        spec = {
            "name": "父触发",
            "id": 2000000001,
            "event": [["INIT_FINISHED"]],
            "action": [{"register_sub_trigger": "自动子触发"}],
            "sub_triggers": [{"name": "自动子触发", "event": [["INIT_FINISHED"]]}],
        }
        first = gen_trigger.build_trigger(spec, index, spec["id"])
        second = gen_trigger.build_trigger(
            {
                "name": "父触发",
                "id": 2000000001,
                "event": [["INIT_FINISHED"]],
                "action": [{"register_sub_trigger": "自动子触发"}],
                "sub_triggers": [{"name": "自动子触发", "event": [["INIT_FINISHED"]]}],
            },
            index,
            spec["id"],
        )
        self.assertEqual(first["action"], second["action"])
        self.assertIn(str(first["action"][0]), first["sub_trigger"])

    def test_condition_list_builds_condition_nodes(self):
        index = {
            "STRING_COMPARE": {"p": ["STRING", "BOOLEAN_OPERATOR", "STRING"], "t": ["COND", "BOOLEAN"], "o": []},
        }
        arg = gen_trigger.build_arg(
            [["STRING_COMPARE", "a", "==", "b"]],
            "CONDITION_LIST",
            index,
            gen_trigger.eid_factory(2000000001),
        )
        self.assertEqual(arg["arg_type"], 100021)
        self.assertEqual(arg["sub_type"], 1)
        self.assertEqual(arg["args_list"][0]["condition_type"], "STRING_COMPARE")
        self.assertEqual(arg["args_list"][0]["args_list"][1]["arg_type"], 100035)

    def test_if_then_else_uses_editor_branch_layout_marker(self):
        index = {
            "IF_THEN_ELSE": {
                "p": ["CONDITION_LIST", "ACTION_LIST", "ACTION_LIST"],
                "t": ["ACTION"],
                "o": [],
            },
            "STRING_COMPARE": {
                "p": ["STRING", "BOOLEAN_OPERATOR", "STRING"],
                "t": ["COND", "BOOLEAN"],
                "o": [],
            },
        }
        action = gen_trigger.build_action(
            ["IF_THEN_ELSE", [["STRING_COMPARE", "a", "==", "b"]], [], []],
            index,
            gen_trigger.eid_factory(2000000001),
        )
        self.assertEqual(action["fake_op"], [2])

    def test_editor_authored_dynamic_trigger_is_reproduced_exactly(self):
        reference_path = (
            SKILL_DIR
            / "tests"
            / "fixtures"
            / "editor_authored_dynamic_trigger.json"
        )
        reference = json.loads(reference_path.read_text(encoding="utf-8"))
        spec = {
            "name": "EEEE",
            "id": 1014001747,
            "event": [["KEYBOARD_KEY_DOWN_EVENT", 18]],
            "action": [
                ["PRINT_MESSAGE_ACTION_TO_DIALOG", 3, "EEE"],
                {
                    "call_function": {
                        "func_id": "6f30cca1e4ca5988a85a195b2987e7cc",
                        "args": [],
                        "returns": [{"var": "T", "type": "TABLE"}],
                    }
                },
                ["DUMP_TABLE", {"var": "T", "type": "TABLE"}],
                {"register_sub_trigger": 1215328340},
            ],
            "sub_triggers": [
                {
                    "name": "子触发器_5",
                    "id": 1215328340,
                    "event": [["RECEIVE_CUSTOM_EVENT", 1876423410]],
                    "action": [
                        [
                            "IF_THEN_ELSE",
                            [
                                [
                                    "STRING_COMPARE",
                                    [
                                        "GET_STRING_TABLE_VAR_1D",
                                        ["GET_CUS_EVENT_PARAM", "回调数据"],
                                        "request_id",
                                    ],
                                    "==",
                                    [
                                        "GET_STRING_TABLE_VAR_1D",
                                        {"var": "T", "type": "TABLE"},
                                        "request_id",
                                    ],
                                ]
                            ],
                            [
                                [
                                    "PRINT_MESSAGE_ACTION_TO_DIALOG",
                                    3,
                                    "ECA创建队伍回调，回调数据如下：",
                                ],
                                ["DUMP_TABLE", ["GET_CUS_EVENT_PARAM", "回调数据"]],
                                [
                                    "UNREG_TRIGGER",
                                    ["CURRENT_DYNAMIC_TRIGGER_INSTANCE"],
                                ],
                            ],
                            [],
                        ]
                    ],
                }
            ],
        }

        generated = gen_trigger.build_trigger(
            spec,
            gen_trigger.load_index(),
            spec["id"],
        )

        self.assertEqual(generated, reference)

    def test_load_index_applies_dynamic_trigger_builtin_patch(self):
        idx = gen_trigger.load_index()
        self.assertEqual(idx["GET_STRING_TABLE_VAR_1D"]["p"], ["TABLE", "STRING"])
        self.assertEqual(idx["GET_STRING_TABLE_VAR_1D"]["t"], ["STRING"])

    def test_editor_validated_dynamic_sub_trigger_can_be_written(self):
        trigger = {
            "trigger_name": "动态子触发待验证",
            "sub_trigger": {"2000000002": {}},
        }
        with tempfile.TemporaryDirectory() as root:
            path, filename, out_dir = gen_trigger.write_trigger(trigger, "EntryMap", root)
            self.assertEqual(filename, "动态子触发待验证.json")
            self.assertEqual(Path(out_dir), Path(root) / "maps" / "EntryMap" / "global_trigger" / "trigger")
            self.assertEqual(json.loads(Path(path).read_text(encoding="utf-8")), trigger)

    def test_main_finds_project_from_dsl_when_called_outside_project(self):
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as outside:
            project_path = Path(project)
            map_dir = project_path / "maps" / "EntryMap"
            dsl_dir = project_path / "tools" / "eca"
            map_dir.mkdir(parents=True)
            dsl_dir.mkdir(parents=True)
            (map_dir / "customevent.json").write_text(
                json.dumps(
                    {
                        "group_info": [
                            {"__tuple__": True, "items": [1876423410, "LobbyDone"]},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            dsl_path = dsl_dir / "trigger.json"
            dsl_path.write_text(
                json.dumps(
                    {
                        "map": "EntryMap",
                        "triggers": [
                            {
                                "name": "外部目录调用测试",
                                "id": 2000000100,
                                "event": [["RECEIVE_CUSTOM_EVENT", "LobbyDone"]],
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            previous_cwd = os.getcwd()
            try:
                os.chdir(outside)
                output = StringIO()
                with redirect_stdout(output):
                    self.assertEqual(gen_trigger.main([str(dsl_path), "--dry-run"]), 0)
                    self.assertEqual(gen_trigger.main([str(dsl_path)]), 0)
            finally:
                os.chdir(previous_cwd)

            self.assertIn("1876423410", output.getvalue())
            generated = (
                project_path
                / "maps"
                / "EntryMap"
                / "global_trigger"
                / "trigger"
                / "外部目录调用测试.json"
            )
            self.assertTrue(generated.is_file())
            event_arg = json.loads(generated.read_text(encoding="utf-8"))["event"][0]["args_list"][0]
            self.assertEqual(event_arg["args_list"], [1876423410])


if __name__ == "__main__":
    unittest.main()
