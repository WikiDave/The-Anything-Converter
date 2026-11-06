"""Bouwt de desktop-app met cx_Freeze.

Gebruik (vanuit de projectmap):
    python desktop/setup_freeze.py build_exe       # alleen de programmamap
    python desktop/setup_freeze.py bdist_msi       # Windows-installer
    python desktop/setup_freeze.py bdist_dmg       # macOS-schijfkopie
    python desktop/setup_freeze.py bdist_appimage  # Linux AppImage

Leg vooraf ffmpeg, ffprobe en deno in desktop/bin/ (de GitHub-workflow doet dat automatisch);
ze komen dan mee in de app.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from cx_Freeze import Executable, setup

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path[:0] = [str(ROOT), str(HERE)]  # app.py, converter/ en window.py

# Eén bron voor het versienummer; de workflow schrijft het bij een release.
VERSION = (ROOT / "VERSION").read_text().strip()
NAME = "Anything Converter"
ICONS = HERE / "icons"

include_files = [(str(ROOT / "static"), "static"), (str(ROOT / "vendor"), "vendor"), (str(ROOT / "VERSION"), "VERSION")]
for name in ("index.html", "favicon.svg", "favicon.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png",
             "manifest.webmanifest"):
    include_files.append((str(ROOT / name), name))
if (HERE / "bin").is_dir() and any((HERE / "bin").iterdir()):
    include_files.append((str(HERE / "bin"), "bin"))
# Programmavenster (pywebview). Als bronbestand naast het programma: op Linux start de systeem-Python
# het (die heeft de GTK/WebKit-koppeling), met pywebview als bronbestanden in pyweb/.
include_files.append((str(HERE / "window.py"), "window.py"))
# catalogus met omschrijvingen van ~1000 formaten (gelezen door converter/catalog.py)
include_files.append((str(ROOT / "converter" / "formaten.txt"), "lib/converter/formaten.txt"))


def pkg_dir(name: str) -> Path | None:
    spec = importlib.util.find_spec(name)
    if not spec or not spec.origin:
        return None
    origin = Path(spec.origin)
    return origin.parent if origin.name == "__init__.py" else origin


# Gegevensbestanden die cx_Freeze niet vanzelf meeneemt (JavaScript, .NET-DLL's).
for pkg, sub in (("webview", "js"), ("webview", "lib"), ("clr_loader", "ffi"), ("pythonnet", "runtime")):
    d = pkg_dir(pkg)
    if d and (d / sub).is_dir() and (sub != "lib" or sys.platform == "win32"):
        include_files.append((str(d / sub), f"lib/{pkg}/{sub}"))
if sys.platform.startswith("linux"):
    for pkg in ("webview", "proxy_tools", "bottle", "typing_extensions"):
        d = pkg_dir(pkg)
        if d:
            include_files.append((str(d), "pyweb/" + d.name))

PACKAGES = ["converter", "textual", "rich", "flask", "werkzeug", "jinja2", "markupsafe", "itsdangerous", "click",
            "blinker", "PIL", "pikepdf", "yt_dlp", "yt_dlp_ejs", "certifi", "libtorrent",
            "webview", "proxy_tools", "bottle", "typing_extensions",
            # PDF-gereedschap, Office-bestanden, 7z, spraakherkenning
            "pymupdf", "fitz", "docx", "openpyxl", "pptx", "lxml", "py7zr", "numpy", "pywhispercpp", "yaml",
            # bestandsformaten uit de catalogus
            "rawpy", "pillow_heif", "fontTools", "brotli", "trimesh", "ezdxf", "pydicom", "extract_msg", "tnefparse",
            "cryptography", "asn1crypto", "fitdecode", "zstandard", "lz4", "pefile", "pygments"]
if sys.platform == "win32":
    PACKAGES += ["clr_loader", "pythonnet", "winrt"]  # winrt: Windows-tekstherkenning
elif sys.platform == "darwin":
    PACKAGES += ["objc", "AppKit", "Foundation", "WebKit", "PyObjCTools", "UniformTypeIdentifiers", "Vision", "Quartz"]
# niet op elk platform beschikbaar
OPTIONAL = {"pikepdf", "libtorrent", "UniformTypeIdentifiers", "pywhispercpp", "winrt", "Vision", "Quartz", "rawpy",
            "pillow_heif", "extract_msg", "tnefparse", "fitdecode", "zstandard", "lz4", "brotli"}

build_exe = {
    "packages": [p for p in PACKAGES if p not in OPTIONAL or importlib.util.find_spec(p)],
    "includes": ["app", "window"] + (["clr"] if sys.platform == "win32" else [])
                + (["_pywhispercpp"] if importlib.util.find_spec("_pywhispercpp") else []),
    "include_files": include_files,
    "excludes": ["tkinter", "unittest", "pytest", "test", "pydoc_data", "cx_Freeze", "matplotlib", "pandas", "scipy", "IPython", "setuptools", "pip"],
    "include_msvcr": True,
    "optimize": 1,
}

if sys.platform == "win32":
    icon = str(ICONS / "app.ico")
    base = "gui"  # geen consolevenster
elif sys.platform == "darwin":
    icon = str(ICONS / "app.icns")
    base = None
else:
    icon = str(ICONS / "app.png")
    base = None

executables = [
    Executable(
        script=str(HERE / "launcher.py"),
        base=base,
        target_name="AnythingConverter",
        icon=icon,
        shortcut_name=NAME,
        shortcut_dir="ProgramMenuFolder",
        copyright="Anything Converter",
    ),
    # Terminalversie: zelfde layout in Windows Terminal/PowerShell, bash/zsh en via SSH.
    Executable(
        script=str(ROOT / "tui.py"),
        base=None,  # console-programma
        target_name="anything-converter-tui",
        icon=icon,
        shortcut_name=NAME + " (terminal)",
        shortcut_dir="ProgramMenuFolder",
        copyright="Anything Converter",
    ),
]

options = {
    "build_exe": build_exe,
    "bdist_msi": {
        # Vaste upgrade-code: een nieuwe versie vervangt de oude netjes.
        "upgrade_code": "{6F0A8D52-3C1E-4B7A-9E2D-5A1C7B3E9F40}",
        # installatiemap in het PATH: dan werkt 'anything-converter-tui' in elke terminal
        "add_to_path": True,
        # Per gebruiker installeren: geen beheerdersrechten nodig.
        "all_users": False,
        "initial_target_dir": r"[LocalAppDataFolder]\Programs\Anything Converter",
        "install_icon": str(ICONS / "app.ico"),
        # Right-click any file > "Convert with Anything Converter" (Windows 11: under "Show more options").
        # In the MSI's own Registry table, so uninstalling removes it again. Root -1 = HKCU for this
        # per-user install.
        "data": {"Registry": [
            ("AcShell", -1, r"Software\Classes\*\shell\AnythingConverter", None,
             "Convert with Anything Converter", "TARGETDIR"),
            ("AcShellIcon", -1, r"Software\Classes\*\shell\AnythingConverter", "Icon",
             "[TARGETDIR]AnythingConverter.exe", "TARGETDIR"),
            ("AcShellCmd", -1, r"Software\Classes\*\shell\AnythingConverter\command", None,
             '"[TARGETDIR]AnythingConverter.exe" "%1"', "TARGETDIR"),
        ]},
        "summary_data": {"author": "Anything Converter", "comments": "Converteer, verklein, vergroot en knip bestanden"},
    },
    "bdist_mac": {
        "bundle_name": NAME,
        "iconfile": str(ICONS / "app.icns"),
        # Gewone app met eigen venster, Dock-icoon en menubalk.
        "plist_items": [("CFBundleShortVersionString", VERSION), ("NSHighResolutionCapable", True),
                        ("NSHumanReadableCopyright", "Anything Converter")],
        "codesign_identity": "-",  # ad-hoc ondertekenen (nodig op Apple Silicon)
        "codesign_deep": True,
    },
    "bdist_dmg": {
        "volume_label": NAME,
        "applications_shortcut": True,
    },
    "bdist_appimage": {
        "target_name": "AnythingConverter",
    },
}

setup(
    name="AnythingConverter",
    version=VERSION,
    description="Converteer, verklein, vergroot en knip bestanden",
    options=options,
    executables=executables,
)
