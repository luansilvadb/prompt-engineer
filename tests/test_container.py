from unittest.mock import patch
from src.infrastructure.container import Container

@patch('src.infrastructure.container.load_avaliador')
def test_container_initialization(mock_load_avaliador):
    container = Container()

    mock_load_avaliador.assert_called_once()

    # Assert and verify instances
    assert container.get_strategy_discoverer() is not None
    assert container.get_agent() is not None
    assert container.get_agent_cognitivo() is not None
    assert container.get_avaliador_modo_b() is not None
    assert container.get_compiler() is not None
    assert container.get_experience_store() is not None
    assert container.get_job_store() is not None
    assert container.get_ai_framework() is not None
