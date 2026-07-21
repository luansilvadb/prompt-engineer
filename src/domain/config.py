from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class MCTSConfig:
    gamma: float
    c_param: float
    progressive_alpha: float
    progressive_c: float
    value_threshold: float
    max_iterations: int
    value_lr: float
    bandit_c_param: float
    bandit_temperature: float
    bandit_temperature_decay: float
    semantic_sim_threshold: float
    lexical_density_min: float
    verbosity_penalty_factor: float
    buzzword_threshold: int
    cognitivo_prior_count: int
    cognitivo_prior_mean_delta: float
    density_multiplier_min: float
    density_multiplier_max: float
    density_threshold: float
    density_structured_bonus: float
    reward_floor: float
    mcts_early_termination_threshold: float = 0.95
    rave_k: float = 10.0
    virtual_loss_weight: float = 1.0
    num_threads: int = 4
    root_median_samples: int = 1
    selection_policy: str = "puct"
    c_bias: float = 0.5

    def __post_init__(self) -> None:
        if self.selection_policy not in ("puct", "ucb1_tuned", "ucb1"):
            raise ValueError(f"selection_policy deve ser um de ('puct', 'ucb1_tuned', 'ucb1'), recebeu '{self.selection_policy}'")
        if not (0.0 < self.gamma <= 1.0):
            raise ValueError("gamma must be in (0.0, 1.0]")
        if self.c_param <= 0.0:
            raise ValueError("c_param must be positive")
        if not (0.0 < self.progressive_alpha <= 1.0):
            raise ValueError("progressive_alpha must be in (0.0, 1.0]")
        if self.progressive_c <= 0.0:
            raise ValueError("progressive_c must be positive")
        if not (0.0 <= self.value_threshold <= 1.0):
            raise ValueError("value_threshold must be in [0.0, 1.0]")
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        if self.density_multiplier_min <= 0.0:
            raise ValueError("density_multiplier_min must be positive")
        if self.density_multiplier_max < self.density_multiplier_min:
            raise ValueError("density_multiplier_max must be >= density_multiplier_min")
        if self.root_median_samples < 1 or self.root_median_samples % 2 != 1:
            raise ValueError(
                f"root_median_samples must be an odd integer >= 1, got {self.root_median_samples}"
            )


@dataclass(frozen=True)
class DriftConfig:
    spearman_floor: float
    spearman_regression_margin: float
    offset_alarm: float
    offset_regression_margin: float
    variance_low_confidence: float
    repetitions: int

    def __post_init__(self) -> None:
        if not (0.0 <= self.spearman_floor <= 1.0):
            raise ValueError("spearman_floor must be in [0.0, 1.0]")
        if self.repetitions < 1:
            raise ValueError("repetitions must be at least 1")
        if self.offset_alarm <= 0.0:
            raise ValueError("offset_alarm must be positive")


def load_mcts_config() -> MCTSConfig:
    load_dotenv()
    return MCTSConfig(
        gamma=float(os.environ.get("MCTS_GAMMA", "0.95")),
        c_param=float(os.environ.get("MCTS_C_PARAM", "1.41")),
        progressive_alpha=float(os.environ.get("MCTS_PROGRESSIVE_ALPHA", "0.5")),
        progressive_c=float(os.environ.get("MCTS_PROGRESSIVE_C", "2.0")),
        value_threshold=float(os.environ.get("MCTS_VALUE_THRESHOLD", "0.2")),
        max_iterations=int(os.environ.get("MCTS_MAX_ITERATIONS", "10")),
        value_lr=float(os.environ.get("MCTS_VALUE_LR", "0.1")),
        bandit_c_param=float(os.environ.get("MCTS_BANDIT_C_PARAM", "1.41")),
        bandit_temperature=float(os.environ.get("MCTS_BANDIT_TEMPERATURE", "2.0")),
        bandit_temperature_decay=float(os.environ.get("MCTS_BANDIT_TEMPERATURE_DECAY", "0.95")),
        semantic_sim_threshold=float(os.environ.get("MCTS_SEMANTIC_SIM_THRESHOLD", "0.85")),
        lexical_density_min=float(os.environ.get("MCTS_LEXICAL_DENSITY_MIN", "0.35")),
        verbosity_penalty_factor=float(os.environ.get("MCTS_VERBOSITY_PENALTY_FACTOR", "0.85")),
        buzzword_threshold=int(os.environ.get("MCTS_BUZZWORD_THRESHOLD", "3")),
        cognitivo_prior_count=int(os.environ.get("MCTS_COGNITIVO_PRIOR_COUNT", "1")),
        cognitivo_prior_mean_delta=float(os.environ.get("MCTS_COGNITIVO_PRIOR_MEAN_DELTA", "0.05")),
        density_multiplier_min=float(os.environ.get("MCTS_DENSITY_MULTIPLIER_MIN", "0.5")),
        density_multiplier_max=float(os.environ.get("MCTS_DENSITY_MULTIPLIER_MAX", "1.5")),
        density_threshold=float(os.environ.get("MCTS_DENSITY_THRESHOLD", "1.0")),
        density_structured_bonus=float(os.environ.get("MCTS_DENSITY_STRUCTURED_BONUS", "0.2")),
        reward_floor=float(os.environ.get("MCTS_REWARD_FLOOR", "0.30")),
        mcts_early_termination_threshold=float(os.environ.get("MCTS_EARLY_TERMINATION_THRESHOLD", "0.95")),
        rave_k=float(os.environ.get("MCTS_RAVE_K", "10.0")),
        virtual_loss_weight=float(os.environ.get("MCTS_VIRTUAL_LOSS_WEIGHT", "1.0")),
        num_threads=int(os.environ.get("MCTS_NUM_THREADS", "4")),
        root_median_samples=int(os.environ.get("MCTS_ROOT_MEDIAN_SAMPLES", "1")),
        selection_policy=os.environ.get("MCTS_SELECTION_POLICY", "puct"),
        c_bias=float(os.environ.get("MCTS_C_BIAS", "0.5")),
    )


def load_drift_config() -> DriftConfig:
    load_dotenv()
    return DriftConfig(
        spearman_floor=float(os.environ.get("DRIFT_SPEARMAN_FLOOR", "0.8")),
        spearman_regression_margin=float(os.environ.get("DRIFT_SPEARMAN_REGRESSION_MARGIN", "0.05")),
        offset_alarm=float(os.environ.get("DRIFT_OFFSET_ALARM", "10.0")),
        offset_regression_margin=float(os.environ.get("DRIFT_OFFSET_REGRESSION_MARGIN", "3.0")),
        variance_low_confidence=float(os.environ.get("DRIFT_VARIANCE_LOW_CONFIDENCE", "8.0")),
        repetitions=int(os.environ.get("DRIFT_REPETITIONS", "3")),
    )
