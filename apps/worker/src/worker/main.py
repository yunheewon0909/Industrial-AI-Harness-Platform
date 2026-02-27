from datetime import datetime, timezone
import os
from random import random
from time import sleep

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def _get_database_url() -> str:
    return os.getenv(
        "WORKER_DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/industrial_ai",
    )


def _get_worker_id() -> str:
    return os.getenv("WORKER_ID", "worker-1")


def _get_heartbeat_seconds() -> int:
    value = os.getenv("WORKER_HEARTBEAT_SECONDS", "30")
    return max(1, int(value))


def _get_retry_base_seconds() -> float:
    value = os.getenv("WORKER_DB_RETRY_BASE_SECONDS", "1")
    return max(0.1, float(value))


def _get_retry_max_seconds() -> float:
    value = os.getenv("WORKER_DB_RETRY_MAX_SECONDS", "30")
    return max(0.5, float(value))


def _create_engine() -> Engine:
    return create_engine(
        _get_database_url(),
        pool_pre_ping=True,
    )


def _upsert_heartbeat(engine: Engine, worker_id: str, now: datetime) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO worker_heartbeats (worker_id, last_heartbeat, updated_at)
                VALUES (:worker_id, :last_heartbeat, CURRENT_TIMESTAMP)
                ON CONFLICT(worker_id) DO UPDATE
                SET last_heartbeat = EXCLUDED.last_heartbeat,
                    updated_at = CURRENT_TIMESTAMP
                """
            ),
            {
                "worker_id": worker_id,
                "last_heartbeat": now,
            },
        )


def send_heartbeat_once(engine: Engine, worker_id: str) -> None:
    now = datetime.now(timezone.utc)
    base = _get_retry_base_seconds()
    max_delay = _get_retry_max_seconds()
    delay = base
    attempt = 1

    while True:
        try:
            _upsert_heartbeat(engine, worker_id, now)
            print(f"[worker] heartbeat upserted worker_id={worker_id} at={now.isoformat()}", flush=True)
            return
        except Exception as exc:
            print(
                f"[worker] heartbeat upsert failed attempt={attempt} error={exc!r}; retrying in {delay:.1f}s",
                flush=True,
            )
            sleep(delay + random() * 0.2 * delay)
            delay = min(delay * 2, max_delay)
            attempt += 1


def main() -> None:
    worker_id = _get_worker_id()
    heartbeat_seconds = _get_heartbeat_seconds()
    engine = _create_engine()

    while True:
        send_heartbeat_once(engine, worker_id)
        sleep(heartbeat_seconds)


if __name__ == "__main__":
    main()
