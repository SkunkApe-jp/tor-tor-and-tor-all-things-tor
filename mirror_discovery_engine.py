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

def get_mirror_intelligence():
    """
    Crawls local data to define mirrors.
    RULE: Identical content inside [brackets] in website_identity/index_title.txt = MIRROR.
    """
    mirror_groups = defaultdict(list)
    base_path = Path(SCRAPED_DATA_DIR)
    
    if not base_path.exists():
        print(f"[ERROR] {SCRAPED_DATA_DIR} not found.")
        return {}

    onion_pattern = re.compile(r'^[a-z2-7]{16}$|^[a-z2-7]{56}$')

    for item in base_path.iterdir():
        if item.is_dir():
            addr = item.name
            title = addr # Fallback
            
            title_file = item / "website_identity" / "index_title.txt"
            if title_file.exists():
                try:
                    content = title_file.read_text(encoding='utf-8').strip()
                    match = re.search(r'\[(.*?)\]', content)
                    if match:
                        title = match.group(1).strip()
                except: pass
            
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
    Outputs the High-End Search Portal for mirror lists, including the Dynamic Bookmark Generator.
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
            display: flex; flex-direction: column; align-items: center; justify-content: flex-start;
        }}

        #mainFrame {{
            width: 100%; max-width: 1100px; padding-top: 25vh;
            text-align: center;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        #mainFrame.searched {{
            padding-top: 5vh;
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

        #loader {{ display: none; margin-top: 80px; flex-direction: column; align-items: center; }}
        .spinner {{
            width: 50px; height: 50px; border: 3px solid rgba(255,255,255,0.05);
            border-top: 3px solid var(--accent); border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

        .result-box {{
            display: none; width: 100%; margin-top: 50px; padding-bottom: 100px;
            animation: slideUp 0.5s ease-out;
        }}

        /* Clean Link Paragraph */
        .link-paragraph {{
            background: var(--glass); border: 1px solid var(--border);
            border-radius: 20px; padding: 40px; margin-bottom: 40px;
            font-family: 'JetBrains Mono', monospace; font-size: 0.95rem;
            line-height: 3; text-align: center; color: #6da5ff;
        }}

        .link-paragraph a {{
            color: #6da5ff; text-decoration: none; 
            display: inline-block; white-space: nowrap; margin: 0 12px;
            transition: 0.2s; border-bottom: 1px solid transparent;
        }}

        .link-paragraph a:hover {{ color: white; border-color: white; transform: scale(1.02); }}

        /* Meta header with Bookmark Button */
        .meta-header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; padding: 0 20px;
        }}
        
        .meta-zero {{
            font-size: 0.9rem; color: var(--dim);
            letter-spacing: 2px; text-transform: uppercase;
        }}

        .btn-bookmark {{
            background: transparent; border: 1px solid var(--border);
            color: white; padding: 10px 20px; border-radius: 8px;
            font-family: 'Outfit', sans-serif; cursor: pointer;
            transition: 0.3s;
        }}

        .btn-bookmark:hover {{
            background: var(--glass); border-color: var(--accent);
            box-shadow: 0 0 15px rgba(109, 93, 252, 0.2);
        }}

        /* Image Grid High Performance */
        .img-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px; margin-top: 20px;
        }}

        .grid-item {{
            border-radius: 12px; overflow: hidden; border: 1px solid var(--border);
            background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center;
            transition: 0.3s;
        }}
        
        .grid-item:hover {{
            border-color: var(--accent); transform: scale(1.02);
            box-shadow: 0 15px 30px rgba(0,0,0,0.5);
        }}

        .grid-item img {{
            width: 100%; height: 160px; object-fit: cover; display: block;
        }}
        
        .grid-title {{
            position: absolute; bottom: 0; left: 0; right: 0;
            background: rgba(0,0,0,0.8); padding: 10px;
            font-size: 0.8rem; text-align: center;
            opacity: 0; transition: 0.3s;
        }}
        
        .grid-item:hover .grid-title {{ opacity: 1; }}

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
            <p style="margin-top: 20px; color: var(--accent); font-size: 0.7rem; letter-spacing: 2px;">CALCULATING MIRROR CLUSTERS...</p>
        </div>

        <div id="resultBox" class="result-box">
            <div class="meta-header">
                <div class="meta-zero" id="metaZero"></div>
                <button class="btn-bookmark" onclick="downloadBookmark()"><i class="fas fa-bookmark" style="margin-right:8px"></i>Export Mirror Bookmarks</button>
            </div>
            
            <div class="link-paragraph" id="lp"></div>
            <div class="img-grid" id="imgGrid"></div>
        </div>
    </div>

    <script>
        const database = {json_data};
        const searchInput = document.getElementById('searchInput');
        const mainFrame = document.getElementById('mainFrame');
        const loader = document.getElementById('loader');
        const resultBox = document.getElementById('resultBox');
        const lp = document.getElementById('lp');
        const imgGrid = document.getElementById('imgGrid');
        const metaZero = document.getElementById('metaZero');

        let debounce = null;
        let currentMatches = []; // Store matches to generate bookmarks dynamically

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
            currentMatches = [];
            let uniqueOnions = new Set();
            let imagesHtml = '';

            for (const item of database) {{
                if (item.title.toLowerCase().includes(q) || item.onions.some(o => o.address.toLowerCase().includes(q))) {{
                    currentMatches.push(item);
                    
                    item.onions.forEach(o => {{
                        uniqueOnions.add(o.url);
                        if (o.image) {{
                            imagesHtml += `
                                <a href="${{o.image}}" target="_blank" class="grid-item" style="position:relative;">
                                    <img src="${{o.image}}" loading="lazy" alt="Mirror Screenshot">
                                    <div class="grid-title">${{item.title}}<br><span style="color:var(--dim); font-size:10px;">${{o.address}}.onion</span></div>
                                </a>
                            `;
                        }}
                    }});
                }}
            }}

            if (uniqueOnions.size > 0) {{
                resultBox.style.display = 'block';
                metaZero.innerText = `Zeroed In: ${{uniqueOnions.size}} Mirrors Found`;
                
                // Render as inline-blocks to prevent breaking words
                lp.innerHTML = Array.from(uniqueOnions).map(url => {{
                    return `<a href="${{url}}" target="_blank">${{url}}</a>`;
                }}).join(' ');
                
                imgGrid.innerHTML = imagesHtml;
            }} else {{
                resultBox.style.display = 'block';
                metaZero.innerText = "No mirrors detected";
                lp.innerHTML = "<span style='color:var(--dim)'>Try a partial identity title or onion string.</span>";
                imgGrid.innerHTML = "";
            }}
        }}

        // Dynamic Bookmark Generator
        function downloadBookmark() {{
            if (currentMatches.length === 0) return;
            
            const ts = Math.floor(Date.now() / 1000);
            
            // Build Netscape Bookmark Format
            // Top level is the HTML structure
            let html = `<!DOCTYPE NETSCAPE-Bookmark-file-1>
<!-- This is an automatically generated file. -->
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks Menu</H1>
<DL><p>\n`;

            // Each group's title becomes a folder, containing its mirrors
            currentMatches.forEach(group => {{
                const safeTitle = group.title.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                html += `    <DT><H3 ADD_DATE="${{ts}}" LAST_MODIFIED="${{ts}}">${{safeTitle}}</H3>\n`;
                html += `    <DL><p>\n`;
                
                group.onions.forEach(onion => {{
                    html += `        <DT><A HREF="${{onion.url}}" ADD_DATE="${{ts}}">${{onion.url}}</A>\n`;
                }});
                
                html += `    </DL><p>\n`;
            }});

            html += `</DL><p>\n`;

            // Trigger secure browser download
            const blob = new Blob([html], {{ type: 'text/html' }});
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Tor_Mirrors_${{ts}}.html`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }}
    </script>
</body>
</html>
"""
    with open(PORTAL_HTML_FILE, 'w', encoding='utf-8') as f:
        f.write(html)

if __name__ == "__main__":
    print("[INIT] Mirror Discovery Engine Starting...")
    intel = get_mirror_intelligence()
    if intel:
        print(f"[PROCESS] Indexed {len(intel)} Unique Identities.")
        generate_discovery_portal(intel)
        print(f"[SUCCESS] Mirror Portal ready: {PORTAL_HTML_FILE}")
    else:
        print("[WARN] No data found in scraped_data.")
