"""What a short hash or a name from pasted generation data is on CivitAI.

Generation data ("Model hash: 19147601cf", "Lora hashes: ...") names models by their AutoV2 hash, the
first ten hex digits of the file's SHA-256, which CivitAI looks up directly. A name is searched for
as a model name. Both answer with the same short items, for the page to show and download from.
"""

from __future__ import annotations

import re

import httpx

from backend import sdsage

HEADERS = {"User-Agent": "CivitaiDaemon/1.0 (SD.Sage plugin)"}
KINDS = {"checkpoint": "Checkpoint", "lora": "LORA", "vae": "VAE"}


def _item(version: dict, model: dict | None = None) -> dict:
    m = model or version.get("model") or {}
    files = version.get("files") or []
    f = next((x for x in files if x.get("primary")), files[0] if files else {})
    model_id = version.get("modelId") or m.get("id")
    return {
        "model_id": model_id,
        "version_id": version.get("id"),
        "name": m.get("name") or "",
        "version": version.get("name") or "",
        "type": m.get("type") or "",
        "base": version.get("baseModel") or "",
        "size_bytes": int((f.get("sizeKB") or 0) * 1024),
        "nsfw": bool(m.get("nsfw")),
        "trained_words": version.get("trainedWords") or [],
        "ref": f"https://civitai.com/models/{model_id}?modelVersionId={version.get('id')}",
    }


def find(hash_: str, query: str, kind: str, adult: bool, api_key: str | None) -> list[dict]:
    """Versions for a short hash, or the best matches for a name (a few)."""
    headers = dict(HEADERS)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    with httpx.Client(timeout=30, headers=headers) as client:
        if hash_:
            if not re.fullmatch(r"[0-9a-fA-F]{8,64}", hash_):
                return []
            r = client.get(f"{sdsage.CIVITAI_API}/model-versions/by-hash/{hash_.upper()}")
            if r.status_code == 404:
                return []
            r.raise_for_status()
            return [_item(r.json())]
        query = query.strip()[:100]
        if not query:
            return []
        params = {"query": query, "limit": 5, "sort": "Highest Rated"}
        if KINDS.get(kind.lower()):
            params["types"] = KINDS[kind.lower()]
        if adult:
            params["nsfw"] = "true"
        r = client.get(f"{sdsage.CIVITAI_API}/models", params=params)
        r.raise_for_status()
        out = []
        for model in r.json().get("items", []):
            versions = model.get("modelVersions") or []
            if versions:
                out.append(_item(versions[0], model))
        return out
