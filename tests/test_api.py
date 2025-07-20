import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import importlib
main = importlib.import_module("backend.main")
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

import pytest


def test_metrics():
    response = client.get("/api/metrics", headers={"Authorization": "Bearer testtoken"})
    assert response.status_code == 200
    data = response.json()
    # Check alle relevante velden
    assert "downloads_per_day" in data
    assert "downloads_per_day_type_status" in data
    assert "file_size_stats_per_type" in data
    assert "download_time_stats_per_type" in data
    assert "total_downloads" in data
