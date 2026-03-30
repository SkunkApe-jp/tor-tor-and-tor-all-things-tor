#!/usr/bin/env python3
"""
Bookmark Generator
Reads .txt files from an input folder and generates bookmark.html with nested folders.
Each .txt file becomes a folder, with links grouped into batches of 10 in sub-folders.
"""

import os
import sys
from datetime import datetime
from pathlib import Path

INPUT_FOLDER = "links"
OUTPUT_FILE = "bookmarks.html"
LINKS_PER_FOLDER = 10


def parse_txt_file(filepath):
    """Parse a single .txt file and return list of (url, title) tuples."""
    links = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(None, 1)
            url = parts[0]
            title = parts[1] if len(parts) > 1 else url

            if (
                url.startswith("http://")
                or url.startswith("https://")
                or url.startswith("file://")
            ):
                links.append((url, title))
    return links


def collect_links_from_folder(folder_path):
    """
    Collect all links from .txt files in the folder.
    Returns dict: {filename_without_ext: [(url, title), ...]}
    """
    if not os.path.exists(folder_path):
        print(f"Error: Folder '{folder_path}' not found!")
        print(f"Create a folder named '{folder_path}' and put your .txt files in it.")
        return None

    all_files = {}
    txt_files = list(Path(folder_path).glob("*.txt"))

    if not txt_files:
        print(f"No .txt files found in '{folder_path}'")
        return None

    for txt_file in sorted(txt_files):
        links = parse_txt_file(txt_file)
        if links:
            folder_name = txt_file.stem
            all_files[folder_name] = links
            print(f"  ✓ {txt_file.name}: {len(links)} links")

    return all_files


def generate_bookmark_html(file_links_map):
    """Generate bookmark HTML with nested folder structure."""
    html = """<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks</H1>
<DL><p>
"""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    main_folder_name = f"Imported Bookmarks - {timestamp}"
    html += f'    <DT><H3 ADD_DATE="{int(datetime.now().timestamp())}">{main_folder_name}</H3>\n'
    html += "    <DL><p>\n"

    for folder_name, links in sorted(file_links_map.items()):
        # Create folder for this .txt file
        html += f'        <DT><H3 ADD_DATE="{int(datetime.now().timestamp())}">{folder_name}</H3>\n'
        html += "        <DL><p>\n"

        # Split links into batches of LINKS_PER_FOLDER
        total_links = len(links)
        num_batches = (total_links + LINKS_PER_FOLDER - 1) // LINKS_PER_FOLDER

        for batch_idx in range(num_batches):
            start = batch_idx * LINKS_PER_FOLDER
            end = min(start + LINKS_PER_FOLDER, total_links)
            batch_links = links[start:end]

            # Create sub-folder name like "Links 1-10", "Links 11-20"
            batch_folder_name = f"Links {start + 1}-{end}"
            html += f'            <DT><H3 ADD_DATE="{int(datetime.now().timestamp())}">{batch_folder_name}</H3>\n'
            html += "            <DL><p>\n"

            # Add links in this batch
            for url, title in batch_links:
                html += f'                <DT><A HREF="{url}" ADD_DATE="{int(datetime.now().timestamp())}">{title}</A>\n'

            html += "            </DL><p>\n"

        html += "        </DL><p>\n"

    html += "    </DL><p>\n"
    html += "</DL><p>\n"

    return html


def main():
    print("=" * 50)
    print("Bookmark Generator")
    print("=" * 50)
    print(f"\nReading .txt files from: ./{INPUT_FOLDER}/")
    print(f"Links per sub-folder: {LINKS_PER_FOLDER}\n")

    file_links_map = collect_links_from_folder(INPUT_FOLDER)

    if file_links_map is None:
        return 1

    if not file_links_map:
        print("No valid links found in any files.")
        return 1

    # Count totals
    total_files = len(file_links_map)
    total_links = sum(len(links) for links in file_links_map.values())

    html = generate_bookmark_html(file_links_map)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nGenerated {OUTPUT_FILE}")
    print(f"  - {total_files} folders (from .txt files)")
    print(f"  - {total_links} total links")
    print(f"\nOpen the file in your browser and import it!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
