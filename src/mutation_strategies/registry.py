"""
Mutation Strategies — Registry (Dynamic Strategy Store)

Catálogo de estratégias de mutação que o MCTS pode aplicar, com suporte
a descoberta autônoma de novas estratégias (Tabula Rasa).

Responsabilidade única deste módulo: persistência e acesso ao catálogo de
estratégias. A seleção por bandit vive em `bandit.py`; a fachada pública
(`get_mutation_prompt`/`get_strategy_description`) vive em `api.py`.

Extraído de `src/mutations.py` (Phase 1 densification, ARC-03/D-01). O
caminho legado `src.mutations` continua resolvendo via re-export shim
(plano 01-05), então consumidores como `optimizer.py` e
`test_discoverer.py` não precisam mudar.
"""

import json
import os
from pathlib import Path
from typing import Dict, List

STRATEGIES_DIR = Path('src/outputs/strategies')


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
        temp_path = path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.strategies, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
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
