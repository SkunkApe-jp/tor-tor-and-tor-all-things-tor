#!/usr/bin/env python3
"""
Improved Force-Graph Global Network Visualization
Fixes link counting to match ECharts, adds degree analysis, and uses local assets.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path
from collections import defaultdict

def extract_onion_addresses_from_file(file_path):
    """Extract all unique onion addresses from a file."""
    onion_addresses = set()
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Enhanced regex to match both v2 and v3
                matches = re.findall(r'([a-z2-7]{16,56})\.onion', content)
                for addr in matches:
                    onion_addresses.add(addr)
        except: pass
    return list(onion_addresses)

def get_onion_sites(scraped_data_dir):
    """Identify directories that look like onion site hashes."""
    if not os.path.exists(scraped_data_dir):
        return []
    sites = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        # Relaxed matching to match ECharts: any directory with length 16-60
        if os.path.isdir(item_path) and 16 <= len(item) <= 60:
            sites.append(item)
    return sites

def extract_title_from_identity(site_dir):
    """Read site title from Go scraper's website_identity folder."""
    identity_dir = os.path.join(site_dir, 'website_identity')
    if os.path.exists(identity_dir):
        for f in os.listdir(identity_dir):
            if f.endswith('_title.txt'):
                try:
                    with open(os.path.join(identity_dir, f), 'r', encoding='utf-8') as file:
                        line = file.readline()
                        match = re.search(r'\[(.*?)\] ->', line)
                        if match: return match.group(1).strip()
                except: pass
    return None

def generate_improved_forcegraph(scraped_data_dir):
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Extracted {len(onion_sites)} node candidates.")

    nodes_data = {}
    out_links = defaultdict(set)
    in_degree = defaultdict(int)

    # 1. Build nodes and collect RAW links
    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)
        title = extract_title_from_identity(site_dir) or f"{addr}.onion"
        
        # Determine image
        img_path = ""
        img_check = os.path.join(site_dir, 'images', 'index.png')
        if os.path.exists(img_check):
            img_path = f"{addr}/images/index.png"
            
        nodes_data[addr] = {
            "id": addr,
            "name": title,
            "img": img_path,
            "total_raw_links": 0
        }

        # Scan for links
        for folder in ['discovered_links', 'urls']:
            folder_path = os.path.join(site_dir, folder)
            if os.path.exists(folder_path):
                for fname in os.listdir(folder_path):
                    if fname.endswith('_links.txt'):
                        found = extract_onion_addresses_from_file(os.path.join(folder_path, fname))
                        nodes_data[addr]["total_raw_links"] += len(found)
                        for target in found:
                            # Filter: only if target is a known node and not self
                            if target in onion_sites and target != addr:
                                out_links[addr].add(target)

    # 2. Finalize links and degrees
    final_links = []
    for source, targets in out_links.items():
        for target in targets:
            final_links.append({"source": source, "target": target})
            in_degree[target] += 1

    # 3. Create nodes list with degree info
    nodes_list = []
    for addr, data in nodes_data.items():
        # Scale value based on in-degree (minimum 10)
        data["val"] = 10 + (in_degree[addr] * 5)
        data["in_degree"] = in_degree[addr]
        data["out_degree"] = len(out_links[addr])
        nodes_list.append(data)

    print(f"Final Graph: {len(nodes_list)} nodes, {len(final_links)} external links.")

    # 4. Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Force-Graph Onion Network</title>
    <script src="https://unpkg.com/force-graph"></script>
    <style>
        body {{ margin: 0; background: #000814; color: #fff; font-family: 'Inter', sans-serif; overflow: hidden; }}
        #title {{ position: absolute; top: 20px; left: 20px; z-index: 10; font-size: 20px; font-weight: 600; background: rgba(0,0,0,0.7); padding: 12px 24px; border-radius: 12px; border-left: 5px solid #00f2ff; backdrop-filter: blur(8px); pointer-events: none; }}
        #title span {{ font-size: 13px; opacity: 0.5; font-weight: 300; }}
        #search-bar {{ position: absolute; top: 20px; right: 20px; z-index: 20; display: flex; gap: 8px; align-items: center; }}
        #searchBox {{ padding: 10px 16px; border-radius: 10px; border: 1px solid #1a2a3a; background: rgba(0,8,20,0.85); color: #fff; font-size: 14px; width: 260px; outline: none; backdrop-filter: blur(10px); transition: border 0.2s, box-shadow 0.2s; }}
        #searchBox:focus {{ border-color: #00f2ff; box-shadow: 0 0 12px rgba(0,242,255,0.25); }}
        #searchBox::placeholder {{ color: #4a6a7a; }}
        #clearBtn {{ padding: 9px 14px; border-radius: 8px; border: 1px solid #1a2a3a; background: rgba(0,8,20,0.85); color: #aaa; cursor: pointer; font-size: 14px; backdrop-filter: blur(10px); transition: all 0.2s; }}
        #clearBtn:hover {{ color: #fff; border-color: #00f2ff; }}
        #match-count {{ position: absolute; top: 65px; right: 20px; z-index: 20; font-size: 11px; color: #4a8a9a; pointer-events: none; }}
        #stats {{ position: absolute; bottom: 16px; right: 20px; font-size: 11px; opacity: 0.35; text-align: right; pointer-events: none; }}
        #graph {{ width: 100vw; height: 100vh; cursor: grab; }}
        #graph:active {{ cursor: grabbing; }}
        .tooltip-card {{ padding: 12px; min-width: 230px; background: rgba(0,8,20,0.95); border: 1px solid #1a3a4a; border-radius: 8px; box-shadow: 0 8px 32px rgba(0,0,0,0.6); }}
        .tooltip-title {{ color: #58a6ff; font-weight: bold; font-size: 14px; margin-bottom: 4px; }}
        .tooltip-meta {{ color: #8b949e; font-size: 11px; display: flex; gap: 10px; margin-bottom: 6px; }}
        .tooltip-img {{ width: 100%; border-radius: 4px; margin-top: 6px; display: block; }}
    </style>
</head>
<body>
    <div id="title">Onion Meta-Network <span>({len(nodes_list)} nodes | {len(final_links)} links)</span></div>
    <div id="search-bar">
        <input type="text" id="searchBox" placeholder="🔍 Search by title or onion address...">
        <button id="clearBtn">✕</button>
    </div>
    <div id="match-count"></div>
    <div id="stats">Force-Graph Canvas Engine | {len(nodes_list)} sites analyzed</div>
    <div id="graph"></div>
    <script>
        const gData = {{ "nodes": {json.dumps(nodes_list)}, "links": {json.dumps(final_links)} }};
        const imgCache = {{}};
        let currentQuery = '';

        const Graph = ForceGraph()(document.getElementById('graph'))
            .graphData(gData)
            .nodeId('id')
            .nodeLabel(node => `
                <div class="tooltip-card">
                    <div class="tooltip-title">${{node.name}}</div>
                    <div class="tooltip-meta">
                        <span>📥 In: ${{node.in_degree}}</span>
                        <span>📤 Out: ${{node.out_degree}}</span>
                        <span>📄 Links: ${{node.total_raw_links}}</span>
                    </div>
                    <div style="font-size:10px;opacity:0.5;">${{node.id}}.onion</div>
                    ${{node.img ? `<img src="${{node.img}}" class="tooltip-img" onerror="this.style.display='none'">` : ''}}
                </div>
            `)
            .backgroundColor('#000814')
            .linkColor(link => {{
                const src = link.source?.id || link.source;
                const tgt = link.target?.id || link.target;
                if (!currentQuery) return 'rgba(88,166,255,0.18)';
                const q = currentQuery;
                const srcNode = gData.nodes.find(n => n.id === src);
                const tgtNode = gData.nodes.find(n => n.id === tgt);
                const matches = n => n && (n.name.toLowerCase().includes(q) || n.id.toLowerCase().includes(q));
                return (matches(srcNode) || matches(tgtNode)) ? 'rgba(0,242,255,0.7)' : 'rgba(88,166,255,0.05)';
            }})
            .linkWidth(1.5)
            .linkDirectionalArrowLength(4)
            .linkDirectionalArrowRelPos(1)
            .linkDirectionalParticles(2)
            .linkDirectionalParticleSpeed(0.004)
            .enableNodeDrag(true)
            .enablePanInteraction(true)
            .enableZoomInteraction(true)
            .nodeCanvasObjectMode(() => 'replace')
            .nodeCanvasObject((node, ctx, globalScale) => {{
                if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;

                const size = (node.val || 10) / 2;
                const q = currentQuery;
                const matched = q && (node.name.toLowerCase().includes(q) || node.id.toLowerCase().includes(q));
                const faded  = q && !matched;

                // Glow (skip if faded)
                if (!faded) {{
                    const glowSize = matched ? size * 3.5 : size * 2;
                    const glowColor = matched ? 'rgba(0,242,255,0.35)' : 'rgba(0,242,255,0.10)';
                    const grad = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, glowSize);
                    grad.addColorStop(0, glowColor);
                    grad.addColorStop(1, 'transparent');
                    ctx.fillStyle = grad;
                    ctx.beginPath(); ctx.arc(node.x, node.y, glowSize, 0, 2 * Math.PI); ctx.fill();
                }}

                // Core circle
                ctx.globalAlpha = faded ? 0.12 : 1;
                ctx.beginPath();
                ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
                ctx.fillStyle = node.img ? '#000' : (matched ? '#00f2ff' : '#1a3a5a');
                ctx.fill();
                ctx.strokeStyle = matched ? '#fff' : '#00f2ff';
                ctx.lineWidth = (matched ? 2.5 : 1) / globalScale;
                ctx.stroke();
                ctx.globalAlpha = 1;

                // Screenshot thumbnail
                if (node.img && !faded) {{
                    if (!imgCache[node.img]) {{
                        const img = new Image(); img.src = node.img;
                        imgCache[node.img] = img;
                    }}
                    const img = imgCache[node.img];
                    if (img.complete && img.naturalWidth > 0) {{
                        ctx.save();
                        ctx.beginPath(); ctx.arc(node.x, node.y, size - 0.5, 0, 2 * Math.PI); ctx.clip();
                        ctx.drawImage(img, node.x - size, node.y - size, size * 2, size * 2);
                        ctx.restore();
                    }}
                }}

                // Label: always show for matched, zoom-dependent otherwise
                if (matched || globalScale > 2) {{
                    const fontSize = (matched ? 14 : 11) / globalScale;
                    ctx.globalAlpha = faded ? 0.15 : 1;
                    ctx.font = `${{matched ? 'bold ' : ''}}${{fontSize}}px Sans-Serif`;
                    ctx.textAlign = 'center'; ctx.textBaseline = 'top';
                    ctx.fillStyle = matched ? '#00f2ff' : 'rgba(255,255,255,0.65)';
                    ctx.fillText(node.name.length > 30 ? node.name.slice(0,28)+'…' : node.name, node.x, node.y + size + 2);
                    ctx.globalAlpha = 1;
                }}
            }})
            .onNodeClick(node => {{
                if (node.img) window.open(node.img, '_blank');
            }});

        Graph.d3Force('charge').strength(-250);
        Graph.d3Force('link').distance(150);

        // Search
        const searchBox = document.getElementById('searchBox');
        const clearBtn  = document.getElementById('clearBtn');
        const matchCount = document.getElementById('match-count');

        function applySearch(q) {{
            currentQuery = q.trim().toLowerCase();
            if (currentQuery) {{
                const hits = gData.nodes.filter(n =>
                    n.name.toLowerCase().includes(currentQuery) ||
                    n.id.toLowerCase().includes(currentQuery)
                ).length;
                matchCount.textContent = hits ? `${{hits}} match${{hits > 1 ? 'es' : ''}} found` : 'No matches';
            }} else {{
                matchCount.textContent = '';
            }}
            Graph.refresh();
        }}

        searchBox.addEventListener('input', e => applySearch(e.target.value));
        clearBtn.addEventListener('click', () => {{ searchBox.value = ''; applySearch(''); searchBox.focus(); }});
    </script>
</body>
</html>"""

    output_file = os.path.join(scraped_data_dir, "forcegraph_network_visualization.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Improved visualization created at {output_file}")

if __name__ == "__main__":
    import sys
    from pathlib import Path as _Path
    _default = str(_Path(__file__).resolve().parent / "../../scraped_data")
    path = sys.argv[1] if len(sys.argv) > 1 else _default
    if os.path.exists(path):
        generate_improved_forcegraph(path)
    else:
        print(f"Path not found: {path}")
