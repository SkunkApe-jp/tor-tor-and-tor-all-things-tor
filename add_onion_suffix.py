#!/usr/bin/env python3
"""
Onion Suffix Adder
Adds .onion suffix to each line in a text file.
Usage: python add_onion_suffix.py [input_file]
Default: processes links.txt in current directory
Output: creates [filename]_onion.txt
"""

import os
import sys
from pathlib import Path

DEFAULT_INPUT = "links.txt"
SUFFIX = ".onion"


def read_file_with_encoding(filepath):
    """Try multiple encodings to read the file."""
    encodings = ['utf-8-sig', 'utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1', 'cp1252']
    
    for enc in encodings:
        try:
            with open(filepath, "r", encoding=enc) as f:
                content = f.read()
            return content, enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    raise UnicodeDecodeError(f"Could not decode file with any known encoding: {filepath}")


def add_suffix(filepath):
    """Add .onion suffix to each non-empty line."""
    content, detected_enc = read_file_with_encoding(filepath)
    lines = content.splitlines(keepends=True)

    processed = []
    for line in lines:
        stripped = line.rstrip('\r\n')
        if stripped:
            processed_line = stripped + SUFFIX + "\n"
            processed.append(processed_line)
        else:
            processed.append(line)

    # Output filename
    stem = Path(filepath).stem
    output_path = str(Path(filepath).with_name(f"{stem}_onion.txt"))

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(processed)

    return output_path, len([l for l in lines if l.strip()]), detected_enc


def main():
    print("=" * 50)
    print("Onion Suffix Adder")
    print("=" * 50)

    input_file = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_INPUT

    print(f"\nProcessing: {input_file}\n")

    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found!")
        print(f"Usage: python {sys.argv[0]} [input_file]")
        print(f"Default: {DEFAULT_INPUT}")
        return 1

    output_path, line_count, detected_enc = add_suffix(input_file)

    print(f"  ✓ Detected encoding: {detected_enc}")
    print(f"  ✓ Processed {line_count} lines")
    print(f"  ✓ Output: {os.path.basename(output_path)}")
    print("\nDone!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
