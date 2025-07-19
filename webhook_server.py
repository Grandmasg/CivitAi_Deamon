import json
import os
import signal
import socket
import subprocess
import sys
from fastapi import FastAPI, Request
import uvicorn

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
WEBHOOK_PATH = '/webhook'

app = FastAPI()

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
