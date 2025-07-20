
# 📋 CivitAI_Daemon — Complete Project TODO v1.0

────────────────────────────
📦 Project Structure & Folders
────────────────────────────

CivitAI_Daemon/
├── backend/
│   ├── __init__.py                    ← Python package
│   ├── templates/                     ← gui.html
│   ├── static/                        ← gui.js, style.css
│   ├── daemon.py                      ← daemon class (start/pause/stop)
│   ├── launch.py                      ← launch class (smart port select + server start)
│   ├── main.py                        ← entrypoint (CLI/server start)
│   ├── updater.py                     ← updater class (check for updates)
│   ├── webhook_launch.py              ← webhook launch class (start webhook server)
│   ├── webhook_server.py              ← webhook class (handle webhook requests)
├── frontend/
│   ├── templates/                     ← search.html
│   ├── static/                        ← search.js, style.css
│   ├── launch.py                      ← launch class (smart port select + server start)
│   └── search.py                      ← search class (search models)
├── configs/                           ← settings.json, manifest rules
│   ├── config.json                    ← main configuration file
│   ├── config.example.json            ← example configuration file
│   ├── manifest.json                  ← manifest json
│   ├── test_manifest.json             ← manifest example
│   ├── test_manifest_invalid.json     ← manifest error example
├── data/                              ← model downloads, databases
├── logs/                              ← log files
├── tests/                             ← test_download.py, test_manifest.py
├── test_downloads/                    ← test location for dummy models / test data
├── systemd/                           ← civitai-daemon.service (template)
├── curl_test.md                       ← curl test example
├── install.py                         ← install script
├── logger.py                          ← logging setup
├── pyproject.toml                     ← PEP 621 config with setuptools
├── remove.py                          ← remove systemd service
├── README.md                          ← project documentation
├── README_advanced.md                 ← advanced usage
├── TODO_backend.md                    ← backend TODO list
├── TODO_frontend.md                   ← frontend TODO list
