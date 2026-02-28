from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDocument:
    doc_id: str
    source_path: str
    text: str


@dataclass(frozen=True)
class ChunkRecord:
    chunk_id: str
    doc_id: str
    source_path: str
    text: str


@dataclass(frozen=True)
class IngestionSummary:
    document_count: int
    chunk_count: int
    output_dir: str
    index_file: str
