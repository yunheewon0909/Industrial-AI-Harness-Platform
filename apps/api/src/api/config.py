from dataclasses import dataclass
from functools import lru_cache
import os


def _to_bool(value: str | None, *, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str
    db_echo: bool


@lru_cache
def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "API_DATABASE_URL",
            "postgresql+psycopg://postgres:postgres@localhost:5432/industrial_ai",
        ),
        db_echo=_to_bool(os.getenv("API_DB_ECHO"), default=False),
    )
