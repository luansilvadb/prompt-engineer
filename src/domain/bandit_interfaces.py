from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class BanditStats:
    strategy_key: str
    count: int
    mean_delta: float
    total_reward: float
    total_llm_calls: int = 0
    estimated_tokens: int = 0
    successful_expansions: int = 0


class IMutationBandit(ABC):
    """Interface para o Multi-Armed Bandit de seleção de estratégia."""

    @abstractmethod
    def select(self) -> str | list[str]:
        ...

    @abstractmethod
    def force_composition(self, n: int) -> list[str]:
        ...

    @abstractmethod
    def update(self, strategy: str, reward: float) -> None:
        ...

    @abstractmethod
    def load_priors(self, strategy_stats: Dict[str, Dict[str, float]]) -> None:
        ...

    @abstractmethod
    def get_stats(self) -> Dict[str, BanditStats]:
        ...

    @abstractmethod
    def record_cost(self, strategy_key: str, llm_calls: int, estimated_tokens: int, success: bool) -> None:
        ...


class IStrategyRegistry(ABC):
    """Interface para o catálogo de estratégias de mutação."""

    @abstractmethod
    def set_job_id(self, job_id: str) -> None:
        ...

    @abstractmethod
    def add_strategy(self, key: str, name: str, prompt: str) -> str | None:
        """Adds a strategy. Returns the existing key if name already registered, else None."""
        ...

    @abstractmethod
    def get_prompt(self, key: str) -> str:
        ...

    @abstractmethod
    def get_name(self, key: str) -> str:
        ...

    @abstractmethod
    def get_all_keys(self) -> List[str]:
        ...