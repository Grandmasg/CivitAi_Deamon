# Advanced Usage: Stable Civitai Download Daemon

This document describes advanced configuration, integration, and testing options for the Civitai Download Daemon.

## config.json — Example and Options

```json
{
  "webhook_url": "http://localhost:9000/webhook",
  "throttle": 2,
  "retries": 3,
  "workers": 2,
  "timeout": 600,
  "download_dir": "data/models",
  "active_port": 8000,
  "civitai_api_key": "<your-api-key>",
  "jwt_secret": "<your-jwt-secret>",
  "civitai_url": "https://civitai.com/api/v1",
  "manifest_mode": "replace" // or "append"
}
```

- `timeout`: Maximum download time per file in seconds (default: 60, increase for large models)
- `download_dir`: Base directory for all downloads (default: `data/models`)
- `manifest_mode`: See README for explanation. Use `replace` to keep only the latest version, or `append` to keep all versions in manifest.json.

## Download Directory Structure

All models are downloaded to:

```text
data/models/<model_type>/<filename>
```

For example, a checkpoint model will be saved as `data/models/checkpoint/model.safetensors`.

## manifest.json — Structure

Each entry **must** include a `model_type` field:

```json
[
  {
    "modelId": 12345,
    "model_type": "checkpoint",
    "sha256": "...",
    "url": "https://...",
    "filename": "...",
    "priority": 1,
    "updatedAt": "2025-07-19T12:00:00Z"
  }
]
```

## Updater/Checker

- Polls Civitai API daily for each model in manifest.json
- Compares `sha256` and `updatedAt` to detect updates
- On update: updates or appends entry in manifest.json (see `manifest_mode`), sends webhook, logs event

## Webhook Events

- `model_update`: Model version changed (fields: model_id, sha256, updatedAt)
- `model_update_error`: Error during polling (fields: model_id, error)
- Download events: see daemon.py for all possible events

## Dependency Management & Testing

- All dependencies (including test tools like `pytest`) are managed in `pyproject.toml`.
- Install everything (including test tools) in one step:

  ```bash
  uv sync
  ```

- No `requirements.txt` is needed; all environments use `pyproject.toml` as the single source of truth.

### Running the Testsuite

To run all tests:

```bash
pytest
```

## Service Integration

- **Linux:** Systemd service is supported via `install.py` (see main README for details).
- **Windows:** Autorun/service is supported via NSSM or Task Scheduler (see install.py and README).

## Testing

- Start daemon: `python launch.py`
- Open GUI at `http://localhost:<port>/gui`
- Test WebSocket and REST API endpoints
- Simulate model update by editing manifest.json or using the Civitai API
- Check logs and database for results

## Extending

- Add new webhook integrations (e.g. Telegram) via webhook_url
- Extend manifest.json with custom fields as needed
- Use APScheduler for custom polling intervals

---
For more, see TODO_backend.md or open an issue.
