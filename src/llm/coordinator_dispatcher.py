from __future__ import annotations

import json
from typing import Any, Dict

from src.agents.specialists import ask_analyst, ask_nutritionist, ask_trainer
from src.llm.dispatcher import dispatch_tool


SUBAGENT_NAMES = {"ask_trainer", "ask_nutritionist", "ask_analyst"}


def dispatch_tool_coord(name: str, args: Dict[str, Any]) -> str:
    """Dispatcher extendido para el Coordinador: tools base + subagentes."""
    try:
        if name == "ask_trainer":
            result = ask_trainer(**args)
        elif name == "ask_nutritionist":
            result = ask_nutritionist(**args)
        elif name == "ask_analyst":
            result = ask_analyst(**args)
        else:
            return dispatch_tool(name, args)

        return json.dumps({"respuesta_subagente": result}, ensure_ascii=False, default=str)
    except Exception as e:
        return json.dumps({"error": str(e), "tool": name, "args": args}, ensure_ascii=False)
