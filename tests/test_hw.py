import subprocess
from pathlib import Path

from converter import media


def _clip(tmp_path: Path) -> Path:
    src = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25", "-t", "1",
                    "-c:v", "libx264", str(src)], check=True)
    return src


def test_failing_hardware_encoder_falls_back_to_software(tmp_path, monkeypatch):
    src = _clip(tmp_path)
    monkeypatch.setattr(media, "hw_encoder", lambda fam: "h264_nvenc")  # pretend there is an NVIDIA card
    msgs = []
    out = tmp_path / "out"
    out.mkdir()
    res = media.process(src, out, {"format": "mp4"}, lambda f, m: msgs.append(m))
    assert res.exists() and res.stat().st_size > 1000
    assert any("software" in m for m in msgs)
    assert media.ffprobe(res)["streams"][0]["codec_name"] == "h264"


def test_hardware_off_never_tries_it(tmp_path, monkeypatch):
    src = _clip(tmp_path)
    called = []
    monkeypatch.setattr(media, "hw_encoder", lambda fam: called.append(fam) or "h264_nvenc")
    out = tmp_path / "out"
    out.mkdir()
    media.process(src, out, {"format": "mp4", "hw": "off"})
    assert not called


def test_rate_control_per_vendor():
    assert media._hw_rate("h264_nvenc", "medium", {}, None)[:2] == ["-preset", "p5"]
    assert media._hw_rate("hevc_qsv", "high", {}, None) == ["-global_quality", "21"]
    assert media._hw_rate("h264_videotoolbox", "low", {}, None) == ["-q:v", "45"]
    assert media._hw_rate("h264_amf", "medium", {}, 800)[:2] == ["-b:v", "800k"]
