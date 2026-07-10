from typing import Protocol, List, Dict, Any, Optional

class IJobStore(Protocol):
    def save_job_state(self, job_id: str, job: Any) -> None:
        ...

    def load_all_jobs(self, skip: int = 0, limit: int = 50, status: Optional[str] = None) -> dict:
        ...

    def load_job(self, job_id: str) -> Optional[dict]:
        ...

    def delete_job(self, job_id: str) -> bool:
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
