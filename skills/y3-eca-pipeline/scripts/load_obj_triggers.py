# -*- coding: utf-8 -*-
"""物编触发器（技能 / 魔法效果 / 单位 / 物品 / 投射物）批量加载。

为什么需要它：`import_eca` 只接受 `global_trigger/trigger/`，物编触发器没有热更通道。
正确顺序只有一条：

    写盘（edit_trigger.py） -> restart_editor(save_before_restart=false)
    -> 等编辑器重新打开 -> save_editor -> 回读校验 valid

中间**一次 save_editor 都不能有**，否则编辑器内存里的旧内容会把盘上新写的顶回去。

清单格式（单个 JSON，或一个目录下的多个 JSON）：

```json
{
  "map": "EntryMap",
  "objects": [
    {
      "container": "ability",
      "key": 110001001,
      "triggers": [
        {"name": "技能-烈焰斩-效果", "id": 2026102001,
         "event": [["ABILITY_SP_END"]], "action": []}
      ]
    }
  ]
}
```

也接受每个文件就是一个对象（含 `container` / `key` / `triggers`）。

用法：
    py -3 load_obj_triggers.py manifest.json
    py -3 load_obj_triggers.py build/eca_obj --dry-run
    py -3 load_obj_triggers.py manifest.json --no-save

退出码：0 全部 valid；1 有生成失败 / 触发器缺失 / valid 不为 true / 重启失败。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDER_DIR = os.path.abspath(os.path.join(SKILL_DIR, "..", "..", "eca-json-builder"))
EDIT_TRIGGER = os.path.join(BUILDER_DIR, "edit_trigger.py")

SKELETON = {
    "local_variable": {},
    "trigger_dict": {},
    "trigger_group_info": [],
    "trigger_version": "1.2",
    "variable_dict": {},
    "variable_group_info": [],
    "variable_length_dict": {},
}

CONTAINER_DIRS = {
    "ability": "ability",
    "modifier": "modifier",
    "unit": "unit",
    "item": "item",
    "projectile": "projectile",
}


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


def load_objects(path):
    """读清单，返回 [(map, container, key, triggers)]。"""
    files = []
    if os.path.isdir(path):
        files = sorted(glob.glob(os.path.join(path, "*.json")))
        if not files:
            raise SystemExit("[!] 目录里没有 JSON：%s" % path)
    else:
        files = [path]

    out = []
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, list):
            items = data
        elif "objects" in data:
            items = data["objects"]
        else:
            items = [data]
        for item in items:
            container = item.get("container")
            key = item.get("key")
            triggers = item.get("triggers")
            if not container or key is None or not triggers:
                raise SystemExit("[!] 清单项缺少 container / key / triggers：%s" % f)
            if container not in CONTAINER_DIRS:
                raise SystemExit("[!] 未知 container=%r（可选：%s）"
                                 % (container, sorted(CONTAINER_DIRS)))
            out.append((item.get("map", data.get("map") if isinstance(data, dict) else None),
                        container, key, triggers))
    return out


def container_path(root, map_name, container, key):
    return os.path.join(root, "maps", map_name, CONTAINER_DIRS[container], "%s.json" % key)


def ensure_skeleton(path):
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                cur = json.load(fh)
            if cur.get("trigger_dict") or cur.get("trigger_group_info"):
                return
        except Exception:  # noqa: BLE001
            pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(SKELETON, fh, ensure_ascii=False, indent=2)


def run_edit(dsl_path, container, key, root, map_name):
    cmd = [sys.executable, EDIT_TRIGGER, dsl_path,
           "--container", container, "--key", str(key),
           "--map", map_name, "--root", root]
    p = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()


def verify(path, triggers):
    """返回 (缺失的 id 列表, valid 不为 true 的 id 列表)。"""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    td = data.get("trigger_dict") or {}
    missing, invalid = [], []
    for trig in triggers:
        tid = trig.get("id")
        if tid is None:
            # 清单没写 id 时，生成器会按名字算稳定 id：回读时按名字找
            tid = next((k for k, v in td.items()
                        if v.get("trigger_name") == trig.get("name")), None)
            if tid is None:
                missing.append(trig.get("name"))
                continue
        tid = str(tid)
        node = td.get(tid)
        if node is None:
            missing.append(tid)
        elif node.get("valid") is not True:
            invalid.append(tid)
    return missing, invalid


def main():
    ap = argparse.ArgumentParser(description="物编触发器批量加载（重启一次 + 回读校验）")
    ap.add_argument("manifest", help="清单 JSON，或装清单的目录")
    ap.add_argument("--root", default=None)
    ap.add_argument("--map", dest="map_name", default=None, help="覆盖清单里的地图名")
    ap.add_argument("--wait", type=float, default=10.0, help="重启后等待秒数，默认 10")
    ap.add_argument("--no-save", action="store_true", help="重启后不调用 save_editor")
    ap.add_argument("--audit", action="store_true",
                    help="加载成功后追加 audit_triggers.py（含物编容器全量审计）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    root = find_root(args.root)
    objects = load_objects(args.manifest)
    default_map = args.map_name or "EntryMap"

    print("工程根：%s" % root)
    print("待加载对象：%d 个" % len(objects))
    for map_name, container, key, triggers in objects:
        print("   %-9s %-12s %s（%d 条触发器）"
              % (map_name or default_map, container, key, len(triggers)))
    if args.dry_run:
        print("\n(--dry-run) 顺序：写盘 -> restart_editor(false) -> 等 %ss -> save -> 回读 valid"
              % args.wait)
        return 0

    failures = 0
    maps_used = set()
    tmpdir = tempfile.mkdtemp(prefix="obj_trig_")
    written = []
    for i, (map_name, container, key, triggers) in enumerate(objects):
        map_name = map_name or default_map
        maps_used.add(map_name)
        path = container_path(root, map_name, container, key)
        ensure_skeleton(path)
        dsl_path = os.path.join(tmpdir, "%02d_%s_%s.json" % (i, container, key))
        with open(dsl_path, "w", encoding="utf-8") as fh:
            json.dump({"map": map_name, "triggers": triggers}, fh, ensure_ascii=False, indent=2)
        rc, out = run_edit(dsl_path, container, key, root, map_name)
        status = "OK" if rc == 0 else "FAIL"
        print("[写盘] %-9s %-12s %-12s %s" % (container, key, map_name, status))
        if rc != 0:
            print(out[-1200:])
            failures += 1
        written.append((map_name, container, key, triggers))

    try:
        from mcp_client import editor_client  # noqa: E402
        client = editor_client(root)
        print("\n[重启] restart_editor(save_before_restart=false) ...")
        client.call("restart_editor", {"save_before_restart": False})
        time.sleep(args.wait)
        if not args.no_save:
            client.call("save_editor")
            print("[保存] save_editor 已调用")
            time.sleep(1.0)
    except Exception as exc:  # noqa: BLE001
        print("\n[!] 重启 / 保存失败：%s" % str(exc)[:200])
        print("    盘上文件已写，但编辑器内存还是旧的：期间不要 save_editor。")
        return 1

    print("\n%-9s %-12s %-9s %s" % ("容器", "Key", "结果", "说明"))
    for map_name, container, key, triggers in written:
        path = container_path(root, map_name, container, key)
        if not os.path.isfile(path):
            print("%-9s %-12s %-9s 文件消失（被保存裁剪）" % (container, key, "FAIL"))
            failures += 1
            continue
        missing, invalid = verify(path, triggers)
        if missing or invalid:
            failures += 1
            detail = []
            if missing:
                detail.append("缺触发器 %s" % missing)
            if invalid:
                detail.append("valid!=true %s" % invalid)
            print("%-9s %-12s %-9s %s" % (container, key, "FAIL", "；".join(detail)))
        else:
            print("%-9s %-12s %-9s 全部 valid" % (container, key, "OK"))

    print("\n%s" % ("全部通过" if failures == 0 else "有 %d 处未通过" % failures))
    if failures == 0 and args.audit:
        audit_script = os.path.join(BUILDER_DIR, "audit_triggers.py")
        for map_name in sorted(maps_used):
            print("\n[审计] %s" % map_name)
            rc = subprocess.call([sys.executable, audit_script,
                                  "--map-dir", os.path.join("maps", map_name),
                                  "--root", root])
            if rc != 0:
                failures += 1
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
