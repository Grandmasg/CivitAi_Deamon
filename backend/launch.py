# launch.py

import json
import os
import random
import socket
import sys
import subprocess
from loguru import logger

# --- Loguru file logging setup ---
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
# Fix: als logs een bestand is, verwijder het en maak een map
if os.path.exists(log_dir) and not os.path.isdir(log_dir):
    os.remove(log_dir)
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)
# Main daemon log
daemon_log_path = os.path.join(log_dir, "daemon.log")
# Forceer aanmaken van daemon.log, ongeacht OS of loguru-filter
with open(daemon_log_path, "a", encoding="utf-8") as f:
    pass
logger.add(daemon_log_path, rotation="5 MB", retention=5, encoding="utf-8", filter=lambda record: record["extra"].get("name", "") in ("civitai.download", "civitai.api"))
# Updater log
logger.add(os.path.join(log_dir, "update.log"), rotation="2 MB", retention=5, encoding="utf-8", filter=lambda record: record["extra"].get("name", "") == "civitai.updater")

CONFIG_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))


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
        logger.info("[launch.py] Not running in venv, restarting in .venv...")
        os.execv(venv_python, [venv_python] + sys.argv)

    try:
        cfg = load_config()
        port = cfg.get('active_port_back')
        if not port:
            logger.error("No active_port_back set in config.json. Run install.py first.")
            raise RuntimeError("No active_port_back set in config.json. Run install.py first.")
        logger.info(f"[launch.py] Using configured backend port: {port}")

        # Start webhook server (background)
        logger.info(f"[launch.py] Starting webhook_server.py in background...")
        webhook_cmd = f".venv/bin/python backend/webhook_server.py"
        webhook_proc = subprocess.Popen(webhook_cmd, shell=True)

        # Start uvicorn (main process)
        logger.info(f"[launch.py] Starting uvicorn on port {port}...")
        cmd = f".venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port {port} --reload"
        try:
            subprocess.run(cmd, shell=True)
        finally:
            logger.info("[launch.py] Stopping webhook server...")
            webhook_proc.terminate()
            webhook_proc.wait()
    except Exception as e:
        logger.error(f"[launch.py] Exception: {e}")
        raise

if __name__ == "__main__":
    main()
