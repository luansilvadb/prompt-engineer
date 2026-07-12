import pytest
from src import store

class DummyJob:
    def __init__(self, status="pending", original_skill="test skill", result=None, logs=None, mcts_nodes=0, model_name="gpt-4", model_prefix="prefix", regras_adicionais=""):
        self.status = status
        self.original_skill = original_skill
        self.result = result
        self.logs = logs or []
        self.mcts_nodes = mcts_nodes
        self.model_name = model_name
        self.model_prefix = model_prefix
        self.regras_adicionais = regras_adicionais

@pytest.fixture(autouse=True)
def mock_jobs_dir(tmp_path, monkeypatch):
    # Monkeypatch the JOBS_DIR to a temporary path for unit tests
    temp_jobs_dir = tmp_path / "jobs"
    monkeypatch.setattr(store, "JOBS_DIR", temp_jobs_dir)
    return temp_jobs_dir

def test_init_store(mock_jobs_dir):
    assert not mock_jobs_dir.exists()
    store.init_store()
    assert mock_jobs_dir.exists()

def test_save_and_load_job(mock_jobs_dir):
    job = DummyJob(status="completed", original_skill="original")
    store.save_job_state("job-123", job)

    file_path = mock_jobs_dir / "job-123.json"
    assert file_path.exists()

    # Load via load_job
    loaded = store.load_job("job-123")
    assert loaded is not None
    assert loaded["id"] == "job-123"
    assert loaded["status"] == "completed"
    assert loaded["original_skill"] == "original"

    # Load non-existent job
    assert store.load_job("non-existent") is None

def test_load_all_jobs(mock_jobs_dir):
    # Save a few jobs
    job1 = DummyJob(status="completed", original_skill="skill 1")
    job2 = DummyJob(status="failed", original_skill="skill 2")
    job3 = DummyJob(status="completed", original_skill="skill 3")

    store.save_job_state("job-1", job1)
    store.save_job_state("job-2", job2)
    store.save_job_state("job-3", job3)

    # Load all
    all_jobs = store.load_all_jobs()
    assert all_jobs["total"] == 3
    assert len(all_jobs["items"]) == 3

    # Load all with filter
    completed_jobs = store.load_all_jobs(status="completed")
    assert completed_jobs["total"] == 2
    assert all(j["status"] == "completed" for j in completed_jobs["items"])

    # Load with pagination
    paginated_jobs = store.load_all_jobs(skip=1, limit=1)
    assert paginated_jobs["total"] == 3
    assert len(paginated_jobs["items"]) == 1

def test_delete_job(mock_jobs_dir):
    job = DummyJob()
    store.save_job_state("job-del", job)

    assert (mock_jobs_dir / "job-del.json").exists()

    # Delete existing
    assert store.delete_job("job-del") is True
    assert not (mock_jobs_dir / "job-del.json").exists()

    # Delete non-existent
    assert store.delete_job("job-del") is False

def test_corrupted_json_loading(mock_jobs_dir):
    store.init_store()
    file_path = mock_jobs_dir / "corrupted.json"
    with open(file_path, "w") as f:
        f.write("invalid json data {")

    assert store.load_job("corrupted") is None
    assert store._read_job_summary(file_path) is None
