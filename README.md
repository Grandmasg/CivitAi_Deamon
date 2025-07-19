
# Stable Civitai Download Daemon

This application automates downloads and updates of models via Civitai, featuring a FastAPI backend, dynamic port selection, and webhook support.

## Features
- FastAPI backend
- Webhook endpoint
- Automatic port selection
- Logging and queueing
- Easily extendable with CI/CD, Telegram, reverse proxy, etc.

## Installation
1. Clone this repo:
   ```bash
   git clone <repo-url>
   cd CivitAI_Deamon
   ```
2. Install Python 3.11+ and uv (if needed)
3. Run the installer:
   ```bash
   python install.py
   ```
4. Start the daemon:
   ```bash
   python launch.py
   ```

## Files
- `install.py` — Setup and dependency management
- `launch.py` — Starts backend and webhook server
- `main.py` — FastAPI app
- `webhook_server.py` — Webhook endpoint
- `config.json` — Configuration (auto-filled)
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
