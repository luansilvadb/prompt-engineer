from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, Sequence


class JobStatus(str, Enum):
    RECEIVED = "received"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"
    ERROR = "error"

    @property
    def is_terminal(self) -> bool:
        return self in _TERMINAL_STATUSES

    @property
    def is_active(self) -> bool:
        return self in _ACTIVE_STATUSES


_TERMINAL_STATUSES: frozenset[JobStatus] = frozenset({
    JobStatus.COMPLETED,
    JobStatus.CANCELLED,
    JobStatus.FAILED,
    JobStatus.ERROR,
})

_ACTIVE_STATUSES: frozenset[JobStatus] = frozenset({
    JobStatus.RECEIVED,
    JobStatus.RUNNING,
})


@dataclass(frozen=True)
class JobCreationRequest:
    skill_original: str
    model_name: str
    model_prefix: str
    api_base: str
    api_key: str
    regras_adicionais: str

    def __post_init__(self) -> None:
        if not self.skill_original.strip():
            raise ValueError("skill_original must not be empty")


@dataclass(frozen=True)
class JobSummary:
    job_id: str
    status: JobStatus
    created_at: float
    original_skill_preview: str


@dataclass(frozen=True)
class PaginatedJobList:
    items: Sequence[JobSummary]
    total: int
    skip: int
    limit: int


class IJobLifecycleManager(Protocol):
    """
    Gerencia o ciclo de vida de jobs: criação, cancelamento global e consulta.
    Extrai RN-JOB-04 (cancel_active_jobs) para fora do router.
    """

    def create_job(self, request: JobCreationRequest) -> str:
        ...

    def cancel_active_jobs(self) -> Sequence[str]:
        ...

    def cancel_job(self, job_id: str) -> bool:
        ...

    def get_job_status(self, job_id: str) -> Optional[JobStatus]:
        ...


class IJobStore(Protocol):
    """
    Protocolo completo de persistência de jobs.
    Adiciona list_by_status e paginação ao contrato anterior.
    """

    def save_job_state(self, job_id: str, job: object) -> None:
        ...

    def load_job(self, job_id: str) -> Optional[dict]:
        ...

    def delete_job(self, job_id: str) -> bool:
        ...

    def load_all_jobs(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> dict:
        ...

    def list_by_status(self, status: JobStatus) -> Sequence[str]:
        ...
