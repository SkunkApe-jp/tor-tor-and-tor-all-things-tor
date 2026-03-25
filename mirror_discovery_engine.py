#!/usr/bin/env python3
import os
import re
import json
import time
from pathlib import Path
from collections import defaultdict

# --- CONFIGURATION ---
SCRAPED_DATA_DIR = "./scraped_data"
PORTAL_HTML_FILE = "mirror_discovery_portal.html"
BOOKMARK_FILE = "tor_mirror_bookmarks.html"

def get_mirror_intelligence():
    """
    Crawls local data to define mirrors.
    RULE: Identical content inside [brackets] in website_identity/index_title.txt = MIRROR.
    """
    mirror_groups = defaultdict(list)
    base_path = Path(SCRAPED_DATA_DIR)
    
    # 1. Gather Mirror Intel
    if not base_path.exists():
        print(f"[ERROR] {SCRAPED_DATA_DIR} not found.")
        return {}

    # Valid onion address (v2/v3)
    onion_pattern = re.compile(r'^[a-z2-7]{16}$|^[a-z2-7]{56}$')

    for item in base_path.iterdir():
        if item.is_dir():
            addr = item.name
            # Simplified title extraction as per user requirement
            title = addr # Fallback
            
            title_file = item / "website_identity" / "index_title.txt"
            if title_file.exists():
                try:
                    content = title_file.read_text(encoding='utf-8').strip()
                    # Rule: find part inside [ ]
                    match = re.search(r'\[(.*?)\]', content)
                    if match:
                        title = match.group(1).strip()
                except: pass
            
            # Metadata for current target
            img_path = item / "images" / "index.png"
            rel_img = ""
            if img_path.exists():
                rel_img = f"scraped_data/{addr}/images/index.png"

            mirror_groups[title].append({
                "address": addr,
                "url": f"http://{addr}.onion/",
                "image": rel_img
            })
            
    return mirror_groups

def generate_discovery_portal(groups):
    """
    Outputs the High-End Search Portal for mirror lists.
    """
    data_list = []
    for title, onions in groups.items():
        data_list.append({"title": title, "onions": onions, "count": len(onions)})
    
    data_list.sort(key=lambda x: x['count'], reverse=True)
    json_data = json.dumps(data_list)
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mirror Discovery & Zero-In Tool</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --bg: #030303;
            --accent: #6d5dfc;
            --glass: rgba(255, 255, 255, 0.04);
            --border: rgba(255, 255, 255, 0.1);
            --text: #ffffff;
            --dim: #777;
        }}

        body, html {{
            margin: 0; padding: 0; min-height: 100vh;
            background-color: var(--bg); color: var(--text);
            font-family: 'Outfit', sans-serif;
            overflow-x: hidden;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
        }}

        #mainFrame {{
            width: 100%; max-width: 90%;
            text-align: center;
            transition: all 0.3s;
        }}

        #mainFrame.searched {{
            transform: translateY(-20vh);
        }}

        h1 {{
            font-size: 3rem; margin-bottom: 50px;
            background: linear-gradient(135deg, #fff 0%, var(--accent) 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}

        .search-area {{
            width: 100%; max-width: 800px; margin: 0 auto;
            background: var(--glass); backdrop-filter: blur(20px);
            border: 1px solid var(--border); border-radius: 60px;
            padding: 8px 30px; display: flex; align-items: center;
        }}

        #searchInput {{
            background: transparent; border: none; outline: none;
            color: white; font-size: 1.4rem; width: 100%; padding: 15px;
            font-family: 'Outfit', sans-serif;
        }}

        #loader {{ display: none; margin-top: 50px; flex-direction: column; align-items: center; }}
        .spinner {{
            width: 40px; height: 40px; border: 3px solid rgba(255,255,255,0.05);
            border-top: 3px solid var(--accent); border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

        .result-box {{
            display: none; width: 100%; margin-top: 60px;
            background: var(--glass); border: 1px solid var(--border);
            border-radius: 30px; padding: 50px;
            animation: slideUp 0.5s ease-out;
        }}

        .link-paragraph {{
            font-family: 'JetBrains Mono', monospace; font-size: 1.1rem;
            line-height: 2.5; text-align: center; color: #6da5ff;
        }}

        .link-paragraph a {{
            color: #6da5ff; text-decoration: none; border-bottom: 1px solid transparent;
            margin: 0 10px; transition: 0.2s;
        }}

        .link-paragraph a:hover {{ color: white; border-color: white; }}

        .meta-zero {{
            margin-bottom: 40px; font-size: 0.8rem; color: var(--dim);
            letter-spacing: 2px; text-transform: uppercase;
        }}

        @keyframes slideUp {{ from {{ opacity: 0; transform: translateY(40px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    </style>
</head>
<body>
    <div id="mainFrame">
        <h1>Mirror Discovery</h1>
        
        <div class="search-area">
            <i class="fas fa-search" style="opacity: 0.3; font-size: 1.4rem;"></i>
            <input type="text" id="searchInput" placeholder="Zero-in on identities..." autocomplete="off">
        </div>

        <div id="loader">
            <div class="spinner"></div>
            <p style="margin-top: 20px; color: var(--accent); font-size: 0.7rem;">CALCULATING MIRROR CLUSTERS...</p>
        </div>

        <div id="resultBox" class="result-box">
            <div class="meta-zero" id="metaZero"></div>
            <div class="link-paragraph" id="lp"></div>
        </div>
    </div>

    <script>
        const database = {json_data};
        const searchInput = document.getElementById('searchInput');
        const mainFrame = document.getElementById('mainFrame');
        const loader = document.getElementById('loader');
        const resultBox = document.getElementById('resultBox');
        const lp = document.getElementById('lp');
        const metaZero = document.getElementById('metaZero');

        let debounce = null;

        searchInput.addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase().trim();
            clearTimeout(debounce);

            if (query.length === 0) {{
                mainFrame.classList.remove('searched');
                loader.style.display = 'none';
                resultBox.style.display = 'none';
                return;
            }}

            mainFrame.classList.add('searched');
            resultBox.style.display = 'none';
            loader.style.display = 'flex';

            debounce = setTimeout(() => {{
                processSearch(query);
            }}, 800);
        }});

        function processSearch(q) {{
            loader.style.display = 'none';
            let uniqueOnions = new Set();
            let matchedTitles = [];

            for (const item of database) {{
                if (item.title.toLowerCase().includes(q) || item.onions.some(o => o.address.toLowerCase().includes(q))) {{
                    matchedTitles.push(item.title);
                    item.onions.forEach(o => uniqueOnions.add(o.url));
                }}
            }}

            if (uniqueOnions.size > 0) {{
                resultBox.style.display = 'block';
                metaZero.innerText = `Zeroed In: ${{uniqueOnions.size}} Mirrors Found`;
                lp.innerHTML = Array.from(uniqueOnions).map(url => {{
                    return `<a href="${{url}}" target="_blank">${{url}}</a>`;
                }}).join(' ');
            }} else {{
                resultBox.style.display = 'block';
                metaZero.innerText = "No mirrors detected";
                lp.innerHTML = "<span style='color:var(--dim)'>Try a partial identity title or onion string.</span>";
            }}
        }}
    </script>
</body>
</html>
"""
    with open(PORTAL_HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

def generate_bookmarks(groups):
    """
    Outputs the Netscape Bookmark file for Tor.
    """
    ts = int(time.time())
    
    header = f"""<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Mirror Bookmarks</TITLE>
<H1>Bookmarks Menu</H1>
<DL><p>
    <DT><H3 ADD_DATE="{ts}" LAST_MODIFIED="{ts}">Mirror Identity Clusters</H3>
    <DL><p>"""
    
    with open(BOOKMARK_FILE, 'w', encoding='utf-8') as f:
        f.write(header)
        for title, onions in groups.items():
            safe_title = title.replace("&", "&amp;").replace("<", "&lt;")
            f.write(f'        <DT><H3 ADD_DATE="{ts}" LAST_MODIFIED="{ts}">{safe_title}</H3>\n')
            f.write('        <DL><p>\n')
            for onion in onions:
                f.write(f'            <DT><A HREF="{onion["url"]}" ADD_DATE="{ts}">{onion["url"]}</A>\n')
            f.write('        </DL><p>\n')
        f.write('    </DL><p>\n</DL>\n')

if __name__ == "__main__":
    print("[INIT] Mirror Discovery Engine Starting...")
    intel = get_mirror_intelligence()
    if intel:
        print(f"[PROCESS] Indexed {len(intel)} Unique Identities.")
        generate_discovery_portal(intel)
        generate_bookmarks(intel)
        print(f"[SUCCESS] Mirror Portal ready: {PORTAL_HTML_FILE}")
        print(f"[SUCCESS] Mirror Bookmarks ready: {BOOKMARK_FILE}")
    else:
        print("[WARN] No data found in scraped_data.")
