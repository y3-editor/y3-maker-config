# -*- coding: utf-8 -*-
"""触发器静态审计：ID 唯一性 / valid / 子触发器注册 / 全局变量引用 / element_id 规则。

补在 `validate`（结构）、`scan`（索引+lint）、`diff`（往返保真）之后的第四道静态关：
前三道都过了，仍然可能因为 **ID 重复、valid=false、子触发器没被裸整数注册、
引用了未声明变量、变量 tuple 写成 3 元组** 而静默失效 —— 这些只有本脚本查。

用法：
  py -3 audit_triggers.py                                  # 默认 maps/EntryMap
  py -3 audit_triggers.py --map-dir maps/OtherMap
  py -3 audit_triggers.py --map-dir maps/EntryMap --root <工程根>

退出码：0 = 全通过，1 = 发现问题（问题会逐条列出）。
详见 skills/eca-json-builder/runtime_pitfalls.md。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def walk_nodes(node, path, out):
    """收集所有 dict 节点；顶层触发器的 sub_trigger 交给调用方单独遍历，避免重复计数。"""
    if isinstance(node, dict):
        out.append((path, node))
        for k, v in node.items():
            if k == "sub_trigger" and path == "":
                continue
            walk_nodes(v, path + "." + str(k), out)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_nodes(v, path + "[%d]" % i, out)


def collect_registered_ids(value, out):
    """收集父触发器 action 里的裸整数（= 子触发器注册 ID）。"""
    if isinstance(value, list):
        for x in value:
            if isinstance(x, int) and not isinstance(x, bool):
                out.add(x)
            else:
                collect_registered_ids(x, out)
    elif isinstance(value, dict):
        for x in value.values():
            collect_registered_ids(x, out)


# 单条父触发器可安全注册的子触发器条数上限（与 gen_trigger.py 保持一致；实测经验值）
MAX_SUB_TRIGGERS_PER_PARENT = 6

OBJECT_CONTAINER_DIRS = ("ability", "unit", "item", "modifier", "projectile")

KNOWN_VAR_TYPES = {
    "INTEGER", "FLOAT", "STRING", "BOOLEAN", "UNIT_ENTITY", "UNIT_GROUP",
    "PLAYER", "PLAYER_GROUP", "POINT", "RECTANGLE", "TABLE", "NEW_TIMER",
    "MODIFIER_ENTITY", "ITEM_ENTITY", "ABILITY", "SFX_ENTITY", "UNIT_NAME",
    "ANGLE", "PROJECTILE_ENTITY", "DESTRUCTIBLE_ENTITY", "LOCAL_UNIT_GROUP",
    "ROUND_AREA", "POLYGON", "CURVED_PATH", "ITEM_NAME", "ABILITY_NAME",
}


def looks_like_uid(s):
    """UI 控件 uid 形如 8-4-4-4-12 的 UUID 字符串。"""
    return isinstance(s, str) and len(s) == 36 and s.count("-") == 4


def collect_ui_uids(ui_dir):
    """收集画板 / 元件 JSON 里出现过的所有控件 uid，用于校验触发器引用是否还存在。"""
    out = set()
    if not os.path.isdir(ui_dir):
        return out
    for dp, _dn, fn in os.walk(ui_dir):
        for f in fn:
            if not f.endswith(".json"):
                continue
            try:
                with open(os.path.join(dp, f), "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception:
                continue
            stack = [data]
            while stack:
                n = stack.pop()
                if isinstance(n, dict):
                    u = n.get("uid")
                    if isinstance(u, str):
                        out.add(u)
                    stack.extend(n.values())
                elif isinstance(n, list):
                    stack.extend(n)
    return out


def audit_object_containers(map_dir, declared_global, seen_trigger_ids,
                           seen_element_ids, ui_uids, problems):
    """审计物编触发器容器：技能/单位/物品/魔法效果/投射物。

    这些文件没有 `import_eca` 热更通道，改完必须重启编辑器；也最容易出现
    `valid=false` 却没人发现。此处至少覆盖：ID 唯一、valid/enabled、
    局部变量声明、全局变量引用、UI uid、element_id 前缀。
    """
    total = 0
    for container in OBJECT_CONTAINER_DIRS:
        folder = os.path.join(map_dir, container)
        if not os.path.isdir(folder):
            continue
        files = sorted(glob.glob(os.path.join(folder, "*.json")))
        if not files:
            continue
        container_count = 0
        for path in files:
            fname = os.path.basename(path)
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError) as exc:
                problems.append("%s/%s 读取失败：%s" % (container, fname, exc))
                continue
            trigger_dict = data.get("trigger_dict") or {}
            if not trigger_dict:
                continue

            local_declared = set()
            for group in (data.get("variable_dict") or {}).values():
                if isinstance(group, dict):
                    local_declared.update(group.keys())

            for tid, trig in trigger_dict.items():
                if not isinstance(trig, dict):
                    continue
                total += 1
                container_count += 1
                where = "%s/%s trigger=%s" % (container, fname, tid)
                if str(trig.get("trigger_id")) != str(tid):
                    problems.append("trigger_dict 键与 trigger_id 不一致：%s（%r != %r）"
                                    % (where, tid, trig.get("trigger_id")))
                if trig.get("valid") is not True:
                    problems.append("valid != true：%s -> %r" % (where, trig.get("valid")))
                if trig.get("enabled") is not True:
                    problems.append("enabled != true：%s -> %r" % (where, trig.get("enabled")))

                if tid in seen_trigger_ids:
                    problems.append("trigger_id 重复：%s 与 %s" % (where, seen_trigger_ids[tid]))
                else:
                    seen_trigger_ids[tid] = where

                var_data = trig.get("var_data") or []
                if len(var_data) >= 2 and isinstance(var_data[1], dict):
                    local_declared.update(var_data[1].keys())
                local_block = (data.get("local_variable") or {}).get(str(tid)) or {}
                for group in (local_block.get("variable_dict") or {}).values():
                    if isinstance(group, dict):
                        local_declared.update(group.keys())

                nodes = []
                walk_nodes(trig, "", nodes)
                for npath, node in nodes:
                    if node.get("arg_type") == 100070:  # UI_COMP
                        for a in node.get("args_list") or []:
                            if looks_like_uid(a):
                                ui_uids.add(a)
                    if node.get("__tuple__") is True and isinstance(node.get("items"), list):
                        items = node["items"]
                        if len(items) == 3 and items[2] == "local":
                            if items[1] not in local_declared:
                                problems.append("引用了未声明的局部变量：%s%s = %r"
                                                % (where, npath, items))
                        elif (len(items) == 2 and isinstance(items[0], str)
                              and items[0] in KNOWN_VAR_TYPES):
                            if items[1] not in declared_global:
                                problems.append("引用了未声明的全局变量：%s%s = %r"
                                                % (where, npath, items))
                    eid = node.get("element_id")
                    if eid is None:
                        continue
                    if eid in seen_element_ids:
                        problems.append("element_id 重复：%s%s = %s（另见 %s）"
                                        % (where, npath, eid, seen_element_ids[eid]))
                    else:
                        seen_element_ids[eid] = where + npath
                    if not str(eid).startswith(str(trig.get("trigger_id"))):
                        problems.append("element_id 前缀不等于 trigger_id：%s%s = %s"
                                        % (where, npath, eid))
        print("  - %s：%d 个触发器" % (container, container_count))
    return total


def collect_type_field_sets(paths):
    """按 事件 / 条件 / 动作 类型收集字段集合（用于和编辑器自己的产物对帐）。

    「编辑器自己写出的触发器」是我们能拿到的最权威样本：**它们带什么字段，我们的产物就该带什么**。
    实测教训：定时器动作 `RUN_*TIMER*` 缺 `local_var` 就是这样发现的
    （编辑器写出的定时器动作 100% 带该字段，缺了会静默失效）。
    """
    events, conds, actions = {}, {}, {}
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        stack = [data]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                for key, bucket in (("event_type", events),
                                    ("condition_type", conds),
                                    ("action_type", actions)):
                    t = n.get(key)
                    if isinstance(t, str):
                        bucket.setdefault(t, set()).update(n.keys())
                stack.extend(n.values())
            elif isinstance(n, list):
                stack.extend(n)
    return events, conds, actions


def check_node_fields(paths, official, problems):
    """**逐节点**比对：生成产物里每个 事件/条件/动作 节点，字段必须覆盖编辑器会写的字段。

    ⚠️ 必须逐节点做，不能按类型取并集：同一类型在别的文件 / 别的节点上带了该字段，
    会把漏字段的那个节点掩盖掉（实测：抽掉某一个节点的 `local_var`，并集写法查不出来）。
    只对"官方样本里出现过的类型"成立；官方没有样本的类型不做判断（由调用方提示）。
    """
    off_e, off_c, off_a = collect_type_field_sets(official)
    hits = 0
    for p in paths:
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        nodes = []
        walk_nodes(data, "", nodes)
        for npath, n in nodes:
            for label, key, bucket in (("事件", "event_type", off_e),
                                       ("条件", "condition_type", off_c),
                                       ("动作", "action_type", off_a)):
                t = n.get(key)
                if isinstance(t, str) and t in bucket:
                    missing = sorted(bucket[t] - set(n.keys()))
                    if missing:
                        hits += 1
                        problems.append(
                            "%s%s 的 %s节点 '%s' 缺少编辑器会写的字段 %s —— 风险：静默失效 / "
                            "保存时被清空；请对照官方样本（global_trigger/trigger/UI、"
                            "global_trigger/function/）补齐字段或改用其它写法"
                            % (os.path.basename(p), npath, label, t, missing))
    return hits


def main():
    ap = argparse.ArgumentParser(description="ECA 触发器静态审计")
    ap.add_argument("--map-dir", default=os.path.join("maps", "EntryMap"),
                    help="地图目录，默认 maps/EntryMap")
    ap.add_argument("--root", default=None, help="工程根（默认自动探测，含 maps/ 的最近祖先）")
    ap.add_argument("--skip-objects", action="store_true",
                    help="跳过 ability/unit/item/modifier/projectile 物编触发器审计")
    args = ap.parse_args()

    root = args.root
    if root is None:
        cur = os.path.abspath(os.getcwd())
        for _ in range(8):
            if os.path.isdir(os.path.join(cur, "maps")):
                root = cur
                break
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
        root = root or os.getcwd()

    map_dir = args.map_dir if os.path.isabs(args.map_dir) else os.path.join(root, args.map_dir)
    trig_dir = os.path.join(map_dir, "global_trigger", "trigger")
    var_file = os.path.join(map_dir, "globaltriggervariable.json")

    if not os.path.isdir(trig_dir):
        print(f"[!] 找不到触发器目录: {trig_dir}")
        return 1
    if not os.path.isfile(var_file):
        print(f"[!] 找不到全局变量文件: {var_file}")
        return 1

    problems = []
    seen_trigger_ids = {}
    seen_element_ids = {}
    var_refs = set()
    ui_uids = set()

    with open(var_file, "r", encoding="utf-8") as f:
        gv = json.load(f)
    declared = set()
    for _vtype, group in (gv.get("variable_dict") or {}).items():
        declared.update(group.keys())

    files = sorted(glob.glob(os.path.join(trig_dir, "*.json")))
    print(f"地图目录: {os.path.relpath(map_dir, root)}")
    print(f"触发器件数：{len(files)}")
    for path in files:
        name = os.path.basename(path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries = [("(顶层)", data)]
        for key, sub in (data.get("sub_trigger") or {}).items():
            entries.append(("sub[%s]" % key, sub))

        for label, trig in entries:
            where = "%s %s" % (name, label)
            tid = trig.get("trigger_id")
            if tid in seen_trigger_ids:
                problems.append("trigger_id 重复：%s 与 %s" % (where, seen_trigger_ids[tid]))
            else:
                seen_trigger_ids[tid] = where

            if label == "(顶层)":
                if trig.get("valid") is not True:
                    problems.append("valid != true：%s -> %r" % (where, trig.get("valid")))
                if trig.get("enabled") is not True:
                    problems.append("enabled != true：%s -> %r" % (where, trig.get("enabled")))
            else:
                if trig.get("is_conf") is not True:
                    problems.append("子触发器 is_conf != true：%s" % where)
                if trig.get("p_trigger_id") != data.get("trigger_id"):
                    problems.append("子触发器 p_trigger_id 不指向父触发：%s" % where)
                if trig.get("enabled") is not False:
                    problems.append("子触发器 enabled 应为 false：%s -> %r" % (where, trig.get("enabled")))

            nodes = []
            walk_nodes(trig, "", nodes)
            for npath, node in nodes:
                # 顺手收集引用的 UI 控件 uid，循环结束后统一校验是否还存在于画板 JSON
                if node.get("arg_type") == 100070:  # UI_COMP
                    for a in node.get("args_list") or []:
                        if looks_like_uid(a):
                            ui_uids.add(a)
                if node.get("__tuple__") is True and isinstance(node.get("items"), list):
                    items = node["items"]
                    if len(items) == 2 and isinstance(items[0], str) and isinstance(items[1], str):
                        var_refs.add(items[1])
                    if len(items) == 3 and items[2] == "global":
                        problems.append("全局变量写成 3 元组（会被判无效）：%s%s = %r"
                                        % (where, npath, items))
                eid = node.get("element_id")
                if eid is None:
                    continue
                if eid in seen_element_ids:
                    problems.append("element_id 重复：%s%s = %s（另见 %s）"
                                    % (where, npath, eid, seen_element_ids[eid]))
                else:
                    seen_element_ids[eid] = where + npath
                if not str(eid).startswith(str(tid)):
                    problems.append("element_id 前缀不等于 trigger_id：%s%s = %s（trigger_id=%s）"
                                    % (where, npath, eid, tid))

        sub_ids = set()
        for key in (data.get("sub_trigger") or {}):
            try:
                sub_ids.add(int(key))
            except (TypeError, ValueError):
                pass
        if sub_ids:
            registered = set()
            collect_registered_ids(data.get("action"), registered)
            missing = sub_ids - registered
            if missing:
                problems.append("%s：子触发器 %s 未被父触发 action 注册（裸整数）" % (name, sorted(missing)))
            else:
                print("  - %s：%d 个子触发器，均已用裸整数注册 ✓" % (name, len(sub_ids)))
            if len(sub_ids) > MAX_SUB_TRIGGERS_PER_PARENT:
                print("    ⚠️ 注册了 %d 条（> %d）：实测注册项多了以后**排在后面的子触发器收不到"
                      "控件事件**（10 条时后 3 条全哑）。建议按画板 / 功能拆成多条父触发器，"
                      "或把关键子触发器放在注册列表前面。" % (len(sub_ids), MAX_SUB_TRIGGERS_PER_PARENT))

    if not args.skip_objects:
        print()
        print("物编触发器：")
        object_total = audit_object_containers(
            map_dir, declared, seen_trigger_ids, seen_element_ids, ui_uids, problems)
        if object_total == 0:
            print("  （没有物编触发器容器）")

    print()
    missing_vars = sorted(v for v in var_refs if v not in declared)
    print("引用到的变量名：%s" % sorted(var_refs))
    if missing_vars:
        problems.append("引用了未声明的变量：%s" % missing_vars)
    else:
        print("变量引用全部已在 globaltriggervariable.json 声明 ✓")

    print()
    # 字段集合对帐：与「编辑器自己写出的触发器」对比（官方 UI / 插件函数目录）
    official = []
    for d in (os.path.join(trig_dir, "UI"),
              os.path.join(map_dir, "global_trigger", "function")):
        if os.path.isdir(d):
            official += glob.glob(os.path.join(d, "**", "*.json"), recursive=True)
    if official:
        off_e, off_c, off_a = collect_type_field_sets(official)
        hits = check_node_fields(files, official, problems)
        _my_e, _my_c, my_a = collect_type_field_sets(files)
        if not hits:
            print("字段集合与编辑器自己的触发器一致（逐节点：事件 / 条件 / 动作）✓")
        no_sample = sorted(set(my_a) - set(off_a))
        if no_sample:
            print("  ℹ️ 以下动作类型**官方样本里没有**，字段集合无法对帐（需靠 ③④ 探针/观察兜底）：%s"
                  % no_sample)
        print()
    board_uids = collect_ui_uids(os.path.join(map_dir, "ui"))
    if ui_uids and board_uids:
        missing_uids = sorted(u for u in ui_uids if u not in board_uids)
        if missing_uids:
            problems.append(
                "触发器引用了画板里不存在的控件 uid（%d 个）——通常是画板重新生成后"
                "没重新解析 uid / 没重新导入引用它的触发器：%s"
                % (len(missing_uids), ", ".join(u[:8] for u in missing_uids[:5])))
    if problems:
        print("发现 %d 个问题：" % len(problems))
        for p in problems:
            print("  [!] " + p)
        return 1
    print("审查通过：ID 唯一 / valid=true / 子触发器结构正确 / 变量引用合法 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
