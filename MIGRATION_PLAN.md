# Migration Plan: Project Structure Refactor

## [ACTION REQUIRED] Move logger.py to backend/ and update imports to backend.logger

This plan helps you migrate your current CivitAI_Daemon project to the new, modular folder structure as described in `PROJECT_STRUCTURE.md`.

---

## 1. Preparation

- [x] Commit all current changes to git.
- [x] Make a backup of your project folder.

## 2. Create New Folders

- [x] backend/
- [x] frontend/
- [x] configs/
- [x] data/
- [x] logs/
- [x] tests/
- [x] test_downloads/
- [x] systemd/

## 3. Move Files

- [x] Move backend-related Python files (daemon.py, main.py, updater.py, etc.) to backend/.
- [x] Move frontend files (HTML, JS, CSS for search, etc.) to frontend/.
- [x] Move config files (config.json, manifest.json, etc.) to configs/.
- [x] Move test scripts to tests/.
- [x] Move test data to test_downloads/.
- [x] Move civitai-daemon.service to systemd/.
- [x] Move log files to logs/ and model data to data/.

## 4. Add __init__.py

- [x] Add an empty `__init__.py` to backend/ (and optionally to other Python folders).

## 5. Update Imports

- [x] Update all Python imports to use the new package/module paths, e.g.:
  - from `import daemon` to `from backend import daemon`
  - from `import main` to `from backend import main`
- [x] Update any relative imports if needed.

## 6. Update Paths in Scripts

- [x] Update all hardcoded file/folder paths in scripts (install.py, launch.py, etc.) to match the new structure.
- [x] Update systemd service template to use the new backend/ path for launch.py.

## 7. Update Documentation

- [x] Update README.md and other docs to reflect the new structure and paths.
- [x] Add or update the `PROJECT_STRUCTURE.md` file.

## 8. Test Everything

- [x] Run install.py and launch.py from the new locations.
- [x] Run all tests and check if imports and paths work.
- [x] Start the daemon and check the GUI, API, and WebSocket.
- [x] Check logging, config loading,

## 9. Clean Up

- Remove any obsolete files or folders from the old structure.
- Commit all changes to git.

---

**Tip:__ Migrate stap voor stap en commit tussendoor. Zo kun je makkelijk terug als er iets misgaat.

**Optional:__ Gebruik een Python tool als `pytest --maxfail=1 -v` om snel te zien waar imports of paden niet kloppen.

---

Ready for a clean, scalable project structure!
