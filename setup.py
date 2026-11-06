"""Build hook for pip / pipx: copies the app's own files into the package (converter/_res) so a wheel holds
everything: app.py, tui.py, the web interface (static/), the browser version (index.html, vendor/), icons, VERSION
and the window code. Configuration is in pyproject.toml."""
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

HERE = Path(__file__).resolve().parent
FILES = ["app.py", "tui.py", "VERSION", "index.html", "favicon.svg", "favicon.png", "apple-touch-icon.png",
         "icon-192.png", "icon-512.png", "manifest.webmanifest", "desktop/launcher.py", "desktop/window.py"]
DIRS = ["static", "vendor"]


class BuildWithResources(build_py):
    def run(self):
        super().run()
        res = Path(self.build_lib) / "converter" / "_res"
        for f in FILES:
            if (HERE / f).is_file():
                (res / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(HERE / f, res / f)
        for d in DIRS:
            if (HERE / d).is_dir():
                shutil.copytree(HERE / d, res / d, dirs_exist_ok=True,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))


setup(cmdclass={"build_py": BuildWithResources})
