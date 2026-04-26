from __future__ import annotations

import json
import os

from openai import OpenAI

from src.agents.prompts import SYSTEM_COORDINADOR
from src.config import LLM_MODEL
from src.llm.coordinator_dispatcher import dispatch_tool_coord
from src.llm.tool_schemas import SUBAGENT_TOOLS, TOOLS_SCHEMA


COORDINATOR_TOOLS_SCHEMA = TOOLS_SCHEMA + SUBAGENT_TOOLS


def coordinator_run(
    user_message: str,
    client_id: str | None = None,
    model: str = LLM_MODEL,
    max_iters: int = 8,
) -> dict:
    """Ejecuta el Coordinador con tools base y subagentes."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return {
            "answer": "No se encontró OPENAI_API_KEY. Configura la clave en .env o Streamlit Secrets.",
            "messages": [],
            "trace": [{"type": "error", "message": "OPENAI_API_KEY no configurada"}],
        }

    client = OpenAI(api_key=api_key)
    sys_prompt = SYSTEM_COORDINADOR
    if client_id:
        sys_prompt += f"\n\nCliente activo seleccionado por la UI: {client_id}. Usa este ID cuando necesites consultar tools o subagentes."

    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": user_message},
    ]

    trace = []
    for _ in range(max_iters):
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=COORDINATOR_TOOLS_SCHEMA,
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

            # Completa client_id si el modelo omitió el cliente activo.
            if client_id and name in {
                "get_client", "register_measurement", "list_progress", "detect_risk",
                "ask_trainer", "ask_nutritionist", "ask_analyst",
            } and "client_id" not in args:
                args["client_id"] = client_id

            result = dispatch_tool_coord(name, args)
            trace.append({"tool": name, "args": args, "result_preview": result[:900]})
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
