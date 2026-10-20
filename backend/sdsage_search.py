"""Searching CivitAI from SD.Sage, and the preview images for it.

The browser never talks to CivitAI itself: results come through the daemon
(trimmed to what the page shows) and so do the thumbnails, so SD.Sage's
strict content policy can stay and no third party sees its users' requests.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from backend import sdsage

TYPES = {"Checkpoint", "LORA", "LoCon", "DoRA", "TextualInversion", "VAE", "Controlnet", "Upscaler"}
SORTS = {"Highest Rated", "Most Downloaded", "Newest"}
PERIODS = {"AllTime", "Year", "Month", "Week", "Day"}
THUMB_HOSTS = {"image.civitai.com", "imagecache.civitai.com"}
MAX_THUMB_BYTES = 4 * 1024 * 1024


def _client(api_key: str | None) -> httpx.Client:
    headers = {"User-Agent": "CivitaiDaemon/1.0 (SD.Sage plugin)"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.Client(timeout=30, headers=headers, follow_redirects=True)


def _thumb(url: str | None) -> str | None:
    """A small version of a CivitAI image, through the daemon."""
    if not url or urlparse(url).hostname not in THUMB_HOSTS:
        return None
    # CivitAI resizes on the fly: /width=450/ in the path.
    parts = url.split("/")
    if len(parts) > 4:
        parts[-2] = "width=450"
        url = "/".join(parts)
    return url


def search(params: dict, api_key: str | None, downloaded: set[int]) -> dict:
    query = {"limit": max(1, min(48, int(params.get("limit") or 24)))}
    if (q := str(params.get("query") or "").strip()):
        query["query"] = q[:100]
    if params.get("type") in TYPES:
        query["types"] = params["type"]
    if (base := str(params.get("base") or "").strip()):
        query["baseModels"] = base[:60]
    query["sort"] = params.get("sort") if params.get("sort") in SORTS else "Highest Rated"
    query["period"] = params.get("period") if params.get("period") in PERIODS else "Month"
    query["nsfw"] = "true" if params.get("nsfw") is True else "false"
    if (cursor := str(params.get("cursor") or "").strip()):
        query["cursor"] = cursor[:200]
    with _client(api_key) as client:
        data = client.get(f"{sdsage.CIVITAI_API}/models", params=query).raise_for_status().json()
    items = []
    for m in data.get("items") or []:
        version = (m.get("modelVersions") or [{}])[0]
        files = version.get("files") or []
        primary = next((f for f in files if f.get("primary")), files[0] if files else {})
        images = [i for i in version.get("images") or [] if i.get("type", "image") == "image"]
        image = images[0] if images else {}
        items.append({
            "id": m.get("id"),
            "name": m.get("name"),
            "type": m.get("type"),
            "nsfw": bool(m.get("nsfw")),
            "creator": (m.get("creator") or {}).get("username"),
            "downloads": (m.get("stats") or {}).get("downloadCount"),
            "rating": (m.get("stats") or {}).get("thumbsUpCount"),
            "version": {
                "id": version.get("id"),
                "name": version.get("name"),
                "base": version.get("baseModel"),
                "size_kb": primary.get("sizeKB"),
                "triggers": version.get("trainedWords") or [],
            },
            "image": _thumb(image.get("url")),
            # Images CivitAI rates above PG-13 are blurred by the page.
            "image_adult": (image.get("nsfwLevel") or 1) > 2,
            "downloaded": version.get("id") in downloaded,
            "commercial": m.get("allowCommercialUse"),
        })
    return {"items": items, "next": (data.get("metadata") or {}).get("nextCursor")}


def thumbnail(url: str, api_key: str | None) -> tuple[bytes, str]:
    """Fetch a CivitAI preview for the page; only CivitAI's image hosts, small files."""
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in THUMB_HOSTS:
        raise ValueError("not a CivitAI image")
    with _client(None) as client:
        r = client.get(url)
        r.raise_for_status()
        if len(r.content) > MAX_THUMB_BYTES:
            raise ValueError("image too large")
        kind = r.headers.get("content-type", "image/jpeg")
        if not kind.startswith("image/"):
            raise ValueError("not an image")
        return r.content, kind
