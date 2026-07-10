import pytest
from src.config import get_mcts_config


def test_cognitivo_config_defaults(monkeypatch):
    monkeypatch.delenv('MCTS_COGNITIVO_PRIOR_COUNT', raising=False)
    monkeypatch.delenv('MCTS_COGNITIVO_PRIOR_MEAN_DELTA', raising=False)
    cfg = get_mcts_config()
    assert cfg['cognitivo_prior_count'] == 4
    assert cfg['cognitivo_prior_mean_delta'] == 0.05


def test_cognitivo_config_override(monkeypatch):
    monkeypatch.setenv('MCTS_COGNITIVO_PRIOR_COUNT', '6')
    monkeypatch.setenv('MCTS_COGNITIVO_PRIOR_MEAN_DELTA', '0.1')
    cfg = get_mcts_config()
    assert cfg['cognitivo_prior_count'] == 6
    assert cfg['cognitivo_prior_mean_delta'] == 0.1


def test_density_config_defaults(monkeypatch):
    monkeypatch.delenv('MCTS_DENSITY_MULTIPLIER_MIN', raising=False)
    monkeypatch.delenv('MCTS_DENSITY_MULTIPLIER_MAX', raising=False)
    monkeypatch.delenv('MCTS_DENSITY_THRESHOLD', raising=False)
    monkeypatch.delenv('MCTS_DENSITY_STRUCTURED_BONUS', raising=False)
    cfg = get_mcts_config()
    assert cfg['density_multiplier_min'] == 0.5
    assert cfg['density_multiplier_max'] == 1.5
    assert cfg['density_threshold'] == 1.0
    assert cfg['density_structured_bonus'] == 0.2


def test_density_config_override(monkeypatch):
    monkeypatch.setenv('MCTS_DENSITY_MULTIPLIER_MIN', '0.3')
    monkeypatch.setenv('MCTS_DENSITY_MULTIPLIER_MAX', '2.0')
    monkeypatch.setenv('MCTS_DENSITY_THRESHOLD', '0.8')
    monkeypatch.setenv('MCTS_DENSITY_STRUCTURED_BONUS', '0.3')
    cfg = get_mcts_config()
    assert cfg['density_multiplier_min'] == 0.3
    assert cfg['density_multiplier_max'] == 2.0
    assert cfg['density_threshold'] == 0.8
    assert cfg['density_structured_bonus'] == 0.3
