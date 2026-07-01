import asyncio
import threading
import dspy
from src.state import jobs
from src.store import save_job_state
from src.config import setup
from src.optimizer import Optimizer, save_optimized_skill
from src.teleprompter import compilar_avaliador

def _create_callbacks(job_id: str, job, loop):
    def log_progress(msg: str):
        job.logs.append(msg)
        asyncio.run_coroutine_threadsafe(job.events_queue.put({'type': 'log', 'data': {'text': msg}}), loop)
        save_job_state(job_id, job)
        
    def log_error(msg: str):
        job.logs.append(msg)
        asyncio.run_coroutine_threadsafe(job.events_queue.put({'type': 'log', 'data': {'text': msg}}), loop)
        save_job_state(job_id, job)
        
    def handle_node(node_data: dict):
        for idx, existing in enumerate(job.mcts_nodes):
            if existing['id'] == node_data['id']:
                job.mcts_nodes[idx] = node_data
                break
        else:
            job.mcts_nodes.append(node_data)
            
        asyncio.run_coroutine_threadsafe(job.events_queue.put({'type': 'node', 'data': node_data}), loop)
        save_job_state(job_id, job)
        
    return log_progress, log_error, handle_node

def _run_bg_compiler(lm):
    try:
        compilar_avaliador(lm=lm)
    except Exception as e:
        print(f"[!] Erro ao rodar compilação em background: {e}")

def execute_optimization_task(job_id: str, loop):
    job = jobs[job_id]
    if job.status == 'cancelled':
        return
    job.status = 'running'
    save_job_state(job_id, job)
    
    log_progress, log_error, handle_node = _create_callbacks(job_id, job, loop)
    
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
            on_progress=log_progress,
            on_error=log_error,
            is_cancelled=lambda: job.status == 'cancelled',
            on_node=handle_node,
            regras_adicionais=job.regras_adicionais
        )
        
        with dspy.context(lm=lm):
            melhor_instrucao = optimizer.optimize()
        
        # Guard: se o job foi cancelado/deletado durante a execução,
        # salvar o melhor resultado parcial encontrado mas com status correto.
        if job.status == 'cancelled':
            if not job.is_deleted and melhor_instrucao and melhor_instrucao.strip() != job.original_skill.strip():
                output_file = save_optimized_skill(melhor_instrucao)
                job.result = melhor_instrucao
                save_job_state(job_id, job)
                log_progress(f"\n[+] Resultado parcial preservado em '{output_file}'")
            return
        
        if job.is_deleted:
            return
        
        output_file = save_optimized_skill(melhor_instrucao)
        job.result = melhor_instrucao
        job.status = 'completed'
        save_job_state(job_id, job)
        log_progress(f"\n[+] Skill otimizada preservada no histórico em '{output_file}'")
        
        # Disparar compilação do teleprompter em background sem travar o loop atual
        threading.Thread(target=_run_bg_compiler, args=(lm,), daemon=True).start()
        
    except Exception as e:
        # Não sobrescrever status 'cancelled' com 'error'
        if job.status != 'cancelled':
            log_error(f'\n[!] Erro fatal durante a execução: {e}')
            job.status = 'error'
            save_job_state(job_id, job)
