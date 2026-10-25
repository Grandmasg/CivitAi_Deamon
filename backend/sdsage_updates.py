"""Update check for models in SD.Sage's model folder.

Every model with a `<name>.civitai.info` next to it (written by this daemon,
SD.Next or the civitai helper extensions) is compared with CivitAI:

- an *update* is a newer version for the same base model (SDXL -> SDXL);
- a *variant* is a newer version for another base model (an inpaint or
  hyper version, or a port to another family).

Versions that are already in the folder are skipped. Results are kept in
`<plugin data>/updates.json`; the check runs at startup when the last one is
older than a day, then daily, and on request.
"""

from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from backend import sdsage
from backend.sdsage_search import _thumb

MODEL_EXTENSIONS = (".safetensors", ".gguf", ".ckpt", ".pt", ".pth", ".bin")
BATCH = 100
DAY = 24 * 3600

_lock = threading.Lock()
_running = False


def _cache_path() -> Path:
    base = Path(sdsage.PLUGIN_DATA) if sdsage.PLUGIN_DATA else Path(__file__).resolve().parent.parent / "data"
    base.mkdir(parents=True, exist_ok=True)
    return base / "updates.json"


def _ignored_path() -> Path:
    return _cache_path().with_name("updates_ignored.json")


def ignored() -> set[int]:
    try:
        return set(json.loads(_ignored_path().read_text(encoding="utf-8")))
    except Exception:
        return set()


def set_ignored(model_id: int, ignore: bool) -> None:
    """Hide (or show again) updates for one model, e.g. collections whose
    "versions" are really different files."""
    ids = ignored()
    (ids.add if ignore else ids.discard)(int(model_id))
    _ignored_path().write_text(json.dumps(sorted(ids)), encoding="utf-8")


def _downloaded_since(checked_at) -> set:
    """(model, version) pairs downloaded after the last check: done, no longer an open update."""
    try:
        from backend.database import recent_downloads

        return {
            (str(r["model_id"]), str(r["model_version_id"]))
            for r in recent_downloads(500)
            if r["status"] == "success" and (not checked_at or r["timestamp"] > checked_at)
        }
    except Exception:
        return set()


def load() -> dict:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
    except Exception:
        data = {"checked_at": None, "items": [], "scanned": 0, "error": None}
    hidden = ignored()
    got = _downloaded_since(data.get("checked_at"))
    data["items"] = [
        i for i in data.get("items", [])
        if i["model_id"] not in hidden and (str(i["model_id"]), str(i["latest"]["id"])) not in got
    ]
    data["ignored"] = len(hidden)
    data["running"] = _running
    return data


def local_models(models_dir: Path) -> list[dict]:
    """Models that have a .civitai.info with model and version ids."""
    found = []
    for info in models_dir.rglob("*.civitai.info"):
        stem = str(info)[: -len(".civitai.info")]
        model_file = next((Path(stem + ext) for ext in MODEL_EXTENSIONS if Path(stem + ext).is_file()), None)
        if model_file is None:
            continue
        try:
            data = json.loads(info.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not (data.get("modelId") and data.get("id")):
            continue
        found.append(
            {
                "file": model_file.relative_to(models_dir).as_posix(),
                "model_id": int(data["modelId"]),
                "version_id": int(data["id"]),
                "version_name": data.get("name", ""),
                "name": (data.get("model") or {}).get("name") or model_file.stem,
                "base_model": data.get("baseModel"),
                "type": (data.get("model") or {}).get("type"),
                "published_at": data.get("publishedAt") or data.get("createdAt"),
            }
        )
    return found


def _published(version: dict) -> str | None:
    return version.get("publishedAt") or version.get("createdAt")


def compare(local: list[dict], remote: dict[int, dict]) -> list[dict]:
    """Pure comparison, kept separate so it can be tested without the network."""
    have = {m["version_id"] for m in local}
    items = []
    seen: set[tuple[int, int]] = set()
    for m in local:
        model = remote.get(m["model_id"])
        if not model:
            continue
        versions = model.get("modelVersions") or []
        ids = [v["id"] for v in versions]
        if m["version_id"] not in ids:
            continue  # version removed from CivitAI; nothing to compare
        # Creators order versions themselves, so a version listed above ours only
        # counts as newer when it was also published later (when both dates are known).
        current = versions[ids.index(m["version_id"])]
        since = m.get("published_at") or _published(current)
        newer = [
            v
            for v in versions[: ids.index(m["version_id"])]
            if v["id"] not in have and not (since and _published(v) and _published(v) <= since)
        ]
        if not newer:
            continue
        same = [v for v in newer if v.get("baseModel") == m["base_model"]]
        latest = same[0] if same else newer[0]
        key = (m["model_id"], latest["id"])
        if key in seen:
            continue
        seen.add(key)
        image = next((i for i in latest.get("images") or [] if i.get("type", "image") == "image"), None) or {}
        primary = next((f for f in latest.get("files") or [] if f.get("primary")), None) or (latest.get("files") or [{}])[0]
        items.append(
            {
                "model_id": m["model_id"],
                "name": model.get("name") or m["name"],
                "type": model.get("type") or m["type"],
                "file": m["file"],
                "nsfw": bool(model.get("nsfw")),
                "creator": (model.get("creator") or {}).get("username"),
                "link": f"https://civitai.com/models/{m['model_id']}?modelVersionId={latest['id']}",
                "current": {
                    "id": m["version_id"],
                    "name": m["version_name"],
                    "base_model": m["base_model"],
                    "published_at": since,
                },
                "latest": {
                    "id": latest["id"],
                    "name": latest.get("name", ""),
                    "base_model": latest.get("baseModel"),
                    "published_at": latest.get("publishedAt") or latest.get("createdAt"),
                    "image": _thumb(image.get("url")),
                    "image_adult": (image.get("nsfwLevel") or 1) > 2,
                    "size_bytes": int((primary.get("sizeKB") or 0) * 1024) or None,
                    "downloads": (latest.get("stats") or {}).get("downloadCount"),
                    "trained_words": (latest.get("trainedWords") or [])[:10],
                    "early_access_ends": latest.get("earlyAccessEndsAt") or (latest.get("paidAccess") or {}).get("endsAt"),
                    "generation_only": (latest.get("usageControl") or "Download") != "Download",
                },
                "kind": "update" if same else "variant",
                "newer_count": len(newer),
            }
        )
    items.sort(key=lambda i: (i["kind"] != "update", (i["name"] or "").lower()))
    return items


def check(api_key: str | None) -> dict:
    """Run one check now (blocking) and store the result."""
    global _running
    with _lock:
        if _running:
            return load()
        _running = True
    result = {"checked_at": None, "items": [], "scanned": 0, "error": None}
    try:
        if not sdsage.MODELS_DIR:
            raise RuntimeError("SDSAGE_MODELS_DIR is not set")
        local = local_models(Path(sdsage.MODELS_DIR))
        headers = {"User-Agent": "CivitaiDaemon/1.0 (SD.Sage plugin)"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        ids = sorted({m["model_id"] for m in local})
        remote: dict[int, dict] = {}
        with httpx.Client(timeout=30, headers=headers) as client:
            for start in range(0, len(ids), BATCH):
                chunk = ids[start : start + BATCH]
                params = {"ids": ",".join(map(str, chunk)), "limit": BATCH, "nsfw": "true"}
                response = client.get(f"{sdsage.CIVITAI_API}/models", params=params)
                response.raise_for_status()
                for model in response.json().get("items", []):
                    remote[model["id"]] = model
                time.sleep(0.5)  # be gentle with CivitAI
        result["items"] = compare(local, remote)
        result["scanned"] = len(local)
    except Exception as e:
        result["error"] = str(e)
    finally:
        result["checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            _cache_path().write_text(json.dumps(result, indent=2), encoding="utf-8")
        except Exception:
            pass
        with _lock:
            _running = False
    if result["items"]:
        sdsage.notify("model.updates_found", {"count": len(result["items"])})
    return load()


def check_in_background(api_key: str | None) -> None:
    threading.Thread(target=check, args=(api_key,), daemon=True, name="update-check").start()


def start_schedule(api_key_source) -> None:
    """Check at startup when the last check is over a day old, then every day."""

    def loop():
        while True:
            last = load().get("checked_at")
            age = DAY
            if last:
                try:
                    age = time.time() - datetime.fromisoformat(last).timestamp()
                except ValueError:
                    pass
            if age >= DAY:
                check(api_key_source())
                age = 0
            time.sleep(max(60, DAY - age))

    threading.Thread(target=loop, daemon=True, name="update-schedule").start()
