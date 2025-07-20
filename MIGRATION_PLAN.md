# Migration Plan: Project Structure Refactor

## [ACTION REQUIRED] Move logger.py to backend/ and update imports to backend.logger

This plan helps you migrate your current CivitAI_Daemon project to the new, modular folder structure as described in `PROJECT_STRUCTURE.md`.

---

## 1. Preparation

- [x] Commit all current changes to git.     <!-- Ensures a clean starting point for migration. -->
- [x] Make a backup of your project folder.  <!-- Prevents data loss in case of migration issues. -->

## 2. Create New Folders

- [x] backend/        <!-- For all backend Python code. -->
- [x] frontend/       <!-- For frontend assets (HTML, JS, CSS, etc.). -->
- [x] configs/        <!-- For configuration files (JSON, manifest, etc.). -->
- [x] data/           <!-- For model data and databases. -->
- [x] logs/           <!-- For log files. -->
- [x] tests/          <!-- For test scripts. -->
- [x] test_downloads/ <!-- For test data used in tests. -->
- [x] systemd/        <!-- For systemd service files. -->

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
  <!-- This makes the folders proper Python packages for import. -->

## 5. Update Imports

- [x] Update all Python imports to use the new package/module paths, e.g.:
  - from `import daemon` to `from backend import daemon`
  - from `import main` to `from backend import main`
- [x] Update any relative imports if needed.
  <!-- Ensures all code references the new structure. -->

## 6. Update Paths in Scripts

- [x] Update all hardcoded file/folder paths in scripts (install.py, launch.py, etc.) to match the new structure.
- [x] Update systemd service template to use the new backend/ path for launch.py.
  <!-- Prevents runtime errors due to moved files. -->

## 7. Update Documentation

- [x] Update README.md and other docs to reflect the new structure and paths.
- [x] Add or update the `PROJECT_STRUCTURE.md` file.
  <!-- Keeps documentation accurate and helpful. -->

## 8. Test Everything

- [x] Run install.py and launch.py from the new locations.
- [x] Run all tests and check if imports and paths work.
- [x] Start the daemon and check the GUI, API, and WebSocket.
- [x] Check logging, config loading,
  <!-- Ensures the refactored project works as expected. -->

## 9. Clean Up

- [x] Remove any obsolete files or folders from the old structure. <!-- Old files/folders have been removed. -->
- [x] Commit all changes to git. <!-- All changes committed, migration finalized. -->
  <!-- Finalize migration and keep version control history clean. -->

---

**Tip:__ Migrate step by step and commit in between. This way you can easily revert if something goes wrong.

**Optional:__ Use a Python tool like `pytest --maxfail=1 -v` to quickly see where imports or paths are incorrect.

---

Ready for a clean, scalable project structure!
