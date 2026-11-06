import time

import pytest
from PIL import Image

from converter import presets
from converter.watch import Watcher


@pytest.fixture(autouse=True)
def own_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("CONVERTER_SETTINGS", str(tmp_path / "settings.json"))


def test_presets_builtin_own_and_short_names():
    assert presets.resolve("web video") == "Web video (MP4 H.264, 1080p)"
    presets.save("Mine", ["image"], {"format": "webp", "quality": "low", "trim_start": 3, "evil": "x"})
    p = presets.get("Mine")
    assert p["opts"] == {"format": "webp", "quality": "low"} and not p["builtin"]
    with pytest.raises(ValueError):
        presets.save("Photos to JPG", ["image"], {"format": "jpg"})  # built-in name
    presets.delete("Mine")
    with pytest.raises(KeyError):
        presets.get("Mine")


def test_watch_folder_converts_new_files_once(tmp_path):
    inp = tmp_path / "in"
    (inp / "sub").mkdir(parents=True)
    Image.new("RGB", (40, 30), "blue").save(inp / "old.png")
    time.sleep(1.1)
    Watcher.add_rule(str(inp), "photos to jpg")
    events = []
    w = Watcher(interval=0.2, on_event=events.append)
    Image.new("RGB", (40, 30), "red").save(inp / "sub" / "new.png")
    (inp / "notes.txt").write_text("hi")
    (inp / "big.mp4.part").write_bytes(b"x" * 100)  # unfinished download: never touched
    for _ in range(4):
        w.scan_once()
        time.sleep(1.1)
    out = inp / "converted"
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == ["sub/new.jpg"]
    assert any(e["kind"] == "skip" and e["file"] == "notes.txt" for e in events)
    assert not any("part" in e["file"] for e in events)
    assert Watcher(interval=0.2).scan_once() == 0  # after a restart: nothing twice


def test_output_folder_must_differ(tmp_path):
    with pytest.raises(ValueError):
        Watcher.add_rule(str(tmp_path), "photos to jpg", out=str(tmp_path))
