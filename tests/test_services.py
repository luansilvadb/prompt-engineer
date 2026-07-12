import pytest
from unittest.mock import MagicMock, patch
from src.state import jobs, JobState
from src.services import OptimizationService

@pytest.fixture
def mock_container_deps():
    return {
        'strategy_discoverer': MagicMock(),
        'agent': MagicMock(),
        'agent_cognitivo': MagicMock(),
        'avaliador_modo_b': MagicMock(),
        'compiler': MagicMock(),
        'experience_store': MagicMock(),
        'job_store': MagicMock(),
        'ai_framework': MagicMock()
    }

@pytest.fixture
def service(mock_container_deps):
    return OptimizationService(
        strategy_discoverer=mock_container_deps['strategy_discoverer'],
        agent=mock_container_deps['agent'],
        agent_cognitivo=mock_container_deps['agent_cognitivo'],
        avaliador_modo_b=mock_container_deps['avaliador_modo_b'],
        compiler=mock_container_deps['compiler'],
        experience_store=mock_container_deps['experience_store'],
        job_store=mock_container_deps['job_store'],
        ai_framework=mock_container_deps['ai_framework']
    )

@pytest.fixture
def mock_loop():
    loop = MagicMock()
    return loop

@patch('src.services.setup')
@patch('src.services.Optimizer')
@patch('src.services.save_optimized_skill')
def test_execute_happy_path(mock_save_skill, mock_optimizer_class, mock_setup, service, mock_loop):
    job_id = "test_job_happy"
    job = JobState()
    job.original_skill = "original skill content"
    jobs[job_id] = job

    mock_optimizer = MagicMock()
    mock_optimizer.optimize.return_value = "optimized skill content"
    mock_optimizer_class.return_value = mock_optimizer
    mock_save_skill.return_value = "dummy_file.txt"

    # Run service
    service.execute(job_id, mock_loop)

    assert job.status == 'completed'
    assert job.result == "optimized skill content"
    service.job_store.save_job_state.assert_called()
    mock_save_skill.assert_called_with("optimized skill content")

def test_execute_already_cancelled(service, mock_loop):
    job_id = "test_job_cancelled"
    job = JobState()
    job.status = 'cancelled'
    jobs[job_id] = job

    service.execute(job_id, mock_loop)

    assert job.status == 'cancelled'
    service.job_store.save_job_state.assert_not_called()

@patch('src.services.setup')
@patch('src.services.Optimizer')
@patch('src.services.save_optimized_skill')
def test_execute_cancelled_during_run(mock_save_skill, mock_optimizer_class, mock_setup, service, mock_loop):
    job_id = "test_job_cancelled_during"
    job = JobState()
    job.original_skill = "original skill content"
    jobs[job_id] = job

    mock_optimizer = MagicMock()
    mock_optimizer.optimize.side_effect = lambda: setattr(job, 'status', 'cancelled') or "partial content"
    mock_optimizer_class.return_value = mock_optimizer
    mock_save_skill.return_value = "dummy_file.txt"

    # Run service
    service.execute(job_id, mock_loop)

    assert job.status == 'cancelled'
    assert job.result == "partial content"
    mock_save_skill.assert_called_with("partial content")

@patch('src.services.setup')
@patch('src.services.Optimizer')
def test_execute_deleted_during_run(mock_optimizer_class, mock_setup, service, mock_loop):
    job_id = "test_job_deleted"
    job = JobState()
    job.original_skill = "original skill content"
    jobs[job_id] = job

    mock_optimizer = MagicMock()
    mock_optimizer.optimize.side_effect = lambda: setattr(job, 'is_deleted', True) or "some content"
    mock_optimizer_class.return_value = mock_optimizer

    # Run service
    service.execute(job_id, mock_loop)

    assert job.is_deleted is True
    # If deleted, it should return early without saving status or result to completed
    assert job.status == 'running'

@patch('src.services.setup')
@patch('src.services.Optimizer')
def test_execute_exception_handling(mock_optimizer_class, mock_setup, service, mock_loop):
    job_id = "test_job_error"
    job = JobState()
    jobs[job_id] = job

    mock_setup.side_effect = Exception("Setup failed")

    # Run service
    service.execute(job_id, mock_loop)

    assert job.status == 'error'
    service.job_store.save_job_state.assert_called()
