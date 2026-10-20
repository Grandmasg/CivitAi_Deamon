"""Which CivitAI image a model's preview file is, and so how CivitAI rates it.

Tools save a preview beside a model, often not the version's first image.
CivitAI gives every image a blurhash (a few colours in a grid); decoding those
and comparing them with the preview, scaled down the same way, finds the
image, and its `nsfwLevel` says whether the preview is adult. The result is
kept in the `.civitai.info` as `sdsagePreview`, with the preview's size and
time, so it is only worked out again when the preview changes.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image

SAMPLE = 32
# Summed squared difference of the components from which no image matches;
# the right image is well below 0.01, other images of a set above 0.05.
MAX_DISTANCE = 0.03
PREVIEW_SUFFIXES = (".preview.png", ".preview.jpeg", ".preview.jpg", ".preview.webp", ".png", ".jpg", ".jpeg", ".webp", ".thumb.jpg")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz#$%*+,-.:;=?@[]^_{|}~"
_INDEX = {c: i for i, c in enumerate(_CHARS)}


def _b83(text: str) -> int:
    value = 0
    for c in text:
        value = value * 83 + _INDEX[c]
    return value


def _linear(v: int) -> float:
    v = v / 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def hash_components(blurhash: str) -> tuple[int, int, list[tuple[float, float, float]]] | None:
    """The colour components a blurhash stores (linear RGB), with their grid size."""
    try:
        sizes = _b83(blurhash[0])
        nx, ny = sizes % 9 + 1, sizes // 9 + 1
        if len(blurhash) != 4 + 2 * nx * ny:
            return None
        peak = (_b83(blurhash[1]) + 1) / 166
        dc = _b83(blurhash[2:6])
        colors = [(_linear(dc >> 16), _linear((dc >> 8) & 255), _linear(dc & 255))]
        for i in range(1, nx * ny):
            v = _b83(blurhash[4 + i * 2 : 6 + i * 2])
            q = (v // 361, (v // 19) % 19, v % 19)
            colors.append(tuple(math.copysign(((c - 9) / 9) ** 2, c - 9) * peak for c in q))
    except (KeyError, IndexError):
        return None
    return nx, ny, colors


def _pixels(path: Path) -> list[tuple[float, float, float]]:
    """The image at SAMPLE x SAMPLE, in linear RGB."""
    with Image.open(path) as im:
        im.draft("RGB", (4 * SAMPLE, 4 * SAMPLE))
        small = im.convert("RGB").resize((SAMPLE, SAMPLE), Image.Resampling.BOX)
        data = small.get_flattened_data() if hasattr(small, "get_flattened_data") else small.getdata()
        return [(_linear(r), _linear(g), _linear(b)) for r, g, b in data]


def image_components(pixels: list[tuple[float, float, float]], nx: int, ny: int) -> list[tuple[float, float, float]]:
    """The same components a blurhash of these pixels would have (before rounding)."""
    out = []
    for j in range(ny):
        for i in range(nx):
            norm = 1 if i == 0 and j == 0 else 2
            r = g = b = 0.0
            for y in range(SAMPLE):
                cy = math.cos(math.pi * j * y / SAMPLE)
                for x in range(SAMPLE):
                    basis = math.cos(math.pi * i * x / SAMPLE) * cy
                    pr, pg, pb = pixels[y * SAMPLE + x]
                    r, g, b = r + basis * pr, g + basis * pg, b + basis * pb
            n = norm / (SAMPLE * SAMPLE)
            out.append((r * n, g * n, b * n))
    return out


def preview_file(model: Path) -> Path | None:
    stem = str(model)[: -len(model.suffix)]
    for suffix in PREVIEW_SUFFIXES:
        p = Path(stem + suffix)
        if p.is_file():
            return p
    return None


def match(preview: Path, images: list[dict]) -> dict | None:
    """The image the preview is, by blurhash; None when none is close."""
    pixels = _pixels(preview)
    cache: dict[tuple[int, int], list] = {}
    best, best_d = None, MAX_DISTANCE
    for image in images:
        parsed = hash_components(image.get("hash") or "")
        if not parsed:
            continue
        nx, ny, colors = parsed
        if (nx, ny) not in cache:
            cache[(nx, ny)] = image_components(pixels, nx, ny)
        d = sum((a - b) ** 2 for ca, cb in zip(colors, cache[(nx, ny)]) for a, b in zip(ca, cb))
        if d < best_d:
            best, best_d = image, d
    return best


def rate(model: Path) -> bool:
    """Work out and store how CivitAI rates the model's preview; True when the info changed."""
    info_path = Path(str(model)[: -len(model.suffix)] + ".civitai.info")
    preview = preview_file(model)
    if not preview or not info_path.is_file():
        return False
    try:
        info = json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    images = [i for i in info.get("images") or [] if i.get("type", "image") == "image"]
    if not isinstance(info, dict) or not images:
        return False
    st = preview.stat()
    stamp = {"file": preview.name, "size": st.st_size, "mtime": int(st.st_mtime)}
    known = info.get("sdsagePreview") or {}
    if all(known.get(k) == v for k, v in stamp.items()):
        return False
    try:
        found = match(preview, images)
    except OSError:
        return False
    info["sdsagePreview"] = {**stamp, "nsfwLevel": found.get("nsfwLevel") if found else None, "url": found.get("url") if found else None}
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    return True
