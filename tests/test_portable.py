"""pip/pipx install: resource lookup and clear messages for missing optional packages."""
from pathlib import Path

from converter import jobs, paths


def test_root_has_static():
    assert (paths.root() / "static" / "index.html").is_file()
    assert paths.version() != "0.0.0"


def test_missing_optional_package_message():
    e = ModuleNotFoundError("No module named 'py7zr'", name="py7zr")
    msg = jobs.missing_module_message(e)
    assert "anything-converter[archives]" in msg and "py7zr" in msg


def test_run_conversion_turns_missing_module_into_conversion_error(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise ModuleNotFoundError("No module named 'fitz'", name="fitz")
    monkeypatch.setattr(jobs, "_run_conversion", boom)
    try:
        jobs.run_conversion(Path("x.pdf"), tmp_path, "pdf", {"format": "png"})
    except jobs.ConversionError as e:
        assert "anything-converter[pdf]" in str(e)
    else:
        raise AssertionError("expected ConversionError")


def test_pyproject_entry_points_exist():
    import tomllib
    data = tomllib.loads((Path(__file__).resolve().parent.parent / "pyproject.toml").read_text())
    from converter import entry
    for target in {**data["project"]["scripts"], **data["project"]["gui-scripts"]}.values():
        mod, func = target.split(":")
        assert mod == "converter.entry" and callable(getattr(entry, func))
