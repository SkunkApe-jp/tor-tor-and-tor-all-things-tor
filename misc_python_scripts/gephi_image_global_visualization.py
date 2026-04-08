#!/usr/bin/env python3
"""
Global Network Visualization Generator - Static Image Version

Creates a high-resolution static image of the network using NetworkX and Matplotlib.
Optimized for large datasets (10k+ nodes) where interactive web visualizations fail.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path
import matplotlib.pyplot as plt
import networkx as nx

def extract_onion_addresses_from_file(file_path):
    """Extract all unique onion addresses from a links file."""
    onion_addresses = set()
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Support both v2 and v3 onion addresses
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
        # Match v3 addresses (56 chars) or v2 (16 chars)
        if os.path.isdir(item_path) and re.match(r'^[a-z2-7]{16,56}$', item):
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
        except Exception as e:
            print(f"Error reading {html_file_path}: {str(e)}")
    return None

def find_screenshot_path(onion_address, scraped_data_dir):
    """Strict-path screenshot lookup."""
    clean_addr = onion_address.replace('.onion', '')
    image_dir = os.path.join(scraped_data_dir, clean_addr, 'images')
    if not os.path.exists(image_dir): return ""
    
    # Global map usually just shows root images
    index_path = os.path.join(image_dir, "index.png")
    if os.path.exists(index_path):
        return f"{clean_addr}/images/index.png"
    return ""

def generate_global_visualization(scraped_data_dir, export_gexf=True):
    """Generate a global visualization with full interactivity."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to visualize")

    site_data = {}
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        urls_dir = os.path.join(site_dir, 'urls')
        
        # 1. Title Discovery
        title = None
        identity_dir = os.path.join(site_dir, 'website_identity')
        if os.path.exists(identity_dir):
            for f in os.listdir(identity_dir):
                if f.endswith('_title.txt'):
                    try:
                        with open(os.path.join(identity_dir, f), 'r', encoding='utf-8') as tf:
                            line = tf.readline()
                            if '->' in line: title = line.split('->', 1)[0].strip().strip('[]')
                    except: pass
        if not title:
            title = extract_title_from_html(os.path.join(site_dir, 'htmls', f"{onion_addr}.html")) or f"{onion_addr}.onion"

        # 2. Link Discovery
        all_links = set()
        for d in ['urls', 'discovered_links']:
            p = os.path.join(site_dir, d)
            if os.path.exists(p):
                for f in os.listdir(p):
                    if f.endswith('_links.txt'):
                        all_links.update(extract_onion_addresses_from_file(os.path.join(p, f)))

        site_data[onion_addr] = {
            'title': title,
            'connected_onions': list(all_links),
            'image_path': find_screenshot_path(onion_addr, scraped_data_dir)
        }

    # Prepare JSON for HTML Visualization
    nodes = []
    links = []
    addr_to_idx = {}
    for idx, (addr, data) in enumerate(site_data.items()):
        addr_to_idx[addr] = idx
        nodes.append({
            'id': addr,
            'title': data['title'],
            'image': data['image_path'],
            'group': 1
        })
    for source_addr, data in site_data.items():
        for conn in data['connected_onions']:
            pure = conn.replace('.onion', '')
            if pure in addr_to_idx and source_addr != pure:
                links.append({'source': addr_to_idx[source_addr], 'target': addr_to_idx[pure]})

    # --- HTML BLOCK ---
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Interconnected Gephi Network</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; background: #050505; color: #fff; font-family: 'Segoe UI', sans-serif; overflow: hidden; }}
        #tooltip {{
            position: absolute; padding: 15px; background: rgba(0,0,0,0.85);
            backdrop-filter: blur(8px); border: 1px solid #333; border-radius: 8px;
            pointer-events: none; opacity: 0; transition: opacity 0.2s; z-index: 100;
        }}
        #tooltip img {{ max-width: 250px; border-radius: 4px; margin-top: 10px; border: 1px solid #444; }}
        .link {{ stroke: #444; stroke-opacity: 0.4; }}
        #overlay {{ position: absolute; top: 20px; left: 20px; z-index: 10; }}
        h1 {{ margin: 0; font-size: 20px; color: #00DAFF; }}
    </style>
</head>
<body>
    <div id="overlay"><h1>Interconnected Gephi Network</h1></div>
    <div id="tooltip"></div>
    <script>
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};
        const width = window.innerWidth, height = window.innerHeight;

        const svg = d3.select("body").append("svg").attr("width", "100%").attr("height", "100vh");
        const g = svg.append("g");
        svg.call(d3.zoom().on("zoom", (e) => g.attr("transform", e.transform)));

        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id((d, i) => i).distance(150))
            .force("charge", d3.forceManyBody().strength(-400))
            .force("center", d3.forceCenter(width/2, height/2));

        const link = g.append("g").selectAll("line").data(links).join("line").attr("class", "link");

        const node = g.append("g").selectAll("g").data(nodes).join("g")
            .on("mouseover", (event, d) => {{
                d3.select("#tooltip").style("opacity", 1)
                  .html(`<b>${{d.title}}</b><br/><small>${{d.id}}.onion</small>${{d.image ? `<br/><img src="${{d.image}}">` : ''}}`)
                  .style("left", (event.pageX + 15) + "px").style("top", (event.pageY + 15) + "px");
            }})
            .on("mouseout", () => d3.select("#tooltip").style("opacity", 0))
            .call(d3.drag().on("start", (e, d) => {{ if (!e.active) simulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; }})
                          .on("drag", (e, d) => {{ d.fx = e.x; d.fy = e.y; }})
                          .on("end", (e, d) => {{ if (!e.active) simulation.alphaTarget(0); d.fx = null; d.fy = null; }}));

        node.append("circle").attr("r", d => d.image ? 15 : 8).attr("fill", d => d.image ? "#00DAFF" : "#555");
        node.append("text").text(d => d.title.substring(0, 15)).attr("dy", 25).attr("text-anchor", "middle").attr("fill", "#aaa").attr("font-size", "10px");

        simulation.on("tick", () => {{
            link.attr("x1", d => d.source.x).attr("y1", d => d.source.y).attr("x2", d => d.target.x).attr("y2", d => d.target.y);
            node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }});
    </script>
</body>
</html>"""
    
    with open(os.path.join(scraped_data_dir, "gephi_interactive_viz.html"), 'w', encoding='utf-8') as f:
        f.write(html_content)

    # --- GEOT / GEXF BLOCK ---
    print(f"Building Graph for {len(site_data)} nodes...")
    import networkx as nx
    G = nx.Graph()
    for addr, data in site_data.items():
        # Important: For Gephi plugins, absolute paths are most reliable
        abs_img = os.path.abspath(os.path.join(scraped_data_dir, data['image_path'])) if data['image_path'] else ""
        G.add_node(addr, title=data['title'], image=abs_img)
    
    for source_addr, data in site_data.items():
        for connected_addr in data['connected_onions']:
            pure = connected_addr.replace('.onion', '')
            if pure in site_data and source_addr != pure:
                G.add_edge(source_addr, pure)

    if export_gexf:
        gexf_file = os.path.join(scraped_data_dir, "global_network.gexf")
        nx.write_gexf(G, gexf_file)
        print(f"Interactive HTML and GEXF exported to {scraped_data_dir}")

    return os.path.join(scraped_data_dir, "gephi_interactive_viz.html")

def main():
    scraped_data_dir = "../scraped_data"

    if not os.path.exists(scraped_data_dir):
        scraped_data_dir = "scraped_data"
        if not os.path.exists(scraped_data_dir):
            print(f"Error: scraped_data directory not found")
            return

    generate_global_visualization(scraped_data_dir)

if __name__ == "__main__":
    main()
