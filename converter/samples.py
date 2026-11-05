"""Test files: make a small sample of (almost) any file type, to try what the converter does with it.

Used by the app (the TEST FILES drop-down) and by tools/formats_report.py (the full format run).
"""
from __future__ import annotations

import datetime
import re
import gzip
import io
import json
import shutil
import sqlite3
import struct
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

from .catalog import catalog
from .util import NO_WINDOW

ROOT = Path(__file__).resolve().parent.parent
if not (ROOT / "static").exists() and (ROOT.parent / "static").exists():  # frozen app: lib/converter
    ROOT = ROOT.parent

# Extensions for which a sample file can be made (checked by making each one; info-only types have none).
SAMPLE_EXTS = ["1", "2", "3", "360", "3dl", "3ga", "3mf", "4", "5", "6", "7", "7z", "8", "9", "940", "aab", "aac", "ac3", "adb", "adml", "admx", "adoc", "ads", "ahk", "ai", "aif", "aifc", "aiff", "alp", "amf", "apk", "apkm", "apks", "apng", "applescript", "appx", "appxbundle", "ascx", "asf", "ashx", "asm", "asmx", "asp", "aspx", "ass", "astro", "asx", "atom", "au", "au3", "avi", "avif", "awk", "bas", "bash", "bat", "bed", "bib", "bicep", "bin", "bmp", "br", "brd", "bwf", "bz2", "bzl", "c", "caf", "cb7", "cbl", "cbt", "cbz", "cc", "cer", "cfc", "cfg", "cfm", "cgi", "cginc", "cif", "cir", "cjs", "cl", "clj", "cljc", "cljs", "cls", "cmake", "cmd", "cob", "cod", "code-workspace", "coffee", "command", "comp", "conf", "config", "cos", "cpp", "cr", "crl", "crt", "cs", "csh", "cshtml", "csproj", "csr", "css", "csv", "csx", "cu", "cube", "cue", "cuh", "cxx", "d", "dart", "db", "db3", "dbf", "dcm", "dds", "deb", "der", "deskthemepack", "desktop", "dfxp", "dib", "dif", "diff", "divx", "diz", "doc", "dockerfile", "docm", "docx", "dot", "dotm", "dotx", "dpr", "dproj", "drl", "dtd", "dts", "dxf", "eac3", "ear", "edl", "edn", "egg", "ejs", "el", "elf", "elm", "emf", "eml", "entitlements", "env", "eps", "epub", "erb", "erl", "evo", "ex", "exr", "f", "f4v", "f90", "f95", "fa", "fasta", "fastq", "fb2", "fcpxml", "fish", "fits", "flac", "flv", "for", "frag", "frm", "fs", "fsi", "fsproj", "fsx", "fzz", "g", "gb", "gba", "gbc", "gbl", "gbr", "gco", "gcode", "gd", "gdoc", "gem", "gen", "geojson", "geom", "gff", "gg", "gguf", "gif", "glb", "glsl", "go", "gpx", "gql", "gradle", "graphql", "groovy", "gsheet", "gslides", "gsm", "gtf", "gtl", "gto", "gv", "gz", "h", "h264", "h265", "haml", "handlebars", "har", "hbs", "hcl", "hdr", "heic", "heif", "hevc", "hex", "hh", "hlsl", "hpp", "hrl", "hs", "hta", "htaccess", "htm", "html", "htpasswd", "hx", "hxx", "ibooks", "ica", "icns", "ico", "ics", "igc", "iml", "inf", "ini", "ino", "insp", "insv", "ipa", "ips", "ipynb", "iso", "ivf", "j2k", "jar", "java", "jfif", "jl", "jp2", "jpe", "jpeg", "jpg", "jpx", "js", "jse", "json", "json5", "jsonc", "jsonl", "jsonld", "jsonnet", "jsp", "jspx", "jsx", "jxl", "kar", "kdenlive", "key", "kicad_pcb", "kicad_pro", "kicad_sch", "kml", "kmz", "kql", "kra", "ksh", "kt", "kts", "lbrn2", "ldif", "less", "lhs", "library-ms", "liquid", "lisp", "list", "loc", "log", "lrc", "lrv", "lsp", "lua", "lz4", "lzma", "m", "m2ts", "m2v", "m3u", "m3u8", "m4a", "m4b", "m4r", "m4v", "manifest", "map", "markdown", "mbox", "mcaddon", "mcpack", "mcworld", "md", "md5", "mdx", "metal", "mht", "mhtml", "mib", "mid", "midi", "mjs", "mk", "mk3d", "mka", "mkv", "ml", "mli", "mlt", "mmcif", "mmd", "mogrt", "mol", "mol2", "mount", "mov", "mp3", "mp4", "mpo", "msix", "msixbundle", "msp", "mtl", "mts", "mustache", "mzml", "n64", "ndjson", "nds", "nes", "net", "nfo", "ngc", "nim", "ninja", "nix", "njk", "nk", "npy", "npz", "nupkg", "nuspec", "o", "obj", "odg", "ofx", "oga", "ogg", "ogv", "opml", "opus", "ora", "org", "orig", "osk", "osz", "otc", "otp", "ots", "ott", "out", "ova", "ovpn", "p7b", "p7c", "pac", "pas", "patch", "path", "pbm", "pbxproj", "pcbdoc", "pce", "pcx", "pdb", "pde", "pdf", "pem", "pgm", "php", "phtml", "pk3", "pkb", "pks", "pl", "plist", "pls", "ply", "pm", "png", "pnm", "pom", "pot", "potm", "potx", "pp", "pp3", "ppm", "ppsm", "ppsx", "ppt", "pptm", "pptx", "pro", "properties", "props", "proto", "ps", "ps1", "ps1xml", "psd1", "psm1", "pug", "puml", "py", "pyi", "pyw", "qbo", "qcow", "qcow2", "qfx", "qif", "qoi", "qrc", "qt", "r", "ra", "ram", "razor", "rb", "rdp", "reg", "rej", "repo", "resx", "rf64", "rgb", "rkt", "rm", "rmd", "rpy", "rs", "rss", "rst", "rtf", "rules", "s", "s19", "safetensors", "sam", "sami", "sass", "sb3", "sbt", "sbv", "sc", "scad", "scala", "sch", "schdoc", "scm", "scss", "sdf", "search-ms", "sed", "service", "sfc", "sgi", "sh", "shader", "shortcut", "shtml", "slk", "sln", "slnx", "sls", "smc", "smd", "smi", "sms", "snd", "so", "socket", "sol", "sp", "spec", "spx", "sql", "sqlite", "sqlite3", "srec", "srt", "ss", "ssa", "sta", "stl", "storyboard", "styl", "sub", "sublime-project", "sv", "svelte", "svg", "svgz", "svh", "swf", "swift", "tap", "tar", "tar.gz", "tar.md5", "target", "targets", "tbz2", "tcl", "tcx", "tex", "tf", "tfstate", "tfvars", "tga", "tgz", "thd", "theme", "themepack", "thm", "thrift", "tif", "tiff", "timer", "toml", "tool", "torrent", "tpl", "ts", "tsv", "tsx", "tta", "ttc", "ttf", "ttml", "twig", "txt", "txz", "ufp", "ui", "unitypackage", "unl", "uplugin", "uproject", "url", "uu", "uue", "v", "v64", "vb", "vbe", "vbhtml", "vbproj", "vbs", "vcf", "vcproj", "vcs", "vcxproj", "vdi", "vert", "vhd", "vhdl", "vhdx", "vmdk", "vnc", "vob", "voc", "vro", "vsix", "vtt", "vue", "w64", "war", "wat", "wav", "weba", "webarchive", "webloc", "webm", "webmanifest", "webp", "wer", "wgsl", "whl", "wim", "wma", "wmf", "wmv", "woff", "woff2", "workflow", "wpl", "wsf", "wv", "xaml", "xapk", "xbm", "xcodeproj", "xcworkspace", "xhtml", "xib", "xln", "xls", "xlsm", "xlsx", "xlt", "xltm", "xltx", "xmind", "xml", "xmp", "xpi", "xsd", "xsl", "xslt", "xspf", "xz", "yaml", "yml", "z64", "zig", "zip", "zipx", "zsh", "zst"]


NEEDS = [("LibreOffice", "libreoffice"), ("Calibre", "Calibre"), ("chdman", "chdman"), ("Ghostscript", "Ghostscript"),
         ("qemu-img", "qemu-img"), ("FluidSynth", "FluidSynth"), ("7-Zip", "7-Zip"), ("Graphviz", "Graphviz"),
         ("pandoc", "pandoc"), ("ImageMagick", "ImageMagick"), ("Chrome", "Chrome")]


def ff(args, out):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args, str(out)], capture_output=True, **NO_WINDOW)
    return out if r.returncode == 0 and out.exists() and out.stat().st_size else None


# --------------------------------------------------------------------------- voorbeelden maken

def _rom_sample(ext: str, d: Path) -> Path | None:
    """Game files: discs (CUE/BIN, ISO), cartridges and patches, with just enough structure to be recognised."""
    p = d / f"sample.{ext}"
    title = b"ANYTHING TEST"
    if ext in ("cue", "bin"):
        sector = bytearray(2352)
        sector[0:12] = b"\x00" + b"\xff" * 10 + b"\x00"
        sector[15] = 1
        data = bytearray()
        for i in range(32):
            s = bytearray(sector)
            s[16:16 + 2048] = (b"\x01CD001\x01" + title).ljust(2048, b"\0") if i == 16 else bytes(2048)
            data += s
        (d / "sample.bin").write_bytes(bytes(data))
        (d / "sample.cue").write_text('FILE "sample.bin" BINARY\n  TRACK 01 MODE1/2352\n    INDEX 01 00:00:00\n')
        return d / f"sample.{ext}"
    if ext == "iso":
        data = bytearray(2048 * 32)
        data[16 * 2048:16 * 2048 + 8] = b"\x01CD001\x01\x00"
        data[16 * 2048 + 40:16 * 2048 + 40 + len(title)] = title
        p.write_bytes(bytes(data))
        return p
    body = bytes(range(256)) * 128  # 32 KB
    if ext == "nes":
        p.write_bytes(b"NES\x1a\x02\x01" + bytes(10) + body + body)
    elif ext in ("z64", "n64", "v64"):
        rom = bytearray(b"\x80\x37\x12\x40" + bytes(28) + title.ljust(20) + bytes(12)) + body * 32
        if ext == "v64":
            rom = bytearray(b for i in range(0, len(rom), 2) for b in (rom[i + 1], rom[i]))
        elif ext == "n64":
            rom = bytearray(b for i in range(0, len(rom), 4) for b in reversed(rom[i:i + 4]))
        p.write_bytes(bytes(rom))
    elif ext in ("sfc", "smc"):
        rom = bytearray(body * 4)
        rom[0x7FC0:0x7FC0 + 21] = title.ljust(21)
        p.write_bytes((bytes(512) if ext == "smc" else b"") + bytes(rom))
    elif ext in ("gb", "gbc", "gba", "gen", "smd", "sms", "gg", "pce", "a26", "lnx", "ws", "wsc", "ngp"):
        rom = bytearray(body * 2)
        rom[0x134:0x134 + len(title)] = title
        p.write_bytes(bytes(rom))
    elif ext == "nds":
        rom = bytearray(body * 4)
        rom[0:12] = title[:12]
        rom[0x12] = 0  # unit code: plain DS (not DSi)
        rom[0x80:0x84] = (len(rom) // 2).to_bytes(4, "little")
        p.write_bytes(bytes(rom))
    elif ext == "ips":
        p.write_bytes(b"PATCH" + (0x10).to_bytes(3, "big") + (4).to_bytes(2, "big") + b"TEST" + b"EOF")
    else:
        return None
    return p


def make_sample(ext: str, d: Path) -> Path | None:  # noqa: C901 - één lange lijst is hier het duidelijkst
    if ext == "ibooks":  # Apple Books: an EPUB under another name
        e = make_sample("epub", d)
        return e.rename(d / "sample.ibooks") if e else None
    if ext == "webarchive":
        import plistlib
        page = b"<html><head><title>Test page</title></head><body><h1>Test page</h1><p>Hello world.</p></body></html>"
        p = d / "sample.webarchive"
        p.write_bytes(plistlib.dumps({"WebMainResource": {"WebResourceData": page, "WebResourceMIMEType": "text/html",
                                                          "WebResourceTextEncodingName": "UTF-8",
                                                          "WebResourceURL": "https://example.com/"}},
                                     fmt=plistlib.FMT_BINARY))
        return p
    if ext in ("cue", "bin", "iso", "nes", "z64", "n64", "v64", "sfc", "smc", "gb", "gbc", "gba", "gen", "smd",
               "sms", "gg", "pce", "nds", "ips"):
        r = _rom_sample(ext, d)
        if r:
            return r
    from PIL import Image, ImageDraw
    p = d / f"sample.{ext}"
    from PIL import ImageFont
    img = Image.new("RGB", (640, 160), "white")
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 56)
    except OSError:
        font = ImageFont.load_default(size=56)
    ImageDraw.Draw(img).text((20, 40), "Converter 2026", fill="black", font=font)
    pil = {"jpg": "JPEG", "jpeg": "JPEG", "jpe": "JPEG", "jfif": "JPEG", "png": "PNG", "gif": "GIF", "webp": "WEBP",
           "avif": "AVIF", "bmp": "BMP", "dib": "DIB", "tif": "TIFF", "tiff": "TIFF", "ico": "ICO", "icns": "ICNS",
           "tga": "TGA", "pcx": "PCX", "ppm": "PPM", "pnm": "PPM", "sgi": "SGI", "rgb": "SGI", "jp2": "JPEG2000",
           "j2k": "JPEG2000", "jpx": "JPEG2000", "qoi": "QOI", "dds": "DDS", "mpo": "MPO", "thm": "JPEG",
           "insp": "JPEG", "blp": "BLP", "msp": "MSP", "eps": "EPS"}
    if ext in pil:
        im = img.convert("1") if ext == "msp" else img
        im.save(p, pil[ext], **({"sizes": [(64, 64)]} if ext == "ico" else {}))
        return p
    if ext in ("pbm", "xbm"):
        img.convert("1").save(p, "PPM" if ext == "pbm" else "XBM")
        return p
    if ext == "pgm":
        img.convert("L").save(p, "PPM")
        return p
    if ext == "apng":
        frames = [img, img.transpose(Image.FLIP_LEFT_RIGHT)]
        frames[0].save(p, "PNG", save_all=True, append_images=frames[1:])
        return p
    if ext in ("heic", "heif"):
        import pillow_heif
        pillow_heif.from_pillow(img).save(p)
        return p
    if ext in ("exr", "hdr", "jxl", "ras", "xwd"):
        src = d / "_b.png"
        img.save(src)
        return ff(["-i", str(src)] + (["-pix_fmt", "gbrpf32le"] if ext == "exr" else []) +
                  (["-f", "sunrast_pipe"] if ext == "ras" else []), p)
    if ext in ("kra", "ora"):
        b = io.BytesIO()
        img.save(b, "PNG")
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("mimetype", "image/openraster" if ext == "ora" else "application/x-krita")
            z.writestr("mergedimage.png", b.getvalue())
        return p
    if ext == "psd":
        return None
    if ext == "fits":
        import numpy as np
        hdr = "".join(f"{c:<80}" for c in ["SIMPLE  =                    T", "BITPIX  =                    8",
                                             "NAXIS   =                    2", "NAXIS1  =                   16",
                                             "NAXIS2  =                   16", "END"])
        p.write_bytes(hdr.encode().ljust(2880, b" ") + np.arange(256, dtype="uint8").tobytes().ljust(2880, b"\0"))
        return p
    # ---- audio
    tone = ["-f", "lavfi", "-i", "sine=frequency=440:duration=1"]
    audio = {"mp3": [], "wav": [], "flac": [], "aiff": [], "aif": ["-f", "aiff"], "aifc": ["-f", "aiff"],
             "aac": ["-c:a", "aac"], "m4a": [], "m4b": ["-f", "ipod"], "m4r": ["-f", "ipod"], "ogg": [], "oga": ["-f", "ogg"],
             "opus": [], "wma": [], "wv": [], "tta": [], "mka": [], "ac3": [], "eac3": [], "thd": ["-c:a", "truehd",
                                                                                                "-strict", "-2", "-f", "truehd"],
             "dts": ["-c:a", "dca", "-strict", "-2", "-ar", "48000", "-f", "dts"], "gsm": ["-ar", "8000", "-ac", "1", "-c:a",
                                                                                     "libgsm", "-f", "gsm"],
             "spx": ["-c:a", "libspeex", "-ar", "16000", "-f", "ogg"], "au": [], "snd": ["-f", "au"], "caf": [],
             "bwf": ["-f", "wav"], "w64": [], "rf64": ["-f", "wav", "-rf64", "always"], "voc": [],
             "weba": ["-c:a", "libopus", "-f", "webm"], "mmf": ["-ar", "8000", "-ac", "1"], "ra": ["-c:a", "real_144",
                                                                                                 "-ar", "8000", "-ac", "1",
                                                                                                 "-f", "rm"],
             "alac": ["-c:a", "alac", "-f", "ipod"], "3ga": ["-c:a", "aac", "-f", "3gp"], "awb": None, "amr": None}
    if ext in audio:
        if audio[ext] is None:
            return None
        return ff(tone + audio[ext], p)
    # ---- video
    vid = ["-f", "lavfi", "-i", "testsrc=size=320x240:rate=10:duration=1", "-f", "lavfi", "-i",
           "sine=duration=1", "-shortest"]
    video = {"mp4": [], "m4v": ["-f", "mp4"], "mov": [], "qt": ["-f", "mov"], "avi": [], "mkv": [], "mk3d": ["-f", "matroska"],
             "webm": [], "wmv": ["-c:v", "wmv2", "-c:a", "wmav2", "-f", "asf"], "asf": ["-c:v", "wmv2", "-c:a", "wmav2"],
             "flv": [], "f4v": ["-f", "mp4"], "swf": ["-c:v", "flv1", "-c:a", "libmp3lame", "-ar", "22050"],
             "mpg": [], "mpeg": [], "mpe": ["-f", "mpeg"], "m1v": ["-an", "-c:v", "mpeg1video", "-f", "mpeg1video"],
             "m2v": ["-an", "-c:v", "mpeg2video", "-f", "mpeg2video"], "vob": ["-f", "vob"], "ts": ["-f", "mpegts"],
             "m2ts": ["-f", "mpegts"], "mts": ["-f", "mpegts"], "3gp": ["-c:a", "aac"], "3g2": ["-c:a", "aac", "-f", "3g2"],
             "ogv": ["-c:v", "libtheora", "-c:a", "libvorbis"], "rm": ["-c:v", "rv10", "-c:a", "real_144", "-ar", "8000",
                                                                       "-ac", "1"],
             "divx": ["-c:v", "mpeg4", "-c:a", "libmp3lame", "-f", "avi"],
             "dv": ["-s", "720x576", "-r", "25", "-pix_fmt", "yuv420p", "-c:v", "dvvideo", "-ar", "48000", "-f", "dv"],
             "mxf": ["-c:v", "mpeg2video", "-c:a", "pcm_s16le", "-ar", "48000"],
             "h264": ["-an", "-c:v", "libx264", "-f", "h264"], "h265": ["-an", "-c:v", "libx265", "-f", "hevc"],
             "hevc": ["-an", "-c:v", "libx265", "-f", "hevc"], "y4m": ["-an"], "ivf": ["-an", "-c:v", "libvpx", "-f", "ivf"],
             "insv": ["-f", "mp4"], "lrv": ["-f", "mp4"], "360": ["-f", "mp4"], "evo": ["-f", "vob"], "vro": ["-f", "vob"],
             "rmvb": None, "bik": None, "dav": None}
    if ext in video:
        if video[ext] is None:
            return None
        return ff(vid + video[ext], p)
    # ---- tekst, code en data
    texts = {
        "txt": "Hello world.\nSecond line.\n", "log": "2026-11-05 10:00:00 INFO start\n2026-11-05 10:00:01 WARN done\n",
        "nfo": "╔══╗\n║AC║ Anything Converter\n╚══╝\n",
        "diz": "Anything Converter v2\n", "md": "# Title\n\nText with **bold**.\n\n- one\n- two\n",
        "markdown": "# Title\n\nText.\n", "mdx": "import X from './x'\n\n# Title\n\nText.\n",
        "rst": "Title\n=====\n\nText.\n", "adoc": "= Title\n\nText.\n", "org": "* Title\nText.\n",
        "tex": "\\documentclass{article}\\begin{document}Hello\\end{document}\n",
        "bib": "@book{x, title={Book}, year={2020}}\n", "1": ".TH EXAMPLE 1\n.SH NAME\nexample \\- test\n",
        "json": '{"name": "Anna", "age": 30, "hobby": ["reading", "cycling"]}',
        "json5": "// comment\n{name: 'x'}\n".replace("name", '"name"').replace("'x'", '"x"'),
        "jsonc": '{\n  // c\n  "a": 1,\n}\n', "jsonl": '{"a": 1}\n{"a": 2}\n', "ndjson": '{"a": 1}\n{"a": 2}\n',
        "jsonld": '{"@context": "https://schema.org", "name": "x"}', "webmanifest": '{"name": "App"}',
        "xml": "<?xml version='1.0'?><people><person id='1'><name>Anna</name></person><person id='2'><name>Bo</name></person></people>",
        "xsd": "<?xml version='1.0'?><xs:schema xmlns:xs='http://www.w3.org/2001/XMLSchema'><xs:element name='a'/></xs:schema>",
        "xsl": "<?xml version='1.0'?><xsl:stylesheet version='1.0' xmlns:xsl='http://www.w3.org/1999/XSL/Transform'/>",
        "xslt": "<?xml version='1.0'?><xsl:stylesheet version='1.0' xmlns:xsl='http://www.w3.org/1999/XSL/Transform'/>",
        "yaml": "name: Anna\nlist:\n  - a\n  - b\n", "yml": "a: 1\n", "toml": "[server]\nhost = 'x'\nport = 80\n",
        "ini": "[a]\nb = 1\n", "cfg": "[a]\nb = 1\n", "conf": "server_name example;\n", "properties": "a=1\nb=2\n",
        "env": "export A=1\nB=\"two\"\n", "csv": "name,age\nAnna,30\nBo,25\n", "tsv": "name\tage\nAnna\t30\n",
        "html": "<!doctype html><html><body><h1>Title</h1><p>Text</p></body></html>",
        "htm": "<html><body><p>Tekst</p></body></html>", "xhtml": "<html xmlns='http://www.w3.org/1999/xhtml'><body><p>x</p></body></html>",
        "shtml": "<html><body><p>x</p></body></html>",
        "srt": "1\n00:00:01,000 --> 00:00:02,500\nHello\n\n2\n00:00:03,000 --> 00:00:04,000\nThere\n",
        "vtt": "WEBVTT\n\n00:00:01.000 --> 00:00:02.500\nHello\n",
        "sbv": "0:00:01.000,0:00:02.500\nHello\n",
        "ass": "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize\nStyle: Default,Arial,20\n\n"
               "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
               "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n",
        "ssa": "[Script Info]\nScriptType: v4.00\n\n[V4 Styles]\nFormat: Name, Fontname, Fontsize\nStyle: Default,Arial,20\n\n"
               "[Events]\nFormat: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
               "Dialogue: Marked=0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hello\n", "lrc": "[00:01.00]First line\n[00:03.50]Second line\n",
        "sub": "{1}{1}25\n{25}{60}Hello|world\n",
        "ttml": "<?xml version='1.0'?><tt xmlns='http://www.w3.org/ns/ttml'><body><div><p begin='00:00:01.000' end='00:00:02.000'>Hello</p></div></body></tt>",
        "dfxp": "<?xml version='1.0'?><tt xmlns='http://www.w3.org/ns/ttml'><body><div><p begin='1s' end='2s'>Hello</p></div></body></tt>",
        "smi": "<SAMI><BODY><SYNC Start=1000><P>Hello<SYNC Start=2000><P>&nbsp;</BODY></SAMI>",
        "sami": "<SAMI><BODY><SYNC Start=1000><P>Hello<SYNC Start=2000><P>&nbsp;</BODY></SAMI>",
        "m3u": "#EXTM3U\n#EXTINF:120,Artiest - Nummer\nmuziek/nummer.mp3\n", "m3u8": "#EXTM3U\n#EXTINF:10,Deel\ndeel1.ts\n",
        "pls": "[playlist]\nFile1=a.mp3\nTitle1=A\nNumberOfEntries=1\n",
        "xspf": "<?xml version='1.0'?><playlist version='1' xmlns='http://xspf.org/ns/0/'><trackList><track><location>a.mp3</location><title>A</title></track></trackList></playlist>",
        "wpl": "<?wpl version='1.0'?><smil><body><seq><media src='a.mp3'/></seq></body></smil>",
        "asx": "<asx version='3.0'><entry><title>A</title><ref href='a.mp3'/></entry></asx>",
        "ram": "rtsp://example.com/stream.rm\n",
        "vcf": "BEGIN:VCARD\nVERSION:3.0\nFN:Anna de Vries\nTEL:+31612345678\nEMAIL:anna@example.com\nEND:VCARD\n",
        "ics": "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Overleg\nDTSTART:20261105T100000Z\nDTEND:20261105T110000Z\nLOCATION:Kantoor\nEND:VEVENT\nEND:VCALENDAR\n",
        "vcs": "BEGIN:VCALENDAR\nBEGIN:VEVENT\nSUMMARY:Oud\nDTSTART:20261105T100000\nEND:VEVENT\nEND:VCALENDAR\n",
        "gpx": "<?xml version='1.0'?><gpx version='1.1' xmlns='http://www.topografix.com/GPX/1/1'><trk><name>Rit</name><trkseg><trkpt lat='52.1' lon='5.1'><ele>3</ele></trkpt><trkpt lat='52.2' lon='5.2'><ele>4</ele></trkpt></trkseg></trk></gpx>",
        "kml": "<?xml version='1.0'?><kml xmlns='http://www.opengis.net/kml/2.2'><Document><Placemark><name>P</name><Point><coordinates>5.1,52.1</coordinates></Point></Placemark></Document></kml>",
        "geojson": '{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"name":"P"},"geometry":{"type":"Point","coordinates":[5.1,52.1]}}]}',
        "tcx": "<?xml version='1.0'?><TrainingCenterDatabase xmlns='http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2'><Activities><Activity><Lap><Track><Trackpoint><Position><LatitudeDegrees>52.1</LatitudeDegrees><LongitudeDegrees>5.1</LongitudeDegrees></Position></Trackpoint></Track></Lap></Activity></Activities></TrainingCenterDatabase>",
        "igc": "AXXX\nB1101355206343N00006198WA0058700558\nB1101455206400N00006200WA0058800560\n",
        "loc": "<?xml version='1.0'?><loc><waypoint><name id='GC1'>Schat</name><coord lat='52.1' lon='5.1'/></waypoint></loc>",
        "rss": "<?xml version='1.0'?><rss version='2.0'><channel><title>N</title><item><title>Bericht</title><link>https://x.nl</link><pubDate>Thu, 05 Nov 2026</pubDate></item></channel></rss>",
        "atom": "<?xml version='1.0'?><feed xmlns='http://www.w3.org/2005/Atom'><entry><title>Bericht</title><link href='https://x.nl'/><updated>2026-11-05</updated></entry></feed>",
        "opml": "<?xml version='1.0'?><opml version='2.0'><body><outline text='Nieuws' xmlUrl='https://x.nl/rss'><outline text='Sub'/></outline></body></opml>",
        "ofx": "OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST><STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261101<TRNAMT>-12.50<FITID>1<NAME>Bakker</STMTTRN></BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>",
        "qfx": "OFXHEADER:100\n<OFX><STMTTRN><DTPOSTED>20261101<TRNAMT>5.00<NAME>X</STMTTRN></OFX>",
        "qbo": "OFXHEADER:100\n<OFX><STMTTRN><DTPOSTED>20261101<TRNAMT>5.00<NAME>X</STMTTRN></OFX>",
        "qif": "!Type:Bank\nD11/01/2026\nT-12.50\nPBakker\n^\n",
        "sta": ":20:REF\n:25:NL01BANK0123456789\n:61:2611011101D12,50NTRFNONREF\n:86:Bakker Jansen\n",
        "940": ":20:REF\n:61:2611011101C100,00NTRFNONREF\n:86:Salaris\n",
        "cod": "0000005112600005        00000000  BANK                      000000000                       2\n"
               "21000100000000000001000000000001250000511260000100000000Bakker Jansen                                         05112600101 0\n",
        "har": '{"log":{"entries":[{"startedDateTime":"2026-11-05","time":12,"request":{"method":"GET","url":"https://x.nl"},"response":{"status":200,"content":{"size":10,"mimeType":"text/html"}}}]}}',
        "ipynb": '{"cells":[{"cell_type":"markdown","source":["# Title"]},{"cell_type":"code","source":["print(1)"],"outputs":[{"text":["1"]}]}],"metadata":{},"nbformat":4,"nbformat_minor":5}',
        "gv": "digraph G { a -> b; }\n", "puml": "@startuml\nA -> B\n@enduml\n", "mmd": "graph TD\nA-->B\n",
        "svg": "<svg xmlns='http://www.w3.org/2000/svg' width='100' height='60'><rect width='100' height='60' fill='#3a8'/><circle cx='50' cy='30' r='20' fill='#fd2'/></svg>",
        "eml": "From: a@x.nl\nTo: b@x.nl\nSubject: Test\nDate: Thu, 05 Nov 2026 10:00:00 +0100\nMIME-Version: 1.0\n"
               "Content-Type: multipart/mixed; boundary=XX\n\n--XX\nContent-Type: text/plain\n\nHello!\n--XX\n"
               "Content-Type: text/plain\nContent-Disposition: attachment; filename=bijlage.txt\n\nbijlage\n--XX--\n",
        "mbox": "From a@x.nl Thu Nov  5 10:00:00 2026\nFrom: a@x.nl\nSubject: Een\n\nHello\n\nFrom b@x.nl Thu Nov  5 11:00:00 2026\nFrom: b@x.nl\nSubject: Twee\n\nThere\n",
        "mhtml": "MIME-Version: 1.0\nContent-Type: multipart/related; boundary=B\n\n--B\nContent-Type: text/html\n\n<html><body><h1>Pagina</h1></body></html>\n--B--\n",
        "mht": "MIME-Version: 1.0\nContent-Type: multipart/related; boundary=B\n\n--B\nContent-Type: text/html\n\n<html><body><p>x</p></body></html>\n--B--\n",
        "url": "[InternetShortcut]\nURL=https://example.com\n", "desktop": "[Desktop Entry]\nName=X\nExec=x\n",
        "gdoc": '{"url": "https://docs.google.com/document/d/abc", "doc_id": "abc"}',
        "gsheet": '{"url": "https://docs.google.com/spreadsheets/d/abc"}', "gslides": '{"url": "https://docs.google.com/presentation/d/abc"}',
        "hex": ":10010000214601360121470136007EFE09D2190140\n:00000001FF\n",
        "gcode": "G21\nG90\nG1 X10 Y10 F3000\n", "md5": "d41d8cd98f00b204e9800998ecf8427e  leeg.txt\n",
        "patch": "--- a.txt\n+++ b.txt\n@@ -1 +1 @@\n-a\n+b\n",
        "fasta": ">seq1\nACGTACGT\n", "fastq": "@r1\nACGT\n+\nIIII\n", "pdb": "HEADER    EIWIT\nATOM      1  N   ALA A   1\n",
    }
    if ext in texts:
        p.write_text(texts[ext], encoding="utf-8")
        return p
    if ext == "webloc":
        import plistlib
        p.write_bytes(plistlib.dumps({"URL": "https://example.com"}))
        return p
    if ext == "plist":
        import plistlib
        p.write_bytes(plistlib.dumps({"name": "x", "list": [1, 2]}))
        return p
    if ext in ("npy", "npz"):
        import numpy as np
        (np.save if ext == "npy" else lambda f, a: np.savez(f, a=a))(str(p), np.arange(6).reshape(2, 3))
        return p
    if ext in ("sqlite", "sqlite3", "db", "db3"):
        con = sqlite3.connect(p)
        con.execute("create table people(name text, age int)")
        con.executemany("insert into people values(?,?)", [("Anna", 30), ("Bo", 25)])
        con.commit()
        con.close()
        return p
    if ext == "dbf":
        fields = [(b"NAAM", b"C", 10), (b"LEEFTIJD", b"N", 3)]
        recs = [(b"Anna", b"30"), (b"Bo", b"25")]
        hlen = 32 + 32 * len(fields) + 1
        rlen = 1 + sum(f[2] for f in fields)
        out = bytearray(struct.pack("<BBBBIHH20x", 3, 126, 11, 5, len(recs), hlen, rlen))
        for name, typ, size in fields:
            out += name.ljust(11, b"\0") + typ + b"\0" * 4 + bytes([size, 0]) + b"\0" * 14
        out += b"\x0d"
        for r in recs:
            out += b" " + r[0].ljust(10) + r[1].rjust(3)
        p.write_bytes(bytes(out) + b"\x1a")
        return p
    if ext == "mid" or ext == "midi" or ext == "kar":
        trk = bytes([0, 0xFF, 3, 5]) + b"Piano" + bytes([0, 0x90, 60, 100, 0x60, 0x80, 60, 0, 0, 0xFF, 0x2F, 0])
        p.write_bytes(b"MThd" + struct.pack(">IHHH", 6, 0, 1, 96) + b"MTrk" + struct.pack(">I", len(trk)) + trk)
        return p
    # ---- documenten via python-bibliotheken
    if ext in ("docx", "docm", "dotx", "dotm"):
        from docx import Document
        doc = Document()
        doc.add_heading("Title", 1)
        doc.add_paragraph("Text of the document.")
        doc.save(p)
        return p
    if ext in ("xlsx", "xlsm", "xltx", "xltm"):
        from openpyxl import Workbook
        wb = Workbook()
        wb.active.append(["name", "age"])
        wb.active.append(["Anna", 30])
        wb.save(p)
        return p
    if ext in ("pptx", "pptm", "ppsx", "potx", "potm", "ppsm"):
        from pptx import Presentation
        prs = Presentation()
        s = prs.slides.add_slide(prs.slide_layouts[1])
        s.shapes.title.text = "Dia"
        prs.save(p)
        return p
    if ext == "pdf":
        import fitz
        doc = fitz.open()
        doc.new_page().insert_text((72, 72), "Voorbeeld-PDF", fontsize=20)
        doc.save(p)
        return p
    if ext == "ai":
        make_sample("pdf", d).rename(p)
        return p
    if ext == "rtf":
        p.write_text(r"{\rtf1\ansi Hello {\b vet}\par wereld}", encoding="ascii")
        return p
    if ext in ("odt", "ods", "odp", "odg", "doc", "xls", "ppt", "ott", "ots", "otp", "sxw", "sxc", "sxi", "dot", "xlt",
               "pot", "pps", "xlsb", "slk", "dif", "wps", "wks", "wk1", "123", "vsd", "vsdx", "pub", "rtf-lo"):
        return _via_lo(ext, d)
    if ext == "svgz":
        p.write_bytes(gzip.compress(make_sample("svg", d).read_bytes()))
        return p
    if ext in ("eps", "ps"):
        if not shutil.which("gs"):
            return None
        pdf = make_sample("pdf", d)
        subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=" + ("eps2write" if ext == "eps" else "ps2write"),
                        f"-sOutputFile={p}", str(pdf)], capture_output=True, **NO_WINDOW)
        return p if p.exists() else None
    if ext in ("xps", "oxps"):
        return None
    if ext in ("emf", "wmf"):
        return _via_lo(ext, d)
    # ---- e-books
    if ext == "epub":
        from converter.ebook import write_epub
        t = d / "boek.txt"
        t.write_text("Hoofdstuk een.\n\nTweede alinea.")
        return write_epub(t, p)
    if ext == "fb2":
        p.write_text("<?xml version='1.0'?><FictionBook xmlns='http://www.gribuser.ru/xml/fictionbook/2.0'><description>"
                     "<title-info><book-title>Boek</book-title></title-info></description><body><section><title><p>Een</p>"
                     "</title><p>Tekst.</p></section></body></FictionBook>", encoding="utf-8")
        return p
    if ext in ("cbz", "cbt", "cb7"):
        pages = []
        for i in range(2):
            f = d / f"{i:02d}.jpg"
            img.save(f)
            pages.append(f)
        if ext == "cbz":
            with zipfile.ZipFile(p, "w") as z:
                for f in pages:
                    z.write(f, f.name)
        elif ext == "cbt":
            import tarfile
            with tarfile.open(p, "w") as t:
                for f in pages:
                    t.add(f, f.name)
        else:
            import py7zr
            with py7zr.SevenZipFile(p, "w") as z:
                for f in pages:
                    z.write(f, f.name)
        return p
    # ---- lettertypes
    if ext in ("ttf", "otf", "woff", "woff2", "ttc", "otc"):
        from fontTools.ttLib import TTCollection, TTFont
        src = ROOT / "static" / "fonts" / "ac-mono-Regular.woff2"
        f = TTFont(str(src))
        if ext in ("ttc", "otc"):
            f.flavor = None
            c = TTCollection()
            c.fonts = [f, TTFont(str(ROOT / "static" / "fonts" / "ac-mono-Bold.woff2"))]
            for x in c.fonts:
                x.flavor = None
            c.save(str(p))
            return p
        if ext == "otf" and "CFF " not in f:
            return None
        f.flavor = {"woff": "woff", "woff2": "woff2"}.get(ext)
        f.save(str(p))
        return p
    # ---- 3D en CAD
    if ext in ("stl", "obj", "ply", "glb", "off", "3mf", "dae", "xyz"):
        import trimesh
        box = trimesh.creation.box()
        try:
            box.export(str(p), file_type=ext)
            return p
        except Exception:  # noqa: BLE001
            return None
    if ext == "dxf":
        import ezdxf
        doc = ezdxf.new()
        msp = doc.modelspace()
        msp.add_line((0, 0), (100, 50))
        msp.add_circle((50, 25), 20)
        doc.saveas(p)
        return p
    # ---- certificaten
    if ext in ("pem", "crt", "cer", "der", "csr", "crl", "p7b", "p7c", "key", "pub"):
        return _cert(ext, p)
    if ext == "dcm":
        try:
            import numpy as np
            from pydicom.dataset import FileDataset, FileMetaDataset
            from pydicom.uid import ExplicitVRLittleEndian, generate_uid
            meta = FileMetaDataset()
            meta.MediaStorageSOPClassUID = "1.2.840.10008.5.1.4.1.1.7"
            meta.MediaStorageSOPInstanceUID = generate_uid()
            meta.TransferSyntaxUID = ExplicitVRLittleEndian
            ds = FileDataset(str(p), {}, file_meta=meta, preamble=b"\0" * 128)
            ds.Modality, ds.Rows, ds.Columns = "OT", 32, 32
            ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, "MONOCHROME2"
            ds.BitsAllocated, ds.BitsStored, ds.HighBit, ds.PixelRepresentation = 8, 8, 7, 0
            ds.PixelData = np.arange(1024, dtype="uint8").tobytes()
            ds.save_as(str(p), enforce_file_format=True)
            return p
        except Exception:  # noqa: BLE001
            return None
    # ---- archieven en compressie
    raw = b"Anything Converter " * 200
    comp = {"gz": lambda: gzip.compress(raw), "bz2": lambda: __import__("bz2").compress(raw),
            "xz": lambda: __import__("lzma").compress(raw), "lzma": lambda: __import__("lzma").compress(
                raw, format=__import__("lzma").FORMAT_ALONE),
            "zst": lambda: __import__("zstandard").ZstdCompressor().compress(raw),
            "lz4": lambda: __import__("lz4.frame").frame.compress(raw), "br": lambda: __import__("brotli").compress(raw)}
    if ext in comp:
        p.write_bytes(comp[ext]())
        return p
    if ext in ("zip", "jar", "war", "ear", "whl", "egg", "nupkg", "vsix", "xpi", "apk", "aab", "xapk", "apks", "apkm",
               "ipa", "appx", "msix", "appxbundle", "msixbundle", "zipx", "kmz", "sb3", "mcpack", "mcaddon", "mcworld",
               "osz", "osk", "pk3", "xmind", "ibooks", "3mf-zip", "ufp", "alp", "mogrt"):
        with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("readme.txt", "inhoud")
            if ext == "kmz":
                z.writestr("doc.kml", make_sample("kml", d).read_text())
            if ext in ("jar", "war", "ear"):
                z.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
            if ext in ("apk", "aab"):
                z.writestr("AndroidManifest.xml", "x")
            if ext == "ipa":
                z.writestr("Payload/App.app/Info.plist", "x")
        return p
    if ext in ("tar", "tgz", "tar.gz", "tbz2", "txz", "ova", "gem", "unitypackage", "tar.md5"):
        import tarfile
        mode = {"tgz": "w:gz", "tar.gz": "w:gz", "tbz2": "w:bz2", "txz": "w:xz", "unitypackage": "w:gz"}.get(ext, "w")
        f = d / "readme.txt"
        f.write_text("contents")
        with tarfile.open(p, mode) as t:
            t.add(f, "readme.txt")
        return p
    if ext in ("7z",):
        import py7zr
        f = d / "readme.txt"
        f.write_text("contents")
        with py7zr.SevenZipFile(p, "w") as z:
            z.write(f, "readme.txt")
        return p
    if ext == "deb":
        import tarfile
        def tar_bytes(name, data):
            b = io.BytesIO()
            with tarfile.open(fileobj=b, mode="w:gz") as t:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                t.addfile(info, io.BytesIO(data))
            return b.getvalue()
        members = [("debian-binary", b"2.0\n"), ("control.tar.gz", tar_bytes("control", b"Package: x\n")),
                   ("data.tar.gz", tar_bytes("usr/bin/x", b"#!/bin/sh\n"))]
        out = b"!<arch>\n"
        for name, data in members:
            out += f"{name:<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(data):<10}`\n".encode() + data + (b"\n" if len(data) % 2 else b"")
        p.write_bytes(out)
        return p
    if ext in ("uue", "uu"):
        import binascii
        data = b"Hello uuencode wereld\n"
        p.write_text("begin 644 hallo.txt\n" + binascii.b2a_uu(data).decode() + "`\nend\n")
        return p
    if ext in ("cpio", "iso", "cab", "wim", "rar", "xar", "dmg", "squashfs"):
        return _via_7z(ext, d)
    if ext in ("vhd", "vhdx", "vmdk", "vdi", "qcow2", "qcow"):
        if not shutil.which("qemu-img"):
            return None
        fmt = {"vhd": "vpc", "qcow": "qcow2"}.get(ext, ext)
        subprocess.run(["qemu-img", "create", "-f", fmt, str(p), "4M"], capture_output=True, **NO_WINDOW)
        return p if p.exists() else None
    # ---- overige binaire voorbeelden
    if ext == "torrent":
        p.write_bytes(b"d8:announce20:http://tracker.nl/a4:infod6:lengthi5e4:name8:test.txt12:piece lengthi16384e6:pieces20:"
                      + b"0" * 20 + b"ee")
        return p
    if ext in ("elf", "out", "so", "o"):
        shutil.copy(sys.executable if Path(sys.executable).exists() else "/bin/true", p)
        return p
    if ext == "gguf":
        def s(x):
            return struct.pack("<Q", len(x)) + x
        p.write_bytes(b"GGUF" + struct.pack("<IQQ", 3, 0, 1) + s(b"general.name") + struct.pack("<I", 8) + s(b"Testmodel"))
        return p
    if ext == "safetensors":
        hdr = json.dumps({"w": {"dtype": "F32", "shape": [2, 2], "data_offsets": [0, 16]}}).encode()
        p.write_bytes(struct.pack("<Q", len(hdr)) + hdr + b"\0" * 16)
        return p
    group = catalog()[ext][0][0] if ext in catalog() else ""
    if group in TEXT_GROUPS and ext not in BINARY_EXT:
        p.write_text(f"# example .{ext}\nname = \"value\"\n", encoding="utf-8")
        return p
    return None


TEXT_GROUPS = {"Programming (source code)", "Project files & build", "Infrastructure as Code", "Web",
               "Linux/Unix system", "Windows system & admin", "macOS system", "Network & IT", "Text & documents",
               "Electronics & firmware", "3D printing, CNC & laser", "Science & medical", "Photo editing & colour",
               "Video editing & VFX", "Data & configuration"}
BINARY_EXT = {"so", "a", "o", "ko", "out", "elf", "class", "pyc", "pyd", "wasm", "dll", "exe", "sys", "drv", "ocx", "cpl",
              "scr", "com", "efi", "mui", "nls", "msstyles", "evtx", "evt", "etl", "dmp", "mdmp", "hdmp", "edb", "sdb",
              "chk", "dylib", "kext", "scpt", "savedsearch", "textclipping", "swp", "nib", "lnk", "pif", "msc", "cat",
              "diagcab", "pol", "gadget", "one", "chm", "hlp", "dvi", "xmind", "mmap", "pcap", "pcapng", "cap", "pkt",
              "gns3", "uf2", "dfu", "bin", "bgcode", "x3g", "makerbot", "gx", "ctb", "cbddlp", "photon", "lys", "chitubox",
              "lbrn", "studio3", "pes", "dst", "jef", "fcstd", "dcm", "nii", "edf", "fits", "bam", "opj", "lrcat",
              "lrtemplate", "dcp", "cocatalog", "dop", "icc", "icm", "abr", "atn", "pat", "grd", "asl", "aco", "ase", "8bf",
              "prproj", "aep", "aet", "mogrt", "drp", "dra", "fcpbundle", "imovielibrary", "veg", "osp", "tscproj", "wfp",
              "wlmp", "avp", "aaf", "omf", "parquet", "avro", "orc", "feather", "arrow", "h5", "hdf5", "nc", "mat", "npy",
              "npz", "pkl", "pickle", "joblib", "rds", "rdata", "rda", "sav", "dta", "sas7bdat", "msgpack", "bson", "cbor",
              "pb", "photoslibrary", "xcarchive", "framework", "bundle", "prefpane", "saver", "app", "pages", "doc",
              "docx", "docm", "dot", "dotx", "dotm", "odt", "ott", "sxw", "wpd", "wps", "pdf", "xps", "oxps", "ps",
              "rtf", "enex", "canvas", "opml", "mm", "xlsx", "pid", "lock"}


def _via_lo(ext: str, d: Path) -> Path | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    base = {"odt": "docx", "ott": "docx", "sxw": "docx", "doc": "docx", "dot": "docx", "wps": "docx", "rtf-lo": "docx",
            "ods": "xlsx", "ots": "xlsx", "sxc": "xlsx", "xls": "xlsx", "xlt": "xlsx", "xlsb": "xlsx", "slk": "xlsx",
            "dif": "xlsx", "wks": "xlsx", "wk1": "xlsx", "123": "xlsx",
            "odp": "pptx", "otp": "pptx", "sxi": "pptx", "ppt": "pptx", "pot": "pptx", "pps": "pptx",
            "odg": "svg", "vsd": "svg", "vsdx": "svg", "pub": "docx", "emf": "svg", "wmf": "svg"}.get(ext)
    if not base:
        return None
    lo_dir = d / "_lo"
    lo_dir.mkdir(exist_ok=True)
    src = make_sample(base, lo_dir)
    filt = {"doc": "doc:MS Word 97", "dot": "dot:MS Word 97 Vorlage", "xls": "xls:MS Excel 97", "xlt": "xlt:MS Excel 97 Vorlage/Template",
            "ppt": "ppt:MS PowerPoint 97", "pot": "pot:MS PowerPoint 97 Vorlage", "pps": "pps:MS PowerPoint 97 AutoPlay",
            "sxw": "sxw:StarOffice XML (Writer)", "sxc": "sxc:StarOffice XML (Calc)", "sxi": "sxi:StarOffice XML (Impress)",
            "slk": "slk:SYLK", "dif": "dif:DIF", "xlsb": "xlsb:Calc MS Excel 2007 Binary", "wks": None, "wk1": None,
            "123": None, "wps": None, "vsd": None, "vsdx": None, "pub": None,
            "odg": "odg", "emf": "emf", "wmf": "wmf"}.get(ext, ext)
    if filt is None:
        return None
    out = d / "_lo_out"
    out.mkdir(exist_ok=True)
    subprocess.run([soffice, "--headless", "--convert-to", filt, "--outdir", str(out), str(src)], capture_output=True, **NO_WINDOW,
                   timeout=180)
    made = out / f"{src.stem}.{ext}"
    if made.exists():
        dst = d / f"sample.{ext}"
        shutil.move(str(made), dst)
        return dst
    return None


def _via_7z(ext: str, d: Path) -> Path | None:
    p = d / f"sample.{ext}"
    f = d / "readme.txt"
    f.write_text("contents")
    tool = shutil.which("7zz") or shutil.which("7z")
    if ext == "cpio":
        r = subprocess.run(f"cd {d} && echo readme.txt | cpio -o -H newc > {p}", shell=True, capture_output=True, **NO_WINDOW)
        return p if r.returncode == 0 and p.stat().st_size else None
    if ext == "iso" and shutil.which("xorriso"):
        subprocess.run(["xorriso", "-as", "mkisofs", "-o", str(p), str(f)], capture_output=True, **NO_WINDOW)
        return p if p.exists() else None
    if tool and ext in ("wim",):
        subprocess.run([tool, "a", f"-t{ext}", str(p), str(f)], capture_output=True, **NO_WINDOW)
        return p if p.exists() else None
    return None


def _cert(ext: str, p: Path) -> Path | None:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.serialization import pkcs7
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "sample.nl")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(1234).not_valid_before(now).not_valid_after(now + datetime.timedelta(days=30))
            .add_extension(x509.SubjectAlternativeName([x509.DNSName("sample.nl")]), False).sign(key, hashes.SHA256()))
    if ext in ("pem", "crt", "cer"):
        p.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    elif ext == "der":
        p.write_bytes(cert.public_bytes(serialization.Encoding.DER))
    elif ext == "csr":
        csr = x509.CertificateSigningRequestBuilder().subject_name(name).sign(key, hashes.SHA256())
        p.write_bytes(csr.public_bytes(serialization.Encoding.PEM))
    elif ext == "crl":
        crl = (x509.CertificateRevocationListBuilder().issuer_name(name).last_update(now)
               .next_update(now + datetime.timedelta(days=1)).sign(key, hashes.SHA256()))
        p.write_bytes(crl.public_bytes(serialization.Encoding.PEM))
    elif ext in ("p7b", "p7c"):
        p.write_bytes(pkcs7.serialize_certificates([cert], serialization.Encoding.DER))
    elif ext == "key":
        p.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                        serialization.NoEncryption()))
    elif ext == "pub":
        p.write_bytes(key.public_key().public_bytes(serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH)
                      + b" test@voorbeeld")
    return p


# --------------------------------------------------------------------------- testen



def make(ext: str, folder: Path | None = None) -> Path:
    """Make a sample .ext in its own new folder; raises ValueError when it cannot be made here."""
    ext = ext.lower().lstrip(".")
    if not re.fullmatch(r"[\w!.\-]{1,16}", ext):
        raise ValueError("Unknown file type.")
    d = Path(tempfile.mkdtemp(prefix="sample-", dir=folder))
    try:
        p = make_sample(ext, d)
    except Exception as e:  # noqa: BLE001
        p = None
        err = str(e)
    else:
        err = ""
    if not p or not p.exists():
        shutil.rmtree(d, ignore_errors=True)
        raise ValueError(f"No test file can be made for .{ext} on this computer{': ' + err if err else ''}.")
    for extra in d.iterdir():  # helper folders (_lo, _lo_out) and helper files are not part of the sample
        if extra.is_dir() and extra.name.startswith("_"):
            shutil.rmtree(extra, ignore_errors=True)
    return p
