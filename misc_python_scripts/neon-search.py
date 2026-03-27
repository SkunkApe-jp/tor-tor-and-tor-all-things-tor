#!/usr/bin/env python3
import os
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict

# Pre-compiled regex for onion address validation (supports sub-domains like blog.xyz)
ONION_PATTERN = re.compile(r'^[a-z0-9_.-]{1,100}$')

def parse_full_intelligence(log_path, scraped_dir, output_path):
    """
    Crawls local data to build a searchable index with:
    - Titles from website_identity/index_title.txt
    - Screenshots from images/index.png
    - Existing Viz from visualizations/addr_viz.html
    - Reliability history from unified_scraper.log
    """
    onion_index = {}
    base_scraped = Path(scraped_dir)
    output_dir = os.path.dirname(os.path.abspath(output_path))
    
    # 1. Gather Site Intelligence
    if base_scraped.exists():
        for item in base_scraped.iterdir():
            if item.is_dir() and ONION_PATTERN.match(item.name):
                addr = item.name
                title_dir = item / "website_identity"
                images_dir = item / "images"
                viz_root = item / "visualizations"
                
                # Each onion site can have multiple scraped paths with their own titles
                # We will index every *_title.txt file found
                if title_dir.exists():
                    for title_file in title_dir.glob("*_title.txt"):
                        try:
                            # Extract path-key from filename (e.g., 'archives_art_Wallpapers_Cityscapes_title.txt' -> 'archives_art_Wallpapers_Cityscapes')
                            path_key = title_file.name.replace("_title.txt", "")
                            
                            # Read Title
                            content = title_file.read_text(encoding='utf-8', errors='ignore').strip()
                            title = addr # Fallback
                            title_match = re.search(r'\[(.*?)\]', content)
                            if title_match:
                                title = title_match.group(1).strip()
                            else:
                                title = content.split('\n')[0].strip()

                            # Extract sub-path if present in the tile file content
                            # Format: [Title] -> http://.../[sub-path]
                            actual_url = f"http://{addr}.onion"
                            url_match = re.search(r'->\s*(http[s]?://[^\s]+)', content)
                            if url_match:
                                actual_url = url_match.group(1).strip()

                            # Corresponding Image and Viz
                            img_file = images_dir / f"{path_key}.png"
                            # Also check generic 'index.png' if this is the root
                            if not img_file.exists() and path_key == "index":
                                img_file = images_dir / "index.png"
                                
                            # 1. Look for unique specific path viz first (addr_path_viz.html)
                            viz_file = viz_root / f"{addr}_{path_key}_viz.html"
                            # 2. Fallback to generic onion viz (addr_viz.html)
                            if not viz_file.exists():
                                viz_file = viz_root / f"{addr}_viz.html"
                            # 3. Last resort fallback
                            if not viz_file.exists():
                                viz_file = viz_root / f"{path_key}_viz.html"

                            # Normalize paths for web relative to search_engine.html
                            rel_img = ""
                            if img_file.exists():
                                rel_img = os.path.relpath(img_file, output_dir).replace("\\", "/")
                            
                            rel_viz = ""
                            if viz_file.exists():
                                rel_viz = os.path.relpath(viz_file, output_dir).replace("\\", "/")

                            # Use a unique key for the index (onion + path_key)
                            entry_id = f"{addr}_{path_key}"
                            onion_index[entry_id] = {
                                "addr": addr,
                                "url": actual_url,
                                "title": title,
                                "image": rel_img,
                                "viz": rel_viz,
                                "history": []
                            }
                        except Exception as e:
                            print(f"Error indexing {title_file}: {e}")
                            continue

    # 2. Add Log History
    # Note: Reliability is usually logged for the root. We'll map root history to all sub-paths.
    log_pattern = re.compile(r'\[(.*?)\] (https?://([a-z0-9_.-]+)\.onion/?) -> (\w+) \((.*?)\)')
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    match = log_pattern.search(line)
                    if match:
                        ts, _, addr, status, _ = match.groups()
                        # Update all entries belonging to this onion address
                        for eid in onion_index:
                            if onion_index[eid]["addr"] == addr:
                                onion_index[eid]["history"].append({"ts": ts, "status": status})
        except: pass
    
    return onion_index

def generate_html(data, output_file):
    json_data = json.dumps(data)
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neon Search | Tor Archive</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono&display=swap');

        :root {{
            --bg: #050505;
            --glass: rgba(255, 255, 255, 0.03);
            --border: rgba(255, 255, 255, 0.08);
            --accent: #ffffff;
            --dim: #555;
            --neon-blue: #0078D7;
        }}

        body, html {{
            margin: 0; padding: 0; min-height: 100vh;
            background-color: var(--bg); color: #eee;
            font-family: 'Inter', sans-serif;
            overflow-x: hidden;
        }}

        main {{
            display: flex; flex-direction: column; align-items: center;
            transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            min-height: 100vh; justify-content: center;
        }}

        main.searched {{
            min-height: auto; justify-content: flex-start; padding-top: 50px;
        }}

        .search-container {{
            width: 90%; max-width: 1100px; position: relative;
            z-index: 100;
        }}

        .search-inner {{
            display: flex; align-items: center;
            background: var(--glass); backdrop-filter: blur(20px);
            border: 1px solid var(--border); border-radius: 4px;
            padding: 5px 25px; transition: all 0.3s;
        }}

        .search-inner:focus-within {{ 
            border-color: rgba(255,255,255,0.3);
            box-shadow: 0 0 20px rgba(255,255,255,0.05);
        }}

        #searchInput {{
            background: transparent; border: none; outline: none;
            color: white; font-size: 1.2rem; width: 100%; padding: 20px;
            font-family: 'JetBrains Mono', monospace;
        }}

        /* Results Grid */
        #results {{
            width: 90%; max-width: 1100px; margin-top: 50px;
            display: grid; grid-template-columns: 1fr; gap: 40px;
            padding-bottom: 100px; display: none;
        }}

        .card {{
            display: flex; gap: 30px; background: rgba(255,255,255,0.01);
            border: 1px solid var(--border); padding: 30px; border-radius: 8px;
            animation: fadeIn 0.5s ease forwards;
            transition: transform 0.3s, background 0.3s;
        }}

        .card:hover {{
            background: rgba(255,255,255,0.02);
            border-color: rgba(255,255,255,0.15);
        }}

        @keyframes fadeIn {{ from{{opacity:0; transform:translateY(20px);}} to{{opacity:1; transform:translateY(0);}} }}

        .thumb-box {{ 
            width: 320px; flex-shrink: 0; position: relative; 
            overflow: hidden; border: 1px solid var(--border);
            height: 180px; border-radius: 4px;
            background: #111;
        }}
        
        .thumb {{ 
            width: 100%; height: 100%; 
            object-fit: cover; 
            object-position: top; /* Important for long screenshots - see the header/top part */
            transition: transform 0.5s;
        }}

        .card:hover .thumb {{ transform: scale(1.05); }}

        .thumb-overlay {{
            position: absolute; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.4); opacity: 0;
            display: flex; align-items: center; justify-content: center;
            transition: 0.3s;
        }}
        .thumb-box:hover .thumb-overlay {{ opacity: 1; }}
        .btn-fullimg {{
            color: white; background: rgba(255,255,255,0.1);
            backdrop-filter: blur(5px); padding: 8px 15px; border-radius: 4px;
            font-size: 0.8rem; text-decoration: none; border: 1px solid rgba(255,255,255,0.2);
        }}

        .info {{ flex: 1; display: flex; flex-direction: column; overflow: hidden; }}
        .title {{ 
            font-size: 1.5rem; color: var(--accent); 
            text-decoration: none; margin-bottom: 8px; font-weight: 600; 
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }}
        .title:hover {{ opacity: 0.8; }}
        
        .addr {{ font-family: 'JetBrains Mono', monospace; font-size: 0.85rem; color: var(--dim); margin-bottom: 20px; }}

        /* Card Actions */
        .actions {{ margin-top: auto; display: flex; gap: 20px; align-items: center; justify-content: space-between; }}
        
        .action-btns {{ display: flex; gap: 15px; }}

        .btn-viz {{ 
            font-size: 0.75rem; text-transform: uppercase; letter-spacing: 1px;
            color: #ccc; text-decoration: none; border: 1px solid #333;
            padding: 10px 18px; border-radius: 4px; transition: 0.2s;
            display: flex; align-items: center;
        }}
        .btn-viz:hover {{ background: #fff; color: #000; border-color: #fff; }}

        /* Small Reliability Sparkline */
        .sparkline {{ display: flex; gap: 3px; background: rgba(255,255,255,0.03); padding: 8px; border-radius: 4px; }}
        .dot {{ width: 5px; height: 14px; border-radius: 1px; }}

        /* Modal for full image */
        #modal {{
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.95); z-index: 1000;
            display: none; align-items: center; justify-content: center;
            cursor: zoom-out;
        }}
        #modal img {{ 
            max-width: 95%; max-height: 95%; 
            box-shadow: 0 0 50px rgba(0,0,0,1);
            object-fit: contain; 
        }}
        
        /* Stats Label */
        #siteCount {{
            margin-top: 15px; font-size: 0.8rem; color: var(--dim);
            opacity: 0; transition: 0.5s;
        }}
        main.searched #siteCount {{ opacity: 1; }}

        /* Custom Scrollbar */
        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: var(--bg); }}
        ::-webkit-scrollbar-thumb {{ background: #222; border-radius: 10px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #333; }}
    </style>
</head>
<body>

    <main id="mainFrame">
        <div class="search-container">
            <div class="search-inner">
                <i class="fas fa-search" style="opacity: 0.2; font-size: 1.2rem;"></i>
                <input type="text" id="searchInput" placeholder="Search Title or Onion Address..." autocomplete="off">
            </div>
            <div id="siteCount"></div>
        </div>

        <div id="results"></div>
    </main>

    <div id="modal" onclick="closeModal()">
        <img id="modalImg" src="">
    </div>

    <script>
        const database = {json_data};
        const searchBox = document.getElementById('searchInput');
        const resultsDiv = document.getElementById('results');
        const mainFrame = document.getElementById('mainFrame');
        const siteCount = document.getElementById('siteCount');
        const modal = document.getElementById('modal');
        const modalImg = document.getElementById('modalImg');

        searchBox.addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase().trim();
            
            if (query.length > 0) {{
                mainFrame.classList.add('searched');
                resultsDiv.style.display = 'grid';
                performSearch(query);
            }} else {{
                mainFrame.classList.remove('searched');
                resultsDiv.style.display = 'none';
                siteCount.innerText = "";
            }}
        }});

        function performSearch(q) {{
            resultsDiv.innerHTML = "";
            const matches = Object.keys(database).filter(addr => {{
                const site = database[addr];
                return addr.includes(q) || site.title.toLowerCase().includes(q);
            }});

            siteCount.innerText = `Found ${{matches.length}} matches in archive`;

            matches.forEach(addr => {{
                const site = database[addr];
                const card = document.createElement('div');
                card.className = 'card';
                
                // Build history sparkline (last 24 events)
                const sparkHTML = site.history.slice(-24).map(h => 
                    `<div class="dot" style="background:${{h.status === 'SUCCESS' ? '#fff' : '#222'}}" title="${{h.ts}} | ${{h.status}}"></div>`
                ).join('');

                card.innerHTML = `
                    <div class="thumb-box" onclick="openModal('${{site.image}}')">
                        <img src="${{site.image}}" class="thumb" onerror="this.src='https://placehold.co/320x180?text=No+Preview'">
                        <div class="thumb-overlay">
                            <span class="btn-fullimg">View Full Resolution</span>
                        </div>
                    </div>
                    <div class="info">
                        <a href="${{site.url}}" target="_blank" class="title">${{site.title}}</a>
                        <div class="addr">${{site.url.replace('http://', '').replace('https://', '')}}</div>
                        
                        <div class="actions">
                            <div class="action-btns">
                                <a href="${{site.viz}}" class="btn-viz" onclick="event.stopPropagation()">
                                    <i class="fas fa-chart-network" style="margin-right:8px"></i>Archive Map
                                </a>
                            </div>
                            <div class="sparkline">${{sparkHTML}}</div>
                        </div>
                    </div>
                `;
                resultsDiv.appendChild(card);
            }});
        }}

        function openModal(src) {{
            if (!src) return;
            modalImg.src = src;
            modal.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }}

        function closeModal() {{
            modal.style.display = 'none';
            document.body.style.overflow = 'auto';
        }}
        
        // Handle ESC key for modal
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'Escape') closeModal();
        }});
    </script>
</body>
</html>
"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Engine built successfully -> {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', default='../logs/unified_scraper.log')
    parser.add_argument('--data', default='../scraped_data')
    parser.add_argument('--output', default='../scraped_data/search_engine.html')
    args = parser.parse_args()
    
    data = parse_full_intelligence(args.log, args.data, args.output)
    generate_html(data, args.output)
