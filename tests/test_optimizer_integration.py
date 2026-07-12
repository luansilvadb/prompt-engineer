import pytest
from unittest.mock import MagicMock
from src.optimizer import Optimizer, MCTSNode


def test_cognitivo_routing_uses_agent_cognitivo(mock_heavy_evaluators):
    opt = Optimizer(skill_original="Test")
    opt.mutation_bandit.select = MagicMock(return_value='mutador_cognitivo')
    mock_pred = MagicMock()
    mock_pred.nova_instrucao = "## Raciocínio\nDeep analysis.\n## Regras\nStrict derivation.\n## Conclusão\nRewrite completely." * 3
    mock_pred.critica = "Precisa de mais estrutura lógica."
    mock_pred.raciocinio_estruturado = "Premissas: The feedback shows gaps.\nDeducoes: Structure must change.\nConclusao: Rewrite with logic."
    opt.agent_cognitivo = MagicMock(return_value=mock_pred)
    opt.agent = MagicMock()
    opt.simulation = MagicMock(return_value=(0.5, "feedback"))
    opt.semantic_sim_threshold = 1.0
    root = MCTSNode(instruction="Test")
    root.last_reward = 0.0
    child = opt._expand_node(root)
    assert opt.agent_cognitivo.called
    assert not opt.agent.called
    assert child.mutation_strategy == 'mutador_cognitivo'


def test_non_cognitivo_routing_uses_agent(mock_heavy_evaluators):
    opt = Optimizer(skill_original="Test")
    opt.mutation_bandit.select = MagicMock(return_value='simplificar')
    mock_pred = MagicMock()
    mock_pred.nova_instrucao = "Simplified instruction with enough content for the test to be valid and meaningful."
    mock_pred.critica = "Could be simpler."
    opt.agent = MagicMock(return_value=mock_pred)
    opt.agent_cognitivo = MagicMock()
    opt.simulation = MagicMock(return_value=(0.5, "feedback"))
    opt.semantic_sim_threshold = 1.0
    root = MCTSNode(instruction="Test")
    root.last_reward = 0.0
    opt._expand_node(root)
    assert opt.agent.called
    assert not opt.agent_cognitivo.called


def test_cognitivo_routing_soft_validation(mock_heavy_evaluators):
    opt = Optimizer(skill_original="Test")
    opt.mutation_bandit.select = MagicMock(return_value='mutador_cognitivo')
    mock_pred = MagicMock()
    mock_pred.raciocinio_estruturado = "invalid missing labels"
    mock_pred.nova_instrucao = "short"
    mock_pred.critica = "Needs work."
    opt.agent_cognitivo = MagicMock(return_value=mock_pred)
    opt.on_error = MagicMock()
    opt.semantic_sim_threshold = 1.0
    root = MCTSNode(instruction="Test")
    root.last_reward = 0.0
    try:
        opt._expand_node(root)
        assert opt.on_error.called
    except Exception:
        pytest.fail("Soft validation should not crash _expand_node")


def test_cognitivo_integration_child_strategy(mock_heavy_evaluators):
    opt = Optimizer(skill_original="Test")
    opt.mutation_bandit.select = MagicMock(return_value='mutador_cognitivo')
    mock_pred = MagicMock()
    mock_pred.nova_instrucao = "## Raciocínio\nDeep analysis.\n## Regras\nStrict derivation.\n## Conclusão\nRewrite completely." * 3
    mock_pred.critica = "Precisa de mais estrutura."
    mock_pred.raciocinio_estruturado = "Premissas: The feedback shows gaps.\nDeducoes: Structure must change.\nConclusao: Rewrite with logic."
    opt.agent_cognitivo = MagicMock(return_value=mock_pred)
    opt.simulation = MagicMock(return_value=(0.5, "feedback"))
    opt.semantic_sim_threshold = 1.0
    root = MCTSNode(instruction="Test")
    root.last_reward = 0.0
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    assert not is_error
    assert reward > 0.0
