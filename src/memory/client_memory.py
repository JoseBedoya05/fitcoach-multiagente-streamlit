from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config import MEMORY_DIR


def _memory_path(client_id: str) -> Path:
    return MEMORY_DIR / f"{str(client_id).upper()}.jsonl"


def save_episode(
    client_id: str,
    role: str,
    content: str,
    agent: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> dict:
    """Guarda un episodio append-only en memory/C{id}.jsonl."""
    episodio = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "client_id": str(client_id).upper(),
        "role": role,
        "agent": agent or "",
        "content": content,
        "metadata": metadata or {},
    }
    path = _memory_path(client_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(episodio, ensure_ascii=False) + "\n")
    return episodio


def load_recent_episodes(client_id: str, n: int = 20) -> list[dict]:
    path = _memory_path(client_id)
    if not path.exists():
        return []
    episodes = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                episodes.append(json.loads(line))
            except Exception:
                continue
    return episodes[-n:]


def memory_summary(client_id: str, n: int = 20) -> str:
    episodes = load_recent_episodes(client_id, n=n)
    if not episodes:
        return "Sin memoria previa para este cliente."
    lines = []
    for ep in episodes:
        role = ep.get("role", "")
        agent = ep.get("agent", "")
        content = str(ep.get("content", "")).replace("\n", " ")
        if len(content) > 350:
            content = content[:350] + "..."
        lines.append(f"- [{ep.get('ts', '')}] {role}/{agent}: {content}")
    return "\n".join(lines)


def clear_memory(client_id: str) -> None:
    path = _memory_path(client_id)
    if path.exists():
        path.unlink()
