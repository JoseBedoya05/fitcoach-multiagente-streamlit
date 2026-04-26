from __future__ import annotations

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Any

import nest_asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.config import BASE_DIR

nest_asyncio.apply()
SERVER_PATH = str(BASE_DIR / "src" / "mcp_server_gym.py")


@asynccontextmanager
async def open_mcp_session():
    """Abre una sesión MCP stdio contra src/mcp_server_gym.py."""
    errlog = open(os.devnull, "w")
    params = StdioServerParameters(command=sys.executable, args=[SERVER_PATH])
    try:
        async with stdio_client(params, errlog=errlog) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                yield session
    finally:
        try:
            errlog.close()
        except Exception:
            pass


def run_async(coro):
    """Ejecuta una corrutina incluso dentro del loop que usa Streamlit."""
    try:
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def mcp_result(resp: Any):
    """Extrae salida de una respuesta MCP call_tool cubriendo variantes frecuentes."""
    for attr in ("structuredContent", "structured_content"):
        sc = getattr(resp, attr, None)
        if sc is not None:
            if isinstance(sc, dict) and set(sc.keys()) == {"result"}:
                return sc["result"]
            return sc

    bloques = getattr(resp, "content", []) or []
    textos = []
    for b in bloques:
        t = getattr(b, "text", None)
        if t:
            textos.append(t)

    if not textos:
        return {}

    joined = "\n".join(textos)
    try:
        return json.loads(joined)
    except Exception:
        return joined


async def _call_tool_async(name: str, args: dict[str, Any]) -> Any:
    async with open_mcp_session() as session:
        resp = await session.call_tool(name, args)
        return mcp_result(resp)


def call_mcp_tool(name: str, args: dict[str, Any]) -> Any:
    return run_async(_call_tool_async(name, args))


async def _list_tools_async():
    async with open_mcp_session() as session:
        resp = await session.list_tools()
        return resp.tools


def list_mcp_tools():
    return run_async(_list_tools_async())
