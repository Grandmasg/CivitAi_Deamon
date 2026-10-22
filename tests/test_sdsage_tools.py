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


def test_preview_rating_found_by_blurhash(folder):
    """The preview is the second CivitAI image: its rating is used, not the first's."""
    from PIL import Image

    from backend import sdsage_previews

    model = folder / "Lora" / "p.safetensors"
    model.write_bytes(b"p")
    red = Image.new("RGB", (64, 96), (220, 30, 30))
    red.save(folder / "Lora" / "p.preview.png")
    blue_hash = "LEHV6nWB2yk8pyo0adR*.7kCMdnj"  # a blue-ish 4x3 blurhash
    # The blurhash of a plain red image: only the average colour is set.
    r, g, b = (sdsage_previews._linear(c) for c in (220, 30, 30))
    assert sdsage_previews.hash_components(blue_hash)
    pixels = sdsage_previews._pixels(folder / "Lora" / "p.preview.png")
    comps = sdsage_previews.image_components(pixels, 1, 1)
    assert abs(comps[0][0] - r) < 0.01 and abs(comps[0][2] - b) < 0.01

    def b83(value, length):
        chars = sdsage_previews._CHARS
        return "".join(chars[(value // 83 ** (length - 1 - i)) % 83] for i in range(length))

    red_hash = b83(0, 1) + b83(0, 1) + b83((220 << 16) | (30 << 8) | 30, 4)
    info = {"id": 2, "modelId": 1, "images": [{"hash": blue_hash, "nsfwLevel": 1}, {"hash": red_hash, "nsfwLevel": 8}]}
    (folder / "Lora" / "p.civitai.info").write_text(json.dumps(info))
    assert sdsage_previews.rate(model)
    saved = json.loads((folder / "Lora" / "p.civitai.info").read_text())
    assert saved["sdsagePreview"]["nsfwLevel"] == 8
    assert not sdsage_previews.rate(model), "not worked out again while the preview is unchanged"


def test_search_fills_a_page_and_marks_other_versions(monkeypatch):
    """CivitAI filters the base after paging: more pages are read to fill one."""
    calls = []

    def page(ids, cursor):
        return {"items": [{"id": i, "name": f"m{i}", "modelVersions": [{"id": i * 10}]} for i in ids], "metadata": {"nextCursor": cursor}}

    pages = {None: page([1, 2], "c2"), "c2": page([], "c3"), "c3": page([3, 4, 5], "c4")}

    class Resp:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            return self

        def json(self):
            return self.data

    class Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            calls.append(dict(params))
            return Resp(pages[params.get("cursor")])

    monkeypatch.setattr(sdsage_search.httpx, "Client", Client)
    out = sdsage_search.search({"query": "fox", "period": "Month", "limit": 4}, None, {10}, {2})
    assert [i["id"] for i in out["items"]] == [1, 2, 3, 4, 5]
    assert out["next"] == "c4" and len(calls) == 3
    assert calls[0]["period"] == "AllTime", "a text search ignores the period"
    have = {i["id"]: (i["downloaded"], i["have_model"]) for i in out["items"]}
    assert have[1] == (True, False) and have[2] == (False, True) and have[3] == (False, False)


def test_model_window_leaves_out_adult_images_without_access(monkeypatch):
    data = {"id": 5, "name": "M", "nsfw": False, "description": "<p>Hi &amp; bye</p>", "modelVersions": [{
        "id": 50, "name": "v1", "images": [
            {"url": "https://image.civitai.com/a/b/width=1024/1.jpeg", "nsfwLevel": 1, "meta": {"prompt": "fox", "steps": 20}},
            {"url": "https://image.civitai.com/a/b/width=1024/2.jpeg", "nsfwLevel": 8},
        ]}]}

    class Resp:
        def raise_for_status(self):
            return self

        def json(self):
            return data

    class Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):
            return Resp()

    monkeypatch.setattr(sdsage_search.httpx, "Client", Client)
    m = sdsage_search.model(5, None, False, {50})
    v = m["versions"][0]
    assert m["description"] == "Hi & bye" and v["downloaded"] is True
    assert len(v["images"]) == 1 and v["images"][0]["prompt"] == "fox" and "width=1280" in v["images"][0]["large"]
    assert len(sdsage_search.model(5, None, True, set())["versions"][0]["images"]) == 2
    data["nsfw"] = True
    with pytest.raises(PermissionError):
        sdsage_search.model(5, None, False, set())


def test_organize_plans_moves_keeps_subfolders_and_undoes(folder):
    from backend import sdsage_organize as o

    sd = folder / "Stable-diffusion"
    (sd / "XL" / "anime").mkdir(parents=True)
    (sd / "SD").mkdir(parents=True)
    a = sd / "XL" / "anime" / "a.safetensors"
    a.write_bytes(b"a")
    (sd / "XL" / "anime" / "a.civitai.info").write_text(json.dumps({"baseModel": "Illustrious"}))
    (sd / "XL" / "anime" / "a.preview.png").write_bytes(b"p")
    (sd / "XL" / "anime" / "a_0.png").write_bytes(b"s")
    (sd / "XL" / "anime" / "ab.safetensors").write_bytes(b"other model")
    b = sd / "SD" / "b.safetensors"
    b.write_bytes(b"b")
    (folder / "Lora" / "mystery.safetensors").write_bytes(b"?")

    plan = o.plan(folder)
    by_from = {m["from"].replace("\\", "/"): m for m in plan["moves"]}
    assert by_from["Stable-diffusion/XL/anime/a.safetensors"]["to"].replace("\\", "/") == "Stable-diffusion/Illustrious/anime/a.safetensors"
    assert len(by_from["Stable-diffusion/XL/anime/a.safetensors"]["files"]) == 4, "model, info, preview and sample move together"
    assert by_from["Stable-diffusion/SD/b.safetensors"]["to"].replace("\\", "/") == "Stable-diffusion/SD 1.5/b.safetensors"
    assert any("mystery" in u for u in plan["unknown"]), "no base known: it stays"
    assert not (sd / "Illustrious").exists(), "a plan moves nothing"

    out = o.apply(folder, plan["moves"])
    assert out["moved"] == 3 and not out["failed"]
    assert (sd / "Illustrious" / "anime" / "a_0.png").exists() and (sd / "SD 1.5" / "b.safetensors").exists()
    assert (sd / "XL" / "anime" / "ab.safetensors").exists() is False, "ab has its own (folder) base and moved on its own"
    back = o.undo()
    assert back["files_back"] >= 5 and a.exists() and b.exists()


def test_downloads_go_to_the_canonical_base_folder(folder):
    assert sdsage.canonical_base("SDXL 1.0") == "SDXL" and sdsage.canonical_base("Wan Video 2.2 I2V-A14B") == "Wan 2.2"
    assert sdsage.canonical_base("Wan") == "Wan" and sdsage.canonical_base("Other") is None
    p = sdsage.target_path("LORA", "x.safetensors", "SDXL 1.0")
    assert p.parent.name == "SDXL" and p.parent.parent.name == "Lora"


def test_trash_moves_with_files_restores_and_purges_only_inside(folder):
    from backend import sdsage_duplicates as dup
    from backend import sdsage_trash as tr

    sd = folder / "Stable-diffusion"
    (sd / "SDXL").mkdir(parents=True)
    (sd / "Pony").mkdir(parents=True)
    a = sd / "SDXL" / "a.safetensors"
    a.write_bytes(b"same")
    (sd / "SDXL" / "a.civitai.info").write_text("{}")
    (sd / "SDXL" / "a.preview.png").write_bytes(b"p")
    b = sd / "Pony" / "a copy.safetensors"
    b.write_bytes(b"same")
    keep = dup.suggest_keep(folder, ["Stable-diffusion/Pony/a copy.safetensors", "Stable-diffusion/SDXL/a.safetensors"])
    assert keep == "Stable-diffusion/SDXL/a.safetensors", "the copy with its info and preview is kept"

    out = tr.move_out(folder, ["Stable-diffusion/Pony/a copy.safetensors", "../outside.safetensors", "Stable-diffusion/SDXL/missing.safetensors"])
    assert out["moved"] == 1 and len(out["failed"]) == 2
    assert not b.exists() and (folder / "_oud" / "Stable-diffusion" / "Pony" / "a copy.safetensors").exists()
    # A model with its sidecars goes together, and a name clash gets its own folder.
    c = sd / "Pony" / "a copy.safetensors"
    c.write_bytes(b"new")
    tr.move_out(folder, ["Stable-diffusion/Pony/a copy.safetensors"])
    assert (folder / "_oud" / "Stable-diffusion" / "Pony (1)" / "a copy.safetensors").exists()
    tr.move_out(folder, ["Stable-diffusion/SDXL/a.safetensors"])
    items = tr.listing(folder)["items"]
    assert {i["was"] for i in items} >= {"Stable-diffusion/SDXL/a.safetensors"}
    assert (folder / "_oud" / "Stable-diffusion" / "SDXL" / "a.preview.png").exists()

    back = tr.restore(folder, ["_oud/Stable-diffusion/SDXL/a.safetensors"])
    assert back["restored"] == 1 and a.exists() and (sd / "SDXL" / "a.civitai.info").exists()
    gone = tr.purge(folder, ["_oud/Stable-diffusion/Pony/a copy.safetensors", "Stable-diffusion/SDXL/a.safetensors"])
    assert gone["deleted"] == 1 and a.exists(), "purge touches only what is in the trash"
