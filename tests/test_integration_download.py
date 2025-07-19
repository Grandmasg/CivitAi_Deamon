
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from fastapi.testclient import TestClient

import importlib
main = importlib.import_module("main")
app = main.app
get_current_user = main.get_current_user
import tempfile
import os

app.dependency_overrides[get_current_user] = lambda: {"user": "test", "role": "admin"}
client = TestClient(app)

def test_full_download_flow(monkeypatch):
    # Use a temp dir for downloads
    from daemon import DownloadDaemon
    temp_dir = tempfile.mkdtemp()
    daemon = DownloadDaemon(download_dir=temp_dir, throttle=0)
    # Patch daemon_instance in main to use our test daemon
    import main
    main.daemon_instance = daemon
    # Patch _download_file to simulate success
    daemon._download_file = lambda item: True
    # Init DB for test
    from database import init_db
    init_db()
    # Add a job via API
    job = {"model_id": "testid", "url": "http://example.com/file", "filename": "file.txt"}
    resp = client.post("/api/download", json=job, headers={"Authorization": "Bearer testtoken"})
    assert resp.status_code == 200
    # Process the job
    item = daemon.queue.get_nowait()[2]
    result = daemon.process_item(item)
    assert result is True
    # Clean up
    try:
        os.remove(os.path.join(temp_dir, "file.txt"))
        os.rmdir(temp_dir)
    except Exception:
        pass
