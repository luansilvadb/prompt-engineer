import uuid
import asyncio
import json
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.schemas import OtimizacaoRequestDTO
from src.state import JobState, jobs
import src.store as job_store
from src.teleprompter import compilar_avaliador
from src.config import setup

class DspyAdapter:
    def context(self, lm):
        import dspy
        return dspy.context(lm=lm)

class JobStoreAdapter:
    def save_job_state(self, job_id, job):
        job_store.save_job_state(job_id, job)
    def load_all_jobs(self, skip=0, limit=50, status=None):
        return job_store.load_all_jobs(skip, limit, status)
    def load_job(self, job_id):
        return job_store.load_job(job_id)
    def delete_job(self, job_id):
        return job_store.delete_job(job_id)

class AvaliadorCompilerAdapter:
    def compilar_avaliador(self, lm=None, min_reward=0.8):
        return compilar_avaliador(lm, min_reward)

router = APIRouter(prefix="/api", tags=["Jobs"])

@router.post('/optimize')
async def start_optimization(request: OtimizacaoRequestDTO, background_tasks: BackgroundTasks):
    for j_state in jobs.values():
        if j_state.status in ('running', 'idle'):
            j_state.status = 'cancelled'
            j_state.events_queue.put_nowait({
                'type': 'log',
                'data': {'text': '\n[!] OTIMIZAÇÃO CANCELADA POR NOVA REQUISIÇÃO.'}
            })

    job_id = str(uuid.uuid4())
    job_state = JobState()
    job_state.original_skill = request.skillOriginal
    job_state.model_name = request.modelName
    job_state.model_prefix = request.modelPrefix
    job_state.api_base = request.apiBase
    job_state.api_key = request.apiKey
    job_state.regras_adicionais = '\n'.join(request.regrasAdicionais) if request.regrasAdicionais else ''

    jobs[job_id] = job_state

    store_adapter = JobStoreAdapter()
    store_adapter.save_job_state(job_id, job_state)
    loop = asyncio.get_running_loop()

    # Injeção de dependências via Container
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
        scoring_pipeline=container.get_scoring_pipeline(),
        bandit=container.create_bandit(),
        strategy_registry=container.create_strategy_registry(),
    )

    background_tasks.add_task(
        service.execute,
        job_id,
        loop
    )
    return {'job_id': job_id}

@router.post('/stop/{job_id}')
async def stop_optimization(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')

    if job.status == 'running':
        job.status = 'cancelled'
        job_store.save_job_state(job_id, job)
        job.events_queue.put_nowait({
            'type': 'log',
            'data': {'text': '\n[!] OTIMIZAÇÃO INTERROMPIDA PELO USUÁRIO.'}
        })
        return {'status': 'success', 'message': 'Sinal de interrupção enviado.'}

    return {'status': 'ignored', 'message': 'Job não está rodando.'}

@router.get('/jobs')
async def get_all_jobs(skip: int = 0, limit: int = 50, status: Optional[str] = None):
    return job_store.load_all_jobs(skip=skip, limit=limit, status=status)

@router.delete('/jobs/{job_id}')
async def delete_job_endpoint(job_id: str):
    # Sinalizar cancelamento para a thread de background antes de deletar.
    # Sem isso, a thread continua rodando com referência local ao job
    # e recria o arquivo JSON ao terminar (ghost job).
    job_in_memory = jobs.get(job_id)
    if job_in_memory:
        job_in_memory.is_deleted = True
        if job_in_memory.status == 'running':
            job_in_memory.status = 'cancelled'

    success = job_store.delete_job(job_id)
    if not success and not job_in_memory:
        raise HTTPException(status_code=404, detail='Job not found or could not be deleted')

    if job_id in jobs:
        del jobs[job_id]

    return {'status': 'success', 'message': 'Job deletado com sucesso.'}

@router.get('/jobs/{job_id}')
async def get_job(job_id: str):
    job = job_store.load_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail='Job not found')
    return job

async def _orphaned_event_generator(disk_job: dict):
    status = disk_job.get('status', 'error')
    if status == 'completed':
        yield {
            'event': 'result',
            'data': json.dumps({
                'status': status,
                'original': disk_job.get('original_skill', ''),
                'optimized': disk_job.get('result', ''),
                'nodes': disk_job.get('mcts_nodes', [])
            })
        }
    yield {'event': 'end', 'data': status}

def _format_event(event: dict) -> dict:
    """Formata evento para envio via SSE."""
    if event['type'] == 'log':
        return {'data': json.dumps(event['data'])}
    if event['type'] == 'node':
        return {'event': 'node', 'data': json.dumps(event['data'])}
    return {}

def _format_result_event(job) -> dict:
    """Formata o evento de resultado final."""
    return {
        'event': 'result',
        'data': json.dumps({
            'status': job.status,
            'original': job.original_skill,
            'optimized': job.result,
            'nodes': job.mcts_nodes
        })
    }

async def _live_event_generator(job):
    while not job.events_queue.empty():
        event = job.events_queue.get_nowait()
        formatted = _format_event(event)
        if formatted:
            yield formatted

    while True:
        try:
            event = await asyncio.wait_for(job.events_queue.get(), timeout=0.1)
            formatted = _format_event(event)
            if formatted:
                yield formatted
            job.events_queue.task_done()
        except asyncio.TimeoutError:
            pass

        queue_empty = job.events_queue.empty()
        if job.status == 'completed' and queue_empty:
            yield _format_result_event(job)

        if job.status in ('completed', 'error', 'cancelled') and queue_empty:
            yield {'event': 'end', 'data': job.status}
            await asyncio.sleep(0.5)
            return

        await asyncio.sleep(0.05)

@router.get('/stream/{job_id}')
async def stream_progress(job_id: str):
    job = jobs.get(job_id)
    if not job:
        disk_job = job_store.load_job(job_id)
        if not disk_job:
            raise HTTPException(status_code=404, detail='Job not found')

        if disk_job.get('status') == 'running':
            temp_job = JobState()
            temp_job.status = 'error'
            temp_job.original_skill = disk_job.get('original_skill', '')
            temp_job.result = disk_job.get('result')
            temp_job.logs = disk_job.get('logs', [])
            temp_job.mcts_nodes = disk_job.get('mcts_nodes', [])
            temp_job.model_name = disk_job.get('model_name')
            temp_job.model_prefix = disk_job.get('model_prefix')
            temp_job.regras_adicionais = disk_job.get('regras_adicionais', '')
            job_store.save_job_state(job_id, temp_job)
            disk_job['status'] = 'error'

        return EventSourceResponse(_orphaned_event_generator(disk_job))

    return EventSourceResponse(_live_event_generator(job))

@router.post('/train-judge')
async def train_judge():
    def _run():
        try:
            lm = setup()
            status = compilar_avaliador(lm=lm)
            return status
        except Exception as e:
            return str(e)

    result = await asyncio.to_thread(_run)
    # Mapeamento do CompileResult.status (A1 — grounding da recompensa).
    if result == 'compiled':
        return {'status': 'success',
                'message': 'Avaliador recompilado e validado contra o golden set.'}
    elif result == 'golden_empty_open':
        return {'status': 'success',
                'warning': 'Golden set ausente; compilação sem portão (fail-open).'}
    elif result == 'drift_rejected':
        # Rejeição de negócio esperada — 422, não 500.
        raise HTTPException(status_code=422, detail='Candidato rejeitado pelo portão de drift. Juiz atual preservado.')
    elif result == 'measurement_error':
        raise HTTPException(status_code=500, detail='Falha ao medir drift (golden presente). Candidato descartado (fail-closed).')
    elif result == 'no_data':
        raise HTTPException(status_code=400, detail='Falta histórico positivo (score > 0.8) ou treinamento em andamento.')
    else:
        raise HTTPException(status_code=500, detail=f'Erro: {result}')


@router.post('/check-drift')
async def check_drift():
    """
    Verificação sob demanda do drift do juiz em produção contra o golden set.
    Executa o circuit breaker se o hard-gate estiver comprometido (BR4).
    Atende ao spike de medição e à checagem periódica — sem acoplar ao loop MCTS.
    """
    from src.config import get_drift_thresholds
    from src.drift_monitor import (
        DriftThresholds,
        circuit_breaker,
        verificar_juiz_atual,
    )

    def _run():
        try:
            setup()
            cfg = get_drift_thresholds()
            thresholds = DriftThresholds.from_config(cfg)
            report = verificar_juiz_atual(thresholds, cfg['repetitions'])
            if report is None:
                return {'status': 'no_golden', 'message': 'Golden set ausente; nada a medir.'}
            decision = circuit_breaker(thresholds, cfg['repetitions'])
            return {'status': 'ok', 'report': report.to_dict(), 'circuit_breaker': {'accept': decision.accept, 'reason': decision.reason}}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    result = await asyncio.to_thread(_run)
    if result.get('status') == 'error':
        raise HTTPException(status_code=500, detail=result['message'])
    return result
