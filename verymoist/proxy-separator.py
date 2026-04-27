#!/usr/bin/env python3
"""
DeepScan | Onion Link Splitter (v2)
Separates clean .onion links from proxied (.onion.ly, etc.) while preserving http/https.
"""

import re
import sys
import argparse
from pathlib import Path

# Captures optional http/https + the hash + .onion + any proxy suffixes (strips paths)
URL_PATTERN_STRIP = r'((?:https?://)?[a-z2-7]{14,56}\.onion(?:\.[a-z0-9.]+)*)'
# Captures full URL including sub-paths
URL_PATTERN_KEEP = r'((?:https?://)?[a-z2-7]{14,56}\.onion(?:\.[a-z0-9.]+)*[^\s]*)'

def process_file(input_path, keep_paths=False):
    path = Path(input_path)
    if not path.exists():
        print(f"[-] Error: File '{input_path}' not found.")
        return None, None

    print(f"[*] Scanning {input_path}...")
    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    
    clean_onions = set()
    proxied_onions = set()

    for line in lines:
        # Clean up YAML syntax: dashes, spaces, and quotes
        line = line.strip().lstrip('- ').strip('"').strip("'")
        
        pattern = URL_PATTERN_KEEP if keep_paths else URL_PATTERN_STRIP
        match = re.search(pattern, line, re.IGNORECASE)
        if match:
            full_url = match.group(1)
            
            # Logic: If it ends exactly in .onion, it's clean. 
            # If there's a suffix like .ly or .sh, it's proxied.
            if full_url.lower().endswith('.onion'):
                clean_onions.add(full_url)
            else:
                proxied_onions.add(full_url)

    return sorted(list(clean_onions)), sorted(list(proxied_onions))

def main():
    parser = argparse.ArgumentParser(description="Split onion links into Clean and Proxied files.")
    parser.add_argument("--keep-paths", action="store_true", help="Preserve sub-paths in extracted URLs (e.g., /path/to/page)")
    args = parser.parse_args()

    clean, proxied = process_file(args.input, keep_paths=args.keep_paths)
    if clean is None: return

    # Define output paths
    clean_out = Path("clean_onions.txt")
    proxy_out = Path("proxied_onions.txt")

    clean_out.write_text("\n".join(clean))
    proxy_out.write_text("\n".join(proxied))

    print("\n" + "="*35)
    print(f" EXTRACTED FROM: {args.input}")
    print("="*35)
    print(f" Clean .onion URLs    : {len(clean)}")
    print(f" Proxied onion URLs   : {len(proxied)}")
    print("-"*35)
    print(f" [SAVED] -> {clean_out}")
    print(f" [SAVED] -> {proxy_out}")
    print("="*35 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 onion_splitter.py <file_to_scan>")
    else:
        main()
