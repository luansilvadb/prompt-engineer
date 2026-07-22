"""Container de Injeção de Dependências com Lifecycle Explícito.

Suporta SINGLETON (instância única compartilhada) e TRANSIENT (nova instância
a cada acesso). Health check valida dependências críticas antes do runtime.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any

import dspy

import src.store as store_module
from src.domain.agent_interfaces import (
    IAiFramework,
    IAvaliadorModoB,
    IMutadorCognitivoAgent,
    ISelfReflectiveAgent,
    IStrategyDiscoverer,
)
from src.domain.config import MCTSConfig, load_mcts_config
from src.domain.scoring_pipeline import IScoringPipeline
from src.domain.store_interfaces import IAvaliadorCompiler, IExperienceStore, IJobStore
from src.experience_store_sqlite import create_experience_store
from src.infrastructure.dspy_impl import (
    DSPyAvaliadorModoB,
    DSPyMutadorCognitivoAgent,
    DSPySelfReflectiveAgent,
    DSPyStrategyDiscoverer,
    load_avaliador,
)
from src.infrastructure.scoring_pipeline import ScoringPipeline
from src.mutation_strategies.bandit import MutationBandit
from src.domain.bandit_interfaces import IMutationBandit, IStrategyRegistry
from src.mutation_strategies.registry import StrategyRegistry
from src.teleprompter import compilar_avaliador


class Lifecycle(Enum):
    SINGLETON = auto()
    TRANSIENT = auto()


# ── Adaptadores ───────────────────────────────────────────────────────────────


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
    def compilar_avaliador(self, lm=None, min_reward=0.8, optimizer_type="bootstrap") -> str:
        return compilar_avaliador(lm, min_reward, optimizer_type)


# ── Container ─────────────────────────────────────────────────────────────────


class Container:
    """Container DI com lifecycle explícito (SINGLETON | TRANSIENT).

    Uso:
        c = Container()
        store = c.get_experience_store()    # SINGLETON — mesma instância sempre
        bandit = c.get_bandit()             # TRANSIENT — nova instância por job
        ok, err = c.health_check()          # valida dependências antes do runtime
    """

    def __init__(self) -> None:
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

        # ── Registro de dependências ──────────────────────────────────────
        self._registry: dict[str, tuple[Lifecycle, Any | None]] = {
            "strategy_discoverer": (Lifecycle.SINGLETON, DSPyStrategyDiscoverer()),
            "agent": (Lifecycle.SINGLETON, DSPySelfReflectiveAgent()),
            "agent_cognitivo": (Lifecycle.SINGLETON, DSPyMutadorCognitivoAgent()),
            "avaliador_modo_b": (Lifecycle.SINGLETON, DSPyAvaliadorModoB()),
            "compiler": (Lifecycle.SINGLETON, AvaliadorCompiler()),
            "job_store": (Lifecycle.SINGLETON, JobStore()),
            "ai_framework": (Lifecycle.SINGLETON, DSPyFramework()),
            # Experience Store: SINGLETON, usa SQLite com fallback JSON Lines
            "experience_store": (Lifecycle.SINGLETON, None),
            # Bandit e StrategyRegistry: TRANSIENT — cada job tem estado independente
            "bandit": (Lifecycle.TRANSIENT, None),
            "strategy_registry": (Lifecycle.TRANSIENT, None),
        }

    # ── Resolução com lifecycle ──────────────────────────────────────────────

    def _resolve(self, key: str, factory) -> Any:
        """Resolve uma dependência respeitando seu lifecycle."""
        lifecycle, cached = self._registry[key]
        if lifecycle == Lifecycle.SINGLETON:
            if cached is None:
                cached = factory()
                self._registry[key] = (lifecycle, cached)
            return cached
        # TRANSIENT: sempre cria nova instância
        return factory()

    # ── Getters ─────────────────────────────────────────────────────────────

    def get_strategy_discoverer(self) -> IStrategyDiscoverer:
        return self._resolve("strategy_discoverer", lambda: DSPyStrategyDiscoverer())

    def get_agent(self) -> ISelfReflectiveAgent:
        return self._resolve("agent", lambda: DSPySelfReflectiveAgent())

    def get_agent_cognitivo(self) -> IMutadorCognitivoAgent:
        return self._resolve("agent_cognitivo", lambda: DSPyMutadorCognitivoAgent())

    def get_avaliador_modo_b(self) -> IAvaliadorModoB:
        return self._resolve("avaliador_modo_b", lambda: DSPyAvaliadorModoB())

    def get_compiler(self) -> IAvaliadorCompiler:
        return self._resolve("compiler", lambda: AvaliadorCompiler())

    def get_experience_store(self) -> IExperienceStore:
        def _factory():
            return create_experience_store(
                gamma=0.995,  # temporal decay factor
                max_experiences=500,
            )

        return self._resolve("experience_store", _factory)

    def get_job_store(self) -> IJobStore:
        return self._resolve("job_store", lambda: JobStore())

    def get_ai_framework(self) -> IAiFramework:
        return self._resolve("ai_framework", lambda: DSPyFramework())

    def get_config(self) -> MCTSConfig:
        return self._config

    def get_scoring_pipeline(self) -> IScoringPipeline:
        return self._scoring_pipeline

    def get_bandit(self) -> IMutationBandit:
        def _factory():
            return MutationBandit(
                c_param=self._config.bandit_c_param,
                temperature=self._config.bandit_temperature,
                temperature_decay=self._config.bandit_temperature_decay,
            )

        return self._resolve("bandit", _factory)

    def get_strategy_registry(self) -> IStrategyRegistry:
        def _factory():
            return StrategyRegistry()

        return self._resolve("strategy_registry", _factory)

    # ── Health Check ────────────────────────────────────────────────────────

    def health_check(self) -> tuple[bool, str | None]:
        """Valida dependências críticas. Retorna (ok, error_message).

        Verifica:
        - SentenceTransformer carrega sem crash
        - Config MCTS é válida (max_iterations > 0)
        - Experience Store consegue escrever/ler
        """
        # 1. Config
        cfg = self.get_config()
        if cfg.max_iterations <= 0:
            return False, "MCTSConfig.max_iterations deve ser > 0"

        # 2. SentenceTransformer (lazy — testa carregamento)
        try:
            from src.evaluators.semantic import get_embedder

            get_embedder()
        except Exception as e:
            return False, f"SentenceTransformer falhou ao carregar: {e}"

        # 3. Experience Store
        try:
            store = self.get_experience_store()
            store.save()
        except Exception as e:
            return False, f"Experience Store falhou: {e}"

        return True, None


# ── Retrocompatibilidade ──────────────────────────────────────────────────────


# Mantém create_bandit e create_strategy_registry como aliases depreciados
# para não quebrar código existente (main.py CLI, tests).
Container.create_bandit = Container.get_bandit  # type: ignore[attr-defined]
Container.create_strategy_registry = Container.get_strategy_registry  # type: ignore[attr-defined]
