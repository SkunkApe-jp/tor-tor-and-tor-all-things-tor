#!/usr/bin/env python3
import os
import re
import time
from pathlib import Path
from collections import defaultdict

# Configuration
SCRAPED_DATA_DIR = "./scraped_data"
OUTPUT_FILE = "tor_mirror_bookmarks.html"

def get_grouped_onions():
    """
    Groups onion addresses by their discovered title.
    """
    groups = defaultdict(list)
    base_path = Path(SCRAPED_DATA_DIR)
    
    if not base_path.exists():
        print(f"[ERROR] {SCRAPED_DATA_DIR} not found.")
        return {}

    # Regex for onion validation
    onion_pattern = re.compile(r'^[a-z2-7]{1,56}$')

    for item in base_path.iterdir():
        if item.is_dir() and onion_pattern.match(item.name):
            addr = item.name
            title = addr # Fallback
            
            # Look for title file
            identity_dir = item / "website_identity"
            if identity_dir.exists():
                for title_file in identity_dir.glob("*_title.txt"):
                    try:
                        content = title_file.read_text(encoding='utf-8').strip()
                        match = re.search(r'\[(.*?)\]', content)
                        if match:
                            title = match.group(1).strip()
                            break
                    except: pass
            
            groups[title].append(f"http://{addr}.onion/")
    
    return groups

def generate_bookmark_file(groups):
    """
    Generates a Netscape-format bookmark file for Tor Browser.
    """
    timestamp = int(time.time())
    
    header = f"""<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file.
     It will be read and overwritten.
     DO NOT EDIT! -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'self'; script-src 'none'; img-src data: *; object-src 'none'"></meta>
<TITLE>Mirror Bookmarks</TITLE>
<H1>Mirror Discovery Bookmarks</H1>

<DL><p>
    <DT><H3 ADD_DATE="{timestamp}" LAST_MODIFIED="{timestamp}">Discovered Mirror Clusters</H3>
    <DL><p>
"""
    
    footer = """    </DL><p>
</DL>
"""

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(header)
        
        for title, onions in groups.items():
            # Sanitize title for HTML
            safe_title = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            
            # Create a folder for each Identity (Title)
            f.write(f'        <DT><H3 ADD_DATE="{timestamp}" LAST_MODIFIED="{timestamp}">{safe_title}</H3>\n')
            f.write('        <DL><p>\n')
            
            for url in onions:
                # Add individual mirror link
                # Note: We skip the base64 icons to keep the file size reasonable unless strictly needed.
                f.write(f'            <DT><A HREF="{url}" ADD_DATE="{timestamp}" LAST_MODIFIED="{timestamp}">{url}</A>\n')
            
            f.write('        </DL><p>\n')
            
        f.write(footer)

if __name__ == "__main__":
    print("[INIT] Generating Tor Mirror Bookmarks...")
    data = get_grouped_onions()
    if data:
        generate_bookmark_file(data)
        print(f"[SUCCESS] Bookmarks generated: {OUTPUT_FILE}")
        print("[INFO] You can now import this file into Tor Browser (Bookmarks > Manage > Import).")
    else:
        print("[WARN] No mirrors found to bookmark.")
