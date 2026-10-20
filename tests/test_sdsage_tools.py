"""Metadata by hash, duplicates and search, without calling CivitAI."""

import hashlib
import json

import pytest

from backend import sdsage, sdsage_duplicates, sdsage_metadata, sdsage_search


@pytest.fixture
def folder(tmp_path, monkeypatch):
    models = tmp_path / "models"
    (models / "Lora").mkdir(parents=True)
    (models / "Stable-diffusion" / "XL").mkdir(parents=True)
    monkeypatch.setattr(sdsage, "MODELS_DIR", str(models))
    monkeypatch.setattr(sdsage, "PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(sdsage_metadata, "PAUSE_SECONDS", 0)
    return models


def test_hashes_are_cached(folder):
    f = folder / "Lora" / "a.safetensors"
    f.write_bytes(b"abc")
    cache = {}
    assert sdsage_metadata.sha256(f, cache) == hashlib.sha256(b"abc").hexdigest()
    assert len(cache) == 1
    f.write_bytes(b"abcd")  # size changes: hashed again
    assert sdsage_metadata.sha256(f, cache) == hashlib.sha256(b"abcd").hexdigest()


def test_metadata_written_for_known_and_remembered_for_unknown(folder, monkeypatch):
    known = folder / "Lora" / "known.safetensors"
    known.write_bytes(b"known")
    unknown = folder / "Lora" / "mine.safetensors"
    unknown.write_bytes(b"mine")
    has_info = folder / "Stable-diffusion" / "XL" / "x.safetensors"
    has_info.write_bytes(b"x")
    (folder / "Stable-diffusion" / "XL" / "x.civitai.info").write_text('{"id": 5, "modelId": 4, "images": []}')
    # An old file with the model instead of the version is replaced.
    old = folder / "Lora" / "old.safetensors"
    old.write_bytes(b"old")
    (folder / "Lora" / "old.civitai.info").write_text('{"id": 1, "nsfw": true, "modelVersions": []}')
    # A hash LoRA Manager saved is used instead of reading the file.
    saved = folder / "Lora" / "saved.safetensors"
    saved.write_bytes(b"saved")
    (folder / "Lora" / "saved.metadata.json").write_text(json.dumps({"sha256": "AB" * 32}))
    asked = []

    def fake_lookup(sha, key):
        asked.append(sha)
        if sha == hashlib.sha256(b"known").hexdigest():
            return {"id": 2, "modelId": 1, "baseModel": "SDXL 1.0", "images": [], "model": {"name": "Known", "allowCommercialUse": "{Image}"}}
        if sha == hashlib.sha256(b"old").hexdigest():
            return {"id": 7, "modelId": 1, "images": [{"nsfwLevel": 8}], "model": {"name": "Old", "nsfw": True}}
        return None

    monkeypatch.setattr(sdsage_metadata, "lookup", fake_lookup)
    sdsage_metadata.run(None)
    info = json.loads((folder / "Lora" / "known.civitai.info").read_text())
    assert info["baseModel"] == "SDXL 1.0"
    assert not (folder / "Lora" / "mine.civitai.info").exists()
    assert json.loads((folder / "Lora" / "old.civitai.info").read_text())["images"][0]["nsfwLevel"] == 8
    assert "modelVersions" in json.loads((folder / "Lora" / "old.civitai.info.bak").read_text())
    assert "ab" * 32 in asked, "the saved hash is used"
    assert len(asked) == 4, "the model with complete info is not looked up"
    st = sdsage_metadata.status()
    assert (st["found"], st["not_found"], st["running"]) == (2, 2, False)
    asked.clear()
    sdsage_metadata.run(None)
    assert asked == [], "an unknown file is not asked again until it changes"


def test_duplicates_found_by_content(folder):
    (folder / "Lora" / "a.safetensors").write_bytes(b"same content")
    (folder / "Stable-diffusion" / "XL" / "b.safetensors").write_bytes(b"same content")
    (folder / "Lora" / "c.safetensors").write_bytes(b"same length!")  # same size, other content
    (folder / "Lora" / "d.safetensors").write_bytes(b"unique")
    groups = sdsage_duplicates.find(folder)
    assert len(groups) == 1
    assert groups[0]["files"] == ["Lora/a.safetensors", "Stable-diffusion/XL/b.safetensors"]
    assert groups[0]["wasted"] == len(b"same content")


def test_search_trims_results_and_marks_downloads(monkeypatch):
    sent = {}

    class Resp:
        def raise_for_status(self):
            return self

        def json(self):
            return {"items": [{
                "id": 7, "name": "Fox XL", "type": "LORA", "nsfw": False, "creator": {"username": "c"},
                "stats": {"downloadCount": 10, "thumbsUpCount": 3}, "allowCommercialUse": ["Image"],
                "modelVersions": [{"id": 70, "name": "v1", "baseModel": "SDXL 1.0", "trainedWords": ["sdsfox"],
                                   "files": [{"primary": True, "sizeKB": 1000}],
                                   "images": [{"url": "https://image.civitai.com/xG1/abc/width=1024/1.jpeg", "nsfwLevel": 1}]}],
            }], "metadata": {"nextCursor": "n2"}}

    class Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            sent.update(params or {})
            return Resp()

    monkeypatch.setattr(sdsage_search.httpx, "Client", Client)
    out = sdsage_search.search({"query": "fox", "type": "LORA", "sort": "bogus", "nsfw": "yes"}, None, {70})
    assert sent["types"] == "LORA" and sent["sort"] == "Highest Rated" and sent["nsfw"] == "false"
    item = out["items"][0]
    assert item["downloaded"] is True and item["version"]["triggers"] == ["sdsfox"]
    assert "width=450" in item["image"]
    assert out["next"] == "n2"


def test_thumbnails_only_from_civitai():
    with pytest.raises(ValueError):
        sdsage_search.thumbnail("https://evil.example/x.jpg", None)
    with pytest.raises(ValueError):
        sdsage_search.thumbnail("http://image.civitai.com/x.jpg", None)
