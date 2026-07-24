import math
from unittest.mock import patch

import pytest

from src.mutation_strategies.bandit import MutationBandit
from src.domain.bandit_interfaces import BanditStats


def test_bandit_cognitivo_prior_counts():
    bandit = MutationBandit()
    bandit.load_priors({'mutador_cognitivo': {'count': 4, 'mean_delta': 0.05}})
    assert bandit._counts['mutador_cognitivo'] == 2
    assert bandit._rewards['mutador_cognitivo'] == 0.10


def test_bandit_cognitivo_prior_formula():
    bandit = MutationBandit()
    bandit.load_priors({'mutador_cognitivo': {'count': 10, 'mean_delta': 0.2}})
    assert bandit._counts['mutador_cognitivo'] == 5
    assert bandit._rewards['mutador_cognitivo'] == 1.0


def test_bandit_cognitivo_key_exists():
    bandit = MutationBandit()
    assert 'mutador_cognitivo' in bandit._counts


def test_optimizer_has_agent_cognitivo(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="Test")
    assert hasattr(opt, 'agent_cognitivo')
    assert opt.agent_cognitivo is not None


def test_optimizer_cognitivo_prior_injected(mock_optimizer_factory):
    opt = mock_optimizer_factory(skill_original="Test")
    assert 'mutador_cognitivo' in opt.mutation_bandit._counts
    assert opt.mutation_bandit._counts['mutador_cognitivo'] > 0
    assert opt.mutation_bandit._rewards['mutador_cognitivo'] > 0


# ---------------------------------------------------------------------------
# UCB1 selection algorithm — pure logic, previously uncovered.
# Contratos sob teste (src/mutation_strategies/bandit.py):
#   - _ensure_key: inicializa braço novo em count=0, reward=0.0
#   - _pick_untried: retorna braço aleatório com count==0, ou None
#   - _ucb_score: mean_reward + c_param * sqrt(ln(total)/n)
#   - select: first-play (untried) depois argmax UCB (exploitation)
#   - update: incrementa count e acumula reward
#   - get_stats: retorna BanditStats por braço
#   - load_priors: virtual_count = min(count*0.5, 10)
# ---------------------------------------------------------------------------


def test_ensure_key_initializes_new_arm_to_zero():
    bandit = MutationBandit()
    bandit._ensure_key('nova_estrategia')
    assert bandit._counts['nova_estrategia'] == 0
    assert bandit._rewards['nova_estrategia'] == 0.0


def test_ensure_key_is_idempotent_for_existing_arm():
    bandit = MutationBandit()
    bandit.update('mutador_cognitivo', 0.9)
    bandit.update('mutador_cognitivo', 0.9)
    # Chamar _ensure_key num braço já populado NÃO zera seus acumuladores.
    bandit._ensure_key('mutador_cognitivo')
    assert bandit._counts['mutador_cognitivo'] == 2
    assert bandit._rewards['mutador_cognitivo'] == pytest.approx(1.8)


def test_pick_untried_returns_an_untried_arm():
    bandit = MutationBandit()
    # Todos os braços nativos (__DISCOVER__, mutador_cognitivo) começam em 0.
    with patch('src.mutation_strategies.bandit.random.choice', return_value='__DISCOVER__') as mock_choice:
        result = bandit._pick_untried()
    assert result == '__DISCOVER__'
    mock_choice.assert_called_once()
    # O pool passado a random.choice contém apenas braços com count==0.
    pool = mock_choice.call_args[0][0]
    assert all(bandit._counts[s] == 0 for s in pool)


def test_pick_untried_returns_none_when_all_arms_tried():
    bandit = MutationBandit()
    for key in list(bandit._counts.keys()):
        bandit._counts[key] = 1
    assert bandit._pick_untried() is None


def test_ucb_score_matches_formula_exactly():
    bandit = MutationBandit(c_param=1.41)
    bandit._counts['__DISCOVER__'] = 1
    bandit._rewards['__DISCOVER__'] = 0.2
    bandit._counts['mutador_cognitivo'] = 1
    bandit._rewards['mutador_cognitivo'] = 0.5
    total_pulls = sum(bandit._counts.values())  # 2

    expected = 0.5 + 1.41 * math.sqrt(math.log(total_pulls) / 1)
    assert bandit._ucb_score('mutador_cognitivo', total_pulls) == pytest.approx(expected)


def test_ucb_score_untried_arm_returns_infinity():
    # Contrato: _ucb_score retorna inf para braços nunca puxados (n=0),
    # garantindo que sejam priorizados caso a fase untried deixe escapar
    # algum braço (ex.: __DISCOVER__ após exclusão seletiva).
    bandit = MutationBandit(c_param=1.41)
    bandit._counts['mutador_cognitivo'] = 0
    bandit._rewards['mutador_cognitivo'] = 0.0
    assert bandit._ucb_score('mutador_cognitivo', total_pulls=5) == float('inf')


def test_ucb_score_mean_reward_guarded_for_single_pull():
    # n=1: mean_reward = rewards/max(1,1) computa sem divisão por zero.
    bandit = MutationBandit(c_param=1.41)
    bandit._counts['mutador_cognitivo'] = 1
    bandit._rewards['mutador_cognitivo'] = 0.5
    total_pulls = 1
    expected_mean = 0.5 / 1
    expected_exploration = 1.41 * math.sqrt(math.log(total_pulls) / 1)
    assert bandit._ucb_score('mutador_cognitivo', total_pulls) == pytest.approx(
        expected_mean + expected_exploration
    )


def test_select_returns_untried_arm_first_first_play():
    # UCB1 first-play: qualquer braço inexplorado tem prioridade sobre a
    # fórmula de exploitation.
    bandit = MutationBandit()
    with patch('src.mutation_strategies.bandit.random.choice', return_value='mutador_cognitivo'):
        chosen = bandit.select()
    assert chosen == 'mutador_cognitivo'
    assert bandit._counts['mutador_cognitivo'] == 0  # select NÃO atualiza contadores


def test_select_exploits_argmax_ucb_after_all_arms_tried():
    # Com temperatura desprezível, o comportamento é argmax determinístico
    # (equivalente ao UCB1 original).
    bandit = MutationBandit(c_param=1.41, temperature=0.0001)
    # Dá recompensas muito diferentes para forçar um argmax determinístico.
    for key in bandit._counts:
        bandit._counts[key] = 5
    bandit._rewards['__DISCOVER__'] = 0.1 * 5      # mean 0.1
    bandit._rewards['mutador_cognitivo'] = 0.9 * 5  # mean 0.9 — argmax claro

    chosen = bandit.select()
    assert chosen == 'mutador_cognitivo'


def test_select_thompson_sampling_is_probabilistic():
    """Thompson Sampling com temperatura > 0 deve explorar braços subótimos."""
    bandit = MutationBandit(c_param=1.41, temperature=10.0, temperature_decay=1.0)
    for key in bandit._counts:
        bandit._counts[key] = 5
    bandit._rewards['__DISCOVER__'] = 0.1 * 5
    bandit._rewards['mutador_cognitivo'] = 0.9 * 5

    # Com T=10 alta, explosão da softmax é atenuada e a distribuição fica
    # quase uniforme. Em 50 seleções, ambos os braços devem aparecer.
    seen = set()
    for _ in range(50):
        seen.add(bandit.select())
    assert len(seen) >= 2, f"Thompson Sampling deveria explorar ambos os braços, mas só viu: {seen}"


def test_thompson_temperature_decays_over_time():
    """A temperatura deve decair exponencialmente a cada select()."""
    bandit = MutationBandit(temperature=2.0, temperature_decay=0.5)
    initial_temp = bandit.temperature
    bandit.select()
    assert bandit.temperature == initial_temp * 0.5
    bandit.select()
    assert bandit.temperature == initial_temp * 0.5 * 0.5


def test_update_increments_count_and_accumulates_reward():
    bandit = MutationBandit()
    bandit.update('mutador_cognitivo', 0.3)
    bandit.update('mutador_cognitivo', 0.5)
    assert bandit._counts['mutador_cognitivo'] == 2
    assert bandit._rewards['mutador_cognitivo'] == pytest.approx(0.8)


def test_update_registers_unknown_arm_before_updating():
    bandit = MutationBandit()
    bandit.update('estrategia_inedita', 0.7)
    assert bandit._counts['estrategia_inedita'] == 1
    assert bandit._rewards['estrategia_inedita'] == pytest.approx(0.7)


def test_get_stats_returns_banditstats_for_every_arm():
    bandit = MutationBandit()
    bandit.update('__DISCOVER__', 0.4)
    stats = bandit.get_stats()

    assert set(stats.keys()) == set(bandit._counts.keys())
    for key, stat in stats.items():
        assert isinstance(stat, BanditStats)
        assert stat.strategy_key == key
        assert stat.count == bandit._counts[key]
        assert stat.total_reward == bandit._rewards[key]
        assert stat.mean_delta == pytest.approx(
            bandit._rewards[key] / max(1, bandit._counts[key])
        )


def test_get_stats_mean_delta_zero_for_unpulled_arm():
    bandit = MutationBandit()  # braços nativos com count==0
    stats = bandit.get_stats()['__DISCOVER__']
    assert stats.count == 0
    assert stats.mean_delta == 0.0  # max(1, 0) evita divisão por zero


def test_select_syncs_new_registry_keys_before_choosing():
    # Estratégia descoberta em runtime deve entrar no bandit durante select().
    bandit = MutationBandit()
    with patch('src.mutation_strategies.bandit.registry.get_all_keys',
               return_value=['mutador_cognitivo', 'estrategia_recem_descoberta']):
        # Força first-play determinístico sobre o novo braço.
        with patch('src.mutation_strategies.bandit.random.choice',
                   return_value='estrategia_recem_descoberta'):
            chosen = bandit.select()
    assert chosen == 'estrategia_recem_descoberta'
    assert 'estrategia_recem_descoberta' in bandit._counts


def test_load_priors_caps_virtual_count_at_ten():
    # Edge case: count alto (ex.: 100) → virtual_count = min(50, 10) = 10.
    bandit = MutationBandit()
    bandit.load_priors({'mutador_cognitivo': {'count': 100, 'mean_delta': 0.2}})
    assert bandit._counts['mutador_cognitivo'] == 10  # cap aplicado
    assert bandit._rewards['mutador_cognitivo'] == pytest.approx(0.2 * 10)


def test_load_priors_accumulates_across_multiple_calls():
    bandit = MutationBandit()
    bandit.load_priors({'mutador_cognitivo': {'count': 4, 'mean_delta': 0.1}})   # +2
    bandit.load_priors({'mutador_cognitivo': {'count': 4, 'mean_delta': 0.1}})   # +2
    assert bandit._counts['mutador_cognitivo'] == 4
    assert bandit._rewards['mutador_cognitivo'] == pytest.approx(0.4)


def test_load_priors_registers_unknown_strategy():
    bandit = MutationBandit()
    bandit.load_priors({'estrategia_nova': {'count': 2, 'mean_delta': 0.05}})
    assert 'estrategia_nova' in bandit._counts
    assert bandit._counts['estrategia_nova'] == 1  # min(1, 10)


def test_default_c_param_is_canonical_literal():
    # c_param padrão é o literal UCB1 canônico 1.41 (~sqrt(2)).
    bandit = MutationBandit()
    assert bandit.c_param == 1.41


def test_discover_arm_always_present():
    # Braço __DISCOVER__ (Tabula Rasa) é invariante do bandit.
    bandit = MutationBandit()
    assert '__DISCOVER__' in bandit._counts
    assert '__DISCOVER__' in bandit._rewards


# ── SubTask 6.2: Composição de estratégias via bandit ──────────────────────────

class TestBanditComposition:
    def test_bandit_returns_composition(self):
        """Com composition_probability=1.0, select() retorna lista de 2+ estratégias distintas."""
        bandit = MutationBandit(composition_probability=1.0, composition_max_strategies=3)

        # Avança o round-robin (consome todas as estratégias conhecidas uma vez)
        known = sorted([k for k in bandit._counts.keys() if k != '__DISCOVER__'])
        for _ in known:
            _ = bandit.select()  # consome fase round-robin

        # Agora select() deve entrar na fase UCB com composição
        chosen = bandit.select()
        assert isinstance(chosen, list), f"select() deveria retornar lista, mas retornou {type(chosen)}"
        assert len(chosen) >= 2, f"Composição deveria ter pelo menos 2 estratégias, mas tem {len(chosen)}"
        # Todas as estratégias devem ser distintas
        assert len(set(chosen)) == len(chosen), "Estratégias na composição deveriam ser distintas"
        # Nenhuma deve ser __DISCOVER__
        assert '__DISCOVER__' not in chosen, "Composição não deveria incluir __DISCOVER__"

    def test_bandit_returns_single_with_zero_prob(self):
        """Com composition_probability=0.0, select() nunca retorna lista."""
        bandit = MutationBandit(composition_probability=0.0)

        # Dá alguns pulls para todas as estratégias nativas
        for key in list(bandit._counts.keys()):
            if key != '__DISCOVER__':
                bandit._counts[key] = 1
                bandit._rewards[key] = 0.5

        # Múltiplas seleções: sempre deve ser string, nunca lista
        for _ in range(20):
            chosen = bandit.select()
            assert isinstance(chosen, str), (
                f"Com composition_probability=0.0, select() deveria sempre retornar str, "
                f"mas retornou {type(chosen)}"
            )

    def test_composite_key_registered_in_counts(self):
        """Após select() retornar lista, a chave composta está em _counts."""
        bandit = MutationBandit(composition_probability=1.0, composition_max_strategies=3)

        # Avança o round-robin antes
        known = sorted([k for k in bandit._counts.keys() if k != '__DISCOVER__'])
        for _ in known:
            _ = bandit.select()

        chosen = bandit.select()
        composite_key = f"composite:{'+'.join(chosen)}"

        assert composite_key in bandit._counts, (
            f"Chave composta '{composite_key}' deveria estar em _counts"
        )
        assert composite_key in bandit._rewards, (
            f"Chave composta '{composite_key}' deveria estar em _rewards"
        )

    def test_composite_key_updated_with_reward(self):
        """update() na chave composta incrementa _counts e _rewards."""
        bandit = MutationBandit(composition_probability=1.0, composition_max_strategies=3)

        # Avança o round-robin antes
        known = sorted([k for k in bandit._counts.keys() if k != '__DISCOVER__'])
        for _ in known:
            _ = bandit.select()

        chosen = bandit.select()
        composite_key = f"composite:{'+'.join(chosen)}"

        # Atualiza a chave composta
        bandit.update(composite_key, 0.8)
        bandit.update(composite_key, 0.6)

        assert bandit._counts[composite_key] == 2, (
            f"Esperado count=2, obtido {bandit._counts[composite_key]}"
        )
        assert bandit._rewards[composite_key] == pytest.approx(1.4), (
            f"Esperado rewards=1.4, obtido {bandit._rewards[composite_key]}"
        )

        # Verifica via get_stats também
        stats = bandit.get_stats()
        assert composite_key in stats
        assert stats[composite_key].count == 2
        assert stats[composite_key].mean_delta == pytest.approx(0.7)
        assert stats[composite_key].total_reward == pytest.approx(1.4)
