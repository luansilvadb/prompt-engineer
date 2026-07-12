from src.mutation_strategies.bandit import MutationBandit


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


def test_optimizer_has_agent_cognitivo(mock_heavy_evaluators):
    from src.optimizer import Optimizer
    opt = Optimizer(skill_original="Test")
    assert hasattr(opt, 'agent_cognitivo')
    assert opt.agent_cognitivo is not None


def test_optimizer_cognitivo_prior_injected(mock_heavy_evaluators):
    from src.optimizer import Optimizer
    opt = Optimizer(skill_original="Test")
    assert 'mutador_cognitivo' in opt.mutation_bandit._counts
    assert opt.mutation_bandit._counts['mutador_cognitivo'] > 0
    assert opt.mutation_bandit._rewards['mutador_cognitivo'] > 0
