"""Hugging Face cache states and removal, without calling the hub."""

import json

import pytest

from backend import sdsage_hf


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("SDSAGE_HF_CACHE", str(tmp_path))
    return tmp_path


def snap(cache, repo, files):
    d = cache / ("models--" + repo.replace("/", "--")) / "snapshots" / "abc123"
    for name, content in files.items():
        p = d / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content if isinstance(content, str) else json.dumps(content))
    return d


INDEX = {"_class_name": "XPipeline", "transformer": ["diffusers", "T"], "vae": ["diffusers", "V"], "scheduler": ["diffusers", "S"]}


def test_states(cache):
    snap(cache, "a/complete", {"model_index.json": INDEX, "transformer/config.json": "{}", "transformer/m.safetensors": "w",
                               "vae/config.json": "{}", "vae/m.safetensors": "w", "scheduler/scheduler_config.json": "{}"})
    snap(cache, "a/partial", {"model_index.json": INDEX, "transformer/config.json": "{}", "vae/config.json": "{}", "vae/m.safetensors": "w"})
    snap(cache, "a/config", {"model_index.json": INDEX, "transformer/config.json": "{}", "vae/config.json": "{}"})
    snap(cache, "a/stopped", {"transformer/config.json": "{}", "transformer/m.safetensors": "w"})
    snap(cache, "a/single", {"svdq-int4_r32-x.safetensors": "w", "README.md": "x"})
    states = {r["repo"]: r["state"] for r in sdsage_hf.local_repos()}
    assert states == {"a/complete": "complete", "a/partial": "partial", "a/config": "config", "a/stopped": "partial", "a/single": "complete"}


def test_delete_only_repos_in_the_cache(cache):
    snap(cache, "a/gone", {"README.md": "x"})
    assert sdsage_hf.delete_repo("a/gone") > 0
    assert not (cache / "models--a--gone").exists()
    with pytest.raises(ValueError):
        sdsage_hf.delete_repo("../../etc")


def test_search_marks_what_runs(cache, monkeypatch):
    class M:
        def __init__(self, id, tags):
            self.id, self.tags = id, tags
            self.downloads, self.likes, self.gated, self.library_name = 5, 1, False, "diffusers"
            self.card_data, self.safetensors, self.last_modified = None, None, None

    class Api:
        def list_models(self, **kw):
            return [M("x/zimage", ["diffusers:ZImagePipeline", "license:apache-2.0"]), M("x/other", ["diffusers:AudioLDMPipeline"]),
                    M("nunchaku-ai/nunchaku-qwen-image", ["license:apache-2.0"])]

    monkeypatch.setattr(sdsage_hf, "_api", lambda: Api())
    items = {i["id"]: i for i in sdsage_hf.search({"task": "bogus"})["items"]}
    assert items["x/zimage"]["runs"] and items["x/zimage"]["license"] == "apache-2.0"
    assert not items["x/other"]["runs"]
    assert items["nunchaku-ai/nunchaku-qwen-image"]["runs"]
