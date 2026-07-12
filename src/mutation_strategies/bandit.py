"""
Mutation Strategies — Multi-Armed Bandit (UCB1) para seleção.

Responsabilidade única deste módulo: selecionar a estratégia de mutação
via UCB1, rastreando dinamicamente estratégias que aparecem ao longo do
tempo. O braço '__DISCOVER__' força o sistema a inventar uma heurística
totalmente nova (Tabula Rasa).

Extraído de `src/mutations.py` (Phase 1 densification, ARC-03/D-01).
ARC-02 (D-02): `select()` foi achatado extraindo dois auxiliares privados
(`_pick_untried`, `_ucb_score`) — funções simples, NÃO hierarquia OO
(CONTEXT.md D-02 proíbe OO Strategy). O comportamento externo é
inalterado (mesmo I/O); apenas a estrutura interna de `select()` foi
simplificada.
"""

import math
import random
from typing import Dict, Optional

from src.mutation_strategies.registry import registry


class MutationBandit:
    """
    Seleciona a estratégia de mutação usando UCB1.
    Rastreia dinamicamente estratégias que aparecem ao longo do tempo.
    Sempre contém o braço '__DISCOVER__' para invenção.
    """

    def __init__(self, c_param: float = 1.41):
        self.c_param = c_param
        self._counts: Dict[str, int] = {'__DISCOVER__': 0}
        self._rewards: Dict[str, float] = {'__DISCOVER__': 0.0}

        for k in registry.get_all_keys():
            self._ensure_key(k)

    def _ensure_key(self, strategy: str):
        if strategy not in self._counts:
            self._counts[strategy] = 0
            self._rewards[strategy] = 0.0

    def load_priors(self, strategy_stats: Dict[str, Dict[str, float]]):
        for strategy, stats in strategy_stats.items():
            self._ensure_key(strategy)
            virtual_count = min(int(stats['count'] * 0.5), 10)
            self._counts[strategy] += virtual_count
            self._rewards[strategy] += stats.get('mean_delta', 0.0) * virtual_count

    def _pick_untried(self) -> Optional[str]:
        """Estratégia ainda não explorada, ou None se todas já tiverem pulls.

        Preserva o comportamento original de seleção aleatória entre os
        braços não tentados (UCB1 first-play). Encapsula o ramo
        untried-first que antes vivia inline em `select()`.
        """
        untried = [s for s in self._counts.keys() if self._counts[s] == 0]
        if untried:
            return random.choice(untried)
        return None

    def _ucb_score(self, strategy: str, total_pulls: int) -> float:
        """Score UCB1 de um braço: recompensa média + bônus de exploração.

        Promove o closure inline que antes vivia dentro de `select()` a
        método nomeado, sem alterar a fórmula.
        """
        n = self._counts[strategy]
        mean_reward = self._rewards[strategy] / max(1, n)
        exploration = self.c_param * math.sqrt(math.log(total_pulls) / n)
        return mean_reward + exploration

    def select(self) -> str:
        for k in registry.get_all_keys():
            self._ensure_key(k)

        total_pulls = sum(self._counts.values())

        untried = self._pick_untried()
        if untried is not None:
            return untried

        return max(self._counts.keys(), key=lambda s: self._ucb_score(s, total_pulls))

    def update(self, strategy: str, reward: float):
        self._ensure_key(strategy)
        self._counts[strategy] += 1
        self._rewards[strategy] += reward

    def get_stats(self) -> dict:
        from src.mutation_strategies.bandit_interfaces import BanditStats
        return {
            key: BanditStats(
                strategy_key=key,
                count=self._counts[key],
                mean_delta=self._rewards[key] / max(1, self._counts[key]),
                total_reward=self._rewards[key],
            )
            for key in self._counts
        }
