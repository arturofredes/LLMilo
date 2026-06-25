from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] | None = None
    cwd: str | Path | None = None


DEFAULT_SERVER = MCPServerConfig(
    name="llmilo-tools",
    command=sys.executable,
    args=[str(Path(__file__).parent / "server.py")],
)


def mcp_tool_to_litellm(tool: Any) -> dict:
    schema = tool.inputSchema if hasattr(tool, "inputSchema") else {}
    if "title" in schema:
        del schema["title"]
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": schema,
        },
    }


class MCPToolClient:
    def __init__(self, servers: list[MCPServerConfig] | None = None):
        self.servers = servers or [DEFAULT_SERVER]
        self._exit_stack = AsyncExitStack()
        self._sessions: dict[str, ClientSession] = {}
        self._tools: list[dict] = []
        self._tool_to_server: dict[str, str] = {}

    async def start(self):
        await self._exit_stack.__aenter__()
        for server in self.servers:
            session = await self._connect(server)
            self._sessions[server.name] = session
        await self._refresh_tools()

    async def stop(self):
        await self._exit_stack.aclose()
        self._sessions.clear()
        self._tools.clear()
        self._tool_to_server.clear()

    async def _connect(self, config: MCPServerConfig) -> ClientSession:
        server_params = StdioServerParameters(
            command=config.command,
            args=config.args,
            env=config.env,
            cwd=config.cwd,
        )
        read_stream, write_stream = await self._exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        session = await self._exit_stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await session.initialize()
        return session

    async def _refresh_tools(self):
        self._tools.clear()
        self._tool_to_server.clear()
        for server_name, session in self._sessions.items():
            result = await session.list_tools()
            for tool in result.tools:
                self._tools.append(mcp_tool_to_litellm(tool))
                self._tool_to_server[tool.name] = server_name

    def get_tools(self) -> list[dict]:
        return list(self._tools)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        server_name = self._tool_to_server.get(name)
        if server_name is None:
            raise ValueError(f"Unknown tool: {name}")
        session = self._sessions[server_name]
        result = await session.call_tool(name, arguments)
        parts = []
        for content in result.content:
            if hasattr(content, "text"):
                parts.append(content.text)
            else:
                parts.append(str(content))
        return "\n".join(parts)
