from api.config import get_settings


def test_rag_db_path_uses_explicit_env(monkeypatch) -> None:
    monkeypatch.setenv("RAG_INDEX_DIR", "data/custom-index")
    monkeypatch.setenv("RAG_DB_PATH", "data/override/r4.db")

    settings = get_settings()

    assert settings.rag_index_dir == "data/custom-index"
    assert settings.rag_db_path == "data/override/r4.db"


def test_rag_db_path_defaults_to_index_dir(monkeypatch) -> None:
    monkeypatch.setenv("RAG_INDEX_DIR", "data/custom-index")
    monkeypatch.delenv("RAG_DB_PATH", raising=False)

    settings = get_settings()

    assert settings.rag_db_path.endswith("data/custom-index/rag.db")
