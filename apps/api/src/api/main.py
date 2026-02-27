from fastapi import FastAPI
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db import get_engine
from api.models import JobRecord

app = FastAPI(title="Industrial AI Harness API", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    get_engine()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/jobs")
def list_jobs() -> list[dict[str, str]]:
    with Session(get_engine()) as session:
        jobs = session.scalars(
            select(JobRecord).order_by(JobRecord.created_at.asc(), JobRecord.id.asc())
        ).all()

    return [{"id": job.id, "status": job.status} for job in jobs]


def run() -> None:
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
