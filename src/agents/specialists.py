from __future__ import annotations

from src.agents.prompts import SYSTEM_ANALISTA, SYSTEM_ENTRENADOR, SYSTEM_NUTRICIONISTA
from src.config import LLM_MODEL
from src.llm.openai_agent import agent_run
from src.llm.tool_schemas import TOOLS_SCHEMA


def _ask_specialist(system_prompt: str, task: str, client_id: str | None = None, model: str = LLM_MODEL) -> str:
    user_msg = task if not client_id else f"[Cliente: {client_id}]\n{task}"
    out = agent_run(
        system_prompt=system_prompt,
        user_message=user_msg,
        tools=TOOLS_SCHEMA,
        model=model,
        max_iters=6,
    )
    return out["answer"]


def ask_trainer(client_id: str, task: str) -> str:
    return _ask_specialist(SYSTEM_ENTRENADOR, task, client_id)


def ask_nutritionist(client_id: str, task: str) -> str:
    return _ask_specialist(SYSTEM_NUTRICIONISTA, task, client_id)


def ask_analyst(client_id: str, task: str) -> str:
    return _ask_specialist(SYSTEM_ANALISTA, task, client_id)
