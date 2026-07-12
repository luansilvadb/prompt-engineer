from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Sequence

from src.domain.job_interfaces import JobStatus


class IJobStore(Protocol):
    """Protocolo completo — adiciona list_by_status ao contrato (fecha GAP-05)."""

    def save_job_state(self, job_id: str, job: Any) -> None:
        ...

    def load_all_jobs(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> dict:
        ...

    def load_job(self, job_id: str) -> Optional[dict]:
        ...

    def delete_job(self, job_id: str) -> bool:
        ...

    def list_by_status(self, status: JobStatus) -> Sequence[str]:
        ...


class IExperienceStore(Protocol):
    def save(self) -> None:
        ...

    def add(self, experience: Any) -> None:
        ...

    def query_similar(self, feedback_query: str, top_k: int = 5) -> List[Any]:
        ...

    def get_strategy_stats(self) -> Dict[str, Dict[str, float]]:
        ...

    @property
    def experiences(self) -> List[Any]:
        ...


class IAvaliadorCompiler(Protocol):
    def compilar_avaliador(self, lm: Any = None, min_reward: float = 0.8) -> str:
        ...
