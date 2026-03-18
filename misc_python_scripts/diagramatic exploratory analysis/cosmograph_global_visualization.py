#!/usr/bin/env python3
"""
Cosmograph High-Performance Global Visualization
Capable of rendering up to 100,000+ nodes using WebGL.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path

def extract_onion_addresses_from_file(file_path):
    onion_addresses = set()
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                url_matches = re.findall(r'https?://([a-z2-7]{16,56})\.onion[^\s\'\"<>]*', content)
                for addr in url_matches:
                    onion_addresses.add(addr)
        except: pass
    return list(onion_addresses)

def get_onion_sites(scraped_data_dir):
    if not os.path.exists(scraped_data_dir):
        return []
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and 16 <= len(item) <= 60:
            onion_dirs.append(item)
    return onion_dirs

def extract_title_from_html(html_file_path):
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    return ' '.join(title_match.group(1).strip().split())
        except: pass
    return None

def extract_title_from_identity(identity_dir):
    if os.path.exists(identity_dir):
        for file_name in os.listdir(identity_dir):
            if file_name.endswith('_title.txt'):
                try:
                    with open(os.path.join(identity_dir, file_name), 'r', encoding='utf-8') as f:
                        line = f.readline()
                        match = re.search(r'\[(.*?)\] ->', line)
                        if match: return match.group(1).strip()
                except: pass
    return None

def generate_cosmograph_viz(scraped_data_dir):
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites for Cosmograph")

    nodes = []
    links = []
    site_data = {}

    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)
        title = extract_title_from_html(os.path.join(site_dir, 'htmls', f"{addr}.html"))
        if not title:
            title = extract_title_from_identity(os.path.join(site_dir, 'website_identity'))
        if not title:
            title = f"{addr}.onion"
        
        connected_onions = set()
        for d in ['discovered_links', 'urls']:
            d_path = os.path.join(site_dir, d)
            if os.path.exists(d_path):
                for f in os.listdir(d_path):
                    if f.endswith('_links.txt'):
                        connected_onions.update(extract_onion_addresses_from_file(os.path.join(d_path, f)))
        
        nodes.append({
            "id": addr,
            "label": title,
            "size": 10
        })
        site_data[addr] = list(connected_onions)

    for source, targets in site_data.items():
        for target in targets:
            pure_target = target.replace('.onion', '')
            if pure_target in site_data:
                links.append({"source": source, "target": pure_target})

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Cosmograph Massive Onion Network Explorer</title>
    <!-- Use the latest stable v2 UMD build -->
    <script src="https://cdn.jsdelivr.net/npm/@cosmograph/cosmograph@2/dist/index.min.js"></script>
    <style>
        body, html {{ margin: 0; padding: 0; width: 100%; height: 100%; overflow: hidden; background: #050505; color: #fff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }}
        #container {{ width: 100vw; height: 100vh; }}
        #ui {{ position: absolute; top: 20px; left: 20px; z-index: 10; background: rgba(10, 10, 15, 0.85); padding: 20px; border-radius: 12px; border: 1px solid #1a1a2e; backdrop-filter: blur(10px); box-shadow: 0 8px 32px rgba(0,0,0,0.8); pointer-events: auto; }}
        h1 {{ margin: 0 0 5px 0; font-size: 18px; color: #00f2ff; letter-spacing: 1px; }}
        .stats {{ font-size: 13px; color: #888; margin-bottom: 15px; border-bottom: 1px solid #222; padding-bottom: 10px; }}
        .instructions {{ font-size: 12px; line-height: 1.6; color: #aaa; }}
        b {{ color: #00f2ff; }}
        #tooltip {{ position: fixed; background: rgba(0,0,0,0.9); color: white; padding: 8px 12px; border-radius: 4px; pointer-events: none; display: none; z-index: 100; border: 1px solid #00f2ff; font-size: 13px; }}
    </style>
</head>
<body>
    <div id="ui">
        <h1>Onion Titan Engine</h1>
        <div class="stats">Nodes: {len(nodes)} | Edges: {len(links)} | WebGL v2 GPU Force</div>
        <div class="instructions">
            • <b>Left Click + Drag</b>: Pan<br>
            • <b>Scroll Wheel</b>: Zoom In/Out<br>
            • <b>Hover Node</b>: View Title<br>
            • <b>Click Node</b>: Focus
        </div>
    </div>
    <div id="tooltip"></div>
    <div id="container"></div>

    <script>
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};
        const tooltip = document.getElementById('tooltip');
        const container = document.getElementById('container');

        // Robust library detection for v2
        const CosmographLib = window.Cosmograph && window.Cosmograph.Cosmograph ? window.Cosmograph.Cosmograph : window.Cosmograph;
        
        if (!CosmographLib) {{
            container.innerHTML = "<div style='padding:40px; color:red; font-size:20px;'>Error: Cosmograph v2 failed to load. Please check your connection.</div>";
            throw new Error("Cosmograph not found");
        }}

        // Initialize Cosmograph v2
        const cosmograph = new CosmographLib(container, {{
            nodes: {{
                data: nodes,
                id: n => n.id,
                color: n => n.color || '#00f2ff',
                size: n => n.size || 4,
                label: n => n.label,
                // Add image support
                image: n => n.image || null,
            }},
            links: {{
                data: links,
                source: l => l.source,
                target: l => l.target,
                color: 'rgba(255, 255, 255, 0.15)',
                width: 1,
            }},
            backgroundColor: '#050505',
            showDynamicLabels: true,
            renderNodeImages: true,
            simulation: {{
                repulsion: 1.2,
                linkDistance: 15,
                friction: 0.8,
                gravity: 0.25
            }},
            onNodeHover: (node, index, event) => {{
                if (node) {{
                    tooltip.style.display = 'block';
                    tooltip.style.left = (event.clientX + 15) + 'px';
                    tooltip.style.top = (event.clientY + 15) + 'px';
                    tooltip.innerHTML = `<b>Title:</b> ${{node.label}}<br><b>Address:</b> ${{node.id}}.onion`;
                }} else {{
                    tooltip.style.display = 'none';
                }}
            }},
            onNodeClick: (node) => {{
                if (node) {{
                    cosmograph.zoomToNode(node);
                }}
            }}
        }});
    </script>
</body>
</html>"""

    out = os.path.join(scraped_data_dir, "cosmograph_visualization.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Cosmograph visualization saved to {out}")

if __name__ == "__main__":
    import sys
    path = "scraped_data" if not len(sys.argv) > 1 else sys.argv[1]
    if os.path.exists(path):
        generate_cosmograph_viz(path)
    else:
        print(f"Path {path} not found.")
