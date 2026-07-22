from dataclasses import replace

from src.domain.mcts import MCTSNode
from src.evaluators import calculate_density_multiplier
from unittest.mock import MagicMock


def test_optimizer_layer1_hard_pruning(mock_optimizer_factory, mock_heavy_evaluators):
    opt = mock_optimizer_factory(skill_original="foo")
    opt.config = replace(opt.config, semantic_sim_threshold=1.0)

    text = "palavra " * 100

    root = MCTSNode(instruction="foo")
    root.last_reward = 0.0
    child = MCTSNode(instruction=text, parent=root)

    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)

    should_break, reward = opt._run_mcts_iteration(root)

    assert reward == 0.0
    assert child.last_reward == 0.0
    assert "Low Lexical Density" in child.feedback

    mock_heavy_evaluators["AvaliadorModoB"].assert_not_called()
    mock_heavy_evaluators["SentenceTransformer"].assert_not_called()


def test_optimizer_layer2_penalty_multiplier(mock_optimizer_factory, sample_verbose_text):
    opt = mock_optimizer_factory(skill_original="foo")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.config = replace(opt.config, semantic_sim_threshold=1.0, lexical_density_min=0.0)

    root = MCTSNode(instruction="foo")
    root.last_reward = 0.0
    child = MCTSNode(instruction=sample_verbose_text, parent=root)

    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)

    should_break, reward = opt._run_mcts_iteration(root)

    assert not should_break
    assert reward > 0.0


def test_optimizer_cognitivo_regression(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="foo")
    assert hasattr(opt, 'agent_cognitivo')
    assert 'mutador_cognitivo' in opt.mutation_bandit._counts


def test_density_boost_applied(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="This is a very long parent instruction that should compress well and demonstrate density boost behavior in the MCTS pipeline.")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.config = replace(opt.config, semantic_sim_threshold=1.0, lexical_density_min=0.35)
    root = MCTSNode(instruction=opt.skill_original)
    root.last_reward = 0.0
    child = MCTSNode(instruction="Short compressed instruction.", parent=root)
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    should_break, reward = opt._run_mcts_iteration(root)
    assert reward > 1.0


def test_density_penalty_applied(mock_optimizer_factory, sample_verbose_text):
    opt = mock_optimizer_factory(skill_original="Short parent.")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.config = replace(opt.config, semantic_sim_threshold=1.0, lexical_density_min=0.35)
    root = MCTSNode(instruction="Short parent.")
    root.last_reward = 0.0
    child = MCTSNode(instruction=sample_verbose_text, parent=root)
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    should_break, reward = opt._run_mcts_iteration(root)
    assert reward < 1.0


def test_density_neutral_at_same_length(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="Same length instruction here")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt.config = replace(opt.config, semantic_sim_threshold=1.0, lexical_density_min=0.0, density_threshold=1.0)
    root = MCTSNode(instruction="Same length instruction here")
    root.last_reward = 0.0
    child = MCTSNode(instruction="Same length instruction here", parent=root)
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    should_break, reward = opt._run_mcts_iteration(root)
    assert reward == 1.0


def test_density_structured_bonus_integration(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="Test")
    assert opt.config.density_threshold == 0.9
    assert opt.config.density_multiplier_min == 0.8
    assert opt.config.density_multiplier_max == 1.2
    assert opt.config.density_structured_bonus == 0.05
    child = "## Raciocínio\npremissas\n## Regras\nregras\n## Conclusão\nconc"
    parent = "x" * len(child)
    result = calculate_density_multiplier(
        child_instruction=child,
        parent_instruction=parent,
        mutation_strategy="mutador_cognitivo",
    )
    assert result > 1.0


def test_density_regression_existing_tests(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="foo")
    assert opt.config.density_threshold == 0.9