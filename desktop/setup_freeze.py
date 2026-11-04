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
sys.path.insert(0, str(ROOT))  # zodat app.py en converter/ gevonden worden

VERSION = "2.1.0"
NAME = "Anything Converter"
ICONS = HERE / "icons"

include_files = [(str(ROOT / "static"), "static"), (str(ROOT / "vendor"), "vendor")]
for name in ("index.html", "favicon.svg", "favicon.png", "apple-touch-icon.png", "icon-192.png", "icon-512.png",
             "manifest.webmanifest"):
    include_files.append((str(ROOT / name), name))
if (HERE / "bin").is_dir() and any((HERE / "bin").iterdir()):
    include_files.append((str(HERE / "bin"), "bin"))

PACKAGES = ["converter", "flask", "werkzeug", "jinja2", "markupsafe", "itsdangerous", "click",
            "blinker", "PIL", "pikepdf", "yt_dlp", "yt_dlp_ejs", "certifi"]
OPTIONAL = {"pikepdf"}  # niet op elk platform beschikbaar

build_exe = {
    "packages": [p for p in PACKAGES if p not in OPTIONAL or importlib.util.find_spec(p)],
    "includes": ["app"],
    "include_files": include_files,
    "excludes": ["tkinter", "unittest", "pytest", "test", "pydoc_data", "cx_Freeze", "numpy", "fontTools",
                 "yaml", "matplotlib", "pandas", "scipy", "IPython", "setuptools", "pip"],
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
    )
]

options = {
    "build_exe": build_exe,
    "bdist_msi": {
        # Vaste upgrade-code: een nieuwe versie vervangt de oude netjes.
        "upgrade_code": "{6F0A8D52-3C1E-4B7A-9E2D-5A1C7B3E9F40}",
        "add_to_path": False,
        # Per gebruiker installeren: geen beheerdersrechten nodig.
        "all_users": False,
        "initial_target_dir": r"[LocalAppDataFolder]\Programs\Anything Converter",
        "install_icon": str(ICONS / "app.ico"),
        "summary_data": {"author": "Anything Converter", "comments": "Converteer, verklein, vergroot en knip bestanden"},
    },
    "bdist_mac": {
        "bundle_name": NAME,
        "iconfile": str(ICONS / "app.icns"),
        # Achtergrond-app zonder Dock-icoon; de interface draait in de browser.
        "plist_items": [("LSUIElement", True), ("CFBundleShortVersionString", VERSION),
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
