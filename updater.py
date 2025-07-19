import time
import httpx
import json
import threading
from logger import get_download_logger, get_error_logger
from database import log_download

class ModelUpdater(threading.Thread):
    def __init__(self, manifest_path, interval=86400):
        super().__init__(daemon=True)
        self.manifest_path = manifest_path
        self.interval = interval  # seconds (default: 1 dag)
        self.running = True
        self.logger = get_download_logger()
        self.err_logger = get_error_logger()

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
                # Vergelijk SHA of updatedAt
                remote_sha = data.get('sha256')
                remote_updated = data.get('updatedAt')
                if remote_sha and remote_sha != entry.get('sha256'):
                    self.logger.info(f"Model {model_id} update detected (SHA mismatch)")
                    # Hier: voeg aan download queue toe of trigger webhook
                elif remote_updated and remote_updated != entry.get('updatedAt'):
                    self.logger.info(f"Model {model_id} update detected (updatedAt mismatch)")
                    # Hier: voeg aan download queue toe of trigger webhook
            except Exception as e:
                self.err_logger.error(f"Update check failed for {model_id}: {e}")

    def stop(self):
        self.running = False

# Example usage:
# updater = ModelUpdater('manifest.json', interval=3600)
# updater.start()
