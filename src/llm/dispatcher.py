from __future__ import annotations

import json
from typing import Any, Dict

from src.config import USE_MCP_SERVER
from src.mcp_tools import local_tools
from src.rag.rag_search import rag_search


MCP_TOOL_NAMES = {
    "get_client",
    "compute_imc",
    "compute_tmb_tdee",
    "plan_macros",
    "recommend_exercises",
    "register_measurement",
    "list_progress",
    "detect_risk",
}


def _safe_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def call_local_tool(name: str, args: Dict[str, Any]) -> Any:
    if name == "get_client":
        return local_tools.get_client(**args)
    if name == "compute_imc":
        return local_tools.compute_imc(**args)
    if name == "compute_tmb_tdee":
        return local_tools.compute_tmb_tdee(**args)
    if name == "plan_macros":
        return local_tools.plan_macros(**args)
    if name == "recommend_exercises":
        return local_tools.recommend_exercises(**args)
    if name == "register_measurement":
        return local_tools.register_measurement(**args)
    if name == "list_progress":
        return local_tools.list_progress(**args)
    if name == "detect_risk":
        return local_tools.detect_risk(**args)
    if name == "rag_search":
        return rag_search(**args)
    raise ValueError(f"Tool no registrada: {name}")


def dispatch_tool(name: str, args: Dict[str, Any]) -> str:
    """Ejecuta tool local o MCP y devuelve JSON serializado para OpenAI tool-calling."""
    try:
        if USE_MCP_SERVER and name in MCP_TOOL_NAMES:
            from src.mcp_tools.mcp_client import call_mcp_tool
            result = call_mcp_tool(name, args)
        else:
            result = call_local_tool(name, args)

        # Reducir texto RAG para no inflar tokens.
        if name == "rag_search" and isinstance(result, list):
            result = [
                {
                    **r,
                    "texto": str(r.get("texto", ""))[:700],
                }
                for r in result
            ]

        return _safe_json(result)
    except Exception as e:
        return _safe_json({"error": str(e), "tool": name, "args": args})
