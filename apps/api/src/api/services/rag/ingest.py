from __future__ import annotations

from pathlib import Path

from api.config import get_settings
from api.services.rag.chunker import chunk_documents
from api.services.rag.embedding_client import EmbeddingClient, OllamaEmbeddingClient
from api.services.rag.loader import load_documents
from api.services.rag.sqlite_store import persist_sqlite_index
from api.services.rag.types import IngestionSummary


def ingest_documents(
    *,
    source_dir: Path,
    db_path: Path,
    chunk_size: int,
    chunk_overlap: int,
    embedding_client: EmbeddingClient | None = None,
) -> IngestionSummary:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    if embedding_client is None:
        settings = get_settings()
        embedding_client = OllamaEmbeddingClient(
            base_url=settings.ollama_embed_base_url,
            model=settings.ollama_embed_model,
            timeout_seconds=settings.ollama_timeout_seconds,
        )

    documents = load_documents(source_dir)
    chunks = chunk_documents(
        documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    embeddings = embedding_client.embed_texts([chunk.text for chunk in chunks])
    index_file = persist_sqlite_index(
        db_path,
        documents=documents,
        chunks=chunks,
        embeddings=embeddings,
    )

    return IngestionSummary(
        document_count=len(documents),
        chunk_count=len(chunks),
        output_dir=str(db_path.parent),
        index_file=str(index_file),
    )
