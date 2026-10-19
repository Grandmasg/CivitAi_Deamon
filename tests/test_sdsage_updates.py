from backend.sdsage_updates import compare


def local(file, model_id, version_id, base="SDXL 1.0"):
    return {"file": file, "model_id": model_id, "version_id": version_id, "version_name": "v1",
            "name": file, "base_model": base, "type": "LORA"}


def remote(model_id, *versions):
    return {model_id: {"id": model_id, "name": f"model {model_id}", "type": "LORA",
                       "modelVersions": [{"id": vid, "name": f"v{vid}", "baseModel": base} for vid, base in versions]}}


def test_update_for_same_base_model():
    items = compare([local("a.safetensors", 1, 10)], remote(1, (12, "SDXL 1.0"), (11, "Pony"), (10, "SDXL 1.0")))
    assert len(items) == 1
    assert items[0]["kind"] == "update"
    assert items[0]["latest"]["id"] == 12
    assert items[0]["newer_count"] == 2


def test_variant_when_only_other_base_models_are_newer():
    items = compare([local("a.safetensors", 1, 10)], remote(1, (11, "Pony"), (10, "SDXL 1.0")))
    assert items[0]["kind"] == "variant"


def test_nothing_when_current_is_newest_or_already_downloaded():
    assert compare([local("a.safetensors", 1, 10)], remote(1, (10, "SDXL 1.0"))) == []
    have_both = [local("a.safetensors", 1, 10), local("b.safetensors", 1, 12)]
    assert compare(have_both, remote(1, (12, "SDXL 1.0"), (10, "SDXL 1.0"))) == []


def test_versions_listed_above_but_published_earlier_are_not_updates():
    models = {1: {"id": 1, "name": "m", "type": "LORA", "modelVersions": [
        {"id": 11, "name": "3", "baseModel": "SDXL 1.0", "publishedAt": "2024-01-01T00:00:00Z"},
        {"id": 10, "name": "3.1", "baseModel": "SDXL 1.0", "publishedAt": "2024-06-01T00:00:00Z"},
    ]}}
    assert compare([local("a.safetensors", 1, 10)], models) == []


def test_removed_version_is_skipped():
    assert compare([local("a.safetensors", 1, 99)], remote(1, (12, "SDXL 1.0"))) == []
