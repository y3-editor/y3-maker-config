# -*- coding: utf-8 -*-
"""画板控件 uid 解析器：按**控件名**查 uid。

为什么需要它：**控件名才是契约，uid 每次重新生成画板都会变**。
触发器里的 `SET_UI_COMP_VISIBLE` / `SET_UI_COMP_TEXT` / `SET_UI_COMP_BIND_*` 等动作按 uid 寻址，
一旦画板重生成而触发器还写着旧 uid，动作会**静默打空**（触发器表面 `valid=true`、审计可能也全绿）。
所以生成触发器时必须"从画板 JSON 读回 uid"，而不是在脚本里写死。

命令行：
  py -3 ui_uid.py <map_dir> --panel <画板名> --list            # 列出全部控件：路径 \t 名字 \t uid
  py -3 ui_uid.py <map_dir> --panel <画板名> <控件名>           # 解析单个控件名 -> uid
  py -3 ui_uid.py <map_dir> --panel <画板名> <控件名> --json     # JSON 输出
  py -3 ui_uid.py <map_dir> --all-uids                          # 所有画板/元件的 uid（供存在性校验）
  py -3 ui_uid.py <map_dir> --panels                            # 列出可用画板

库用法（供生成器脚本 import）：
  from ui_uid import resolve, panel_controls, all_uids
  uid = resolve("maps/EntryMap", "MyPanel", "my_bar")
"""
from __future__ import annotations

import argparse
import difflib
import glob
import json
import os
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def iter_nodes(node, path=""):
    """深度优先遍历节点，产出 (路径, 节点)。路径形如 `block.hud_hp_bar`。"""
    if isinstance(node, dict):
        name = node.get("name")
        cur = ("%s.%s" % (path, name)) if (path and name) else (name or path)
        yield cur, node
        for c in node.get("children") or []:
            yield from iter_nodes(c, cur)
    elif isinstance(node, list):
        for c in node:
            yield from iter_nodes(c, path)


def panel_path(map_dir, panel):
    """定位画板 / 元件 JSON：先找 `ui/<名>.json`，再找 `ui/prefab/<名>.json`。"""
    for cand in (os.path.join(map_dir, "ui", panel + ".json"),
                 os.path.join(map_dir, "ui", "prefab", panel + ".json")):
        if os.path.isfile(cand):
            return cand
    return None


def list_panels(map_dir):
    out = []
    for p in sorted(glob.glob(os.path.join(map_dir, "ui", "*.json"))):
        out.append(os.path.splitext(os.path.basename(p))[0])
    for p in sorted(glob.glob(os.path.join(map_dir, "ui", "prefab", "*.json"))):
        out.append("prefab/" + os.path.splitext(os.path.basename(p))[0])
    return out


def panel_controls(map_dir, panel):
    """返回该画板全部控件：[{"path":…, "name":…, "uid":…, "type":…}, …]"""
    path = panel_path(map_dir, panel)
    if not path:
        raise FileNotFoundError("找不到画板 JSON：%s（ui/%s.json 或 ui/prefab/%s.json）"
                                % (map_dir, panel, panel))
    data = _read_json(path)
    out = []
    for p, node in iter_nodes(data):
        if node.get("name"):
            out.append({"path": p, "name": node.get("name"),
                        "uid": node.get("uid"), "type": node.get("type")})
    return out


def resolve(map_dir, panel, name):
    """按控件名解析 uid；找不到就抛错并列出候选（重名时提示用路径）。"""
    hits = [c for c in panel_controls(map_dir, panel) if c["name"] == name]
    if not hits:
        all_names = [str(c["name"]) for c in panel_controls(map_dir, panel)]
        near = difflib.get_close_matches(name, all_names, n=8, cutoff=0.6)
        if not near:
            near = [n for n in all_names if name[:4] in n][:8]
        raise KeyError("画板 %s 里没有控件 '%s'；名字相近的有：%s" % (panel, name, near))
    if len(hits) > 1:
        sys.stderr.write(
            "[WARN] 控件名 '%s' 在画板 %s 里出现 %d 次（路径：%s）——"
            "按名字取会撞车，建议生成画板后把重名控件改名（例如进度条内的百分比文字"
            "与技能格 CD 标签同名），或改用路径定位。\n"
            % (name, panel, len(hits), [h["path"] for h in hits]))
    return hits[0]["uid"]


def all_uids(map_dir):
    """所有画板 / 元件里出现过的 uid（供"触发器 uid 是否存在"校验）。"""
    out = set()
    for p in glob.glob(os.path.join(map_dir, "ui", "**", "*.json"), recursive=True):
        try:
            data = _read_json(p)
        except Exception:
            continue
        for _path, node in iter_nodes(data):
            u = node.get("uid")
            if isinstance(u, str):
                out.add(u)
    return out


def main():
    ap = argparse.ArgumentParser(description="画板控件 uid 解析（控件名是契约，uid 会变）")
    ap.add_argument("map_dir", help="地图目录，例如 maps/EntryMap")
    ap.add_argument("name", nargs="?", help="控件名（配合 --panel）")
    ap.add_argument("--panel", help="画板 / 元件名")
    ap.add_argument("--list", action="store_true", help="列出该画板全部控件")
    ap.add_argument("--panels", action="store_true", help="列出可用画板")
    ap.add_argument("--all-uids", action="store_true", help="打印所有 uid")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    args = ap.parse_args()

    if args.panels:
        for p in list_panels(args.map_dir):
            print(p)
        return 0

    if args.all_uids:
        uids = sorted(all_uids(args.map_dir))
        if args.json:
            print(json.dumps(uids, ensure_ascii=False, indent=2))
        else:
            print("\n".join(uids))
        return 0

    if not args.panel:
        ap.error("需要 --panel（或 --panels / --all-uids）")

    if args.list or not args.name:
        for c in panel_controls(args.map_dir, args.panel):
            if args.json:
                print(json.dumps(c, ensure_ascii=False))
            else:
                print("%-58s %-26s %s" % (c["path"], c["name"], c["uid"]))
        return 0

    try:
        uid = resolve(args.map_dir, args.panel, args.name)
    except (KeyError, FileNotFoundError) as e:
        print("[!] %s" % e)
        return 1
    print(json.dumps({"panel": args.panel, "name": args.name, "uid": uid},
                     ensure_ascii=False) if args.json else uid)
    return 0


if __name__ == "__main__":
    sys.exit(main())
