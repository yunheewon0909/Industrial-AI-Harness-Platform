from datetime import datetime, timezone

from sqlalchemy import create_engine, text

from worker.main import _upsert_heartbeat


def test_upsert_heartbeat_inserts_and_updates_single_row(tmp_path) -> None:
    sqlite_db_path = tmp_path / "worker-tests.db"
    engine = create_engine(f"sqlite+pysqlite:///{sqlite_db_path}")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE worker_heartbeats (
                    worker_id VARCHAR(64) PRIMARY KEY,
                    last_heartbeat TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )

    _upsert_heartbeat(engine, "worker-test", datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc))
    _upsert_heartbeat(engine, "worker-test", datetime(2026, 1, 1, 0, 1, 0, tzinfo=timezone.utc))

    with engine.connect() as connection:
        row_count = connection.execute(text("SELECT COUNT(*) FROM worker_heartbeats")).scalar_one()
        last_heartbeat = connection.execute(
            text("SELECT last_heartbeat FROM worker_heartbeats WHERE worker_id = :worker_id"),
            {"worker_id": "worker-test"},
        ).scalar_one()

    assert row_count == 1
    assert "2026-01-01 00:01:00" in str(last_heartbeat)
