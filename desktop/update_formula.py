"""Zet versie en sha256-waarden in Formula/anything-converter.rb (gebruikt door de release-workflow).

Gebruik: python desktop/update_formula.py <versie> <map-met-tar.gz-bestanden>
"""
import hashlib
import re
import sys
from pathlib import Path

FORMULA = Path(__file__).resolve().parent.parent / "Formula" / "anything-converter.rb"


def main(version: str, folder: str) -> None:
    text = FORMULA.read_text()
    text = re.sub(r'version "[^"]+"', f'version "{version}"', text)
    text = re.sub(r"/download/v[^/]+/", f"/download/v{version}/", text)

    def fill(m: re.Match) -> str:
        name = m.group(2)
        digest = hashlib.sha256((Path(folder) / name).read_bytes()).hexdigest()
        return f'{m.group(1)}{name}"\n{m.group(3)}sha256 "{digest}"'

    text, n = re.subn(r'(url "[^"]*/)([^/"]+\.tar\.gz)"\n(\s*)sha256 "[0-9a-f]{64}"', fill, text)
    assert n == 3, f"verwachtte 3 downloads, vond {n}"
    FORMULA.write_text(text)
    print(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
