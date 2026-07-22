import asyncio
import json
import os
import uuid

from dotenv import load_dotenv as _reload_dotenv
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from loguru import logger
from slowapi import Limiter
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

import src.store as job_store
from src.config import _get_env_path
from src.schemas import AuditRequestDTO, CompileRequestDTO, ConfigRequestDTO, ConfigResponseDTO, OtimizacaoRequestDTO
from src.state import JobState, jobs

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


# ── Audit ─────────────────────────────────────────────────────────────────────
@router.post("/audit")
@limiter.limit("20/minute")
async def audit_skill_endpoint(request: Request, body: AuditRequestDTO):
    """Executa auditoria pré-flight instantânea do contexto nos 7 critérios empíricos."""
    from src.context_audit import audit_context_heuristics
    report = audit_context_heuristics(body.skillText)
    return report.to_dict()





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
        bandit=container.get_bandit(),
        strategy_registry=container.get_strategy_registry(),
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
async def get_all_jobs(skip: int = 0, limit: int = 50, status: str | None = None):
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
    """Gera eventos SSE com heartbeat, timeout dinâmico e cleanup de conexões órfãs."""
    start_time = asyncio.get_event_loop().time()
    last_heartbeat = start_time
    HEARTBEAT_INTERVAL = 15.0  # envia keepalive a cada 15s para evitar timeout de proxy/load balancer
    ORPHAN_TIMEOUT = 120.0  # considera job órfão se status='running' mas sem eventos por 120s
    ORPHAN_GRACE_PERIOD = 120.0  # só ativa detecção de órfão após 120s (startup do job é lento)

    # Drena eventos já enfileirados
    first_event_received = not job.events_queue.empty()
    while not job.events_queue.empty():
        event = job.events_queue.get_nowait()
        formatted = _format_event(event)
        if formatted:
            yield formatted

    last_event_time = start_time

    while True:
        now = asyncio.get_event_loop().time()
        elapsed = now - start_time

        # Heartbeat: mantém conexão viva mesmo sem eventos de negócio
        if now - last_heartbeat >= HEARTBEAT_INTERVAL:
            last_heartbeat = now
            yield {"comment": "heartbeat"}

        # Timeout máximo do job
        if elapsed > MAX_JOB_DURATION_SECONDS:
            logger.warning("Job {} excedeu timeout máximo de {}s — encerrando SSE", job, MAX_JOB_DURATION_SECONDS)
            yield {"event": "end", "data": "timeout"}
            return

        # Cleanup de jobs órfãos: só ativa após grace period e primeiro evento
        if (
            job.status == "running"
            and first_event_received
            and elapsed > ORPHAN_GRACE_PERIOD
            and (now - last_event_time) > ORPHAN_TIMEOUT
        ):
            logger.warning(
                "Job {} parece órfão: status=running mas {}s sem eventos — encerrando SSE",
                id(job), int(now - last_event_time),
            )
            job.status = "error"
            yield {"event": "end", "data": "error"}
            return

        try:
            event = await asyncio.wait_for(job.events_queue.get(), timeout=0.1)
            first_event_received = True
            last_event_time = now
            formatted = _format_event(event)
            if formatted:
                yield formatted
            job.events_queue.task_done()
        except TimeoutError:
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


# ── Config (Desktop .env persistence) ────────────────────────────────────────

_ENV_PATH = _get_env_path()

def _read_dotenv() -> dict[str, str]:
    """Lê chave=valor do .env, retorna dict. Linhas vazias/comentários ignorados."""
    result: dict[str, str] = {}
    if not _ENV_PATH.exists():
        return result
    for line in _ENV_PATH.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, _, value = line.partition('=')
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result

def _write_dotenv(updates: dict[str, str]) -> None:
    """Atualiza/insere/remove chaves no .env preservando o restante do arquivo."""
    _ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = _read_dotenv()
    for k, v in updates.items():
        if v == '':
            current.pop(k, None)
        else:
            current[k] = v
    lines = [f'{k}={v}' for k, v in current.items()]
    _ENV_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    # Recarregar os.environ para refletir mudanças imediatamente
    _reload_dotenv(_ENV_PATH, override=True)

@router.get("/config", response_model=ConfigResponseDTO)
async def get_config():
    env = _read_dotenv()
    has_key = bool(env.get('API_KEY'))
    return ConfigResponseDTO(
        modelName=env.get('MODEL_NAME', ''),
        modelPrefix=env.get('MODEL_PREFIX', ''),
        apiBase=env.get('API_BASE', ''),
        hasApiKey=has_key,
    )

@router.post("/config")
async def save_config(body: ConfigRequestDTO):
    updates: dict[str, str] = {}
    mapping = [
        ('modelName', 'MODEL_NAME'),
        ('modelPrefix', 'MODEL_PREFIX'),
        ('apiBase', 'API_BASE'),
        ('apiKey', 'API_KEY'),
    ]
    for attr, env_key in mapping:
        value = getattr(body, attr, None)
        if value is not None:
            updates[env_key] = value

    _write_dotenv(updates)

    return {"status": "ok", "message": "Configurações salvas no .env"}


@router.get("/drift-status")
async def get_drift_status():
    """Retorna o relatório do Drift Gate e o número de elementos do Golden Set."""
    from src.drift.cache import load_drift_cache
    from src.drift.golden import GoldenSet

    golden = GoldenSet()
    report = load_drift_cache()

    return {
        "status": "ok",
        "golden_count": len(golden.probes),
        "is_golden_empty": golden.is_empty(),
        "cached_report": {
            "spearman_composite": report.spearman_composite if report else None,
            "offset_scale": report.offset_scale if report else None,
            "mean_variance": report.mean_variance if report else None,
            "critical_rules_violated": report.critical_rules_violated if report else None,
        } if report else None,
    }


@router.post("/compile")
@limiter.limit("2/minute")
async def compile_evaluator_endpoint(request: Request, body: CompileRequestDTO, background_tasks: BackgroundTasks):
    """Compila os agentes usando DSPy Optimizers (BootstrapFewShot, MIPROv2, GEPA) com memórias passadas."""
    from src.teleprompter import compilar_avaliador

    def _do_compile():
        compilar_avaliador(
            min_reward=body.minReward or 0.8,
            optimizer_type=body.optimizerType or "bootstrap"
        )

    background_tasks.add_task(_do_compile)
    return {
        "status": "ok",
        "message": f"Compilação DSPy ({body.optimizerType}) iniciada em background.",
    }


