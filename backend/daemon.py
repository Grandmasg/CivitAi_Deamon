import threading
import queue
import hashlib
import httpx
import os
import json
import time
from loguru import logger
daemon_logger = logger.bind(name="civitai.download")
from backend.database import log_download, log_error

# --- Webhook sender (module-level, for test patching) ---
def send_webhook(event, data):

    try:
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))
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

import threading
import asyncio
class WebSocketManager:
    def __init__(self):
        self.connections = set()
        self.lock = threading.Lock()
        self.loop = None  # To be set from FastAPI app

    def set_loop(self, loop):
        self.loop = loop

    def add(self, ws):
        with self.lock:
            self.connections.add(ws)
        print(f"[WebSocketManager] Added connection: {ws}")

    def remove(self, ws):
        with self.lock:
            self.connections.discard(ws)
        print(f"[WebSocketManager] Removed connection: {ws}")

    async def abroadcast(self, event, data):
        import json
        msg = json.dumps({"event": event, "data": data})
        # print(f"[WebSocketManager.abroadcast] {msg}")  # Debug log verwijderd
        to_remove = []
        with self.lock:
            connections = list(self.connections)
        for ws in connections:
            try:
                await ws.send_text(msg)
            except Exception as e:
                print(f"[WebSocketManager] Failed to send to {ws}: {e}")
                to_remove.append(ws)
        for ws in to_remove:
            self.remove(ws)

    def broadcast(self, event, data):
        # Thread-safe: schedule abroadcast on the event loop
        if self.loop is None:
            print("[WebSocketManager] No event loop set for broadcast!")
            return
        coro = self.abroadcast(event, data)
        asyncio.run_coroutine_threadsafe(coro, self.loop)

ws_manager = WebSocketManager()

# Download queue item structure
def make_queue_item(model_id, url, filename, sha256=None, priority=None, model_type=None, model_version_id=None, base_model=None):
    # Default priority is 2 if not set, so explicit 0 or 1 are always higher priority
    if priority is None:
        priority = 2
    return {
        'model_id': model_id,
        'url': url,
        'filename': filename,
        'sha256': sha256,
        'priority': priority,
        'retries': 0,
        'model_type': model_type or 'other',
        'model_version_id': model_version_id,
        'base_model': base_model
    }

from backend.database import is_already_downloaded

class DownloadDaemon(threading.Thread):
    def __init__(self, max_retries=None, download_dir=None, throttle=None, timeout=None, workers=None):
        super().__init__(daemon=True)
        # Load config values if not provided
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))
        config = {}
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                try:
                    config = json.load(f)
                except Exception:
                    config = {}
        # Use config values or fallback to defaults
        self.max_retries = max_retries if max_retries is not None else int(config.get('retries', 5))
        self.throttle = throttle if throttle is not None else int(config.get('throttle', 0))
        self.workers = workers if workers is not None else int(config.get('workers', 1))
        self.download_dir = download_dir if download_dir is not None else config.get('download_dir', '')
        self.timeout = timeout if timeout is not None else float(config.get('timeout', 60.0))
        self.queue = queue.PriorityQueue()
        self.running = True
        self.paused = False
        self.cancel_current = False
        self.logger = daemon_logger
        self.err_logger = daemon_logger
        # self._logged_downloads = set()  # Suppress duplicate log_download calls per (model_id, filename, status) -- redundant, suppressie nu via database
        # Note: self.workers is not yet used; for future multi-threaded support
        # TODO: log_level dynamisch uit config halen en logging aanpassen
        self.active_downloads = []  # Lijst van actieve downloads
        self.last_downloaded = self._load_last_downloaded()
        self.all_downloaded = self._load_all_downloaded()
        self.current_job = None  # Track the currently processing job

    def _load_last_downloaded(self):
        # Haal laatste 5 downloads uit database
        import sqlite3
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'completed.db'))
        if not os.path.exists(db_path):
            return []
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''SELECT model_id, model_version_id, filename, file_size, download_time, model_type, base_model FROM downloads WHERE status="success" ORDER BY timestamp DESC LIMIT 5''')
        rows = c.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                'model_id': row[0],
                'model_version_id': row[1],
                'filename': row[2],
                'file_size': row[3],
                'download_time': row[4],
                'model_type': row[5],
                'base_model': row[6]
            })
        return result
    def _load_all_downloaded(self):
        # Haal alle succesvolle downloads uit database
        import sqlite3
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'completed.db'))
        if not os.path.exists(db_path):
            return []
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''SELECT model_id, model_version_id, filename, file_size, download_time, model_type, base_model FROM downloads WHERE status="success" ORDER BY timestamp DESC''')
        rows = c.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                'model_id': row[0],
                'model_version_id': row[1],
                'filename': row[2],
                'file_size': row[3],
                'download_time': row[4],
                'model_type': row[5],
                'base_model': row[6]
            })
        return result
    def pause(self):
        self.paused = True
        self.logger.info("Daemon paused")
        ws_manager.broadcast('daemon_paused', {})
        send_webhook('daemon_paused', {})
        log_download('system', None, '-', 'paused', message='Daemon paused')

    def resume(self):
        self.paused = False
        self.logger.info("Daemon resumed")
        ws_manager.broadcast('daemon_resumed', {})
        send_webhook('daemon_resumed', {})
        log_download('system', None, '-', 'resumed', message='Daemon resumed')

    def cancel(self):
        self.cancel_current = True
        self.logger.info("Download cancel requested")
        ws_manager.broadcast('download_cancel_requested', {})
        send_webhook('download_cancel_requested', {})
        log_download('system', None, '-', 'cancel_requested', message='Download cancel requested')
        self.logger = logger.bind(name="civitai.download")
        self.err_logger = logger.bind(name="civitai.error")


    def add_job(self, item, skipped=False, reason=None):
        # Universele skip-detectie: check altijd of al gedownload
        if not skipped and is_already_downloaded(item.get('model_id'), item.get('model_version_id')):
            skipped = True
            reason = "already downloaded"
        if skipped:
            msg = f"Download skipped: {item['filename']} (model_id={item['model_id']})"
            if reason:
                msg += f" | Reason: {reason}"
            self.logger.info(msg)
            ws_manager.broadcast('download_skipped', {'model_id': item['model_id'], 'filename': item['filename'], 'reason': reason})
            send_webhook('download_skipped', {'model_id': item['model_id'], 'filename': item['filename'], 'reason': reason})
            log_download(
                item['model_id'],
                item.get('model_version_id'),
                item['filename'],
                'skipped',
                message=reason or 'skipped',
                model_type=item.get('model_type'),
                file_size=0,
                download_time=0,
                base_model=item.get('base_model')
            )
            return
        self.queue.put((item['priority'], time.time(), item))
        # Stuur direct een 'in_queue' event per model
        ws_manager.broadcast('in_queue', {'model_id': item['model_id'], 'filename': item['filename']})
        ws_manager.broadcast('queue_update', {'queued': self.queue.qsize()})

    def run(self):
        self.logger.info("Daemon thread started")
        send_webhook('daemon_started', {})
        queue_was_empty = False
        try:
            while self.running:
                if self.paused:
                    time.sleep(0.5)
                    continue
                try:
                    # Remove and get the first item from the queue (active job is NOT in the queue)
                    priority, ts, item = self.queue.get(timeout=1)
                    if queue_was_empty:
                        queue_was_empty = False
                except queue.Empty:
                    if not queue_was_empty:
                        self.logger.info("Queue is empty, waiting for new jobs...")
                        queue_was_empty = True
                    ws_manager.broadcast('queue_empty', {})
                    self.current_job = None
                    time.sleep(1)
                    continue
                try:
                    self.current_job = item
                    self.process_item(item)
                    self.current_job = None
                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    self.err_logger.error(f"Exception in process_item: {e}\n{tb}")
                    log_error(item.get('model_id', 'unknown'), item.get('filename', '-'), f"Exception in process_item: {e}\n{tb}")
                    ws_manager.broadcast('process_item_error', {'model_id': item.get('model_id'), 'filename': item.get('filename'), 'error': str(e)})
                    send_webhook('process_item_error', {'model_id': item.get('model_id'), 'filename': item.get('filename'), 'error': str(e)})
                    self.current_job = None
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.err_logger.error(f"Daemon thread crashed: {e}\n{tb}")
            log_error('system', '-', f"Daemon thread crashed: {e}\n{tb}")
            send_webhook('daemon_crashed', {'error': str(e)})
        finally:
            self.current_job = None
            self.logger.warning("Daemon thread stopped")
            send_webhook('daemon_stopped', {})
            # log_download('system', None, '-', 'stopped', message='Daemon thread stopped')

    def send_webhook(event, data):
        try:
            config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))
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
        self.logger.info(f"Starting download: {item['filename']} (model_id={item['model_id']}, url={item.get('url')})")
        ws_manager.broadcast('download_start', {'model_id': item['model_id'], 'filename': item['filename']})
        send_webhook('download_start', {'model_id': item['model_id'], 'filename': item['filename']})
        # Voeg toe aan actieve downloads
        self.active_downloads.append(item)
        try:
            for attempt in range(self.max_retries):
                try:
                    self.logger.info(f"Attempt {attempt+1}/{self.max_retries} for {item['filename']}")
                    self.cancel_current = False
                    t0 = time.time()
                    success, filepath = self._download_file(item)
                    t1 = time.time()
                    download_time = round(t1 - t0, 3)
                    file_size = os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    if success:
                        self.logger.success(f"Download finished: {item['filename']} ({file_size} bytes, {download_time}s)")
                        if item.get('sha256'):
                            ws_manager.broadcast('hash_start', {
                                'filename': item['filename'],
                                'model_id': item['model_id'],
                                'model_version_id': item.get('model_version_id')
                            })
                            self.logger.info(f"Verifying SHA256 for {item['filename']}")
                            expected_hash = str(item['sha256']).lower()
                            result = self.verify_hash(filepath, expected_hash, item.get('model_id'), item.get('model_version_id'))
                            actual_hash = None
                            with open(filepath, 'rb') as f:
                                sha256 = hashlib.sha256()
                                while True:
                                    chunk = f.read(1024*1024)
                                    if not chunk:
                                        break
                                    sha256.update(chunk)
                                actual_hash = sha256.hexdigest().lower()
                            if not result:
                                msg = (f"SHA256 mismatch for {item['filename']}\n"
                                       f"Expected: {expected_hash}\n"
                                       f"Actual:   {actual_hash}")
                                self.err_logger.error(msg)
                                log_error(item['model_id'], item['filename'], msg)
                                raise ValueError('SHA256 mismatch')
                            else:
                                self.logger.success(f"SHA256 verified for {item['filename']}")
                                ws_manager.broadcast('hash_finished', {
                                    'filename': item['filename'],
                                    'model_id': item['model_id'],
                                    'model_version_id': item.get('model_version_id'),
                                    'sha256': actual_hash
                                })
                        log_download(
                            item['model_id'],
                            item.get('model_version_id'),
                            item['filename'],
                            f'success',
                            message=f'success ({file_size} bytes, UA=CivitaiDaemon)',
                            model_type=item.get('model_type'),
                            file_size=file_size,
                            download_time=download_time,
                            base_model=item.get('base_model')
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
                        # Voeg toe aan laatste downloads (max 5)
                        self.last_downloaded.insert(0, {
                            'model_id': item['model_id'],
                            'filename': item['filename'],
                            'file_size': file_size,
                            'download_time': download_time,
                            'model_type': item.get('model_type'),
                            'model_version_id': item.get('model_version_id'),
                            'base_model': item.get('base_model')
                        })
                        if len(self.last_downloaded) > 5:
                            self.last_downloaded = self.last_downloaded[:5]
                        # Voeg toe aan all_downloaded
                        self.all_downloaded.insert(0, {
                            'model_id': item['model_id'],
                            'model_version_id': item.get('model_version_id'),
                            'filename': item['filename'],
                            'file_size': file_size,
                            'download_time': download_time,
                            'model_type': item.get('model_type'),
                            'base_model': item.get('base_model')
                        })
                        return True
                    else:
                        self.err_logger.warning(f"Download failed for {item['filename']} (no exception, returned False)")
                        log_download(
                            item['model_id'],
                            item.get('model_version_id'),
                            item['filename'],
                            'failed',
                            message='Download failed',
                            model_type=item.get('model_type'),
                            file_size=file_size,
                            download_time=download_time,
                            base_model=item.get('base_model')
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
                            self.logger.info(f"Removed incomplete file: {filepath}")
                        except Exception as cleanup_err:
                            self.err_logger.warning(f"Failed to remove incomplete file {filepath}: {cleanup_err}")
                    item['retries'] += 1
                    if item['retries'] < self.max_retries:
                        self.logger.warning(f"Retrying {item['filename']} (retry {item['retries']}/{self.max_retries}) after 2s...")
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
        finally:
            # Verwijder uit actieve downloads
            if item in self.active_downloads:
                self.active_downloads.remove(item)

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
        config_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'configs', 'config.json'))
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
                last_progress_sent = 0
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
                        now = time.time()
                        # Only send progress every 0.2s, but always send 100% at the end
                        if total > 0:
                            progress = round(100 * downloaded / total, 1)
                            if (now - last_progress_sent > 0.2) or (downloaded == total):
                                ws_manager.broadcast('download_progress', {
                                    'model_id': item['model_id'],
                                    'filename': item['filename'],
                                    'progress': progress,
                                    'downloaded': downloaded,
                                    'total': total
                                })
                                last_progress_sent = now
                        else:
                            if (now - last_progress_sent > 0.2):
                                ws_manager.broadcast('download_progress', {
                                    'model_id': item['model_id'],
                                    'filename': item['filename'],
                                    'progress': None,
                                    'downloaded': downloaded,
                                    'total': None
                                })
                                last_progress_sent = now
                # Always send 100% at the end if not already sent
                if total > 0 and downloaded == total:
                    ws_manager.broadcast('download_progress', {
                        'model_id': item['model_id'],
                        'filename': item['filename'],
                        'progress': 100,
                        'downloaded': downloaded,
                        'total': total
                    })
            return True, filepath
        except Exception as e:
            self.err_logger.error(f"Exception during download for {item.get('url')}: {e}")
            return False, filepath

    def verify_hash(self, filepath, expected_sha256, model_id=None, model_version_id=None):
        hash_event = {'filename': os.path.basename(filepath), 'progress': 0}
        if model_id is not None:
            hash_event['model_id'] = model_id
        if model_version_id is not None:
            hash_event['model_version_id'] = model_version_id
        ws_manager.broadcast('hash_progress', hash_event)
        sha256 = hashlib.sha256()
        total = os.path.getsize(filepath)
        last_progress_sent = 0
        with open(filepath, 'rb') as f:
            read = 0
            while True:
                chunk = f.read(1024*1024)
                if not chunk:
                    break
                sha256.update(chunk)
                read += len(chunk)
                now = time.time()
                progress = round(100*read/total, 1)
                hash_event = {'filename': os.path.basename(filepath), 'progress': progress}
                if model_id is not None:
                    hash_event['model_id'] = model_id
                if model_version_id is not None:
                    hash_event['model_version_id'] = model_version_id
                if (now - last_progress_sent > 0.2) or (read == total):
                    ws_manager.broadcast('hash_progress', hash_event)
                    last_progress_sent = now
        # Always send 100% at the end if not already sent
        if read == total:
            hash_event = {'filename': os.path.basename(filepath), 'progress': 100.0}
            if model_id is not None:
                hash_event['model_id'] = model_id
            if model_version_id is not None:
                hash_event['model_version_id'] = model_version_id
            ws_manager.broadcast('hash_progress', hash_event)
        # Compare hashes in lowercase to avoid case sensitivity issues
        result = sha256.hexdigest().lower() == str(expected_sha256).lower()
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
            priority=entry.get('priority') if 'priority' in entry else None,
            model_type=entry.get('model_type'),
            model_version_id=entry.get('modelVersionId'),
            base_model=entry.get('baseModel')
        )
        daemon.add_job(item)
    daemon.logger.info(f"Batch manifest queued: {len(manifest)} items from {manifest_path}")
    ws_manager.broadcast('batch_queued', {'count': len(manifest)})

# Example usage:
# daemon = DownloadDaemon()
# daemon.start()
# process_manifest('manifest.json', daemon)
# daemon.add_job(make_queue_item(...))
