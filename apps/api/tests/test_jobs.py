from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from api.db import get_engine
from api.models import JobRecord


def test_jobs_returns_empty_list_when_db_is_empty(client: TestClient) -> None:
    response = client.get("/jobs")

    assert response.status_code == 200
    assert response.json() == []


def test_jobs_returns_seeded_row(client: TestClient) -> None:
    with Session(get_engine()) as session:
        session.add(JobRecord(id="job-1", type="generic", status="queued"))
        session.commit()

    response = client.get("/jobs")

    assert response.status_code == 200
    assert response.json() == [{"id": "job-1", "type": "generic", "status": "queued"}]


def test_jobs_supports_type_and_status_filters(client: TestClient) -> None:
    with Session(get_engine()) as session:
        session.add_all(
            [
                JobRecord(id="job-1", type="rag_reindex", status="queued"),
                JobRecord(id="job-2", type="rag_reindex", status="succeeded"),
                JobRecord(id="job-3", type="generic", status="queued"),
            ]
        )
        session.commit()

    response = client.get("/jobs", params={"type": "rag_reindex", "status": "queued"})

    assert response.status_code == 200
    assert response.json() == [{"id": "job-1", "type": "rag_reindex", "status": "queued"}]


def test_get_job_detail_returns_404_for_missing_job(client: TestClient) -> None:
    response = client.get("/jobs/missing")

    assert response.status_code == 404
