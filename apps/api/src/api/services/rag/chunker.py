from __future__ import annotations

from api.services.rag.types import ChunkRecord, SourceDocument


def _chunk_text(text: str, *, chunk_size: int, chunk_overlap: int) -> list[str]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be >= 0")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    chunks: list[str] = []
    cursor = 0
    text_length = len(text)

    while cursor < text_length:
        end = min(text_length, cursor + chunk_size)
        chunk = text[cursor:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= text_length:
            break
        cursor = end - chunk_overlap

    return chunks


def chunk_documents(
    documents: list[SourceDocument],
    *,
    chunk_size: int,
    chunk_overlap: int,
) -> list[ChunkRecord]:
    chunk_records: list[ChunkRecord] = []

    for document in documents:
        chunks = _chunk_text(
            document.text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for index, chunk_text in enumerate(chunks):
            chunk_records.append(
                ChunkRecord(
                    chunk_id=f"{document.doc_id}-{index:04d}",
                    doc_id=document.doc_id,
                    source_path=document.source_path,
                    text=chunk_text,
                )
            )

    return chunk_records
