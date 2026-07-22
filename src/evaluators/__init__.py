"""Avaliadores — densidade, heurísticas, semântica e estimativa de valor."""

from src.evaluators.density import calculate_density_multiplier, compute_lexical_density
from src.evaluators.heuristic import evaluate_heuristics
from src.evaluators.semantic import calculate_semantic_penalty, get_embedder
from src.evaluators.value import ValueEstimator

__all__ = [
    "ValueEstimator",
    "calculate_density_multiplier",
    "calculate_semantic_penalty",
    "compute_lexical_density",
    "evaluate_heuristics",
    "get_embedder",
]
