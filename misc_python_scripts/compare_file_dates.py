import os
from datetime import datetime
from pathlib import Path
from collections import defaultdict

folder = Path("misc_python_scripts")
py_files = [f for f in folder.glob("**/*.py") if "venv" not in str(f)]

print(f"{'File':<45} {'Created':<25} {'Modified':<25} {'Path'}")
print("=" * 110)

by_name = defaultdict(list)
for f in py_files:
    created = datetime.fromtimestamp(f.stat().st_ctime).strftime("%Y-%m-%d %H:%M:%S")
    modified = datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    rel_path = f.relative_to(folder)
    print(f"{f.name:<45} {created:<25} {modified:<25} {rel_path}")
    by_name[f.name].append(rel_path)

print("\n" + "=" * 110)
print("POTENTIAL DUPLICATES (same filename in different locations):")
print("=" * 110)
for name, paths in sorted(by_name.items()):
    if len(paths) > 1:
        print(f"\n{name}:")
        for p in paths:
            print(f"  - {p}")
