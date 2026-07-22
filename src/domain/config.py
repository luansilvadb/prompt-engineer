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
        _validate_selection_policy(self.selection_policy)
        _validate_bounds(self.gamma, self.c_param, self.progressive_c)
        _validate_thresholds(self.progressive_alpha, self.value_threshold, self.max_iterations)
        _validate_density(self.density_multiplier_min, self.density_multiplier_max)
        _validate_root_samples(self.root_median_samples)


def _validate_selection_policy(policy: str) -> None:
    if policy not in ("puct", "ucb1_tuned", "ucb1"):
        raise ValueError(f"selection_policy deve ser um de ('puct', 'ucb1_tuned', 'ucb1'), recebeu '{policy}'")


def _validate_bounds(gamma: float, c_param: float, progressive_c: float) -> None:
    if not (0.0 < gamma <= 1.0):
        raise ValueError("gamma must be in (0.0, 1.0]")
    if c_param <= 0.0:
        raise ValueError("c_param must be positive")
    if progressive_c <= 0.0:
        raise ValueError("progressive_c must be positive")


def _validate_thresholds(progressive_alpha: float, value_threshold: float, max_iterations: int) -> None:
    if not (0.0 < progressive_alpha <= 1.0):
        raise ValueError("progressive_alpha must be in (0.0, 1.0]")
    if not (0.0 <= value_threshold <= 1.0):
        raise ValueError("value_threshold must be in [0.0, 1.0]")
    if max_iterations < 1:
        raise ValueError("max_iterations must be at least 1")


def _validate_density(density_multiplier_min: float, density_multiplier_max: float) -> None:
    if density_multiplier_min <= 0.0:
        raise ValueError("density_multiplier_min must be positive")
    if density_multiplier_max < density_multiplier_min:
        raise ValueError("density_multiplier_max must be >= density_multiplier_min")


def _validate_root_samples(root_median_samples: int) -> None:
    if root_median_samples < 1 or root_median_samples % 2 != 1:
        raise ValueError(
            f"root_median_samples must be an odd integer >= 1, got {root_median_samples}"
        )


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
