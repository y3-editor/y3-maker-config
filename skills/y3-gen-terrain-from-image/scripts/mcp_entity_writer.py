#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcp_entity_writer.py
批量装饰物实体写入脚本 — 读取 decoration_entities.json，通过 HTTP 直接调用 MCP Server 的 entity_create_block。

用法:
  python mcp_entity_writer.py <decoration_entities.json> [options]

选项:
  --url URL          MCP Server URL（默认从 mcp_settings.json 读取）
  --batch-size N     每批实体数量（默认 200）
  --timeout N        MCP 调用超时秒数（默认 300）
  --dry-run          只读取并输出统计，不实际写入
  --download-models  写入前自动下载所有用到的模型资源

示例:
  python scripts/mcp_entity_writer.py output/decoration_entities.json --download-models
"""

import argparse
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
# MCP Client（与 mcp_batch_writer.py 共用协议）
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

    def _next_id(self):
        self._req_id += 1
        return self._req_id

    def _parse_sse(self, text):
        """从 SSE 格式 'data: {json}' 中提取 JSON 对象"""
        for line in text.strip().splitlines():
            line = line.strip()
            if line.startswith("data: "):
                return json.loads(line[6:])
        return json.loads(text)

    def initialize(self):
        """MCP initialize 握手"""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp_entity_writer", "version": "1.0"},
            },
        }
        resp = self.session.post(self.url, json=payload, headers=self._headers, timeout=10)
        resp.raise_for_status()
        data = self._parse_sse(resp.text)
        if "error" in data:
            raise RuntimeError(f"MCP initialize 失败: {data['error']}")

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
# MCP URL 发现（与 mcp_batch_writer.py 相同逻辑）
# ---------------------------------------------------------------------------

def discover_mcp_url(url_override=None):
    """按优先级查找 MCP Server URL"""
    if url_override:
        return url_override

    # 1. 环境变量
    env_url = os.environ.get("MCP_SERVER_URL")
    if env_url:
        return env_url

    # 2. mcp_settings.json（向上逐级搜索）
    search_dir = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        settings_path = os.path.join(search_dir, "mcp_settings.json")
        if os.path.exists(settings_path):
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
            url = settings.get("y3editor", {}).get("url")
            if url:
                return url
        parent = os.path.dirname(search_dir)
        if parent == search_dir:
            break
        search_dir = parent

    # 3. 默认
    return "http://127.0.0.1:25000/mcp"


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="批量装饰物实体写入 — 读取 JSON 通过 HTTP 直接调用 MCP entity_create_block"
    )
    parser.add_argument("entities_json", help="decoration_entities.json 路径")
    parser.add_argument("--url", default=None, help="MCP Server URL（默认自动发现）")
    parser.add_argument("--batch-size", type=int, default=200, help="每批实体数量（默认 200）")
    parser.add_argument("--timeout", type=int, default=300, help="MCP 调用超时秒数（默认 300）")
    parser.add_argument("--dry-run", action="store_true", help="只读取并输出统计，不实际写入")
    parser.add_argument("--download-models", action="store_true", help="写入前自动下载所有用到的模型资源")
    parser.add_argument("--delay", type=float, default=1.0, help="每批之间的延迟秒数（默认 1.0）")
    args = parser.parse_args()

    # --- Step 1: 读取实体 JSON ---
    print("=" * 60)
    print("  MCP Entity Writer v1.0")
    print("=" * 60)

    if not os.path.exists(args.entities_json):
        print(f"\n❌ 文件不存在: {args.entities_json}")
        sys.exit(1)

    with open(args.entities_json, "r", encoding="utf-8") as f:
        entities = json.load(f)

    if not isinstance(entities, list):
        print(f"\n❌ JSON 根元素必须是数组，实际类型: {type(entities).__name__}")
        sys.exit(1)

    print(f"\n[Step 1] 读取 {len(entities)} 个实体")

    # --- 统计 ---
    model_ids = set()
    type_counts = {}
    for ent in entities:
        mid = ent.get("model_id")
        if mid:
            model_ids.add(mid)
        # 按 model_id 统计
        key = str(mid) if mid else "unknown"
        type_counts[key] = type_counts.get(key, 0) + 1

    print(f"   模型种类: {len(model_ids)}")
    print(f"   模型 ID: {sorted(model_ids)}")
    for mid, cnt in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"     model {mid}: {cnt} 个")

    total_batches = (len(entities) + args.batch_size - 1) // args.batch_size
    print(f"   将分 {total_batches} 批写入（每批 {args.batch_size} 个）")

    if args.dry_run:
        print("\n🏁 --dry-run 模式，不实际写入。")
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
        print(f"   ✅ MCP 连接成功: {info[:80]}...")
    except Exception as e:
        print(f"   ⚠️ 探活失败: {e}")
        sys.exit(1)

    # --- Step 3: 下载模型资源（可选） ---
    if args.download_models and model_ids:
        print(f"\n[Step 3] 下载 {len(model_ids)} 种模型资源 ...")
        for mid in sorted(model_ids):
            try:
                result = mcp.call_tool("download_editor_model_resource", {"model_id": mid})
                print(f"   ✅ model {mid}: {result[:60] if result else 'ok'}")
            except Exception as e:
                print(f"   ⚠️ model {mid}: {e}")
            time.sleep(0.3)
    else:
        print(f"\n[Step 3] 跳过模型下载（{'未指定 --download-models' if not args.download_models else '无模型'}）")

    # --- Step 4: 分批写入 ---
    print(f"\n[Step 4] 开始分批写入 ...")
    total_ok = 0
    total_err = 0

    for batch_idx in range(total_batches):
        start = batch_idx * args.batch_size
        end = min(start + args.batch_size, len(entities))
        batch = entities[start:end]

        print(f"\n   批次 {batch_idx + 1}/{total_batches}: 实体 [{start}..{end - 1}] ({len(batch)} 个) ...", end=" ")

        try:
            result = mcp.call_tool("entity_create_block", {"entities": batch})
            print(f"✅ {result[:80] if result else 'ok'}")
            total_ok += len(batch)
        except Exception as e:
            print(f"❌ {e}")
            total_err += len(batch)

        if batch_idx < total_batches - 1:
            time.sleep(args.delay)

    # --- Step 5: 总结 ---
    print(f"\n{'=' * 60}")
    print(f"  写入完成!")
    print(f"  成功: {total_ok} 个实体")
    if total_err > 0:
        print(f"  失败: {total_err} 个实体")
    print(f"{'=' * 60}")

    # 输出机器可读结果
    summary = {
        "status": "all_done",
        "total": len(entities),
        "success": total_ok,
        "failed": total_err,
        "batches": total_batches,
        "models": len(model_ids),
    }
    print(f'\nENTITY_RESULT:{json.dumps(summary, ensure_ascii=False)}')


if __name__ == "__main__":
    main()
