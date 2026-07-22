import asyncio
import threading
from src.state import jobs
from src.config import setup
from src.optimizer import Optimizer
from src.store import save_optimized_skill
from src.domain.agent_interfaces import IStrategyDiscoverer, ISelfReflectiveAgent, IMutadorCognitivoAgent, IAvaliadorModoB, IAiFramework
from src.domain.config import MCTSConfig, load_mcts_config
from src.domain.store_interfaces import IJobStore, IAvaliadorCompiler, IExperienceStore
from src.infrastructure.events import JobEventEmitter
from src.mutation_strategies.bandit import MutationBandit
from src.domain.bandit_interfaces import IMutationBandit, IStrategyRegistry
from src.mutation_strategies.registry import StrategyRegistry

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

    def handle_cost(cost_data: dict):
        asyncio.run_coroutine_threadsafe(job.events_queue.put({'type': 'cost', 'data': cost_data}), loop)

    return log_progress, log_error, handle_node, handle_cost

def _run_bg_compiler(lm, compiler: IAvaliadorCompiler):
    try:
        compiler.compilar_avaliador(lm=lm)
    except Exception as e:
        print(f"[!] Erro ao rodar compilação em background: {e}")

class OptimizationService:
    def __init__(
        self,
        strategy_discoverer: IStrategyDiscoverer,
        agent: ISelfReflectiveAgent,
        agent_cognitivo: IMutadorCognitivoAgent,
        avaliador_modo_b: IAvaliadorModoB,
        compiler: IAvaliadorCompiler,
        experience_store: IExperienceStore,
        job_store: IJobStore,
        ai_framework: IAiFramework,
        config: MCTSConfig | None = None,
        bandit: IMutationBandit | None = None,
        strategy_registry: IStrategyRegistry | None = None,
    ) -> None:
        self.strategy_discoverer = strategy_discoverer
        self.agent = agent
        self.agent_cognitivo = agent_cognitivo
        self.avaliador_modo_b = avaliador_modo_b
        self.compiler = compiler
        self.experience_store = experience_store
        self.job_store = job_store
        self.ai_framework = ai_framework
        self._config = config if config is not None else load_mcts_config()
        self._bandit = bandit if bandit is not None else MutationBandit(c_param=self._config.bandit_c_param)
        self._strategy_registry = strategy_registry if strategy_registry is not None else StrategyRegistry()

    def execute(self, job_id: str, loop) -> None:
        job = jobs[job_id]
        if job.status == 'cancelled':
            return
        job.status = 'running'
        self.job_store.save_job_state(job_id, job)

        log_progress, log_error, handle_node, handle_cost = _create_callbacks(job_id, job, loop, self.job_store)
        emitter = JobEventEmitter(
            on_log=log_progress,
            on_error=log_error,
            on_node=handle_node,
            on_cost=handle_cost,
            is_cancelled=lambda: job.status == 'cancelled',
        )

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
                config=self._config,
                emitter=emitter,
                strategy_discoverer=self.strategy_discoverer,
                agent=self.agent,
                agent_cognitivo=self.agent_cognitivo,
                avaliador_modo_b=self.avaliador_modo_b,
                experience_store=self.experience_store,
                bandit=self._bandit,
                strategy_registry=self._strategy_registry,
                regras_adicionais=job.regras_adicionais,
            )

            with self.ai_framework.context(lm=lm):
                melhor_instrucao = optimizer.optimize()

            if job.status == 'cancelled':
                if not job.is_deleted and melhor_instrucao and melhor_instrucao.strip() != job.original_skill.strip():
                    output_file = save_optimized_skill(melhor_instrucao)
                    job.result = melhor_instrucao
                    self.job_store.save_job_state(job_id, job)
                    log_progress(f"\n[+] Resultado parcial preservado em '{output_file}'")
                return

            if job.is_deleted:
                return

            output_file = save_optimized_skill(melhor_instrucao)
            job.result = melhor_instrucao
            job.status = 'completed'
            self.job_store.save_job_state(job_id, job)
            log_progress(f"\n[+] Skill otimizada preservada no histórico em '{output_file}'")

            threading.Thread(target=_run_bg_compiler, args=(lm, self.compiler), daemon=True).start()

        except Exception as e:
            if job.status != 'cancelled':
                log_error(f'\n[!] Erro fatal durante a execução: {e}')
                job.status = 'error'
                self.job_store.save_job_state(job_id, job)

    def audit_skill(self, skill_text: str) -> dict:
        """Executa auditoria pré-flight dos 7 critérios de contexto."""
        from src.context_audit import audit_context_heuristics
        report = audit_context_heuristics(skill_text)
        return report.to_dict()


