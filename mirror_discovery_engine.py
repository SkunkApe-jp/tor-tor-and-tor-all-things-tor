#!/usr/bin/env python3
import os
import re
import json
import time
import shutil
from pathlib import Path
from collections import defaultdict
import http.server

# --- CONFIGURATION ---
SCRAPED_DATA_DIR = "./scraped_data"
PORTAL_HTML_FILE = "mirror_discovery_portal.html"
CRAWLER_GRAPH_JSON = "./scraped_data/crawler_graph.json"
API_PORT = 8989

def calculate_in_degrees():
    in_degrees = defaultdict(int)
    graph_path = Path(CRAWLER_GRAPH_JSON)
    if graph_path.exists():
        try:
            with open(graph_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for source, targets in data.items():
                for target in targets:
                    clean_target = target.replace(".onion", "").strip("/")
                    in_degrees[clean_target] += 1
        except Exception as e:
            print(f"[WARN] Failed to parse crawler_graph.json: {e}")
    return in_degrees

def get_mirror_intelligence():
    mirror_groups = defaultdict(list)
    base_path = Path(SCRAPED_DATA_DIR)
    
    if not base_path.exists():
        print(f"[ERROR] {SCRAPED_DATA_DIR} not found.")
        return {}

    onion_pattern = re.compile(r'^[a-zA-Z0-9_-]{1,80}$')
    in_degrees = calculate_in_degrees()

    for item in base_path.iterdir():
        if item.is_dir() and onion_pattern.match(item.name):
            addr = item.name
            title = addr 
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
                "image": rel_img,
                "in_degree": in_degrees.get(addr, 0)
            })
            
    return mirror_groups

def generate_discovery_portal(groups):
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
    <title>Mirror Discovery Engine</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --bg: #050505;
            --accent: #ffffff;
            --glass: rgba(255, 255, 255, 0.02);
            --border: rgba(255, 255, 255, 0.08);
            --text: #eeeeee;
            --dim: #555555;
            --dimmer: #222222;
            --delete: #ff4444;
        }}

        * {{ box-sizing: border-box; }}

        body, html {{
            margin: 0; padding: 0; min-height: 100vh;
            background-color: var(--bg); color: var(--text);
            font-family: 'Inter', sans-serif;
            overflow-x: hidden;
            display: flex; flex-direction: column; align-items: center; justify-content: flex-start;
        }}

        /* CRT Scanlines Effect */
        body::after {{
            content: ""; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: repeating-linear-gradient(
                0deg,
                transparent,
                transparent 2px,
                rgba(0, 0, 0, 0.25) 2px,
                rgba(0, 0, 0, 0.25) 4px
            );
            pointer-events: none; z-index: 9999;
            animation: flicker 0.3s infinite;
        }}
        
        @keyframes flicker {{
            0% {{ opacity: 0.98; }}
            50% {{ opacity: 1; }}
            100% {{ opacity: 0.97; }}
        }}

        #mainFrame {{
            width: 100%; max-width: 1200px; padding-top: 25vh;
            text-align: center;
            transition: all 0.5s cubic-bezier(0.16, 1, 0.3, 1);
            padding-left: 20px; padding-right: 20px;
        }}

        #mainFrame.searched {{ padding-top: 5vh; }}

        .ascii-art {{
            font-family: 'JetBrains Mono', monospace; font-size: 0.6rem;
            color: #39ff14; text-shadow: 0 0 8px rgba(57, 255, 20, 0.5);
            text-align: left; display: inline-block; margin-bottom: 40px;
            font-weight: bold; line-height: 1.15;
            letter-spacing: -0.5px;
        }}

        .search-area {{
            width: 100%; max-width: 800px; margin: 0 auto;
            background: var(--glass); backdrop-filter: blur(20px);
            border: 1px solid var(--border); border-radius: 4px;
            padding: 5px 25px; display: flex; align-items: center;
            transition: 0.3s;
        }}

        .search-area:focus-within {{ border-color: rgba(255,255,255,0.25); }}

        #searchInput {{
            flex: 1; background: transparent; border: none; outline: none;
            color: white; font-size: 1.1rem; width: 100%; padding: 15px 10px;
            font-family: 'JetBrains Mono', monospace;
        }}

        #loader {{ display: none; margin-top: 80px; flex-direction: column; align-items: center; }}
        .spinner {{
            width: 40px; height: 40px; border: 1px solid var(--border);
            border-top: 1px solid var(--accent); border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}
        @keyframes spin {{ to {{ transform: rotate(360deg); }} }}

        .result-box {{
            display: none; width: 100%; margin-top: 50px; padding-bottom: 100px;
            animation: slideUp 0.5s ease-out; text-align: left;
        }}

        /* Clean Link Layout */
        .link-paragraph {{
            background: var(--glass); border: 1px solid var(--border);
            border-radius: 4px; padding: 30px; margin-bottom: 40px;
            line-height: 2.2; text-align: center;
        }}

        .onion-node {{
            display: inline-flex; align-items: center; 
            margin: 10px 15px; background: var(--bg);
            border-radius: 4px; padding: 4px 12px; border: 1px solid var(--border);
        }}

        .onion-node a {{
            color: var(--text); text-decoration: none; font-family: 'JetBrains Mono', monospace; font-size: 0.85rem;
            white-space: nowrap; transition: 0.2s;
            margin-right: 15px; 
        }}

        .onion-node a:hover {{ color: var(--accent); text-decoration: underline; }}

        /* Stats */
        .onion-stats {{
            font-size: 0.8rem; color: var(--dim); font-family: 'JetBrains Mono', monospace;
            padding: 2px 8px; border-radius: 2px; border: 1px dotted var(--dim);
        }}

        /* Meta header with Buttons */
        .meta-header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 20px; padding: 0 10px;
            border-bottom: 1px solid var(--dimmer); padding-bottom: 20px;
        }}
        
        .meta-zero {{ font-size: 0.9rem; color: var(--dim); text-transform: uppercase; letter-spacing: 1px; }}

        .actions-group {{ display: flex; gap: 15px; }}

        .btn-action {{
            background: transparent; border: 1px solid var(--border);
            color: var(--text); padding: 10px 20px; border-radius: 2px;
            font-family: 'Inter', sans-serif; cursor: pointer; transition: 0.2s;
            font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;
        }}
        
        .btn-action:hover {{ background: var(--accent); color: var(--bg); border-color: var(--accent); }}
        
        .btn-danger:hover {{ background: var(--delete); color: #fff; border-color: var(--delete); }}

        /* Image Grid */
        .img-grid {{
            display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px; margin-top: 20px;
        }}

        .grid-item {{
            overflow: hidden; border: 1px solid var(--border); border-radius: 2px;
            background: rgba(0,0,0,0.5); position: relative;
            transition: 0.3s; display: block;
        }}
        
        .grid-item:hover {{ border-color: var(--accent); }}

        .grid-item img {{ width: 100%; height: 160px; object-fit: cover; display: block; filter: grayscale(40%); transition: 0.3s; }}
        .grid-item:hover img {{ filter: grayscale(0%); }}
        
        .grid-title {{
            position: absolute; bottom: 0; left: 0; right: 0;
            background: rgba(0,0,0,0.9); padding: 10px;
            font-size: 0.75rem; text-align: center; color: #fff;
            opacity: 0; transition: 0.3s; border-top: 1px solid var(--border);
        }}
        
        .grid-item:hover .grid-title {{ opacity: 1; }}

        @keyframes slideUp {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    </style>
</head>
<body>
    <div id="mainFrame">
        <pre class="ascii-art">
   __  ____                                ____  _                                
  /  |/  (_)_____________  _____          / __ \(_)______________ _   _____  _______  __
 / /|_/ / / ___/ ___/ __ \/ ___/         / / / / / ___/ ___/ __ \ | / / _ \/ ___/ / / /
/ /  / / / /  / /  / /_/ / /            / /_/ / (__  ) /__/ /_/ / |/ /  __/ /  / /_/ /  
/_/  /_/_/_/  /_/   \____/_/           /_____/_/____/\___/\____/|___/\___/_/   \__, /   
                                                                             /____/     
        </pre>
        
        <div class="search-area">
            <i class="fas fa-search" style="opacity: 0.3; font-size: 1.2rem;"></i>
            <input type="text" id="searchInput" placeholder="Search exclusively by website title..." autocomplete="off">
        </div>

        <div id="loader">
            <div class="spinner"></div>
            <p style="margin-top: 20px; color: var(--dim); font-size: 0.7rem; letter-spacing: 2px;">AGGREGATING CLUSTERS...</p>
        </div>

        <div id="resultBox" class="result-box">
            <div class="meta-header">
                <div class="meta-zero" id="metaZero"></div>
                
                <div class="actions-group">
                    <button class="btn-action btn-danger" onclick="deleteMinorMirrors()"><i class="fas fa-trash-alt" style="margin-right:8px"></i>Purge Minor Mirrors</button>
                    <button class="btn-action" onclick="downloadBookmark()"><i class="fas fa-bookmark" style="margin-right:8px"></i>Export Bookmarks</button>
                </div>
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
        let currentMatches = [];

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
            }}, 500);
        }});

        function processSearch(q) {{
            loader.style.display = 'none';
            currentMatches = [];
            let uniqueOnions = new Map();
            let imagesHtml = '';

            for (const item of database) {{
                // Searching ONLY by title
                if (item.title.toLowerCase().includes(q)) {{
                    currentMatches.push(item);
                    
                    item.onions.forEach(o => {{
                        uniqueOnions.set(o.address, o);
                        if (o.image) {{
                            imagesHtml += `
                                <a href="${{o.image}}" target="_blank" class="grid-item">
                                    <img src="${{o.image}}" loading="lazy" alt="Mirror">
                                    <div class="grid-title">${{item.title}}<br><span style="color:var(--dim); font-size:10px; font-family:monospace;">${{o.address}}.onion</span></div>
                                </a>
                            `;
                        }}
                    }});
                }}
            }}

            if (uniqueOnions.size > 0) {{
                resultBox.style.display = 'block';
                metaZero.innerText = `Zeroed In: ${{uniqueOnions.size}} Mirrors Found`;
                
                let linksHtml = '';
                uniqueOnions.forEach((o, addr) => {{
                    const inDeg = o.in_degree;
                    const statsHtml = `<span class="onion-stats" title="Incoming Links (In-Degree)">
                                        <i class="fas fa-link" style="font-size:9px; margin-right:4px;"></i>${{inDeg}}
                                       </span>`;
                    
                    linksHtml += `
                        <div class="onion-node" id="node-${{addr}}">
                            <a href="${{o.url}}" target="_blank">${{o.url}}</a>
                            ${{statsHtml}}
                        </div>
                    `;
                }});
                
                lp.innerHTML = linksHtml;
                imgGrid.innerHTML = imagesHtml;
            }} else {{
                resultBox.style.display = 'block';
                metaZero.innerText = "No mirrors detected";
                lp.innerHTML = "<span style='color:var(--dim)'>Try a different identity title.</span>";
                imgGrid.innerHTML = "";
            }}
        }}

        // Intelligent Batch Purge Function
        async function deleteMinorMirrors() {{
            if (currentMatches.length === 0) return;
            
            let toDelete = [];
            let deletionLog = [];

            // Execute logic per Mirror Cluster
            currentMatches.forEach(group => {{
                // Find highest in-degree for this specific site's identity
                const maxDeg = Math.max(...group.onions.map(o => o.in_degree));
                
                group.onions.forEach(o => {{
                    if (maxDeg === 0) {{
                        toDelete.push(o); // All 0s, all die
                        deletionLog.push(`${{o.address}} (Score: 0 - Complete wipe of 0s)`);
                    }} else if (o.in_degree < maxDeg) {{
                        toDelete.push(o); // Protect the max-degree nodes, purge the rest
                        deletionLog.push(`${{o.address}} (Score: ${{o.in_degree}} vs Max: ${{maxDeg}})`);
                    }}
                }});
            }});

            if (toDelete.length === 0) {{
                alert("Nothing to purge. All viewed mirrors are top-ranked active nodes for their identities.");
                return;
            }}

            const confirmMsg = `Are you sure you want to permanently delete ${{toDelete.length}} minor mirror(s) from disk?\\n\\nThe highest linked mirrors will be saved.\\n\\nTargets:\\n` + deletionLog.slice(0,5).join("\\n") + (toDelete.length > 5 ? "\\n...and more" : "");
            if(!confirm(confirmMsg)) return;

            let successCount = 0;
            const baseUrl = window.location.protocol === "file:" ? "http://localhost:8989" : "";
            
            for (const o of toDelete) {{
                try {{
                    const response = await fetch(`${{baseUrl}}/api/delete/${{o.address}}`, {{ method: 'POST' }});
                    if (response.ok) {{
                        successCount++;
                        const nodeEl = document.getElementById(`node-${{o.address}}`);
                        if (nodeEl) nodeEl.remove();
                    }}
                }} catch (e) {{}}
            }}

            if (successCount > 0) {{
                alert(`Purged ${{successCount}} minor mirrors successfully. Reload the engine to fully refresh state.`);
            }} else {{
                alert("Purge failed. Is the API server (mirror_discovery_engine.py) actively running?");
            }}
        }}

        function downloadBookmark() {{
            if (currentMatches.length === 0) return;
            const ts = Math.floor(Date.now() / 1000);
            
            let html = `<!DOCTYPE NETSCAPE-Bookmark-file-1>
<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">
<TITLE>Bookmarks</TITLE>
<H1>Bookmarks Menu</H1>
<DL><p>\\n`;

            currentMatches.forEach(group => {{
                // Replace invalid title characters
                const safeTitle = group.title.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
                html += `    <DT><H3 ADD_DATE="${{ts}}" LAST_MODIFIED="${{ts}}">${{safeTitle}}</H3>\\n`;
                html += `    <DL><p>\\n`;
                
                group.onions.forEach(onion => {{
                    html += `        <DT><A HREF="${{onion.url}}" ADD_DATE="${{ts}}">${{onion.url}}</A>\\n`;
                }});
                html += `    </DL><p>\\n`;
            }});

            html += `</DL><p>\\n`;

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

# --- LOCAL API SERVER FOR BATCH DELETION ---
class DiscoveryAPIHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_POST(self):
        if self.path.startswith('/api/delete/'):
            onion_addr = self.path.split('/')[-1]
            if re.match(r'^[a-zA-Z0-9_-]{1,80}$', onion_addr):
                target_dir = Path(SCRAPED_DATA_DIR) / onion_addr
                if target_dir.exists() and target_dir.is_dir():
                    try:
                        shutil.rmtree(target_dir)
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b'{"status":"success"}')
                        print(f"[*] Successfully wiped mirror: {onion_addr}")
                        return
                    except Exception as e:
                        print(f"[!] Failed to delete {onion_addr}: {e}")
        self.send_response(500)
        self.end_headers()
        self.wfile.write(b'{"status":"fail"}')

def run_server():
    server = http.server.HTTPServer(('', API_PORT), DiscoveryAPIHandler)
    print(f"\n[ACTIVE] Mirror Discovery Engine running on port {API_PORT}")
    print("[ACTIVE] Keep this terminal open to enable Batch Purging via the UI.")
    print("Press Ctrl+C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Engine shutting down.")
        server.server_close()

if __name__ == "__main__":
    print("[INIT] Booting Mirror Discovery Engine...")
    intel = get_mirror_intelligence()
    if intel:
        print(f"[PROCESS] Indexed {len(intel)} Unique Identities.")
        generate_discovery_portal(intel)
        print(f"[SUCCESS] Mirror Portal rebuilt: {PORTAL_HTML_FILE}")
        # Run server
        run_server()
    else:
        print("[WARN] No data found in scraped_data.")
