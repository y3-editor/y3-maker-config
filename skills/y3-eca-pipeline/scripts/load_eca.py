# -*- coding: utf-8 -*-
"""ECA 全局触发器批量加载：生成 - 串行 import - 等 3 秒 - 保存 - 逐个回读对拍。

为什么需要它（两个实测踩过的坑）：
1. save_editor 以编辑器内存为准写回。磁盘上存在但没 import_eca 过的触发器文件会被删除、
   index.txt 条目也会被移除。所以顺序必须是「先导入、后保存」；反过来会直接丢文件。
2. import_eca 只能串行，且两次之间要留时间；批量并发会出现「返回成功但没进去」。

用法：
  py -3 load_eca.py                      # 导入 global_trigger/trigger/*.json（跳过 New trigger.json）
  py -3 load_eca.py --dsl <DSL.json>     # 先按 DSL 重新生成，再导入
  py -3 load_eca.py --only a.json,b.json
  py -3 load_eca.py --dry-run

退出码：0 全部通过；1 有导入失败 / valid 不为 true / 回读对拍不一致。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", "eca-json-builder"))
sys.path.insert(0, BUILDER_DIR)

from mcp_client import editor_client  # noqa: E402


def find_root(start=None):
    cur = os.path.abspath(start or os.getcwd())
    for _ in range(8):
        if os.path.isdir(os.path.join(cur, "maps")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return os.path.abspath(start or os.getcwd())


def trigger_dir(root, map_name):
    return os.path.join(root, "maps", map_name, "global_trigger", "trigger")


def regenerate(dsl_path, map_name, root):
    # gen_trigger.py 的地图名来自 DSL 的 "map" 字段；它不接受 --map。
    # 旧实现把 --map 传过去会直接 ArgumentParser 报错，导致 --dsl 分支不可用。
    cmd = [sys.executable, os.path.join(BUILDER_DIR, "gen_trigger.py"), dsl_path,
           "--root", root]
    print("[gen] 按 DSL 重新生成 ...")
    p = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    for line in (p.stdout or "").splitlines():
        if line.startswith("OK ["):
            print("   " + line)
    if p.returncode != 0:
        print(p.stdout or "")
        print(p.stderr or "")
        raise SystemExit("[!] 生成失败，已中止（不要在此状态下保存）")


def diff_ok(generated_copy, current):
    cmd = [sys.executable, os.path.join(BUILDER_DIR, "eca_json_helper.py"),
           "diff", generated_copy, current]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = ((p.stdout or "") + (p.stderr or "")).strip()
    return out.startswith("OK"), (out.splitlines()[0] if out else "(无输出)")


def main():
    ap = argparse.ArgumentParser(description="ECA 全局触发器批量加载（正确顺序 + 回读对拍）")
    ap.add_argument("--map", dest="map_name", default="EntryMap")
    ap.add_argument("--root", default=None)
    ap.add_argument("--dsl", default=None, help="先按该 DSL 重新生成（gen_trigger.py）")
    ap.add_argument("--only", default=None, help="只导入这些文件名（逗号分隔）")
    ap.add_argument("--wait", type=float, default=3.0, help="导入与保存之间的等待秒数")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = find_root(args.root)
    tdir = trigger_dir(root, args.map_name)
    if not os.path.isdir(tdir):
        raise SystemExit("[!] 找不到触发器目录：%s" % tdir)

    if args.dsl and not args.dry_run:
        regenerate(args.dsl, args.map_name, root)

    files = [f for f in sorted(glob.glob(os.path.join(tdir, "*.json")))
             if os.path.basename(f) != "New trigger.json"]
    if args.only:
        want = {x.strip() for x in args.only.split(",") if x.strip()}
        files = [f for f in files if os.path.basename(f) in want]
    if not files:
        raise SystemExit("[!] 没有要导入的触发器文件")

    print("工程根: %s" % root)
    print("触发器目录: %s（%d 个文件）" % (os.path.relpath(tdir, root), len(files)))
    for f in files:
        print("  - " + os.path.basename(f))
    if args.dry_run:
        print("\n(--dry-run) 顺序：串行 import_eca -> 等 %ss -> save_editor -> 逐个回读对拍" % args.wait)
        return 0

    tmpdir = tempfile.mkdtemp(prefix="eca_gen_")
    for f in files:
        shutil.copy2(f, os.path.join(tmpdir, os.path.basename(f)))

    client = editor_client(root)
    results = []
    for f in files:
        name = os.path.basename(f)
        try:
            # mcp_client.call 返回 (text, payload)
            text, payload = client.call("import_eca", {"trigger_json_path": os.path.abspath(f)})
            res = payload if isinstance(payload, dict) else {}
            ok = bool(res.get("success"))
            results.append((name, ok, None))
            print("[import] %-24s success=%s mode=%s hotfix=%s"
                  % (name, ok, res.get("mode"), res.get("hotfix_status")))
        except Exception as e:  # noqa: BLE001
            results.append((name, False, str(e)[:120]))
            print("[import] %-24s 失败: %s" % (name, str(e)[:120]))

    time.sleep(args.wait)
    client.call("save_editor")
    print("[save] save_editor 已调用（它不返回真实成败，靠下一步回读判定）")
    time.sleep(1.0)

    bad = 0
    print("\n%-26s %-8s %-6s %s" % ("文件", "import", "valid", "回读对拍"))
    for name, ok, err in results:
        cur = os.path.join(tdir, name)
        if not os.path.isfile(cur):
            print("%-26s %-8s %-6s 文件消失（被 save 裁剪）" % (name, ok, "-"))
            bad += 1
            continue
        with open(cur, "r", encoding="utf-8") as fh:
            valid = json.load(fh).get("valid")
        d_ok, d_msg = diff_ok(os.path.join(tmpdir, name), cur)
        if not ok or not d_ok or valid is not True:
            bad += 1
        print("%-26s %-8s %-6s %s" % (name, ok, valid, d_msg))
        if err:
            print("    错误: %s" % err)

    shutil.rmtree(tmpdir, ignore_errors=True)
    print("\n%s" % ("全部通过" if bad == 0 else "有 %d 个文件未通过" % bad))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
