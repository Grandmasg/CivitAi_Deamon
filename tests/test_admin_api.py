
import sys
import os
import tempfile
import importlib
import shutil
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
tmp_db = tempfile.NamedTemporaryFile(delete=False)
os.environ['CIVITAI_DAEMON_DB_PATH'] = tmp_db.name
importlib.invalidate_caches()
main = importlib.import_module("backend.main")
app = main.app
get_current_user = main.get_current_user
# Patch authentication for tests: always return an admin user
app.dependency_overrides[get_current_user] = lambda: {"user": "admin", "role": "admin"}
client = TestClient(app)

def teardown_module(module):
    tmp_db.close()
    os.unlink(tmp_db.name)

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
