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
    max_depth: int = 20
    sufficiency_threshold: float = 0.95
    ab_margin_min: float = 0.05
    knowledge_bias_lambda: float = 0.3
    llm_timeout: int = 60
    post_eval_margin_min: float = 0.05
    post_eval_sample_size: int = 5
    composition_max_strategies: int = 3
    composition_probability: float = 0.3
    iteration_timeout_s: int = 300
    iteration_llm_call_limit: int = 50
    composite_timeout_s: int = 45

    def __post_init__(self) -> None:
        _validate_selection_policy(self.selection_policy)
        _validate_bounds(self.gamma, self.c_param, self.progressive_c)
        _validate_thresholds(self.progressive_alpha, self.value_threshold, self.max_iterations)
        _validate_density(self.density_multiplier_min, self.density_multiplier_max)
        _validate_root_samples(self.root_median_samples)
        _validate_max_depth(self.max_depth)
        _validate_sufficiency_threshold(self.sufficiency_threshold)
        _validate_ab_margin_min(self.ab_margin_min)
        _validate_knowledge_bias_lambda(self.knowledge_bias_lambda)
        _validate_llm_timeout(self.llm_timeout)
        _validate_post_eval_margin_min(self.post_eval_margin_min)
        _validate_post_eval_sample_size(self.post_eval_sample_size)
        _validate_composition_max_strategies(self.composition_max_strategies)
        _validate_composition_probability(self.composition_probability)
        _validate_iteration_timeout_s(self.iteration_timeout_s)
        _validate_iteration_llm_call_limit(self.iteration_llm_call_limit)
        _validate_composite_timeout_s(self.composite_timeout_s)


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


def _validate_max_depth(max_depth: int) -> None:
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1")


def _validate_sufficiency_threshold(sufficiency_threshold: float) -> None:
    if not (0.0 <= sufficiency_threshold <= 1.0):
        raise ValueError("sufficiency_threshold must be in [0.0, 1.0]")


def _validate_ab_margin_min(ab_margin_min: float) -> None:
    if not (0.0 <= ab_margin_min <= 1.0):
        raise ValueError("ab_margin_min must be in [0.0, 1.0]")


def _validate_knowledge_bias_lambda(knowledge_bias_lambda: float) -> None:
    if not (0.0 <= knowledge_bias_lambda <= 1.0):
        raise ValueError("knowledge_bias_lambda must be in [0.0, 1.0]")


def _validate_llm_timeout(llm_timeout: int) -> None:
    if llm_timeout < 1:
        raise ValueError("llm_timeout must be at least 1 second")


def _validate_post_eval_margin_min(post_eval_margin_min: float) -> None:
    if not (0.0 <= post_eval_margin_min <= 1.0):
        raise ValueError("post_eval_margin_min must be in [0.0, 1.0]")


def _validate_post_eval_sample_size(post_eval_sample_size: int) -> None:
    if post_eval_sample_size < 1:
        raise ValueError("post_eval_sample_size must be at least 1")


def _validate_composition_max_strategies(composition_max_strategies: int) -> None:
    if composition_max_strategies < 2:
        raise ValueError("composition_max_strategies must be at least 2")


def _validate_composition_probability(composition_probability: float) -> None:
    if not (0.0 <= composition_probability <= 1.0):
        raise ValueError("composition_probability must be in [0.0, 1.0]")


def _validate_iteration_timeout_s(iteration_timeout_s: int) -> None:
    if iteration_timeout_s < 30:
        raise ValueError("iteration_timeout_s must be at least 30 seconds")


def _validate_iteration_llm_call_limit(iteration_llm_call_limit: int) -> None:
    if iteration_llm_call_limit < 10:
        raise ValueError("iteration_llm_call_limit must be at least 10")


def _validate_composite_timeout_s(composite_timeout_s: int) -> None:
    if composite_timeout_s < 20:
        raise ValueError("composite_timeout_s must be at least 20 seconds")


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
        cognitivo_prior_count=int(os.environ.get("MCTS_COGNITIVO_PRIOR_COUNT", "4")),
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
        max_depth=int(os.environ.get("MCTS_MAX_DEPTH", "20")),
        sufficiency_threshold=float(os.environ.get("MCTS_SUFFICIENCY_THRESHOLD", "0.95")),
        ab_margin_min=float(os.environ.get("MCTS_AB_MARGIN_MIN", "0.05")),
        knowledge_bias_lambda=float(os.environ.get("MCTS_KNOWLEDGE_BIAS_LAMBDA", "0.3")),
        llm_timeout=int(os.environ.get("MCTS_LLM_TIMEOUT", "60")),
        post_eval_margin_min=float(os.environ.get("MCTS_POST_EVAL_MARGIN_MIN", "0.05")),
        post_eval_sample_size=int(os.environ.get("MCTS_POST_EVAL_SAMPLE_SIZE", "5")),
        composition_max_strategies=int(os.environ.get("MCTS_COMPOSITION_MAX_STRATEGIES", "3")),
        composition_probability=float(os.environ.get("MCTS_COMPOSITION_PROBABILITY", "0.3")),
        iteration_timeout_s=int(os.environ.get("MCTS_ITERATION_TIMEOUT_S", "300")),
        iteration_llm_call_limit=int(os.environ.get("MCTS_ITERATION_LLM_CALL_LIMIT", "50")),
        composite_timeout_s=int(os.environ.get("MCTS_COMPOSITE_TIMEOUT_S", "45")),
    )
