#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_batch_writer.py
批量 MCP 地形写入脚本 — 读取 CSV，通过 HTTP 直接调用 MCP Server 写入 Y3 编辑器地形。

用法:
  python mcp_batch_writer.py --terrain-csv terrain_grid.csv --texture-csv texture_grid.csv [options]

写入顺序（严格不可调换）:
  Pass 1: crack        — 裂缝最先，刷完即确定为空洞
  Pass 2: ground height — 逐层叠加，每次 +2（1 个基础高度）
  Pass 3: water        — deep_water + shallow_water
  Pass 4: slope/road   — 高度差=2 且需要斜坡的位置（通常由引擎自动生成，可选跳过）
  Pass 5: texture      — 纹理与地形不在一个维度，所有地形操作完成后再刷
"""

import argparse
import csv
import json
import os
import sys
import time

try:
    import requests
except ImportError:
    print("❌ 缺少 requests 库，请运行: pip install requests")
    sys.exit(1)


# ---------------------------------------------------------------------------
# MCP Client
# ---------------------------------------------------------------------------

class McpClient:
    """JSON-RPC 2.0 over Streamable HTTP — MCP Server 通信客户端"""

    def __init__(self, url, timeout=300):
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()
        self._req_id = 0
        self._headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    # -- helpers --

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    def _parse_sse(self, text):
        """从 SSE 格式 'data: {json}' 中提取 JSON 对象"""
        for line in text.strip().splitlines():
            line = line.strip()
            if line.startswith("data: "):
                return json.loads(line[6:])
        # 尝试直接解析整段文本
        return json.loads(text)

    # -- protocol --

    def initialize(self):
        """MCP initialize 握手"""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp_batch_writer", "version": "1.0"},
            },
        }
        resp = self.session.post(self.url, json=payload, headers=self._headers, timeout=10)
        resp.raise_for_status()
        data = self._parse_sse(resp.text)
        if "error" in data:
            raise RuntimeError(f"MCP initialize 失败: {data['error']}")

        # notifications/initialized
        notify = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }
        self.session.post(self.url, json=notify, headers=self._headers, timeout=10)
        return data

    def call_tool(self, tool_name, arguments):
        """调用 MCP tool，返回 result.content[0].text（字符串）"""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }
        resp = self.session.post(self.url, json=payload, headers=self._headers, timeout=self.timeout)
        resp.raise_for_status()
        data = self._parse_sse(resp.text)
        if "error" in data:
            raise RuntimeError(f"MCP tool/{tool_name} 错误: {data['error']}")
        content = data.get("result", {}).get("content", [])
        if content:
            return content[0].get("text", "")
        return ""


# ---------------------------------------------------------------------------
# CSV 解析
# ---------------------------------------------------------------------------

def parse_terrain_csv(path):
    """
    解析 terrain_grid.csv
    每格: "type,height,cliff_tex_id"
    返回: rows × cols 的列表，每元素 = (type_str, height_int, cliff_tex_id_int)
    """
    if not os.path.exists(path):
        print(f"❌ 文件不存在: {path}")
        sys.exit(1)

    grid = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for z, row in enumerate(reader):
            parsed_row = []
            for x, cell in enumerate(row):
                parts = cell.strip().strip('"').split(",")
                if len(parts) != 3:
                    print(f"❌ CSV 格式错误: 第 {z} 行第 {x} 列, 期望 3 字段, 得到 {len(parts)}: '{cell}'")
                    sys.exit(1)
                try:
                    parsed_row.append((parts[0], int(parts[1]), int(parts[2])))
                except ValueError:
                    print(f"❌ CSV 格式错误: 第 {z} 行第 {x} 列, 无法解析数值: '{cell}'")
                    sys.exit(1)
            grid.append(parsed_row)
    return grid


def parse_texture_csv(path):
    """
    解析 texture_grid.csv
    每格: texture_id (int)
    返回: rows × cols 的列表
    """
    if not os.path.exists(path):
        print(f"❌ 文件不存在: {path}")
        sys.exit(1)

    grid = []
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        for z, row in enumerate(reader):
            parsed_row = []
            for x, cell in enumerate(row):
                try:
                    parsed_row.append(int(cell.strip()))
                except ValueError:
                    print(f"❌ texture CSV 格式错误: 第 {z} 行第 {x} 列: '{cell}'")
                    sys.exit(1)
            grid.append(parsed_row)
    return grid


# inherit_neighbor 特殊值：道路/轮廓线继承邻居高度
INHERIT_NEIGHBOR = -999


def resolve_inherit_neighbor(terrain_grid):
    """将 terrain_grid 中 height=-999 的格子替换为邻居高度的平均值（多遍迭代）

    对所有 height=-999 的 ground/slope 格子，取上下左右邻居中非 -999 的
    ground/slope 高度平均值。采用多遍迭代：每遍 resolve 边缘（有有效邻居的），
    下一遍继续处理内层，直到没有 -999 残留或无法再 resolve。

    Args:
        terrain_grid: rows × cols 的列表，每元素 = (type_str, height_int, cliff_tex_id_int)
    Returns:
        resolved_count: 替换的格子总数
    """
    LAND_TYPES = {"ground", "slope"}
    rows = len(terrain_grid)
    cols = len(terrain_grid[0]) if rows > 0 else 0
    resolved_count = 0
    max_iterations = max(rows, cols)  # 安全上限，防止无限循环

    for iteration in range(max_iterations):
        batch_resolved = 0
        # 收集本轮需要 resolve 的格子及其新高度
        updates = []

        for z in range(rows):
            for x in range(cols):
                t, h, cid = terrain_grid[z][x]
                if t in LAND_TYPES and h == INHERIT_NEIGHBOR:
                    # 收集邻居高度（8 方向，增加连片区域的 resolve 速度）
                    neighbor_heights = []
                    for dz in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            if dz == 0 and dx == 0:
                                continue
                            nz, nx = z + dz, x + dx
                            if 0 <= nz < rows and 0 <= nx < cols:
                                nt, nh, _ = terrain_grid[nz][nx]
                                if nt in LAND_TYPES and nh != INHERIT_NEIGHBOR:
                                    neighbor_heights.append(nh)

                    if neighbor_heights:
                        resolved_h = int(round(sum(neighbor_heights) / len(neighbor_heights)))
                        updates.append((z, x, t, resolved_h, cid))

        if not updates:
            break

        for z, x, t, resolved_h, cid in updates:
            terrain_grid[z][x] = (t, resolved_h, cid)
            batch_resolved += 1

        resolved_count += batch_resolved
        print(f"  🔄 迭代 {iteration + 1}: resolve {batch_resolved} 格")

        # 检查是否还有残留
        remaining = sum(
            1 for z in range(rows) for x in range(cols)
            if terrain_grid[z][x][0] in LAND_TYPES and terrain_grid[z][x][1] == INHERIT_NEIGHBOR
        )
        if remaining == 0:
            break

    # 最终安全检查：如果仍有 -999 残留（孤立格子），强制设为 2（基础地面高度）
    fallback_count = 0
    for z in range(rows):
        for x in range(cols):
            t, h, cid = terrain_grid[z][x]
            if t in LAND_TYPES and h == INHERIT_NEIGHBOR:
                terrain_grid[z][x] = (t, 2, cid)
                fallback_count += 1

    if resolved_count > 0 or fallback_count > 0:
        print(f"  🔄 resolve inherit_neighbor 完成: {resolved_count} 格邻居均值"
              + (f", {fallback_count} 格兜底=2" if fallback_count > 0 else ""))

    return resolved_count + fallback_count


def compute_stats(terrain_grid, texture_grid):
    """计算并打印统计信息，返回统计字典"""
    rows = len(terrain_grid)
    cols = len(terrain_grid[0]) if rows > 0 else 0

    stats = {
        "rows": rows,
        "cols": cols,
        "total": rows * cols,
        "crack": 0,
        "ground": 0,
        "deep_water": 0,
        "shallow_water": 0,
        "slope": 0,
        "max_height": 0,
        "texture_cells": 0,
    }

    for z in range(rows):
        for x in range(cols):
            t, h, cid = terrain_grid[z][x]
            if t == "crack":
                stats["crack"] += 1
            elif t == "ground":
                stats["ground"] += 1
                if h != INHERIT_NEIGHBOR and h > stats["max_height"]:
                    stats["max_height"] = h
            elif t == "deep_water":
                stats["deep_water"] += 1
            elif t == "shallow_water":
                stats["shallow_water"] += 1
            elif t == "slope":
                stats["slope"] += 1
                if h != INHERIT_NEIGHBOR and h > stats["max_height"]:
                    stats["max_height"] = h

            if texture_grid and texture_grid[z][x] > 0:
                stats["texture_cells"] += 1

    max_layers = stats["max_height"] // 2 if stats["max_height"] > 0 else 0
    stats["max_layers"] = max_layers

    print(f"\n📊 地形统计:")
    print(f"   网格尺寸: {cols} × {rows} = {stats['total']} 格")
    print(f"   crack:         {stats['crack']:>6} 格")
    print(f"   ground:        {stats['ground']:>6} 格 (最大高度={stats['max_height']}, 层数={max_layers})")
    print(f"   deep_water:    {stats['deep_water']:>6} 格")
    print(f"   shallow_water: {stats['shallow_water']:>6} 格")
    print(f"   slope:         {stats['slope']:>6} 格")
    print(f"   texture:       {stats['texture_cells']:>6} 格")

    return stats


# ---------------------------------------------------------------------------
# Pass 调度
# ---------------------------------------------------------------------------

# MCP 调用间隔（秒）— 防止请求过快导致编辑器响应不及时
MCP_CALL_INTERVAL = 0
BATCH_SIZE = 1500  # 每批最多发送的格子数


def call_with_retry(mcp, tool_name, arguments, pass_label, max_retries=3):
    """带重试的 MCP 调用，每次调用后自动等待 MCP_CALL_INTERVAL 秒"""
    delays = [1, 2, 4]
    for attempt in range(max_retries + 1):
        try:
            result = mcp.call_tool(tool_name, arguments)
            if attempt > 0:
                print(f"   ⚠️ {pass_label} 重试 {attempt}/{max_retries} 成功")
            # 调用成功后等待间隔，避免连续请求过快
            time.sleep(MCP_CALL_INTERVAL)
            return result
        except Exception as e:
            if attempt < max_retries:
                delay = delays[attempt] if attempt < len(delays) else 4
                print(f"   ⚠️ {pass_label} 失败 ({e})，{delay}s 后重试 ({attempt+1}/{max_retries})...")
                time.sleep(delay)
            else:
                raise


def call_batched(mcp, tool_name, cells, extra_args, pass_label, batch_size=BATCH_SIZE, dry_run=False):
    """分批调用 MCP tool，每批最多 batch_size 个格子"""
    total = len(cells)
    if total == 0:
        return
    num_batches = (total + batch_size - 1) // batch_size
    success_total = 0
    for i in range(num_batches):
        batch = cells[i * batch_size : (i + 1) * batch_size]
        batch_label = f"{pass_label} [{i+1}/{num_batches}]"
        if dry_run:
            success_total += len(batch)
            continue
        estimated_time = len(batch) * 0.05
        print(f"   ⏳ {batch_label}: {len(batch)} 格发送中，预计等待 ~{estimated_time:.0f}s ...")
        args = {"cells": batch}
        args.update(extra_args)
        result = call_with_retry(mcp, tool_name, args, batch_label)
        success_total += len(batch)
        if num_batches > 1:
            print(f"   ✅ {batch_label}: {len(batch)} 格 — {result}")
    if num_batches == 1:
        print(f"   ✅ {pass_label}: {result}")
    else:
        print(f"   ✅ {pass_label} 全部完成: {success_total}/{total} 格")


def run_pass_crack(mcp, terrain_grid, dry_run=False):
    """Pass 1: 裂缝"""
    rows = len(terrain_grid)
    cols = len(terrain_grid[0])

    cells = []
    for z in range(rows):
        for x in range(cols):
            t, h, cid = terrain_grid[z][x]
            if t == "crack":
                cells.append({"x": x, "z": z, "y": 0, "radius": 1, "cliff_tex_id": cid})

    if not cells:
        print("   ⏭️ 无 crack 格子，跳过")
        return True

    print(f"   📍 收集到 {len(cells)} 个 crack 格子")
    if dry_run:
        return True

    crack_cid = cells[0].get("cliff_tex_id", 0) if cells else 0
    # 去掉 cells 里的 cliff_tex_id（只保留 x, z, y, radius）
    for c in cells:
        c.pop("cliff_tex_id", None)
    call_batched(mcp, "terrain_set_crack_block", cells, {"cliff_tex_id": crack_cid}, "Pass 1 Crack")
    return True


def run_pass_ground_height(mcp, terrain_grid, max_layers, dry_run=False):
    """Pass 2: Ground Height 逐层叠加"""
    rows = len(terrain_grid)
    cols = len(terrain_grid[0])

    if max_layers == 0:
        print("   ⏭️ 所有 ground 高度=0，跳过")
        return True

    for layer in range(1, max_layers + 1):
        target_height = layer * 2  # 每层 +2
        cells = []
        cid_counter = {}  # 统计本层最常见的 cliff_tex_id
        for z in range(rows):
            for x in range(cols):
                t, h, cid = terrain_grid[z][x]
                if t == "ground" and h >= target_height:
                    cells.append({"x": x, "z": z, "height": 2})
                    cid_counter[cid] = cid_counter.get(cid, 0) + 1

        if not cells:
            print(f"   ⏭️ 第 {layer}/{max_layers} 层无格子，跳过")
            continue

        print(f"   📍 第 {layer}/{max_layers} 层: {len(cells)} 格 (height>={target_height})")
        if dry_run:
            continue

        layer_cid = max(cid_counter, key=cid_counter.get) if cid_counter else 0
        call_batched(mcp, "terrain_set_height_block", cells, {"cliff_tex_id": layer_cid}, f"Pass 2 Height 层{layer}")
    return True


def run_pass_water(mcp, terrain_grid, dry_run=False):
    """Pass 3: Water（深水 + 浅水）"""
    rows = len(terrain_grid)
    cols = len(terrain_grid[0])

    # 深水
    dw_cells = []
    dw_cid_counter = {}
    for z in range(rows):
        for x in range(cols):
            t, h, cid = terrain_grid[z][x]
            if t == "deep_water":
                dw_cells.append({"x": x, "z": z})
                dw_cid_counter[cid] = dw_cid_counter.get(cid, 0) + 1

    if dw_cells:
        print(f"   📍 深水: {len(dw_cells)} 格")
        if not dry_run:
            dw_cid = max(dw_cid_counter, key=dw_cid_counter.get) if dw_cid_counter else 0
            call_batched(mcp, "terrain_set_deep_water_block", dw_cells, {"cliff_tex_id": dw_cid}, "Pass 3 DeepWater")
    else:
        print("   ⏭️ 无深水格子")

    # 浅水
    sw_cells = []
    sw_cid_counter = {}
    for z in range(rows):
        for x in range(cols):
            t, h, cid = terrain_grid[z][x]
            if t == "shallow_water":
                sw_cells.append({"x": x, "z": z})
                sw_cid_counter[cid] = sw_cid_counter.get(cid, 0) + 1

    if sw_cells:
        print(f"   📍 浅水: {len(sw_cells)} 格")
        if not dry_run:
            sw_cid = max(sw_cid_counter, key=sw_cid_counter.get) if sw_cid_counter else 0
            call_batched(mcp, "terrain_set_shallow_water_block", sw_cells, {"cliff_tex_id": sw_cid}, "Pass 3 ShallowWater")
    else:
        print("   ⏭️ 无浅水格子")

    return True


def run_pass_slope(mcp, terrain_grid, dry_run=False):
    """
    Pass 4: Slope/Road
    处理 terrain_grid 中 type='slope' 的格子，调用 terrain_set_road_block 写入斜坡。
    slope 格子由 cv_shallow_water_infer.py 在 Round 4 中标记（浅水两端陆地过渡带）。
    如果没有 slope 格子，则跳过（引擎也会在高差=2 处自动生成斜坡）。
    """
    rows = len(terrain_grid)
    cols = len(terrain_grid[0])

    cells = []
    slope_cid_counter = {}
    for z in range(rows):
        for x in range(cols):
            t, h, cid = terrain_grid[z][x]
            if t == "slope":
                # terrain_set_road_block 需要世界坐标 y（若为0则自动读取真实地面高度）
                cells.append({"x": x, "z": z, "y": h})
                slope_cid_counter[cid] = slope_cid_counter.get(cid, 0) + 1

    if not cells:
        print("   ⏭️ 无 slope 格子（斜坡由引擎自动生成），跳过")
        return True

    print(f"   📍 slope: {len(cells)} 格")
    if dry_run:
        return True

    slope_cid = max(slope_cid_counter, key=slope_cid_counter.get) if slope_cid_counter else 0
    call_batched(mcp, "terrain_set_road_block", cells, {"cliff_tex_id": slope_cid}, "Pass 4 Slope")
    return True


def run_pass_texture(mcp, texture_grid, dry_run=False):
    """Pass 5: 纹理"""
    if not texture_grid:
        print("   ⏭️ 无纹理数据，跳过")
        return True

    rows = len(texture_grid)
    cols = len(texture_grid[0])

    cells = []
    for z in range(rows):
        for x in range(cols):
            tid = texture_grid[z][x]
            if tid > 0:
                # TODO: 理想情况下应由 AI 根据地形语义判断每格的 strength/attenuation，
                #       例如道路边缘用较低 strength 做渐变过渡，核心区域用 1.0。
                #       目前统一使用默认值（strength=1.0, attenuation=0.5），同时保留
                #       power 字段以兼容经典模式（terrain_mode=0）的 COVER_DRAW 接口。
                cells.append({
                    "x": x, "z": z, "texture_type": tid,
                    "power": 1.0,        # 经典模式（terrain_mode=0）COVER_DRAW 用
                    "strength": 1.0,     # 叠加模式（terrain_mode=1）DRAW_TEXTURE 用
                    "attenuation": 0.5,  # 叠加模式衰减
                })

    if not cells:
        print("   ⏭️ 无纹理格子")
        return True

    print(f"   📍 纹理: {len(cells)} 格")
    if dry_run:
        return True

    call_batched(mcp, "terrain_draw_texture_block", cells, {}, "Pass 5 Texture")
    return True


# ---------------------------------------------------------------------------
# 断点续传
# ---------------------------------------------------------------------------

PASS_ORDER = ["crack", "ground_height", "water", "slope", "texture"]


def _compute_csv_fingerprint(terrain_csv_path, texture_csv_path):
    """计算 CSV 文件的指纹（修改时间 + 文件大小），用于检测 CSV 变更"""
    parts = []
    for p in [terrain_csv_path, texture_csv_path]:
        if p and os.path.exists(p):
            st = os.stat(p)
            parts.append(f"{p}:{st.st_mtime_ns}:{st.st_size}")
    return "|".join(parts)


def load_progress(output_dir, csv_fingerprint=None):
    """读取 progress.json，返回进度字典（兼容 pass 级和 batch 级）
    
    如果 csv_fingerprint 与保存的不匹配，说明 CSV 已变更，自动清除进度重新开始。
    """
    path = os.path.join(output_dir, "progress.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        # 检查 CSV 指纹是否匹配
        saved_fingerprint = data.get("csv_fingerprint", None)
        if csv_fingerprint and saved_fingerprint and saved_fingerprint != csv_fingerprint:
            print("   ⚠️ 检测到 CSV 文件已变更，自动清除旧进度，从头开始！")
            os.remove(path)
            return {
                "completed_passes": set(),
                "current_pass": None,
                "batch_offset": 0,
                "total_batches_in_pass": 0,
                "cells_done_in_pass": 0,
                "cells_total_in_pass": 0,
                "csv_fingerprint": csv_fingerprint,
            }
        
        return {
            "completed_passes": set(data.get("completed_passes", [])),
            "current_pass": data.get("current_pass", None),
            "batch_offset": data.get("batch_offset", 0),
            "total_batches_in_pass": data.get("total_batches_in_pass", 0),
            "cells_done_in_pass": data.get("cells_done_in_pass", 0),
            "cells_total_in_pass": data.get("cells_total_in_pass", 0),
            "csv_fingerprint": saved_fingerprint or csv_fingerprint,
        }
    return {
        "completed_passes": set(),
        "current_pass": None,
        "batch_offset": 0,
        "total_batches_in_pass": 0,
        "cells_done_in_pass": 0,
        "cells_total_in_pass": 0,
        "csv_fingerprint": csv_fingerprint,
    }


def save_progress(output_dir, progress):
    """保存 progress.json（支持 batch 级粒度）
    
    Args:
        progress: dict 或 set（向后兼容全量模式传 set 的情况）
    """
    path = os.path.join(output_dir, "progress.json")
    if isinstance(progress, set):
        # 向后兼容：全量模式仍传 set
        data = {"completed_passes": list(progress)}
    else:
        data = {
            "completed_passes": list(progress.get("completed_passes", set())),
            "current_pass": progress.get("current_pass"),
            "batch_offset": progress.get("batch_offset", 0),
            "total_batches_in_pass": progress.get("total_batches_in_pass", 0),
            "cells_done_in_pass": progress.get("cells_done_in_pass", 0),
            "cells_total_in_pass": progress.get("cells_total_in_pass", 0),
            "csv_fingerprint": progress.get("csv_fingerprint"),
        }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def clear_progress(output_dir):
    """删除 progress.json"""
    path = os.path.join(output_dir, "progress.json")
    if os.path.exists(path):
        os.remove(path)


def save_failed(output_dir, failed_passes):
    """保存 failed_passes.json"""
    if not failed_passes:
        return
    path = os.path.join(output_dir, "failed_passes.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(failed_passes, f, ensure_ascii=False, indent=2)
    print(f"   ⚠️ 失败记录已保存到: {path}")


# ---------------------------------------------------------------------------
# Single-batch 模式
# ---------------------------------------------------------------------------

def collect_pass_cells(pass_id, terrain_grid, texture_grid, stats):
    """为指定 pass 预收集所有 cells 和 MCP 工具名/额外参数（不执行写入）
    
    Returns:
        (tool_name, cells, extra_args) 或 None（如果该 pass 无数据可跳过）
        对于多阶段 pass（如 ground_height 多层、water 深浅），返回扁平化的 cells 列表
    """
    rows = len(terrain_grid)
    cols = len(terrain_grid[0]) if rows > 0 else 0

    if pass_id == "crack":
        cells = []
        for z in range(rows):
            for x in range(cols):
                t, h, cid = terrain_grid[z][x]
                if t == "crack":
                    cells.append({"x": x, "z": z, "y": 0, "radius": 1})
        if not cells:
            return None
        crack_cid = terrain_grid[0][0][2] if terrain_grid else 0
        # 取第一个 crack 格的 cliff_tex_id
        for z in range(rows):
            for x in range(cols):
                if terrain_grid[z][x][0] == "crack":
                    crack_cid = terrain_grid[z][x][2]
                    break
            else:
                continue
            break
        return ("terrain_set_crack_block", cells, {"cliff_tex_id": crack_cid})

    elif pass_id == "ground_height":
        max_layers = stats.get("max_layers", 0)
        if max_layers == 0:
            return None
        # 扁平化所有层的 cells
        all_cells = []
        for layer in range(1, max_layers + 1):
            target_height = layer * 2
            cid_counter = {}
            for z in range(rows):
                for x in range(cols):
                    t, h, cid = terrain_grid[z][x]
                    if t == "ground" and h >= target_height:
                        all_cells.append({"x": x, "z": z, "height": 2})
                        cid_counter[cid] = cid_counter.get(cid, 0) + 1
        if not all_cells:
            return None
        layer_cid = 0  # 默认
        return ("terrain_set_height_block", all_cells, {"cliff_tex_id": layer_cid})

    elif pass_id == "water":
        all_cells = []
        # 深水
        dw_cid_counter = {}
        for z in range(rows):
            for x in range(cols):
                t, h, cid = terrain_grid[z][x]
                if t == "deep_water":
                    all_cells.append({"x": x, "z": z, "_tool": "terrain_set_deep_water_block"})
                    dw_cid_counter[cid] = dw_cid_counter.get(cid, 0) + 1
        # 浅水
        sw_cid_counter = {}
        for z in range(rows):
            for x in range(cols):
                t, h, cid = terrain_grid[z][x]
                if t == "shallow_water":
                    all_cells.append({"x": x, "z": z, "_tool": "terrain_set_shallow_water_block"})
                    sw_cid_counter[cid] = sw_cid_counter.get(cid, 0) + 1
        if not all_cells:
            return None
        dw_cid = max(dw_cid_counter, key=dw_cid_counter.get) if dw_cid_counter else 0
        return ("_water_mixed", all_cells, {"cliff_tex_id": dw_cid})

    elif pass_id == "slope":
        cells = []
        slope_cid_counter = {}
        for z in range(rows):
            for x in range(cols):
                t, h, cid = terrain_grid[z][x]
                if t == "slope":
                    cells.append({"x": x, "z": z, "y": h})
                    slope_cid_counter[cid] = slope_cid_counter.get(cid, 0) + 1
        if not cells:
            return None
        slope_cid = max(slope_cid_counter, key=slope_cid_counter.get) if slope_cid_counter else 0
        return ("terrain_set_road_block", cells, {"cliff_tex_id": slope_cid})

    elif pass_id == "texture":
        if not texture_grid:
            return None
        cells = []
        for z in range(rows):
            for x in range(cols):
                tid = texture_grid[z][x]
                if tid > 0:
                    cells.append({
                        "x": x, "z": z, "texture_type": tid,
                        "power": 1.0, "strength": 1.0, "attenuation": 0.5,
                    })
        if not cells:
            return None
        return ("terrain_draw_texture_block", cells, {})

    return None


def run_single_batch_mode(mcp, terrain_grid, texture_grid, stats, output_dir, max_batches, progress):
    """单批模式：执行最多 max_batches 批后退出，输出 BATCH_RESULT JSON

    Args:
        mcp: McpClient 实例
        terrain_grid: 地形网格
        texture_grid: 纹理网格
        stats: compute_stats 返回的统计字典
        output_dir: 进度文件目录
        max_batches: 每次最多执行的批数（如 5）
        progress: load_progress 返回的进度字典
    """
    completed = progress["completed_passes"]
    batches_executed = 0

    for pass_idx, pass_id in enumerate(PASS_ORDER):
        if pass_id in completed:
            continue

        # 收集当前 pass 的 cells
        result = collect_pass_cells(pass_id, terrain_grid, texture_grid, stats)
        if result is None:
            # 该 pass 无数据，标记完成并继续
            completed.add(pass_id)
            progress["completed_passes"] = completed
            progress["current_pass"] = None
            progress["batch_offset"] = 0
            save_progress(output_dir, progress)
            print(f"   ⏭️ {pass_id}: 无数据，跳过")
            continue

        tool_name, cells, extra_args = result
        total_cells = len(cells)
        num_batches = (total_cells + BATCH_SIZE - 1) // BATCH_SIZE

        # 从 batch_offset 恢复
        batch_start = 0
        if progress.get("current_pass") == pass_id:
            batch_start = progress.get("batch_offset", 0)

        print(f"\n=== {pass_id} ({total_cells} 格, batch {batch_start+1}~/{num_batches}) ===")

        while batch_start < num_batches and batches_executed < max_batches:
            batch = cells[batch_start * BATCH_SIZE : (batch_start + 1) * BATCH_SIZE]
            batch_label = f"{pass_id} [{batch_start+1}/{num_batches}]"

            # 处理 water pass 的混合工具（深水/浅水在同一 cells 列表中）
            if tool_name == "_water_mixed":
                # 按 _tool 字段分组当前 batch
                dw_batch = [{"x": c["x"], "z": c["z"]} for c in batch if c.get("_tool") == "terrain_set_deep_water_block"]
                sw_batch = [{"x": c["x"], "z": c["z"]} for c in batch if c.get("_tool") == "terrain_set_shallow_water_block"]
                if dw_batch:
                    args = {"cells": dw_batch}
                    args.update(extra_args)
                    print(f"   ⏳ {batch_label}: {len(dw_batch)} 深水格发送中...")
                    call_with_retry(mcp, "terrain_set_deep_water_block", args, batch_label)
                if sw_batch:
                    args = {"cells": sw_batch}
                    args.update(extra_args)
                    print(f"   ⏳ {batch_label}: {len(sw_batch)} 浅水格发送中...")
                    call_with_retry(mcp, "terrain_set_shallow_water_block", args, batch_label)
            else:
                args = {"cells": batch}
                args.update(extra_args)
                print(f"   ⏳ {batch_label}: {len(batch)} 格发送中...")
                call_with_retry(mcp, tool_name, args, batch_label)

            batch_start += 1
            batches_executed += 1
            cells_done = min(batch_start * BATCH_SIZE, total_cells)

            # 保存 batch 级进度
            progress["current_pass"] = pass_id
            progress["batch_offset"] = batch_start
            progress["total_batches_in_pass"] = num_batches
            progress["cells_done_in_pass"] = cells_done
            progress["cells_total_in_pass"] = total_cells
            save_progress(output_dir, progress)
            print(f"   ✅ {batch_label}: 完成 ({cells_done}/{total_cells})")

        # 检查当前 pass 是否完成
        if batch_start >= num_batches:
            completed.add(pass_id)
            progress["completed_passes"] = completed
            progress["current_pass"] = None
            progress["batch_offset"] = 0
            progress["cells_done_in_pass"] = 0
            progress["cells_total_in_pass"] = 0
            save_progress(output_dir, progress)

            # 判断是否所有 pass 都完成
            remaining = [p for p in PASS_ORDER if p not in completed]
            # 检查剩余 pass 是否都无数据
            all_remaining_empty = True
            for rp in remaining:
                if collect_pass_cells(rp, terrain_grid, texture_grid, stats) is not None:
                    all_remaining_empty = False
                    break

            if not remaining or all_remaining_empty:
                # 标记所有剩余空 pass 为完成
                for rp in remaining:
                    completed.add(rp)
                progress["completed_passes"] = completed
                save_progress(output_dir, progress)
                clear_progress(output_dir)
                summary = {
                    "total": stats["total"], "ground": stats["ground"],
                    "deep_water": stats["deep_water"], "texture": stats["texture_cells"],
                }
                print(f'BATCH_RESULT:{json.dumps({"status":"all_done","summary":summary}, ensure_ascii=False)}')
                return
            else:
                next_pass = remaining[0] if remaining else None
                print(f'BATCH_RESULT:{json.dumps({"status":"pass_complete","completed_pass":pass_id,"next_pass":next_pass}, ensure_ascii=False)}')
                # 如果还有配额，继续下一个 pass
                if batches_executed < max_batches:
                    continue
                return
        else:
            # 当前 pass 未完成，配额用尽
            print(f'BATCH_RESULT:{json.dumps({"status":"in_progress","pass":pass_id,"batch":f"{batch_start}/{num_batches}","cells_done":min(batch_start * BATCH_SIZE, total_cells),"cells_total":total_cells}, ensure_ascii=False)}')
            return

    # 所有 pass 遍历完毕（都跳过了）
    clear_progress(output_dir)
    summary = {
        "total": stats["total"], "ground": stats["ground"],
        "deep_water": stats["deep_water"], "texture": stats["texture_cells"],
    }
    print(f'BATCH_RESULT:{json.dumps({"status":"all_done","summary":summary}, ensure_ascii=False)}')


# ---------------------------------------------------------------------------
# MCP URL 发现
# ---------------------------------------------------------------------------

def discover_mcp_url(override_url=None):
    """
    获取 MCP Server URL
    优先级: --url 参数 > mcp_settings.json > 默认值
    """
    if override_url:
        return override_url

    # 尝试从 mcp_settings.json 读取
    candidates = [
        os.path.join(".codemaker", "mcp_settings.json"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "mcp_settings.json"),
    ]
    for settings_path in candidates:
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                url = settings.get("mcpServers", {}).get("y3editor", {}).get("url")
                if url:
                    return url
            except (json.JSONDecodeError, KeyError):
                pass

    return "http://127.0.0.1:8765/mcp"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="批量 MCP 地形写入 — 读取 CSV 通过 HTTP 直接调用 MCP Server"
    )
    parser.add_argument("--terrain-csv", required=True, help="terrain_grid.csv 路径")
    parser.add_argument("--texture-csv", required=True, help="texture_grid.csv 路径")
    parser.add_argument("--output-dir", default=None, help="进度文件和日志输出目录（默认=CSV 同目录）")
    parser.add_argument("--url", default=None, help="MCP Server URL（默认从 mcp_settings.json 读取）")
    parser.add_argument("--restart", action="store_true", help="忽略进度文件，从头开始")
    parser.add_argument("--dry-run", action="store_true", help="只解析 CSV 并输出统计，不实际写入")
    parser.add_argument("--timeout", type=int, default=300, help="MCP 调用超时秒数（默认 300）")
    parser.add_argument("--single-batch", nargs='?', const=1, type=int, default=None,
                        metavar='N', help="单批模式: 每次执行 N 批(默认1)后退出，输出 BATCH_RESULT JSON")
    args = parser.parse_args()

    # 输出目录
    output_dir = args.output_dir or os.path.dirname(os.path.abspath(args.terrain_csv))
    os.makedirs(output_dir, exist_ok=True)

    print("=" * 60)
    print("  MCP Batch Terrain Writer v1.0")
    print("=" * 60)

    # --- Step 1: 解析 CSV ---
    print("\n[Step 1] 解析 CSV ...")
    terrain_grid = parse_terrain_csv(args.terrain_csv)
    texture_grid = parse_texture_csv(args.texture_csv) if args.texture_csv else []

    # --- Step 1b: 解析 inherit_neighbor ---
    print("\n[Step 1b] 解析 inherit_neighbor (height=-999) ...")
    resolve_inherit_neighbor(terrain_grid)

    stats = compute_stats(terrain_grid, texture_grid)

    if args.dry_run:
        print("\n🏁 --dry-run 模式，不实际写入。")

        # 输出每个 pass 的预计格子数
        print("\n📋 各 Pass 预计:")
        print(f"   Pass 1 Crack:        {stats['crack']} 格")
        layers = stats["max_layers"]
        for layer in range(1, layers + 1):
            target_h = layer * 2
            cnt = sum(1 for row in terrain_grid for (t, h, cid) in row if t == "ground" and h >= target_h)
            print(f"   Pass 2 Height 层{layer}/{layers}: {cnt} 格 (height>={target_h})")
        print(f"   Pass 3 DeepWater:    {stats['deep_water']} 格")
        print(f"   Pass 3 ShallowWater: {stats['shallow_water']} 格")
        print(f"   Pass 4 Slope:        {stats['slope']} 格")
        print(f"   Pass 5 Texture:      {stats['texture_cells']} 格")
        slope_calls = 1 if stats['slope'] > 0 else 0
        print(f"\n   预计 MCP 调用次数: ~{1 + layers + 2 + slope_calls + 1} 次")
        return

    # --- Step 2: MCP 连接 ---
    print("\n[Step 2] 连接 MCP Server ...")
    mcp_url = discover_mcp_url(args.url)
    print(f"   URL: {mcp_url}")

    mcp = McpClient(mcp_url, timeout=args.timeout)
    try:
        mcp.initialize()
    except Exception as e:
        print(f"\n⚠️ 无法连接 MCP Server: {e}")
        print("请检查:")
        print("  1. Y3 编辑器是否已打开?")
        print("  2. MCP Server 是否已启动?")
        print("  3. 目标地图是否已加载?")
        sys.exit(1)

    # 探活
    try:
        info = mcp.call_tool("get_map_info", {})
        print(f"   ✅ MCP 连接成功: {info}")
    except Exception as e:
        print(f"   ⚠️ 探活失败: {e}")
        sys.exit(1)

    # --- Step 3: 断点续传 ---
    if args.restart:
        clear_progress(output_dir)
        print("\n   🔄 已清除进度文件，从头开始")

    csv_fp = _compute_csv_fingerprint(args.terrain_csv, args.texture_csv)
    progress = load_progress(output_dir, csv_fingerprint=csv_fp)
    completed = progress["completed_passes"]
    if completed:
        print(f"\n   📌 恢复进度: 已完成 {sorted(completed)}")

    # --- Step 3b: single-batch 分流 ---
    if args.single_batch is not None:
        run_single_batch_mode(mcp, terrain_grid, texture_grid, stats, output_dir, args.single_batch, progress)
        return

    # --- Step 4: 执行各 Pass（全量模式） ---
    total_start = time.time()
    failed_passes = []

    pass_map = {
        "crack": ("Pass 1: Crack 裂缝", lambda: run_pass_crack(mcp, terrain_grid)),
        "ground_height": (
            f"Pass 2: Ground Height 逐层叠加 ({stats['max_layers']} 层)",
            lambda: run_pass_ground_height(mcp, terrain_grid, stats["max_layers"]),
        ),
        "water": (
            f"Pass 3: Water 水体 (深水={stats['deep_water']}, 浅水={stats['shallow_water']})",
            lambda: run_pass_water(mcp, terrain_grid),
        ),
        "slope": ("Pass 4: Slope 斜坡 (引擎自动)", lambda: run_pass_slope(mcp, terrain_grid)),
        "texture": (
            f"Pass 5: Texture 纹理 ({stats['texture_cells']} 格)",
            lambda: run_pass_texture(mcp, texture_grid),
        ),
    }

    for pass_id in PASS_ORDER:
        label, fn = pass_map[pass_id]

        if pass_id in completed:
            print(f"\n=== {label} === ⏭️ 已完成，跳过")
            continue

        print(f"\n=== {label} ===")
        pass_start = time.time()

        try:
            fn()
            completed.add(pass_id)
            save_progress(output_dir, completed)
            elapsed = time.time() - pass_start
            print(f"   ⏱️ 耗时 {elapsed:.1f}s")
        except Exception as e:
            elapsed = time.time() - pass_start
            print(f"   ❌ {pass_id} 写入失败 ({elapsed:.1f}s): {e}")
            failed_passes.append({"pass": pass_id, "error": str(e)})

    # --- Step 5: 完成摘要 ---
    total_elapsed = time.time() - total_start

    print("\n" + "=" * 60)
    print("  写入完成摘要")
    print("=" * 60)
    print(f"   总格子: {stats['total']}")
    print(f"   crack:         {stats['crack']}")
    print(f"   ground:        {stats['ground']} (height 层数={stats['max_layers']})")
    print(f"   deep_water:    {stats['deep_water']}")
    print(f"   shallow_water: {stats['shallow_water']}")
    print(f"   slope:         {stats['slope']}")
    print(f"   texture:       {stats['texture_cells']}")
    print(f"   失败 pass:     {len(failed_passes)}")
    print(f"   总耗时:        {total_elapsed:.1f}s")

    if failed_passes:
        save_failed(output_dir, failed_passes)
        print(f"\n   ⚠️ 有 {len(failed_passes)} 个 pass 失败，详见 failed_passes.json")
    else:
        clear_progress(output_dir)
        print("\n   ✅ 全部成功！progress.json 已清理")


if __name__ == "__main__":
    main()
