import pytest
from unittest.mock import MagicMock
from src.domain.mcts import MCTSNode


def test_cognitivo_routing_uses_agent_cognitivo(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="Test")
    opt.mutation_bandit.select = MagicMock(return_value='mutador_cognitivo')
    mock_pred = MagicMock()
    mock_pred.nova_instrucao = "## Raciocínio\nDeep analysis.\n## Regras\nStrict derivation.\n## Conclusão\nRewrite completely." * 3
    mock_pred.critica = "Precisa de mais estrutura lógica."
    mock_pred.raciocinio_estruturado = "Premissas: The feedback shows gaps.\nDeducoes: Structure must change.\nConclusao: Rewrite with logic."
    opt._agent_cognitivo = MagicMock(return_value=mock_pred)
    opt._agent = MagicMock()
    opt.simulation = MagicMock(return_value=(0.5, "feedback"))
    opt.semantic_sim_threshold = 1.0
    root = MCTSNode(instruction="Test")
    root.last_reward = 0.0
    child = opt._expand_node(root)
    assert opt._agent_cognitivo.called
    assert not opt._agent.called
    assert child.mutation_strategy == 'mutador_cognitivo'


def test_non_cognitivo_routing_uses_agent(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="Test")
    opt.mutation_bandit.select = MagicMock(return_value='simplificar')
    mock_pred = MagicMock()
    mock_pred.nova_instrucao = "Simplified instruction with enough content for the test to be valid and meaningful."
    mock_pred.critica = "Could be simpler."
    opt._agent = MagicMock(return_value=mock_pred)
    opt._agent_cognitivo = MagicMock()
    opt.simulation = MagicMock(return_value=(0.5, "feedback"))
    opt.semantic_sim_threshold = 1.0
    root = MCTSNode(instruction="Test")
    root.last_reward = 0.0
    opt._expand_node(root)
    assert opt._agent.called
    assert not opt._agent_cognitivo.called


def test_cognitivo_routing_soft_validation(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="Test")
    opt.mutation_bandit.select = MagicMock(return_value='mutador_cognitivo')
    mock_pred = MagicMock()
    mock_pred.raciocinio_estruturado = "invalid missing labels"
    mock_pred.nova_instrucao = "short"
    mock_pred.critica = "Needs work."
    opt._agent_cognitivo = MagicMock(return_value=mock_pred)
    opt._emitter.emit_log = MagicMock()
    opt.semantic_sim_threshold = 1.0
    root = MCTSNode(instruction="Test")
    root.last_reward = 0.0
    try:
        opt._expand_node(root)
        assert opt._emitter.emit_log.called
    except Exception:
        pytest.fail("Soft validation should not crash _expand_node")


def test_cognitivo_integration_child_strategy(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="Test")
    opt.mutation_bandit.select = MagicMock(return_value='mutador_cognitivo')
    mock_pred = MagicMock()
    mock_pred.nova_instrucao = "## Raciocínio\nDeep analysis.\n## Regras\nStrict derivation.\n## Conclusão\nRewrite completely." * 3
    mock_pred.critica = "Precisa de mais estrutura."
    mock_pred.raciocinio_estruturado = "Premissas: The feedback shows gaps.\nDeducoes: Structure must change.\nConclusao: Rewrite with logic."
    opt._agent_cognitivo = MagicMock(return_value=mock_pred)
    opt.simulation = MagicMock(return_value=(0.5, "feedback"))
    opt.semantic_sim_threshold = 1.0
    root = MCTSNode(instruction="Test")
    root.last_reward = 0.0
    should_break, is_error, reward = opt._run_mcts_iteration(root)
    assert not is_error
    assert reward > 0.0
