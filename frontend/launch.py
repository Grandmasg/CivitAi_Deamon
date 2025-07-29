# launch.py
import json
import os
import sys
import subprocess
from loguru import logger

# --- Loguru file logging setup ---
log_dir = os.path.join(os.path.dirname(__file__), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
# Frontend log
logger.add(os.path.join(log_dir, "frontend.log"), rotation="5 MB", retention=5, encoding="utf-8", filter=lambda record: record["extra"].get("name", "") == "civitai.frontend")

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
        port = cfg.get('active_port_front')
        if not port:
            logger.error("No active_port_front set in config.json. Run install.py first.")
            raise RuntimeError("No active_port_front set in config.json. Run install.py first.")
        logger.info(f"[launch.py] Using configured frontend port: {port}")

        # Start uvicorn (main process) with reload and extra watch dirs
        frontend_dir = os.path.dirname(__file__)
        extra_watch_dirs = [
            os.path.join(frontend_dir, 'templates'),
            os.path.join(frontend_dir, 'static'),
            frontend_dir,  # Watch the whole frontend dir (including main.py etc)
        ]
        reload_dirs = ' '.join([f'--reload-dir {d}' for d in extra_watch_dirs])
        logger.info(f"[launch.py] Starting uvicorn on port {port} with reload and extra watch dirs: {extra_watch_dirs}")
        cmd = f".venv/bin/uvicorn frontend.main:app --host 0.0.0.0 --port {port} --reload {reload_dirs}"
        subprocess.run(cmd, shell=True)
    except Exception as e:
        logger.error(f"[launch.py] Exception: {e}")
        raise

if __name__ == "__main__":
    main()
