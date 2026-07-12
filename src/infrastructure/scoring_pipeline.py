from __future__ import annotations

from src.domain.scoring_pipeline import CompositeScore, HeuristicResult, IScoringPipeline
from src.density_evaluator import calculate_density_multiplier
from src.semantic_evaluator import calculate_semantic_penalty


class ScoringPipeline(IScoringPipeline):
    """RN-SCORE-01: raw_reward × heuristic × semantic × density → shaped_reward."""

    def __init__(
        self,
        semantic_sim_threshold: float,
        density_threshold: float,
        density_multiplier_min: float,
        density_multiplier_max: float,
        density_structured_bonus: float,
        lexical_density_min: float,
    ) -> None:
        self._semantic_sim_threshold = semantic_sim_threshold
        self._density_threshold = density_threshold
        self._density_multiplier_min = density_multiplier_min
        self._density_multiplier_max = density_multiplier_max
        self._density_structured_bonus = density_structured_bonus
        self._lexical_density_min = lexical_density_min

    def run(
        self,
        raw_reward: float,
        candidate_instruction: str,
        parent_instruction: str,
        mutation_strategy: str,
        heuristic_result: HeuristicResult,
    ) -> CompositeScore:
        heuristic_multiplier = heuristic_result.penalty_multiplier
        semantic_multiplier = calculate_semantic_penalty(
            candidate_instruction,
            parent_instruction,
            threshold=self._semantic_sim_threshold,
        )
        density_multiplier = float(
            calculate_density_multiplier(
                child_instruction=candidate_instruction,
                parent_instruction=parent_instruction,
                mutation_strategy=mutation_strategy,
                density_threshold=self._density_threshold,
                density_multiplier_min=self._density_multiplier_min,
                density_multiplier_max=self._density_multiplier_max,
                structured_bonus=self._density_structured_bonus,
                min_density=self._lexical_density_min,
            )
        )
        shaped_reward = (
            raw_reward
            * heuristic_multiplier
            * semantic_multiplier
            * density_multiplier
        )
        return CompositeScore(
            raw_reward=raw_reward,
            heuristic_multiplier=heuristic_multiplier,
            semantic_multiplier=semantic_multiplier,
            density_multiplier=density_multiplier,
            shaped_reward=shaped_reward,
        )
