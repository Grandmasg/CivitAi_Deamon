"""Tidy model folders: every checkpoint and LoRA in <type>/<base>/ (your own
subfolders below it stay), with one name per base (the same names SD.Sage shows and the daemon downloads into).

The base comes from CivitAI's info beside the file, else LoRA Manager's
.metadata.json, else the file's own training metadata, else the folder it is
in. Files whose base cannot be told stay where they are. A model moves with
all its sidecar files (.civitai.info, previews, .json, …). Nothing is ever
overwritten; every move is logged, so a run can be undone.
"""

from __future__ import annotations

import json
import re
import struct
import time
from pathlib import Path

from backend import sdsage
from backend.sdsage import canonical_base

TYPES = ("Stable-diffusion", "Lora")
MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".sft"}
# Sidecars: the stem plus a dotted ending (".civitai.info", ".preview.png") or a
# numbered sample image ("_0.png").
SIDECAR = re.compile(r"^(\.[\w.\- ]+|_\d+\.\w+)$")
LOG = "organize-moves.json"


def _json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _header_base(path: Path) -> str | None:
    """The base kohya and ModelSpec write into a LoRA's safetensors header."""
    if path.suffix.lower() != ".safetensors":
        return None
    try:
        with open(path, "rb") as f:
            size = struct.unpack("<Q", f.read(8))[0]
            if size > 50_000_000:
                return None
            meta = json.loads(f.read(size)).get("__metadata__") or {}
    except (OSError, ValueError, struct.error):
        return None
    for key in ("ss_base_model_version", "modelspec.architecture"):
        if base := canonical_base(str(meta.get(key) or "")):
            return base
    return None


def base_of(path: Path, folder: str | None) -> tuple[str | None, str]:
    """The canonical base of a model file, and where it was read."""
    stem = str(path)[: -len(path.suffix)]
    if base := canonical_base(_json(Path(stem + ".civitai.info")).get("baseModel")):
        return base, "civitai"
    meta = _json(Path(stem + ".metadata.json"))
    if base := canonical_base(meta.get("base_model") or (meta.get("civitai") or {}).get("baseModel")):
        return base, "metadata"
    if base := _header_base(path):
        return base, "header"
    if base := canonical_base(folder):
        return base, "folder"
    return None, ""


def sidecars(path: Path) -> list[Path]:
    """The files beside a model that belong to it."""
    stem = path.name[: -len(path.suffix)]
    out = []
    for p in path.parent.iterdir():
        if p != path and p.is_file() and p.name.startswith(stem) and SIDECAR.match(p.name[len(stem):]):
            # Not another model whose name starts with this one's.
            if p.suffix.lower() in MODEL_EXTENSIONS:
                continue
            out.append(p)
    return out


def plan(root: Path) -> dict:
    """What would move where; nothing is touched."""
    moves, unknown, conflicts = [], [], []
    for type_dir in TYPES:
        base_dir = root / type_dir
        if not base_dir.is_dir():
            continue
        for path in sorted(base_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in MODEL_EXTENSIONS:
                continue
            rel = path.relative_to(base_dir)
            folder = rel.parts[0] if len(rel.parts) > 1 else None
            base, source = base_of(path, folder)
            if not base:
                unknown.append(str(path.relative_to(root)))
                continue
            # Only the base folder changes; your own subfolders under it stay
            # (SDXL 1.0/anime -> SDXL/anime). A first folder that names no base
            # (or another one) is kept below the new base folder.
            inner = rel.parts[1:-1] if folder and canonical_base(folder) else rel.parts[:-1]
            target_dir = base_dir.joinpath(base, *inner)
            if path.parent == target_dir:
                continue
            target = target_dir / path.name
            files = [path, *sidecars(path)]
            clash = [str(f.relative_to(root)) for f in files if (target_dir / f.name).exists()]
            item = {
                "from": str(path.relative_to(root)),
                "to": str(target.relative_to(root)),
                "base": base,
                "source": source,
                "files": [str(f.relative_to(root)) for f in files],
                "bytes": sum(f.stat().st_size for f in files),
            }
            (conflicts if clash else moves).append({**item, "clash": clash} if clash else item)
    summary: dict[str, int] = {}
    for m in moves:
        key = f"{Path(m['from']).parent.as_posix()} -> {Path(m['to']).parent.as_posix()}"
        summary[key] = summary.get(key, 0) + 1
    return {"moves": moves, "unknown": unknown, "conflicts": conflicts, "summary": dict(sorted(summary.items()))}


def apply(root: Path, moves: list[dict]) -> dict:
    """Carry out a plan's moves (as planned, checked again); logged for undo."""
    done, failed = [], []
    for m in moves:
        src_model = (root / m["from"]).resolve()
        target_dir = (root / m["to"]).resolve().parent
        if root.resolve() not in target_dir.parents or not src_model.is_file():
            failed.append({"from": m["from"], "error": "not there or outside the models folder"})
            continue
        files = [src_model, *sidecars(src_model)]
        if any((target_dir / f.name).exists() for f in files):
            failed.append({"from": m["from"], "error": "a file with that name is already there"})
            continue
        target_dir.mkdir(parents=True, exist_ok=True)
        moved = []
        try:
            for f in files:
                dest = target_dir / f.name
                f.replace(dest)
                moved.append([str(f), str(dest)])
        except OSError as e:
            # Put back what moved already: a model never ends up split from its files.
            for src, dest in reversed(moved):
                Path(dest).replace(src)
            failed.append({"from": m["from"], "error": str(e)})
            continue
        done.append({"at": int(time.time()), "files": moved})
    rekey(done)
    log = _log()
    log.extend(done)
    _save_log(log)
    if done:
        sdsage.notify("model.added", {"organized": len(done)})
    return {"moved": len(done), "failed": failed}


def rekey(entries: list[dict]) -> None:
    """Hashes and "not on CivitAI" notes are kept by path: move them along,
    so a moved model is not hashed (or looked up) again."""
    from backend import sdsage_metadata as meta

    moved = {src: dest for e in entries for src, dest in e["files"]}
    if not moved:
        return
    hashes = meta._load("hashes.json")
    changed = {}
    for key, sha in hashes.items():
        path, _, rest = key.partition("|")
        changed[f"{moved.get(path, path)}|{rest}" if rest else key] = sha
    meta._save("hashes.json", changed)
    unknown = meta._load("unknown_hashes.json")
    new_unknown = {}
    for path, key in unknown.items():
        dest = moved.get(path, path)
        new_unknown[dest] = key.replace(path, dest, 1) if isinstance(key, str) else key
    meta._save("unknown_hashes.json", new_unknown)


def undo() -> dict:
    """Move back everything the last runs moved, newest first."""
    log = _log()
    back, failed = 0, []
    for entry in reversed(log):
        for src, dest in reversed(entry["files"]):
            try:
                if Path(dest).exists() and not Path(src).exists():
                    Path(src).parent.mkdir(parents=True, exist_ok=True)
                    Path(dest).replace(src)
                    back += 1
            except OSError as e:
                failed.append({"file": dest, "error": str(e)})
    rekey([{"files": [[dest, src] for src, dest in e["files"]]} for e in log])
    _save_log([])
    if back:
        sdsage.notify("model.added", {"organized": -back})
    return {"files_back": back, "failed": failed}


def _log() -> list:
    base = Path(sdsage.PLUGIN_DATA or ".")
    try:
        return json.loads((base / LOG).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save_log(log: list) -> None:
    base = Path(sdsage.PLUGIN_DATA or ".")
    base.mkdir(parents=True, exist_ok=True)
    (base / LOG).write_text(json.dumps(log), encoding="utf-8")
