"""MCPClient — MCP stdio 协议客户端。

对接 AgentScope MCPClient（Task 4 填充 AgentScope 集成），
首期实现纯 Python stdio 子进程生命周期管理：
  connect()  — spawn 子进程 + MCP handshake → 返回 tools list
  call_tool() — 发送 JSON-RPC tool/call → 返回 result
  close()    — 终止子进程
"""
from __future__ import annotations
import asyncio
import json
import shutil
import sys
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class MCPTool:
    """MCP 工具描述（来自 tools/list 返回值）。"""
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)


class MCPClient:
    """stdio 协议 MCP 客户端 —— 不依赖 AgentScope 也可独立运行。"""

    def __init__(self, server_cmd: str, server_args: list[str] | None = None,
                 env: dict[str, str] | None = None):
        self.server_cmd = server_cmd
        self.server_args = server_args or []
        self.env = env
        self._proc: asyncio.subprocess.Process | None = None
        self._tools: list[MCPTool] = []
        self._next_id = 1
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self) -> list[MCPTool]:
        """spawn 子进程 → initialize → tools/list。"""
        if self._proc is not None:
            return self._tools
        # 记录 connect 时的事件循环 —— 供 _ensure_alive 检测跨 loop 失联
        self._loop = asyncio.get_running_loop()
        logger.info(f"MCPClient.connect() → {self.server_cmd} {' '.join(self.server_args)}")
        try:
            # Windows 下 npx / windows-mcp 等是 .cmd 批处理，create_subprocess_exec
            # 直接 spawn 会 WinError 2 —— 先用 shutil.which 按 PATHEXT 解析真实路径
            resolved = shutil.which(self.server_cmd) or self.server_cmd
            self._proc = await asyncio.create_subprocess_exec(
                resolved, *self.server_args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
                # 截图类工具（如 windows-mcp Screenshot）单行响应含 base64 图片，
                # 远超 StreamReader 默认 64KB 限制，放开到 32MB
                limit=32 * 1024 * 1024,
            )
        except FileNotFoundError as e:
            logger.error(f"MCPClient spawn failed: {e}")
            raise
        # initialize handshake
        init_id = await self._send({
            "jsonrpc": "2.0", "id": self._next_id, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "superagent", "version": "0.1.0"},
            },
        })
        await self._recv_response(init_id)
        # initialized notification
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        # tools/list
        list_id = await self._send({
            "jsonrpc": "2.0", "id": self._next_id, "method": "tools/list", "params": {},
        })
        resp = await self._recv_response(list_id)
        self._tools = [
            MCPTool(
                name=t["name"],
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
            )
            for t in resp.get("result", {}).get("tools", [])
        ]
        logger.info(f"MCPClient connected · {len(self._tools)} tools")
        return self._tools

    async def _ensure_alive(self) -> None:
        """跨事件循环失联自愈 —— build_agent_toolkit_sync 常在临时 loop（线程池
        或 asyncio.run）中 connect，该 loop 关闭后 stdio pipe transport 失效
        （表现为 'NoneType' object has no attribute 'send'）。检测到调用 loop
        与 connect loop 不一致时终止旧子进程并重建握手。"""
        loop = asyncio.get_running_loop()
        if self._proc is None:
            await self.connect()
            return
        if self._loop is loop:
            return
        logger.warning(
            f"MCPClient loop 已切换（connect={self._loop} → call={loop}），"
            f"重建子进程: {self.server_cmd}")
        self._kill_process_tree()
        self._proc = None
        self._tools = []
        self._next_id = 1
        # 等待被杀进程树释放 playwright profile 等资源后再重启
        await asyncio.sleep(1)
        await self.connect()

    def _kill_process_tree(self) -> None:
        """Windows 下终止整个进程树 —— self._proc.terminate() 只杀 npx.cmd
        包装进程，node 子进程与 chromium 孙进程会以孤儿身份存活并锁住
        playwright 持久化 profile，导致重建后的浏览器停留在 about:blank。"""
        if self._proc is None:
            return
        try:
            if sys.platform == "win32":
                import subprocess as _sp

                _sp.run(
                    ["taskkill", "/F", "/T", "/PID", str(self._proc.pid)],
                    capture_output=True, timeout=10,
                )
            else:
                self._proc.terminate()
        except Exception:
            pass

    async def call_tool(self, name: str,
                        arguments: dict[str, Any] | None = None) -> Any:
        """调用 MCP tool —— 支持超时。"""
        await self._ensure_alive()
        req_id = await self._send({
            "jsonrpc": "2.0", "id": self._next_id, "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })
        resp = await self._recv_response(req_id)
        if "error" in resp:
            err = resp["error"]
            raise RuntimeError(f"MCP tool '{name}' error: {err}")
        return resp.get("result", {})

    async def close(self) -> None:
        """终止子进程。"""
        if self._proc is None:
            return
        logger.info("MCPClient.close()")
        try:
            self._proc.terminate()
            try:
                await asyncio.wait_for(self._proc.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._proc.kill()
        except Exception:
            pass
        finally:
            # 显式关闭 stdio 管道，避免 Windows Proactor 事件循环
            # 在 GC 阶段抛 unclosed transport 警告
            for pipe in (self._proc.stdin, self._proc.stdout, self._proc.stderr):
                try:
                    if pipe is not None:
                        pipe.close()
                except Exception:
                    pass
            self._proc = None

    async def _send(self, msg: dict) -> int | None:
        """发送 JSON-RPC 消息，返回其请求 id（notification 返回 None）。"""
        assert self._proc and self._proc.stdin
        data = (json.dumps(msg) + "\n").encode()
        self._proc.stdin.write(data)
        await self._proc.stdin.drain()
        if "id" in msg and msg["method"] not in ("notifications/initialized",):
            req_id = msg["id"]
            self._next_id += 1
            return req_id
        return None

    async def _recv_response(self, expected_id: int | None = None) -> dict:
        """读取一条 JSON-RPC 响应 —— 按 id 过滤，跳过 notification/无关消息。"""
        assert self._proc and self._proc.stdout
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP process closed stdout")
            text = line.decode().strip()
            if not text.startswith("{"):
                continue
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                continue
            if expected_id is not None and obj.get("id") != expected_id:
                continue  # notification（logging/progress）或旧响应
            if "result" in obj or "error" in obj:
                return obj
            # 有 id 但既非请求也非响应的畸形消息 —— 继续等待
