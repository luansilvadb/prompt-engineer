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
