from __future__ import annotations

import os
from typing import Literal

from src.agents.coordinator import coordinator_run
from src.agents.prompts import AGENT_PROMPTS
from src.config import LLM_MODEL
from src.llm.openai_agent import agent_run
from src.llm.tool_schemas import TOOLS_SCHEMA
from src.mcp_tools.local_tools import (
    compute_imc,
    compute_tmb_tdee,
    get_client,
    plan_macros,
    recommend_exercises,
)
from src.memory.client_memory import memory_summary, save_episode


AgentName = Literal["Coordinador", "Entrenador", "Nutricionista", "Analista"]


def _local_demo_response(user_input: str, client_id: str, agent_name: str) -> dict:
    """Respuesta determinística de respaldo si no hay API key."""
    c = get_client(client_id)
    if "error" in c:
        return {"respuesta": c["error"], "trace": []}

    imc = compute_imc(c["weight_kg"], c["height_cm"])
    tdee = compute_tmb_tdee(
        weight_kg=c["weight_kg"],
        height_cm=c["height_cm"],
        age=c["age"],
        gender=c["gender"],
        activity="moderada",
    )
    macros = plan_macros(tdee=tdee["tdee"], goal=c["goal"])
    ejercicios = recommend_exercises(c.get("category", ""), c.get("restrictions", []))[:8]

    answer = f"""
### Respuesta demo local

No se encontró `OPENAI_API_KEY`, por eso se generó una respuesta determinística con las herramientas locales del proyecto.

**Cliente:** {c['id']} — {c['name']}  
**Objetivo:** {c['goal']}  
**Restricciones:** {', '.join(c.get('restrictions') or ['Sin restricciones registradas'])}

**Línea base**
- IMC: {imc['imc']} — categoría `{imc['categoria']}`
- TMB estimada: {tdee['tmb']} kcal/día
- TDEE estimado: {tdee['tdee']} kcal/día

**Macros sugeridos**
- kcal objetivo: {macros['kcal_objetivo']}
- proteína: {macros['proteina_g']} g
- carbohidratos: {macros['carbos_g']} g
- grasas: {macros['grasas_g']} g

**Ejercicios aptos de base**
{chr(10).join([f"- {e['ejercicio']} ({e['grupo']}, impacto {e['impacto']})" for e in ejercicios])}

Para activar el sistema multiagente con razonamiento LLM, configura `OPENAI_API_KEY`.
"""
    trace = [
        {"tool": "get_client", "args": {"client_id": client_id}, "result_preview": str(c)[:500]},
        {"tool": "compute_imc", "args": {"weight_kg": c["weight_kg"], "height_cm": c["height_cm"]}, "result_preview": str(imc)},
        {"tool": "compute_tmb_tdee", "args": {"activity": "moderada"}, "result_preview": str(tdee)},
        {"tool": "plan_macros", "args": {"goal": c["goal"]}, "result_preview": str(macros)},
        {"tool": "recommend_exercises", "args": {"category": c.get("category", "")}, "result_preview": str(ejercicios)[:500]},
    ]
    return {"respuesta": answer.strip(), "trace": trace}


def run_multiagent(
    user_input: str,
    client_id: str = "C1",
    agent_name: AgentName = "Coordinador",
    model: str = LLM_MODEL,
    use_memory: bool = True,
) -> dict:
    """
    Punto central usado por Streamlit.
    Retorna:
    - respuesta
    - agente
    - trace
    - memoria_usada
    """
    client_id = str(client_id).upper()
    agent_name = agent_name if agent_name in AGENT_PROMPTS else "Coordinador"

    if not os.getenv("OPENAI_API_KEY"):
        out = _local_demo_response(user_input, client_id, agent_name)
        return {
            "respuesta": out["respuesta"],
            "agente": f"{agent_name} (demo local)",
            "trace": out["trace"],
            "memoria_usada": False,
        }

    memoria_txt = memory_summary(client_id) if use_memory else "Memoria desactivada en la UI."
    user_msg = (
        f"[Cliente activo: {client_id}]\n"
        f"[Memoria reciente]\n{memoria_txt}\n\n"
        f"[Solicitud]\n{user_input}"
    )

    if use_memory:
        save_episode(client_id, role="user", content=user_input, agent=agent_name)

    if agent_name == "Coordinador":
        out = coordinator_run(user_message=user_msg, client_id=client_id, model=model)
    else:
        out = agent_run(
            system_prompt=AGENT_PROMPTS[agent_name],
            user_message=user_msg,
            tools=TOOLS_SCHEMA,
            model=model,
            max_iters=6,
        )

    answer = out.get("answer", "")

    if use_memory:
        save_episode(
            client_id,
            role="assistant",
            content=answer,
            agent=agent_name,
            metadata={"trace": out.get("trace", [])},
        )

    return {
        "respuesta": answer,
        "agente": agent_name,
        "trace": out.get("trace", []),
        "memoria_usada": use_memory,
    }
