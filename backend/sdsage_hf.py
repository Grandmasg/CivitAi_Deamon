"""Hugging Face for SD.Sage: search, download, updates and half-finished repos.

Downloads go into the Hugging Face cache SD.Sage scans (SDSAGE_HF_CACHE), in
the cache's own layout, so the library finds them like any `hf download`.
For a diffusers repo only the files the pipeline loads are fetched: the
components named in model_index.json, not the single-file copies many repos
keep beside them (23 GB for FLUX.1-dev, 26 GB for Krea 2). Repos without a
model_index.json (Nunchaku INT4 builds, single files) download the files the
admin picks. Gated repos need HF_TOKEN and the licence accepted on the site.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
import time
from pathlib import Path

from backend import sdsage

# Pipelines SD.Sage runs, as Hugging Face tags them ("diffusers:<class>").
RUNS = {
    "StableDiffusionPipeline", "StableDiffusionXLPipeline", "LatentConsistencyModelPipeline", "ZImagePipeline",
    "FluxPipeline", "Flux2KleinPipeline", "QwenImagePipeline", "Krea2Pipeline", "WanPipeline",
    "WanImageToVideoPipeline", "LTXPipeline", "LTXConditionPipeline", "LTX2Pipeline",
    "HunyuanVideo15ImageToVideoPipeline", "HunyuanVideo15Pipeline",
}
PIPELINE_TAGS = {"text-to-image", "image-to-image", "text-to-video", "image-to-video"}
SORTS = {"downloads", "likes", "last_modified", "trending_score"}
# Never fetched for a pipeline: pictures, and weights the pipeline does not load.
SKIP = ["*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.mp4", "*.md5", "*.onnx", "*.onnx_data", "*.msgpack", "*.h5", "*.ot"]
# Parts of a pipeline that are settings, not weights.
NOT_LOADED = {"scheduler", "tokenizer", "tokenizer_2", "tokenizer_3", "feature_extractor", "processor"}

_lock = threading.Lock()
_state: dict = {"active": None, "queue": [], "recent": [], "cancel": False}


def cache_dir() -> Path:
    path = os.environ.get("SDSAGE_HF_CACHE") or os.environ.get("HF_HUB_CACHE")
    if not path:
        raise RuntimeError("the Hugging Face cache is not known (SDSAGE_HF_CACHE)")
    return Path(path)


def token() -> str | None:
    return os.environ.get("HF_TOKEN") or None


def _api():
    from huggingface_hub import HfApi

    return HfApi(token=token())


def repo_dir(repo: str) -> Path:
    return cache_dir() / ("models--" + repo.replace("/", "--"))


def snapshot(repo: str) -> Path | None:
    snaps = repo_dir(repo) / "snapshots"
    if not snaps.is_dir():
        return None
    dirs = [d for d in snaps.iterdir() if d.is_dir()]
    return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None


def complete(snap: Path) -> bool:
    """Every component the pipeline loads has its weights (as the gateway judges it)."""
    # OpenVINO conversions keep model_index.json but have their own layout.
    if next(snap.rglob("openvino_model.xml"), None) is not None:
        return True
    try:
        index = json.loads((snap / "model_index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # Component folders without model_index.json: a pipeline that stopped
        # halfway (model_index.json comes last). Otherwise: any weights will do.
        if any(d.is_dir() and os.path.lexists(d / "config.json") for d in snap.iterdir()):
            return False
        return _has_weights(snap)
    for name, value in index.items():
        if name.startswith("_") or name in NOT_LOADED or not (isinstance(value, list) and len(value) == 2 and all(isinstance(v, str) for v in value)):
            continue
        part = snap / name
        if not part.is_dir():
            return False
        if not os.path.lexists(part / "config.json"):
            continue
        shard_index = next(part.glob("*.index.json"), None)
        if shard_index:
            shards = set(json.loads(shard_index.read_text(encoding="utf-8")).get("weight_map", {}).values())
            if not shards or not all(os.path.lexists(part / s) and os.path.exists(part / s) for s in shards):
                return False
        elif not any(f.suffix.lower() in WEIGHTS for f in part.iterdir()):
            return False
    return True


WEIGHTS = (".safetensors", ".bin", ".gguf", ".sft", ".pt", ".pth", ".ckpt", ".xml", ".onnx")


def _has_weights(path: Path) -> bool:
    for f in path.rglob("*"):
        if f.suffix.lower() in WEIGHTS:
            return True
    return False


def state(snap: Path | None) -> str | None:
    """complete, partial, or config (a pipeline's configs without weights, as
    diffusers fetches them to load single files)."""
    if snap is None:
        return None
    if complete(snap):
        return "complete"
    if (snap / "model_index.json").exists() and not _has_weights(snap):
        return "config"
    return "partial"


# ---- Search ----


def _license(tags: list[str], card: dict | None) -> str | None:
    if card and card.get("license_name"):
        return card["license_name"]
    if card and card.get("license"):
        return card["license"]
    return next((t.split(":", 1)[1] for t in tags if t.startswith("license:")), None)


def search(params: dict) -> dict:
    query = str(params.get("query") or "").strip()[:100] or None
    task = params.get("task") if params.get("task") in PIPELINE_TAGS else "text-to-image"
    sort = params.get("sort") if params.get("sort") in SORTS else "downloads"
    limit = max(1, min(48, int(params.get("limit") or 24)))
    models = _api().list_models(
        search=query,
        pipeline_tag=task,
        sort=sort,
        limit=limit,
        expand=["downloads", "likes", "gated", "tags", "lastModified", "library_name", "cardData", "safetensors"],
    )
    items = []
    for m in models:
        tags = list(m.tags or [])
        classes = [t.split(":", 1)[1] for t in tags if t.startswith("diffusers:")]
        name = m.id.rsplit("/", 1)[-1].lower()
        nunchaku = name.startswith("nunchaku-")
        snap = snapshot(m.id)
        params_count = getattr(getattr(m, "safetensors", None), "total", None)
        items.append({
            "id": m.id,
            "downloads": m.downloads,
            "likes": m.likes,
            "gated": bool(m.gated),
            "library": m.library_name,
            "pipeline": classes[0] if classes else None,
            "runs": bool(set(classes) & RUNS) or nunchaku,
            "license": _license(tags, m.card_data.to_dict() if getattr(m, "card_data", None) else None),
            "params": params_count,
            "updated": m.last_modified.isoformat() if getattr(m, "last_modified", None) else None,
            "have": state(snap),
        })
    return {"items": items}


# ---- Choosing files ----


def plan(repo: str) -> dict:
    """Which files a download fetches: for a pipeline, its components; otherwise
    the weight files to choose from. Sizes, and whether access is granted."""
    from huggingface_hub.utils import GatedRepoError, RepositoryNotFoundError

    api = _api()
    try:
        info = api.model_info(repo, files_metadata=True)
    except GatedRepoError:
        return {"repo": repo, "gated": True, "access": False, "url": f"https://huggingface.co/{repo}"}
    except RepositoryNotFoundError:
        raise ValueError(f"{repo} does not exist or is private")
    files = {s.rfilename: (s.size or 0) for s in info.siblings or []}
    out = {"repo": repo, "gated": bool(info.gated), "access": True, "sha": info.sha, "url": f"https://huggingface.co/{repo}"}
    if info.gated:
        # The card is public; the files need the licence accepted (and HF_TOKEN).
        try:
            api.auth_check(repo)
        except GatedRepoError:
            return {**out, "access": False}
    if "model_index.json" in files:
        # Read outside the cache SD.Sage scans: a plan must not leave a repo behind.
        scratch = Path(sdsage.PLUGIN_DATA or ".") / "hf-plans"
        index = json.loads(open(api.hf_hub_download(repo, "model_index.json", cache_dir=str(scratch)), encoding="utf-8").read())
        parts = [k for k, v in index.items() if not k.startswith("_") and isinstance(v, list) and len(v) == 2 and v[0]]
        wanted = [f for f in files if "/" not in f and f.endswith((".json", ".txt"))]
        wanted += [f for f in files if f.split("/", 1)[0] in parts]
        wanted = [f for f in wanted if not any(Path(f).match(p) for p in SKIP)]
        # A component with sharded and single weights keeps the shards its index names.
        out.update(kind="pipeline", files=sorted(wanted), total=sum(files[f] for f in wanted),
                   skipped=sum(v for k, v in files.items() if k not in wanted))
    else:
        weights = sorted((f for f in files if f.endswith((".safetensors", ".gguf", ".sft"))), key=lambda f: files[f])
        out.update(kind="files", choices=[{"file": f, "size": files[f]} for f in weights],
                   extra=[f for f in files if f.endswith((".json", ".txt", ".md"))])
    return out


# ---- Downloading ----


def _folder_size(path: Path) -> int:
    """Bytes in a folder, each file once: on Linux the snapshot holds symlinks
    to blobs (skipped), on Windows without them the files themselves."""
    import stat as _stat

    if not path.exists():
        return 0
    total = 0
    for f in path.rglob("*"):
        try:
            st = f.lstat()
        except OSError:
            continue
        # Regular files only: symlinks (and broken ones) are not counted.
        if _stat.S_ISREG(st.st_mode):
            total += st.st_size
    return total


def status() -> dict:
    with _lock:
        active = dict(_state["active"]) if _state["active"] else None
        queue = [dict(q) for q in _state["queue"]]
        recent = list(_state["recent"])
    if active:
        # Blobs land in the repo folder (and .incomplete files while running).
        active["downloaded"] = max(0, _folder_size(repo_dir(active["repo"])) - active.get("start_bytes", 0))
    return {"active": active, "queue": queue, "recent": recent}


def enqueue(repo: str, files: list[str] | None) -> dict:
    p = plan(repo)
    if not p.get("access"):
        raise PermissionError(f"accept the licence of {repo} on huggingface.co first")
    if p["kind"] == "files":
        chosen = [f for f in (files or []) if f in {c["file"] for c in p["choices"]}]
        if not chosen:
            raise ValueError("choose at least one file")
        sizes = {c["file"]: c["size"] for c in p["choices"]}
        job = {"repo": repo, "files": chosen + p["extra"], "total": sum(sizes[f] for f in chosen)}
    else:
        job = {"repo": repo, "files": p["files"], "total": p["total"]}
    with _lock:
        if _state["active"] and _state["active"]["repo"] == repo or any(q["repo"] == repo for q in _state["queue"]):
            return {"status": "already queued"}
        _state["queue"].append(job)
        start = _state["active"] is None
    if start:
        threading.Thread(target=_worker, daemon=True).start()
    return {"status": "queued", "total": job["total"]}


def cancel(repo: str) -> str:
    with _lock:
        before = len(_state["queue"])
        _state["queue"] = [q for q in _state["queue"] if q["repo"] != repo]
        if before != len(_state["queue"]):
            return "removed"
        if _state["active"] and _state["active"]["repo"] == repo:
            _state["cancel"] = True
            return "cancelling"
    return "not found"


def _worker() -> None:
    from huggingface_hub import hf_hub_download

    while True:
        with _lock:
            if not _state["queue"]:
                _state["active"] = None
                return
            job = _state["queue"].pop(0)
            job["start_bytes"] = _folder_size(repo_dir(job["repo"]))
            job["started_at"] = time.time()
            _state["active"] = job
            _state["cancel"] = False
        result = {"repo": job["repo"], "total": job["total"], "finished_at": None, "error": None}
        try:
            for name in job["files"]:
                with _lock:
                    if _state["cancel"]:
                        raise InterruptedError("cancelled")
                    _state["active"]["current"] = name
                hf_hub_download(job["repo"], name, cache_dir=str(cache_dir()), token=token())
            result["status"] = "done"
            sdsage.notify("model.added", {"repo": job["repo"]})
        except InterruptedError:
            result["status"] = "cancelled"
        except Exception as e:  # noqa: BLE001 - report it on the page
            result["status"] = "failed"
            result["error"] = str(e)[:300]
        result["finished_at"] = int(time.time())
        with _lock:
            _state["recent"] = [result, *_state["recent"]][:20]
            _state["active"] = None


# ---- Updates and half-finished repos ----


def local_repos() -> list[dict]:
    out = []
    root = cache_dir()
    if not root.is_dir():
        return out
    for d in sorted(root.iterdir()):
        if not d.is_dir() or not d.name.startswith("models--"):
            continue
        repo = d.name[len("models--"):].replace("--", "/", 1)
        snap = snapshot(repo)
        out.append({
            "repo": repo,
            "commit": snap.name if snap else None,
            "state": state(snap),
            "size": _folder_size(d),
            "incomplete_files": len(list((d / "blobs").glob("*.incomplete"))) if (d / "blobs").is_dir() else 0,
        })
    return out


_updates: dict = {"checked_at": None, "items": [], "running": False, "error": None}


def updates() -> dict:
    with _lock:
        return {**_updates, "items": list(_updates["items"])}


def check_updates() -> None:
    """Repos whose newest commit on the hub is not the one in the cache."""
    with _lock:
        if _updates["running"]:
            return
        _updates["running"] = True
    items, error = [], None
    try:
        api = _api()
        for local in local_repos():
            if not local["commit"]:
                continue
            try:
                info = api.model_info(local["repo"])
            except Exception:  # noqa: BLE001 - gone, private or gated: nothing to compare
                continue
            if info.sha and info.sha != local["commit"]:
                items.append({"repo": local["repo"], "local": local["commit"][:10], "latest": info.sha[:10],
                              "updated": info.last_modified.isoformat() if info.last_modified else None})
            time.sleep(0.3)
    except Exception as e:  # noqa: BLE001
        error = str(e)[:300]
    with _lock:
        _updates.update(checked_at=int(time.time()), items=items, running=False, error=error)


def delete_repo(repo: str) -> int:
    """Remove a repo from the cache (half-finished ones, on the admin's word). Bytes freed."""
    target = repo_dir(repo).resolve()
    root = cache_dir().resolve()
    if target.parent != root or not target.name.startswith("models--") or not target.is_dir():
        raise ValueError("not a repo in the cache")
    with _lock:
        busy = _state["active"] and _state["active"]["repo"] == repo
    if busy:
        raise ValueError("it is downloading")
    freed = _folder_size(target)
    shutil.rmtree(target)
    sdsage.notify("model.added", {"removed": repo})
    return freed
