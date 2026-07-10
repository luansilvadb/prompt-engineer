import pytest
from src.optimizer import Optimizer, MCTSNode
from unittest.mock import MagicMock

def test_optimizer_layer1_hard_pruning(mock_heavy_evaluators):
    # Setup optimizer mock
    opt = Optimizer(skill_original="foo")
    # Disable semantic penalty so we only test heuristics
    opt.semantic_sim_threshold = 1.0 
    
    # Hollow verbosity (lexical density below 0.35)
    text = "palavra " * 100
    
    # Parent node needed for delta reward shaping
    root = MCTSNode(instruction="foo")
    root.last_reward = 0.0
    child = MCTSNode(instruction=text, parent=root)
    
    # Mock expand
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    
    # Run iteration
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    
    # Assert it was pruned
    assert reward == 0.0
    assert child.last_reward == 0.0
    assert "Low Lexical Density" in child.feedback
    
    # Ensure heavy evaluator was NOT called
    mock_heavy_evaluators["AvaliadorModoB"].assert_not_called()
    mock_heavy_evaluators["SentenceTransformer"].assert_not_called()

def test_optimizer_layer2_penalty_multiplier(mock_heavy_evaluators, sample_verbose_text):
    opt = Optimizer(skill_original="foo")
    # Mock simulation so we get a base reward
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.semantic_sim_threshold = 1.0
    
    root = MCTSNode(instruction="foo")
    root.last_reward = 0.0
    child = MCTSNode(instruction=sample_verbose_text, parent=root)
    
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    
    # Assert not pruned
    assert reward > 0.0
    # The reward should be penalized by verbosity_penalty_factor (0.85 default)
    assert reward == 1.0 * opt.verbosity_penalty_factor
    assert child.last_reward == opt.verbosity_penalty_factor
