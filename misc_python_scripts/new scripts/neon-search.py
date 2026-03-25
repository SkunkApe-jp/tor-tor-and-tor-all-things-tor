#!/usr/bin/env python3
import os
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict

# Pre-compiled regex for onion address validation (v2: 16 chars, v3: 56 chars, or vanity: <=56 chars)
ONION_PATTERN = re.compile(r'^[a-z2-7]{1,56}$')

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
                
                # Fetch Title
                title = addr  # Fallback
                title_file = item / "website_identity" / "index_title.txt"
                if title_file.exists():
                    try:
                        content = title_file.read_text().strip()
                        # Extract part inside [ ]
                        title_match = re.search(r'\[(.*?)\]', content)
                        if title_match:
                            title = title_match.group(1)
                    except: pass

                # Paths relative to the output HTML file
                img_path = item / "images" / "index.png"
                viz_path = item / "visualizations" / f"{addr}_viz.html"
                
                # Verify paths and normalize for web
                rel_img = ""
                if img_path.exists():
                    rel_img = os.path.relpath(img_path, output_dir).replace("\\", "/")
                
                rel_viz = ""
                if viz_path.exists():
                    rel_viz = os.path.relpath(viz_path, output_dir).replace("\\", "/")

                onion_index[addr] = {
                    "title": title,
                    "image": rel_img,
                    "viz": rel_viz,
                    "history": []
                }

    # 2. Add Log History for the card viz
    # Support v2 (16 chars), v3 (56 chars), and vanity addresses (1-56 chars)
    log_pattern = re.compile(r'\[(.*?)\] (https?://([a-z2-7]{1,56})\.onion/?) -> (\w+) \((.*?)\)')
    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            for line in f:
                match = log_pattern.search(line)
                if match:
                    ts, _, addr, status, _ = match.groups()
                    if addr in onion_index:
                        onion_index[addr]["history"].append({"ts": ts, "status": status})
    
    return onion_index

def generate_html(data, output_file):
    json_data = json.dumps(data)
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Search </title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --bg: #050505;
            --glass: rgba(255, 255, 255, 0.03);
            --border: rgba(255, 255, 255, 0.08);
            --accent: #ffffff;
            --dim: #555;
        }}

        body, html {{
            margin: 0; padding: 0; min-height: 100vh;
            background-color: var(--bg); color: #eee;
            font-family: 'Inter', -apple-system, sans-serif;
            overflow-x: hidden;
        }}

        /* Splash State Logic */
        main {{
            display: flex; flex-direction: column; align-items: center;
            transition: all 0.6s cubic-bezier(0.16, 1, 0.3, 1);
            min-height: 100vh; justify-content: center; /* Initial center */
        }}

        main.searched {{
            min-height: auto; justify-content: flex-start; padding-top: 50px;
        }}

        /* Search Bar */
        .search-container {{
            width: 90%; max-width: 1100px; position: relative;
        }}

        .search-inner {{
            display: flex; align-items: center;
            background: var(--glass); backdrop-filter: blur(20px);
            border: 1px solid var(--border); border-radius: 2px;
            padding: 5px 25px; transition: border 0.3s;
        }}

        .search-inner:focus-within {{ border-color: rgba(255,255,255,0.25); }}

        #searchInput {{
            background: transparent; border: none; outline: none;
            color: white; font-size: 1.2rem; width: 100%; padding: 20px;
            font-family: 'JetBrains Mono', monospace;
        }}

        /* Results Grid */
        #results {{
            width: 90%; max-width: 1100px; margin-top: 50px;
            display: grid; grid-template-columns: 1fr; gap: 30px;
            padding-bottom: 100px; display: none;
        }}

        .card {{
            display: flex; gap: 30px; background: rgba(255,255,255,0.01);
            border: 1px solid var(--border); padding: 25px; border-radius: 4px;
            animation: fadeIn 0.5s ease forwards;
        }}

        @keyframes fadeIn {{ from{{opacity:0; transform:translateY(10px);}} to{{opacity:1; transform:translateY(0);}} }}

        .thumb-box {{ width: 320px; flex-shrink: 0; position: relative; }}
        .thumb {{ width: 100%; height: 180px; object-fit: cover; border: 1px solid var(--border); }}

        .info {{ flex: 1; display: flex; flex-direction: column; }}
        .title {{ font-size: 1.4rem; color: var(--accent); text-decoration: none; margin-bottom: 8px; font-weight: 500; }}
        .title:hover {{ text-decoration: underline; }}
        
        .addr {{ font-family: monospace; font-size: 0.8rem; color: var(--dim); margin-bottom: 20px; }}

        /* Card Actions */
        .actions {{ margin-top: auto; display: flex; gap: 20px; align-items: center; }}
        .btn-viz {{ 
            font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;
            color: #fff; text-decoration: none; border: 1px solid #333;
            padding: 8px 15px; border-radius: 2px; transition: 0.2s;
        }}
        .btn-viz:hover {{ background: #fff; color: #000; }}

        /* Small Reliability Sparkline */
        .sparkline {{ display: flex; gap: 3px; }}
        .dot {{ width: 4px; height: 12px; border-radius: 1px; }}
    </style>
</head>
<body>

    <main id="mainFrame">
        <div class="search-container">
            <div class="search-inner">
                <i class="fas fa-search" style="opacity: 0.2; font-size: 1.2rem;"></i>
                <input type="text" id="searchInput" placeholder="Search Title or Onion..." autocomplete="off">
            </div>
        </div>

        <div id="results"></div>
    </main>

    <script>
        const database = {json_data};
        const searchBox = document.getElementById('searchInput');
        const resultsDiv = document.getElementById('results');
        const mainFrame = document.getElementById('mainFrame');

        searchBox.addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase().trim();
            
            if (query.length > 0) {{
                mainFrame.classList.add('searched');
                resultsDiv.style.display = 'grid';
                performSearch(query);
            }} else {{
                mainFrame.classList.remove('searched');
                resultsDiv.style.display = 'none';
            }}
        }});

        function performSearch(q) {{
            resultsDiv.innerHTML = "";
            const matches = Object.keys(database).filter(addr => {{
                const site = database[addr];
                return addr.includes(q) || site.title.toLowerCase().includes(q);
            }});

            matches.forEach(addr => {{
                const site = database[addr];
                const card = document.createElement('div');
                card.className = 'card';
                
                // Build history sparkline (last 20 events)
                const sparkHTML = site.history.slice(-20).map(h => 
                    `<div class="dot" style="background:${{h.status === 'SUCCESS' ? '#fff' : '#333'}}" title="${{h.ts}}"></div>`
                ).join('');

                card.innerHTML = `
                    <div class="thumb-box">
                        <img src="${{site.image}}" class="thumb" onerror="this.src='https://placehold.co/320x180?text=No+Preview'">
                    </div>
                    <div class="info">
                        <a href="http://${{addr}}.onion" target="_blank" class="title">${{site.title}}</a>
                        <div class="addr">${{addr}}.onion</div>
                        
                        <div class="actions">
                            <a href="${{site.viz}}" class="btn-viz">
                                <i class="fas fa-chart-line" style="margin-right:8px"></i>View Reliability Viz
                            </a>
                            <div class="sparkline">${{sparkHTML}}</div>
                        </div>
                    </div>
                `;
                resultsDiv.appendChild(card);
            }});
        }}
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
