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
        session.add(JobRecord(id="job-1", status="queued"))
        session.commit()

    response = client.get("/jobs")

    assert response.status_code == 200
    assert response.json() == [{"id": "job-1", "status": "queued"}]
