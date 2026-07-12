from unittest.mock import MagicMock, patch
from src.optimizer import Optimizer
from src.domain.mcts import MCTSNode

def test_evaluate_and_prune(mock_heavy_evaluators):
    opt = Optimizer(skill_original="skill")
    opt.on_progress = MagicMock()
    opt.backpropagation = MagicMock()
    child = MCTSNode(instruction="child")

    with patch('src.optimizer.evaluate_heuristics', return_value={"prune": True, "reason": "too long"}):
        is_pruned, res = opt._evaluate_and_prune(child)
        assert is_pruned is True
        assert child.feedback == "too long"
        assert child.last_reward == 0.0
        opt.backpropagation.assert_called_once_with(child, 0.0)

def test_apply_heuristic_multiplier(mock_heavy_evaluators):
    opt = Optimizer(skill_original="skill")
    opt.on_progress = MagicMock()

    res = opt._apply_heuristic_multiplier(10.0, {"penalty_multiplier": 0.5})
    assert res == 5.0
    opt.on_progress.assert_called()

def test_apply_semantic_penalty(mock_heavy_evaluators):
    opt = Optimizer(skill_original="skill")
    opt.on_progress = MagicMock()
    child = MCTSNode(instruction="child")

    with patch('src.optimizer.calculate_semantic_penalty', return_value=0.8):
        res = opt._apply_semantic_penalty(child, 10.0)
        assert res == 8.0
        opt.on_progress.assert_called()

def test_apply_density_multiplier(mock_heavy_evaluators):
    opt = Optimizer(skill_original="skill")
    opt.on_progress = MagicMock()
    child = MCTSNode(instruction="child")

    with patch('src.optimizer.calculate_density_multiplier', return_value=1.2):
        res = opt._apply_density_multiplier(child, 10.0)
        assert res == 12.0
        opt.on_progress.assert_called()

def test_optimizer_mcts_iteration_cancelled(mock_heavy_evaluators):
    opt = Optimizer(skill_original="skill")
    opt.is_cancelled = MagicMock(return_value=True)
    root = MCTSNode(instruction="skill")

    should_break, is_error, reward = opt._run_mcts_iteration(root)
    assert should_break is True
    assert reward == 0.0

def test_optimizer_mcts_iteration_happy_path(mock_heavy_evaluators):
    opt = Optimizer(skill_original="skill")
    opt.semantic_sim_threshold = 1.0
    opt.lexical_density_min = 0.0

    root = MCTSNode(instruction="skill")
    child = MCTSNode(instruction="child", parent=root)

    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    opt.simulation = MagicMock(return_value=(10.0, "feedback"))

    should_break, is_error, reward = opt._run_mcts_iteration(root)

    assert should_break is False
    assert is_error is False
    assert reward == 10.0
    assert child.feedback == "feedback"
    assert child.last_reward == 10.0

def test_optimizer_mcts_iteration_max_children(mock_heavy_evaluators):
    opt = Optimizer(skill_original="skill")
    opt.semantic_sim_threshold = 1.0
    opt.lexical_density_min = 0.0

    root = MCTSNode(instruction="skill")
    child = MCTSNode(instruction="child", parent=root)
    root.children.append(child)

    # Mock to say it has max children already
    root.max_children_allowed = MagicMock(return_value=1)

    opt.selection = MagicMock(return_value=root)
    opt.simulation = MagicMock(return_value=(5.0, "feedback2"))

    should_break, is_error, reward = opt._run_mcts_iteration(root)

    assert should_break is False
    assert reward == 5.0
