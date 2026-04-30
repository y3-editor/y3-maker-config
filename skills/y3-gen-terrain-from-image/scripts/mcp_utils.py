"""
mcp_utils.py
MCP 调用封装工具，供三个 Pass 脚本共用。
进度条输出、状态文件读写、断点续传逻辑。
"""
import json
import os
import sys
import time


STATE_FILE = "terrain_write_state.json"

# 分层写入顺序（按地形硬度从强到弱）
TERRAIN_LAYER_ORDER = ["cliff", "water", "slope", "ground"]


# ── 进度条 ────────────────────────────────────────────────────────────────────

def progress_bar(current: int, total: int, width: int = 16) -> str:
    filled = int(width * current / total) if total > 0 else 0
    bar = "█" * filled + "░" * (width - filled)
    pct = int(100 * current / total) if total > 0 else 0
    return f"{bar} {pct:3d}%"


def print_progress(pass_name: str, layer: str, current: int, total: int, elapsed: float):
    bar = progress_bar(current, total)
    remaining = ""
    if current > 0 and elapsed > 0:
        rate = current / elapsed
        secs_left = (total - current) / rate if rate > 0 else 0
        remaining = f" | 预计剩余 ~{int(secs_left)}s"
    line = f"\r[{pass_name} - {layer}] 第 {current}/{total} 行 {bar}{remaining}"
    sys.stdout.write(line)
    sys.stdout.flush()


def print_progress_deco(pass_name: str, current: int, total: int, elapsed: float):
    bar = progress_bar(current, total)
    remaining = ""
    if current > 0 and elapsed > 0:
        rate = current / elapsed
        secs_left = (total - current) / rate if rate > 0 else 0
        remaining = f" | 预计剩余 ~{int(secs_left)}s"
    line = f"\r[{pass_name}] 已放置 {current}/{total} 个 {bar}{remaining}"
    sys.stdout.write(line)
    sys.stdout.flush()


# ── 状态文件 ──────────────────────────────────────────────────────────────────

def load_state(pass_id: str) -> dict:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        if state.get("pass_id") == pass_id:
            return state
    return {"pass_id": pass_id, "layers_done": [], "current_layer": None, "current_row": 0}


def save_state(state: dict):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def clear_state():
    if os.path.exists(STATE_FILE):
        os.remove(STATE_FILE)


# ── CSV 读取 ──────────────────────────────────────────────────────────────────

def read_csv_rows(csv_path: str) -> list[list[str]]:
    import csv
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        return list(reader)


# ── MCP 调用占位（实际实现时替换为真实 MCP 调用）────────────────────────────

def mcp_set_terrain_row(row: int, cells: list[str]) -> dict:
    """调用 Y3 编辑器 MCP set_terrain_row 接口。"""
    # TODO: 替换为真实 MCP 调用
    # from mcp_client import call
    # return call("set_terrain_row", {"row": row, "cells": cells})
    return {"success": True}


def mcp_set_texture_row(row: int, textures: list[str]) -> dict:
    """调用 Y3 编辑器 MCP set_texture_row 接口。"""
    # TODO: 替换为真实 MCP 调用
    return {"success": True}


def mcp_get_terrain_row(row: int) -> dict:
    """调用 Y3 编辑器 MCP get_terrain_row 接口，读回实际地形。"""
    # TODO: 替换为真实 MCP 调用
    return {"cells": [], "error": None}


def mcp_get_decoration_presets(category: str = None) -> dict:
    """调用 Y3 编辑器 MCP get_decoration_presets 接口。"""
    # TODO: 替换为真实 MCP 调用
    return {"presets": []}


def mcp_place_decorations(decorations: list[dict]) -> dict:
    """调用 Y3 编辑器 MCP place_decorations 接口。"""
    # TODO: 替换为真实 MCP 调用
    return {"success": True, "failed": []}
