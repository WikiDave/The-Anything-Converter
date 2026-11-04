"""Bouwt de vertalingen in index.html in.

Elke taal staat in <taal>.txt: één regel per tekst, in dezelfde volgorde als KEYS in keys.py
(de Nederlandse brontekst). {0}, {1} ... zijn plekken voor getallen of namen en moeten blijven staan.

Gebruik (vanuit de projectmap):  python i18n/build.py
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from keys import KEYS  # noqa: E402

LANGS = ["en", "de", "es", "fr", "pt", "ru", "tr", "id", "ar", "hi", "bn", "zh", "ja"]


def main() -> None:
    data = {"keys": KEYS}
    for lang in LANGS:
        lines = (HERE / f"{lang}.txt").read_text(encoding="utf-8").rstrip("\n").split("\n")
        if len(lines) != len(KEYS):
            raise SystemExit(f"{lang}.txt heeft {len(lines)} regels, verwacht {len(KEYS)}")
        for k, v in zip(KEYS, lines):
            if sorted(re.findall(r"\{\d\}", k)) != sorted(re.findall(r"\{\d\}", v)):
                raise SystemExit(f"{lang}: plekken kloppen niet bij {k!r} -> {v!r}")
        data[lang] = lines
    page = HERE.parent / "index.html"
    html = page.read_text(encoding="utf-8")
    new = "const I18N = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";"
    html, n = re.subn(r"^const I18N = .*;$", lambda m: new, html, count=1, flags=re.M)
    if n != 1:
        raise SystemExit("regel 'const I18N = ...;' niet gevonden in index.html")
    page.write_text(html, encoding="utf-8")
    print(f"index.html bijgewerkt: {len(LANGS)} talen × {len(KEYS)} teksten")


if __name__ == "__main__":
    main()
