"""The trash for models: `_oud` inside the models folder.

Clearing out never deletes at once. A model goes to `_oud/<same path>` with
every file that belongs to it (previews, info, sample images), is listed
there and can be put back; only "delete for good" frees the space. The
gateway scans the type folders, not `_oud`, so a model in it is not offered.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from backend import sdsage
from backend.sdsage_organize import MODEL_EXTENSIONS, TYPES, rekey, sidecars

TRASH = "_oud"
LOG = "trash-moves.json"


def _model(root: Path, rel: str, *, in_trash: bool) -> Path:
    """The model file for a relative path, checked to be a model inside the
    models folder (and in or out of the trash, as asked)."""
    base = (root / TRASH).resolve() if in_trash else root.resolve()
    path = (root / rel).resolve()
    if base not in path.parents:
        raise ValueError(f"{rel}: outside the {'trash' if in_trash else 'models folder'}")
    if not in_trash:
        top = path.relative_to(root.resolve()).parts[0]
        if top == TRASH or top not in (*TYPES, "vae", "embeddings", "LyCORIS", "controlnet", "ESRGAN", "diffusion_models", "UNET"):
            raise ValueError(f"{rel}: not in a model folder")
    if not (path.suffix.lower() in MODEL_EXTENSIONS or path.name.lower().endswith(".part")) or not path.is_file():
        raise ValueError(f"{rel}: not a model file")
    return path


def _free_dir(dest_dir: Path, names: list[str]) -> Path:
    """dest_dir, or a numbered sibling when a file of that name is already there."""
    if not any((dest_dir / n).exists() for n in names):
        return dest_dir
    n = 1
    while any((dest_dir.parent / f"{dest_dir.name} ({n})" / name).exists() for name in names):
        n += 1
    return dest_dir.parent / f"{dest_dir.name} ({n})"


def _move(root: Path, files: list[Path], target_dir: Path) -> list[list[str]]:
    """Move files into target_dir; a model never ends up split from its files."""
    target_dir.mkdir(parents=True, exist_ok=True)
    moved: list[list[str]] = []
    try:
        for f in files:
            dest = target_dir / f.name
            f.replace(dest)
            moved.append([str(f), str(dest)])
    except OSError:
        for src, dest in reversed(moved):
            Path(dest).replace(src)
        raise
    return moved


def move_out(root: Path, rels: list[str]) -> dict:
    """Models (relative paths) to the trash, with their files."""
    done, failed, freed = [], [], 0
    for rel in rels:
        try:
            path = _model(root, rel, in_trash=False)
            files = [path, *sidecars(path)]
            size = sum(f.stat().st_size for f in files)
            parent = path.parent.relative_to(root.resolve())
            target = _free_dir(root / TRASH / parent, [f.name for f in files])
            moved = _move(root, files, target)
        except (ValueError, OSError) as e:
            failed.append({"file": rel, "error": str(e)})
            continue
        done.append({"at": int(time.time()), "files": moved})
        freed += size
    rekey(done)
    log = _log()
    log.extend(done)
    _save_log(log)
    if done:
        sdsage.notify("model.added", {"trashed": len(done)})
    return {"moved": len(done), "bytes": freed, "failed": failed}


def listing(root: Path) -> dict:
    """Models in the trash: where they were, how big they are."""
    trash = root / TRASH
    origin: dict[str, str] = {}
    for entry in _log():
        for src, dest in entry["files"]:
            origin[Path(dest).as_posix()] = Path(src).as_posix()
    items = []
    if trash.is_dir():
        for path in sorted(trash.rglob("*")):
            if not path.is_file() or not (path.suffix.lower() in MODEL_EXTENSIONS or path.name.lower().endswith(".part")):
                continue
            files = [path, *sidecars(path)]
            items.append({
                "path": path.relative_to(root).as_posix(),
                "was": _relative(origin.get(path.as_posix()), root),
                "bytes": sum(f.stat().st_size for f in files),
            })
    return {"items": items, "bytes": sum(i["bytes"] for i in items)}


def _relative(path: str | None, root: Path) -> str | None:
    try:
        return Path(path).resolve().relative_to(root.resolve()).as_posix() if path else None
    except ValueError:
        return None


def restore(root: Path, rels: list[str]) -> dict:
    """Models from the trash back to where they were (never over a file there)."""
    origin: dict[str, str] = {}
    for entry in _log():
        for src, dest in entry["files"]:
            origin[Path(dest).as_posix()] = Path(src).as_posix()
    done, failed = [], []
    for rel in rels:
        try:
            path = _model(root, rel, in_trash=True)
            was = origin.get(path.as_posix())
            # From the log, else the same path without the trash folder.
            back = Path(was).parent if was else root / path.parent.relative_to(root / TRASH)
            files = [path, *sidecars(path)]
            if any((back / f.name).exists() for f in files):
                raise ValueError("a file with that name is already there")
            moved = _move(root, files, back)
        except (ValueError, OSError) as e:
            failed.append({"file": rel, "error": str(e)})
            continue
        done.append({"at": int(time.time()), "files": moved})
    rekey(done)
    if done:
        sdsage.notify("model.added", {"restored": len(done)})
    return {"restored": len(done), "failed": failed}


def purge(root: Path, rels: list[str]) -> dict:
    """Delete trashed models for good (only inside the trash)."""
    n, freed, failed = 0, 0, []
    for rel in rels:
        try:
            path = _model(root, rel, in_trash=True)
            for f in [path, *sidecars(path)]:
                freed += f.stat().st_size
                f.unlink()
            n += 1
        except (ValueError, OSError) as e:
            failed.append({"file": rel, "error": str(e)})
    return {"deleted": n, "bytes": freed, "failed": failed}


def _log() -> list:
    try:
        return json.loads((Path(sdsage.PLUGIN_DATA or ".") / LOG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_log(log: list) -> None:
    base = Path(sdsage.PLUGIN_DATA or ".")
    base.mkdir(parents=True, exist_ok=True)
    (base / LOG).write_text(json.dumps(log[-5000:]), encoding="utf-8")
