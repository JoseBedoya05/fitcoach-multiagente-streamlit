from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Carga variables locales si existe .env. En Streamlit Cloud usa st.secrets o variables de entorno.
load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
DOCS_DIR = BASE_DIR / "docs"
RAG_STORE_DIR = BASE_DIR / "rag_store"
MEMORY_DIR = BASE_DIR / "memory"
REPORTS_DIR = BASE_DIR / "reports"
OUTPUTS_DIR = BASE_DIR / "outputs"

for _dir in [DATA_DIR, DOCS_DIR, RAG_STORE_DIR, MEMORY_DIR, REPORTS_DIR, OUTPUTS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
LLM_MODEL_FAST = os.getenv("LLM_MODEL_FAST", "gpt-4o-mini")
EMBED_MODEL = os.getenv("EMBED_MODEL", "intfloat/multilingual-e5-small")

# Por defecto se llama el dispatcher local para que Streamlit Cloud sea estable.
# Si quieres forzar llamadas por MCP stdio, define USE_MCP_SERVER=true.
USE_MCP_SERVER = os.getenv("USE_MCP_SERVER", "false").lower() in {"1", "true", "yes", "y"}

# RAG puede quedarse apagado si no has indexado documentos o no quieres cargar embeddings.
ENABLE_RAG = os.getenv("ENABLE_RAG", "true").lower() in {"1", "true", "yes", "y"}
