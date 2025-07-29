
# 📋 TODO-backend.md — Stable Civitai Download Daemon

---

## Preparation & Installation

- [x] Install Python 3.11+
- [x] Install uv: `pip install uv`
- [x] Create project folder: `Civitai_Daemon/` (this folder)
- [x] Create subfolders: downloads, logs, templates, static, configs, systemd, updater
- [x] Add empty files: pyproject.toml, config.json, manifest.json, install.py, setup.sh, launch.py

---

## Dependency Management

- [x] Fill pyproject.toml with FastAPI, uvicorn, httpx, jinja2, sqlite-utils, python-multipart, apscheduler
- [x] Install all dependencies via venv uv pip install
- [x] Add smart uv-check in install.py

---

## Configuration Files

- [x] Fill config.json with webhook_url, throttle, retries, workers, timeout, download_dir, and active_port (leave active_port empty/null on initialization)
- [x] Fill manifest.json with test model data (modelId, sha256, url, filename, priority)

---

## Smart Port Selection

- [x] Write launch.py:
  - Exclude port 8000
  - Scan range 8100–8200
  - Pick a random free port (only if 'active_port' is not set in config.json)
  - Write chosen port directly to config.json
  - Start uvicorn server

---

## Build Backend Modules

- [x] logger.py → Rotating logs (log_level from config.json: TODO)
- [x] database.py → Log to SQLite + analysis
- [x] daemon.py → Queue, retry, hash, WebSocket, manifest processing (timeout & download_dir from config.json)
- [x] updater/checker.py → Civitai update checker + scheduler
- [x] main.py → FastAPI app + routers + startup event

---

## API & GUI

- [x] WebSocket endpoint: `/ws/downloads`
- [x] REST API endpoints: `/api/download`, `/api/batch`, `/api/status`, `/api/completed`, `/api/metrics`
- [x] GUI endpoint: `/gui`
- [x] `templates/gui.html` → Bootstrap interface
- [x] `static/client.js` → frontend WebSocket client module

---

## Webhook System

- [x] Add webhook call in daemon.py on success/fail
- [x] Send JSON to URL from config.json

---

## Model Update Checker

- [x] Create updater/checker.py with polling on `/v1/models/{modelId}`
- [x] Compare SHA and updatedAt
- [x] Automatically add new versions to queue
- [x] Log upgrade and notify via webhook
- [x] Schedule daily with APScheduler

---

## Systemd Support (Linux, optional/automatic via installation)

- [x] Create civitai-daemon.service with correct paths (automatic via install.py)
- [x] Copy to `/etc/systemd/system/` (automatic via install.py)
- [x] daemon-reload + enable + start via systemctl (automatic via install.py)

> Systemd and Linux steps are performed automatically by the install script, since this daemon works as a plugin/extension of another app.

---

## Windows Service/Autorun (optional/future)

- [ ] Add Windows service/autorun support (e.g. via NSSM, Task Scheduler, or pythonw)
- [ ] Document Windows install/run steps
  - Example with NSSM (Non-Sucking Service Manager):
    1. Download nssm.exe from <https://nssm.cc/download>
    2. Open an administrator command prompt in the project folder
    3. Install the service:
       `nssm install civitai-daemon "C:\path\to\python.exe" "C:\path\to\launch.py"`
       (Working directory: `C:\path\to\project`)
    4. Start the service via Windows Services or:
       `nssm start civitai-daemon`
    5. Remove with:
       `nssm remove civitai-daemon confirm`
  - Alternative: use Windows Task Scheduler for autorun at login.

---

## Installation Scripts

- [x] install.py → Check uv, install dependencies, start launch.py
- [x] setup.sh → Bash installer + feedback

---

## Testing

- [x] Start daemon via launch.py
- [x] Open GUI and check status
- [x] Test WebSocket via client.js or GUI
- [x] Send manifest.json and check downloads
- [x] Read logs: logs/download.log & error.log
- [x] Inspect database: sqlite-utils completed.db
- [x] Simulate model update and check upgrade flow

---

## Queue Loading/Progress Indicator (optional)

- [ ] (Optional) Stuur queue/progress events via WebSocket zodat de frontend een laadindicator of voortgangsbalk kan tonen

---

## Multi-worker/Parallel Downloads (TODO)

- [ ] Implementeer echte multi-worker/parallelle downloads in daemon.py
  - De instelling 'workers' in config.json wordt nu genegeerd; er draait altijd maar 1 download tegelijk
  - Voeg threading of asyncio toe zodat meerdere downloads tegelijk verwerkt kunnen worden
  - Pas queue/active_downloads en status aan zodat dit correct zichtbaar is in de GUI

---

## Webhook Testing & Development (TODO)

- [ ] Create a simple webhook listener for local testing (e.g. FastAPI or Flask app on port 9000)
- [ ] Test webhook delivery by triggering events (download, update, error)
- [ ] Log received webhook payloads for debugging
- [ ] Add error handling and retry logic for failed webhook calls
- [ ] Document how to set up and test a webhook endpoint (example code)
- [ ] (Optional) Add support for custom webhook headers or authentication

---

## Extensions (optional)

- [ ] CLI tool for daemon status & queue management
- [ ] Telegram integration via webhook or bot (optional, for later)
- [ ] Set up reverse proxy + SSL on VPS (optional, for later)
- [ ] Extend GUI with previews and user roles
- [ ] Add token authentication to endpoints

---

## Ready for Launch

- [ ] Save documentation as stappenplan_backend.txt
- [ ] Start daemon on server or locally via systemd
- [ ] Connect frontend or dashboard to /api + /ws
