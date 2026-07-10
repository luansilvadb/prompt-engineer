import asyncio
import threading
from src.state import jobs
from src.config import setup
from src.optimizer import Optimizer, save_optimized_skill
from src.domain.store_interfaces import IJobStore, IAvaliadorCompiler, IExperienceStore
from src.domain.agent_interfaces import IStrategyDiscoverer, ISelfReflectiveAgent, IMutadorCognitivoAgent, IAvaliadorModoB, IAiFramework

def _create_callbacks(job_id: str, job, loop, store: IJobStore):
    def log_progress(msg: str):
        job.logs.append(msg)
        asyncio.run_coroutine_threadsafe(job.events_queue.put({'type': 'log', 'data': {'text': msg}}), loop)
        store.save_job_state(job_id, job)
        
    def log_error(msg: str):
        job.logs.append(msg)
        asyncio.run_coroutine_threadsafe(job.events_queue.put({'type': 'log', 'data': {'text': msg}}), loop)
        store.save_job_state(job_id, job)
        
    def handle_node(node_data: dict):
        for idx, existing in enumerate(job.mcts_nodes):
            if existing['id'] == node_data['id']:
                job.mcts_nodes[idx] = node_data
                break
        else:
            job.mcts_nodes.append(node_data)
            
        asyncio.run_coroutine_threadsafe(job.events_queue.put({'type': 'node', 'data': node_data}), loop)
        store.save_job_state(job_id, job)
        
    return log_progress, log_error, handle_node

def _run_bg_compiler(lm, compiler: IAvaliadorCompiler):
    try:
        compiler.compilar_avaliador(lm=lm)
    except Exception as e:
        print(f"[!] Erro ao rodar compilação em background: {e}")

def execute_optimization_task(
    job_id: str, 
    loop, 
    store: IJobStore,
    strategy_discoverer: IStrategyDiscoverer,
    agent: ISelfReflectiveAgent,
    agent_cognitivo: IMutadorCognitivoAgent,
    avaliador_modo_b: IAvaliadorModoB,
    compiler: IAvaliadorCompiler,
    experience_store: IExperienceStore,
    ai_framework: IAiFramework
):
    job = jobs[job_id]
    if job.status == 'cancelled':
        return
    job.status = 'running'
    store.save_job_state(job_id, job)
    
    log_progress, log_error, handle_node = _create_callbacks(job_id, job, loop, store)
    
    try:
        log_progress('[*] Configurando o provedor e modelo de IA...')
        lm = setup(
            model_name=job.model_name,
            model_prefix=job.model_prefix,
            api_base=job.api_base,
            api_key=job.api_key
        )
        
        optimizer = Optimizer(
            skill_original=job.original_skill,
            strategy_discoverer=strategy_discoverer,
            agent=agent,
            agent_cognitivo=agent_cognitivo,
            avaliador_modo_b=avaliador_modo_b,
            experience_store=experience_store,
            on_progress=log_progress,
            on_error=log_error,
            is_cancelled=lambda: job.status == 'cancelled',
            on_node=handle_node,
            regras_adicionais=job.regras_adicionais
        )
        
        with ai_framework.context(lm=lm):
            melhor_instrucao = optimizer.optimize()
        
        if job.status == 'cancelled':
            if not job.is_deleted and melhor_instrucao and melhor_instrucao.strip() != job.original_skill.strip():
                output_file = save_optimized_skill(melhor_instrucao)
                job.result = melhor_instrucao
                store.save_job_state(job_id, job)
                log_progress(f"\n[+] Resultado parcial preservado em '{output_file}'")
            return
        
        if job.is_deleted:
            return
        
        output_file = save_optimized_skill(melhor_instrucao)
        job.result = melhor_instrucao
        job.status = 'completed'
        store.save_job_state(job_id, job)
        log_progress(f"\n[+] Skill otimizada preservada no histórico em '{output_file}'")
        
        threading.Thread(target=_run_bg_compiler, args=(lm, compiler), daemon=True).start()
        
    except Exception as e:
        if job.status != 'cancelled':
            log_error(f'\n[!] Erro fatal durante a execução: {e}')
            job.status = 'error'
            store.save_job_state(job_id, job)
