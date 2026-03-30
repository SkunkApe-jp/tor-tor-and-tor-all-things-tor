#!/usr/bin/env python3
"""
Link Cleaner
Removes leading hyphens from lines in a single .txt file.
Useful for cleaning onion links or other URLs that may have "- " prefix.
Usage: python link_cleaner.py [input_file]
Default: cleans links.txt in current directory
"""

import os
import sys
from pathlib import Path

DEFAULT_INPUT = "links.txt"
BACKUP_SUFFIX = ".bak"


def clean_file(filepath):
    """Remove leading hyphens from each line in the file."""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned = []
    changes = 0
    for line in lines:
        original = line
        # Strip leading whitespace, hyphen, then more whitespace
        cleaned_line = line.lstrip().removeprefix("-").lstrip()
        if cleaned_line != line.lstrip():
            changes += 1
        # Preserve newline and any trailing content
        if line.endswith("\n"):
            cleaned.append(cleaned_line + "\n")
        else:
            cleaned.append(cleaned_line)

    # Backup original
    backup_path = str(filepath) + BACKUP_SUFFIX
    os.rename(filepath, backup_path)

    # Write cleaned content
    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(cleaned)

    return changes, backup_path


def main():
    print("=" * 50)
    print("Link Cleaner - Remove leading hyphens")
    print("=" * 50)

    # Get input file from command line or use default
    input_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT

    print(f"\nCleaning: {input_file}\n")

    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found!")
        print(f"Usage: python {sys.argv[0]} [input_file]")
        print(f"Default: {DEFAULT_INPUT}")
        return 1

    changes, backup = clean_file(Path(input_file))

    if changes > 0:
        print(f"  ✓ Cleaned {changes} lines")
        print(f"  ✓ Backup created: {os.path.basename(backup)}")
    else:
        print(f"  - No changes needed")

    print("\nDone!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
