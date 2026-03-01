from dataclasses import dataclass
from functools import lru_cache
import os


def _to_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value: str | None, *, default: int, minimum: int) -> int:
    if value is None:
        return default
    parsed = int(value)
    return max(minimum, parsed)


@dataclass(frozen=True)
class Settings:
    database_url: str
    db_echo: bool
    rag_source_dir: str
    rag_index_dir: str
    rag_chunk_size: int
    rag_chunk_overlap: int
    rag_embedding_dim: int
    ollama_base_url: str
    ollama_model: str
    ollama_fallback_model: str
    ollama_timeout_seconds: float


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "API_DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/industrial_ai",
        ),
        db_echo=_to_bool(os.getenv("API_DB_ECHO"), default=False),
        rag_source_dir=os.getenv("RAG_SOURCE_DIR", "/workspace/data/sample_docs"),
        rag_index_dir=os.getenv("RAG_INDEX_DIR", "/workspace/data/rag_index"),
        rag_chunk_size=_to_int(os.getenv("RAG_CHUNK_SIZE"), default=500, minimum=100),
        rag_chunk_overlap=_to_int(os.getenv("RAG_CHUNK_OVERLAP"), default=50, minimum=0),
        rag_embedding_dim=_to_int(os.getenv("RAG_EMBEDDING_DIM"), default=32, minimum=8),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b-instruct-q4_K_M"),
        ollama_fallback_model=os.getenv("OLLAMA_FALLBACK_MODEL", "qwen2.5:3b-instruct-q4_K_M"),
        ollama_timeout_seconds=float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "30")),
    )
