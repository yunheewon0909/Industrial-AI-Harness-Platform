from pathlib import Path

from fastapi import FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db import get_engine
from api.models import JobRecord
from api.services.rag import search_index

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


@app.get("/rag/search")
def rag_search(q: str, k: int = 3) -> list[dict[str, object]]:
    if not q.strip():
        raise HTTPException(status_code=400, detail="q must not be empty")

    settings = get_settings()
    top_k = max(1, min(k, 20))

    try:
        hits = search_index(
            index_dir=Path(settings.rag_index_dir),
            query_text=q,
            top_k=top_k,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return [
        {
            "chunk_id": hit.chunk_id,
            "source_path": hit.source_path,
            "score": round(hit.score, 6),
            "text": hit.text,
        }
        for hit in hits
    ]


def run() -> None:
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
