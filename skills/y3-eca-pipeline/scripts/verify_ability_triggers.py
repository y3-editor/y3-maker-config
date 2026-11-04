# -*- coding: utf-8 -*-
"""技能触发器验证脚手架 —— 把「技能触发器到底生效没有」变成一条可复现的命令。

为什么需要它：技能触发器的失效是**静默**的（触发器 valid=true、静态校验全绿、运行时零效果），
而手工验证的每一步都踩过坑（实测）：
  · 英雄被波次打死了还继续施法 → `cast()` 照样返回成功，测试结论全是假的
  · `unit:set_hp(n)` 只写血量、**不会复活** → 死了之后越测越错
  · 点目标技能（圆形指示器 sight_type=3）在脚本里**根本放不出去** → 白试很多轮
  · 用 CD / 蓝量当"施法发生"的判据 → 读晚一步就恢复了，什么也证明不了
  · 探针写到游戏自己也会写的变量上 → 读回来的是游戏的值
本脚本把这些前置做成固定步骤，并按判据给出 PASS / FAIL / NEEDS_MANUAL / BLOCKED。

用法：
    py -3 verify_ability_triggers.py --skill 100002004 --slot 4 [--restart]
    py -3 verify_ability_triggers.py --skill 100002002 --slot 2 --dry-run    # 只打印计划
    py -3 verify_ability_triggers.py --skill 100002004 --slot 4 --emit       # 打印可执行的 Lua
    py -3 verify_ability_triggers.py --judge-setup "<布置返回>" --judge-after "<回读返回>"

两种执行方式：
  ① 直连（默认）：脚本自己连 y3-helper 的 MCP HTTP 端点（需要在编辑器里执行过
     `y3-helper: Start MCP Server`，端口见 `.codemaker/mcp_settings.json`（或 `.codex/config.toml`），脚本会读）。
  ② `--emit` + `--judge`：会话里已经挂了 MCP 工具时用这条 —— 脚本只给 Lua 与判定，
     不依赖 HTTP 端点。

退出码：0 = PASS / NEEDS_MANUAL，1 = FAIL，2 = BLOCKED（环境问题，不是功能问题）。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve()
BUILDER_DIR = HERE.parents[2] / "eca-json-builder"  # .codemaker/skills/eca-json-builder
sys.path.insert(0, str(BUILDER_DIR))

import mcp_client  # noqa: E402

MAP_DEFAULT = "EntryMap"
HERO_VAR = "英雄"          # 工程里存英雄的全局变量名
FAIL_LIMIT = 2             # MCP 连续失败上限（与 MCP 调用纪律一致：绝不盲重试）


class Blocked(Exception):
    """环境问题导致测不下去（不是功能结论）。"""


class Bridge:
    """MCP 调用 + 熔断计数。"""

    def __init__(self, project_root: Path):
        self.root = project_root
        # helper_client() 内部已经 connect；再次 connect 会重复 initialize，
        # 实测 y3-helper 返回 HTTP 400。
        self.helper = mcp_client.helper_client(str(project_root))
        self.fail = 0

    def call(self, tool, arguments=None):
        try:
            text, payload = self.helper.call(tool, arguments or {})
        except Exception as exc:  # noqa: BLE001 - 统一转成熔断
            self.fail += 1
            if self.fail >= FAIL_LIMIT:
                raise Blocked(f"MCP 连续 {self.fail} 次调用失败（{tool}）：{exc}") from exc
            raise
        self.fail = 0
        return text, payload

    def lua(self, code: str) -> str:
        """跑一段 Lua，返回输出串。空输出视作失败（实测偶发，按纪律不重试）。"""
        text, payload = self.call("execute_lua", {"code": code})
        out = payload.get("output") if isinstance(payload, dict) else None
        if out is None:
            out = text or ""
        if not str(out).strip():
            self.fail += 1
            if self.fail >= FAIL_LIMIT:
                raise Blocked("execute_lua 连续返回空输出（实测过：静默丢弃，重试无用）")
        return str(out)

    def status(self) -> dict:
        _, payload = self.call("get_game_status")
        return payload or {}


# ---------------------------------------------------------------------------
# 物编：技能配置（决定能不能脚本验证）
# ---------------------------------------------------------------------------

SIGHT_TYPE_LABEL = {
    0: "无指示器（自身/立即）",
    1: "扇形（返回角度）",
    2: "箭头（返回角度）",
    3: "圆形指示器（取点）",
    4: "目标指示器（单位/物品）",
    5: "单位或地点指示器",
    6: "建造指示器",
    7: "多段/向量指示器",
}

# 脚本能可靠施法的指示器类型 → 施法表达式（其余一律判 NEEDS_MANUAL，别空转）
#   0 无指示器：hero:cast(技能)
#   4 单位目标：hero:cast(技能, 目标单位)（实测可用）
#   3 圆形指示器（取点）：脚本放不出去（cast 返回成功但不消耗 CD/蓝量）→ 只能人工手点
CAST_MODE = {0: "self", 4: "unit"}

# 不能脚本施法的指示器类型 → 为什么（用于 NEEDS_MANUAL 的说明与人工步骤提示）
MANUAL_REASON = {
    1: "扇形/角度指示器：脚本无法给出选取角度",
    2: "箭头/角度指示器：脚本无法给出选取角度",
    3: "圆形指示器（取点）：脚本 cast 放不出去（返回成功但不消耗 CD/蓝量）",
    5: "单位或地点指示器：脚本无法确定选取目标",
    6: "建造指示器：属于建造流程，不走技能验证",
    7: "多段/向量指示器：脚本无法给出选取点与角度",
}


def read_ability(root: Path, map_name: str, key: int) -> dict:
    path = root / "maps" / map_name / "editor_table" / "abilityall" / f"{key}.json"
    if not path.is_file():
        raise Blocked(f"找不到技能物编文件：{path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    def first_item(name):
        node = data.get(name)
        if isinstance(node, dict) and isinstance(node.get("items"), list) and node["items"]:
            return node["items"][0]
        return None

    return {
        "key": data.get("key", key),
        "sight_type": data.get("sight_type"),
        "cast_type": data.get("ability_cast_type"),
        "immediate": data.get("is_immediate"),
        "circle_radius": first_item("circle_radius"),
        "cast_range": first_item("ability_cast_range"),
        "cd": first_item("cold_down_time"),
        "cost": first_item("ability_cost"),
    }


def parse_kv(text: str) -> dict:
    """把 Lua 侧拼出来的 `k=v|k=v` 串解析成 dict（Lua 里不依赖 json 库）。"""
    line = ""
    for candidate in reversed(str(text).splitlines()):
        if "=" in candidate and "|" in candidate:
            line = candidate
            break
    out = {}
    for chunk in line.strip().strip('"').split("|"):
        if "=" not in chunk:
            continue
        k, _, v = chunk.partition("=")
        out[k.strip()] = v.strip()
    return out


def num(mapping: dict, key: str, default=0.0) -> float:
    try:
        return float(mapping.get(key, default))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Lua 步骤（--emit 与直连共用同一份）
# ---------------------------------------------------------------------------

LUA_SELECT_HERO = """
local p = y3.player(1)
local card = y3.ui.get_ui(p, '{panel}.card_{card}')
if card then card:send_event('card_{card}_click') end
local btn = y3.ui.get_ui(p, '{panel}.btn_confirm')
if btn then btn:send_event('confirm_click') end
return 'sent=1'
"""

LUA_SETUP = """
local out = {{}}
local ok, raw = pcall(function() return GameAPI.get_trigger_variable_unit_entity('{hero_var}') end)
if not ok or not raw then return 'error=no_hero' end
local hero = y3.unit.get_by_handle(raw)
_G.__vt_hero = hero
out[#out+1] = 'hero=' .. tostring(hero:get_key())
out[#out+1] = 'alive=' .. tostring(hero:is_alive())
local hx, hy = {hx}, {hy}
hero:set_point(y3.point.create(hx, hy, 0))
hero:set_hp(hero:get_attr('hp_max'))
out[#out+1] = 'hero_hp=' .. string.format('%.1f', hero:get_hp())
out[#out+1] = 'hero_cd=' .. string.format('%.2f', {ab_expr}:get_cd())
out[#out+1] = 'hero_mp=' .. string.format('%.1f', hero:get_mp())
out[#out+1] = 'hero_buffs=' .. tostring(#(hero:get_buffs() or {{}}))
local targets = {{}}
for i = 1, {count} do
  local ang = (i - 1) * (6.2831853 / {count})
  local px = hx + {offset} * math.cos(ang)
  local py = hy + {offset} * math.sin(ang)
  local u = y3.unit.create_unit(y3.player(31), {creep}, y3.point.create(px, py, 0), 0)
  targets[#targets+1] = u
  out[#out+1] = 'target' .. i .. '_hp=' .. string.format('%.1f', u:get_hp())
end
_G.__vt_targets = targets
local okc, err = pcall(function() {cast_expr} end)
out[#out+1] = 'cast=' .. tostring(okc) .. '/' .. tostring(err)
return table.concat(out, '|')
"""

LUA_READ = """
local out = {{}}
local hero = _G.__vt_hero
local targets = _G.__vt_targets or {{}}
if hero then
  out[#out+1] = 'hero_alive=' .. tostring(hero:is_alive())
  out[#out+1] = 'hero_hp=' .. string.format('%.1f', hero:get_hp())
  out[#out+1] = 'hero_cd=' .. string.format('%.2f', {ab_expr}:get_cd())
  out[#out+1] = 'hero_mp=' .. string.format('%.1f', hero:get_mp())
  out[#out+1] = 'hero_buffs=' .. tostring(#(hero:get_buffs() or {{}}))
else
  out[#out+1] = 'hero_alive=false'
end
for i, u in ipairs(targets) do
  out[#out+1] = 'target' .. i .. '_hp=' .. string.format('%.1f', u:get_hp())
end
return table.concat(out, '|')
"""


def ab_expr(slot: int) -> str:
    return f"hero:get_ability_by_slot(3, {slot})"


def lua_select_hero(card: int, panel: str) -> str:
    """panel = 英雄选择界面的「画板.根控件」路径。**面板名是项目专属的**，
    脚本不带默认值，必须由调用方给出（见 --hero-panel）。"""
    return LUA_SELECT_HERO.format(card=card, panel=panel)


def lua_setup(slot: int, count: int, creep: int, offset: float, cast_expr: str,
              hx: float = 3000.0, hy: float = 3000.0) -> str:
    return LUA_SETUP.format(hero_var=HERO_VAR, hx=hx, hy=hy, count=count, creep=creep,
                            offset=float(offset), ab_expr=ab_expr(slot), cast_expr=cast_expr)


def lua_read(slot: int) -> str:
    return LUA_READ.format(ab_expr=ab_expr(slot))


def verdict(setup: dict, after: dict, count: int):
    """按实测口径判定：(退出码, 结论文本)。"""
    cd_gain = num(after, "hero_cd") - num(setup, "hero_cd")
    mp_loss = num(setup, "hero_mp") - num(after, "hero_mp")
    damage = sum(max(0.0, num(setup, f"target{i}_hp") - num(after, f"target{i}_hp"))
                 for i in range(1, count + 1))
    hero_loss = max(0.0, num(setup, "hero_hp") - num(after, "hero_hp"))
    fact = ("施法调用=%s | 冷却增加=%.2fs | 蓝量下降=%.1f | 测试怪总掉血=%.1f | 英雄掉血=%.1f"
            % (setup.get("cast", "").startswith("true"), cd_gain, mp_loss, damage, hero_loss))
    if after.get("hero_alive", "true") != "true":
        return 2, fact + "\n   ⚠️ 英雄在观测窗口内死亡，本局数据不可用（重开一局再测）"
    if damage > 0:
        return 0, fact + "\n[结论] PASS —— 测试怪掉血，总伤害 %.1f。" % damage
    if cd_gain > 0 or mp_loss > 0:
        return 1, fact + (
            "\n[结论] FAIL —— 施法确实发生了（冷却/蓝量有变化），但目标一点血都没掉。\n"
            "   排查顺序：① 伤害槽位是否写反（APPLY_DAMAGE 第 0 槽是伤害所属、第 2 槽才是受伤目标）\n"
            "            ② AOE 半径单位（ECA 形状按厘米，物编 circle_radius 按米）与选区中心点\n"
            "            ③ 阵营/状态过滤是否把中立敌对怪排除了")
    return 1, fact + (
        "\n[结论] FAIL(存疑) —— 没观察到施法发生（冷却与蓝量都没变）：这次 cast 根本没放出去，\n"
        "   不能据此判定触发器坏了。请确认：英雄存活、技能已学会、蓝量足够、距离在施法范围内。")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="技能触发器验证脚手架（ECA · Y3）")
    ap.add_argument("--skill", type=int, help="技能 Key（物编 abilityall/<key>.json）")
    ap.add_argument("--slot", type=int, help="技能在单位技能栏的位置（第几格，1 起）")
    ap.add_argument("--hero-panel", default=None,
                    help="英雄选择界面的「画板.根控件」路径，例：'MySelect.MySelect_root'"
                         "（面板名是项目专属的，不给就只做布置+回读，跳过选人）")
    ap.add_argument("--hero-card", type=int, default=2, help="英雄选择界面的卡片序号（默认 2）")
    ap.add_argument("--creep", type=int, default=200005, help="测试怪单位 Key（默认 200005，血厚好观察）")
    ap.add_argument("--count", type=int, default=3, help="造几只测试怪（默认 3）")
    ap.add_argument("--offset", type=float, default=150.0, help="测试怪离英雄的距离（厘米，默认 150）")
    ap.add_argument("--wait", type=float, default=2.5, help="施法后等多久再读（秒）")
    ap.add_argument("--restart", action="store_true", help="先重启游戏（英雄已死/环境脏时用）")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划与判据，不接触游戏")
    ap.add_argument("--emit", action="store_true", help="打印可直接执行的 Lua（供 MCP 工具会话使用）")
    ap.add_argument("--judge-setup", help="布置步骤返回的 k=v|k=v 串（配合 --emit 用）")
    ap.add_argument("--judge-after", help="回读步骤返回的 k=v|k=v 串（配合 --emit 用）")
    ap.add_argument("--map", default=MAP_DEFAULT)
    ap.add_argument("--root", default=None)
    args = ap.parse_args(argv)

    # 纯判定模式：不需要技能 / 槽位信息，也不需要连游戏
    if args.judge_setup is not None or args.judge_after is not None:
        code, text = verdict(parse_kv(args.judge_setup or ""), parse_kv(args.judge_after or ""),
                             args.count)
        print(text)
        return code

    if not args.skill or not args.slot:
        ap.error("--skill 与 --slot 必填（除非用 --judge-setup / --judge-after）")

    root = Path(args.root).resolve() if args.root else Path(mcp_client.find_project_root() or os.getcwd())
    info = read_ability(root, args.map, args.skill)
    sight = info["sight_type"]
    label = SIGHT_TYPE_LABEL.get(sight, "未知(%s)" % sight)
    print("技能 %s：指示器 sight_type=%s（%s），指示器半径/施法距离/冷却 = %s/%s/%s"
          % (args.skill, sight, label, info["circle_radius"], info["cast_range"], info["cd"]))
    mode = CAST_MODE.get(sight)
    if mode == "self":
        cast_expr = "hero:cast(%s)" % ab_expr(args.slot)
    elif mode == "unit":
        cast_expr = "hero:cast(%s, targets[1])" % ab_expr(args.slot)
    else:
        cast_expr = None
    reason = MANUAL_REASON.get(sight, "脚本无法施法")

    if args.dry_run:
        print("\n[计划]（--dry-run，不接触游戏）")
        print("  1. 重启游戏（%s）并选第 %d 张卡" % ("是" if args.restart else "否，用当前会话", args.hero_card))
        print("  2. 英雄回满血 + 传送到 (3000,3000)（远离刷怪路径）")
        print("  3. 在英雄周围 %g 厘米造 %d 只测试怪（Key %s）" % (args.offset, args.count, args.creep))
        print("  4. 记录英雄 / 测试怪的基线血量、蓝量、冷却、buff 数")
        if cast_expr:
            print("  5. 脚本施法：%s → 等 %gs → 按身份逐只回读" % (cast_expr, args.wait))
        else:
            print("  5. ⚠️ 该指示器类型脚本施法不可靠 → 预期结论 NEEDS_MANUAL，改人工手点")
        print("  6. 判据：任一测试怪掉血 = PASS；全不掉血且施法确认发生 = FAIL；")
        print("           英雄掉血只作参考（怪会打英雄）")
        if not cast_expr:
            print("\n[预期结论] NEEDS_MANUAL：%s" % reason)
        return 0

    if args.emit:
        if args.hero_panel:
            print("\n[步骤 1] 选择英雄（第 %d 张卡）—— 用 y3_helper.execute_lua 执行：" % args.hero_card)
            print(lua_select_hero(args.hero_card, args.hero_panel).strip())
        else:
            print("\n[步骤 1] 跳过选人：没给 --hero-panel（面板名是项目专属的）。"
                  "若游戏里还没选英雄，先手动选一个再执行下一步。")
        if not cast_expr:
            print("\n⚠️ 该技能 sight_type=%s（%s）：%s"
                  % (sight, label, reason))
            print("   结论应为 NEEDS_MANUAL，请人工手点验证；下面只给出「布置 + 读回」两段，" )
            print("   布置段不含施法调用。")
        print("\n[步骤 2] 等 3 秒后：布置现场并施法 —— 用 y3_helper.execute_lua 执行：")
        print(lua_setup(args.slot, args.count, args.creep, args.offset,
                        cast_expr or "-- 需人工手点，此行不施法").strip())
        print("\n[步骤 3] 等 %gs 后回读 —— 用 y3_helper.execute_lua 执行：" % args.wait)
        print(lua_read(args.slot).strip())
        print("\n[步骤 4] 判定（把两步返回的 k=v|k=v 串贴进来）：")
        print('  py -3 verify_ability_triggers.py --judge-setup "<步骤2 的返回>" '
              '--judge-after "<步骤3 的返回>" --count %d' % args.count)
        return 0

    bridge = Bridge(root)
    try:
        if not bridge.status().get("client_connected") and not args.restart:
            raise Blocked("当前没有已连接的游戏客户端；加 --restart 或先启动游戏")
        if args.restart:
            print("[1/5] 重启游戏 …")
            bridge.call("stop_game")
            bridge.call("launch_game")
            for _ in range(12):
                time.sleep(5)
                if bridge.status().get("client_connected"):
                    break
            else:
                raise Blocked("游戏重启后 60 秒内没有连上客户端")
        if args.hero_panel:
            print("[1/5] 选择英雄 …")
            bridge.lua(lua_select_hero(args.hero_card, args.hero_panel))
            time.sleep(3)
        else:
            print("[1/5] 跳过选人（未给 --hero-panel）→ 用游戏里当前已选的英雄")

        if not cast_expr:
            print("\n[结论] NEEDS_MANUAL —— %s" % reason)
            print("  人工步骤：")
            print("    1) 游戏里选中英雄，点第 %d 格技能" % args.slot)
            print("    2) 往怪堆里点一下，观察怪是否掉血")
            print("    3) 若怪不掉血，先核对单位口径：物编 circle_radius 按**米**、")
            print("       触发器 CONST_CIRCULAR_SHAPE 按**厘米**（4.0 米 = 400 厘米）")
            return 0

        print("[2/5] 布置现场（回血 / 传送 / 造怪）并施法 …")
        setup = parse_kv(bridge.lua(lua_setup(args.slot, args.count, args.creep,
                                             args.offset, cast_expr)))
        print("   " + json.dumps(setup, ensure_ascii=False))
        if setup.get("error"):
            raise Blocked("取英雄失败：%s（英雄还没创建？）" % setup["error"])
        if setup.get("alive") != "true":
            raise Blocked("英雄当前是死亡状态：施法会静默无效，先 --restart 重开一局再测")

        print("[3/5] 等待 %gs …" % args.wait)
        time.sleep(args.wait)

        print("[4/5] 回读 …")
        after = parse_kv(bridge.lua(lua_read(args.slot)))
        print("   " + json.dumps(after, ensure_ascii=False))

        print("[5/5] 判定 …")
        code, text = verdict(setup, after, args.count)
        print("   " + text.replace("\n", "\n   "))
        return code
    except Blocked as exc:
        print("\n[结论] BLOCKED —— %s" % exc)
        print("\n下一步二选一：")
        print("  ① 在编辑器里执行 `y3-helper: Start MCP Server`（启用 MCP HTTP 端点）后重跑；")
        print("  ② 加 `--emit` 拿到三段 Lua，用会话里的 MCP 工具执行，再用 `--judge-*` 判定。")
        return 2


if __name__ == "__main__":
    sys.exit(main())
