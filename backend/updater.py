
# --- Standaard imports altijd eerst ---
import os
import time
import httpx
import json
import threading
from loguru import logger

# --- Loguru file logging setup (ook als updater direct wordt geladen) ---
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(log_dir, exist_ok=True)
if not any([h._name == 'update.log' for h in logger._core.handlers.values()]):
    logger.add(os.path.join(log_dir, "update.log"), rotation="2 MB", retention=5, encoding="utf-8", filter=lambda record: record["extra"].get("name", "") == "civitai.updater")

class ModelUpdater(threading.Thread):
    def __init__(self, manifest_path, interval=86400):
        super().__init__(daemon=True)
        self.manifest_path = manifest_path
        self.interval = interval  # seconds (default: 1 day)
        self.running = True
        self.logger = logger.bind(name="civitai.updater")
        self.err_logger = logger.bind(name="civitai.updater")

    def run(self):
        while self.running:
            try:
                self.check_updates()
            except Exception as e:
                self.err_logger.error(f"Updater error: {e}")
            time.sleep(self.interval)

    def check_updates(self):
        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        for entry in manifest:
            model_id = entry.get('modelId')
            url = f'https://civitai.com/api/v1/models/{model_id}'
            try:
                resp = httpx.get(url, timeout=10)
                resp.raise_for_status()
                data = resp.json()
                # Compare SHA or updatedAt
                remote_sha = data.get('sha256')
                remote_updated = data.get('updatedAt')
                if remote_sha and remote_sha != entry.get('sha256'):
                    self.logger.info(f"Model {model_id} update detected (SHA mismatch)")
                    # Here: add to download queue or trigger webhook
                elif remote_updated and remote_updated != entry.get('updatedAt'):
                    self.logger.info(f"Model {model_id} update detected (updatedAt mismatch)")
                    # Here: add to download queue or trigger webhook
            except Exception as e:
                self.err_logger.error(f"Update check failed for {model_id}: {e}")

    def stop(self):
        self.running = False

# Example usage:
# updater = ModelUpdater('manifest.json', interval=3600)
# updater.start()
