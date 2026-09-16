# -*- coding: utf-8 -*-
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "gen_function.py"
SPEC = importlib.util.spec_from_file_location("gen_function", SCRIPT)
gen_function = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gen_function)


class FunctionGeneratorTests(unittest.TestCase):
    def test_lua_bind_no_params_table_return(self):
        data = gen_function.build_function(
            {
                "name": "大厅服务 - 创建队伍",
                "func_id": "a1377fd18bfb11f1b9d919bc08ffd172",
                "id": 1263239224,
                "description": "函数描述",
                "returns": [{"name": "result", "type": "TABLE", "var": "t"}],
                "lua_bind": True,
            },
            "EntryMap",
        )

        self.assertEqual(data["func_name"], "大厅服务 - 创建队伍")
        self.assertTrue(data["func_return"])
        self.assertEqual(
            data["func_rtv_name_list"],
            [{"__tuple__": True, "items": ["result", "TABLE"]}],
        )
        eval_arg = data["action"][0]["args_list"][1]
        self.assertEqual(eval_arg["sub_type"], "Eval_Lua_TABLE")
        self.assertEqual(eval_arg["args_list"][0]["args_list"], ["Bind['大厅服务 - 创建队伍']()"])
        self.assertEqual(eval_arg["op_arg"], [None, None, None, None, None])
        self.assertEqual(data["action"][1]["action_type"], 400342)
        self.assertIsNone(data["var_data"][0]["TABLE"]["t"])
        self.assertEqual(data["var_data"][1]["t"], 0)

    def test_integer_and_string_params_use_editor_variable_subtypes(self):
        data = gen_function.build_function(
            {
                "name": "Calc",
                "description": "计算{count}并标记为{label}",
                "params": [
                    {"name": "count", "type": "INTEGER"},
                    {"name": "label", "type": "STRING"},
                ],
                "returns": [{"name": "result", "type": "TABLE", "var": "t"}],
                "lua_bind": True,
            },
            "EntryMap",
        )

        eval_arg = data["action"][0]["args_list"][1]
        self.assertEqual(eval_arg["args_list"][0]["args_list"], ["Bind['Calc'](args[1], args[2])"])
        self.assertEqual(eval_arg["op_arg_enable"], [True, True, False, False, False])
        self.assertEqual(eval_arg["op_arg"][0]["arg_type"], 100002)
        self.assertEqual(eval_arg["op_arg"][0]["sub_type"], 6)
        self.assertEqual(
            eval_arg["op_arg"][0]["args_list"],
            [{"__tuple__": True, "items": ["INTEGER", "count", "local"]}],
        )
        self.assertEqual(eval_arg["op_arg"][1]["arg_type"], 100003)
        self.assertEqual(eval_arg["op_arg"][1]["sub_type"], 2)
        self.assertEqual(data["var_data"][0]["INTEGER"]["count"], 0)
        self.assertEqual(data["var_data"][0]["STRING"]["label"], "")
        self.assertEqual(data["func_des"], "计算{count}并标记为{label}")

    def test_boolean_param_uses_editor_variable_subtype(self):
        data = gen_function.build_function(
            {
                "name": "Connect",
                "description": "按玩法{gameplay_id}连接并设置游戏关卡状态为{is_game_map}",
                "params": [
                    {"name": "gameplay_id", "type": "INTEGER"},
                    {"name": "is_game_map", "type": "BOOLEAN", "required": False},
                ],
                "returns": [{"name": "result", "type": "TABLE", "var": "t"}],
                "lua_bind": True,
            },
            "EntryMap",
        )

        eval_arg = data["action"][0]["args_list"][1]
        self.assertEqual(eval_arg["op_arg_enable"], [True, True, False, False, False])
        self.assertEqual(eval_arg["op_arg"][0]["sub_type"], 6)
        self.assertEqual(
            eval_arg["op_arg"][1],
            {
                "arg_type": 100001,
                "args_list": [
                    {"__tuple__": True, "items": ["BOOLEAN", "is_game_map", "local"]},
                ],
                "sub_type": "VARIABLE",
            },
        )

    def test_optional_param_is_recorded(self):
        data = gen_function.build_function(
            {
                "name": "Optional",
                "description": "使用可选名称{name}",
                "params": [{"name": "name", "type": "STRING", "required": False}],
                "returns": [{"name": "result", "type": "TABLE", "var": "t"}],
                "lua_bind": True,
            },
            "EntryMap",
        )
        self.assertEqual(
            data["func_param_list"],
            [{"__tuple__": True, "items": ["name", False]}],
        )

    def test_param_names_must_appear_as_description_placeholders(self):
        with self.assertRaisesRegex(ValueError, r"\{count\}, \{label\}"):
            gen_function.build_function(
                {
                    "name": "Missing Placeholders",
                    "description": "计算并返回结果",
                    "params": [
                        {"name": "count", "type": "INTEGER"},
                        {"name": "label", "type": "STRING"},
                    ],
                    "returns": [{"name": "result", "type": "TABLE", "var": "t"}],
                    "lua_bind": True,
                },
                "EntryMap",
            )

    def test_stable_ids_are_reproducible_and_shared_across_maps(self):
        spec = {
            "name": "Shared Function",
            "returns": [{"name": "result", "type": "TABLE", "var": "t"}],
            "lua_bind": True,
        }
        first = gen_function.build_function(spec, "EntryMap")
        second = gen_function.build_function(spec, "EntryMap")
        battle = gen_function.build_function(spec, "MapName001")

        self.assertEqual(first["func_id"], second["func_id"])
        self.assertEqual(first["trigger_id"], second["trigger_id"])
        self.assertEqual(first["func_id"], battle["func_id"])
        self.assertEqual(first["trigger_id"], battle["trigger_id"])
        self.assertGreater(first["trigger_id"], 0)

    def test_index_write_appends_without_reordering(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "maps" / "EntryMap" / "global_trigger" / "function"
            out_dir.mkdir(parents=True)
            idx_path = out_dir / "index.txt"
            idx_path.write_text(
                json.dumps({"old.json": 3}, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )

            first = gen_function.update_index(str(out_dir), "new.json")
            second = gen_function.update_index(str(out_dir), "new.json")
            index = json.loads(idx_path.read_text(encoding="utf-8"))

            self.assertEqual(first, 4)
            self.assertEqual(second, 4)
            self.assertEqual(list(index.items()), [("old.json", 3), ("new.json", 4)])


if __name__ == "__main__":
    unittest.main()
