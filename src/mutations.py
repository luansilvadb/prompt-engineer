"""
Mutation Strategies — Policy Diversification & Open-Ended Discovery

Catálogo de estratégias de mutação que o MCTS pode aplicar, com suporte
a descoberta autônoma de novas estratégias (Tabula Rasa).

Um Multi-Armed Bandit (UCB1) seleciona a estratégia. O braço __DISCOVER__
força o sistema a inventar uma heurística totalmente nova, expandindo
seu próprio catálogo de "reflexos cognitivos".

Referência: David Silver — "Throwing out human data forces the creation
of infinitely scalable self-learning mechanisms"
"""

import json
import math
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

STRATEGIES_DIR = Path('src/outputs/strategies')

# ─────────────────────────────────────────────
# Registro de Estratégias (Dynamic Strategy Store)
# ─────────────────────────────────────────────

class StrategyRegistry:
    def __init__(self):
        self.strategies: Dict[str, Dict[str, str]] = {}
        self._load()
        
    def _store_path(self) -> Path:
        STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
        return STRATEGIES_DIR / 'discovered_strategies.json'
        
    def _load(self):
        path = self._store_path()
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.strategies = json.load(f)
            except Exception:
                self.strategies = {}

    def save(self):
        path = self._store_path()
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(self.strategies, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add_strategy(self, key: str, name: str, prompt: str):
        self.strategies[key] = {'name': name, 'prompt': prompt}
        self.save()

    def get_prompt(self, key: str) -> str:
        if key == '__DISCOVER__':
            return ''
        return self.strategies.get(key, {}).get('prompt', '')

    def get_name(self, key: str) -> str:
        if key == '__DISCOVER__':
            return 'Descoberta Autônoma de Reflexo (Tabula Rasa)'
        return self.strategies.get(key, {}).get('name', key)
        
    def get_all_keys(self) -> List[str]:
        return list(self.strategies.keys())

# Instância global do registry
registry = StrategyRegistry()

# ─────────────────────────────────────────────
# Multi-Armed Bandit (UCB1) para seleção
# ─────────────────────────────────────────────

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

    def select(self) -> str:
        for k in registry.get_all_keys():
            self._ensure_key(k)
            
        total_pulls = sum(self._counts.values())

        untried = [s for s in self._counts.keys() if self._counts[s] == 0]
        if untried:
            return random.choice(untried)

        def ucb_score(strategy: str) -> float:
            n = self._counts[strategy]
            mean_reward = self._rewards[strategy] / max(1, n)
            exploration = self.c_param * math.sqrt(math.log(total_pulls) / n)
            return mean_reward + exploration

        return max(self._counts.keys(), key=ucb_score)

    def update(self, strategy: str, reward: float):
        self._ensure_key(strategy)
        self._counts[strategy] += 1
        self._rewards[strategy] += reward


def get_mutation_prompt(strategy: str) -> str:
    return registry.get_prompt(strategy)

def get_strategy_description(strategy: str) -> str:
    return registry.get_name(strategy)
