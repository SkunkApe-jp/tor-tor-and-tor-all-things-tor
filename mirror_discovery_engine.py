import os
import re
import json
from pathlib import Path
from collections import defaultdict

# Configuration
SCRAPED_DATA_DIR = "./scraped_data"
LOG_FILE = "./logs/unified_scraper.log"
OUTPUT_HTML = "mirror_discovery_portal.html"

def get_onion_intel():
    """
    Crawls local data to build a grouped index of mirrors.
    Groups by Title -> List of Onions with their metadata.
    """
    groups = defaultdict(list) # title -> list of {addr, img, status}
    base_path = Path(SCRAPED_DATA_DIR)
    
    if not base_path.exists():
        print(f"[ERROR] Directory {SCRAPED_DATA_DIR} not found.")
        return {}

    # 1. Index titles and group onions
    for item in base_path.iterdir():
        if item.is_dir() and (len(item.name) == 56 or len(item.name) == 16):
            addr = item.name
            
            # Fetch Title
            title = "Unknown Site"
            # We look for any title file in website_identity
            identity_dir = item / "website_identity"
            if identity_dir.exists():
                for title_file in identity_dir.glob("*_title.txt"):
                    try:
                        content = title_file.read_text(encoding='utf-8').strip()
                        # Extract part inside [ ]
                        title_match = re.search(r'\[(.*?)\]', content)
                        if title_match:
                            title = title_match.group(1).strip()
                            break 
                    except: pass

            # Fetch Image and Viz
            img_path = item / "images" / "index.png"
            rel_img = ""
            if img_path.exists():
                rel_img = f"scraped_data/{addr}/images/index.png"

            groups[title].append({
                "addr": addr,
                "url": f"http://{addr}.onion",
                "img": rel_img
            })
    
    return groups

def generate_portal(groups):
    # Prepare data for JS
    data_list = []
    for title, onions in groups.items():
        data_list.append({
            "title": title,
            "onions": onions,
            "count": len(onions)
        })
    
    # Sort by mirror count descending
    data_list.sort(key=lambda x: x['count'], reverse=True)

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mirror Discovery Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #050505;
            --accent: #6d5dfc;
            --text: #ffffff;
            --dim: #a0a0a0;
            --card: rgba(255, 255, 255, 0.03);
            --border: rgba(255, 255, 255, 0.1);
        }}

        body {{
            background: var(--bg);
            color: var(--text);
            font-family: 'Outfit', sans-serif;
            margin: 0; padding: 40px;
            display: flex; flex-direction: column; align-items: center;
        }}

        .container {{ width: 100%; max-width: 1100px; }}

        h1 {{
            font-size: 2.5rem; text-align: center;
            background: linear-gradient(135deg, #fff 0%, var(--accent) 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }}

        .search-section {{
            position: sticky; top: 0; z-index: 100;
            background: var(--bg); padding: 20px 0;
        }}

        input[type="text"] {{
            width: 100%; padding: 20px;
            background: rgba(255,255,255,0.05);
            border: 1px solid var(--border); border-radius: 12px;
            color: white; font-size: 1.1rem; outline: none;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}

        #masterLinkBox {{
            width: 100%; height: 180px;
            background: #000; border: 1px solid var(--accent);
            border-radius: 12px; color: #a0c4ff;
            font-family: 'Courier New', Courier, monospace;
            padding: 15px; margin-top: 15px;
            font-size: 0.9rem; resize: vertical;
        }}

        .label {{
            font-size: 0.7rem; color: var(--dim);
            text-transform: uppercase; letter-spacing: 2px;
            display: block; margin-top: 20px;
        }}

        #results {{ margin-top: 40px; display: grid; gap: 30px; }}

        .group-card {{
            background: var(--card); border: 1px solid var(--border);
            border-radius: 20px; padding: 0; overflow: hidden;
            display: flex; flex-direction: column;
            transition: 0.3s;
        }}

        .group-card:hover {{ border-color: var(--accent); }}

        .group-header {{
            padding: 25px; background: rgba(255,255,255,0.02);
            border-bottom: 1px solid var(--border);
            display: flex; justify-content: space-between; align-items: center;
        }}

        .group-title {{ font-size: 1.5rem; font-weight: 600; }}
        .badge {{ background: var(--accent); padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; }}

        .mirror-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 20px; padding: 25px;
        }}

        .onion-card {{
            background: rgba(0,0,0,0.3); border: 1px solid var(--border);
            border-radius: 12px; padding: 15px;
        }}

        .preview-img {{
            width: 100%; height: 120px; object-fit: cover;
            border-radius: 8px; margin-bottom: 10px;
            background: #111;
        }}

        .onion-addr {{
            font-family: monospace; font-size: 0.8rem;
            color: #6da5ff; text-decoration: none;
            overflow-wrap: break-word;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Mirror Discovery</h1>
        
        <div class="search-section">
            <span class="label">Keyword Filter</span>
            <input type="text" id="searchInput" placeholder="Search by mirrors or identity..." onkeyup="filter()">
            
            <span class="label">Master Mirror List (Copy-Paste)</span>
            <textarea id="masterLinkBox" readonly></textarea>
        </div>

        <div id="results"></div>
    </div>

    <script>
        const groups = {json.dumps(data_list)};

        function render(filtered) {{
            const results = document.getElementById('results');
            const linkBox = document.getElementById('masterLinkBox');
            results.innerHTML = "";
            let allLinks = [];

            filtered.forEach(group => {{
                const groupEl = document.createElement('div');
                groupEl.className = "group-card";
                
                let mirrorHtml = "";
                group.onions.forEach(onion => {{
                    allLinks.push(onion.url);
                    mirrorHtml += `
                        <div class="onion-card">
                            <img class="preview-img" src="${{onion.img}}" onerror="this.src='https://placehold.co/320x180?text=No+Preview'">
                            <a href="${{onion.url}}" class="onion-addr" target="_blank">${{onion.addr}}.onion</a>
                        </div>
                    `;
                }});

                groupEl.innerHTML = `
                    <div class="group-header">
                        <div class="group-title">${{group.title}}</div>
                        <div class="badge">${{group.count}} MIRRORS DETECTED</div>
                    </div>
                    <div class="mirror-grid">${{mirrorHtml}}</div>
                `;
                results.appendChild(groupEl);
            }});

            linkBox.value = allLinks.join('\\n');
        }}

        function filter() {{
            const q = document.getElementById('searchInput').value.toLowerCase();
            const filtered = groups.filter(g => 
                g.title.toLowerCase().includes(q) || 
                g.onions.some(o => o.addr.toLowerCase().includes(q))
            );
            render(filtered);
        }}

        render(groups);
    </script>
</body>
</html>"""
    with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html_template)
    print(f"[SUCCESS] Discovery Portal generated: {OUTPUT_HTML}")

if __name__ == "__main__":
    print("[INIT] Indexing mirrors by identity...")
    groups = get_onion_intel()
    generate_portal(groups)
