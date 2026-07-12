from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class HeuristicResult:
    prune: bool
    penalty_multiplier: float
    reason: str

    def __post_init__(self) -> None:
        if not (0.0 <= self.penalty_multiplier <= 1.0):
            raise ValueError("penalty_multiplier must be in [0.0, 1.0]")


@dataclass(frozen=True)
class SemanticPenaltyResult:
    penalty_multiplier: float
    similarity_score: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.penalty_multiplier <= 1.0):
            raise ValueError("penalty_multiplier must be in [0.0, 1.0]")


@dataclass(frozen=True)
class DensityMultiplierResult:
    multiplier: float
    direction: str

    def __post_init__(self) -> None:
        if self.multiplier <= 0.0:
            raise ValueError("multiplier must be positive")


@dataclass(frozen=True)
class CompositeScore:
    raw_reward: float
    heuristic_multiplier: float
    semantic_multiplier: float
    density_multiplier: float
    shaped_reward: float

    @property
    def final_score(self) -> float:
        return self.shaped_reward


class IHeuristicEvaluator(Protocol):
    def evaluate(
        self,
        instruction: str,
        density_min: float,
        penalty_factor: float,
        buzzword_threshold: int,
    ) -> HeuristicResult:
        ...


class ISemanticEvaluator(Protocol):
    def evaluate(
        self,
        candidate_instruction: str,
        parent_instruction: str,
        threshold: float,
    ) -> SemanticPenaltyResult:
        ...


class IDensityEvaluator(Protocol):
    def evaluate(
        self,
        child_instruction: str,
        parent_instruction: str,
        mutation_strategy: str,
        density_threshold: float,
        multiplier_min: float,
        multiplier_max: float,
        structured_bonus: float,
    ) -> DensityMultiplierResult:
        ...


class IValueEstimator(Protocol):
    @property
    def confidence(self) -> float:
        ...

    def estimate(self, instruction: str) -> float:
        ...

    def update(self, instruction: str, actual_reward: float) -> None:
        ...


class IScoringPipeline(Protocol):
    """
    Encapsula a sequência obrigatória de scoring (RN-SCORE-01):
    raw_reward × heuristic × semantic × density → shaped_reward.
    """

    def run(
        self,
        raw_reward: float,
        candidate_instruction: str,
        parent_instruction: str,
        mutation_strategy: str,
        heuristic_result: HeuristicResult,
    ) -> CompositeScore:
        ...
