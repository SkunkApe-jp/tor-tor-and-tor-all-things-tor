#!/usr/bin/env python3
"""
Force-Graph Nodes-Only Visualization
Displays onion sites as floating nodes with force-directed layout but NO edges.
Uses force-graph for high-performance rendering.
"""

import os
import json
import re
from pathlib import Path

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

def extract_title_from_identity(identity_dir):
    """Extract title from website_identity folder."""
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

def generate_nodes_only_viz(scraped_data_dir):
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites for nodes-only visualization")

    nodes = []
    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)
        images_dir = os.path.join(site_dir, 'images')
        
        title = extract_title_from_identity(os.path.join(site_dir, 'website_identity'))
        if not title:
            title = f"{addr}.onion"
        
        image_path = ""
        if os.path.exists(images_dir):
            for img in ["index.png", f"{addr}.png"]:
                if os.path.exists(os.path.join(images_dir, img)):
                    image_path = f"{addr}/images/{img}"
                    break

        nodes.append({
            "id": addr,
            "name": title,
            "img": image_path,
            "val": 10 + (len(title) % 20)  # Slight variation in size
        })

    graph_data = {"nodes": nodes, "links": []}

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Force-Graph Nodes Galaxy</title>
    <script src="https://unpkg.com/force-graph"></script>
    <style>
        body {{ margin: 0; background: #050510; color: #eee; font-family: 'Outfit', 'Inter', sans-serif; overflow: hidden; }}
        #ui {{ position: absolute; top: 20px; left: 20px; z-index: 10; pointer-events: none; }}
        #ui h1 {{ margin: 0; font-size: 24px; font-weight: 600; background: linear-gradient(90deg, #7ce7ff, #58a6ff); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        #ui p {{ margin: 5px 0; opacity: 0.6; font-size: 13px; }}
        #search-bar {{ position: absolute; top: 20px; right: 20px; z-index: 20; display: flex; gap: 8px; align-items: center; }}
        #searchBox {{ padding: 10px 16px; border-radius: 10px; border: 1px solid #1a1a3a; background: rgba(10,10,30,0.85); color: #fff; font-size: 14px; width: 260px; outline: none; backdrop-filter: blur(8px); transition: border 0.2s, box-shadow 0.2s; }}
        #searchBox:focus {{ border-color: #58a6ff; box-shadow: 0 0 12px rgba(88,166,255,0.25); }}
        #searchBox::placeholder {{ color: #3a4a6a; }}
        #clearBtn {{ padding: 9px 14px; border-radius: 8px; border: 1px solid #1a1a3a; background: rgba(10,10,30,0.85); color: #aaa; cursor: pointer; font-size: 14px; }}
        #clearBtn:hover {{ color: #fff; border-color: #58a6ff; }}
        #match-count {{ position: absolute; top: 65px; right: 20px; z-index: 20; font-size: 11px; color: #4a6a9a; pointer-events: none; }}
        #graph {{ width: 100vw; height: 100vh; cursor: grab; }}
        #graph:active {{ cursor: grabbing; }}
    </style>
</head>
<body>
    <div id="ui">
        <h1>Onion Site Galaxy</h1>
        <p>{len(nodes)} sites discovered | No-link force-directed layout</p>
    </div>
    <div id="search-bar">
        <input type="text" id="searchBox" placeholder="🔍 Search by title or address...">
        <button id="clearBtn" onclick="document.getElementById('searchBox').value=''; document.getElementById('searchBox').dispatchEvent(new Event('input')); document.getElementById('searchBox').focus();">✕</button>
    </div>
    <div id="match-count"></div>
    <div id="graph"></div>
    <script>
        const gData = {json.dumps(graph_data)};
        const imgCache = {{}};

        const Graph = ForceGraph()(document.getElementById('graph'))
            .graphData(gData)
            .nodeId('id')
            .nodeLabel('name')
            .nodeAutoColorBy('id')
            .backgroundColor('#050510')
            .cooldownTicks(100)
            .enableNodeDrag(true)
            .enablePanInteraction(true)
            .enableZoomInteraction(true)
            .nodeCanvasObjectMode(() => 'replace')
            .onNodeClick(node => {{
                if (node.img) window.open('../' + node.img, '_blank');
            }});

        // Stronger repulsion for a nice galaxy feel
        Graph.d3Force('charge').strength(-150);
        Graph.d3Force('center').strength(0.05);

        Graph.nodeCanvasObject((node, ctx, globalScale) => {{
            // Guard against non-finite coordinates
            if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;

            const size = node.val / 2;
            const isFaded = node.__faded;
            const isHighlighted = node.__highlighted;
            
            // Draw Glow
            if (!isFaded) {{
                const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, size * 2);
                gradient.addColorStop(0, node.color + 'aa');
                gradient.addColorStop(1, 'transparent');
                ctx.fillStyle = gradient;
                ctx.beginPath();
                ctx.arc(node.x, node.y, size * 2, 0, 2 * Math.PI, false);
                ctx.fill();
            }}

            // Draw Node Circle
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = isFaded ? '#111' : (isHighlighted ? '#fff' : node.color);
            ctx.fill();
            
            if (isHighlighted) {{
                ctx.strokeStyle = '#fff';
                ctx.lineWidth = 2 / globalScale;
                ctx.stroke();
            }}

            // Draw Image
            if (node.img && !isFaded) {{
                if (!imgCache[node.img]) {{
                    const img = new Image();
                    img.src = '../' + node.img;
                    imgCache[node.img] = img;
                }}
                const img = imgCache[node.img];
                if (img.complete) {{
                    ctx.save();
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, size - 0.5, 0, 2 * Math.PI, false);
                    ctx.clip();
                    ctx.drawImage(img, node.x - size, node.y - size, size * 2, size * 2);
                    ctx.restore();
                }}
            }}

            // Labels zoom dependent
            if (globalScale > 2 || isHighlighted) {{
                const fontSize = (isHighlighted ? 18 : 12) / globalScale;
                ctx.font = `${{fontSize}}px Sans-Serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillStyle = isHighlighted ? '#fff' : 'rgba(255, 255, 255, 0.7)';
                ctx.fillText(node.name, node.x, node.y + size + 2);
            }}
        }});

        // Search
        let currentQuery = '';
        const searchBox = document.getElementById('searchBox');
        const matchCount = document.getElementById('match-count');

        searchBox.addEventListener('input', e => {{
            currentQuery = e.target.value.trim().toLowerCase();
            if (currentQuery) {{
                const hits = gData.nodes.filter(n =>
                    n.name.toLowerCase().includes(currentQuery) ||
                    n.id.toLowerCase().includes(currentQuery)
                ).length;
                matchCount.textContent = hits ? `${{hits}} match${{hits > 1 ? 'es' : ''}} found` : 'No matches';
            }} else {{
                matchCount.textContent = '';
            }}
            gData.nodes.forEach(node => {{
                node.__highlighted = currentQuery && (
                    node.name.toLowerCase().includes(currentQuery) ||
                    node.id.toLowerCase().includes(currentQuery)
                );
                node.__faded = currentQuery && !node.__highlighted;
            }});
            Graph.refresh();
        }});
    </script>
</body>
</html>"""

    output_file = os.path.join(scraped_data_dir, "forcegraph_nodes_only.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Nodes-only visualization created at {output_file}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=str, default=None)
    parser.add_argument('--output', type=str, default=None)
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    scraped_data_dir = args.input_dir or str(script_dir / "../../scraped_data")
    output_file = args.output or os.path.join(scraped_data_dir, "forcegraph_nodes_only.html")
    generate_nodes_only_viz(scraped_data_dir)
