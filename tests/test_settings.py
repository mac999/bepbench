import json

from bepkit import settings


def test_defaults_are_loaded():
    assert settings.get("ai.provider") == "ollama"
    assert isinstance(settings.get("viewer.modes"), list)
    assert settings.get("viewer.lod.levels.300.geometry") == "mesh"


def test_missing_path_returns_default():
    assert settings.get("nope.not.here", "fallback") == "fallback"


def test_override_file_deep_merges(tmp_path, monkeypatch):
    override = tmp_path / "bep.config.json"
    override.write_text(json.dumps({
        "ai": {"model": "qwen3:8b"},
        "scoring": {"ready_score": 80},
    }), encoding="utf-8")
    monkeypatch.setenv("BEP_CONFIG", str(override))
    settings.reload()
    try:
        assert settings.get("ai.model") == "qwen3:8b"
        assert settings.get("scoring.ready_score") == 80
        # untouched keys survive the merge
        assert settings.get("ai.provider") == "ollama"
        assert settings.get("viewer.default_mode") == "solid"
    finally:
        monkeypatch.delenv("BEP_CONFIG")
        settings.reload()


def test_broken_override_is_ignored(tmp_path, monkeypatch, capsys):
    override = tmp_path / "broken.json"
    override.write_text("{not json", encoding="utf-8")
    monkeypatch.setenv("BEP_CONFIG", str(override))
    settings.reload()
    try:
        assert settings.get("ai.provider") == "ollama"
    finally:
        monkeypatch.delenv("BEP_CONFIG")
        settings.reload()


def test_returned_containers_are_copies():
    first = settings.get("viewer.palette")
    first["IfcWall"] = "#000000"
    assert settings.get("viewer.palette")["IfcWall"] != "#000000"
