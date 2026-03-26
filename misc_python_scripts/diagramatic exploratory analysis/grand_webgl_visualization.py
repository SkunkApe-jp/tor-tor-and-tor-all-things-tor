#!/usr/bin/env python3
"""
Grand WebGL Visualization Generator
High-performance version of grand_visualization1.py using Force-Graph (Canvas/WebGL).
Handles thousands of nested nodes and links with screenshot previews.
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
                url_matches = re.findall(r'https?://[^\s\'\"<>]+', content)
                for match in url_matches:
                    onion_match = re.search(r'([a-z2-7]{16,56}\.onion)', match)
                    if onion_match:
                        onion_addresses.add(onion_match.group(1))
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

def generate_grand_webgl_viz(scraped_data_dir):
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} root onion sites for Grand WebGL")

    nodes = []
    links = []
    processed_urls = set()

    # Process each onion site as a root cluster
    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)
        title = extract_title_from_html(os.path.join(site_dir, 'htmls', f"{addr}.html"))
        if not title:
            title = extract_title_from_identity(os.path.join(site_dir, 'website_identity'))
        if not title:
            title = f"{addr}.onion"
        
        # Root node
        root_id = f"root_{addr}"
        nodes.append({
            "id": root_id,
            "name": title,
            "val": 20,
            "group": addr,
            "isRoot": True
        })
        processed_urls.add(root_id)

        # Get all linked onions - limit to prevent explosion
        connected_links = set()
        max_links_per_site = 50  # Limit links per site to prevent too many edges
        
        for d in ['discovered_links', 'urls']:
            d_path = os.path.join(site_dir, d)
            if os.path.exists(d_path):
                for f in os.listdir(d_path):
                    if f.endswith('_links.txt') and len(connected_links) < max_links_per_site:
                        with open(os.path.join(d_path, f), 'r', encoding='utf-8') as file:
                            for line in file:
                                if len(connected_links) >= max_links_per_site:
                                    break
                                line = line.strip()
                                # Only match actual onion URLs
                                onion_match = re.search(r'([a-z2-7]{16,56}\.onion)', line)
                                if onion_match:
                                    connected_links.add(onion_match.group(1))

        # Add links as child nodes
        for link in connected_links:
            child_id = f"child_{link}"
            
            if child_id not in processed_urls:
                nodes.append({
                    "id": child_id,
                    "name": link,
                    "val": 5,
                    "group": addr,
                    "isRoot": False
                })
                processed_urls.add(child_id)
            
            links.append({
                "source": root_id,
                "target": child_id
            })

    graph_data = {"nodes": nodes, "links": links}

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Grand Deep Web Explorer (WebGL)</title>
    <script src="../../../force-graph.min.js"></script>
    <style>
        body {{ margin: 0; background: #00050a; color: #eee; font-family: 'Segoe UI', sans-serif; overflow: hidden; }}
        #title {{ position: absolute; top: 20px; left: 20px; z-index: 10; font-size: 20px; font-weight: 300; background: rgba(0,20,40,0.7); padding: 12px 25px; border-radius: 8px; border-left: 5px solid #00d2ff; backdrop-filter: blur(10px); }}
        #graph {{ width: 100vw; height: 100vh; }}
        #ui-overlay {{ position: absolute; bottom: 20px; left: 20px; background: rgba(0,10,20,0.6); padding: 15px; border-radius: 6px; font-size: 13px; z-index: 10; border: 1px solid #103050; }}
        #tooltip {{ position: absolute; padding: 12px; background: rgba(0,10,20,0.95); border: 1px solid #00d2ff; border-radius: 8px; pointer-events: none; opacity: 0; transition: opacity 0.2s; z-index: 100; max-width: 320px; }}
        #tooltip img {{ max-width: 100%; max-height: 150px; width: auto; height: auto; border-radius: 4px; margin-top: 8px; display: block; }}
        #tooltip .name {{ font-weight: bold; color: #00d2ff; margin-bottom: 4px; }}
        #tooltip .addr {{ font-size: 11px; color: #aaa; }}
        #searchContainer {{ position: absolute; top: 20px; right: 20px; z-index: 10; display: flex; gap: 8px; }}
        #searchBox {{ padding: 10px 16px; border-radius: 6px; border: 1px solid #103050; background: rgba(0,20,40,0.8); color: #fff; font-size: 14px; width: 200px; outline: none; }}
        #searchBox:focus {{ border-color: #00d2ff; }}
        #searchBox::placeholder {{ color: #666; }}
        #clearSearch {{ padding: 8px 12px; border-radius: 6px; border: 1px solid #103050; background: rgba(0,20,40,0.8); color: #fff; cursor: pointer; font-size: 14px; }}
        #clearSearch:hover {{ background: rgba(0,80,120,0.8); }}
    </style>
</head>
<body>
    <div id="title">Grand Network Explorer <span style="font-size: 14px; opacity: 0.6;">({len(nodes)} nodes, {len(links)} edges)</span></div>
    <div id="searchContainer">
        <input type="text" id="searchBox" placeholder="🔍 Search nodes...">
        <button id="clearSearch">✕</button>
    </div>
    <div id="tooltip"></div>
    <div id="ui-overlay">
        <b>Groups:</b> Nodes colored by root onion site<br/>
        <b>Interaction:</b> Click to expand, Scroll to zoom, Drag to move
    </div>
    <div id="graph"></div>
    <script>
        const gData = {json.dumps(graph_data)};
        const Graph = ForceGraph()(document.getElementById('graph'))
            .graphData(gData)
            .nodeId('id')
            .nodeLabel('name')
            .nodeAutoColorBy('group')
            .backgroundColor('#00050a')
            .linkColor(() => 'rgba(0, 210, 255, 0.15)')
            .linkDirectionalParticles(2)
            .linkDirectionalParticleSpeed(0.005)
            .nodeCanvasObject((node, ctx, globalScale) => {{
                const label = node.name;
                const fontSize = (node.isRoot ? 16 : 10) / globalScale;
                ctx.font = `${{fontSize}}px Sans-Serif`;
                
                // Draw node
                const r = node.isRoot ? 6 : 2;
                ctx.fillStyle = node.color;
                ctx.beginPath();
                ctx.arc(node.x, node.y, r, 0, 2 * Math.PI, false);
                ctx.fill();

                // Glow for root nodes
                if (node.isRoot) {{
                    ctx.shadowBlur = 15;
                    ctx.shadowColor = node.color;
                }}

                if (globalScale > 2 || node.isRoot) {{
                    const textWidth = ctx.measureText(label).width;
                    const bckgDimensions = [textWidth, fontSize].map(n => n + fontSize * 0.2);
                    
                    ctx.fillStyle = 'rgba(0, 5, 10, 0.8)';
                    ctx.fillRect(node.x - bckgDimensions[0] / 2, node.y + r + 2, ...bckgDimensions);

                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'top';
                    ctx.fillStyle = node.isRoot ? '#fff' : 'rgba(255, 255, 255, 0.7)';
                    ctx.fillText(label, node.x, node.y + r + 2);
                }}
                
                ctx.shadowBlur = 0;
            }});

        // Adjust forces for better grand distribution
        Graph.d3Force('charge').strength(-150);
        Graph.d3Force('link').distance(80);

        // Search functionality
        const searchBox = document.getElementById('searchBox');
        const clearSearch = document.getElementById('clearSearch');
        const tooltip = document.getElementById('tooltip');
        
        function performSearch() {{
            const query = searchBox.value.toLowerCase().trim();
            
            if (!query) {{
                Graph.nodeColor(node => node.color || '#00d2ff');
                Graph.linkColor(link => 'rgba(0, 210, 255, 0.15)');
                Graph.nodeRelSize(1);
                return;
            }}
            
            Graph.nodeColor(node => {{
                const matches = node.name && node.name.toLowerCase().includes(query);
                const matchesId = node.id && node.id.toLowerCase().includes(query);
                return (matches || matchesId) ? '#d5ff16' : 'rgba(0, 210, 255, 0.15)';
            }});
            
            Graph.linkColor(link => {{
                const srcMatch = link.source.name && link.source.name.toLowerCase().includes(query);
                const tgtMatch = link.target.name && link.target.name.toLowerCase().includes(query);
                return (srcMatch || tgtMatch) ? 'rgba(213, 255, 22, 0.4)' : 'rgba(0, 210, 255, 0.05)';
            }});
            
            Graph.nodeRelSize(node => {{
                const matches = node.name && node.name.toLowerCase().includes(query);
                const matchesId = node.id && node.id.toLowerCase().includes(query);
                return (matches || matchesId) ? 3 : 0.5;
            }});
        }}
        
        searchBox.addEventListener('input', performSearch);
        clearSearch.addEventListener('click', () => {{
            searchBox.value = '';
            performSearch();
            searchBox.focus();
        }});
        
        // Tooltip functionality
        Graph.onNodeHover(node => {{
            if (node) {{
                let html = '<div class="name">' + node.name + '</div><div class="addr">' + node.id + '</div>';
                // Show image if it's a root node with screenshot
                if (node.isRoot) {{
                    const addr = node.id.replace('root_', '');
                    html += '<img src="' + addr + '/images/index.png" alt="screenshot" onerror="this.style.display=' + "'none'" + '"/>';
                }}
                tooltip.innerHTML = html;
                tooltip.style.opacity = 1;
            }} else {{
                tooltip.style.opacity = 0;
            }}
        }});
        
        Graph.onNodeClick(node => {{
            if (node && node.isRoot) {{
                const addr = node.id.replace('root_', '');
                window.open(addr + '/images/index.png', '_blank');
            }}
        }});
    </script>
</body>
</html>"""

    out = os.path.join(scraped_data_dir, "grand_webgl_visualization.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Grand WebGL visualization saved to {out}")

if __name__ == "__main__":
    import sys
    path = "scraped_data" if not len(sys.argv) > 1 else sys.argv[1]
    if os.path.exists(path):
        generate_grand_webgl_viz(path)
    else:
        print(f"Path {path} not found.")
