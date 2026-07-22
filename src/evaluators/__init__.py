"""Avaliadores — densidade, heurísticas, semântica e estimativa de valor.

Consolidado de:
- density_evaluator.py → density.py
- heuristic_evaluator.py → heuristic.py
- semantic_evaluator.py → semantic.py
- value_estimator.py → value.py
"""

from src.evaluators.density import (
    DensityContext,
    DensityMultiplier,
    DensityResult,
    DensityResultFloat,
    calculate_density_multiplier,
    compute_lexical_density,
)
from src.evaluators.heuristic import evaluate_heuristics
from src.evaluators.semantic import calculate_semantic_penalty, get_embedder
from src.evaluators.value import ValueEstimator

__all__ = [
    "DensityContext",
    "DensityMultiplier",
    "DensityResult",
    "DensityResultFloat",
    "ValueEstimator",
    "calculate_density_multiplier",
    "calculate_semantic_penalty",
    "compute_lexical_density",
    "evaluate_heuristics",
    "get_embedder",
]
