"""
Compatibility shim (Phase 1 densification).
Implementation now lives under src.mutation_strategies.*
"""

from src.mutation_strategies.registry import StrategyRegistry, registry
from src.mutation_strategies.bandit import MutationBandit
from src.mutation_strategies.api import get_mutation_prompt, get_strategy_description

__all__ = [
    'StrategyRegistry',
    'registry',
    'MutationBandit',
    'get_mutation_prompt',
    'get_strategy_description'
]
