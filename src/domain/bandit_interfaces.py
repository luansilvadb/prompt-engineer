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


class IMutationBandit(ABC):
    """Interface para o Multi-Armed Bandit de seleção de estratégia."""

    @abstractmethod
    def select(self) -> str:
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


class IStrategyRegistry(ABC):
    """Interface para o catálogo de estratégias de mutação."""

    @abstractmethod
    def set_job_id(self, job_id: str) -> None:
        ...

    @abstractmethod
    def add_strategy(self, key: str, name: str, prompt: str) -> None:
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