#!/usr/bin/env python3
import os
import re
import json
import argparse
from pathlib import Path
from collections import defaultdict

# Pre-compiled regex for onion address validation
ONION_PATTERN = re.compile(r'^[a-z2-7]{1,56}$')

def parse_full_intelligence(log_path, scraped_dir, output_path):
    """
    Crawls local data to build a mirror index grouped by title.
    """
    groups = defaultdict(list)
    base_scraped = Path(scraped_dir)
    
    if base_scraped.exists():
        for item in base_scraped.iterdir():
            if item.is_dir() and ONION_PATTERN.match(item.name):
                addr = item.name
                title = addr  # Fallback
                title_file = item / "website_identity" / "index_title.txt"
                if title_file.exists():
                    try:
                        content = title_file.read_text(encoding='utf-8').strip()
                        title_match = re.search(r'\[(.*?)\]', content)
                        if title_match:
                            title = title_match.group(1).strip()
                    except: pass

                groups[title].append(f"http://{addr}.onion")
    
    return groups

def generate_html(groups, output_file):
    json_data = json.dumps(groups)
    
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mirror Discovery Portal</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --bg: #030303;
            --accent: #6d5dfc;
            --glass: rgba(255, 255, 255, 0.03);
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

        /* --- SPLASH STATE --- */
        #mainContainer {{
            width: 100%; max-width: 900px;
            text-align: center;
            transition: all 0.8s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        #mainContainer.searched {{
            transform: translateY(-20vh);
        }}

        h1 {{
            font-size: 3.5rem; letter-spacing: -2px; margin-bottom: 50px;
            background: linear-gradient(135deg, #fff 0%, var(--accent) 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
            font-weight: 600;
        }}

        .search-area {{
            width: 100%; position: relative;
            background: var(--glass); backdrop-filter: blur(20px);
            border: 1px solid var(--border); border-radius: 60px;
            padding: 8px 35px; display: flex; align-items: center;
            transition: 0.3s;
        }}

        .search-area:focus-within {{ 
            border-color: var(--accent);
            box-shadow: 0 0 40px rgba(109, 93, 252, 0.15);
        }}

        #searchInput {{
            background: transparent; border: none; outline: none;
            color: white; font-size: 1.4rem; width: 100%; padding: 18px;
            font-family: 'Outfit', sans-serif;
        }}

        /* --- LOADING SPINNER --- */
        #loader {{
            display: none; margin-top: 60px;
            flex-direction: column; align-items: center;
            animation: fadeIn 0.4s ease;
        }}

        .spinner {{
            width: 50px; height: 50px;
            border: 3px solid rgba(255,255,255,0.05);
            border-top: 3px solid var(--accent);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}

        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

        /* --- LINK PARAGRAPH BOX --- */
        #resultBox {{
            display: none; width: 100%; margin-top: 50px;
            background: var(--glass); border: 1px solid var(--border);
            border-radius: 30px; padding: 50px;
            box-shadow: 0 20px 50px rgba(0,0,0,0.5);
            animation: slideUp 0.6s cubic-bezier(0.16, 1, 0.3, 1);
        }}

        .meta-info {{
            text-align: center; margin-bottom: 35px;
            color: var(--dim); font-size: 0.8rem;
            text-transform: uppercase; letter-spacing: 3px;
        }}

        .link-container {{
            font-family: 'JetBrains Mono', monospace;
            font-size: 1.05rem; line-height: 2.2;
            text-align: justify; color: #6da5ff;
            word-break: break-all;
        }}

        .link-container a {{
            color: #6da5ff; text-decoration: none;
            padding: 0 8px; transition: 0.2s;
            display: inline-block;
        }}

        .link-container a:hover {{
            color: white; transform: scale(1.05);
            text-shadow: 0 0 10px rgba(109, 93, 252, 0.5);
        }}

        @keyframes fadeIn {{ from{{opacity:0;}} to{{opacity:1;}} }}
        @keyframes slideUp {{
            from {{ opacity: 0; transform: translateY(40px); }}
            to {{ opacity: 1; transform: translateY(0); }}
        }}

    </style>
</head>
<body>

    <div id="mainContainer">
        <h1>Mirror Finder</h1>
        
        <div class="search-area">
            <i class="fas fa-search" style="opacity: 0.3; font-size: 1.4rem;"></i>
            <input type="text" id="searchInput" placeholder="Search Title or Keyword..." autocomplete="off">
        </div>

        <div id="loader">
            <div class="spinner"></div>
            <p style="margin-top: 20px; color: var(--accent); font-size: 0.8rem; letter-spacing: 2px;">AGGREGATING MIRROR LINKS...</p>
        </div>

        <div id="resultBox">
            <div class="meta-info" id="resultMeta"></div>
            <div class="link-container" id="linkList"></div>
        </div>
    </div>

    <script>
        const database = {json_data};
        const searchInput = document.getElementById('searchInput');
        const mainContainer = document.getElementById('mainContainer');
        const loader = document.getElementById('loader');
        const resultBox = document.getElementById('resultBox');
        const linkList = document.getElementById('linkList');
        const resultMeta = document.getElementById('resultMeta');

        let debounce = null;

        searchInput.addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase().trim();
            clearTimeout(debounce);

            if (query.length === 0) {{
                mainContainer.classList.remove('searched');
                loader.style.display = 'none';
                resultBox.style.display = 'none';
                return;
            }}

            // Enter Search State
            mainContainer.classList.add('searched');
            resultBox.style.display = 'none';
            loader.style.display = 'flex';

            debounce = setTimeout(() => {{
                processDiscovery(query);
            }}, 900);
        }});

        function processDiscovery(q) {{
            loader.style.display = 'none';
            
            let uniqueOnions = new Set();
            let matches = 0;

            for (const [title, onions] of Object.entries(database)) {{
                if (title.toLowerCase().includes(q) || onions.some(o => o.toLowerCase().includes(q))) {{
                    matches++;
                    onions.forEach(o => uniqueOnions.add(o));
                }}
            }}

            if (uniqueOnions.size > 0) {{
                resultBox.style.display = 'block';
                resultMeta.innerText = `Matches Found: ${{uniqueOnions.size}} Unique Onion Addresses`;
                
                linkList.innerHTML = Array.from(uniqueOnions).map(url => {{
                    return `<a href="${{url}}" target="_blank">${{url}}</a>`;
                }}).join(' ');

            }} else {{
                resultBox.style.display = 'block';
                resultMeta.innerText = "No mirrors discovered for this keyword";
                linkList.innerHTML = "<center style='color:var(--dim)'>Try a broader keyword or a partial onion address string.</center>";
            }}
        }}
    </script>
</body>
</html>
"""
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"[SUCCESS] Mirror Discovery Engine ready: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', default='./logs/unified_scraper.log')
    parser.add_argument('--data', default='./scraped_data')
    parser.add_argument('--output', default='mirror_finder.html')
    args = parser.parse_args()
    
    data = parse_full_intelligence(args.log, args.data, args.output)
    generate_html(data, args.output)
