import asyncio
import threading
import time
from typing import Dict


class JobState:
    def __init__(self):
        self.logs = []
        self.mcts_nodes = []
        self.status = 'idle'
        self.result = None
        self.original_skill = ''
        self.model_name = None
        self.model_prefix = None
        self.api_base = None
        self.api_key = None
        self.regras_adicionais = ''
        self.is_deleted = False
        self.events_queue = asyncio.Queue()
        self.last_activity_time: float = time.time()  # Timestamp da última atividade real do job


jobs: Dict[str, JobState] = {}
_jobs_lock = threading.Lock()


def get_job(job_id: str) -> JobState | None:
    """Thread-safe: obtém um job pelo ID."""
    with _jobs_lock:
        return jobs.get(job_id)


def set_job(job_id: str, job: JobState) -> None:
    """Thread-safe: insere/atualiza um job."""
    with _jobs_lock:
        jobs[job_id] = job


def remove_job(job_id: str) -> JobState | None:
    """Thread-safe: remove e retorna um job, ou None se não existir."""
    with _jobs_lock:
        return jobs.pop(job_id, None)


def get_all_jobs() -> Dict[str, JobState]:
    """Thread-safe: retorna cópia rasa do dict de jobs."""
    with _jobs_lock:
        return dict(jobs)


def cancel_job(job_id: str):
    """Thread-safe: marca job como cancelled e envia evento de término."""
    with _jobs_lock:
        job = jobs.get(job_id)
        if job and job.status == 'running':
            job.status = 'cancelled'
            job.events_queue.put_nowait({
                'type': 'log',
                'data': {'text': '\n[!] OTIMIZAÇÃO INTERROMPIDA PELO USUÁRIO.'},
            })
            job.events_queue.put_nowait({'type': 'end', 'data': 'cancelled'})


def get_running_jobs_count() -> int:
    """Thread-safe: conta jobs com status 'running'."""
    with _jobs_lock:
        return sum(1 for j in jobs.values() if j.status == 'running')


def cancel_all_active_jobs(exclude_id: str | None = None) -> int:
    """Thread-safe: cancela todos os jobs running/idle, opcionalmente excluindo um ID.
    Retorna o número de jobs cancelados."""
    count = 0
    with _jobs_lock:
        for j_id, j_state in list(jobs.items()):
            if j_id == exclude_id:
                continue
            if j_state.status in ('running', 'idle'):
                j_state.status = 'cancelled'
                j_state.events_queue.put_nowait({
                    'type': 'log',
                    'data': {'text': '\n[!] OTIMIZAÇÃO CANCELADA POR NOVA REQUISIÇÃO.'},
                })
                count += 1
    return count
