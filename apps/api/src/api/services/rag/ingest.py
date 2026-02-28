from __future__ import annotations

from pathlib import Path

from api.services.rag.chunker import chunk_documents
from api.services.rag.embedder import embed_chunks
from api.services.rag.index_store import persist_index
from api.services.rag.loader import load_documents
from api.services.rag.types import IngestionSummary


def ingest_documents(
    *,
    source_dir: Path,
    output_dir: Path,
    chunk_size: int,
    chunk_overlap: int,
    embedding_dim: int,
) -> IngestionSummary:
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    documents = load_documents(source_dir)
    chunks = chunk_documents(
        documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    embeddings = embed_chunks(chunks, dimensions=embedding_dim)
    index_file = persist_index(output_dir, chunks=chunks, embeddings=embeddings)

    return IngestionSummary(
        document_count=len(documents),
        chunk_count=len(chunks),
        output_dir=str(output_dir),
        index_file=str(index_file),
    )
