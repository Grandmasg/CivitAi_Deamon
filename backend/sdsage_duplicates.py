"""The same model in more than one place, found by content.

Only files of equal size can be the same, so those are hashed (with the cache
the metadata lookup fills too); groups with the same SHA256 are duplicates.
Nothing is deleted here: SD.Sage shows the groups and the admin decides.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from pathlib import Path

from backend import sdsage
from backend.sdsage_metadata import _load, _save, model_files, sha256
from backend.sdsage_organize import canonical_base, sidecars

_lock = threading.Lock()
_state: dict = {"running": False, "total": 0, "done": 0, "current": None, "finished_at": None, "groups": [], "error": None}


def status() -> dict:
    with _lock:
        return {**_state, "groups": list(_state["groups"])}


def suggest_keep(root: Path, rels: list[str]) -> str:
    """Which copy to keep: the one with the most that belongs to it (CivitAI
    info, a preview), in a folder named for its base, with the shortest path."""
    def score(rel: str):
        path = root / rel
        names = {f.name.lower() for f in sidecars(path)}
        info = any(n.endswith(".civitai.info") for n in names)
        preview = any(".preview." in n or n.endswith(".thumb.jpg") for n in names)
        parts = Path(rel).parts
        base_folder = len(parts) > 2 and canonical_base(parts[1]) is not None
        return (-int(info), -int(preview), -int(base_folder), len(rel), rel)
    return min(rels, key=score)


def find(root: Path, progress=None) -> list[dict]:
    by_size: dict[int, list[Path]] = defaultdict(list)
    for path in model_files(root):
        by_size[path.stat().st_size].append(path)
    candidates = [p for paths in by_size.values() if len(paths) > 1 for p in paths]
    hashes = _load("hashes.json")
    by_hash: dict[str, list[Path]] = defaultdict(list)
    for n, path in enumerate(candidates):
        if progress:
            progress(n, len(candidates), path)
        by_hash[sha256(path, hashes)].append(path)
        _save("hashes.json", hashes)
    groups = []
    for sha, paths in by_hash.items():
        if len(paths) > 1:
            size = paths[0].stat().st_size
            groups.append({
                "sha256": sha,
                "size": size,
                "files": (files := [str(p.relative_to(root)).replace("\\", "/") for p in sorted(paths)]),
                "keep": suggest_keep(root, files),
                # Space freed by keeping one copy.
                "wasted": size * (len(paths) - 1),
            })
    return sorted(groups, key=lambda g: -g["wasted"])


def run() -> None:
    if not sdsage.MODELS_DIR:
        with _lock:
            _state.update(running=False, error="SDSAGE_MODELS_DIR is not set")
        return
    root = Path(sdsage.MODELS_DIR)

    def progress(n, total, path):
        with _lock:
            _state.update(done=n, total=total, current=str(path.relative_to(root)))

    try:
        groups = find(root, progress)
        with _lock:
            _state.update(groups=groups, error=None)
    except OSError as e:
        with _lock:
            _state.update(error=str(e))
    finally:
        with _lock:
            _state.update(running=False, current=None, finished_at=int(time.time()))


def start() -> bool:
    with _lock:
        if _state["running"]:
            return False
        _state.update(running=True, done=0, total=0)
    threading.Thread(target=run, daemon=True).start()
    return True
