import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import importlib
main = importlib.import_module("main")
app = main.app
get_current_user = main.get_current_user
# Patch authentication for tests: always return a test user
app.dependency_overrides[get_current_user] = lambda: {"user": "test", "role": "admin"}
client = TestClient(app)

def test_status():
    response = client.get("/api/status", headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert "queue_size" in response.json()
    assert "running" in response.json()
    assert "paused" in response.json()

def test_gui():
    response = client.get("/gui")
    assert response.status_code == 200
    assert "Civitai Download Daemon" in response.text

def test_queue():
    response = client.get("/api/queue", headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert "queue" in response.json()

def test_completed():
    response = client.get("/api/completed", headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert "completed" in response.json()

def test_metrics():
    response = client.get("/api/metrics", headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    assert "downloads_per_day" in response.json()
