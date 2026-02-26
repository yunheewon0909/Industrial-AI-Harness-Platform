from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True)
class Job:
    id: str
    status: str


class JobRepository(Protocol):
    """DB integration target for the next milestone."""

    def list_jobs(self) -> Sequence[Job]:
        ...
