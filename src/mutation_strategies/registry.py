"""
Mutation Strategies — Registry (Dynamic Strategy Store)

Catálogo de estratégias de mutação que o MCTS pode aplicar, com suporte
a descoberta autônoma de novas estratégias (Tabula Rasa).

Responsabilidade única deste módulo: persistência e acesso ao catálogo de
estratégias. A seleção por bandit vive em `bandit.py`; a fachada pública
(`get_strategy_description`) vive em `api.py`.

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
        self.job_id = None
        self.strategies: Dict[str, Dict[str, str]] = {}
        self._load()
        self._seed_hardcoded_strategies()

    def set_job_id(self, job_id: str):
        """Define o escopo da sessão (job) e recarrega as estratégias locais."""
        self.job_id = job_id
        self._load()
        self._seed_hardcoded_strategies()

    def _store_path(self) -> Path:
        STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
        if self.job_id:
            return STRATEGIES_DIR / f'discovered_strategies_{self.job_id}.json'
        return STRATEGIES_DIR / 'discovered_strategies.json'

    def _load(self):
        self.strategies = {}
        path = self._store_path()
        if path.exists():
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                seen_names: set[str] = set()
                deduplicated: dict[str, dict[str, str]] = {}
                for key, entry in raw.items():
                    name = entry.get('name', '')
                    if name in seen_names:
                        continue
                    seen_names.add(name)
                    deduplicated[key] = entry
                self.strategies = deduplicated
                if len(deduplicated) < len(raw):
                    self.save()
            except Exception:
                pass

    def save(self):
        path = self._store_path()
        temp_path = path.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.strategies, f, ensure_ascii=False, indent=2)
            os.replace(temp_path, path)
        except Exception:
            pass

    def add_strategy(self, key: str, name: str, prompt: str) -> str | None:
        for existing_key, s in self.strategies.items():
            if s['name'] == name:
                return existing_key
        self.strategies[key] = {'name': name, 'prompt': prompt}
        self.save()
        return None

    def get_prompt(self, key: str) -> str:
        if key == '__DISCOVER__':
            return ''
        return self.strategies.get(key, {}).get('prompt', '')

    def get_name(self, key: str) -> str:
        if key == '__DISCOVER__':
            return 'Descoberta Autônoma de Reflexo (Tabula Rasa)'
        return self.strategies.get(key, {}).get('name', key)

    def _seed_hardcoded_strategies(self):
        COGNITIVO_KEY = 'mutador_cognitivo'
        if COGNITIVO_KEY not in self.strategies:
            self.add_strategy(
                key=COGNITIVO_KEY,
                name='Mutador Cognitivo',
                prompt=(
                    "Aplique derivação lógica estruturada obrigatória. "
                    "Antes de reescrever, derive explicitamente: "
                    "(1) Premissas — o que o feedback revela sobre a instrução atual; "
                    "(2) Deduções — implicações lógicas sobre o que precisa mudar; "
                    "(3) Conclusão — a regra arquitetural que a nova instrução deve implementar. "
                    "A nova instrução DEVE conter as seções ## Raciocínio, ## Regras, ## Conclusão."
                )
            )

    def get_all_keys(self) -> List[str]:
        return list(self.strategies.keys())


# Instância global do registry
registry = StrategyRegistry()
