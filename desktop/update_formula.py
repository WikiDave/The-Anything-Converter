"""Puts the version and sha256 values in Formula/anything-converter.rb (used by the release workflow).

Usage: python desktop/update_formula.py <version> <folder-with-tar.gz-files>
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

    original = FORMULA.read_text()
    old_urls = re.findall(r'url "([^"]+)"\n\s*sha256 "([0-9a-f]{64})"', original)

    def fill(m: re.Match) -> str:
        name = m.group(2)
        f = Path(folder) / name
        if not f.is_file():  # this release has no build for it: keep the previous download
            prev = next((u, h) for u, h in old_urls if u.endswith("/" + name))
            print(f"warning: {name} not in this release; keeping {prev[0]}", file=sys.stderr)
            return f'url "{prev[0]}"\n{m.group(3)}sha256 "{prev[1]}"'
        digest = hashlib.sha256(f.read_bytes()).hexdigest()
        return f'{m.group(1)}{name}"\n{m.group(3)}sha256 "{digest}"'

    text, n = re.subn(r'(url "[^"]*/)([^/"]+\.tar\.gz)"\n(\s*)sha256 "[0-9a-f]{64}"', fill, text)
    assert n == 4, f"expected 4 downloads, found {n}"
    FORMULA.write_text(text)
    print(text)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
