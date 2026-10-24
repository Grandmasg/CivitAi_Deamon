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
import time
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


def canonical_base(name: str | None) -> str | None:
    """One name per base model; the gateway's canonical_base, kept in step."""
    if not name:
        return None
    n = name.lower().replace("_", " ").replace("-", " ").strip()
    has = lambda k: k in n
    words = re.split(r"[^a-z0-9.]+", n)
    if has("zimage") or has("z image"):
        return "Z-Image"
    if has("qwen"):
        return "Qwen-Image"
    if has("wan") and has("2.2"):
        return "Wan 2.2"
    if has("wan") and has("2.1"):
        return "Wan 2.1"
    if "wan" in words:
        return "Wan"
    if has("ltx"):
        return "LTX Video"
    if has("hunyuan"):
        return "Hunyuan"
    if has("krea 2") or has("krea2"):
        return "Krea 2"
    if has("flux.2") or has("flux2") or has("klein"):
        return "Flux.2"
    if has("flux") and has("krea"):
        return "Flux.1 Krea"
    if has("flux") and (has("schnell") or n.endswith(" s")):
        return "Flux.1 S"
    if has("flux"):
        return "Flux.1 D"
    if has("lumina"):
        return "Lumina"
    if has("chroma"):
        return "Chroma"
    if has("hidream"):
        return "HiDream"
    if has("cascade"):
        return "Stable Cascade"
    if has("pony"):
        return "Pony"
    if has("illustrious"):
        return "Illustrious"
    if has("noob"):
        return "NoobAI"
    if has("sd 3") or has("sd3"):
        return "SD 3"
    if has("sd 2") or has("sd2"):
        return "SD 2"
    if has("sd 1") or has("sd1") or n == "sd":
        return "SD 1.5"
    if has("lightning"):
        return "SDXL Lightning"
    if has("hyper"):
        return "SDXL Hyper"
    if has("turbo"):
        return "SDXL Turbo"
    if has("sdxl") or "xl" in words:
        return "SDXL"
    return None


def target_path(model_type: str | None, filename: str, base_model: str | None = None) -> Path:
    """Where a download goes inside the shared models folder, e.g. Lora/SDXL/name.safetensors."""
    if not MODELS_DIR:
        raise RuntimeError("SDSAGE_MODELS_DIR is not set")
    root = Path(MODELS_DIR).resolve()
    folder = FOLDERS.get((model_type or "").lower().replace(" ", ""), "other")
    parts = [folder]
    if base_model:
        # One folder per base, the names SD.Sage shows (SDXL, not "SDXL 1.0").
        parts.append(safe_part(canonical_base(base_model) or base_model))
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


_open_cache: dict[str, tuple[float, str | None]] = {}


def refusal(url: str | None, headers: dict) -> str | None:
    """Why CivitAI refuses a download right now, or None when it does not: Early Access files answer 403 until their date or until paid for with Buzz. Remembered for half an hour."""
    if not url:
        return None
    hit = _open_cache.get(url)
    if hit and time.time() - hit[0] < 1800:
        return hit[1]
    why = None
    try:
        with httpx.Client(timeout=15, headers={**headers, "Range": "bytes=0-0"}) as client:
            with client.stream("GET", url) as r:
                if r.status_code == 403:
                    try:
                        info = json.loads(r.read().decode("utf-8", "replace"))
                    except ValueError:
                        info = {}
                    if info.get("error") == "Early Access":
                        until = (info.get("deadline") or "")[:10]
                        why = "Early Access on CivitAI" + (f" until {until}" if until else "") + ": it can only be fetched there, with Buzz"
                    else:
                        why = "CivitAI refuses this download (403): " + (info.get("message") or "login needed")
    except httpx.HTTPError:
        return None
    _open_cache[url] = (time.time(), why)
    return why


def _check_open(url: str | None, headers: dict) -> None:
    why = refusal(url, headers)
    if why:
        raise ValueError(why)


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
    _check_open(file.get("downloadUrl") or version.get("downloadUrl"), headers)
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
