#!/usr/bin/env python3
"""
Bookmark Generator
Reads links from an input file and generates a bookmark.html file.
Place your links in links.txt (one URL per line, optional title after URL separated by space/tab)
"""

import os
import sys
from datetime import datetime

INPUT_FILE = "links.txt"
OUTPUT_FILE = "bookmarks.html"


def parse_links(input_file):
    links = []
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found!")
        print("Create a links.txt file with one URL per line.")
        print("Optional: Add a title after each URL separated by space or tab")
        print("Example:")
        print("  https://example.com Example Site")
        print("  https://another.com")
        return None

    with open(input_file, "r", encoding="utf-8") as f:
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


def generate_bookmark_html(links):
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
    html += f'    <DT><H3 ADD_DATE="{int(datetime.now().timestamp())}">My Bookmarks - {timestamp}</H3>\n'
    html += "    <DL><p>\n"

    for url, title in links:
        html += f'        <DT><A HREF="{url}" ADD_DATE="{int(datetime.now().timestamp())}">{title}</A>\n'

    html += "    </DL><p>\n"
    html += "</DL><p>\n"

    return html


def main():
    print("=" * 50)
    print("Bookmark Generator")
    print("=" * 50)

    links = parse_links(INPUT_FILE)

    if links is None:
        return 1

    if not links:
        print("No valid links found in input file.")
        return 1

    html = generate_bookmark_html(links)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Generated {OUTPUT_FILE} with {len(links)} bookmarks")
    print("Open the file in your browser and bookmark it!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
