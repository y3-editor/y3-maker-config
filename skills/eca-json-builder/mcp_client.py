# -*- coding: utf-8 -*-
"""极简 MCP(HTTP) 客户端 + 端口解析（供 verify_trigger.py / probe.py 复用）。

为什么需要它：会话里可能**没有挂载** y3editor / y3-helper 的 MCP 工具
（本地实测情况），但这两个 MCP 都是本地 HTTP 端点，
脚本直连即可完成「导入触发器 / 保存 / 读运行时状态」的闭环。

端口来源：依次查找 `.codex/config.toml`、`.codemaker/mcp_settings.json`、
`.y3maker/mcp_settings.json`，都找不到就用默认端口。
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request

DEFAULT_PORTS = {"y3editor": 8765, "y3-helper": 8766, "y3runtime": 8767}


def find_project_root(start=None):
    cur = os.path.abspath(start or os.getcwd())
    if os.path.isfile(cur):
        cur = os.path.dirname(cur)
    while True:
        if os.path.isdir(os.path.join(cur, "maps")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def resolve_ports(project_root=None):
    """返回 {server_name: port}；缺失项用 DEFAULT_PORTS 兜底。"""
    ports = dict(DEFAULT_PORTS)
    root = project_root or find_project_root()
    if not root:
        return ports
    for toml_path in (os.path.join(root, ".codex", "config.toml"),
                      os.path.join(root, ".codemaker", "config.toml")):
        if not os.path.isfile(toml_path):
            continue
        try:
            with open(toml_path, "r", encoding="utf-8") as f:
                current = None
                for line in f:
                    line = line.strip()
                    m = re.match(r"\[mcp_servers\.([^\]]+)\]", line)
                    if m:
                        current = m.group(1)
                        continue
                    m = re.match(r'url\s*=\s*"https?://127\.0\.0\.1:(\d+)', line)
                    if m and current:
                        ports[current] = int(m.group(1))
        except OSError:
            pass
        break
    for cfg_path in (os.path.join(root, ".codemaker", "mcp_settings.json"),
                     os.path.join(root, ".y3maker", "mcp_settings.json")):
        if not os.path.isfile(cfg_path):
            continue
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for name, cfg in (data.get("mcpServers") or {}).items():
                m = re.search(r"127\.0\.0\.1:(\d+)", cfg.get("url", ""))
                if m:
                    ports.setdefault(name, int(m.group(1)))
        except (ValueError, OSError):
            pass
    return ports


class McpClient:
    """对一个 MCP(HTTP) 端点做 initialize + tools/call。"""

    def __init__(self, port, timeout=120):
        self.url = "http://127.0.0.1:%d/mcp" % port
        self.timeout = timeout
        self.session = None

    def _post(self, payload):
        req = urllib.request.Request(
            self.url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     **({"Mcp-Session-Id": self.session} if self.session else {})},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            self.session = resp.headers.get("mcp-session-id") or self.session
            raw = resp.read().decode("utf-8", "replace")
        if raw.strip().startswith("{"):
            return json.loads(raw)
        out = None
        for line in raw.splitlines():
            if line.startswith("data:"):
                chunk = line[5:].strip()
                if chunk:
                    out = json.loads(chunk)
        return out

    def connect(self):
        self._post({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                               "clientInfo": {"name": "eca-json-builder", "version": "1.0"}}})
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def call(self, tool, arguments=None):
        """调用工具，返回 (text, payload)。text 为 content[0].text，payload 为可解析时的对象。"""
        res = self._post({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                          "params": {"name": tool, "arguments": arguments or {}}})
        content = ((res or {}).get("result") or {}).get("content") or []
        text = ""
        for item in content:
            if item.get("type") == "text":
                text = item.get("text", "")
                break
        payload = None
        try:
            payload = json.loads(text)
        except (ValueError, TypeError):
            pass
        if payload is None and (res or {}).get("result", {}).get("isError"):
            raise RuntimeError("MCP 工具 %s 调用失败：%s" % (tool, text))
        return text, payload


def editor_client(project_root=None):
    return McpClient(resolve_ports(project_root).get("y3editor", DEFAULT_PORTS["y3editor"])).connect()


def helper_client(project_root=None):
    return McpClient(resolve_ports(project_root).get("y3-helper", DEFAULT_PORTS["y3-helper"])).connect()
