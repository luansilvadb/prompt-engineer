import pytest
from src.optimizer import Optimizer, MCTSNode
from src.density_evaluator import calculate_density_multiplier
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
    opt.lexical_density_min = 0.0
    
    root = MCTSNode(instruction="foo")
    root.last_reward = 0.0
    child = MCTSNode(instruction=sample_verbose_text, parent=root)
    
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    
    # Assert pipeline processes without error
    assert not should_break
    assert reward > 0.0


def test_optimizer_cognitivo_regression(mock_heavy_evaluators):
    opt = Optimizer(skill_original="foo")
    assert hasattr(opt, 'agent_cognitivo')
    assert 'mutador_cognitivo' in opt.mutation_bandit._counts


def test_density_boost_applied(mock_heavy_evaluators):
    opt = Optimizer(skill_original="This is a very long parent instruction that should compress well and demonstrate density boost behavior in the MCTS pipeline.")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.semantic_sim_threshold = 1.0
    opt.lexical_density_min = 0.0
    root = MCTSNode(instruction=opt.skill_original)
    root.last_reward = 0.0
    child = MCTSNode(instruction="Short compressed instruction.", parent=root)
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    assert reward > 1.0


def test_density_penalty_applied(mock_heavy_evaluators, sample_verbose_text):
    opt = Optimizer(skill_original="Short parent.")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.semantic_sim_threshold = 1.0
    opt.lexical_density_min = 0.0
    root = MCTSNode(instruction="Short parent.")
    root.last_reward = 0.0
    child = MCTSNode(instruction=sample_verbose_text, parent=root)
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    assert reward < 1.0


def test_density_neutral_at_same_length(mock_heavy_evaluators):
    opt = Optimizer(skill_original="Same length instruction here")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.semantic_sim_threshold = 1.0
    opt.lexical_density_min = 0.0
    root = MCTSNode(instruction="Same length instruction here")
    root.last_reward = 0.0
    child = MCTSNode(instruction="Same length instruction here", parent=root)
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    assert reward == 1.0


def test_density_structured_bonus_integration(mock_heavy_evaluators):
    opt = Optimizer(skill_original="Test")
    assert hasattr(opt, 'density_threshold')
    assert opt.density_threshold == 1.0
    assert hasattr(opt, 'density_multiplier_min')
    assert opt.density_multiplier_min == 0.5
    assert hasattr(opt, 'density_multiplier_max')
    assert opt.density_multiplier_max == 1.5
    assert hasattr(opt, 'density_structured_bonus')
    assert opt.density_structured_bonus == 0.2
    child = "## Raciocínio\npremissas\n## Regras\nregras\n## Conclusão\nconc"
    parent = "x" * len(child)
    result = calculate_density_multiplier(
        child_instruction=child,
        parent_instruction=parent,
        mutation_strategy="mutador_cognitivo",
    )
    assert result > 1.0


def test_density_regression_existing_tests(mock_heavy_evaluators):
    opt = Optimizer(skill_original="foo")
    assert hasattr(opt, 'density_threshold')
    assert opt.density_threshold == 1.0
