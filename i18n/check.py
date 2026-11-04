import re, sys
from keys import KEYS
for lang in sys.argv[1:]:
    lines = open(f"{lang}.txt", encoding="utf-8").read().rstrip("\n").split("\n")
    ok = len(lines) == len(KEYS)
    bad = [(i, KEYS[i], l) for i, (k, l) in enumerate(zip(KEYS, lines))
           if sorted(re.findall(r"\{\d\}", k)) != sorted(re.findall(r"\{\d\}", l))
           or (k.startswith("//") != l.startswith("//")) or (k.startswith("[") != l.startswith("["))]
    print(f"{lang}: {len(lines)}/{len(KEYS)} regels", "OK" if ok and not bad else "FOUT")
    for b in bad[:8]: print("   ", b)
