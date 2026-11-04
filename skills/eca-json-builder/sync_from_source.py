# -*- coding: utf-8 -*-
"""从编辑器源码派生 ECA 参数类型数据（`eca_source_data.json`）。

为什么需要它：编辑器对不认识的写法**不报错**，只在 `save_editor` 时把参数清成 `null`
或让触发器 `valid=false`。早期 `gen_trigger.py` 的 `ARG_TYPE_ID` / sub_type 表是手工逆向
维护的（只覆盖 71/311 个类型），本脚本改为从源码派生，避免继续靠猜。

数据来源与对应关系（全部可追溯到源码，见输出的 `_source` 指纹）：

  1. `dm/commons/black_box/consts/const_name.py`
       扁平常量表 `NAME = <int>`：类型名/枚举名的 ID 源。
  2. `dm/commons/black_box/trigger/game_trigger/eca/GameTriggerArg.py`
       `类型名 = reg_arg('类型名', const_name.X, <default>, ..., <is_global_var>, <is_local_var>,
                          <is_kv_value>, <can_compare>, ...)`
       `GameTriggerArgType` 的成员值就是 `const_name.X`（例：`PLAYER = reg_arg('PLAYER', const_name.ROLE, ...)`
       所以 PLAYER 的 ID 来自 `ROLE`），flags 决定该类型能否作为全局/局部变量、KV 值、参与比较。
  3. `dm/commons/black_box/trigger/game_trigger/args/*.py`
       `@register_trigger_arg_sub_type(GameTriggerArgType.X)` 类体 → 该类型**合法的 sub_type 表**
       （取值可能是整数、字符串，或 `const_name.Y` 引用，三种都要解析）。
       同文件的 `@register_trigger_arg_cls(...)` → 哪些 sub_type 真正有实现。
       `get_op_arg(i, EAExprConst(value=v, val_type=T))` → 可选参数默认值。

用法（**仅维护者**；使用者不需要源码，直接读随包的 eca_source_data.json）：
  py -3 sync_from_source.py --src <engine-src>              # 派生并写入产物
  py -3 sync_from_source.py --src <engine-src> --dry-run    # 只打印覆盖报告

`--src` 无默认值，必须显式传入：脚本会随 skill 分发，不能把维护者本机的源码路径写死在里面。

> ⚠️ 版本一致性：派生的 ID 表必须与当前编辑器/引擎构建匹配。换引擎后重新运行本脚本，
> 并用 `verify_trigger.py` 抽验至少一条触发器（`valid=true`）再提交。
> 输出**不含时间戳**，同一份源码重复运行结果逐字节一致，便于 diff 审查。
>
> 🔒 **脱敏**：产物会随 skill 分发给外部用户，因此**默认不写**引擎源码根与文件清单
> （绝对路径 + 引擎目录结构属信息泄漏），只保留 sha256 与计数。
> 维护者本地排查可加 `--include-source-paths`，但**不要把带路径的产物提交/分发**。
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(SKILL_DIR, "eca_source_data.json")
INDEX_PATH = os.path.join(SKILL_DIR, "eca_index.json")

# 分发数据里**不写**引擎源码根与文件清单：那个 JSON 会随 skill 发给外部用户，
# 暴露「维护者本机的绝对路径」与「引擎内部目录结构」属于信息泄漏。
# 只保留 sha256（不可逆）与计数，既能让维护者判断"数据是哪一批"，又不泄漏任何路径。
# 维护者本地排查可用 `--include-source-paths` 临时带出，但**不要把它提交/分发**。
REDACTED_ENGINE_ROOT = "<engine-source:redacted>"
DATA_VERSION = "1"          # 维护者重新派生时手动递增（保持输出可 diff）

CONST_REL = "dm/commons/black_box/consts/const_name.py"
ARG_TYPE_REL = "dm/commons/black_box/trigger/game_trigger/eca/GameTriggerArg.py"
ARGS_REL = "dm/commons/black_box/trigger/game_trigger/args"

_CONST_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(-?\d+)\s*(?:#\s*(.*))?$")
_SUBTYPE_DECORATOR = re.compile(r"@register_trigger_arg_sub_type\(\s*GameTriggerArgType\.([A-Z0-9_]+)\s*\)")
_ARGCLS_DECORATOR = re.compile(
    r"@register_trigger_arg_cls\(\s*GameTriggerArgType\.([A-Z0-9_]+)\s*,\s*[A-Za-z0-9_]+\.([A-Za-z0-9_]+)\s*\)")
_ASSIGN_LINE = re.compile(r"^([A-Z][A-Z0-9_]*)\s*=\s*(.+?)\s*(?:#\s*(.*))?$")
_OPARG = re.compile(
    r"get_op_arg\(\s*(\d+)\s*,\s*EAExprConst\(value=([^,]+),\s*val_type=([A-Za-z0-9_.]+)\)")
_REGARG_HEAD = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*reg_arg\(")
_CLASS_HEAD = re.compile(r"^class\s+([A-Za-z0-9_]+)\s*[\(:]")
_ALIAS_TO_CONST = re.compile(r"^\s+([A-Z][A-Z0-9_]*)\s*=\s*const_name\.([A-Z0-9_]+)\s*(?:#.*)?$")
_ALIAS_TO_MEMBER = re.compile(r"^\s+([A-Z][A-Z0-9_]*)\s*=\s*([A-Z][A-Z0-9_]*)\s*(?:#.*)?$")
_ARG_CATEGORY_REF = re.compile(r'^\s+([A-Z][A-Z0-9_]*)\s*=\s*ARG_TYPE_CATEGORY\[')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_consts(path):
    consts = {}
    with io.open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = _CONST_LINE.match(line.strip())
            if m:
                consts[m.group(1)] = int(m.group(2))
    return consts


def _raw_literal(raw):
    """源码字面量 → JSON 值（字符串保留，sub_type 允许字符串）。"""
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] in "'\"" and raw[-1] == raw[0]:
        return raw[1:-1]
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def _resolve_value(raw, consts):
    """解析 sub_type 取值：字面量 或 `const_name.X` 引用。"""
    raw = raw.strip()
    if raw.startswith("const_name."):
        name = raw[len("const_name."):].strip()
        return consts.get(name, "<%s>" % name)
    return _raw_literal(raw)


def _split_top_level(s):
    """按顶层逗号切分函数实参（忽略嵌套括号/引号内的逗号）。"""
    out, buf, depth, quote = [], [], 0, None
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "'\"":
            quote = ch
            buf.append(ch)
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if "".join(buf).strip():
        out.append("".join(buf).strip())
    return out


def _class_body(text, class_name):
    """截取某个顶层类的类体文本（到下一个顶层 class 或文件末尾）。"""
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        m = _CLASS_HEAD.match(line)
        if m and m.group(1) == class_name:
            start = i
            continue
        if start is not None and line.startswith("class "):
            return "\n".join(lines[start:i])
    return "\n".join(lines[start:]) if start is not None else ""


def parse_reg_args(path, consts, class_name="GameTriggerArgType"):
    """解析 `GameTriggerArgType` 类体 → {类型名: {id, default, flags...}}。

    类体里 ID 有三种写法，都要认：
      a) `NAME = reg_arg('NAME', const_name.X, <default>, ...)`  ← 主流
      b) `NAME = const_name.X`                                    ← 直接别名（如 ACTION_LIST / BOOLEAN_OPERATOR）
      c) `NAME = OTHER_MEMBER`                                    ← 成员别名（后处理继承 ID）
      `NAME = ARG_TYPE_CATEGORY["X"]` / `NAME = [...]` 是并集伪类型，本就没有独立 ID，跳过。
    """
    text = io.open(path, encoding="utf-8", errors="replace").read()
    body = _class_body(text, class_name)
    lines = body.split("\n")
    result = {}
    member_alias = {}
    i = 0
    while i < len(lines):
        m = _REGARG_HEAD.match(lines[i])
        if not m:
            am = _ALIAS_TO_CONST.match(lines[i])
            if am:
                const_name = am.group(2)
                entry = {"const": const_name}
                if const_name in consts:
                    entry["id"] = consts[const_name]
                result[am.group(1)] = entry
                i += 1
                continue
            if _ARG_CATEGORY_REF.match(lines[i]):
                i += 1
                continue
            mm = _ALIAS_TO_MEMBER.match(lines[i])
            if mm:
                member_alias[mm.group(1)] = mm.group(2)
            i += 1
            continue
        # 拼接跨行实参，直到括号配平
        chunk = lines[i]
        depth = chunk.count("(") - chunk.count(")")
        while depth > 0 and i + 1 < len(lines):
            i += 1
            chunk += "\n" + lines[i]
            depth = chunk.count("(") - chunk.count(")")
        name = m.group(1)
        body = chunk[chunk.index("reg_arg(") + len("reg_arg("):]
        body = body.rsplit(")", 1)[0]
        parts = _split_top_level(body)
        if len(parts) < 2:
            i += 1
            continue
        const_ref = parts[1].strip()
        const_name = const_ref[len("const_name."):].strip() if const_ref.startswith("const_name.") else None
        entry = {"const": const_name}
        if const_name is not None and const_name in consts:
            entry["id"] = consts[const_name]
        if len(parts) > 2:
            entry["default"] = _resolve_value(parts[2], consts)
        flag_names = ["is_global_var", "is_local_var", "is_kv_value", "can_compare"]
        for offset, flag in enumerate(flag_names):
            idx = 5 + offset
            if len(parts) > idx and parts[idx].strip() in ("True", "False"):
                entry[flag] = parts[idx].strip() == "True"
        result[name] = entry
        i += 1
    # 成员别名继承 ID（一次遍历足够：别名链在实际表里只有一层）
    for alias, target in sorted(member_alias.items()):
        if alias in result:
            continue
        base = result.get(target) or {}
        if "id" in base:
            entry = {"const": base.get("const"), "id": base["id"], "alias_of": target}
            result[alias] = entry
    return result


def parse_arg_files(args_dir, consts):
    """解析 args/*.py → {类型名: {sub_types, implemented, op_arg_defaults}}。"""
    result = {}

    def bucket(type_name):
        return result.setdefault(
            type_name, {"sub_types": {}, "implemented": [], "op_arg_defaults": {}})

    for fname in sorted(os.listdir(args_dir)):
        if not fname.endswith(".py"):
            continue
        lines = io.open(os.path.join(args_dir, fname), encoding="utf-8",
                        errors="replace").read().split("\n")
        current_type = None
        pending_type = None
        in_subtype_class = False
        for line in lines:
            m = _SUBTYPE_DECORATOR.search(line)
            if m:
                pending_type = m.group(1)
                bucket(pending_type)
                in_subtype_class = False
                continue
            m = _ARGCLS_DECORATOR.search(line)
            if m:
                type_name, sub_name = m.group(1), m.group(2)
                impl = bucket(type_name)["implemented"]
                if sub_name not in impl:
                    impl.append(sub_name)
                in_subtype_class = False
                pending_type = None
                continue
            # 紧跟在 sub_type 装饰器后的 class 定义 → 进入其类体读赋值
            if pending_type and line.startswith("class "):
                current_type = pending_type
                in_subtype_class = True
                pending_type = None
                continue
            if line.startswith((" ", "\t")):
                if in_subtype_class and current_type:
                    am = _ASSIGN_LINE.match(line.strip())
                    if am and not am.group(2).startswith("["):
                        bucket(current_type)["sub_types"][am.group(1)] = _resolve_value(am.group(2), consts)
                op = _OPARG.search(line)
                if op and current_type:
                    idx = int(op.group(1))
                    result[current_type]["op_arg_defaults"].setdefault(
                        idx, [_resolve_value(op.group(2), consts), op.group(3).split(".")[-1]])
                continue
            if line.startswith("class ") or line.strip() == "" or line.startswith("@"):
                in_subtype_class = False
                continue
            in_subtype_class = False

    for v in result.values():
        v["sub_types"] = {k: v["sub_types"][k] for k in sorted(v["sub_types"])}
        v["implemented"] = sorted(v["implemented"])
        v["op_arg_defaults"] = {str(k): v["op_arg_defaults"][k] for k in sorted(v["op_arg_defaults"])}
    return result


def index_param_type_names(path=INDEX_PATH):
    if not os.path.isfile(path):
        return set()
    idx = json.load(io.open(path, encoding="utf-8"))
    names = set()
    for e in idx.values():
        for p in (e.get("p") or []) + (e.get("o") or []):
            s = str(p).strip().strip("[]")
            for part in re.split(r"[,/]", s):
                part = part.strip()
                if part:
                    names.add(part)
    return names


def build(src_root, include_source_paths=False):
    const_path = os.path.join(src_root, CONST_REL.replace("/", os.sep))
    arg_type_path = os.path.join(src_root, ARG_TYPE_REL.replace("/", os.sep))
    args_dir = os.path.join(src_root, ARGS_REL.replace("/", os.sep))
    for p in (const_path, arg_type_path):
        if not os.path.isfile(p):
            raise SystemExit("源码文件缺失：%s" % p)
    if not os.path.isdir(args_dir):
        raise SystemExit("源码目录缺失：%s" % args_dir)

    consts = parse_consts(const_path)
    reg = parse_reg_args(arg_type_path, consts)
    subs = parse_arg_files(args_dir, consts)

    arg_types = {}
    for name in sorted(set(reg) | set(subs)):
        entry = dict(reg.get(name) or {})
        entry.update(subs.get(name) or {})
        arg_types[name] = entry

    arg_type_ids = {n: v["id"] for n, v in sorted(arg_types.items()) if "id" in v}

    # 变量读取 sub_type：各类型自己声明的 VARIABLE 取值（取代手工逆向的映射表）
    variable_subtype = {}
    for name, v in arg_types.items():
        st = (v.get("sub_types") or {})
        if "VARIABLE" in st:
            variable_subtype[name] = st["VARIABLE"]

    categories = {
        "GLOBAL_VAR_ARG_TYPE": sorted(n for n, v in arg_types.items() if v.get("is_global_var")),
        "LOCAL_VAR_ARG_TYPE": sorted(n for n, v in arg_types.items() if v.get("is_local_var")),
        "KV_VAR": sorted(n for n, v in arg_types.items() if v.get("is_kv_value")),
        "COMPARABLE_VAR": sorted(n for n, v in arg_types.items() if v.get("can_compare")),
    }

    files = [CONST_REL, ARG_TYPE_REL]
    files += [ARGS_REL + "/" + f for f in sorted(os.listdir(args_dir)) if f.endswith(".py")]
    digest = hashlib.sha256()
    for rel in files:
        digest.update(sha256_file(os.path.join(src_root, rel.replace("/", os.sep))).encode())

    source_meta = {
        "data_version": DATA_VERSION,
        "derived_by": "sync_from_source.py",
        "sha256": digest.hexdigest(),
        "file_count": len(files),
        "const_count": len(consts),
        "arg_type_count": len(arg_types),
    }
    if include_source_paths:
        # 仅维护者本地排查用；带绝对路径与引擎目录结构，禁止提交/分发
        source_meta["engine_root"] = src_root.replace(os.sep, "/")
        source_meta["files"] = files
    return {
        "_source": source_meta,
        "arg_type_ids": arg_type_ids,
        "variable_subtype": {k: variable_subtype[k] for k in sorted(variable_subtype)},
        "categories": categories,
        "arg_types": {k: arg_types[k] for k in sorted(arg_types)},
        "consts": consts,
    }


def report(data):
    wanted = index_param_type_names()
    ids = data["arg_type_ids"]
    subs = data["arg_types"]
    resolved = sorted(n for n in wanted if n in ids)
    unresolved = sorted(n for n in wanted if n not in ids)
    src = data["_source"]
    print("数据版本          : %s" % src.get("data_version"))
    print("源码指纹 sha256   : %s（分发数据只保留哈希与计数，不含任何路径）" % src["sha256"][:16])
    print("扫描文件数        : %d（const_name + GameTriggerArg + args/*.py）" % src["file_count"])
    if src.get("engine_root"):
        print("⚠️  本次带出源码路径（仅维护者本地排查用）：%s" % src["engine_root"])
    print("const_name 常量    : %d" % src["const_count"])
    print("登记的参数类型     : %d（其中有 ID 的 %d）" % (src["arg_type_count"], len(ids)))
    print("sub_type 声明的类型: %d，共 %d 个 sub_type"
          % (sum(1 for v in subs.values() if v.get("sub_types")),
             sum(len(v.get("sub_types") or {}) for v in subs.values())))
    print("变量读取 sub_type  : %d 个类型可派生" % len(data["variable_subtype"]))
    print("分类（由源码 flags 推导）：")
    for k, v in data["categories"].items():
        print("    %-20s %d 个" % (k, len(v)))
    print()
    print("eca_index.json 参数类型名: %d" % len(wanted))
    print("  源码可解析 : %d" % len(resolved))
    if unresolved:
        print("  仍未解析   : %d（并集/伪类型，无独立 ID，属正常）" % len(unresolved))
        print("               %s" % (unresolved[:18],))
    return unresolved


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--src", required=True,
                   help="编辑器源码根（包含 dm/commons/...）。无默认值：本脚本会随 skill 分发，"
                        "不能把维护者本机路径写死在里面")
    p.add_argument("--dry-run", action="store_true", help="只打印覆盖报告，不写文件")
    p.add_argument("--include-source-paths", action="store_true",
                   help="把引擎源码根与文件清单写进产物（**仅维护者本地排查用，禁止提交/分发**）")
    args = p.parse_args(argv)

    src = args.src.replace("/", os.sep)
    if not os.path.isdir(src):
        raise SystemExit("源码根目录不存在：%s" % src)

    data = build(src, include_source_paths=args.include_source_paths)
    report(data)
    if args.dry_run:
        print("\n[dry-run] 未写文件")
        return 0
    with io.open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1, sort_keys=True)
    print("\n已写入 %s（%d bytes）" % (OUT_PATH, os.path.getsize(OUT_PATH)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
