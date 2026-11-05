"""Set version, url and sha256 in bucket/anything-converter.json (used by the release workflow).

Usage: python desktop/update_scoop.py <version> <folder-with-AnythingConverter-Windows-portable.zip>
"""
import hashlib
import json
import sys
from pathlib import Path

MANIFEST = Path(__file__).resolve().parent.parent / "bucket" / "anything-converter.json"
ZIP = "AnythingConverter-Windows-portable.zip"


def main(version: str, folder: str) -> None:
    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    m["version"] = version
    arch = m["architecture"]["64bit"]
    arch["url"] = f"https://github.com/WikiDave/The-Anything-Converter/releases/download/v{version}/{ZIP}"
    arch["hash"] = hashlib.sha256((Path(folder) / ZIP).read_bytes()).hexdigest()
    MANIFEST.write_text(json.dumps(m, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
    print(MANIFEST.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
