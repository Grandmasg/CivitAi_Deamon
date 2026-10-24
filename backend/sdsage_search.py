"""Searching CivitAI from SD.Sage, and the preview images for it.

The browser never talks to CivitAI itself: results come through the daemon
(trimmed to what the page shows) and so do the thumbnails, so SD.Sage's
strict content policy can stay and no third party sees its users' requests.
"""

from __future__ import annotations

import html
import re
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import httpx

from backend import sdsage

TYPES = {"Checkpoint", "LORA", "LoCon", "DoRA", "TextualInversion", "VAE", "Controlnet", "Upscaler"}
SORTS = {"Highest Rated", "Most Downloaded", "Newest"}
PERIODS = {"AllTime", "Year", "Month", "Week", "Day"}
# CivitAI filters the base model after taking a page, so a page can come back
# nearly empty; up to this many pages are read to fill one.
MAX_ROUNDS = 5
THUMB_HOSTS = {"image.civitai.com", "imagecache.civitai.com"}
MAX_THUMB_BYTES = 4 * 1024 * 1024


def _client(api_key: str | None) -> httpx.Client:
    headers = {"User-Agent": "CivitaiDaemon/1.0 (SD.Sage plugin)"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return httpx.Client(timeout=30, headers=headers, follow_redirects=True)


def _thumb(url: str | None, width: int = 450) -> str | None:
    """A smaller version of a CivitAI image, through the daemon."""
    if not url or urlparse(url).hostname not in THUMB_HOSTS:
        return None
    # CivitAI resizes on the fly: /width=450/ in the path.
    parts = url.split("/")
    if len(parts) > 4:
        parts[-2] = f"width={width}"
        url = "/".join(parts)
    return url


def html_text(text: str | None, limit: int = 8000) -> str:
    """CivitAI's HTML descriptions as plain text with paragraphs."""
    if not text:
        return ""
    text = re.sub(r"(?i)<br\s*/?>|</p>|</h[1-6]>|</li>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "• ", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def model(model_id: int, api_key: str | None, adult: bool, downloaded: set[int]) -> dict:
    """One model with its versions and their images, for SD.Sage's model window.
    Without adult access, models CivitAI marks adult are refused and images
    rated above PG-13 are left out."""
    with _client(api_key) as client:
        m = client.get(f"{sdsage.CIVITAI_API}/models/{int(model_id)}").raise_for_status().json()
    if m.get("nsfw") and not adult:
        raise PermissionError("adult model")
    versions = []
    for v in m.get("modelVersions") or []:
        files = v.get("files") or []
        primary = next((f for f in files if f.get("primary")), files[0] if files else {})
        images = []
        for i in v.get("images") or []:
            if i.get("type", "image") != "image":
                continue
            rated_adult = (i.get("nsfwLevel") or 1) > 2
            if rated_adult and not adult:
                continue
            meta = i.get("meta") or {}
            images.append({
                "thumb": _thumb(i.get("url")),
                "large": _thumb(i.get("url"), 1280),
                "width": i.get("width"),
                "height": i.get("height"),
                "adult": rated_adult,
                "prompt": (meta.get("prompt") or "")[:2000] or None,
                "settings": {k: meta[k] for k in ("sampler", "steps", "cfgScale", "Size", "seed", "Model") if k in meta} or None,
            })
        versions.append({
            "id": v.get("id"),
            "name": v.get("name"),
            "base": v.get("baseModel"),
            "published": v.get("publishedAt") or v.get("createdAt"),
            "size_kb": primary.get("sizeKB"),
            "downloads": (v.get("stats") or {}).get("downloadCount"),
            "triggers": v.get("trainedWords") or [],
            "notes": html_text(v.get("description"), 3000),
            "images": images,
            "downloaded": v.get("id") in downloaded,
        })
    return {
        "id": m.get("id"),
        "name": m.get("name"),
        "type": m.get("type"),
        "nsfw": bool(m.get("nsfw")),
        "creator": (m.get("creator") or {}).get("username"),
        "tags": (m.get("tags") or [])[:20],
        "description": html_text(m.get("description")),
        "downloads": (m.get("stats") or {}).get("downloadCount"),
        "likes": (m.get("stats") or {}).get("thumbsUpCount"),
        "commercial": m.get("allowCommercialUse"),
        "allow_no_credit": m.get("allowNoCredit"),
        "allow_derivatives": m.get("allowDerivatives"),
        "link": f"https://civitai.com/models/{m.get('id')}",
        "versions": versions,
    }


def search(params: dict, api_key: str | None, downloaded: set[int], have_models: set[int] = frozenset()) -> dict:
    limit = max(1, min(48, int(params.get("limit") or 24)))
    query = {"limit": limit}
    q = str(params.get("query") or "").strip()
    if q:
        query["query"] = q[:100]
    if params.get("type") in TYPES:
        query["types"] = params["type"]
    if (base := str(params.get("base") or "").strip()):
        query["baseModels"] = base[:60]
    query["sort"] = params.get("sort") if params.get("sort") in SORTS else "Highest Rated"
    # With a search text CivitAI uses another index, where a period returns
    # nothing at all: search over all time then.
    query["period"] = "AllTime" if q else (params.get("period") if params.get("period") in PERIODS else "Month")
    query["nsfw"] = "true" if params.get("nsfw") is True else "false"
    if (cursor := str(params.get("cursor") or "").strip()):
        query["cursor"] = cursor[:200]
    found: list[dict] = []
    seen: set = set()
    next_cursor = None
    with _client(api_key) as client:
        for _ in range(MAX_ROUNDS):
            data = client.get(f"{sdsage.CIVITAI_API}/models", params=query).raise_for_status().json()
            for m in data.get("items") or []:
                if m.get("id") not in seen:
                    seen.add(m.get("id"))
                    found.append(m)
            next_cursor = (data.get("metadata") or {}).get("nextCursor")
            # The end: no next page, a full page, or a cursor that did not move.
            if not next_cursor or len(found) >= limit or str(next_cursor) == str(query.get("cursor")):
                break
            query["cursor"] = next_cursor
    items = []
    for m in found:
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
            # Another version of this model is in the folder.
            "have_model": m.get("id") in have_models and version.get("id") not in downloaded,
            "commercial": m.get("allowCommercialUse"),
        })
    # Early Access files cannot be downloaded: found out here, so the page does not offer them.
    headers = {"User-Agent": "CivitaiDaemon/1.0 (SD.Sage plugin)"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    urls = []
    for m in found:
        version = (m.get("modelVersions") or [{}])[0]
        files = version.get("files") or []
        primary = next((f for f in files if f.get("primary")), files[0] if files else {})
        urls.append(primary.get("downloadUrl") or version.get("downloadUrl"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        why = list(pool.map(lambda u: sdsage.refusal(u, headers), urls))
    for item, reason in zip(items, why):
        item["refused"] = reason or ""
    return {"items": items, "next": next_cursor}


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
