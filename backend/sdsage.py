"""Running the daemon as an SD.Sage plugin.

SD.Sage starts the daemon with these environment variables:

- SDSAGE_PLUGIN_TOKEN: shared secret. Every request from the gateway carries it
  as `Authorization: Bearer <token>`, plus `X-SDSage-User` and `X-SDSage-Role`.
  The daemon uses it to report events back to the gateway.
- SDSAGE_GATEWAY_URL: where to report events (POST /api/plugin/events).
- SDSAGE_MODELS_DIR: the shared model folder (A1111 / SD.Next / ComfyUI layout).
- SDSAGE_PLUGIN_DATA: a folder for the daemon's own database and logs.

Without SDSAGE_PLUGIN_TOKEN the daemon runs standalone, as before.
"""

from __future__ import annotations

import hmac
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

PLUGIN_TOKEN = os.environ.get("SDSAGE_PLUGIN_TOKEN", "")
ENABLED = bool(PLUGIN_TOKEN)
GATEWAY_URL = os.environ.get("SDSAGE_GATEWAY_URL", "").rstrip("/")
MODELS_DIR = os.environ.get("SDSAGE_MODELS_DIR", "")
PLUGIN_DATA = os.environ.get("SDSAGE_PLUGIN_DATA", "")

CIVITAI_API = "https://civitai.com/api/v1"

# CivitAI model types -> folder names used by A1111 / SD.Next.
FOLDERS = {
    "checkpoint": "Stable-diffusion",
    "lora": "Lora",
    "locon": "Lora",
    "dora": "Lora",
    "lycoris": "LyCORIS",
    "vae": "vae",
    "controlnet": "controlnet",
    "textualinversion": "embeddings",
    "embedding": "embeddings",
    "upscaler": "ESRGAN",
}

_UNSAFE = re.compile(r"[^\w\-. ()+\[\]]")


def check_token(token: str | None) -> bool:
    return ENABLED and token is not None and hmac.compare_digest(token, PLUGIN_TOKEN)


def safe_part(name: str, fallback: str = "other") -> str:
    """One path segment: no separators, no '..', only harmless characters."""
    cleaned = _UNSAFE.sub("_", (name or "").replace("/", "_").replace("\\", "_")).strip(" .")
    return cleaned[:150] or fallback


def target_path(model_type: str | None, filename: str, base_model: str | None = None) -> Path:
    """Where a download goes inside the shared models folder, e.g. Lora/SDXL 1.0/name.safetensors."""
    if not MODELS_DIR:
        raise RuntimeError("SDSAGE_MODELS_DIR is not set")
    root = Path(MODELS_DIR).resolve()
    folder = FOLDERS.get((model_type or "").lower().replace(" ", ""), "other")
    parts = [folder]
    if base_model:
        parts.append(safe_part(base_model))
    path = root.joinpath(*parts, safe_part(filename, "model.safetensors")).resolve()
    if root not in path.parents:
        raise ValueError("download path points outside the models folder")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Never overwrite or delete a file the user already has: pick a free name instead.
    n = 1
    candidate = path
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
        n += 1
    return candidate


def notify(event: str, data: dict) -> None:
    """Tell the gateway something happened; never let this break a download."""
    if not (ENABLED and GATEWAY_URL):
        return
    try:
        httpx.post(
            f"{GATEWAY_URL}/api/plugin/events",
            json={"event": event, "data": data},
            headers={"Authorization": f"Bearer {PLUGIN_TOKEN}"},
            timeout=5,
        )
    except Exception:
        pass


def write_civitai_info(model_path: Path, info: dict | None) -> None:
    """Write `<name>.civitai.info` next to the model, as SD.Next does, so SD.Sage
    picks up the base model and trigger words."""
    if not info:
        return
    try:
        stem = str(model_path)[: -len(model_path.suffix)] if model_path.suffix else str(model_path)
        Path(stem + ".civitai.info").write_text(json.dumps(info, indent=2), encoding="utf-8")
    except Exception:
        pass


def parse_civitai_ref(ref: str) -> tuple[int | None, int | None]:
    """(model_id, version_id) from a CivitAI link, an AIR, or a plain number (a model id)."""
    ref = ref.strip()
    if ref.isdigit():
        return int(ref), None
    url = urlparse(ref)
    if url.netloc and not url.netloc.endswith("civitai.com"):
        raise ValueError("only civitai.com links are supported")
    version = parse_qs(url.query).get("modelVersionId", [None])[0]
    m = re.search(r"/models/(\d+)", url.path)
    d = re.search(r"/api/download/models/(\d+)", url.path)
    if d:
        return None, int(d.group(1))
    return (int(m.group(1)) if m else None), (int(version) if version and version.isdigit() else None)


def resolve_civitai(ref: str, api_key: str | None) -> dict:
    """Look up a model version on CivitAI and describe the file to download."""
    model_id, version_id = parse_civitai_ref(ref)
    headers = {"User-Agent": "CivitaiDaemon/1.0 (SD.Sage plugin)"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(timeout=20, headers=headers) as client:
        if version_id is None:
            if model_id is None:
                raise ValueError("no model or version id in the link")
            model = client.get(f"{CIVITAI_API}/models/{model_id}").raise_for_status().json()
            version_id = model["modelVersions"][0]["id"]
        version = client.get(f"{CIVITAI_API}/model-versions/{version_id}").raise_for_status().json()
    files = version.get("files") or []
    if not files:
        raise ValueError("this version has no files")
    file = next((f for f in files if f.get("primary")), files[0])
    model_info = version.get("model") or {}
    return {
        "model_id": version.get("modelId") or model_id,
        "model_version_id": version["id"],
        "url": file.get("downloadUrl") or version.get("downloadUrl"),
        "filename": file.get("name") or f"{version['id']}.safetensors",
        "sha256": (file.get("hashes") or {}).get("SHA256"),
        "model_type": model_info.get("type", "other"),
        "base_model": version.get("baseModel"),
        "name": f"{model_info.get('name', '')} {version.get('name', '')}".strip(),
        "civitai_info": version,
    }
