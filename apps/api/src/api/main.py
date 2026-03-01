from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.config import get_settings
from api.db import get_engine
from api.llm import LLMClient, LLMClientError, OllamaChatClient
from api.models import JobRecord
from api.services.rag import search_index

app = FastAPI(title="Industrial AI Harness API", version="0.1.0")


class AskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1)
    k: int = Field(default=3, ge=1, le=20)


@app.on_event("startup")
def startup() -> None:
    get_engine()


def get_llm_client() -> LLMClient:
    settings = get_settings()
    return OllamaChatClient(
        base_url=settings.ollama_base_url,
        default_model=settings.ollama_model,
        fallback_model=settings.ollama_fallback_model,
        timeout_seconds=settings.ollama_timeout_seconds,
    )


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


@app.post("/ask")
def ask(
    request: AskRequest,
    llm_client: Annotated[LLMClient, Depends(get_llm_client)],
) -> dict[str, Any]:
    question = request.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question must not be empty")

    settings = get_settings()

    try:
        hits = search_index(index_dir=Path(settings.rag_index_dir), query_text=question, top_k=request.k)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    context = "\n\n".join(
        f"[{hit.source_path}#{hit.chunk_id}]\n{hit.text}"
        for hit in hits
    ) or "No relevant context found in local retrieval index."

    try:
        chat_result = llm_client.generate_answer(question=question, context=context)
    except LLMClientError as exc:
        raise HTTPException(status_code=502, detail=f"LLM request failed: {exc}") from exc

    return {
        "answer": chat_result.answer,
        "sources": [
            {
                "chunk_id": hit.chunk_id,
                "source_path": hit.source_path,
                "score": round(hit.score, 6),
                "text": hit.text,
            }
            for hit in hits
        ],
        "meta": {
            "provider": "ollama",
            "model": chat_result.model,
            "used_fallback": chat_result.used_fallback,
            "retrieval_k": request.k,
            "retrieved_count": len(hits),
            "ollama_base_url": settings.ollama_base_url,
        },
    }


def run() -> None:
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
