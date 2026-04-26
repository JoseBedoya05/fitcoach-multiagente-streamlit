from __future__ import annotations

import json
import os
from typing import Optional

from openai import OpenAI

from src.config import LLM_MODEL
from src.llm.dispatcher import dispatch_tool
from src.llm.tool_schemas import TOOLS_SCHEMA


def get_openai_client() -> Optional[OpenAI]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return None
    return OpenAI(api_key=api_key)


def agent_run(
    system_prompt: str,
    user_message: str,
    tools: list = TOOLS_SCHEMA,
    model: str = LLM_MODEL,
    max_iters: int = 6,
    history: list | None = None,
) -> dict:
    """
    Ejecuta un agente con tool-calling.
    Retorna {"answer": str, "messages": list, "trace": list}.
    """
    client = get_openai_client()
    if client is None:
        return {
            "answer": "No se encontró OPENAI_API_KEY. Configura la clave en .env o en Streamlit Secrets.",
            "messages": [],
            "trace": [{"type": "error", "message": "OPENAI_API_KEY no configurada"}],
        }

    messages = history[:] if history else []
    if not messages or messages[0].get("role") != "system":
        messages = [{"role": "system", "content": system_prompt}] + messages
    messages.append({"role": "user", "content": user_message})

    trace = []

    for _ in range(max_iters):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.25,
        )
        msg = resp.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return {
                "answer": msg.content or "",
                "messages": messages,
                "trace": trace,
            }

        for tc in msg.tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except Exception:
                args = {}

            result = dispatch_tool(name, args)
            trace.append({
                "tool": name,
                "args": args,
                "result_preview": result[:900],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": name,
                "content": result,
            })

    return {
        "answer": "No pude cerrar la respuesta dentro del número máximo de iteraciones.",
        "messages": messages,
        "trace": trace,
    }
