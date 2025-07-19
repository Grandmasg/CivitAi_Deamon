
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import pytest
from fastapi.testclient import TestClient

import importlib
main = importlib.import_module("main")
app = main.app
import json

client = TestClient(app)

def test_websocket_downloads():
    # Get a valid JWT token for the websocket
    response = client.post("/token", json={"username": "wsuser", "role": "user"})
    assert response.status_code == 200
    token = response.json()["access_token"]
    ws_url = f"/ws/downloads?token={token}"
    with client.websocket_connect(ws_url) as websocket:
        # Send a message and expect an echo
        websocket.send_text("hello")
        data = websocket.receive_text()
        assert "Echo: hello" in data
