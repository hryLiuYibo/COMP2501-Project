# -*- coding: utf-8 -*-
"""Pre-push sanity check: no absolute paths, no personal identifiers, no secrets."""
import os
import re
import sys

PATTERNS = [
    (r"C:\\Users", "absolute Windows path"),
    (r"C:/Users", "absolute Windows path"),
    (r"25912", "username fragment"),
    (r"OneDrive", "OneDrive path"),
    (r"WorkBuddy", "local app path"),
    (r"Desktop[\\/]work", "local desktop path"),
    (r"(?i)api[_-]?key\s*=\s*[\"'][^\"']{8,}", "possible API key"),
    (r"(?i)password\s*=\s*[\"'][^\"']+", "possible password"),
    (r"(?i)secret\s*=\s*[\"'][^\"']+", "possible secret"),
    (r"(?i)token\s*=\s*[\"'][A-Za-z0-9_\-]{16,}", "possible token"),
]
EXT = (".py", ".R", ".md", ".txt", ".csv", ".json", ".toml", ".cfg", ".gitignore", ".yml", ".yaml")

root = os.path.dirname(os.path.abspath(__file__))
if os.path.basename(root) == "scripts":
    root = os.path.dirname(root)

hits = 0
scanned = 0
SKIP = {"_prepush_check.py"}
for base, dirs, files in os.walk(root):
    dirs[:] = [d for d in dirs if d not in (".git", "__pycache__", ".Rproj.user")]
    for f in files:
        if not f.endswith(EXT) or f in SKIP:
            continue
        p = os.path.join(base, f)
        scanned += 1
        try:
            lines = open(p, encoding="utf-8", errors="ignore").read().splitlines()
        except OSError as e:
            print(f"  [skip] {p}: {e}")
            continue
        for i, line in enumerate(lines, 1):
            for pat, label in PATTERNS:
                if re.search(pat, line):
                    # numeric data files can contain any digit run by chance
                    if label == "username fragment" and f.endswith(".csv"):
                        continue
                    rel = os.path.relpath(p, root)
                    print(f"  {rel}:{i}  [{label}]  {line.strip()[:96]}")
                    hits += 1

print(f"\nscanned {scanned} files, {hits} hit(s)")
sys.exit(1 if hits else 0)
