from src.mutation_strategies.registry import StrategyRegistry


def test_seed_registered():
    registry = StrategyRegistry()
    assert 'mutador_cognitivo' in registry.get_all_keys()


def test_seed_prompt_content():
    registry = StrategyRegistry()
    prompt = registry.get_prompt('mutador_cognitivo')
    assert prompt
    assert 'premissas' in prompt.lower()


def test_seed_name():
    registry = StrategyRegistry()
    assert registry.get_name('mutador_cognitivo') == 'Mutador Cognitivo'


def test_seed_idempotent():
    registry = StrategyRegistry()
    from unittest.mock import MagicMock
    registry.save = MagicMock()
    registry._seed_hardcoded_strategies()
    registry.save.assert_not_called()
