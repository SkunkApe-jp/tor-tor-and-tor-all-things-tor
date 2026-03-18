#!/usr/bin/env python3
"""
Force-Graph Global Network Visualization Generator
Uses WebGL/Canvas via force-graph for smooth rendering of thousands of nodes.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path

def extract_onion_addresses_from_file(file_path):
    """Extract all unique onion addresses from a links file."""
    onion_addresses = set()
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            url_matches = re.findall(r'https?://[^\s\'\"<>]+', content)
            for match in url_matches:
                try:
                    parsed = urllib.parse.urlparse(match)
                    if parsed.scheme and parsed.netloc:
                        onion_match = re.search(r'([a-z2-7]{16,56}\.onion)|([a-z2-7]{52}\.b32\.i2p)', match)
                        if onion_match:
                            onion_addr = next(g for g in onion_match.groups() if g is not None)
                            onion_addresses.add(onion_addr)
                except:
                    continue
    return list(onion_addresses)

def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    if not os.path.exists(scraped_data_dir):
        return []
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and 16 <= len(item) <= 60:
            onion_dirs.append(item)
    return onion_dirs

def extract_title_from_html(html_file_path):
    """Extract title from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    title = ' '.join(title.split())
                    return title
        except: pass
    return None

def extract_title_from_identity(identity_dir):
    """Extract title from website_identity folder as used by Go scraper."""
    if os.path.exists(identity_dir):
        for file_name in os.listdir(identity_dir):
            if file_name.endswith('_title.txt'):
                try:
                    with open(os.path.join(identity_dir, file_name), 'r', encoding='utf-8') as f:
                        line = f.readline()
                        match = re.search(r'\[(.*?)\] ->', line)
                        if match:
                            return match.group(1).strip()
                except: pass
    return None

def generate_forcegraph_visualization(scraped_data_dir):
    """Generate a high-performance force-graph visualization."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to visualize")

    nodes = []
    links = []
    addr_to_idx = {}

    for i, addr in enumerate(onion_sites):
        site_dir = os.path.join(scraped_data_dir, addr)
        htmls_dir = os.path.join(site_dir, 'htmls')
        images_dir = os.path.join(site_dir, 'images')
        
        main_html_file = os.path.join(htmls_dir, f"{addr}.html")
        title = extract_title_from_html(main_html_file)
        if not title:
            title = extract_title_from_identity(os.path.join(site_dir, 'website_identity'))
        
        if not title:
            title = f"{addr}.onion"
        
        image_path = ""
        if os.path.exists(images_dir):
            for img in ["index.png", f"{addr}.png"]:
                if os.path.exists(os.path.join(images_dir, img)):
                    image_path = f"{addr}/images/{img}"
                    break

        addr_to_idx[addr] = addr
        nodes.append({
            "id": addr,
            "name": title,
            "img": image_path,
            "val": 10
        })

    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)
        for d in [os.path.join(site_dir, 'urls'), os.path.join(site_dir, 'discovered_links')]:
            if os.path.exists(d):
                for file_name in os.listdir(d):
                    if file_name.endswith('_links.txt'):
                        links_file_path = os.path.join(d, file_name)
                        connected = extract_onion_addresses_from_file(links_file_path)
                        for target in connected:
                            pure_target = target.replace('.onion', '')
                            if pure_target in addr_to_idx:
                                links.append({"source": addr, "target": pure_target})

    graph_data = {"nodes": nodes, "links": links}

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Force-Graph Onion Network Visualization</title>
    <script src="https://unpkg.com/force-graph"></script>
    <style>
        body {{ margin: 0; background: #000d1a; color: #eee; font-family: 'Segoe UI', sans-serif; overflow: hidden; }}
        #title {{ position: absolute; top: 20px; left: 20px; z-index: 10; font-size: 20px; font-weight: 300; background: rgba(0,0,0,0.6); padding: 10px 20px; border-radius: 4px; border-left: 4px solid #00f2ff; backdrop-filter: blur(4px); }}
        #graph {{ width: 100vw; height: 100vh; }}
        #legend {{ position: absolute; bottom: 20px; left: 20px; background: rgba(0,0,0,0.6); padding: 15px; border-radius: 4px; font-size: 13px; color: #aaa; z-index: 10; border: 1px solid #1a3a4a; }}
    </style>
</head>
<body>
    <div id="title">Deep Web Network Explorer <span style="font-size: 14px; opacity: 0.6;">({len(nodes)} nodes, {len(links)} edges)</span></div>
    <div id="legend">
        <b>Navigation:</b> Drag to rotate/pan, Scroll to zoom<br/>
        <b>Arrows:</b> Show link direction<br/>
        <b>Particles:</b> Indicate active data flow
    </div>
    <div id="graph"></div>
    <script>
        const gData = {json.dumps(graph_data)};
        // Cache for loaded images
        const imgCache = {{}};

        const Graph = ForceGraph()(document.getElementById('graph'))
            .graphData(gData)
            .nodeId('id')
            .nodeLabel('name')
            .nodeAutoColorBy('id')
            .backgroundColor('#000d1a')
            .linkColor(() => 'rgba(255,255,255,0.3)')
            .linkDirectionalArrowLength(6)
            .linkDirectionalArrowRelPos(0.8)
            .linkDirectionalArrowColor(() => '#00f2ff')
            .linkDirectionalParticles(3)
            .linkDirectionalParticleSpeed(0.005)
            .linkDirectionalParticleWidth(2)
            .onNodeClick(node => {{
                if (node.img) window.open(node.img, '_blank');
            }});

        // Enhance visuals with custom node drawing (Images + Labels)
        Graph.nodeCanvasObject((node, ctx, globalScale) => {{
            const size = 12;
            const label = node.name;
            const fontSize = 14/globalScale;
            
            // Draw node circle/background
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = node.color || '#58a6ff';
            ctx.fill();

            // Draw Image if available
            if (node.img) {{
                if (!imgCache[node.img]) {{
                    const img = new Image();
                    img.src = node.img;
                    imgCache[node.img] = img;
                }}
                
                const img = imgCache[node.img];
                if (img.complete) {{
                    ctx.save();
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, size - 1, 0, 2 * Math.PI, false);
                    ctx.clip();
                    ctx.drawImage(img, node.x - size, node.y - size, size * 2, size * 2);
                    ctx.restore();
                }}
            }}

            // Draw Labels when zoomed in
            if (globalScale > 1.5) {{
                ctx.font = `${fontSize}px Sans-Serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
                ctx.fillText(label, node.x, node.y + size + 10);
            }}
        }});
    </script>
</body>
</html>"""

    output_file = os.path.join(scraped_data_dir, "forcegraph_network_visualization.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Force-graph visualization created at {output_file}")
    return output_file

if __name__ == "__main__":
    import sys
    path = "../scraped_data"
    if len(sys.argv) > 1:
        path = sys.argv[1]
    
    if not os.path.exists(path):
        print(f"Directory {path} not found.")
    else:
        generate_forcegraph_visualization(path)
