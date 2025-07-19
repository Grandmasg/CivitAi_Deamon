
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from fastapi.testclient import TestClient

import importlib
main = importlib.import_module("main")
app = main.app
get_current_user = main.get_current_user
client = TestClient(app)

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
    resp = client.post("/api/download", json={})
    assert resp.status_code in (422, 400)

def test_batch_invalid_manifest():
    app.dependency_overrides[get_current_user] = lambda: {"user": "test", "role": "admin"}
    resp = client.post("/api/batch", json={"manifest": "notalist"})
    assert resp.status_code in (422, 400, 500)

def test_metrics_db_error(monkeypatch):
    # Simuleer database error
    def fail():
        raise Exception("db fail")
    from main import downloads_per_day
    monkeypatch.setattr("main.downloads_per_day", fail)
    resp = client.get("/api/metrics", headers={"Authorization": "Bearer testtoken"})
    assert resp.status_code == 200
    assert resp.json()["downloads_per_day"] == []
