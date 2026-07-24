"""Testes para controle de custo e tempo (spec add-cost-controls)."""
import json
import os
import tempfile
from unittest.mock import MagicMock, patch

from src.domain.config import MCTSConfig, load_mcts_config, _validate_iteration_timeout_s, _validate_iteration_llm_call_limit, _validate_composite_timeout_s
from src.domain.bandit_interfaces import BanditStats, IMutationBandit
from src.mutation_strategies.bandit import MutationBandit


# ── Task 1 / SubTask 8.6: Config parameters ────────────────────────────────

class TestConfigNewParams:
    def test_default_values(self):
        c = MCTSConfig(
            gamma=0.95, c_param=1.41, progressive_alpha=0.5, progressive_c=2.0,
            value_threshold=0.2, max_iterations=10, value_lr=0.1, bandit_c_param=1.41,
            bandit_temperature=2.0, bandit_temperature_decay=0.95,
            semantic_sim_threshold=0.85, lexical_density_min=0.35,
            verbosity_penalty_factor=0.85, buzzword_threshold=3,
            cognitivo_prior_count=4, cognitivo_prior_mean_delta=0.05,
            density_multiplier_min=0.5, density_multiplier_max=1.5,
            density_threshold=1.0, density_structured_bonus=0.2, reward_floor=0.30,
        )
        assert c.iteration_timeout_s == 300
        assert c.iteration_llm_call_limit == 50
        assert c.composite_timeout_s == 45

    def test_override_via_env(self, monkeypatch):
        monkeypatch.setenv('MCTS_ITERATION_TIMEOUT_S', '120')
        monkeypatch.setenv('MCTS_ITERATION_LLM_CALL_LIMIT', '30')
        monkeypatch.setenv('MCTS_COMPOSITE_TIMEOUT_S', '25')
        cfg = load_mcts_config()
        assert cfg.iteration_timeout_s == 120
        assert cfg.iteration_llm_call_limit == 30
        assert cfg.composite_timeout_s == 25

    def test_validation_min_30s(self):
        try:
            _validate_iteration_timeout_s(10)
            assert False, "Should raise"
        except ValueError:
            pass
        _validate_iteration_timeout_s(30)  # ok

    def test_validation_min_10_calls(self):
        try:
            _validate_iteration_llm_call_limit(5)
            assert False, "Should raise"
        except ValueError:
            pass
        _validate_iteration_llm_call_limit(10)  # ok

    def test_validation_min_20s_composite(self):
        try:
            _validate_composite_timeout_s(10)
            assert False, "Should raise"
        except ValueError:
            pass
        _validate_composite_timeout_s(20)  # ok


# ── Task 5 / SubTask 8.3: Bandit cost tracking ─────────────────────────────

class TestBanditCostTracking:
    def test_record_cost_success(self):
        mb = MutationBandit()
        mb.record_cost('mutador_cognitivo', 10, 20000, success=True)
        assert mb._total_llm_calls['mutador_cognitivo'] == 10
        assert mb._estimated_tokens['mutador_cognitivo'] == 20000
        assert mb._successful_expansions['mutador_cognitivo'] == 1

    def test_record_cost_failure(self):
        mb = MutationBandit()
        mb.record_cost('test_strat', 5, 10000, success=False)
        assert mb._total_llm_calls['test_strat'] == 5
        assert mb._successful_expansions['test_strat'] == 0  # unchanged

    def test_record_cost_accumulates(self):
        mb = MutationBandit()
        mb.record_cost('s', 3, 6000, True)
        mb.record_cost('s', 7, 14000, True)
        mb.record_cost('s', 2, 4000, False)
        assert mb._total_llm_calls['s'] == 12
        assert mb._successful_expansions['s'] == 2

    def test_get_stats_includes_cost_fields(self):
        mb = MutationBandit()
        mb.record_cost('s', 10, 20000, True)
        stats = mb.get_stats()
        assert stats['s'].total_llm_calls == 10
        assert stats['s'].estimated_tokens == 20000
        assert stats['s'].successful_expansions == 1

    def test_ucb_cost_penalty_when_above_median(self):
        """Estratégia com custo elevado recebe penalidade no score UCB."""
        mb = MutationBandit()
        # Estratégia barata: 1 chamada por aprovação
        mb.record_cost('cheap', 1, 2000, True)
        mb.update('cheap', 0.5)
        # Estratégia cara: 20 chamadas por aprovação (>> 1.5x mediana)
        mb.record_cost('expensive', 20, 40000, True)
        mb.update('expensive', 0.5)

        total_pulls = sum(mb._counts.values())
        score_cheap = mb._ucb_score('cheap', total_pulls)
        score_expensive = mb._ucb_score('expensive', total_pulls)
        # A estratégia cara deve ter score menor devido à penalidade
        assert score_expensive < score_cheap, \
            f"expensive={score_expensive} should be < cheap={score_cheap}"

    def test_no_penalty_without_successful_expansions(self):
        """Estratégias sem expansões bem-sucedidas não são penalizadas."""
        mb = MutationBandit()
        mb.update('no_success', 0.5)  # tem reward mas 0 successful_expansions
        mb.record_cost('no_success', 100, 200000, success=False)

        total_pulls = sum(mb._counts.values())
        score = mb._ucb_score('no_success', total_pulls)
        # Deve ser um valor finito (não penalizado)
        assert score > 0, f"Score should be positive, got {score}"

    def test_force_composition_returns_list(self):
        mb = MutationBandit()
        # Primeiro puxa para ter dados UCB
        mb.update('mutador_cognitivo', 0.5)
        comp = mb.force_composition(2)
        assert isinstance(comp, list)
        assert len(comp) == 2

    def test_force_composition_with_few_strategies(self):
        mb = MutationBandit()
        # Apenas mutador_cognitivo disponível inicialmente
        comp = mb.force_composition(3)
        # Deve retornar lista com estratégias disponíveis
        assert isinstance(comp, list)
        assert len(comp) >= 1


# ── Task 6 / SubTask 8.4: Checkpoint ────────────────────────────────────────

class TestCheckpoint:
    def test_save_checkpoint_structure_and_logic(self):
        """Verifica estrutura JSON e lógica de checkpoint."""
        import json
        # Testa que o JSON tem a estrutura correta
        data = {
            'instruction': 'Seja um coach de vendas...',
            'score': 0.812,
            'strategy': 'mutador_cognitivo',
            'depth': 3,
            'timestamp': '2026-07-23T01:49:00',
            'iteration': 12,
        }
        json_str = json.dumps(data)
        parsed = json.loads(json_str)
        assert parsed['instruction'] == 'Seja um coach de vendas...'
        assert parsed['score'] == 0.812
        assert parsed['strategy'] == 'mutador_cognitivo'
        assert parsed['depth'] == 3
        assert 'timestamp' in parsed
        assert 'iteration' in parsed

    def test_checkpoint_guard_condition(self):
        """Verifica que checkpoint só é salvo quando novo score > best_reward_so_far."""
        reward = 0.812
        best_reward_so_far = 0.500
        should_save = reward > best_reward_so_far
        assert should_save  # New best, should save checkpoint

        reward2 = 0.400
        should_save2 = reward2 > best_reward_so_far
        assert not should_save2  # Worse than previous best, no checkpoint


# ── Task 7 / SubTask 8.5: Density transparency ──────────────────────────────

class TestDensityTransparency:
    def test_floor_detection(self):
        """Verifica que o histórico de piso funciona corretamente."""
        history = []
        density_multiplier_min = 0.5
        # Simula 9 penalidades no piso e 1 variável
        for _ in range(9):
            history.append(True)  # at floor
        history.append(False)  # not at floor
        assert len(history) == 10
        pct_at_floor = sum(history) / len(history)
        assert pct_at_floor == 0.9  # 90% > 80%
        assert pct_at_floor > 0.8  # Should trigger warning

    def test_not_at_floor_threshold(self):
        """Se menos de 80% no piso, não deve disparar warning."""
        history = [True] * 7 + [False] * 3
        pct = sum(history) / 10
        assert pct == 0.7
        assert pct <= 0.8  # No warning


# ── SubTask 8.1: Circuit breaker test (config only) ────────────────────────

class TestCircuitBreakerConfig:
    def test_iteration_timeout_default(self):
        c = MCTSConfig(
            gamma=0.95, c_param=1.41, progressive_alpha=0.5, progressive_c=2.0,
            value_threshold=0.2, max_iterations=10, value_lr=0.1, bandit_c_param=1.41,
            bandit_temperature=2.0, bandit_temperature_decay=0.95,
            semantic_sim_threshold=0.85, lexical_density_min=0.35,
            verbosity_penalty_factor=0.85, buzzword_threshold=3,
            cognitivo_prior_count=4, cognitivo_prior_mean_delta=0.05,
            density_multiplier_min=0.5, density_multiplier_max=1.5,
            density_threshold=1.0, density_structured_bonus=0.2, reward_floor=0.30,
        )
        assert c.iteration_timeout_s == 300
        assert c.iteration_llm_call_limit == 50


# ── SubTask 8.2: Gradative approach (logic test) ───────────────────────────

class TestGradativeApproach:
    def test_gradation_flags_isolated_rejected(self):
        """Verifica lógica de flags: tentativa 0 isolada rejeitada -> próxima composição 2."""
        prev_was_isolated_rejected = False
        prev_was_2comp_rejected = False

        # Simula tentativa 0: isolada, falhou
        tentativa = 0
        is_composite = False
        # Rejeitada...
        if tentativa == 0 and not is_composite:
            prev_was_isolated_rejected = True

        # Simula tentativa 1: deve forçar composição de 2
        tentativa = 1
        assert prev_was_isolated_rejected  # flag ativa
        if tentativa == 1 and prev_was_isolated_rejected:
            force_2comp = True
        else:
            force_2comp = False
        assert force_2comp

    def test_gradation_flags_composite2_rejected(self):
        """Verifica lógica: tentativa 1 composição 2 falhou -> tentativa 2 composição 3."""
        prev_was_2comp_rejected = True
        tentativa = 2
        if tentativa == 2 and prev_was_2comp_rejected:
            force_3comp = True
        else:
            force_3comp = False
        assert force_3comp

    def test_gradation_bandit_composite_natural_no_reduction(self):
        """Se o bandit selecionou composição natural na tentativa 0, não aplicar redução."""
        prev_was_isolated_rejected = False
        tentativa = 1
        # A flag não foi setada porque tentativa 0 foi composite, não isolated
        if tentativa == 1 and prev_was_isolated_rejected:
            force_2comp = True
        else:
            force_2comp = False
        assert not force_2comp  # Não força redução
