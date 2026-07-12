from unittest.mock import patch
from fastapi.testclient import TestClient

# Mock components before importing the app to avoid side effects during setup/run
with patch("src.store.init_store"), \
     patch("src.config.setup"):
    from src.api import app

client = TestClient(app)

def test_serve_spa_index():
    # Test GET / should serve index.html (or 404 if not found, but it exists in workspace)
    response = client.get("/")
    # If frontend/index.html exists and is readable, it should return 200.
    # Otherwise, it might raise 404 with a detail.
    if response.status_code == 200:
        assert "html" in response.headers.get("content-type", "")
    else:
        assert response.status_code == 404

def test_get_jobs_empty():
    with patch("src.store.load_all_jobs") as mock_load_all:
        mock_load_all.return_value = {"total": 0, "items": [], "skip": 0, "limit": 50}
        response = client.get("/api/jobs")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert len(data["items"]) == 0

def test_get_job_not_found():
    with patch("src.store.load_job") as mock_load:
        mock_load.return_value = None
        response = client.get("/api/jobs/non-existent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

def test_delete_job_not_found():
    with patch("src.store.delete_job") as mock_delete:
        mock_delete.return_value = False
        response = client.delete("/api/jobs/non-existent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

def test_stop_optimization_not_found():
    response = client.post("/api/stop/non-existent-id")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

@patch("src.services.OptimizationService.execute")
def test_start_optimization(mock_execute):
    payload = {
        "skillOriginal": "Sempre elogie o usuário.",
        "modelName": "gpt-3.5-turbo",
        "modelPrefix": "system",
        "apiBase": "https://api.openai.com/v1",
        "apiKey": "sk-123",
        "regrasAdicionais": ["Não use emojis."]
    }

    with patch("src.store.save_job_state") as mock_save:
        response = client.post("/api/optimize", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert mock_save.called
        assert mock_execute.called
