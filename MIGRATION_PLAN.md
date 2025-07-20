# Migration Plan: Project Structure Refactor

This plan helps you migrate your current CivitAI_Daemon project to the new, modular folder structure as described in `PROJECT_STRUCTURE.md`.

---

## 1. Preparation

- Commit all current changes to git.
- Make a backup of your project folder.

## 2. Create New Folders

- backend/
- frontend/
- configs/
- data/
- logs/
- tests/
- test_downloads/
- systemd/

## 3. Move Files

- Move backend-related Python files (daemon.py, main.py, updater.py, etc.) to backend/.
- Move frontend files (HTML, JS, CSS for search, etc.) to frontend/.
- Move config files (config.json, manifest.json, etc.) to configs/.
- Move test scripts to tests/.
- Move test data to test_downloads/.
- Move civitai-daemon.service to systemd/.
- Move log files to logs/ and model data to data/.

## 4. Add __init__.py

- Add an empty `__init__.py` to backend/ (and optionally to other Python folders).

## 5. Update Imports

- Update all Python imports to use the new package/module paths, e.g.:
  - from `import daemon` to `from backend import daemon`
  - from `import main` to `from backend import main`
- Update any relative imports if needed.

## 6. Update Paths in Scripts

- Update all hardcoded file/folder paths in scripts (install.py, launch.py, etc.) to match the new structure.
- Update systemd service template to use the new backend/ path for launch.py.

## 7. Update Documentation

- Update README.md and other docs to reflect the new structure and paths.
- Add or update the `PROJECT_STRUCTURE.md` file.

## 8. Test Everything

- Run install.py and launch.py from the new locations.
- Run all tests and check if imports and paths work.
- Start the daemon and check the GUI, API, and WebSocket.
- Check logging, config loading, and model downloads.

## 9. Clean Up

- Remove any obsolete files or folders from the old structure.
- Commit all changes to git.

---

**Tip:__ Migrate stap voor stap en commit tussendoor. Zo kun je makkelijk terug als er iets misgaat.

**Optional:__ Gebruik een Python tool als `pytest --maxfail=1 -v` om snel te zien waar imports of paden niet kloppen.

---

Ready for a clean, scalable project structure!
