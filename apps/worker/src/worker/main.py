from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from random import random
import subprocess
from threading import Event, Thread
from time import sleep
from typing import Any, Callable

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


def _get_poll_seconds() -> int:
    value = os.getenv("WORKER_POLL_SECONDS", "5")
    return max(1, int(value))


def _get_default_max_attempts() -> int:
    value = os.getenv("JOB_MAX_ATTEMPTS", "3")
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


def _heartbeat_loop(engine: Engine, worker_id: str, interval_seconds: int, stop_event: Event) -> None:
    while not stop_event.is_set():
        send_heartbeat_once(engine, worker_id)
        stop_event.wait(interval_seconds)


def _normalize_payload(payload_json: Any) -> dict[str, Any] | None:
    if isinstance(payload_json, dict):
        return payload_json
    if isinstance(payload_json, str) and payload_json.strip():
        try:
            parsed = json.loads(payload_json)
        except json.JSONDecodeError:
            return None
        if isinstance(parsed, dict):
            return parsed
    return None


def _coerce_job_id(job_id: Any) -> int | str:
    if isinstance(job_id, bool):
        return str(job_id)
    if isinstance(job_id, int):
        return job_id
    if isinstance(job_id, str):
        normalized = job_id.strip()
        if normalized.isdigit():
            return int(normalized)
        return normalized
    return str(job_id)


def _claim_next_rag_reindex_job(engine: Engine) -> dict[str, Any] | None:
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT id, payload_json, attempts, max_attempts
                    FROM jobs
                    WHERE type = 'rag_reindex' AND status = 'queued'
                    ORDER BY created_at ASC, id ASC
                    FOR UPDATE SKIP LOCKED
                    LIMIT 1
                    """
                )
            ).mappings().first()
            if row is None:
                return None

            connection.execute(
                text(
                    """
                    UPDATE jobs
                    SET status = 'running',
                        started_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP,
                        finished_at = NULL,
                        error = NULL
                    WHERE CAST(id AS TEXT) = CAST(:job_id AS TEXT)
                    """
                ),
                {"job_id": _coerce_job_id(row["id"])},
            )

            return {
                "id": _coerce_job_id(row["id"]),
                "payload_json": _normalize_payload(row["payload_json"]),
                "attempts": int(row["attempts"] or 0),
                "max_attempts": int(row["max_attempts"] or _get_default_max_attempts()),
            }

    with engine.begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT id, payload_json, attempts, max_attempts
                FROM jobs
                WHERE type = 'rag_reindex' AND status = 'queued'
                ORDER BY created_at ASC, id ASC
                LIMIT 1
                """
            )
        ).mappings().first()
        if row is None:
            return None

        claimed = connection.execute(
            text(
                """
                UPDATE jobs
                SET status = 'running',
                    started_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    finished_at = NULL,
                    error = NULL
                WHERE CAST(id AS TEXT) = CAST(:job_id AS TEXT) AND status = 'queued'
                """
            ),
            {"job_id": _coerce_job_id(row["id"])},
        )
        if claimed.rowcount != 1:
            return None

        return {
            "id": _coerce_job_id(row["id"]),
            "payload_json": _normalize_payload(row["payload_json"]),
            "attempts": int(row["attempts"] or 0),
            "max_attempts": int(row["max_attempts"] or _get_default_max_attempts()),
        }


def _run_reindex_subprocess(payload_json: dict[str, Any] | None = None) -> dict[str, Any]:
    api_project_dir = os.getenv("WORKER_API_PROJECT_DIR", "/workspace/apps/api")
    command = [
        "uv",
        "run",
        "--project",
        api_project_dir,
        "python",
        "-m",
        "api.services.rag.reindex_job_runner",
    ]
    if payload_json is not None:
        command.extend(["--payload-json", json.dumps(payload_json)])
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        cwd="/workspace",
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or completed.stdout.strip()
        stderr_first_line = stderr.splitlines()[0] if stderr else "<empty>"
        print(
            f"[worker] reindex subprocess failed exit={completed.returncode} stderr_first={stderr_first_line}",
            flush=True,
        )
        raise RuntimeError(f"reindex subprocess failed (exit={completed.returncode}): {stderr}")

    output = completed.stdout.strip().splitlines()
    if not output:
        raise RuntimeError("reindex subprocess produced no output")

    try:
        parsed = json.loads(output[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"reindex subprocess returned invalid JSON: {output[-1]}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("reindex subprocess payload must be an object")
    return parsed


def _mark_job_succeeded(engine: Engine, job_id: int | str, result_json: dict[str, Any]) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE jobs
                SET status = 'succeeded',
                    result_json = :result_json,
                    finished_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    error = NULL
                WHERE CAST(id AS TEXT) = CAST(:job_id AS TEXT)
                """
            ),
            {"job_id": job_id, "result_json": json.dumps(result_json)},
        )


def _mark_job_failure(
    engine: Engine,
    *,
    job_id: int | str,
    attempts: int,
    max_attempts: int,
    error_message: str,
) -> None:
    next_attempts = attempts + 1
    requeue = next_attempts < max_attempts

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE jobs
                SET status = CAST(:status AS VARCHAR),
                    attempts = :attempts,
                    error = :error,
                    finished_at = CASE WHEN CAST(:status AS VARCHAR) = 'failed' THEN CURRENT_TIMESTAMP ELSE NULL END,
                    started_at = CASE WHEN CAST(:status AS VARCHAR) = 'queued' THEN NULL ELSE started_at END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE CAST(id AS TEXT) = CAST(:job_id AS TEXT)
                """
            ),
            {
                "job_id": job_id,
                "status": "queued" if requeue else "failed",
                "attempts": next_attempts,
                "error": error_message,
            },
        )


def _process_claimed_job(
    engine: Engine,
    job: dict[str, Any],
    *,
    runner: Callable[[dict[str, Any] | None], dict[str, Any]],
) -> None:
    job_id = _coerce_job_id(job["id"])
    attempts = int(job.get("attempts", 0))
    max_attempts = int(job.get("max_attempts") or _get_default_max_attempts())
    payload = _normalize_payload(job.get("payload_json"))

    try:
        result_json = runner(payload)
    except Exception as exc:
        _mark_job_failure(
            engine,
            job_id=job_id,
            attempts=attempts,
            max_attempts=max_attempts,
            error_message=str(exc),
        )
        print(
            f"[worker] job failed job_id={job_id} attempts={attempts + 1}/{max_attempts} error={exc}",
            flush=True,
        )
        return

    _mark_job_succeeded(engine, job_id, result_json)
    print(f"[worker] job succeeded job_id={job_id} result={result_json}", flush=True)


def main() -> None:
    worker_id = _get_worker_id()
    heartbeat_seconds = _get_heartbeat_seconds()
    poll_seconds = _get_poll_seconds()
    engine = _create_engine()

    stop_event = Event()
    heartbeat_thread = Thread(
        target=_heartbeat_loop,
        args=(engine, worker_id, heartbeat_seconds, stop_event),
        daemon=True,
    )
    heartbeat_thread.start()

    while True:
        job = _claim_next_rag_reindex_job(engine)
        if job is None:
            sleep(poll_seconds)
            continue

        _process_claimed_job(engine, job, runner=_run_reindex_subprocess)


if __name__ == "__main__":
    main()
