# launch.py
import json
import os
import random
import socket
import sys
import subprocess

CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


def load_config():
    with open(CONFIG_PATH, 'r') as f:
        return json.load(f)

def save_config(cfg):
    with open(CONFIG_PATH, 'w') as f:
        json.dump(cfg, f, indent=2)


def in_venv():
    return (
        hasattr(sys, 'real_prefix') or
        (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix)
    )

def main():
    # Check if running in venv, else restart in venv
    venv_python = os.path.join(os.path.dirname(__file__), '.venv', 'bin', 'python')
    if not in_venv() and os.path.exists(venv_python):
        print("[launch.py] Not running in venv, restarting in .venv...")
        os.execv(venv_python, [venv_python] + sys.argv)


    cfg = load_config()
    port = cfg.get('active_port')
    if not port:
        raise RuntimeError("No active_port set in config.json. Run install.py first.")
    print(f"[launch.py] Using configured port: {port}")


    # Start webhook server (background)
    print(f"[launch.py] Starting webhook_server.py in background...")
    webhook_cmd = f".venv/bin/python webhook_server.py"
    webhook_proc = subprocess.Popen(webhook_cmd, shell=True)

    # Start uvicorn (main process)
    print(f"[launch.py] Starting uvicorn on port {port}...")
    cmd = f".venv/bin/uvicorn main:app --host 0.0.0.0 --port {port}"
    try:
        subprocess.run(cmd, shell=True)
    finally:
        print("[launch.py] Stopping webhook server...")
        webhook_proc.terminate()
        webhook_proc.wait()

if __name__ == "__main__":
    main()
