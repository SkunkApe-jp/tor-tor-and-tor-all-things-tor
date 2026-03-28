#!/usr/bin/env python3
import os
import re
import argparse
from pathlib import Path

# --- CONFIGURATION ---
SCRAPED_DATA_DIR = "./scraped_data"
TARGETS_YAML = "targets.yaml"


def extract_onions_from_file(file_path):
    """
    Scans a single file for all unique onion addresses.
    Matches v2 (16 chars) and v3 (56 chars), including subdomains and subpaths.
    Returns full URLs (subdomain.onion/path).
    """
    onions = set()

    # Patterns that capture subdomains, v2/v3 onions, and subpaths
    # v3: 56-char base32 with optional subdomains like sub.domain.abc123....onion/path
    v3_pattern = re.compile(r'https?://([a-z0-9-]+\.)*[a-z2-7]{56}\.onion(:[0-9]+)?(/[^\s"\'<>]*)?', re.IGNORECASE)
    # v2: 16-char base32 with optional subdomains
    v2_pattern = re.compile(r'https?://([a-z0-9-]+\.)*[a-z2-7]{16}\.onion(:[0-9]+)?(/[^\s"\'<>]*)?', re.IGNORECASE)
    # Also match onion addresses without protocol (just the domain)
    bare_v3_pattern = re.compile(r'([a-z0-9-]+\.)*[a-z2-7]{56}\.onion(:[0-9]+)?(/[^\s"\'<>]*)?', re.IGNORECASE)
    bare_v2_pattern = re.compile(r'([a-z0-9-]+\.)*[a-z2-7]{16}\.onion(:[0-9]+)?(/[^\s"\'<>]*)?', re.IGNORECASE)

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

            for pattern in [v3_pattern, v2_pattern, bare_v3_pattern, bare_v2_pattern]:
                for match in pattern.finditer(content):
                    full = match.group(0).lower()
                    # Ensure it has protocol for consistency
                    if not full.startswith('http'):
                        full = 'http://' + full
                    onions.add(full)
    except Exception as e:
        print(f"[!] Warning: Could not read {file_path}: {e}")

    return onions


def harvest_onions(directory):
    """
    Crawls the directory to find HTML files and extracts onions.
    """
    all_discovered = set()
    base_path = Path(directory)

    if not base_path.exists():
        print(f"[ERROR] {directory} not found.")
        return set()

    print(f"[*] Scanning {directory} for HTML files...")

    # Search for all .html files (index.html, etc)
    for html_file in base_path.rglob("*.html"):
        # Skip files in the .system or engine-generated folders
        if "mirror_discovery" in html_file.name or ".system" in str(html_file):
            continue

        found = extract_onions_from_file(html_file)
        if found:
            all_discovered.update(found)

    return all_discovered


def update_targets_yaml(new_onions):
    """
    Reads existing targets.yaml and appends only unique new URLs.
    """
    existing_onions = set()
    targets_path = Path(TARGETS_YAML)

    if targets_path.exists():
        try:
            with open(targets_path, "r", encoding="utf-8") as f:
                for line in f:
                    # Clean up: remove yaml marker "-", whitespace, and trailing slashes
                    clean = line.strip().replace("-", "").strip().rstrip("/")
                    if clean:
                        existing_onions.add(clean.lower())
        except Exception as e:
            print(f"[!] Error reading {TARGETS_YAML}: {e}")

    to_add = []
    for o in new_onions:
        o_clean = o.rstrip("/")
        if o_clean.lower() not in existing_onions:
            to_add.append(o_clean)

    if not to_add:
        print("[*] No new unique onions discovered.")
        return

    # Sort for tidiness
    to_add.sort()

    try:
        with open(targets_path, "a", encoding="utf-8") as f:
            for url in to_add:
                f.write(f"- {url}\n")
        print(f"[SUCCESS] Added {len(to_add)} new unique target(s) to {TARGETS_YAML}.")
    except Exception as e:
        print(f"[ERROR] Could not write to {TARGETS_YAML}: {e}")


def print_onions(onions):
    """Print discovered onions to stdout."""
    if not onions:
        print("[!] No onions found.")
        return

    sorted_onions = sorted(onions)
    for o in sorted_onions:
        print(o)
    print(f"\n[*] Total: {len(sorted_onions)} onion(s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Harvest .onion links from scraped HTML and add them to targets.yaml"
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="HTML file(s) to scan for onion addresses",
    )
    parser.add_argument(
        "--input",
        default=SCRAPED_DATA_DIR,
        help="Directory containing HTML files (default: ./scraped_data)",
    )
    parser.add_argument(
        "--file", help="Scan a specific HTML file (legacy, use positional args instead)"
    )
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print results to stdout instead of appending to targets.yaml",
    )
    args = parser.parse_args()

    discovered = set()

    # Handle positional file arguments
    if args.files:
        for html_file in args.files:
            if os.path.isfile(html_file):
                print(f"[*] Harvesting from: {html_file}")
                discovered.update(extract_onions_from_file(html_file))
            else:
                print(f"[!] File not found: {html_file}")
    # Handle legacy --file option
    elif args.file:
        print(f"[*] Harvesting from single file: {args.file}")
        discovered = extract_onions_from_file(args.file)
    else:
        discovered = harvest_onions(args.input)

    if discovered:
        print(f"[*] Found {len(discovered)} total onion links.")
        if args.print:
            print_onions(discovered)
        else:
            update_targets_yaml(discovered)
    else:
        print("[!] No onions found.")
