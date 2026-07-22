"""
Mutation Strategies — Multi-Armed Bandit (UCB1 + Thompson Sampling) para seleção.

Responsabilidade única deste módulo: selecionar a estratégia de mutação
via UCB1 com Thompson Sampling (Boltzmann softmax), rastreando dinamicamente
estratégias que aparecem ao longo do tempo. O braço '__DISCOVER__' força o
sistema a inventar uma heurística totalmente nova (Tabula Rasa).

Extraído de `src/mutations.py` (Phase 1 densification, ARC-03/D-01).
ARC-02 (D-02): `select()` foi achatado extraindo dois auxiliares privados
(`_pick_untried`, `_ucb_score`) — funções simples, NÃO hierarquia OO
(CONTEXT.md D-02 proíbe OO Strategy). O comportamento externo é
inalterado (mesmo I/O); apenas a estrutura interna de `select()` foi
simplificada.

Melhoria ARC-04: Thompson Sampling com temperatura decrescente (annealing)
substitui o argmax determinístico, garantindo exploração contínua
proporcional à incerteza residual.
"""

import math
import random
from typing import Dict, List, Optional

from src.domain.bandit_interfaces import BanditStats, IMutationBandit
from src.mutation_strategies.registry import registry


class MutationBandit(IMutationBandit):
    """
    Seleciona a estratégia de mutação usando UCB1 + Thompson Sampling.

    Rastreia dinamicamente estratégias que aparecem ao longo do tempo.
    Sempre contém o braço '__DISCOVER__' para invenção.

    Thompson Sampling via Boltzmann softmax com temperatura decrescente
    (annealing): quanto menor a temperatura, mais exploitation; quanto
    maior, mais exploration. A temperatura parte de T_init e decai
    exponencialmente a cada select(), convergindo para exploitation
    puro quando a evidência acumulada justificar.
    """

    def __init__(self, c_param: float = 1.41, temperature: float = 2.0, temperature_decay: float = 0.95):
        self.c_param = c_param
        self.temperature = temperature
        self.temperature_decay = temperature_decay
        self._counts: Dict[str, int] = {'__DISCOVER__': 0}
        self._rewards: Dict[str, float] = {'__DISCOVER__': 0.0}
        self._round_robin_index: int = 0
        self._known_strategies: List[str] = []

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

    def _boltzmann_probs(self, ucb_scores: Dict[str, float]) -> List[tuple]:
        """Calcula probabilidades Boltzmann (softmax) sobre scores UCB1.

        Thompson Sampling via softmax: P(s) ∝ exp(UCB(s) / T).
        Temperatura alta (T >> 1) → distribuição quase uniforme (exploração).
        Temperatura baixa (T → 0) → distribuição concentrada no argmax (exploitation).

        Returns:
            Lista de tuplas (strategy_key, probability) ordenada desc por prob.
        """
        if self.temperature <= 0.001:
            # Temperatura negligível → argmax determinístico
            best = max(ucb_scores, key=ucb_scores.get)
            return [(best, 1.0)]

        exp_scores = {}
        for s, score in ucb_scores.items():
            exp_scores[s] = math.exp(score / self.temperature)

        total = sum(exp_scores.values())
        if total == 0.0:
            # Fallback: uniforme
            n = len(ucb_scores)
            return [(s, 1.0 / n) for s in ucb_scores]

        probs = [(s, exp_scores[s] / total) for s in ucb_scores]
        probs.sort(key=lambda x: x[1], reverse=True)
        return probs

    def _sample_from_probs(self, probs: List[tuple]) -> str:
        """Amostra uma estratégia ponderada pelas probabilidades de Boltzmann."""
        r = random.random()
        cumulative = 0.0
        for strategy, prob in probs:
            cumulative += prob
            if r <= cumulative:
                return strategy
        # Fallback numérico: retorna a mais provável
        return probs[0][0]

    def select(self) -> str:
        for k in registry.get_all_keys():
            self._ensure_key(k)

        # ── Round-Robin inicial: testa cada estratégia uma vez antes do UCB ─
        # Elimina a variância das primeiras escolhas do bandit.
        # __DISCOVER__ é excluído propositalmente — só deve ser acionado pelo UCB.
        if not self._known_strategies:
            self._known_strategies = sorted(
                [k for k in self._counts.keys() if k != '__DISCOVER__']
            )
        if self._round_robin_index < len(self._known_strategies):
            chosen = self._known_strategies[self._round_robin_index]
            self._round_robin_index += 1
            self._decay_temperature()
            return chosen
        # ── Fim Round-Robin ──────────────────────────────────────────────────

        total_pulls = sum(self._counts.values())

        untried = self._pick_untried()
        if untried is not None:
            self._decay_temperature()
            return untried

        ucb_scores = {s: self._ucb_score(s, total_pulls) for s in self._counts}
        probs = self._boltzmann_probs(ucb_scores)
        chosen = self._sample_from_probs(probs)

        self._decay_temperature()
        return chosen

    def _decay_temperature(self):
        """Decaimento exponencial da temperatura a cada select()."""
        self.temperature *= self.temperature_decay

    def update(self, strategy: str, reward: float):
        self._ensure_key(strategy)
        self._counts[strategy] += 1
        self._rewards[strategy] += reward

    def get_stats(self) -> Dict[str, BanditStats]:
        return {
            key: BanditStats(
                strategy_key=key,
                count=self._counts[key],
                mean_delta=self._rewards[key] / max(1, self._counts[key]),
                total_reward=self._rewards[key],
            )
            for key in self._counts
        }