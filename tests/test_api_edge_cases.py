import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from fastapi.testclient import TestClient
from loguru import logger


# Loguru test log setup
_test_log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(_test_log_dir, exist_ok=True)
logger.add(os.path.join(_test_log_dir, "test.log"), rotation="1 MB", retention=3, encoding="utf-8")


# Use a temporary DB for all tests in this module
import tempfile
import importlib
import shutil
import os
tmp_db = tempfile.NamedTemporaryFile(delete=False)
os.environ['CIVITAI_DAEMON_DB_PATH'] = tmp_db.name
importlib.invalidate_caches()
main = importlib.import_module("backend.main")
app = main.app
get_current_user = main.get_current_user
client = TestClient(app)

def teardown_module(module):
    tmp_db.close()
    os.unlink(tmp_db.name)

def test_status_missing_auth():
    # Remove override for this test
    app.dependency_overrides = {}
    resp = client.get("/api/status")
    assert resp.status_code == 401

def test_queue_missing_auth():
    app.dependency_overrides = {}
    resp = client.get("/api/queue")
    assert resp.status_code == 401

def test_download_missing_fields():
    # Set override for auth
    app.dependency_overrides[get_current_user] = lambda: {"user": "test", "role": "admin"}
    # Missing all fields
    resp = client.post("/api/download", json={})
    assert resp.status_code in (422, 400)
    # Missing model_version_id
    job = {"model_id": "id", "url": "url", "filename": "file", "model_type": "checkpoint"}
    resp2 = client.post("/api/download", json=job)
    assert resp2.status_code == 422
    assert "model_version_id" in resp2.text

def test_batch_invalid_manifest():
    app.dependency_overrides[get_current_user] = lambda: {"user": "test", "role": "admin"}
    resp = client.post("/api/batch", json={"manifest": "notalist"})
    assert resp.status_code in (422, 400, 500)
    # Manifest with missing model_version_id
    manifest = [{"model_id": "id", "url": "url", "filename": "file", "model_type": "vae"}]
    resp2 = client.post("/api/batch", json={"manifest": manifest})
    assert resp2.status_code == 200
    # Should skip jobs missing model_version_id, so queued should be 0
    assert resp2.json().get("queued") == 0

def test_metrics_db_error(monkeypatch):
    # Simuleer database error
    def fail():
        raise Exception("db fail")
    from backend.database import downloads_per_day
    monkeypatch.setattr("backend.database.downloads_per_day", fail)
    resp = client.get("/api/metrics", headers={"Authorization": "Bearer testtoken"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["downloads_per_day"] == []
    assert data["downloads_per_day_type_status"] == []
    assert data["file_size_stats_per_type"] == []
    assert data["download_time_stats_per_type"] == []
    assert data["total_downloads"] == 0
