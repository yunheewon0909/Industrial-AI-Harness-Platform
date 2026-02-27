from fastapi import FastAPI

from api.db import get_engine

app = FastAPI(title="Industrial AI Harness API", version="0.1.0")


@app.on_event("startup")
def startup() -> None:
    get_engine()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/jobs")
def list_jobs() -> list[dict[str, str]]:
    return []


def run() -> None:
    import uvicorn

    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    run()
