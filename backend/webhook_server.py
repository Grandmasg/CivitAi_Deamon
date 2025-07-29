
# --- Standaard imports altijd eerst ---
import os
import json
import signal
import socket
import subprocess
import sys
from fastapi import FastAPI, Request
import uvicorn
from loguru import logger

# --- Loguru file logging setup (ook als webhook_server direct wordt geladen) ---
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(log_dir, exist_ok=True)
# Verwijder alle bestaande handlers om dubbele logging te voorkomen
logger.remove()
logger.add(os.path.join(log_dir, "daemon.log"), rotation="5 MB", retention=5, encoding="utf-8", filter=lambda record: record["extra"].get("name", "") in ("civitai.download", "civitai.api"))

# Bind logger for webhook logging
log = logger.bind(name="civitai.api")

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))
WEBHOOK_PATH = '/webhook'


app = FastAPI()

# Log every request via middleware (universeel, net als in main.py)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
class LogRequestsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        log.info(f"Request: {request.method} {request.url.path}")
        response = await call_next(request)
        log.info(f"Response: {request.method} {request.url.path} {response.status_code}")
        return response
app.add_middleware(LogRequestsMiddleware)

@app.post(WEBHOOK_PATH)
async def webhook_endpoint(request: Request):
    data = await request.json()
    print(f"[webhook_server] Received webhook: {data}")
    return {"status": "ok"}

def get_webhook_port():
    with open(CONFIG_PATH, 'r') as f:
        cfg = json.load(f)
    url = cfg.get('webhook_url', '')
    try:
        port = int(url.split(':')[2].split('/')[0])
        return port
    except Exception:
        raise RuntimeError("No valid webhook port found in config.json")

def find_process_on_port(port):
    # Only works on Linux with lsof
    try:
        result = subprocess.check_output(["lsof", "-t", f"-i:{port}"]).decode().strip()
        pids = [int(pid) for pid in result.split('\n') if pid]
        return pids
    except Exception:
        return []

def kill_processes(pids):
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"[webhook_server] Killed process {pid} on port.")
        except Exception as e:
            print(f"[webhook_server] Could not kill process {pid}: {e}")

def main():
    port = get_webhook_port()
    print(f"[webhook_server] Starting on port {port}...")
    try:
        uvicorn.run("webhook_server:app", host="0.0.0.0", port=port, reload=False)
    except Exception as e:
        if "address already in use" in str(e).lower():
            print(f"[webhook_server] Port {port} in use, attempting to stop existing service...")
            pids = find_process_on_port(port)
            if pids:
                kill_processes(pids)
                print(f"[webhook_server] Restarting on port {port}...")
                uvicorn.run("webhook_server:app", host="0.0.0.0", port=port, reload=False)
            else:
                print(f"[webhook_server] No process found on port {port}, cannot free port.")
                sys.exit(1)
        else:
            raise

if __name__ == "__main__":
    main()
