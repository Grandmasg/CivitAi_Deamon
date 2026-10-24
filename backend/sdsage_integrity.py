"""Is a model file whole? Interrupted downloads and copies leave files that look like models.

A .safetensors file starts with the length of its header (8 bytes), then the header (JSON) that says where
each tensor lies; the file must end where the last tensor ends. A shorter file is cut off. Other formats
cannot be checked this cheaply and count as whole. Results are kept per path, size and time of change.
"""

from __future__ import annotations

import json
import re
import struct
from pathlib import Path

from backend import sdsage_metadata

# A header larger than this is not a header (the format allows 100 MB; real ones are a few MB).
MAX_HEADER = 100 * 1024 * 1024
_seen: dict[str, tuple[bool, int | None]] = {}


def safetensors_check(path: Path) -> tuple[bool, int | None]:
    """(whole, size it should have). Unreadable or unusual files count as whole: only a proven cut-off is flagged."""
    size = path.stat().st_size
    try:
        with open(path, "rb") as f:
            head = f.read(8)
            if len(head) < 8:
                return False, None
            (n,) = struct.unpack("<Q", head)
            if n > MAX_HEADER:
                return True, None
            if 8 + n > size:
                return False, None
            header = json.loads(f.read(n))
    except (OSError, ValueError, struct.error):
        return True, None
    ends = [v["data_offsets"][1] for k, v in header.items() if k != "__metadata__" and isinstance(v, dict) and "data_offsets" in v]
    if not ends:
        return True, None
    expected = 8 + n + max(ends)
    return size >= expected, expected


def whole(path: Path) -> tuple[bool, int | None]:
    """Cached check of one model file."""
    if path.suffix.lower() not in (".safetensors", ".sft"):
        return True, None
    key = sdsage_metadata._key(path)
    if key not in _seen:
        _seen[key] = safetensors_check(path)
    return _seen[key]


def partials(root: Path, busy: set[str]) -> list[dict]:
    """Interrupted downloads (.part files nobody is writing) and cut-off model files in the model folders."""
    items = []
    for folder in sdsage_metadata.FOLDERS:
        base = root / folder
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(root).as_posix()
            if p.name.lower().endswith(".part"):
                if p.name[: -len(".part")] in busy:
                    continue
                items.append({"path": rel, "bytes": p.stat().st_size, "kind": "part", "expected": None})
            elif p.suffix.lower() in sdsage_metadata.MODEL_EXTENSIONS:
                ok, expected = whole(p)
                if not ok:
                    items.append({"path": rel, "bytes": p.stat().st_size, "kind": "cut", "expected": expected})
    return items


def name_key(name: str) -> str:
    """A file name as a copy of it would be called: lowercase, without a " (1)" before the extension."""
    return re.sub(r" \(\d+\)(?=\.[^.]+$)", "", name.strip().lower())


def local_index(root: Path) -> tuple[set[str], set[str]]:
    """What is in the folders as whole files: their names (see name_key) and the SHA256 hashes known for them."""
    names = {name_key(p.name) for p in sdsage_metadata.model_files(root) if whole(p)[0]}
    hashes = {str(h).upper() for h in sdsage_metadata._load("hashes.json").values() if isinstance(h, str)}
    return names, hashes
