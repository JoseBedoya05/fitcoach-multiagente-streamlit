from __future__ import annotations

from pathlib import Path
from typing import Optional, List, Dict

from src.config import ENABLE_RAG, RAG_STORE_DIR, EMBED_MODEL


def rag_search(
    query: str,
    k: int = 4,
    categoria: Optional[str] = None,
    subcategoria: Optional[str] = None,
) -> List[Dict]:
    """
    Busca evidencia documental en un Chroma persistido.

    Si no existe rag_store/ o no están instaladas las dependencias pesadas,
    devuelve una lista vacía con un mensaje controlado para no romper la UI.
    """
    if not ENABLE_RAG:
        return [{
            "texto": "RAG desactivado por configuración ENABLE_RAG=false.",
            "archivo": "N/A",
            "categoria": categoria or "",
            "subcategoria": subcategoria or "",
            "score": None,
        }]

    if not RAG_STORE_DIR.exists() or not any(RAG_STORE_DIR.iterdir()):
        return [{
            "texto": "No se encontró un índice RAG en rag_store/. Ejecuta scripts/build_rag_index.py o copia tu vectorstore fuera de GitHub.",
            "archivo": "N/A",
            "categoria": categoria or "",
            "subcategoria": subcategoria or "",
            "score": None,
        }]

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_chroma import Chroma
    except Exception as e:
        return [{
            "texto": f"No se pudieron importar dependencias RAG: {e}",
            "archivo": "N/A",
            "categoria": categoria or "",
            "subcategoria": subcategoria or "",
            "score": None,
        }]

    try:
        emb = HuggingFaceEmbeddings(
            model_name=EMBED_MODEL,
            encode_kwargs={"normalize_embeddings": True},
        )
        db = Chroma(persist_directory=str(RAG_STORE_DIR), embedding_function=emb)

        filtros = []
        if categoria:
            filtros.append({"categoria": categoria.upper()})
        if subcategoria:
            filtros.append({"subcategoria": subcategoria.upper()})

        where = None
        if len(filtros) == 1:
            where = filtros[0]
        elif len(filtros) > 1:
            where = {"$and": filtros}

        docs = db.similarity_search_with_score(query, k=int(k), filter=where)
        out = []
        for doc, score in docs:
            md = doc.metadata or {}
            out.append({
                "texto": doc.page_content[:900],
                "archivo": md.get("source") or md.get("archivo") or "desconocido",
                "categoria": md.get("categoria", ""),
                "subcategoria": md.get("subcategoria", ""),
                "score": float(score) if score is not None else None,
            })
        return out
    except Exception as e:
        return [{
            "texto": f"Error consultando RAG: {e}",
            "archivo": "N/A",
            "categoria": categoria or "",
            "subcategoria": subcategoria or "",
            "score": None,
        }]
