# install.py
import os
import subprocess
import sys

def run(cmd, check=True):
    print(f"[install.py] $ {cmd}")
    result = subprocess.run(cmd, shell=True)
    if check and result.returncode != 0:
        print(f"[install.py] Command failed: {cmd}")
        sys.exit(result.returncode)

def ensure_uv():
    try:
        import uv
    except ImportError:
        print("[install.py] 'uv' not found, installing via pip...")
        run(f"{sys.executable} -m pip install uv")


def is_port_free(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

def pick_free_webhook_port():
    import random
    WEBHOOK_PORT_RANGE = list(range(9000, 9101))
    random.shuffle(WEBHOOK_PORT_RANGE)
    for port in WEBHOOK_PORT_RANGE:
        if is_port_free(port):
            return port
    raise RuntimeError("No free webhook port found in range 9000-9100")

def update_webhook_url():
    import json
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')
    WEBHOOK_PATH = '/webhook'
    with open(CONFIG_PATH, 'r') as f:
        cfg = json.load(f)
    url = cfg.get('webhook_url', '')
    port_in_url = None
    try:
        port_in_url = int(url.split(':')[2].split('/')[0])
    except Exception:
        pass
    if not port_in_url or not is_port_free(port_in_url):
        port = pick_free_webhook_port()
        cfg['webhook_url'] = f"http://localhost:{port}{WEBHOOK_PATH}"
        with open(CONFIG_PATH, 'w') as f:
            json.dump(cfg, f, indent=2)
        print(f"[install.py] Picked free webhook port: {port}")
    else:
        print(f"[install.py] Using configured webhook port: {port_in_url}")

def main():
    ensure_uv()
    if not os.path.isdir('.venv'):
        print("[install.py] Creating venv with uv...")
        run("uv venv .venv")
    else:
        print("[install.py] .venv already exists.")
    print("[install.py] Installing dependencies with uv pip...")
    run(".venv/bin/uv pip install fastapi uvicorn[standard] httpx jinja2 sqlite-utils python-multipart apscheduler")
    update_webhook_url()
    print("[install.py] Done. Activate with: source .venv/bin/activate")

if __name__ == "__main__":
    main()
