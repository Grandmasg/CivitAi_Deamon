
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

   - `uv` is a fast, modern drop-in replacement for `pip` and works with or without virtual environments (`venv`).
   - You can use a virtual environment for isolation, or install globally if preferred.
   - To create and activate a virtual environment (recommended):

     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```

   - Then install `uv` (if not already installed):

     ```bash
     pip install uv
     ```

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

All dependencies (including test tools like `pytest`) are specified in `pyproject.toml`:

```toml
python = ">=3.11,<4.0"
fastapi = "*"
uvicorn[standard] = "*"
httpx = "*"
jinja2 = "*"
sqlite-utils = "*"
python-multipart = "*"
apscheduler = "*"
python-jose = "*"
pip = "*"
ipykernel = "*"
websockets = ">=15.0"
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

## Live Notebook Test (Jupyter) with Test Authentication

Want to test live download progress in a Jupyter notebook? Follow these steps:

1. **Stop any running backend.**
2. **Start the backend in a terminal with test authentication enabled:**

   ```bash
   CIVITAI_TEST_AUTH=1 uvicorn main:app --reload
   ```

   This will run the backend with test authentication, so the notebook can connect using the test token.

3. **Open and run the notebook `test_live_download_progress.ipynb`**
   - The notebook contains cells that start a download and receive live progress events via WebSocket.
   - You will see the download progress directly in the notebook output.

4. **Note:** Make sure all dependencies are installed (see installation instructions above).

---

### Download Directory Structure

All models are downloaded to:

```text
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

## Questions

For questions or feature requests: see TODO_backend.md or TODO_frontend_search.md or open an issue.

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
