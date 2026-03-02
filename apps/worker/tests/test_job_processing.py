from sqlalchemy import create_engine, text

from worker.main import _claim_next_rag_reindex_job, _coerce_job_id, _process_claimed_job


def _create_schema(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE jobs (
                    id VARCHAR(64) PRIMARY KEY,
                    type VARCHAR(32) NOT NULL,
                    status VARCHAR(32) NOT NULL,
                    payload_json TEXT,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    max_attempts INTEGER NOT NULL DEFAULT 3,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    finished_at TIMESTAMP,
                    error TEXT,
                    result_json TEXT
                )
                """
            )
        )


def test_coerce_job_id_converts_numeric_string_to_int() -> None:
    assert _coerce_job_id("42") == 42
    assert _coerce_job_id(7) == 7


def test_worker_claim_and_execute_success(tmp_path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'worker-success.db'}")
    _create_schema(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO jobs (id, type, status, payload_json, attempts, max_attempts)
                VALUES ('1', 'rag_reindex', 'queued', '{"source":"test"}', 0, 3)
                """
            )
        )

    job = _claim_next_rag_reindex_job(engine)
    assert job is not None
    assert job["id"] == 1

    _process_claimed_job(engine, job, runner=lambda _: {"chunks": 12, "duration_ms": 30})

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT status, attempts, result_json, error FROM jobs WHERE id = '1'")
        ).fetchone()

    assert row is not None
    assert row[0] == "succeeded"
    assert row[1] == 0
    assert "\"chunks\": 12" in str(row[2])
    assert row[3] is None


def test_worker_retries_then_fails_after_max_attempts(tmp_path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'worker-fail.db'}")
    _create_schema(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO jobs (id, type, status, attempts, max_attempts)
                VALUES ('2', 'rag_reindex', 'queued', 0, 2)
                """
            )
        )

    job = _claim_next_rag_reindex_job(engine)
    assert job is not None
    _process_claimed_job(engine, job, runner=lambda _: (_ for _ in ()).throw(RuntimeError("boom-1")))

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT status, attempts, error FROM jobs WHERE id = '2'")
        ).fetchone()

    assert row is not None
    assert row[0] == "queued"
    assert row[1] == 1
    assert "boom-1" in str(row[2])

    job = _claim_next_rag_reindex_job(engine)
    assert job is not None
    _process_claimed_job(engine, job, runner=lambda _: (_ for _ in ()).throw(RuntimeError("boom-2")))

    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT status, attempts, error FROM jobs WHERE id = '2'")
        ).fetchone()

    assert row is not None
    assert row[0] == "failed"
    assert row[1] == 2
    assert "boom-2" in str(row[2])
