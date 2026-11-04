# -*- coding: utf-8 -*-
"""一条命令跑完「写法验证」闭环：lint → 快照 → import_eca → 保存×2 → 回读 → diff → valid。

把实战中手工做的 5 步固定成脚本：
  1. 本地 lint（`eca_json_helper._lint_editor_rejected_encodings`）先拦已知坏写法
  2. `y3editor.save_editor` 先落盘编辑器当前修改
  3. `y3editor.import_eca` 导入待验证触发器
  4. 等 3 秒 → `save_editor`；再等 2 秒 → `save_editor`（valid 需要第二次保存才稳定）
  5. 回读磁盘文件与生成快照比对（忽略 element_id / local_var / valid），并读 valid 标记

用法：
  py -3 verify_trigger.py <触发器名 或 json 路径> [--map EntryMap] [--root <工程根>] [--json]
  py -3 verify_trigger.py --all                    # 批量回归：该地图 trigger 目录下全部触发器

退出码：0 = 通过；1 = 有被改写/清空或 valid=false；2 = 环境/MCP 失败。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if SKILL_DIR not in sys.path:
    sys.path.insert(0, SKILL_DIR)

import eca_json_helper  # noqa: E402
import mcp_client  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# 编辑器自动补/改、不算「被改写」的差异
_BENIGN = (".valid", "local_var")


def resolve_trigger_path(name_or_path, map_name, root):
    if os.path.isfile(name_or_path):
        return os.path.abspath(name_or_path)
    stem = name_or_path if name_or_path.endswith(".json") else name_or_path + ".json"
    return os.path.join(root, "maps", map_name, "global_trigger", "trigger", stem)


def diff_snapshots(expected_path, actual_path):
    """生成快照 vs 编辑器回读，过滤掉编辑器自动补的无害差异。"""
    with open(expected_path, "r", encoding="utf-8") as f:
        expected = json.load(f)
    with open(actual_path, "r", encoding="utf-8") as f:
        actual = json.load(f)
    raw = []
    eca_json_helper._diff_nodes(
        eca_json_helper._strip_eids(expected),
        eca_json_helper._strip_eids(actual), "$", raw)
    return [item for item in raw if not any(tag in item for tag in _BENIGN)]


def verify_one(path, root, *, do_lint=True, sleep_after_import=3.0):
    """对一个触发器跑完整闭环，返回结构化报告。"""
    name = os.path.splitext(os.path.basename(path))[0]
    report = {"trigger": name, "path": path, "lint_errors": [], "lint_warnings": [],
              "import": None, "diff": [], "valid": None, "ok": False, "error": None}
    if not os.path.isfile(path):
        report["error"] = "触发器文件不存在"
        return report

    if do_lint:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        errors, warnings = [], []
        eca_json_helper._lint_editor_rejected_encodings(data, "$", errors, warnings, path)
        report["lint_errors"], report["lint_warnings"] = errors, warnings
        if errors:
            return report

    snap_dir = tempfile.mkdtemp(prefix="eca_verify_")
    snap = os.path.join(snap_dir, name + ".json")
    shutil.copyfile(path, snap)
    try:
        # 首次导入会先 save_editor；而保存以编辑器内存为准，会把「未 import 过」的文件从磁盘裁掉
        # （实测）。这种情况下 import 会直接报「文件不存在」，属于预期路径，
        # 不该当作致命错误——用快照还原文件后再导一次。
        first_import_error = None
        try:
            report["import"] = import_trigger(path, root)
        except Exception as exc:  # noqa: BLE001
            first_import_error = exc
        if not os.path.isfile(path):
            shutil.copyfile(snap, path)
            report["restored_after_prune"] = True
            report["import"] = import_trigger(path, root, flush_first=False)
        elif first_import_error is not None:
            raise first_import_error
        flush(root, sleep_after_import=sleep_after_import)
    except Exception as exc:  # noqa: BLE001
        report["error"] = "%s: %s" % (type(exc).__name__, exc)
        shutil.rmtree(snap_dir, ignore_errors=True)
        return report

    report.update(inspect(snap, path))
    shutil.rmtree(snap_dir, ignore_errors=True)
    return report


def open_editor(root):
    """打开编辑器 MCP 连接。"""
    return mcp_client.editor_client(root)


def call_editor(tool, arguments=None, root=None, *, expect_json=True):
    """调用编辑器 MCP 工具。

    ⚠️ 每次调用都开一个**新的 MCP 会话**：实测在同一会话里连续多次 tools/call 时，
    第二次起的 `import_eca` 会返回成功但编辑器不采纳（保存时该触发器被当成未知文件裁剪掉）。
    分开会话与手工验证流程一致，行为稳定。
    """
    client = mcp_client.editor_client(root or mcp_client.find_project_root())
    text, payload = client.call(tool, arguments)
    if expect_json and payload is None:
        raise RuntimeError(
            "编辑器 MCP 工具 %s 未返回 JSON（原始返回：%s）。"
            "常见原因：save_editor 刚结束、编辑器仍在写文件，紧接着的 import 会被丢弃。"
            "解决：保存后等 1~3 秒再导入。" % (tool, (text or "")[:200]))
    return text, payload


def import_trigger(path, root, *, flush_first=True):
    """导入单个触发器；flush_first 时先 save_editor 落盘编辑器当前修改。"""
    if flush_first:
        # save_editor 正常返回纯文本（「已尝试保存编辑器。」），不要求 JSON
        call_editor("save_editor", root=root, expect_json=False)
        # 保存是异步落盘：紧接着 import 有概率被编辑器丢弃（实测）→ 留一拍
        time.sleep(1.5)
    _, payload = call_editor("import_eca", {"trigger_json_path": path}, root)
    if not isinstance(payload, dict) or not payload.get("success"):
        raise RuntimeError("import_eca 未返回 success：%s（文件：%s）" % (payload, path))
    return payload


def flush(root, *, sleep_after_import=3.0):
    """导入后固定动作：等 3 秒 → 保存 → 等 2 秒 → 再保存（valid 需要第二次保存才稳定）。"""
    time.sleep(sleep_after_import)
    call_editor("save_editor", root=root, expect_json=False)
    time.sleep(2)
    call_editor("save_editor", root=root, expect_json=False)


def snapshot(path):
    """把当前生成结果存一份快照，返回 (快照目录, 快照文件)。"""
    snap_dir = tempfile.mkdtemp(prefix="eca_verify_")
    snap = os.path.join(snap_dir, os.path.basename(path))
    shutil.copyfile(path, snap)
    return snap_dir, snap


def inspect(snap, path):
    """回读磁盘文件，返回 {diff, valid, ok}。"""
    if not os.path.isfile(path):
        # 编辑器保存时会以内存为准裁剪磁盘上未 import 的触发器（实测）
        return {"diff": ["文件已被编辑器保存流程裁剪（未 import 到编辑器）"], "valid": None, "ok": False}
    diff = diff_snapshots(snap, path)
    with open(path, "r", encoding="utf-8") as f:
        valid = bool(json.load(f).get("valid"))
    # 全局变量存活检查：save_editor 以编辑器内存为准写回 globaltriggervariable.json，
    # 尚未被编辑器加载的新变量会被裁剪；此时触发器里的引用会被标红「无效的变量」。
    # 证据：声明多个变量后未重启编辑器就保存，变量全部消失。
    missing = missing_global_vars(path, snap)
    if missing:
        diff = list(diff) + [
            "引用的全局变量在保存后不见了：%s（编辑器会把这些引用标红为「无效的变量」；"
            "正确顺序：save_editor → var_manager add → restart_editor(save_before_restart=false) → 再导入触发器）"
            % ", ".join(missing)
        ]
    return {"diff": diff, "valid": valid, "ok": (not diff) and valid}


def _collect_global_var_names(node, out):
    """收集生成快照里引用的全局变量名。

    变量引用是 tuple：局部为 3 元组 ["TYPE","name","local"]，全局为 2 元组 ["TYPE","name"]。
    """
    if isinstance(node, dict):
        items = node.get("items")
        # 只认「两项都是字符串」的 2 元组（["TYPE","name"]）。
        # 注意 `local_var` 也是 2 元组但内容是 [{},{}]，不加这个判断会误报出 "{}"。
        if (node.get("__tuple__") and isinstance(items, list) and len(items) == 2
                and isinstance(items[0], str) and isinstance(items[1], str)):
            out.add(items[1])
        for v in node.values():
            _collect_global_var_names(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_global_var_names(v, out)


def missing_global_vars(actual_path, snap_path):
    """返回「触发器引用了、但当前 globaltriggervariable.json 里已不存在」的变量名。"""
    try:
        with open(snap_path, "r", encoding="utf-8") as f:
            referenced = set()
            _collect_global_var_names(json.load(f), referenced)
    except (OSError, ValueError):
        return []
    if not referenced:
        return []
    var_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(actual_path))),
                            "globaltriggervariable.json")
    if not os.path.isfile(var_file):
        return []
    try:
        with open(var_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    declared = set()
    for names in (data.get("variable_dict") or {}).values():
        declared.update(str(n) for n in (names or {}))
    # 工程自带变量（UI_Manager 等）与自定义事件等也走 2 元组，但不会出现在变量表里；
    # 只报「像变量名一样、且声明表里完全没有」的项，避免误伤。
    return sorted(n for n in referenced if n and n not in declared and not n.startswith("$"))


def emit(report, as_json):
    if as_json:
        print(json.dumps(report, ensure_ascii=False))
        return
    print("=== verify_trigger: %s ===" % report["trigger"])
    if report["error"]:
        print("  [error] %s" % report["error"])
    imported = report.get("import") or {}
    if imported:
        print("  import_eca: mode=%s trigger_id=%s hotfix_status=%s" % (
            imported.get("mode"), imported.get("trigger_id"), imported.get("hotfix_status")))
    for warn in report["lint_warnings"]:
        print("  [WARN] %s" % warn)
    for err in report["lint_errors"]:
        print("  [lint] %s" % err)
    for item in report["diff"]:
        print("  [diff] %s" % item)
    print("  valid=%s" % report["valid"])
    print("  通过：写法被编辑器接受、valid=true、无参数被清空" if report["ok"]
          else "  未通过：见上方明细")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", help="触发器名（不含 .json 也可）或 json 路径")
    parser.add_argument("--all", action="store_true",
                        help="批量验证该地图 trigger 目录下所有触发器（回归基线）")
    parser.add_argument("--map", default="EntryMap")
    parser.add_argument("--root", default=None)
    parser.add_argument("--no-lint", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root) if args.root else mcp_client.find_project_root()
    if not root:
        print("找不到工程根目录，请用 --root 指定", file=sys.stderr)
        return 2

    if args.all:
        trig_dir = os.path.join(root, "maps", args.map, "global_trigger", "trigger")
        if not os.path.isdir(trig_dir):
            print("触发器目录不存在：%s" % trig_dir, file=sys.stderr)
            return 2
        names = sorted(f for f in os.listdir(trig_dir)
                       if f.endswith(".json") and f != "New trigger.json")
        reports = []
        for fname in names:
            report = verify_one(os.path.join(trig_dir, fname), root, do_lint=not args.no_lint)
            emit(report, args.json)
            reports.append(report)
        failed = [r["trigger"] for r in reports if not r["ok"]]
        print("\n==== 批量验证：%d 个触发器，%d 个通过 ====" % (len(reports), len(reports) - len(failed)))
        if failed:
            print("未通过：%s" % "、".join(failed))
            return 1
        return 0

    if not args.target:
        print("请给出触发器名/路径，或用 --all 批量验证", file=sys.stderr)
        return 2
    path = resolve_trigger_path(args.target, args.map, root)
    report = verify_one(path, root, do_lint=not args.no_lint)
    emit(report, args.json)
    if report["error"] and "不存在" in str(report["error"]):
        return 2
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
