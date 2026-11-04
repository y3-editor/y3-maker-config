# -*- coding: utf-8 -*-
"""生成期硬校验的回归测试。

覆盖已实测踩过的坑，防止再生成出「编辑器会飘红/静默清空」的触发器：
  1. 引用未声明的全局变量 → 直接报错
  2. SET_VARIABLE 值参数 arg_type 必须与目标变量类型一致
  3. IF 不能嵌在 ELSE 分支的动作列表里（编辑器会丢掉）
  4. ITER_UI_COMP_DO 用在无子节点的控件上（遍历为空，事件注册不上）
  5. UNIT_TYPE_COMPARE 字面量必须是 UNIT_NAME(100116)
  6. MATH_OPERATION 的运算符必须是 ARITHMETIC_OPERATOR(100016)
  7. 全局 UNIT_NAME 变量的读取要给出告警
  8. DSL 的 event 必须是「事件列表的列表」（一维数组会生成 event_type: UNKNOWN 静默不触发）
  9. 位置参数个数必须与定义一致（少传 → 后面的参数整体前移错位；多传 → 被编辑器静默丢弃）
 10. 参数类型相同的「易错动作」必须具名传参（APPLY_DAMAGE 的第 0/2 槽都是单位，
     写反了编辑器不报错、触发器 valid=true，但伤害全落在施法者身上）
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR))

import gen_trigger  # noqa: E402
import eca_json_helper  # noqa: E402


MAP = "TestMap"


def make_project(tmp: Path, *, globals_=None, panels=None) -> Path:
    """搭一个最小工程：全局变量文件 + 画板 JSON。"""
    map_dir = tmp / "maps" / MAP
    (map_dir / "ui").mkdir(parents=True, exist_ok=True)
    if globals_ is not None:
        (map_dir / "globaltriggervariable.json").write_text(
            json.dumps({"variable_dict": globals_, "variable_group_info": [],
                        "variable_length_dict": {}}, ensure_ascii=False),
            encoding="utf-8")
    if panels is not None:
        (map_dir / "ui" / "TestPanel.json").write_text(panels, encoding="utf-8")
    return tmp


class GeneratorGuardTest(unittest.TestCase):
    def setUp(self):
        self.idx = gen_trigger.load_index()
        self.tmp = Path(tempfile.mkdtemp())
        make_project(
            self.tmp,
            globals_={"INTEGER": {"金币": 0}, "BOOLEAN": {"已选英雄": False},
                      "UNIT_NAME": {"目标单位类型": ""},
                      "UNIT_ENTITY": {"技能目标": 0}},
            panels=json.dumps({
                "name": "TestPanel", "uid": "panel-uid", "type": 2,
                "children": [
                    {"name": "block", "uid": "block-uid", "type": 7, "children": [
                        {"name": "btn_ok", "uid": "btn-ok-uid", "type": 1, "children": []},
                        {"name": "card_1", "uid": "card-uid", "type": 1, "children": [
                            {"name": "icon", "uid": "icon-uid", "type": 4, "children": []}
                        ]},
                    ]},
                ],
            }, ensure_ascii=False),
        )
        gen_trigger.load_global_vars(str(self.tmp), MAP)
        gen_trigger.load_ui_nodes(str(self.tmp), MAP)
        self.eid = gen_trigger.eid_factory(1930000001)

    def action(self, spec):
        return gen_trigger.build_action(spec, self.idx, self.eid)

    def test_undeclared_global_var_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.action(["SET_VARIABLE",
                         {"var": "不存在的变量", "type": "INTEGER", "scope": "global"}, 1])
        self.assertIn("未声明的全局变量", str(ctx.exception))

    def test_set_variable_value_type_pinned_to_target(self):
        node = self.action(["SET_VARIABLE",
                            {"var": "金币", "type": "INTEGER", "scope": "global"},
                            ["MATH_OPERATION",
                             {"var": "金币", "type": "INTEGER", "scope": "global"}, "+", 5]])
        value = node["args_list"][1]
        # 关键：arg_type 必须是 INTEGER(100002)，不能是表达式自身的 FLOAT(100000)
        self.assertEqual(100002, value["arg_type"])
        self.assertEqual("MATH_OPERATION", value["sub_type"])

    def test_if_in_else_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.action(["IF_THEN_ELSE", [], [],
                         [["IF_THEN_ELSE", [], [], []]]])
        self.assertIn("ELSE", str(ctx.exception))

    def test_bare_event_list_rejected(self):
        """event 写成一维数组 ["INIT_FINISHED"] 必须直接报错（否则生成 UNKNOWN，触发器静默不触发）。"""
        spec = {"name": "错误事件写法", "id": 1930000999,
                "event": ["INIT_FINISHED"], "action": []}
        with self.assertRaises(ValueError) as ctx:
            gen_trigger.build_trigger(spec, self.idx, spec["id"])
        self.assertIn("event", str(ctx.exception))
        self.assertIn("UNKNOWN", str(ctx.exception))

    def test_nested_event_list_accepted(self):
        """event 写成 [["INIT_FINISHED"]] 是正确写法，应正常生成。"""
        spec = {"name": "正确事件写法", "id": 1930000998,
                "event": [["INIT_FINISHED"]], "action": []}
        trig = gen_trigger.build_trigger(spec, self.idx, spec["id"])
        self.assertEqual("INIT_FINISHED", trig["event"][0]["event_type"])

    def test_iter_ui_comp_on_childless_uid_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.action(["ITER_UI_COMP_DO", ["GET_CLIENT_ROLE"], "btn-ok-uid", []])
        self.assertIn("没有子节点", str(ctx.exception))

    def test_iter_ui_comp_on_container_uid_allowed(self):
        node = self.action(["ITER_UI_COMP_DO", ["GET_CLIENT_ROLE"], "block-uid", []])
        self.assertEqual("ITER_UI_COMP_DO", node["action_type"])

    def test_unit_type_compare_literal_override(self):
        node = gen_trigger.build_condition(
            ["UNIT_TYPE_COMPARE",
             ["GET_UNIT_TYPE", ["GET_UNIT_FROM_EVENT"]], "==", 200001],
            self.idx, self.eid)
        self.assertEqual(100116, node["args_list"][2]["arg_type"])
        self.assertEqual(100010, node["args_list"][0]["arg_type"])

    def test_arithmetic_operator_override(self):
        node = self.action(["SET_VARIABLE",
                            {"var": "金币", "type": "INTEGER", "scope": "global"},
                            ["MATH_OPERATION",
                             {"var": "金币", "type": "INTEGER", "scope": "global"}, "-", 1]])
        operator = node["args_list"][1]["args_list"][1]
        self.assertEqual(100016, operator["arg_type"])

    def test_global_unit_name_read_warns(self):
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            gen_trigger.build_variable_arg(
                {"var": "目标单位类型", "type": "UNIT_NAME", "scope": "global"}, "UNIT_NAME", self.idx)
        self.assertIn("清成 null", buf.getvalue())

    # ── 参数形状守卫：个数 ────────────────────────────────────────────────
    def test_action_too_few_positional_args_rejected(self):
        """少传位置参数 → 后面的参数整体前移，必须生成期报错。"""
        with self.assertRaises(ValueError) as ctx:
            self.action(["GET_UNIT_KEY_OF_UNIT"])
        self.assertIn("参数个数不对", str(ctx.exception))
        self.assertIn("UNIT_ENTITY", str(ctx.exception))

    def test_action_too_many_positional_args_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.action(["GET_UNIT_KEY_OF_UNIT", ["ABILITY_OWNER"], 1])
        self.assertIn("参数个数不对", str(ctx.exception))

    def test_nested_call_too_few_args_rejected(self):
        """嵌套函数调用同样要校验个数（少传即错位）。"""
        with self.assertRaises(ValueError) as ctx:
            self.action(["SET_VARIABLE",
                         {"var": "金币", "type": "INTEGER", "scope": "global"},
                         ["MATH_OPERATION", 1, "+"]])
        self.assertIn("MATH_OPERATION", str(ctx.exception))
        self.assertIn("错位", str(ctx.exception))

    def test_op_arg_dict_is_not_counted_as_positional(self):
        """动作位不支持可选参数：末尾写 {'op_arg': ...} 要给出可执行的替代写法。"""
        with self.assertRaises(ValueError) as ctx:
            self.action(["ADD_MODIFIER", ["ABILITY_OWNER"], 900001,
                         {"op_arg": [["ABILITY_OWNER"], ["CUR_ABILITY"], 3.0]}])
        msg = str(ctx.exception)
        self.assertIn("动作位不支持可选参数", msg)
        self.assertIn("SET_VARIABLE", msg)

    # ── 参数形状守卫：易错动作必须具名 ────────────────────────────────────
    def test_apply_damage_positional_rejected(self):
        """APPLY_DAMAGE 位置写法必须被拦下（第 0/2 槽都是单位，写反是静默失效）。"""
        with self.assertRaises(ValueError) as ctx:
            self.action(["APPLY_DAMAGE", ["FOR_EACH_SELECTED_UNIT"], ["CUR_ABILITY"],
                         ["ABILITY_OWNER"], 1, 200.0, False])
        msg = str(ctx.exception)
        self.assertIn("具名传参", msg)
        self.assertIn("source", msg)
        # 报错里必须带上 cont 的槽位编号（唯一一手依据）
        self.assertIn("伤害所属{#0}", msg)

    def test_apply_damage_named_builds_declared_order(self):
        """具名写法按 p 的声明顺序落 args_list：伤害所属 / 技能 / 受伤目标 / …"""
        node = self.action(["APPLY_DAMAGE", {
            "target": ["FOR_EACH_SELECTED_UNIT"],
            "value": 200.0,
            "source": ["ABILITY_OWNER"],
            "crit": False,
            "ability": ["CUR_ABILITY"],
            "damage_type": 1,
        }])
        args = node["args_list"]
        self.assertEqual("ABILITY_OWNER", args[0]["sub_type"])        # 槽 0 = 伤害所属
        self.assertEqual("CUR_ABILITY", args[1]["sub_type"])          # 槽 1 = 所属技能
        self.assertEqual("FOR_EACH_SELECTED_UNIT", args[2]["sub_type"])  # 槽 2 = 受伤目标
        self.assertEqual([200.0], args[4]["args_list"])

    def test_apply_damage_named_missing_key_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.action(["APPLY_DAMAGE", {
                "source": ["ABILITY_OWNER"], "ability": ["CUR_ABILITY"],
                "damage_type": 1, "value": 10.0, "crit": False}])   # 缺 target
        self.assertIn("缺少", str(ctx.exception))
        self.assertIn("target", str(ctx.exception))

    def test_apply_damage_named_unknown_key_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.action(["APPLY_DAMAGE", {
                "source": ["ABILITY_OWNER"], "ability": ["CUR_ABILITY"],
                "target": ["FOR_EACH_SELECTED_UNIT"], "damage_type": 1,
                "value": 10.0, "crit": False, "victim": ["CUR_UNIT"]}])
        self.assertIn("多余", str(ctx.exception))
        self.assertIn("victim", str(ctx.exception))

    def test_variable_ref_dict_not_mistaken_for_named_args(self):
        """{'var':...,'type':...} 是变量引用（不是具名参数表），且能当槽位值用。"""
        node = self.action(["APPLY_DAMAGE", {
            "source": ["ABILITY_OWNER"], "ability": ["CUR_ABILITY"],
            "target": {"var": "技能目标", "type": "UNIT_ENTITY", "scope": "global"},
            "damage_type": 1, "value": 10.0, "crit": False}])
        target = node["args_list"][2]
        self.assertEqual(100006, target["arg_type"])   # UNIT_ENTITY
        self.assertEqual(11, target["sub_type"])       # 变量引用
        self.assertIn("UNIT_ENTITY", json.dumps(target, ensure_ascii=False))
        self.assertIn("技能目标", json.dumps(target, ensure_ascii=False))

    def test_apply_damage_positional_after_unit_ref_still_rejected(self):
        """位置写法里第一个参数是变量引用时，也不能被误判成具名参数表。"""
        with self.assertRaises(ValueError) as ctx:
            self.action(["APPLY_DAMAGE",
                         {"var": "技能目标", "type": "UNIT_ENTITY", "scope": "global"},
                         ["CUR_ABILITY"], ["FOR_EACH_SELECTED_UNIT"], 1, 10.0, False])
        self.assertIn("具名传参", str(ctx.exception))


class LintGuardTest(unittest.TestCase):
    """validate 的本地 lint 必须能拦住这些写法（不必上编辑器）。"""

    def lint(self, node, anchor=None):
        errors, warnings = [], []
        eca_json_helper._lint_editor_rejected_encodings(node, "$", errors, warnings, anchor)
        return errors

    def test_set_variable_value_type_mismatch(self):
        node = {
            "action_type": "SET_VARIABLE",
            "args_list": [
                {"arg_type": 100030, "sub_type": 1,
                 "args_list": [{"__tuple__": True, "items": ["INTEGER", "金币"]}]},
                {"arg_type": 100000, "sub_type": "MATH_OPERATION", "args_list": []},
            ],
        }
        errors = self.lint(node)
        self.assertTrue(any("值参数 arg_type" in e for e in errors), errors)

    def test_math_operation_operator_id(self):
        node = {"arg_type": 100002, "sub_type": "MATH_OPERATION", "args_list": [
            {"arg_type": 100002, "sub_type": 6, "args_list": []},
            {"arg_type": 100017, "sub_type": 1, "args_list": ["+"]},
            {"arg_type": 100002, "sub_type": 1, "args_list": [1]},
        ]}
        errors = self.lint(node)
        self.assertTrue(any("ARITHMETIC_OPERATOR" in e for e in errors), errors)

    def test_unit_type_compare_literal_id(self):
        node = {
            "condition_type": "UNIT_TYPE_COMPARE",
            "args_list": [
                {"arg_type": 100010, "sub_type": "GET_UNIT_TYPE", "args_list": []},
                {"arg_type": 100035, "sub_type": 1, "args_list": ["=="]},
                {"arg_type": 100010, "sub_type": 1, "args_list": [200001]},
            ],
        }
        errors = self.lint(node)
        self.assertTrue(any("UNIT_NAME" in e for e in errors), errors)

    def test_if_nested_in_else_branch(self):
        node = {
            "action_type": "IF_THEN_ELSE",
            "args_list": [
                {"arg_type": 100021, "sub_type": 1, "args_list": []},
                {"arg_type": 100022, "sub_type": 1, "args_list": []},
                {"arg_type": 100022, "sub_type": 1, "args_list": [
                    {"action_type": "IF_THEN_ELSE", "args_list": []}]},
            ],
        }
        errors = self.lint(node)
        self.assertTrue(any("ELSE 分支" in e for e in errors), errors)

    def test_iter_ui_comp_on_childless_uid(self):
        tmp = Path(tempfile.mkdtemp())
        make_project(
            tmp,
            panels=json.dumps({
                "name": "TestPanel", "uid": "panel-uid", "type": 2,
                "children": [{"name": "btn_ok", "uid": "btn-ok-uid", "type": 1, "children": []}],
            }, ensure_ascii=False),
        )
        # 清掉按路径索引的缓存，避免与其它用例互相污染
        eca_json_helper._UI_INDEX_CACHE.clear()
        anchor = str(tmp / "maps" / MAP / "global_trigger" / "trigger" / "x.json")
        node = {"action_type": "ITER_UI_COMP_DO", "args_list": [
            {"arg_type": 100025, "sub_type": "GET_CLIENT_ROLE", "args_list": []},
            {"arg_type": 100070, "sub_type": 1, "args_list": ["btn-ok-uid"]},
            {"arg_type": 100022, "sub_type": 1, "args_list": []},
        ]}
        errors = self.lint(node, anchor)
        self.assertTrue(any("没有子节点" in e for e in errors), errors)


class SemanticGuardTest(unittest.TestCase):
    """TRIGGER_PLAYER / 位置参数超限 / 未登记参数类型 三条守卫。"""

    def setUp(self):
        self.idx = gen_trigger.load_index()
        self.tmp = Path(tempfile.mkdtemp())
        make_project(self.tmp, globals_={"UNIT_ENTITY": {"英雄": 0}})
        gen_trigger.load_global_vars(str(self.tmp), MAP)
        gen_trigger.load_ui_nodes(str(self.tmp), MAP)

    def trigger(self, spec):
        return gen_trigger.build_trigger(spec, self.idx, spec["id"])

    # --- 守卫 1：TRIGGER_PLAYER 在物编事件触发器里非法 ---
    def test_trigger_player_in_unit_event_rejected(self):
        spec = {"name": "t1", "id": 1930000101,
                "event": [["GENERIC_UNIT_EVENT", "ET_UNIT_DIE"]],
                "action": [["SET_UI_COMP_VISIBLE", ["TRIGGER_PLAYER"], True, "some-uid"]]}
        with self.assertRaises(ValueError) as ctx:
            self.trigger(spec)
        self.assertIn("TRIGGER_PLAYER", str(ctx.exception))
        self.assertIn("t_unit", str(ctx.exception))

    def test_trigger_player_in_system_event_rejected(self):
        """t_system（如 INIT_FINISHED）同样拿不到 ROLE_ID。"""
        spec = {"name": "t1b", "id": 1930000108,
                "event": [["INIT_FINISHED"]],
                "action": [["SET_UI_COMP_VISIBLE", ["TRIGGER_PLAYER"], True, "some-uid"]]}
        with self.assertRaises(ValueError) as ctx:
            self.trigger(spec)
        self.assertIn("t_system", str(ctx.exception))

    def test_trigger_player_in_player_event_allowed(self):
        spec = {"name": "t2", "id": 1930000102,
                "event": [["ANY_ROLE_JOIN_GAME"]],
                "action": [["SET_UI_COMP_VISIBLE", ["TRIGGER_PLAYER"], True, "some-uid"]]}
        node = self.trigger(spec)
        self.assertEqual("TRIGGER_PLAYER",
                         node["action"][0]["args_list"][0]["sub_type"])

    # --- 守卫 1b：包装类事件（GENERIC_UNIT_EVENT）的事件名必须是字符串 ---
    # 实测：DSL 写成数组会生成 args_list: [["ET_UNIT_DIE"]]，
    # --dry-run / import_eca / 往返 diff / audit 四道检查全过，但编辑器保存时
    # check_prefab_name 拿 list 去 set 里查成员 → TypeError: unhashable type: 'list'
    # → 整次保存失败、编辑器会话变脏。
    def test_wrapped_event_name_must_be_scalar(self):
        spec = {"name": "t2b", "id": 1930000109,
                "event": [["GENERIC_UNIT_EVENT", ["ET_UNIT_DIE"]]],
                "action": []}
        with self.assertRaises(ValueError) as ctx:
            self.trigger(spec)
        self.assertIn("字符串", str(ctx.exception))
        self.assertIn("ET_UNIT_DIE", str(ctx.exception))

    def test_wrapped_event_name_scalar_produces_flat_args_list(self):
        spec = {"name": "t2c", "id": 1930000110,
                "event": [["GENERIC_UNIT_EVENT", "ET_UNIT_DIE"]],
                "action": []}
        node = self.trigger(spec)
        arg = node["event"][0]["args_list"][0]
        self.assertEqual("GENERIC_UNIT_EVENT", arg["sub_type"])
        self.assertEqual(["ET_UNIT_DIE"], arg["args_list"])

    # --- 守卫 2：位置参数超限应报错并引导用 op_arg ---
    def test_extra_positional_args_rejected(self):
        spec = {"name": "t3", "id": 1930000103, "event": [["INIT_FINISHED"]],
                "action": [["PRINT_MESSAGE_ACTION_TO_DIALOG", 3,
                            ["STR_JOIN", "A", "B", "C"]]]}
        with self.assertRaises(ValueError) as ctx:
            self.trigger(spec)
        self.assertIn("op_arg", str(ctx.exception))
        self.assertIn("STR_JOIN", str(ctx.exception))

    def test_op_arg_literals_are_filled(self):
        """STR_JOIN 的第 3~10 段走 op_arg——编辑器接受且运行时拼接正确。"""
        spec = {"name": "t4", "id": 1930000104, "event": [["INIT_FINISHED"]],
                "action": [["PRINT_MESSAGE_ACTION_TO_DIALOG", 3,
                            ["STR_JOIN", "P1", "P2", {"op_arg": ["O1", None, "O3"]}]]]}
        node = self.trigger(spec)
        sj = node["action"][0]["args_list"][1]
        self.assertEqual("STR_JOIN", sj["sub_type"])
        self.assertEqual(2, len(sj["args_list"]))          # 位置参数仍然是 2 个
        self.assertEqual(["O1"], sj["op_arg"][0]["args_list"])
        self.assertEqual(["O3"], sj["op_arg"][2]["args_list"])
        self.assertEqual([True, False, True, False, False, False, False, False],
                         sj["op_arg_enable"])

    # --- 守卫 3：未登记的参数类型必须报错，不能静默退化成 POINT ---
    def test_typed_id_escape_hatch(self):
        """已取证的未登记类型可用 {"typed_id": N, "value": ...} 就地传入（并打告警）。"""
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            node = gen_trigger.build_arg(
                {"typed_id": 100999, "value": ["UNIT_COMMAND_ATTACK_MOVE", 10000]},
                "UNIT_COMMAND", self.idx, gen_trigger.eid_factory(1930000106))
        self.assertEqual(100999, node["arg_type"])
        self.assertEqual("UNIT_COMMAND_ATTACK_MOVE", node["sub_type"])
        self.assertIn("typed_id", buf.getvalue())

    def test_unregistered_param_type_rejected(self):
        # 未登记的类型必须报错而不是静默退化成 100004(POINT)。
        # 注意：UNIT_COMMAND 曾长期未登记，后由 sync_from_source.py 从源码补上，
        # 所以这里改用真正不存在的类型名来验证守卫本身。
        with self.assertRaises(ValueError) as ctx:
            gen_trigger.arg_type_id_for("NOT_A_REAL_ARG_TYPE_XYZ")
        self.assertIn("未登记", str(ctx.exception))

    # --- 源码派生数据（eca_source_data.json）---
    _HAS_SOURCE = bool(gen_trigger.load_source_data())

    @unittest.skipUnless(_HAS_SOURCE, "需要先运行 sync_from_source.py 生成 eca_source_data.json")
    def test_source_derived_ids_loaded(self):
        """源码派生表应补上手写表里长期缺失/写错的类型。"""
        self.assertEqual(100037, gen_trigger.ARG_TYPE_ID["ROLE_RES_KEY"])
        self.assertEqual(100216, gen_trigger.ARG_TYPE_ID["UNIT_COMMAND"])
        self.assertEqual(101001, gen_trigger.ARG_TYPE_ID["UNIT_GROUP_COMMAND"])
        self.assertEqual(100332, gen_trigger.ARG_TYPE_ID["MOVE_DIRECTION"])
        # 这两个是手写表猜错、由源码纠正的典型；END_GAME_FOR_ROLE 曾因此被清成 null
        self.assertEqual(100047, gen_trigger.ARG_TYPE_ID["WIN_OR_LOSE"])
        self.assertEqual(100048, gen_trigger.ARG_TYPE_ID["ON_OR_OFF"])

    @unittest.skipUnless(_HAS_SOURCE, "需要先运行 sync_from_source.py")
    def test_source_derived_variable_subtype(self):
        """变量读取 sub_type 由各类型自己声明的 VARIABLE 取值派生。"""
        self.assertEqual(6, gen_trigger.VARIABLE_READ_SUBTYPE["INTEGER"])
        self.assertEqual(19, gen_trigger.VARIABLE_READ_SUBTYPE["POINT"])
        # 全局变量口径由实测覆盖，仍需是 "VARIABLE"
        self.assertEqual("VARIABLE", gen_trigger.GLOBAL_VARIABLE_READ_SUBTYPE["BOOLEAN"])

    @unittest.skipUnless(_HAS_SOURCE, "需要先运行 sync_from_source.py")
    def test_sub_type_mismatch_warns_not_raises(self):
        """sub_type 偏离声明表时只告警（静态表天生不含运行时注册的 KV 系列，不能阻断）。"""
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            node = gen_trigger.build_arg(
                ["LAST_CREATE_UNIT"], "POINT", self.idx,
                gen_trigger.eid_factory(1930000107))
        self.assertEqual("LAST_CREATE_UNIT", node["sub_type"])
        self.assertIn("不在类型 POINT", buf.getvalue())

    @unittest.skipUnless(_HAS_SOURCE, "需要先运行 sync_from_source.py")
    def test_hand_table_has_no_conflict_with_source(self):
        """手写表不得与源码派生值冲突——防止再次写入拍脑袋的「共享 ID」猜测。

        背景：首次从源码派生时发现手写表有 29 处错值（如 WIN_OR_LOSE 猜成
        STRING 的 100003，实际 100047），正是 END_GAME_FOR_ROLE 被清成 null 的根因。
        """
        generated = gen_trigger.load_source_data().get("arg_type_ids") or {}
        conflicts = {n: (h, generated[n]) for n, h in gen_trigger._HAND_ARG_TYPE_ID.items()
                     if n in generated and generated[n] != h}
        self.assertEqual({}, conflicts, "手写表与源码冲突：%s" % conflicts)

    def test_fallback_table_ids_correct_without_source_data(self):
        """分发包若缺少 eca_source_data.json，回退手写表的取值也必须是对的。

        （使用者拿不到编辑器源码，不能假设派生数据一定存在。）
        """
        saved = gen_trigger._SOURCE_DATA
        gen_trigger._SOURCE_DATA = {}
        try:
            merged, _ = gen_trigger._build_arg_type_id()
        finally:
            gen_trigger._SOURCE_DATA = saved
        self.assertEqual(100047, merged.get("WIN_OR_LOSE"))
        self.assertEqual(100048, merged.get("ON_OR_OFF"))
        self.assertEqual(100037, merged.get("ROLE_RES_KEY"))
        self.assertEqual(100031, merged.get("ITEM_ENTITY"))
        self.assertEqual(100027, merged.get("PLAYER_GROUP"))

    @unittest.skipUnless(_HAS_SOURCE, "需要先运行 sync_from_source.py")
    def test_shipped_source_data_leaks_no_paths(self):
        """分发数据会随 skill 发给外部用户，禁止出现引擎源码路径或内部目录结构。

        早期产物含 `engine_root` 绝对路径与 `files` 清单（暴露引擎目录树），
        已改为只保留 sha256 + 计数；`--include-source-paths` 仅供维护者本地排查。
        """
        raw = (SKILL_DIR / "eca_source_data.json").read_text(encoding="utf-8")
        for leaked in ("I:/", "I:\\", "src/Server", "black_box", "commons/",
                       "game_trigger/", "/map/"):
            self.assertNotIn(leaked, raw, "分发数据泄漏了源码路径信息：%s" % leaked)


if __name__ == "__main__":
    unittest.main()
