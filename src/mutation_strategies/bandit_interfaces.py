from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Protocol


@dataclass(frozen=True)
class BanditStats:
    strategy_key: str
    count: int
    mean_delta: float
    total_reward: float


class IMutationBandit(Protocol):
    """
    Contrato do Multi-Armed Bandit de estratégias de mutação (UCB1).
    Separa seleção de atualização para testabilidade.
    """

    def select(self) -> str:
        ...

    def update(self, strategy_key: str, reward: float) -> None:
        ...

    def load_priors(self, stats: Dict[str, Dict[str, float]]) -> None:
        ...

    def get_stats(self) -> Dict[str, BanditStats]:
        ...


class IStrategyRegistry(Protocol):
    """Contrato do catálogo de estratégias dinâmicas."""

    def set_job_id(self, job_id: str) -> None:
        ...

    def add_strategy(self, key: str, name: str, prompt: str) -> None:
        ...

    def get_prompt(self, key: str) -> str:
        ...

    def get_name(self, key: str) -> str:
        ...

    def get_all_keys(self) -> List[str]:
        ...
