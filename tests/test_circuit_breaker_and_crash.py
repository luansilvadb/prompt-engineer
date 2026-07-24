"""
Testes de Circuit Breaker e Crash Prevention no Optimizer.

Cobre:
  - Crash NoneType: _discover_strategy não crasha quando nome_estrategia é None.
  - Circuit Breaker Preventivo: _discover_strategy não submete LLM quando deadline passou.
  - Preservação de strat no log: _last_iter_strategy reflete estratégia real mesmo com abort.
  - Abort de Batch: _run_single_iteration pula iterações quando _remaining_time <= 0.
"""

import threading
from unittest.mock import MagicMock

from src.domain.agent_interfaces import DiscoveredStrategy
from src.domain.config import MCTSConfig
from src.domain.mcts import MCTSNode
from src.optimizer import Optimizer


def _make_config(**overrides) -> MCTSConfig:
    """Cria MCTSConfig com valores padrão, aceitando overrides via kwargs."""
    defaults = dict(
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
        cognitivo_prior_count=4,
        cognitivo_prior_mean_delta=0.05,
        density_multiplier_min=0.5,
        density_multiplier_max=1.5,
        density_threshold=1.0,
        density_structured_bonus=0.2,
        reward_floor=0.30,
    )
    defaults.update(overrides)
    return MCTSConfig(**defaults)


# ── TESTE 1: Crash NoneType ──────────────────────────────────────────────────

def test_discover_strategy_handles_none_nome_estrategia():
    """Quando o LLM retorna nome_estrategia=None, _discover_strategy deve usar fallback sem crash."""
    config = _make_config()
    optimizer = Optimizer.__new__(Optimizer)
    optimizer.config = config
    optimizer._iteration_circuit_broken = False
    optimizer._abort_flag = False

    # Configurar emitter
    emitter = MagicMock()
    optimizer._emitter = emitter

    # Configurar lock
    optimizer.lock = threading.Lock()

    # Configurar strategy_registry com fallback keys
    registry = MagicMock()
    registry.get_all_keys.return_value = ['__DISCOVER__', 'compressao', 'enriquecimento']
    registry.get_name.side_effect = lambda k: k
    optimizer._strategy_registry = registry
    optimizer._discovered_strategies = set()

    # Mockar _check_iteration_abort para retornar False
    optimizer._check_iteration_abort = MagicMock(return_value=False)

    # Mockar _remaining_time para retornar tempo suficiente
    optimizer._remaining_time = MagicMock(return_value=30.0)

    # Mockar _count_llm_call
    optimizer._count_llm_call = MagicMock()

    # Mockar strategy_discoverer
    optimizer.strategy_discoverer = MagicMock()

    # Criar future que retorna DiscoveredStrategy com nome None
    future = MagicMock()
    future.result.return_value = DiscoveredStrategy(nome_estrategia=None, prompt_estrategia="algum prompt")

    # Mockar executor.submit
    mock_executor = MagicMock()
    mock_executor.submit.return_value = future
    optimizer._llm_executor = mock_executor

    # Criar leaf node
    leaf = MagicMock()
    leaf.instruction = "skill original"
    leaf.feedback = "feedback"

    result = optimizer._discover_strategy(leaf)

    # Deve retornar fallback (primeira chave que não é __DISCOVER__), não crashar
    assert result in ['compressao', 'enriquecimento']
    # Deve ter logado o warning
    emitter.emit_log.assert_any_call('[Discovery] nome_estrategia vazio/None, usando fallback')


# ── TESTE 2: Circuit Breaker Preventivo ──────────────────────────────────────

def test_circuit_breaker_prevents_llm_submit_when_deadline_passed():
    """Quando _remaining_time <= 0, _discover_strategy não deve chamar executor.submit()."""
    config = _make_config(llm_timeout=120)
    optimizer = Optimizer.__new__(Optimizer)
    optimizer.config = config
    optimizer._iteration_circuit_broken = False
    optimizer._abort_flag = False

    emitter = MagicMock()
    optimizer._emitter = emitter

    optimizer.lock = threading.Lock()

    registry = MagicMock()
    registry.get_all_keys.return_value = ['__DISCOVER__', 'compressao']
    registry.get_name.side_effect = lambda k: k
    optimizer._strategy_registry = registry
    optimizer._discovered_strategies = set()

    optimizer._check_iteration_abort = MagicMock(return_value=False)
    # Simular deadline já passado
    optimizer._remaining_time = MagicMock(return_value=0.0)
    optimizer._count_llm_call = MagicMock()

    mock_executor = MagicMock()
    optimizer._llm_executor = mock_executor

    leaf = MagicMock()
    leaf.instruction = "skill original"
    leaf.feedback = "feedback"

    result = optimizer._discover_strategy(leaf)

    # Não deve ter chamado submit()
    mock_executor.submit.assert_not_called()
    # Deve retornar fallback
    assert result == 'compressao'
    # Deve ter setado circuit_broken
    assert optimizer._iteration_circuit_broken is True
    # Deve ter logado o aviso de deadline
    emitter.emit_log.assert_any_call('    [Circuit Breaker] Deadline já passado, abortando submissão de discovery')


# ── TESTE 3: Preservação de strat no log ─────────────────────────────────────

def test_last_iter_strategy_preserved_when_abort_after_expansion():
    """_last_iter_strategy deve refletir a estratégia real mesmo quando circuit breaker dispara após _expand_child."""
    config = _make_config()
    optimizer = Optimizer.__new__(Optimizer)
    optimizer.config = config
    optimizer._iteration_circuit_broken = False
    optimizer._abort_flag = False

    emitter = MagicMock()
    optimizer._emitter = emitter

    # Criar root e child
    root = MCTSNode(instruction="root")
    child = MCTSNode(instruction="child", parent=root, mutation_strategy="compressao", depth=1)
    root.children.append(child)

    # Mockar selection
    optimizer.selection = MagicMock(return_value=root)

    # Mockar _expand_child para retornar o child
    optimizer._expand_child = MagicMock(return_value=child)

    # Mockar _check_iteration_abort: False na primeira chamada, True na segunda (checkpoint 2)
    abort_responses = [False, True]
    def abort_side_effect():
        return abort_responses.pop(0)
    optimizer._check_iteration_abort = MagicMock(side_effect=abort_side_effect)

    result = optimizer._run_mcts_iteration(root)

    # Deve ter retornado (True, 0.0) devido ao abort
    assert result == (True, 0.0)
    # _last_iter_strategy deve ser 'compressao', NÃO 'N/A'
    assert optimizer._last_iter_strategy == 'compressao'
    assert optimizer._last_iter_depth == 1


# ── TESTE 4: Abort de Batch ──────────────────────────────────────────────────

def test_batch_abort_skips_remaining_iterations():
    """Quando _remaining_time <= 0, _run_single_iteration deve pular iterações restantes."""
    config = _make_config(max_iterations=10)
    optimizer = Optimizer.__new__(Optimizer)
    optimizer.config = config
    optimizer._abort_flag = False

    emitter = MagicMock()
    optimizer._emitter = emitter

    # Mockar _remaining_time para retornar 0 a partir da iteração 3
    remaining_responses = [30.0, 30.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    def remaining_side_effect(*args):
        return remaining_responses.pop(0)
    optimizer._remaining_time = MagicMock(side_effect=remaining_side_effect)

    # Mockar _run_mcts_iteration para retornar sucesso
    optimizer._run_mcts_iteration = MagicMock(return_value=(False, 0.5))
    optimizer._last_iter_strategy = 'compressao'
    optimizer._last_iter_depth = 2
    optimizer._last_iter_mult = None
    optimizer._last_iter_shaped = None
    optimizer._emit_cost_event = MagicMock()

    root = MCTSNode(instruction="root")

    # Rodar iterações 0, 1, 2 (a terceira deve abortar)
    should_break = False
    zeros = 0
    errors = 0
    for i in range(config.max_iterations):
        result = optimizer._run_single_iteration(root, i, zeros, errors)
        if result[0]:  # should_break
            should_break = True
            break
        zeros = result[1]
        errors = result[2]

    # Deve ter parado na iteração 2 (índice 2)
    assert should_break is True
    # _run_mcts_iteration deve ter sido chamado apenas 2 vezes (iterações 0 e 1)
    assert optimizer._run_mcts_iteration.call_count == 2
    # Deve ter logado Batch Abort
    emitter.emit_log.assert_any_call('[Batch Abort] Deadline esgotado, pulando iterações 3-10')
