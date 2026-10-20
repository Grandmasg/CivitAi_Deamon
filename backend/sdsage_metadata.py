"""CivitAI info for models that have none, found by their SHA256.

Models copied by hand, or downloaded elsewhere, often lack the
`<name>.civitai.info` file SD.Sage reads for the base model, trigger words,
licence and suggested settings. CivitAI can name a file by its hash: this
module hashes the models without one (once; hashes are cached by path, size
and modification time), asks CivitAI, and writes the sidecar the same way a
download does. Files CivitAI does not know are remembered, so they are not
asked about again until they change.

The hash cache is shared with the duplicate finder.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import httpx

from backend import sdsage

MODEL_EXTENSIONS = {".safetensors", ".ckpt", ".pt", ".pth", ".bin", ".gguf", ".sft"}
# Folders with models CivitAI may know.
FOLDERS = ("Stable-diffusion", "Lora", "LyCORIS", "vae", "embeddings", "diffusion_models", "UNET", "controlnet", "ESRGAN")
# Between CivitAI requests, to stay well inside its rate limits.
PAUSE_SECONDS = 1.0
CHUNK = 8 * 1024 * 1024

_lock = threading.Lock()
_status: dict = {"running": False, "total": 0, "done": 0, "found": 0, "not_found": 0, "current": None, "finished_at": None, "error": None}


def _data(name: str) -> Path:
    base = Path(sdsage.PLUGIN_DATA or ".")
    base.mkdir(parents=True, exist_ok=True)
    return base / name


def _load(name: str) -> dict:
    try:
        return json.loads(_data(name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(name: str, data: dict) -> None:
    path = _data(name)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(path)


def _key(path: Path) -> str:
    st = path.stat()
    return f"{path}|{st.st_size}|{int(st.st_mtime)}"


def sha256(path: Path, cache: dict) -> str:
    """The file's SHA256, from the cache when the file has not changed."""
    key = _key(path)
    if key in cache:
        return cache[key]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK):
            h.update(chunk)
    cache[key] = h.hexdigest()
    return cache[key]


def sidecar(path: Path) -> Path:
    return path.with_name(path.stem + ".civitai.info")


def model_files(root: Path) -> list[Path]:
    out = []
    for folder in FOLDERS:
        base = root / folder
        if base.is_dir():
            out += [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in MODEL_EXTENSIONS]
    return sorted(out)


def has_info(path: Path) -> bool:
    """A complete .civitai.info beside the model: a model version as CivitAI's
    API returns it, with its images and their ratings. Older tools saved the
    model instead (`modelVersions`, no `modelId`) or left fields out; those
    files are looked up again and replaced."""
    try:
        info = json.loads(sidecar(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(info, dict) and "modelId" in info and "images" in info


def known_sha(path: Path) -> str | None:
    """The SHA256 another tool saved in its .metadata.json (LoRA Manager), so
    large files need not be hashed again."""
    try:
        sha = json.loads(path.with_name(path.stem + ".metadata.json").read_text(encoding="utf-8")).get("sha256")
    except (OSError, ValueError, AttributeError):
        return None
    if isinstance(sha, str) and len(sha) == 64 and all(c in "0123456789abcdefABCDEF" for c in sha):
        return sha.lower()
    return None


def missing(root: Path, unknown: dict) -> list[Path]:
    """Models without complete CivitAI info that were not looked up unchanged before."""
    return [p for p in model_files(root) if not has_info(p) and unknown.get(str(p)) != _key(p)]


def replace_info(path: Path, info: dict) -> None:
    """Write the new info; an older file is kept once as .civitai.info.bak."""
    old = sidecar(path)
    backup = old.with_name(old.name + ".bak")
    if old.exists() and not backup.exists():
        old.replace(backup)
    sdsage.write_civitai_info(path, info)


def lookup(sha: str, api_key: str | None) -> dict | None:
    """The CivitAI version for a hash, with the model's permissions merged in as
    a downloaded `.civitai.info` has them; None when CivitAI does not know it."""
    headers = {"User-Agent": "CivitaiDaemon/1.0 (SD.Sage plugin)"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(timeout=30, headers=headers) as client:
        r = client.get(f"{sdsage.CIVITAI_API}/model-versions/by-hash/{sha}")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        version = r.json()
        model_id = version.get("modelId")
        if model_id:
            time.sleep(PAUSE_SECONDS)
            m = client.get(f"{sdsage.CIVITAI_API}/models/{model_id}")
            if m.status_code == 200:
                model = m.json()
                keep = ("name", "type", "nsfw", "poi", "tags", "allowNoCredit", "allowCommercialUse", "allowDerivatives", "allowDifferentLicense")
                version["model"] = {**(version.get("model") or {}), **{k: model[k] for k in keep if k in model}}
    return version


def status() -> dict:
    with _lock:
        return dict(_status)


def _set(**kw) -> None:
    with _lock:
        _status.update(kw)


def run(api_key: str | None) -> None:
    """Find and write info for every model without it. One run at a time."""
    if not sdsage.MODELS_DIR:
        _set(error="SDSAGE_MODELS_DIR is not set")
        return
    root = Path(sdsage.MODELS_DIR)
    hashes = _load("hashes.json")
    unknown = _load("unknown_hashes.json")
    todo = missing(root, unknown)
    _set(running=True, total=len(todo), done=0, found=0, not_found=0, current=None, error=None)
    written = []
    try:
        for path in todo:
            _set(current=str(path.relative_to(root)))
            try:
                sha = known_sha(path)
                if not sha:
                    sha = sha256(path, hashes)
                    _save("hashes.json", hashes)
                info = lookup(sha, api_key)
                time.sleep(PAUSE_SECONDS)
            except (OSError, httpx.HTTPError) as e:
                _set(error=f"{path.name}: {e}")
                continue
            if info:
                replace_info(path, info)
                written.append(str(path.relative_to(root)))
                with _lock:
                    _status["found"] += 1
            else:
                unknown[str(path)] = _key(path)
                _save("unknown_hashes.json", unknown)
                with _lock:
                    _status["not_found"] += 1
            with _lock:
                _status["done"] += 1
    finally:
        _set(running=False, current=None, finished_at=int(time.time()))
        if written:
            # The gateway rescans: new base models, licences, trigger words.
            sdsage.notify("model.added", {"metadata": len(written)})


def start(api_key: str | None) -> bool:
    """Start a run in the background; False when one is already running."""
    with _lock:
        if _status["running"]:
            return False
        _status["running"] = True
    threading.Thread(target=run, args=(api_key,), daemon=True).start()
    return True
