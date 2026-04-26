"""
Construye el índice RAG local en rag_store/ desde documentos ubicados en docs/.

Uso:
    python scripts/build_rag_index.py

Estructura esperada:
    docs/
      ENTRENADOR/
      NUTRICION/
      RENDIMIENTO/
      CLIENTES/
        HIPERTROFIA/
        BAJAR/
        OBESIDAD/
        POST_CIRUGIA/
"""

from __future__ import annotations

import shutil
from pathlib import Path

from tqdm.auto import tqdm

from src.config import DOCS_DIR, EMBED_MODEL, RAG_STORE_DIR


CATEGORIAS = {"RENDIMIENTO", "NUTRICION", "ENTRENADOR", "CLIENTES"}
SUBCATEGORIAS = {"POST_CIRUGIA", "OBESIDAD", "HIPERTROFIA", "BAJAR"}


def clasificar_ruta(path: Path) -> dict:
    rel = path.relative_to(DOCS_DIR)
    partes = [p.upper() for p in rel.parts]
    categoria = ""
    subcategoria = ""
    for p in partes:
        if p in CATEGORIAS and not categoria:
            categoria = p
        if p in SUBCATEGORIAS and not subcategoria:
            subcategoria = p
    return {
        "archivo": str(rel),
        "categoria": categoria,
        "subcategoria": subcategoria,
        "source": str(rel),
    }


def main():
    if not DOCS_DIR.exists() or not any(DOCS_DIR.rglob("*")):
        raise SystemExit(
            f"No hay documentos en {DOCS_DIR}. Copia PDFs/DOCX/TXT/MD antes de indexar."
        )

    from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_chroma import Chroma

    loaders = {
        ".pdf": PyPDFLoader,
        ".docx": Docx2txtLoader,
        ".txt": lambda p: TextLoader(p, encoding="utf-8"),
        ".md": UnstructuredMarkdownLoader,
    }

    documentos = []
    files = [p for p in DOCS_DIR.rglob("*") if p.is_file() and p.suffix.lower() in loaders]
    print(f"Documentos detectados: {len(files)}")

    for path in tqdm(files, desc="Cargando documentos"):
        loader_cls = loaders[path.suffix.lower()]
        try:
            loader = loader_cls(str(path))
            docs = loader.load()
            metadata = clasificar_ruta(path)
            for d in docs:
                d.metadata.update(metadata)
            documentos.extend(docs)
        except Exception as e:
            print(f"[WARN] No se pudo cargar {path}: {e}")

    splitter = RecursiveCharacterTextSplitter(chunk_size=900, chunk_overlap=150)
    chunks = splitter.split_documents(documentos)
    print(f"Chunks generados: {len(chunks)}")

    if RAG_STORE_DIR.exists():
        shutil.rmtree(RAG_STORE_DIR)
    RAG_STORE_DIR.mkdir(parents=True, exist_ok=True)

    emb = HuggingFaceEmbeddings(
        model_name=EMBED_MODEL,
        encode_kwargs={"normalize_embeddings": True},
    )

    Chroma.from_documents(
        documents=chunks,
        embedding=emb,
        persist_directory=str(RAG_STORE_DIR),
    )

    print(f"Índice RAG creado en: {RAG_STORE_DIR}")


if __name__ == "__main__":
    main()
