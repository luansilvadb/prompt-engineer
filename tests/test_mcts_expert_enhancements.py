import pytest
from src.domain.config import MCTSConfig
from src.domain.mcts import MCTSNode, TranspositionTable


def test_mcts_config_selection_policy():
    cfg = MCTSConfig(
        gamma=0.95,
        c_param=1.41,
        progressive_alpha=0.5,
        progressive_c=2.0,
        value_threshold=0.2,
        max_iterations=10,
        value_lr=0.1,
        bandit_c_param=1.41,
        bandit_temperature=2.0,
        bandit_temperature_decay=0.95,
        semantic_sim_threshold=0.85,
        lexical_density_min=0.35,
        verbosity_penalty_factor=0.85,
        buzzword_threshold=3,
        cognitivo_prior_count=1,
        cognitivo_prior_mean_delta=0.05,
        density_multiplier_min=0.5,
        density_multiplier_max=1.5,
        density_threshold=1.0,
        density_structured_bonus=0.2,
        reward_floor=0.30,
        selection_policy="ucb1_tuned",
        c_bias=0.8,
    )
    assert cfg.selection_policy == "ucb1_tuned"
    assert cfg.c_bias == 0.8

    with pytest.raises(ValueError):
        MCTSConfig(
            gamma=0.95,
            c_param=1.41,
            progressive_alpha=0.5,
            progressive_c=2.0,
            value_threshold=0.2,
            max_iterations=10,
            value_lr=0.1,
            bandit_c_param=1.41,
            bandit_temperature=2.0,
            bandit_temperature_decay=0.95,
            semantic_sim_threshold=0.85,
            lexical_density_min=0.35,
            verbosity_penalty_factor=0.85,
            buzzword_threshold=3,
            cognitivo_prior_count=1,
            cognitivo_prior_mean_delta=0.05,
            density_multiplier_min=0.5,
            density_multiplier_max=1.5,
            density_threshold=1.0,
            density_structured_bonus=0.2,
            reward_floor=0.30,
            selection_policy="invalida",
        )


def test_best_child_puct_with_progressive_bias():
    parent = MCTSNode("Instrucao Pai")
    child_high_prior = MCTSNode("Filho Alto Prior", parent=parent, prior=0.9, mutation_strategy="strat1")
    child_low_prior = MCTSNode("Filho Baixo Prior", parent=parent, prior=0.1, mutation_strategy="strat2")
    parent.children = [child_high_prior, child_low_prior]
    parent.visits = 10

    best = parent.best_child_puct(c_param=1.41, c_bias=1.0)
    assert best == child_high_prior


def test_best_child_ucb_tuned_enhanced():
    parent = MCTSNode("Instrucao Pai")
    child_a = MCTSNode("Filho A", parent=parent, mutation_strategy="strat_a")
    child_a.visits = 5
    child_a.q_value = 4.0
    child_a.sq_q_value = 3.5

    child_b = MCTSNode("Filho B", parent=parent, mutation_strategy="strat_b")
    child_b.visits = 5
    child_b.q_value = 4.0
    child_b.sq_q_value = 3.2

    parent.children = [child_a, child_b]
    parent.visits = 10

    bandit_stats = {"strat_b": 0.9}
    best = parent.best_child_ucb_tuned(c_param=1.0, bandit_stats=bandit_stats, rave_k=5.0)
    assert best == child_b


def test_transposition_table_dag_hits():
    tt = TranspositionTable()
    node1 = MCTSNode("Instrucao Reutilizada")
    node1.visits = 2
    node1.q_value = 1.6

    tt.put("Instrucao Reutilizada", node1)
    retrieved = tt.get("Instrucao Reutilizada")
    assert retrieved == node1
    assert tt.hits == 1
