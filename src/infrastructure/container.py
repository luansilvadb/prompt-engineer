import dspy
from src.domain.agent_interfaces import IStrategyDiscoverer, ISelfReflectiveAgent, IMutadorCognitivoAgent, IAvaliadorModoB, IAiFramework
from src.domain.config import MCTSConfig, load_mcts_config
from src.domain.scoring_pipeline import IScoringPipeline
from src.domain.store_interfaces import IJobStore, IAvaliadorCompiler, IExperienceStore
from src.mutation_strategies.bandit import MutationBandit
from src.mutation_strategies.bandit_interfaces import IMutationBandit, IStrategyRegistry
from src.mutation_strategies.registry import StrategyRegistry

from src.infrastructure.dspy_impl import (
    DSPyStrategyDiscoverer,
    DSPySelfReflectiveAgent,
    DSPyMutadorCognitivoAgent,
    DSPyAvaliadorModoB,
    load_avaliador
)
from src.infrastructure.scoring_pipeline import ScoringPipeline
from src.experience_store import ExperienceStore
import src.store as store_module
from src.teleprompter import compilar_avaliador

class DSPyFramework(IAiFramework):
    def context(self, lm) -> dspy.context:
        return dspy.context(lm=lm)

class JobStore(IJobStore):
    def save_job_state(self, job_id: str, job) -> None:
        store_module.save_job_state(job_id, job)

    def load_all_jobs(self, skip: int = 0, limit: int = 50, status: str = None) -> dict:
        return store_module.load_all_jobs(skip=skip, limit=limit, status=status)

    def load_job(self, job_id: str) -> dict:
        return store_module.load_job(job_id)

    def delete_job(self, job_id: str) -> bool:
        return store_module.delete_job(job_id)

class AvaliadorCompiler(IAvaliadorCompiler):
    def compilar_avaliador(self, lm=None, min_reward=0.8) -> str:
        return compilar_avaliador(lm, min_reward)

class Container:
    def __init__(self) -> None:
        # Carrega os modelos/pesos treinados do avaliador
        load_avaliador()
        self._config = load_mcts_config()
        self._scoring_pipeline = ScoringPipeline(
            semantic_sim_threshold=self._config.semantic_sim_threshold,
            density_threshold=self._config.density_threshold,
            density_multiplier_min=self._config.density_multiplier_min,
            density_multiplier_max=self._config.density_multiplier_max,
            density_structured_bonus=self._config.density_structured_bonus,
            lexical_density_min=self._config.lexical_density_min,
        )
        self._strategy_discoverer = DSPyStrategyDiscoverer()
        self._agent = DSPySelfReflectiveAgent()
        self._agent_cognitivo = DSPyMutadorCognitivoAgent()
        self._avaliador_modo_b = DSPyAvaliadorModoB()
        self._compiler = AvaliadorCompiler()
        self._experience_store = ExperienceStore()
        self._job_store = JobStore()
        self._ai_framework = DSPyFramework()

    def get_strategy_discoverer(self) -> IStrategyDiscoverer:
        return self._strategy_discoverer

    def get_agent(self) -> ISelfReflectiveAgent:
        return self._agent

    def get_agent_cognitivo(self) -> IMutadorCognitivoAgent:
        return self._agent_cognitivo

    def get_avaliador_modo_b(self) -> IAvaliadorModoB:
        return self._avaliador_modo_b

    def get_compiler(self) -> IAvaliadorCompiler:
        return self._compiler

    def get_experience_store(self) -> IExperienceStore:
        return self._experience_store

    def get_job_store(self) -> IJobStore:
        return self._job_store

    def get_ai_framework(self) -> IAiFramework:
        return self._ai_framework

    def get_config(self) -> MCTSConfig:
        return self._config

    def get_scoring_pipeline(self) -> IScoringPipeline:
        return self._scoring_pipeline

    def create_bandit(self) -> IMutationBandit:
        return MutationBandit(c_param=self._config.bandit_c_param)

    def create_strategy_registry(self) -> IStrategyRegistry:
        return StrategyRegistry()
