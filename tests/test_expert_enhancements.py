from unittest.mock import MagicMock, patch

from src.domain.config import load_mcts_config
from src.optimizer import Optimizer
from src.domain.mcts import MCTSNode
from src.teleprompter import _run_teleprompt

def test_simulation_cache_deduplication():
    cfg = load_mcts_config()
    emitter = MagicMock()
    emitter.is_cancelled.return_value = False
    strategy_discoverer = MagicMock()
    agent = MagicMock()
    agent_cognitivo = MagicMock()
    avaliador_modo_b = MagicMock()
    experience_store = MagicMock()
    experience_store.get_strategy_stats.return_value = {}
    bandit = MagicMock()
    strategy_registry = MagicMock()

    optimizer = Optimizer(
        skill_original="Instrução teste",
        config=cfg,
        emitter=emitter,
        strategy_discoverer=strategy_discoverer,
        agent=agent,
        agent_cognitivo=agent_cognitivo,
        avaliador_modo_b=avaliador_modo_b,
        experience_store=experience_store,
        bandit=bandit,
        strategy_registry=strategy_registry,
    )

    with patch("src.optimizer.funcao_de_recompensa", return_value=(0.85, "Bom")):
        r1, f1 = optimizer.simulation("Instrução de teste repetida para cache")
        r2, f2 = optimizer.simulation("Instrução de teste repetida para cache")

        assert r1 == 0.85
        assert r2 == 0.85
        # Chama a função de recompensa apenas UMA vez por causa do cache
        assert optimizer._simulation_cache is not None
        assert len(optimizer._simulation_cache) == 1

def test_early_termination_on_target_reward():
    cfg = load_mcts_config()
    emitter = MagicMock()
    emitter.is_cancelled.return_value = False
    strategy_discoverer = MagicMock()
    agent = MagicMock()
    agent_cognitivo = MagicMock()
    avaliador_modo_b = MagicMock()
    experience_store = MagicMock()
    experience_store.get_strategy_stats.return_value = {}
    bandit = MagicMock()
    strategy_registry = MagicMock()

    optimizer = Optimizer(
        skill_original="Instrução teste",
        config=cfg,
        emitter=emitter,
        strategy_discoverer=strategy_discoverer,
        agent=agent,
        agent_cognitivo=agent_cognitivo,
        avaliador_modo_b=avaliador_modo_b,
        experience_store=experience_store,
        bandit=bandit,
        strategy_registry=strategy_registry,
    )

    optimizer.best_reward_so_far = 0.98  # Excede limiar 0.95
    optimizer._run_mcts_iteration = MagicMock(return_value=(False, 0.5))
    root = MCTSNode("Instrução teste")

    should_break, zeros, errors = optimizer._run_single_iteration(root, 0, 0, 0)
    assert should_break is True

def test_teleprompt_optimizer_type_fallback(tmp_path):
    trainset = [MagicMock()]
    cand_path = tmp_path / "candidate.json"

    from dspy.teleprompt import BootstrapFewShot
    with patch.object(BootstrapFewShot, "compile") as mock_compile:
        mock_compiled = MagicMock()
        mock_compile.return_value = mock_compiled

        _run_teleprompt(trainset, cand_path, optimizer_type="bootstrap")
        assert mock_compile.called

def test_teleprompt_quality_metric(tmp_path):
    trainset = [MagicMock()]
    cand_path = tmp_path / "candidate.json"

    captured_metric = None
    from dspy.teleprompt import BootstrapFewShot
    def mock_init(self, metric=None, **kwargs):
        nonlocal captured_metric
        captured_metric = metric

    with patch.object(BootstrapFewShot, "__init__", mock_init):
        with patch.object(BootstrapFewShot, "compile") as mock_compile:
            mock_compiled = MagicMock()
            mock_compile.return_value = mock_compiled

            _run_teleprompt(trainset, cand_path, optimizer_type="bootstrap")
            assert captured_metric is not None

            # Testar casos do quality_metric
            assert captured_metric(None, None) is False

            pred_invalid_rule = MagicMock()
            pred_invalid_rule.manteve_regras_criticas = False
            assert captured_metric(None, pred_invalid_rule) is False

            pred_no_feedback = MagicMock()
            pred_no_feedback.manteve_regras_criticas = True
            pred_no_feedback.feedback_detalhado = ""
            assert captured_metric(None, pred_no_feedback) is False

            pred_valid = MagicMock()
            pred_valid.manteve_regras_criticas = True
            pred_valid.feedback_detalhado = "Feedback construtivo e detalhado."
            assert captured_metric(None, pred_valid) is True

