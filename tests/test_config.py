import os
from contextlib import contextmanager
from unittest.mock import patch, MagicMock

from src.config import (
    get_drift_thresholds,
    _resolve_api_key,
    _resolve_model_name,
    _apply_model_quirks,
    setup,
)
from src.domain.config import load_mcts_config


def test_cognitivo_config_defaults(monkeypatch):
    # Sobrescreve com os defaults hardcoded do sistema (evita que .env interfira)
    monkeypatch.setenv('MCTS_COGNITIVO_PRIOR_COUNT', '1')
    monkeypatch.setenv('MCTS_COGNITIVO_PRIOR_MEAN_DELTA', '0.05')
    cfg = load_mcts_config()
    assert cfg.cognitivo_prior_count == 1
    assert cfg.cognitivo_prior_mean_delta == 0.05


def test_cognitivo_config_override(monkeypatch):
    monkeypatch.setenv('MCTS_COGNITIVO_PRIOR_COUNT', '6')
    monkeypatch.setenv('MCTS_COGNITIVO_PRIOR_MEAN_DELTA', '0.1')
    cfg = load_mcts_config()
    assert cfg.cognitivo_prior_count == 6
    assert cfg.cognitivo_prior_mean_delta == 0.1


def test_density_config_defaults(monkeypatch):
    monkeypatch.delenv('MCTS_DENSITY_MULTIPLIER_MIN', raising=False)
    monkeypatch.delenv('MCTS_DENSITY_MULTIPLIER_MAX', raising=False)
    monkeypatch.delenv('MCTS_DENSITY_THRESHOLD', raising=False)
    monkeypatch.delenv('MCTS_DENSITY_STRUCTURED_BONUS', raising=False)
    cfg = load_mcts_config()
    assert cfg.density_multiplier_min == 0.5
    assert cfg.density_multiplier_max == 1.5
    assert cfg.density_threshold == 1.0
    assert cfg.density_structured_bonus == 0.2


def test_density_config_override(monkeypatch):
    monkeypatch.setenv('MCTS_DENSITY_MULTIPLIER_MIN', '0.3')
    monkeypatch.setenv('MCTS_DENSITY_MULTIPLIER_MAX', '2.0')
    monkeypatch.setenv('MCTS_DENSITY_THRESHOLD', '0.8')
    monkeypatch.setenv('MCTS_DENSITY_STRUCTURED_BONUS', '0.3')
    cfg = load_mcts_config()
    assert cfg.density_multiplier_min == 0.3
    assert cfg.density_multiplier_max == 2.0
    assert cfg.density_threshold == 0.8
    assert cfg.density_structured_bonus == 0.3


def test_buzzword_threshold_default(monkeypatch):
    monkeypatch.delenv('MCTS_BUZZWORD_THRESHOLD', raising=False)
    cfg = load_mcts_config()
    assert cfg.buzzword_threshold == 3


def test_buzzword_threshold_override(monkeypatch):
    monkeypatch.setenv('MCTS_BUZZWORD_THRESHOLD', '5')
    cfg = load_mcts_config()
    assert cfg.buzzword_threshold == 5


def test_resolve_api_key_explicit_arg_takes_priority(monkeypatch):
    for var in ('API_KEY', 'NVIDIA_API_KEY', 'OPENAI_API_KEY'):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv('API_KEY', 'env-key')
    assert _resolve_api_key('explicit-key') == 'explicit-key'


def test_resolve_api_key_fallback_chain(monkeypatch):
    for var in ('API_KEY', 'NVIDIA_API_KEY', 'OPENAI_API_KEY'):
        monkeypatch.delenv(var, raising=False)

    monkeypatch.setenv('API_KEY', 'api-key')
    assert _resolve_api_key() == 'api-key'

    monkeypatch.delenv('API_KEY', raising=False)
    monkeypatch.setenv('NVIDIA_API_KEY', 'nv-key')
    assert _resolve_api_key() == 'nv-key'

    monkeypatch.delenv('NVIDIA_API_KEY', raising=False)
    monkeypatch.setenv('OPENAI_API_KEY', 'oai-key')
    assert _resolve_api_key() == 'oai-key'


def test_resolve_api_key_default_when_no_env(monkeypatch):
    for var in ('API_KEY', 'NVIDIA_API_KEY', 'OPENAI_API_KEY'):
        monkeypatch.delenv(var, raising=False)
    assert _resolve_api_key() == 'sk-1234'


def test_resolve_model_name_without_prefix(monkeypatch):
    monkeypatch.delenv('MODEL_NAME', raising=False)
    monkeypatch.delenv('MODEL_PREFIX', raising=False)
    assert _resolve_model_name('gpt-4o') == 'gpt-4o'


def test_resolve_model_name_nvidia_nim_alias(monkeypatch):
    assert _resolve_model_name('gpt-4o', 'nvidia_nim') == 'openai/gpt-4o'


def test_resolve_model_name_zhipu_alias(monkeypatch):
    assert _resolve_model_name('glm-4', 'zhipu') == 'zai/glm-4'


def test_resolve_model_name_generic_prefix_appends_slash(monkeypatch):
    assert _resolve_model_name('claude-3', 'anthropic') == 'anthropic/claude-3'


def test_resolve_model_name_prefix_keeps_existing_trailing_slash(monkeypatch):
    assert _resolve_model_name('claude-3', 'anthropic/') == 'anthropic/claude-3'


def test_resolve_model_name_from_env(monkeypatch):
    monkeypatch.setenv('MODEL_NAME', 'gpt-4o-mini')
    monkeypatch.setenv('MODEL_PREFIX', 'openai')
    assert _resolve_model_name() == 'openai/gpt-4o-mini'


def test_apply_model_quirks_gemma_sets_thinking_kwargs():
    kwargs = {'model': 'gemma-4-xxx'}
    _apply_model_quirks('google/gemma-4-it', kwargs)
    assert kwargs['extra_body'] == {'chat_template_kwargs': {'enable_thinking': True}}
    assert kwargs['max_tokens'] == 16384
    assert kwargs['timeout'] == 120


def test_apply_model_quirks_non_gemma_gets_default_timeout():
    kwargs = {'model': 'gpt-4o'}
    _apply_model_quirks('gpt-4o', kwargs)
    assert 'extra_body' not in kwargs
    assert 'max_tokens' not in kwargs
    assert kwargs['timeout'] == 90


def test_setup_normal_model_configures_dspy(monkeypatch):
    for var in ('API_KEY', 'NVIDIA_API_KEY', 'OPENAI_API_KEY', 'MODEL_NAME', 'MODEL_PREFIX', 'API_BASE'):
        monkeypatch.delenv(var, raising=False)

    with setup_dspy_mocks() as mocks:
        lm = setup(model_name='gpt-4o', model_prefix='', api_key='my-key', api_base='https://api.test')

    mocks['lm_class'].assert_called_once()
    call_kwargs = mocks['lm_class'].call_args.kwargs
    assert call_kwargs['model'] == 'gpt-4o'
    assert call_kwargs['api_key'] == 'my-key'
    assert call_kwargs['api_base'] == 'https://api.test'
    mocks['configure'].assert_called_once_with(lm=mocks['lm_instance'])
    assert lm is mocks['lm_instance']


def test_setup_zhipu_provider_sets_zhipu_env(monkeypatch):
    for var in ('API_KEY', 'NVIDIA_API_KEY', 'OPENAI_API_KEY', 'ZAI_API_KEY', 'ZHIPUAI_API_KEY'):
        monkeypatch.delenv(var, raising=False)

    with setup_dspy_mocks():
        setup(model_name='glm-4', model_prefix='zhipu', api_key='zhipu-key')

    assert os.environ.get('ZAI_API_KEY') == 'zhipu-key'
    assert os.environ.get('ZHIPUAI_API_KEY') == 'zhipu-key'


def test_setup_swallows_runtime_error_from_configure(monkeypatch):
    for var in ('API_KEY', 'NVIDIA_API_KEY', 'OPENAI_API_KEY', 'MODEL_NAME', 'MODEL_PREFIX', 'API_BASE'):
        monkeypatch.delenv(var, raising=False)

    with setup_dspy_mocks(configure_side_effect=RuntimeError("already configured")) as mocks:
        lm = setup(model_name='gpt-4o', model_prefix='', api_key='k')

    assert lm is mocks['lm_instance']


def test_drift_thresholds_defaults(monkeypatch):
    for k in (
        'DRIFT_SPEARMAN_FLOOR', 'DRIFT_SPEARMAN_REGRESSION_MARGIN',
        'DRIFT_OFFSET_ALARM', 'DRIFT_OFFSET_REGRESSION_MARGIN',
        'DRIFT_VARIANCE_LOW_CONFIDENCE', 'DRIFT_REPETITIONS',
    ):
        monkeypatch.delenv(k, raising=False)
    cfg = get_drift_thresholds()
    assert cfg['spearman_floor'] == 0.8
    assert cfg['spearman_regression_margin'] == 0.05
    assert cfg['offset_alarm'] == 10.0
    assert cfg['offset_regression_margin'] == 3.0
    assert cfg['variance_low_confidence'] == 8.0
    assert cfg['repetitions'] == 3


def test_drift_thresholds_override(monkeypatch):
    monkeypatch.setenv('DRIFT_SPEARMAN_FLOOR', '0.9')
    monkeypatch.setenv('DRIFT_OFFSET_ALARM', '15.0')
    monkeypatch.setenv('DRIFT_REPETITIONS', '5')
    cfg = get_drift_thresholds()
    assert cfg['spearman_floor'] == 0.9
    assert cfg['offset_alarm'] == 15.0
    assert cfg['repetitions'] == 5


def test_litellm_sanitization_patch():
    import litellm
    with setup_dspy_mocks():
        setup(model_name='glm-4', model_prefix='zhipu', api_key='zhipu-key')

    captured = {}
    orig = getattr(litellm, '_orig_completion', litellm.completion)
    def mock_inner_completion(*args, **kwargs):
        captured['kwargs'] = kwargs
        return {"choices": [{"message": {"content": "ok"}}]}

    with patch('litellm.completion', side_effect=mock_inner_completion):
        # Trigger setup to wrap litellm.completion
        litellm._sanitization_patched = False
        setup(model_name='glm-4', model_prefix='zhipu', api_key='zhipu-key')
        messages = [{"role": "user", "content": "teste — com travessão \u2014 e ácentôs"}]
        litellm.completion(model="gpt-3.5-turbo", api_key="sk-mock", messages=messages)

    sanitized_content = captured['kwargs']['messages'][0]['content']
    assert '\u2014' not in sanitized_content
    assert '—' not in sanitized_content
    assert '--' in sanitized_content


@contextmanager
def setup_dspy_mocks(configure_side_effect=None):
    """Isola setup() de efeitos colaterais reais do DSPy e litellm."""
    lm_instance = MagicMock(name='lm')
    with patch('src.config.dspy.LM', return_value=lm_instance) as lm_class, \
         patch('src.config.dspy.configure', side_effect=configure_side_effect) as configure:
        yield {
            'lm_class': lm_class,
            'lm_instance': lm_instance,
            'configure': configure,
        }


# ── SubTask 6.5: MCTSConfig rejeitando valores inválidos ──────────────────────

from src.domain.config import MCTSConfig
import pytest


class TestMCTSConfigValidation:
    """Testes de validação para os novos campos do MCTSConfig."""

    def _make_config(self, **overrides):
        """Cria um MCTSConfig com defaults válidos, permitindo sobrescrever campos."""
        defaults = dict(
            gamma=0.95, c_param=1.41, progressive_alpha=0.5, progressive_c=2.0,
            value_threshold=0.3, max_iterations=100, value_lr=0.1,
            bandit_c_param=1.41, bandit_temperature=2.0, bandit_temperature_decay=0.95,
            semantic_sim_threshold=0.92, lexical_density_min=0.35,
            verbosity_penalty_factor=0.7, buzzword_threshold=3,
            cognitivo_prior_count=2, cognitivo_prior_mean_delta=0.05,
            density_multiplier_min=0.8, density_multiplier_max=1.2,
            density_threshold=0.9, density_structured_bonus=0.05, reward_floor=0.30,
        )
        defaults.update(overrides)
        return MCTSConfig(**defaults)

    def test_config_rejects_invalid_ab_margin_min_negative(self):
        """ab_margin_min < 0 deve levantar ValueError."""
        with pytest.raises(ValueError, match="ab_margin_min must be in"):
            self._make_config(ab_margin_min=-0.1)

    def test_config_rejects_invalid_ab_margin_min_over_one(self):
        """ab_margin_min > 1 deve levantar ValueError."""
        with pytest.raises(ValueError, match="ab_margin_min must be in"):
            self._make_config(ab_margin_min=1.5)

    def test_config_rejects_invalid_post_eval_margin_min_negative(self):
        """post_eval_margin_min < 0 deve levantar ValueError."""
        with pytest.raises(ValueError, match="post_eval_margin_min must be in"):
            self._make_config(post_eval_margin_min=-0.1)

    def test_config_rejects_invalid_post_eval_margin_min_over_one(self):
        """post_eval_margin_min > 1 deve levantar ValueError."""
        with pytest.raises(ValueError, match="post_eval_margin_min must be in"):
            self._make_config(post_eval_margin_min=1.5)

    def test_config_rejects_invalid_post_eval_sample_size(self):
        """post_eval_sample_size < 1 deve levantar ValueError."""
        with pytest.raises(ValueError, match="post_eval_sample_size must be at least 1"):
            self._make_config(post_eval_sample_size=0)

    def test_config_rejects_invalid_post_eval_sample_size_negative(self):
        """post_eval_sample_size negativo deve levantar ValueError."""
        with pytest.raises(ValueError, match="post_eval_sample_size must be at least 1"):
            self._make_config(post_eval_sample_size=-5)

    def test_config_rejects_invalid_composition_max_strategies(self):
        """composition_max_strategies < 2 deve levantar ValueError."""
        with pytest.raises(ValueError, match="composition_max_strategies must be at least 2"):
            self._make_config(composition_max_strategies=1)

    def test_config_rejects_invalid_composition_max_strategies_zero(self):
        """composition_max_strategies = 0 deve levantar ValueError."""
        with pytest.raises(ValueError, match="composition_max_strategies must be at least 2"):
            self._make_config(composition_max_strategies=0)

    def test_config_rejects_invalid_composition_probability_negative(self):
        """composition_probability < 0 deve levantar ValueError."""
        with pytest.raises(ValueError, match="composition_probability must be in"):
            self._make_config(composition_probability=-0.1)

    def test_config_rejects_invalid_composition_probability_over_one(self):
        """composition_probability > 1 deve levantar ValueError."""
        with pytest.raises(ValueError, match="composition_probability must be in"):
            self._make_config(composition_probability=1.5)

    def test_config_accepts_valid_boundary_values(self):
        """Valores válidos nos limites devem ser aceitos."""
        # Testa valores extremos válidos individualmente
        cfg = self._make_config(
            ab_margin_min=0.0,
            post_eval_margin_min=1.0,
            post_eval_sample_size=1,
            composition_max_strategies=2,
            composition_probability=0.0,
        )
        assert cfg is not None
        assert cfg.ab_margin_min == 0.0
        assert cfg.post_eval_margin_min == 1.0
        assert cfg.post_eval_sample_size == 1
        assert cfg.composition_max_strategies == 2
        assert cfg.composition_probability == 0.0

        # Testa defaults
        cfg2 = self._make_config()
        assert cfg2.ab_margin_min == 0.05
        assert cfg2.post_eval_margin_min == 0.05
        assert cfg2.post_eval_sample_size == 5
        assert cfg2.composition_max_strategies == 3
        assert cfg2.composition_probability == 0.3
