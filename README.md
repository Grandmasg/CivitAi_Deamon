
# Stable Civitai Download Daemon

This application automates downloads and updates of models via Civitai, featuring a FastAPI backend, dynamic port selection, and webhook support.

## Features
- FastAPI backend
- Webhook endpoint
- Automatic port selection
- Logging and queueing
- Model downloads organized in `data/models/<model_type>/`
- Each job requires a `model_type` (e.g. checkpoint, lora, vae, etc)
- Easily extendable with CI/CD, Telegram, reverse proxy, etc.


## Installation
1. Clone this repo:
   ```bash
   git clone https://github.com/Grandmasg/CivitAi_Deamon.git
   cd CivitAI_Deamon
   ```
2. Install Python 3.11+ and [uv](https://github.com/astral-sh/uv) (if needed)
3. Install all dependencies (including test tools) in one step:
   ```bash
   uv sync
   ```
   - All dependencies are managed in `pyproject.toml` (see below).
   - **Note:** `pytest` is included in main dependencies so it is always installed with `uv sync`.
4. Run the installer:
   ```bash
   python install.py
   ```
5. Start the daemon:
   ```bash
   python launch.py
   ```

## Dependency Management

All dependencies (including test tools like `pytest`) are specified in `pyproject.toml` under `[tool.poetry.dependencies]`:

```toml
[tool.poetry.dependencies]
python = ">=3.11,<4.0"
fastapi = "*"
uvicorn = {extras = ["standard"], version = "*"}
httpx = "*"
jinja2 = "*"
sqlite-utils = "*"
python-multipart = "*"
apscheduler = "*"
python-jose = "*"
pytest = "*"
```

This ensures that `uv sync` or `pip install .` will always install all required packages for both running and testing the project.

**No separate requirements.txt is needed.**

To run the testsuite:
```bash
pytest
```

## Files
- `install.py` — Setup and dependency management
- `launch.py` — Starts backend and webhook server
- `main.py` — FastAPI app
- `webhook_server.py` — Webhook endpoint
- `config.json` — Configuration (auto-filled)

-### Download Directory Structure

All models are downloaded to:

```
data/models/<model_type>/<filename>
```

For example, a checkpoint model will be saved as `data/models/checkpoint/model.safetensors`.

### manifest.json and API: Required Fields

Each job **must** include a `model_type` field. Example manifest entry:

```json
[
  {
    "modelId": 12345,
    "model_type": "checkpoint",
    "sha256": "...",
    "url": "https://...",
    "filename": "model.safetensors",
    "priority": 1
  }
]
```

### Configuration: manifest_mode

The `manifest_mode` option in `config.json` controls how model updates are handled in `manifest.json`:

- `"replace"` (default): When a model update is detected, the existing entry is replaced with the new version (only the latest version is kept).
- `"append"`: When a model update is detected, the new version is added as an extra entry, so multiple versions of the same model can coexist in the manifest.

Example:

```json
{
  "manifest_mode": "replace" // or "append"
}
```

Set this option according to your workflow needs.
- `.gitignore` — Files excluded from git

## GitHub integration
- Add this folder to a new GitHub repository
- Commit and push only the relevant files (see `.gitignore`)

## CI/CD (optional)
- Add a workflow in `.github/workflows/` for automated tests/deployment

---

For questions or feature requests: see TODO_backend.md or open an issue.

## License

MIT License

Copyright (c) 2025 Grandmasg

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
