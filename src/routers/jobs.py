import uuid
import asyncio
import json
import os
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from loguru import logger

from src.schemas import OtimizacaoRequestDTO
from src.state import JobState, jobs
import src.store as job_store
from src.teleprompter import compilar_avaliador
from src.config import setup

# ── Router ────────────────────────────────────────────────────────────────────
router = APIRouter(prefix="/api", tags=["Jobs"])
limiter = Limiter(key_func=get_remote_address)

# Timeout máximo de um job: calculado dinamicamente a partir de max_iterations.
# Budget por iteração (com dspy.LM num_retries=0):
#   - LLM mutação:  ~90s (1 chamada, sem retry automático)
#   - LLM avaliação: ~90s
#   - Overhead (parsing, rede, sleep de backoff mínimo): ~30s
#   Total: ~210s/iteração
# Fallback: 30 minutos se a config não puder ser lida.
def _resolve_max_job_duration() -> int:
    try:
        from src.domain.config import load_mcts_config
        cfg = load_mcts_config()
        per_iteration = 210  # ~3.5 min/iter: mutação 90s + avaliação 90s + overhead 30s
        duration = cfg.max_iterations * per_iteration
        return max(duration, 600)  # mínimo 10 min
    except Exception:
        return 30 * 60

MAX_JOB_DURATION_SECONDS = _resolve_max_job_duration()

# Timeout máximo da verificação de drift (P1-C2). Calculado dinamicamente
# considerando o paralelismo: _measure_all_probes usa ThreadPoolExecutor com
# max_workers=4. O tempo total é O(ceil(n_probes/4) × reps × 8s) + 10s buffer.
# Fallback: 100s se o golden set não puder ser inspecionado.
# Ex: 11 probes, 4 workers, 3 reps → ceil(11/4)=3 × 3 × 8s + 10s = 82s.
def _resolve_drift_check_timeout() -> int:
    import math
    try:
        from pathlib import Path
        import json
        golden_path = Path('src/outputs/golden/golden_set.json')
        if golden_path.exists():
            data = json.loads(golden_path.read_text(encoding='utf-8'))
            n_probes = len(data.get('probes', []))
            if n_probes > 0:
                from src.config import get_drift_thresholds
                cfg = get_drift_thresholds()
                reps = cfg.get('repetitions', 3)
                max_workers = 4  # mesmo valor do ThreadPoolExecutor em metrics.py
                probes_per_worker = math.ceil(n_probes / max_workers)
                # 12s por chamada LLM (latência observada com o modelo atual: ~10-11s/call) + 15s buffer
                return max(120, probes_per_worker * reps * 12 + 15)
    except Exception:
        pass
    return 100

DRIFT_CHECK_TIMEOUT_SECONDS = _resolve_drift_check_timeout()

# ── Health Check ──────────────────────────────────────────────────────────────
@router.get("/health")
async def health_check():
    """Endpoint de health check — frontend usa para verificar se API está viva."""
    llm_configured = bool(os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("NVIDIA_API_KEY"))
    return {
        "status": "ok",
        "version": "0.4.0",
        "llm_configured": llm_configured,
    }


# ── Métricas Simplificadas ────────────────────────────────────────────────────
_request_metrics: list[dict] = []  # Em produção, substituir por Prometheus


@router.get("/metrics/summary")
async def metrics_summary():
    """Resumo de latência das últimas 100 requests."""
    if not _request_metrics:
        return {"status": "ok", "total_requests": 0, "message": "Nenhuma métrica coletada ainda."}

    durations = sorted([m["duration_ms"] for m in _request_metrics])
    n = len(durations)
    p50 = durations[int(n * 0.50)] if n > 0 else 0
    p95 = durations[int(n * 0.95)] if n > 1 else durations[-1]
    p99 = durations[int(n * 0.99)] if n > 2 else durations[-1]

    return {
        "status": "ok",
        "total_requests": n,
        "avg_ms": round(sum(durations) / n, 2),
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
        "max_ms": durations[-1],
        "min_ms": durations[0],
    }


# ── Optimize ──────────────────────────────────────────────────────────────────
@router.post("/optimize")
@limiter.limit("5/minute")
async def start_optimization(request: Request, body: OtimizacaoRequestDTO, background_tasks: BackgroundTasks):
    logger.info(
        "Nova otimização solicitada | model={} | skill_len={}",
        body.modelName or "default",
        len(body.skillOriginal),
    )

    for j_state in jobs.values():
        if j_state.status in ("running", "idle"):
            j_state.status = "cancelled"
            j_state.events_queue.put_nowait({
                "type": "log",
                "data": {"text": "\n[!] OTIMIZAÇÃO CANCELADA POR NOVA REQUISIÇÃO."},
            })

    job_id = str(uuid.uuid4())
    job_state = JobState()
    job_state.original_skill = body.skillOriginal
    job_state.model_name = body.modelName
    job_state.model_prefix = body.modelPrefix
    job_state.api_base = body.apiBase
    job_state.api_key = body.apiKey
    job_state.regras_adicionais = "\n".join(body.regrasAdicionais) if body.regrasAdicionais else ""

    jobs[job_id] = job_state
    job_store.save_job_state(job_id, job_state)

    loop = asyncio.get_running_loop()

    from src.infrastructure.container import Container
    from src.services import OptimizationService

    container = Container()
    service = OptimizationService(
        strategy_discoverer=container.get_strategy_discoverer(),
        agent=container.get_agent(),
        agent_cognitivo=container.get_agent_cognitivo(),
        avaliador_modo_b=container.get_avaliador_modo_b(),
        compiler=container.get_compiler(),
        experience_store=container.get_experience_store(),
        job_store=container.get_job_store(),
        ai_framework=container.get_ai_framework(),
        config=container.get_config(),
        bandit=container.create_bandit(),
        strategy_registry=container.create_strategy_registry(),
    )

    background_tasks.add_task(service.execute, job_id, loop)
    logger.info("Job {} iniciado em background", job_id)
    return {"job_id": job_id}


# ── Stop ──────────────────────────────────────────────────────────────────────
@router.post("/stop/{job_id}")
async def stop_optimization(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == "running":
        job.status = "cancelled"
        job_store.save_job_state(job_id, job)
        job.events_queue.put_nowait({
            "type": "log",
            "data": {"text": "\n[!] OTIMIZAÇÃO INTERROMPIDA PELO USUÁRIO."},
        })
        logger.info("Job {} cancelado pelo usuário", job_id)
        return {"status": "success", "message": "Sinal de interrupção enviado."}

    return {"status": "ignored", "message": "Job não está rodando."}


# ── List / Delete / Get ───────────────────────────────────────────────────────
@router.get("/jobs")
async def get_all_jobs(skip: int = 0, limit: int = 50, status: Optional[str] = None):
    return job_store.load_all_jobs(skip=skip, limit=limit, status=status)


@router.delete("/jobs/{job_id}")
async def delete_job_endpoint(job_id: str):
    job_in_memory = jobs.get(job_id)
    if job_in_memory:
        job_in_memory.is_deleted = True
        if job_in_memory.status == "running":
            job_in_memory.status = "cancelled"

    success = job_store.delete_job(job_id)
    if not success and not job_in_memory:
        raise HTTPException(status_code=404, detail="Job not found or could not be deleted")

    if job_id in jobs:
        del jobs[job_id]

    logger.info("Job {} deletado", job_id)
    return {"status": "success", "message": "Job deletado com sucesso."}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_store.load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


# ── SSE: Geradores de Eventos ─────────────────────────────────────────────────
async def _orphaned_event_generator(disk_job: dict):
    status = disk_job.get("status", "error")
    if status == "completed":
        yield {
            "event": "result",
            "data": json.dumps({
                "status": status,
                "original": disk_job.get("original_skill", ""),
                "optimized": disk_job.get("result", ""),
                "nodes": disk_job.get("mcts_nodes", []),
            }),
        }
    yield {"event": "end", "data": status}


def _format_event(event: dict) -> dict:
    if event["type"] == "log":
        return {"data": json.dumps(event["data"])}
    if event["type"] == "node":
        return {"event": "node", "data": json.dumps(event["data"])}
    if event["type"] == "cost":
        return {"event": "cost", "data": json.dumps(event["data"])}
    return {}


def _format_result_event(job) -> dict:
    return {
        "event": "result",
        "data": json.dumps({
            "status": job.status,
            "original": job.original_skill,
            "optimized": job.result,
            "nodes": job.mcts_nodes,
        }),
    }


async def _live_event_generator(job):
    """Gera eventos SSE com timeout máximo dinâmico (calculado a partir de max_iterations)."""
    start_time = asyncio.get_event_loop().time()

    # Drena eventos já enfileirados
    while not job.events_queue.empty():
        event = job.events_queue.get_nowait()
        formatted = _format_event(event)
        if formatted:
            yield formatted

    while True:
        # Verifica timeout máximo
        elapsed = asyncio.get_event_loop().time() - start_time
        if elapsed > MAX_JOB_DURATION_SECONDS:
            logger.warning("Job {} excedeu timeout máximo de {}s — encerrando SSE", job, MAX_JOB_DURATION_SECONDS)
            yield {"event": "end", "data": "timeout"}
            return

        try:
            event = await asyncio.wait_for(job.events_queue.get(), timeout=0.1)
            formatted = _format_event(event)
            if formatted:
                yield formatted
            job.events_queue.task_done()
        except asyncio.TimeoutError:
            pass
        except asyncio.CancelledError:
            logger.info("SSE stream do job {} cancelado (CancelledError)", id(job))
            yield {"event": "end", "data": "cancelled"}
            return

        queue_empty = job.events_queue.empty()
        if job.status == "completed" and queue_empty:
            yield _format_result_event(job)

        if job.status in ("completed", "error", "cancelled") and queue_empty:
            yield {"event": "end", "data": job.status}
            await asyncio.sleep(0.5)
            return

        await asyncio.sleep(0.05)


# ── Stream ────────────────────────────────────────────────────────────────────
@router.get("/stream/{job_id}")
async def stream_progress(job_id: str):
    job = jobs.get(job_id)
    if not job:
        disk_job = job_store.load_job(job_id)
        if not disk_job:
            raise HTTPException(status_code=404, detail="Job not found")

        if disk_job.get("status") == "running":
            temp_job = JobState()
            temp_job.status = "error"
            temp_job.original_skill = disk_job.get("original_skill", "")
            temp_job.result = disk_job.get("result")
            temp_job.logs = disk_job.get("logs", [])
            temp_job.mcts_nodes = disk_job.get("mcts_nodes", [])
            temp_job.model_name = disk_job.get("model_name")
            temp_job.model_prefix = disk_job.get("model_prefix")
            temp_job.regras_adicionais = disk_job.get("regras_adicionais", "")
            job_store.save_job_state(job_id, temp_job)
            disk_job["status"] = "error"

        return EventSourceResponse(_orphaned_event_generator(disk_job))

    logger.info("SSE stream iniciado para job {}", job_id)
    return EventSourceResponse(_live_event_generator(job))


# ── Judge ─────────────────────────────────────────────────────────────────────
@router.post("/train-judge")
async def train_judge():
    # setup() deve rodar na thread do event loop — dspy.configure() só pode ser
    # chamado pela thread que fez a configuração inicial. Passar o lm como
    # argumento evita reconfigurar o singleton dentro da thread worker.
    lm = setup()

    def _run():
        try:
            status = compilar_avaliador(lm=lm)
            return status
        except Exception as e:
            logger.opt(exception=True).error("Falha ao treinar juiz")
            return str(e)

    result = await asyncio.to_thread(_run)
    if result == "compiled":
        return {"status": "success", "message": "Avaliador recompilado e validado contra o golden set."}
    elif result == "golden_required":
        raise HTTPException(
            status_code=428,
            detail="Golden set ausente. Candidato descartado para evitar model collapse. Crie o golden set antes de treinar o avaliador."
        )
    elif result == "drift_rejected":
        raise HTTPException(status_code=422, detail="Candidato rejeitado pelo portão de drift. Juiz atual preservado.")
    elif result == "measurement_error":
        raise HTTPException(status_code=500, detail="Falha ao medir drift (golden presente). Candidato descartado (fail-closed).")
    elif result == "no_data":
        raise HTTPException(status_code=400, detail="Falta histórico positivo (score > 0.8) ou treinamento em andamento.")
    else:
        raise HTTPException(status_code=500, detail=f"Erro: {result}")


@router.post("/check-drift")
async def check_drift():
    from src.config import get_drift_thresholds
    from src.drift.models import DriftThresholds
    from src.drift.circuit_breaker import verificar_juiz_atual, _execute_circuit_breaker, _has_api_key
    from src.drift.cache import save_drift_cache
    from src.drift.history import append_drift_report
    from pathlib import Path

    # Pre-flight (P1-C5): distinção no endpoint entre 'no_golden' e 'no_api_key'.
    # Mapeia para status distintos para o frontend exibir mensagem específica.
    golden_path = Path('src/outputs/golden/golden_set.json')
    has_golden = golden_path.exists() and golden_path.stat().st_size > 0
    if not has_golden:
        return {"status": "no_golden", "message": "Golden set ausente; nada a medir."}
    if not _has_api_key():
        model_path = Path('src/outputs/models/avaliador_modo_b_otimizado.json')
        if not model_path.exists():
            return {
                "status": "no_api_key",
                "message": "Nenhuma API key configurada e juiz não treinado. Configure API_KEY/OPENAI_API_KEY/NVIDIA_API_KEY no .env.",
            }

    # setup() na thread do event loop — mesmo motivo de train_judge.
    setup()

    def _run():
        try:
            cfg = get_drift_thresholds()
            thresholds = DriftThresholds.from_config(cfg)
            report = verificar_juiz_atual(thresholds, cfg["repetitions"])
            if report is None:
                return {"status": "no_golden", "message": "Golden set ausente; nada a medir."}

            decision = _execute_circuit_breaker(report)
            save_drift_cache(report)
            append_drift_report(
                report,
                triggered_cb=not decision.accept,
                cb_reason=decision.reason if not decision.accept else None,
            )
            return {
                "status": "ok",
                "report": report.to_dict(),
                "circuit_breaker": {"accept": decision.accept, "reason": decision.reason},
            }
        except Exception as e:
            logger.opt(exception=True).error("Falha ao verificar drift")
            return {"status": "error", "message": str(e)}

    # P1-C2: teto absoluto de tempo. Se excedido, retorna 504 (frontend tem
    # AbortController de 120s como última linha de defesa). O fail-fast do
    # runner (60s) já deve abortar antes em cascata de infra.
    try:
        result = await asyncio.wait_for(asyncio.to_thread(_run), timeout=DRIFT_CHECK_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.warning("check-drift excedeu timeout de {}s", DRIFT_CHECK_TIMEOUT_SECONDS)
        raise HTTPException(
            status_code=504,
            detail=f"Verificação de drift excedeu o tempo máximo de {DRIFT_CHECK_TIMEOUT_SECONDS}s. Tente novamente.",
        )

    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result


@router.get("/drift-history")
async def drift_history(limit: int = 50):
    from src.drift.history import load_drift_history

    entries = load_drift_history()
    return {
        "status": "ok",
        "total": len(entries),
        "entries": entries[:limit],
    }


@router.get("/drift-status")
async def drift_status():
    from src.drift.cache import load_drift_cache

    cache = load_drift_cache()
    if cache is None:
        return {"status": "no_cache", "message": "Nenhuma medição de drift disponível."}
    return {"status": "ok", "report": cache.to_dict()}