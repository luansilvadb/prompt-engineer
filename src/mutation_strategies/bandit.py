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

from __future__ import annotations

import logging
import math
import random
import threading
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

    def __init__(self, c_param: float = 1.41, temperature: float = 2.0, temperature_decay: float = 0.95,
                 composition_probability: float = 0.3, composition_max_strategies: int = 3):
        self.c_param = c_param
        self.temperature = temperature
        self.temperature_decay = temperature_decay
        self.composition_probability = composition_probability
        self.composition_max_strategies = composition_max_strategies
        self._counts: Dict[str, int] = {'__DISCOVER__': 0}
        self._rewards: Dict[str, float] = {'__DISCOVER__': 0.0}
        self._total_llm_calls: Dict[str, int] = {'__DISCOVER__': 0}
        self._estimated_tokens: Dict[str, int] = {'__DISCOVER__': 0}
        self._successful_expansions: Dict[str, int] = {'__DISCOVER__': 0}
        self._round_robin_index: int = 0
        self._known_strategies: List[str] = []
        self._lock = threading.Lock()

        for k in registry.get_all_keys():
            self._ensure_key(k)

    def _ensure_key(self, strategy: str):
        if strategy not in self._counts:
            self._counts[strategy] = 0
            self._rewards[strategy] = 0.0
        if strategy not in self._total_llm_calls:
            self._total_llm_calls[strategy] = 0
            self._estimated_tokens[strategy] = 0
            self._successful_expansions[strategy] = 0

    def load_priors(self, strategy_stats: Dict[str, Dict[str, float]]):
        with self._lock:
            for strategy, stats in strategy_stats.items():
                self._ensure_key(strategy)
                mean_delta = stats.get('mean_delta', 0.0)
                mean_reward = stats.get('mean_reward', None)

                # Validação de escala canônica: valores devem estar em [0, 1]
                if mean_reward is not None and (mean_reward < 0.0 or mean_reward > 1.0):
                    logger = logging.getLogger('mcts.bandit')
                    logger.warning(
                        f'Possível inconsistência de escala nos priors do bandit: '
                        f'estratégia={strategy}, mean_reward={mean_reward:.3f} fora de [0, 1]. '
                        f'Clampando para [0, 1].'
                    )
                    mean_reward = max(0.0, min(1.0, mean_reward))

                # Estratégias com desempenho histórico negativo não recebem boost
                if mean_delta < 0:
                    virtual_count = 1  # mínimo, sem prior boost
                    logger = logging.getLogger('mcts.bandit')
                    logger.warning(
                        f'Estratégia {strategy} tem desempenho histórico negativo '
                        f'(mean_delta={mean_delta:.3f}), virtual_count reduzido para 1.'
                    )
                else:
                    virtual_count = max(1, min(int(stats['count'] * 0.5), 10))

                self._counts[strategy] += virtual_count
                self._rewards[strategy] += mean_delta * virtual_count

    def _pick_untried(self) -> Optional[str]:
        """Estratégia ainda não explorada, ou None se todas já tiverem pulls.

        Preserva o comportamento original de seleção aleatória entre os
        braços não tentados (UCB1 first-play). Inclui __DISCOVER__ —
        o bloqueio para primeira expansão é feito via force_known em _pick_strategy.
        """
        untried = [s for s in self._counts.keys() if self._counts[s] == 0]
        if untried:
            return random.choice(untried)
        return None

    def _ucb_score(self, strategy: str, total_pulls: int) -> float:
        """Score UCB1 de um braço: recompensa média + bônus de exploração.

        Promove o closure inline que antes vivia dentro de `select()` a
        método nomeado, sem alterar a fórmula.

        Aplica penalidade de custo para estratégias com custo por aprovação
        significativamente acima da mediana (somente quando há dados de
        successful_expansions).
        """
        n = self._counts[strategy]
        if n == 0:
            return float('inf')  # Nunca puxado → prioridade máxima
        mean_reward = self._rewards[strategy] / n
        exploration = self.c_param * math.sqrt(math.log(total_pulls) / n)
        score = mean_reward + exploration

        # ── Cost-based penalty ──────────────────────────────────────────
        successful = self._successful_expansions.get(strategy, 0)
        if successful > 0:
            # Coleta cost_per_approval de todas as estratégias com dados
            costs: List[float] = []
            for s in self._total_llm_calls:
                s_successful = self._successful_expansions.get(s, 0)
                if s_successful > 0:
                    s_calls = self._total_llm_calls.get(s, 0)
                    costs.append(s_calls / s_successful)

            if costs:
                costs.sort()
                n_costs = len(costs)
                if n_costs % 2 == 0:
                    median = (costs[n_costs // 2 - 1] + costs[n_costs // 2]) / 2.0
                else:
                    median = costs[n_costs // 2]

                strategy_cost = self._total_llm_calls.get(strategy, 0) / successful
                if median > 0 and strategy_cost > median * 1.5:
                    penalty = min(0.30, (strategy_cost / max(1, median) - 1.0) * 0.15)
                    score -= penalty

        return score

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

    def _make_composite_key(self, keys: list[str]) -> str:
        """Gera chave composta no formato composite:estrat1+estrat2+..."""
        return f"composite:{'+'.join(keys)}"

    def _sample_multiple_from_probs(self, probs: List[tuple], n: int) -> List[str]:
        """Amostra n estratégias distintas ponderadas pelas probabilidades de Boltzmann.

        Amostragem sem reposição: remove a estratégia selecionada e renormaliza
        as probabilidades restantes a cada passo.
        """
        selected: List[str] = []
        remaining: List[tuple] = list(probs)

        for _ in range(n):
            if not remaining:
                break
            total = sum(p for _, p in remaining)
            if total <= 0.0:
                # Fallback: pega a primeira disponível
                selected.append(remaining[0][0])
                remaining.pop(0)
                continue

            r = random.random()
            cumulative = 0.0
            picked = False
            for i, (strategy, prob) in enumerate(remaining):
                cumulative += prob / total
                if r <= cumulative:
                    selected.append(strategy)
                    remaining.pop(i)
                    picked = True
                    break
            if not picked:
                # Fallback numérico: retorna a mais provável
                selected.append(remaining[0][0])
                remaining.pop(0)

        return selected

    def select(self) -> str | list[str]:
        with self._lock:
            for k in registry.get_all_keys():
                self._ensure_key(k)

            # ── Round-Robin inicial: testa cada estratégia uma vez antes do UCB ─
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

            # ── Composição de estratégias ────────────────────────────────────────
            composable = [
                k for k in self._counts
                if k != '__DISCOVER__' and not k.startswith('composite:')
            ]
            if (self.composition_probability > 0
                    and random.random() < self.composition_probability
                    and len(composable) >= 2):
                max_n = min(self.composition_max_strategies, len(composable))
                n_strategies = random.randint(2, max_n)

                if total_pulls > 0:
                    comp_ucb = {k: self._ucb_score(k, total_pulls) for k in composable}
                    comp_probs = self._boltzmann_probs(comp_ucb)
                    chosen_keys = self._sample_multiple_from_probs(comp_probs, n_strategies)
                else:
                    # Sem dados acumulados, seleção aleatória uniforme
                    chosen_keys = random.sample(composable, n_strategies)

                composite_key = self._make_composite_key(chosen_keys)
                self._ensure_key(composite_key)

                self._decay_temperature()
                return chosen_keys
            # ── Fim Composição ───────────────────────────────────────────────────

            untried = self._pick_untried()
            if untried is not None:
                self._decay_temperature()
                return untried

            ucb_scores = {s: self._ucb_score(s, total_pulls) for s in self._counts}
            probs = self._boltzmann_probs(ucb_scores)
            chosen = self._sample_from_probs(probs)

            self._decay_temperature()
            return chosen

    def force_composition(self, n: int) -> list[str]:
        """Força composição de exatamente n estratégias distintas para abordagem gradativa."""
        with self._lock:
            composable = [
                k for k in self._counts
                if k != '__DISCOVER__' and not k.startswith('composite:')
            ]
            actual_n = min(n, len(composable))
            if actual_n < 2:
                # Fallback: retorna lista com uma estratégia
                return [composable[0]] if composable else ['mutador_cognitivo']

            total_pulls = sum(self._counts.values())
            if total_pulls > 0:
                comp_ucb = {k: self._ucb_score(k, total_pulls) for k in composable}
                comp_probs = self._boltzmann_probs(comp_ucb)
                chosen_keys = self._sample_multiple_from_probs(comp_probs, actual_n)
            else:
                chosen_keys = random.sample(composable, actual_n)

            composite_key = self._make_composite_key(chosen_keys)
            self._ensure_key(composite_key)
            self._decay_temperature()
            return chosen_keys

    def _decay_temperature(self):
        """Decaimento exponencial da temperatura a cada select()."""
        self.temperature *= self.temperature_decay

    def update(self, strategy: str, reward: float):
        with self._lock:
            self._ensure_key(strategy)
            self._counts[strategy] += 1
            self._rewards[strategy] += reward

    def record_cost(self, strategy_key: str, llm_calls: int, estimated_tokens: int, success: bool) -> None:
        with self._lock:
            self._ensure_key(strategy_key)
            self._total_llm_calls[strategy_key] += llm_calls
            self._estimated_tokens[strategy_key] += estimated_tokens
            if success:
                self._successful_expansions[strategy_key] += 1

    def get_stats(self) -> Dict[str, BanditStats]:
        with self._lock:
            return {
                key: BanditStats(
                    strategy_key=key,
                    count=self._counts[key],
                    mean_delta=self._rewards[key] / max(1, self._counts[key]),
                    total_reward=self._rewards[key],
                    total_llm_calls=self._total_llm_calls.get(key, 0),
                    estimated_tokens=self._estimated_tokens.get(key, 0),
                    successful_expansions=self._successful_expansions.get(key, 0),
                )
                for key in self._counts
            }