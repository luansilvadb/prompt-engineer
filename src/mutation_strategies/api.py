"""
Mutation Strategies — Fachada pública (thin API).

Responsabilidade única deste módulo: expor os acessores de prompt/nome de
estratégia como funções de nível de módulo, delegando ao singleton
`registry`. Estes nomes são load-bearing — `optimizer.py` os consome
diretamente (L257/258/424/432). Assinaturas são idênticas às do legado
`src/mutations.py` L128-132.

Extraído de `src/mutations.py` (Phase 1 densification, ARC-03/D-01).
"""

from src.mutation_strategies.registry import registry


def get_mutation_prompt(strategy: str) -> str:
    return registry.get_prompt(strategy)


def get_strategy_description(strategy: str) -> str:
    return registry.get_name(strategy)
