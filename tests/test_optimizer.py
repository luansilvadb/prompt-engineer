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
    """Density boost deve ser refletido em child.multiplied_reward, não no raw_reward retornado.
    
    A partir de fix-score-scale-consistency, _run_mcts_iteration retorna raw_reward
    (escala canônica de qualidade). O multiplied_reward (com density boost) é
    armazenado no nó e usado apenas para navegação (shaped_reward → backprop).
    """
    opt = mock_optimizer_factory(skill_original="This is a very long parent instruction that should compress well and demonstrate density boost behavior in the MCTS pipeline.")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt._evaluate_and_prune = MagicMock(return_value=(False, {}))
    opt.config = replace(opt.config, semantic_sim_threshold=1.0, lexical_density_min=0.35)
    root = MCTSNode(instruction=opt.skill_original)
    root.last_reward = 0.0
    child = MCTSNode(instruction="Short compressed instruction.", parent=root)
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    should_break, reward = opt._run_mcts_iteration(root)
    # raw_reward é a saída de simulation(), sempre em [0, 1]
    assert reward == 1.0
    # multiplied_reward no nó reflete o density boost (> 1.0 possível)
    assert child.multiplied_reward > 1.0


def test_density_penalty_applied(mock_optimizer_factory, sample_verbose_text):
    """Density penalty deve ser refletido em child.multiplied_reward, não no raw_reward.

    A partir de fix-score-scale-consistency, _run_mcts_iteration retorna raw_reward
    (escala canônica de qualidade), que é a saída de simulation(), sempre em [0, 1].
    """
    opt = mock_optimizer_factory(skill_original="Short parent.")
    opt.simulation = MagicMock(return_value=(1.0, "Good job"))
    opt._evaluate_and_prune = MagicMock(return_value=(False, {}))
    opt.config = replace(opt.config, semantic_sim_threshold=1.0, lexical_density_min=0.35)
    root = MCTSNode(instruction="Short parent.")
    root.last_reward = 0.0
    child = MCTSNode(instruction=sample_verbose_text, parent=root)
    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)
    should_break, reward = opt._run_mcts_iteration(root)
    # raw_reward é a saída de simulation(), sempre em [0, 1]
    assert reward == 1.0
    # multiplied_reward no nó reflete o density penalty (< 1.0)
    assert child.multiplied_reward < 1.0


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


def test_time_gate_aborts_before_expansion(mock_optimizer_factory):
    """Time-gate preventivo deve abortar iteração ANTES de chamar _expand_child."""
    opt = mock_optimizer_factory(skill_original="test")
    # Faz _remaining_time retornar valor < min_time_for_gates_s + 60 (default: 10+60=70)
    opt._remaining_time = MagicMock(return_value=5.0)
    opt.config = replace(opt.config, min_time_for_gates_s=10.0)

    root = MCTSNode(instruction="test")
    opt.selection = MagicMock(return_value=root)
    opt._expand_child = MagicMock()

    should_break, reward = opt._run_mcts_iteration(root)

    assert should_break is True
    assert reward == 0.0
    # _expand_child NUNCA deve ser chamado
    opt._expand_child.assert_not_called()
    # Deve ter logado a mensagem de time-gate
    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('Tempo restante insuficiente para gates + simulação' in str(c) for c in log_calls)


def test_gate_fallback_on_simulation_timeout(mock_optimizer_factory):
    """Fallback deve preservar candidato gate-approved quando simulação sofre timeout."""
    import concurrent.futures

    opt = mock_optimizer_factory(skill_original="test")
    opt._evaluate_and_prune = MagicMock(return_value=(False, {}))
    opt._remaining_time = MagicMock(return_value=100.0)  # tempo suficiente para não abortar
    opt._commit_iteration = MagicMock()
    opt._save_checkpoint = MagicMock()
    opt.backpropagation = MagicMock()
    opt._apply_reward_multipliers = MagicMock(return_value=0.5)

    root = MCTSNode(instruction="test")
    root.raw_reward = 0.5
    root.last_reward = 0.5

    # Cria child com gate scores (simulando aprovação dupla dos gates)
    child = MCTSNode(instruction="mutated test", parent=root, depth=1)
    child.gate_ab_score = 0.465
    child.gate_post_eval_score = 0.650

    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)

    # Simula simulation que lança TimeoutError
    def mock_simulation_timeout(instruction):
        raise concurrent.futures.TimeoutError()

    opt.simulation = MagicMock(side_effect=mock_simulation_timeout)

    should_break, reward = opt._run_mcts_iteration(root)

    # Deve retornar fallback_raw (não 0.0)
    assert should_break is False
    assert reward == 0.465  # fallback_raw = gate_ab_score

    # child deve ter raw_reward definido
    assert child.raw_reward == 0.465
    assert child.last_reward == 0.465
    assert child.feedback == "fallback: simulação timeout, gate-approved"

    # _commit_iteration deve ter sido chamado
    opt._commit_iteration.assert_called_once()

    # _save_checkpoint deve ter sido chamado (se fallback > best_reward_so_far)
    opt._save_checkpoint.assert_called()


def test_provisional_checkpoint_for_gate_approved(mock_optimizer_factory):
    """Checkpoint provisório deve ser salvo para candidato gate-approved ANTES da simulação."""
    opt = mock_optimizer_factory(skill_original="test")
    opt._evaluate_and_prune = MagicMock(return_value=(False, {}))
    opt.simulation = MagicMock(return_value=(0.8, "good"))
    opt._save_checkpoint = MagicMock()
    opt._remaining_time = MagicMock(return_value=100.0)

    root = MCTSNode(instruction="test")
    root.raw_reward = 0.5
    root.last_reward = 0.5

    child = MCTSNode(instruction="mutated test", parent=root, depth=1)
    child.gate_ab_score = 0.7
    child.gate_post_eval_score = 0.8

    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)

    opt._run_mcts_iteration(root)

    # Verifica que _save_checkpoint foi chamado pelo menos 1 vez (checkpoint provisório)
    # e o primeiro call foi com gate_ab_score
    call_args_list = opt._save_checkpoint.call_args_list
    assert len(call_args_list) >= 1

    # O primeiro call deve ser do checkpoint provisório (gate_ab_score)
    first_call_child = call_args_list[0][0][0]
    first_call_score = call_args_list[0][0][1]
    assert first_call_child == child
    assert first_call_score == 0.7  # gate_ab_score

    # Verifica log do checkpoint provisório
    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('[Checkpoint Provisório] Candidato gate-approved salvo' in str(c) for c in log_calls)


def test_no_fallback_without_gate_scores(mock_optimizer_factory):
    """Fallback NÃO deve ser aplicado quando gate_ab_score == 0.0 (não passou pelos gates)."""
    import concurrent.futures

    opt = mock_optimizer_factory(skill_original="test")
    opt._evaluate_and_prune = MagicMock(return_value=(False, {}))
    opt._remaining_time = MagicMock(return_value=100.0)

    root = MCTSNode(instruction="test")
    root.raw_reward = 0.5

    # Child SEM gate scores (não passou pelos gates)
    child = MCTSNode(instruction="mutated test", parent=root, depth=1)
    # gate_ab_score e gate_post_eval_score são 0.0 por padrão

    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)

    def mock_simulation_timeout(instruction):
        raise concurrent.futures.TimeoutError()

    opt.simulation = MagicMock(side_effect=mock_simulation_timeout)

    should_break, reward = opt._run_mcts_iteration(root)

    # Deve manter comportamento original: abortar com 0.0
    assert should_break is True
    assert reward == 0.0
    assert child.raw_reward == 0.0  # não foi definido

    # Não deve logar Gate Fallback
    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert not any('[Gate Fallback]' in str(c) for c in log_calls)
    # Deve logar o circuit breaker normal
    assert any('Thread em background continuará mas resultado será descartado' in str(c) for c in log_calls)


def test_incremental_checkpoint_gate_ab(mock_optimizer_factory):
    """Checkpoint incremental deve ser salvo com stage='gate_ab' após aprovação do Gate A/B."""
    opt = mock_optimizer_factory(skill_original="test")
    opt._emitter.emit_log = MagicMock()

    opt._save_incremental_checkpoint(
        stage='gate_ab',
        instruction='mutated instruction text',
        strategy_key='variacao_tom',
        strategy_desc='Variação de Tom',
        gate_ab_score=0.299,
    )

    # Verifica que o checkpoint incremental foi armazenado
    assert opt._incremental_checkpoint is not None
    assert opt._incremental_checkpoint['stage'] == 'gate_ab'
    assert opt._incremental_checkpoint['gate_ab_score'] == 0.299
    assert opt._incremental_checkpoint['instruction'] == 'mutated instruction text'
    assert opt._incremental_checkpoint['strategy_desc'] == 'Variação de Tom'

    # Verifica log emitido
    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('[Checkpoint Incremental] Gate A/B aprovado: score=0.299' in str(c) for c in log_calls)


def test_incremental_checkpoint_post_eval_update(mock_optimizer_factory):
    """Checkpoint incremental deve ser atualizado com stage='post_eval' após ambos os gates aprovarem."""
    opt = mock_optimizer_factory(skill_original="test")
    opt._emitter.emit_log = MagicMock()

    # Primeiro: Gate A/B aprova
    opt._save_incremental_checkpoint(
        stage='gate_ab',
        instruction='mutated text',
        strategy_key='variacao_tom',
        strategy_desc='Variação de Tom',
        gate_ab_score=0.465,
    )

    # Depois: Post-Eval aprova (atualiza o mesmo checkpoint)
    opt._save_incremental_checkpoint(
        stage='post_eval',
        instruction='mutated text',
        strategy_key='variacao_tom',
        strategy_desc='Variação de Tom',
        gate_ab_score=0.465,
        gate_post_eval_score=0.650,
    )

    # Verifica que ambos os scores estão presentes
    assert opt._incremental_checkpoint is not None
    assert opt._incremental_checkpoint['stage'] == 'post_eval'
    assert opt._incremental_checkpoint['gate_ab_score'] == 0.465
    assert opt._incremental_checkpoint['gate_post_eval_score'] == 0.650

    # Verifica log de atualização
    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('[Checkpoint Incremental] Post-Eval aprovado: score=0.650' in str(c) for c in log_calls)
    assert any('completo: A/B=0.465, Post-Eval=0.650' in str(c) for c in log_calls)


def test_discard_incremental_checkpoint(mock_optimizer_factory):
    """Checkpoint incremental deve ser descartado quando Post-Eval reprova."""
    opt = mock_optimizer_factory(skill_original="test")
    opt._emitter.emit_log = MagicMock()

    # Salva checkpoint do Gate A/B
    opt._save_incremental_checkpoint(
        stage='gate_ab',
        instruction='mutated text',
        strategy_key='variacao_tom',
        strategy_desc='Variação de Tom',
        gate_ab_score=0.299,
    )
    assert opt._incremental_checkpoint is not None

    # Descarta (Post-Eval reprovou)
    opt._discard_incremental_checkpoint()

    # Verifica que foi limpo
    assert opt._incremental_checkpoint is None

    # Verifica log de descarte
    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('[Checkpoint Incremental] Descartado (Post-Eval reprovou)' in str(c) for c in log_calls)


def test_guard_uses_gate_ab_score_as_proxy(mock_optimizer_factory):
    """Guarda anti-regressão deve usar gate_ab_score como proxy quando raw_reward=0.0."""
    opt = mock_optimizer_factory(skill_original="test skill instruction")
    opt._emitter.emit_log = MagicMock()
    opt._emitter.emit_error = MagicMock()
    opt.simulation = MagicMock(return_value=(0.5, "feedback"))

    # Cria raiz com raw_reward alto
    root = MCTSNode(instruction="test skill instruction")
    root.raw_reward = 0.657
    root.last_reward = 0.657
    root.q_value = 0.657
    root.visits = 1

    # Cria best_node com raw_reward=0 mas gate_ab_score > root.raw_reward
    # Sem o fix, o guard retornaria root (0.0 < 0.657).
    # Com o fix, deve usar gate_ab_score=0.700 > 0.657 e NÃO retornar root.
    best_node = MCTSNode(instruction="mutated better", parent=root, depth=1)
    best_node.raw_reward = 0.0
    best_node.gate_ab_score = 0.700
    best_node.gate_post_eval_score = 0.0
    best_node.q_value = 0.700
    best_node.visits = 1
    best_node.mutation_strategy = 'variacao_tom'

    # Mock _select_and_log_best_node para retornar nosso best_node
    opt._select_and_log_best_node = MagicMock(return_value=(best_node, 0.7))

    # Chama _format_best_node
    result = opt._format_best_node(root)

    # Não deve retornar root.instruction (gate_ab_score 0.700 > root 0.657)
    assert result != root.instruction

    # Verifica log do proxy
    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('gate_ab_score=0.700' in str(c) and 'proxy' in str(c) for c in log_calls)


def test_guard_still_rejects_worse_proxy(mock_optimizer_factory):
    """Guarda anti-regressão deve rejeitar mesmo com proxy quando gate_ab_score < root.raw_reward."""
    opt = mock_optimizer_factory(skill_original="test skill instruction")
    opt._emitter.emit_log = MagicMock()
    opt._emitter.emit_error = MagicMock()

    root = MCTSNode(instruction="test skill instruction")
    root.raw_reward = 0.657
    root.last_reward = 0.657
    root.q_value = 0.657
    root.visits = 1

    # gate_ab_score é 0.299 < root 0.657 → deve rejeitar
    best_node = MCTSNode(instruction="mutated worse", parent=root, depth=1)
    best_node.raw_reward = 0.0
    best_node.gate_ab_score = 0.299
    best_node.q_value = 0.299
    best_node.visits = 1
    best_node.mutation_strategy = 'variacao_tom'

    opt._select_and_log_best_node = MagicMock(return_value=(best_node, 0.299))

    result = opt._format_best_node(root)

    # Deve retornar root.instruction (gate_ab_score 0.299 < root 0.657)
    assert result == root.instruction

    # Verifica log do proxy
    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('gate_ab_score=0.299' in str(c) and 'proxy' in str(c) for c in log_calls)


def test_discovery_checkpoint_incremental(mock_optimizer_factory):
    """Descoberta bem-sucedida deve salvar checkpoint incremental com stage='discovery'."""
    opt = mock_optimizer_factory(skill_original="test")
    opt._emitter.emit_log = MagicMock()

    opt._save_incremental_checkpoint(
        stage='discovery',
        strategy_key='nova_estrategia_abc123',
        strategy_desc='Estratégia de Contexto Avançada',
    )

    # Verifica checkpoint
    assert opt._incremental_checkpoint is not None
    assert opt._incremental_checkpoint['stage'] == 'discovery'
    assert opt._incremental_checkpoint['strategy_desc'] == 'Estratégia de Contexto Avançada'
    assert opt._incremental_checkpoint['strategy_key'] == 'nova_estrategia_abc123'

    # Verifica log
    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('[Checkpoint Incremental] Descoberta salva' in str(c) for c in log_calls)


def test_gate_fallback_on_pre_simulation_abort(mock_optimizer_factory):
    """Gate Fallback deve ser aplicado quando _check_iteration_abort() dispara
    com gate_post_eval_score > 0 (circuit breaker pré-simulação).
    
    Nota: _check_iteration_abort é chamado 3 vezes no fluxo da iteração:
    1. No início (linha ~1441) — deve retornar False para prosseguir
    2. Após _expand_child (linha ~1466) — deve retornar False para prosseguir
    3. Após checkpoint provisório (linha ~1490) — deve retornar True para disparar fallback
    """
    opt = mock_optimizer_factory(skill_original="test")
    opt._evaluate_and_prune = MagicMock(return_value=(False, {}))
    opt._remaining_time = MagicMock(return_value=100.0)
    opt._commit_iteration = MagicMock()
    opt._save_checkpoint = MagicMock()
    opt._apply_reward_multipliers = MagicMock(return_value=0.5)

    root = MCTSNode(instruction="test")
    root.raw_reward = 0.657
    root.last_reward = 0.657

    child = MCTSNode(instruction="condicionais_de_execução", parent=root, depth=1)
    child.gate_ab_score = 0.374
    child.gate_post_eval_score = 0.525

    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)

    # side_effect: False, False, True → abort só no 3º checkpoint (pós-expansão)
    opt._check_iteration_abort = MagicMock(side_effect=[False, False, True])

    should_break, reward = opt._run_mcts_iteration(root)

    assert should_break is False
    assert reward == 0.374
    assert child.raw_reward == 0.374
    assert child.last_reward == 0.374
    assert child.feedback == "fallback: circuit breaker pré-simulação, gate-approved"

    opt._commit_iteration.assert_called_once()
    opt._save_checkpoint.assert_called()

    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('Circuit breaker pré-simulação' in str(c) for c in log_calls)
    assert not any('Simulação timeout' in str(c) for c in log_calls)


def test_gate_fallback_on_remaining_time_zero(mock_optimizer_factory):
    """Gate Fallback deve ser aplicado quando _remaining_time() <= 0
    com gate_post_eval_score > 0 (deadline pré-simulação).

    Nota: _remaining_time() é chamado em dois pontos:
    1. Time-gate preventivo (linha ~1447) — deve retornar >70 para prosseguir
    2. Verificação pré-simulação (linha ~1495) — deve retornar <=0 para disparar fallback
    """
    opt = mock_optimizer_factory(skill_original="test")
    opt._evaluate_and_prune = MagicMock(return_value=(False, {}))
    opt._check_iteration_abort = MagicMock(side_effect=[False, False, False])  # passa todos checks de abort
    opt._remaining_time = MagicMock(side_effect=[100.0, -1.0])  # time-gate ok, deadline estourado
    opt._commit_iteration = MagicMock()
    opt._save_checkpoint = MagicMock()
    opt._apply_reward_multipliers = MagicMock(return_value=0.5)

    root = MCTSNode(instruction="test")
    root.raw_reward = 0.657
    root.last_reward = 0.657

    child = MCTSNode(instruction="condicionais_de_execução", parent=root, depth=1)
    child.gate_ab_score = 0.374
    child.gate_post_eval_score = 0.525

    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)

    should_break, reward = opt._run_mcts_iteration(root)

    assert should_break is False
    assert reward == 0.374
    assert child.raw_reward == 0.374

    opt._commit_iteration.assert_called_once()

    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert any('Circuit breaker pré-simulação' in str(c) for c in log_calls)
    assert not any('Sem tempo restante para iniciar simulation()' in str(c) for c in log_calls)


def test_no_fallback_pre_simulation_without_post_eval(mock_optimizer_factory):
    """Gate Fallback NÃO deve ser aplicado no abort pré-simulação
    quando gate_post_eval_score == 0.0."""
    opt = mock_optimizer_factory(skill_original="test")
    opt._evaluate_and_prune = MagicMock(return_value=(False, {}))
    opt._remaining_time = MagicMock(return_value=100.0)
    opt._commit_iteration = MagicMock()
    opt._save_checkpoint = MagicMock()

    root = MCTSNode(instruction="test")
    root.raw_reward = 0.5

    child = MCTSNode(instruction="mutated test", parent=root, depth=1)
    child.gate_ab_score = 0.3

    opt.selection = MagicMock(return_value=root)
    opt._expand_node = MagicMock(return_value=child)

    opt._check_iteration_abort = MagicMock(return_value=True)

    should_break, reward = opt._run_mcts_iteration(root)

    assert should_break is True
    assert reward == 0.0
    assert child.raw_reward == 0.0

    opt._commit_iteration.assert_not_called()

    log_calls = [str(c) for c in opt._emitter.emit_log.call_args_list]
    assert not any('[Gate Fallback]' in str(c) for c in log_calls)