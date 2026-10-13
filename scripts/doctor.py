#!/usr/bin/env python3
"""Read-only installation diagnostics using only the standard library."""
import importlib.util
import shutil
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

def main():
    failures = []
    def check(label, ok, remedy):
        print(f"{'OK' if ok else 'MISSING'}: {label}")
        if not ok:
            failures.append(remedy)
    print(f"Python: {sys.executable}\nProject: {ROOT}")
    check("Python 3.10+", sys.version_info >= (3, 10), "Install Python 3.10+ and recreate .venv.")
    for module in ("PIL", "reportlab", "pypdf", "astronomy"):
        check(module, importlib.util.find_spec(module) is not None, "Activate .venv and run python -m pip install -r requirements.txt.")
    catalogs = ('stars.6.json', 'starnames.json', 'constellations.lines.json',
                'constellations.borders.json', 'constellations.json', 'targets.json')
    check("Bundled astronomy catalogs", all((ROOT / 'data' / 'catalogs' / name).is_file() for name in catalogs), "Restore the project's data/catalogs/ directory.")
    try:
        ZoneInfo("America/Chicago")
        zone_ok = True
    except Exception:
        zone_ok = False
    check("Timezone data", zone_ok, "Run python -m pip install tzdata.")
    for tool in ("pdftoppm",):
        print(f"{'OK' if shutil.which(tool) else 'OPTIONAL MISSING'}: {tool}")
    for remedy in dict.fromkeys(failures):
        print(f"Fix: {remedy}")
    print("Installation ready." if not failures else "Resolve missing requirements before building.")
    return 2 if failures else 0

if __name__ == "__main__":
    raise SystemExit(main())
