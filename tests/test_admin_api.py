
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from fastapi.testclient import TestClient

import importlib
main = importlib.import_module("main")
app = main.app
get_current_user = main.get_current_user
# Patch authentication for tests: always return an admin user
app.dependency_overrides[get_current_user] = lambda: {"user": "admin", "role": "admin"}
client = TestClient(app)

def test_admin_pause_resume_stop():
    # Pause
    resp = client.post("/api/pause")
    assert resp.status_code == 200
    assert resp.json()["status"] == "paused"
    # Resume
    resp = client.post("/api/resume")
    assert resp.status_code == 200
    assert resp.json()["status"] == "resumed"
    # Stop
    resp = client.post("/api/stop")
    assert resp.status_code == 200
    assert resp.json()["status"] == "stopped"

def test_admin_only_endpoint():
    resp = client.get("/api/admin-only")
    assert resp.status_code == 200
    assert "admin" in resp.json()["message"]

def test_admin_forbidden_for_non_admin():
    # Patch to simulate non-admin
    app.dependency_overrides[get_current_user] = lambda: {"user": "user", "role": "user"}
    resp = client.get("/api/admin-only")
    assert resp.status_code == 403
    app.dependency_overrides[get_current_user] = lambda: {"user": "admin", "role": "admin"}

def test_pause_requires_admin():
    app.dependency_overrides[get_current_user] = lambda: {"user": "user", "role": "user"}
    resp = client.post("/api/pause")
    assert resp.status_code == 403
    app.dependency_overrides[get_current_user] = lambda: {"user": "admin", "role": "admin"}
