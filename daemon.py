import threading
import queue
import hashlib
import httpx
import os
import json
import time
from logger import get_download_logger, get_error_logger
from database import log_download, log_error

# --- Webhook sender (module-level, for test patching) ---
def send_webhook(event, data):

    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if not os.path.exists(config_path):
            return
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        url = config.get('webhook_url')
        if not url:
            return
        payload = {'event': event, 'data': data}
        httpx.post(url, json=payload, timeout=5)
    except Exception:
        pass

# WebSocket broadcast placeholder (to be integrated with FastAPI app)
class WebSocketManager:
    def __init__(self):
        self.connections = set()
    def broadcast(self, event, data):
        # In main.py: call ws_manager.broadcast(event, data) to all clients
        pass
ws_manager = WebSocketManager()

# Download queue item structure
def make_queue_item(model_id, url, filename, sha256=None, priority=0, model_type=None, model_version_id=None):
    return {
        'model_id': model_id,
        'url': url,
        'filename': filename,
        'sha256': sha256,
        'priority': priority,
        'retries': 0,
        'model_type': model_type or 'other',
        'model_version_id': model_version_id
    }

class DownloadDaemon(threading.Thread):
    def __init__(self, max_retries=5, download_dir='', throttle=0, timeout=60.0):
        super().__init__(daemon=True)
        self.queue = queue.PriorityQueue()
        self.max_retries = max_retries
        self.download_dir = download_dir
        self.throttle = throttle  # seconds between downloads
        self.timeout = timeout    # per download
        self.running = True
        self.paused = False
        self.cancel_current = False
        self.logger = get_download_logger()
        self.err_logger = get_error_logger()
    def pause(self):
        self.paused = True
        ws_manager.broadcast('daemon_paused', {})

    def resume(self):
        self.paused = False
        ws_manager.broadcast('daemon_resumed', {})

    def cancel(self):
        self.cancel_current = True
        ws_manager.broadcast('download_cancel_requested', {})
        self.logger = get_download_logger()
        self.err_logger = get_error_logger()

    def add_job(self, item):
        # Lower priority value = higher priority
        self.queue.put((item['priority'], time.time(), item))
        ws_manager.broadcast('queue_update', {'queued': self.queue.qsize()})

    def run(self):
        while self.running:
            if self.paused:
                time.sleep(0.5)
                continue
            try:
                _, _, item = self.queue.get(timeout=1)
            except queue.Empty:
                continue
            self.process_item(item)

    def send_webhook(event, data):
        try:
            config_path = os.path.join(os.path.dirname(__file__), 'config.json')
            if not os.path.exists(config_path):
                return
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            url = config.get('webhook_url')
            if not url:
                return
            payload = {'event': event, 'data': data}
            httpx.post(url, json=payload, timeout=5)
        except Exception:
            pass

    def process_item(self, item):
        ws_manager.broadcast('download_start', {'model_id': item['model_id'], 'filename': item['filename']})
        send_webhook('download_start', {'model_id': item['model_id'], 'filename': item['filename']})
        for attempt in range(self.max_retries):
            try:
                self.cancel_current = False
                t0 = time.time()
                success, filepath = self._download_file(item)
                t1 = time.time()
                download_time = round(t1 - t0, 3)
                file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                if success:
                    if item.get('sha256'):
                        ws_manager.broadcast('hash_start', {'filename': item['filename']})
                        # Custom SHA256 mismatch logging
                        actual_hash = None
                        hash_mismatch = False
                        with open(filepath, 'rb') as f:
                            sha256 = hashlib.sha256()
                            while True:
                                chunk = f.read(1024*1024)
                                if not chunk:
                                    break
                                sha256.update(chunk)
                            actual_hash = sha256.hexdigest().lower()
                        expected_hash = str(item['sha256']).lower()
                        if actual_hash != expected_hash:
                            hash_mismatch = True
                            msg = (f"SHA256 mismatch for {item['filename']}\n"
                                   f"Expected: {expected_hash}\n"
                                   f"Actual:   {actual_hash}")
                            self.err_logger.error(msg)
                            log_error(item['model_id'], item['filename'], msg)
                            raise ValueError('SHA256 mismatch')
                    log_download(
                        item['model_id'],
                        item.get('model_version_id'),
                        item['filename'],
                        f'success',
                        message=f'success ({file_size} bytes, UA=CivitaiDaemon)',
                        model_type=item.get('model_type'),
                        file_size=file_size,
                        download_time=download_time
                    )
                    ws_manager.broadcast('download_finished', {
                        'model_id': item['model_id'],
                        'filename': item['filename'],
                        'file_size': file_size,
                        'download_time': download_time
                    })
                    send_webhook('download_finished', {
                        'model_id': item['model_id'],
                        'filename': item['filename'],
                        'file_size': file_size,
                        'download_time': download_time
                    })
                    if self.throttle > 0:
                        time.sleep(self.throttle)
                    return True
                else:
                    # Log fail/cancel met juiste status
                    log_download(
                        item['model_id'],
                        item.get('model_version_id'),
                        item['filename'],
                        'failed',
                        message='Download failed',
                        model_type=item.get('model_type'),
                        file_size=file_size,
                        download_time=download_time
                    )
                    raise Exception('Download failed')
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                self.err_logger.error(f"Download failed: {item['filename']} (url: {item.get('url')}) ({e})\nTraceback:\n{tb}")
                log_error(item['model_id'], item['filename'], f"{e}\nURL: {item.get('url')}\nTraceback:\n{tb}")
                ws_manager.broadcast('download_error', {'model_id': item['model_id'], 'filename': item['filename'], 'error': str(e)})
                send_webhook('download_error', {'model_id': item['model_id'], 'filename': item['filename'], 'error': str(e)})
                # Cleanup incomplete file
                filepath = os.path.join(self.download_dir, item['filename'])
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception:
                        pass
                item['retries'] += 1
                if item['retries'] < self.max_retries:
                    time.sleep(2)
                else:
                    self.err_logger.error(f"Max retries reached for: {item['filename']}")
                    ws_manager.broadcast('download_failed', {
                        'model_id': item['model_id'],
                        'filename': item['filename'],
                        'error': f'Max retries ({self.max_retries}) reached.'
                    })
                    send_webhook('download_failed', {
                        'model_id': item['model_id'],
                        'filename': item['filename'],
                        'error': f'Max retries ({self.max_retries}) reached.'
                    })
                    return False

    def _download_file(self, item):
        """Download logic, returns (True, filepath) on success, (False, filepath) on failure/cancel."""
        self.logger.info(f"Start download: {item['filename']}")
        model_type = item.get('model_type', 'other')
        subdir = os.path.join('data', 'models', model_type)
        os.makedirs(subdir, exist_ok=True)
        filepath = os.path.join(subdir, item['filename'])
        # Cleanup incomplete file if exists
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception:
                pass
        # Add Civitai API key if present
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        api_key = None
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                api_key = config.get('civitai_api_key')
        headers = {'User-Agent': f'CivitaiDaemon/1.0 (Python httpx)'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        try:
            with httpx.stream('GET', item['url'], timeout=self.timeout, headers=headers, follow_redirects=True) as r:
                try:
                    r.raise_for_status()
                except httpx.HTTPStatusError as http_err:
                    # Log statuscode, response body en redirect chain
                    body = r.read().decode(errors='replace') if hasattr(r, 'read') else ''
                    redirects = []
                    if hasattr(r, 'history') and r.history:
                        for resp in r.history:
                            redirects.append(f"{resp.status_code} -> {resp.headers.get('location', '')}")
                    redirect_info = f" Redirect chain: {' | '.join(redirects)}" if redirects else ''
                    self.err_logger.error(f"HTTP error {r.status_code} for {item['url']}: {body}{redirect_info}")
                    return False, filepath
                total = int(r.headers.get('content-length', 0))
                downloaded = 0
                with open(filepath, 'wb') as f:
                    for chunk in r.iter_bytes():
                        if self.cancel_current:
                            ws_manager.broadcast('download_cancelled', {'model_id': item['model_id'], 'filename': item['filename']})
                            send_webhook('download_cancelled', {'model_id': item['model_id'], 'filename': item['filename']})
                            if os.path.exists(filepath):
                                try:
                                    os.remove(filepath)
                                except Exception:
                                    pass
                            return False, filepath
                        while self.paused:
                            time.sleep(0.2)
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            progress = int(100 * downloaded / total)
                            ws_manager.broadcast('download_progress', {
                                'model_id': item['model_id'],
                                'filename': item['filename'],
                                'progress': progress,
                                'downloaded': downloaded,
                                'total': total
                            })
                        else:
                            ws_manager.broadcast('download_progress', {
                                'model_id': item['model_id'],
                                'filename': item['filename'],
                                'progress': None,
                                'downloaded': downloaded,
                                'total': None
                            })
            return True, filepath
        except Exception as e:
            self.err_logger.error(f"Exception during download for {item.get('url')}: {e}")
            return False, filepath

    def verify_hash(self, filepath, expected_sha256):
        ws_manager.broadcast('hash_progress', {'filename': os.path.basename(filepath), 'progress': 0})
        sha256 = hashlib.sha256()
        total = os.path.getsize(filepath)
        with open(filepath, 'rb') as f:
            read = 0
            while True:
                chunk = f.read(1024*1024)
                if not chunk:
                    break
                sha256.update(chunk)
                read += len(chunk)
                ws_manager.broadcast('hash_progress', {'filename': os.path.basename(filepath), 'progress': int(100*read/total)})
        # Compare hashes in lowercase to avoid case sensitivity issues
        result = sha256.hexdigest().lower() == str(expected_sha256).lower()
        ws_manager.broadcast('hash_progress', {'filename': os.path.basename(filepath), 'progress': 100})
        return result

    def stop(self):
        self.running = False

# Manifest batch processing
def process_manifest(manifest_path, daemon):
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    for entry in manifest:
        item = make_queue_item(
            model_id=entry.get('modelId'),
            url=entry.get('url'),
            filename=entry.get('filename'),
            sha256=entry.get('sha256'),
            priority=entry.get('priority', 0),
            model_type=entry.get('model_type'),
            model_version_id=entry.get('modelVersionId')
        )
        daemon.add_job(item)
    ws_manager.broadcast('batch_queued', {'count': len(manifest)})

# Example usage:
# daemon = DownloadDaemon()
# daemon.start()
# process_manifest('manifest.json', daemon)
# daemon.add_job(make_queue_item(...))
