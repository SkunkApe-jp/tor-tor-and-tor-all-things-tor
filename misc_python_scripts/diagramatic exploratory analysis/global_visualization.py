#!/usr/bin/env python3
"""
Global Network Visualization Generator - Improved Stability Version

Creates a comprehensive visualization showing all onion sites and their interconnections.
Optimized physics to prevent nodes from flying off-screen or failing to settle.
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

def generate_global_visualization(scraped_data_dir):
    """Generate a global visualization with improved physics and stability."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to visualize")

    site_data = {}
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        urls_dir = os.path.join(site_dir, 'urls')
        htmls_dir = os.path.join(site_dir, 'htmls')
        images_dir = os.path.join(site_dir, 'images')

        all_onion_addresses = set()
        # Check standard urls folder
        if os.path.exists(urls_dir):
            for file_name in os.listdir(urls_dir):
                if file_name.endswith('_links.txt'):
                    links_file_path = os.path.join(urls_dir, file_name)
                    all_onion_addresses.update(extract_onion_addresses_from_file(links_file_path))

        # Also check discovered_links folder
        discovered_links_dir = os.path.join(site_dir, 'discovered_links')
        if os.path.exists(discovered_links_dir):
            for file_name in os.listdir(discovered_links_dir):
                if file_name.endswith('_links.txt'):
                    links_file_path = os.path.join(discovered_links_dir, file_name)
                    all_onion_addresses.update(extract_onion_addresses_from_file(links_file_path))

        main_html_file = os.path.join(htmls_dir, f"{onion_addr}.html")
        title = extract_title_from_html(main_html_file)
        if not title:
            title = f"{onion_addr}.onion"

        index_image_path = os.path.join(images_dir, "index.png")
        onion_image_path = os.path.join(images_dir, f"{onion_addr}.png")
        
        if os.path.exists(index_image_path):
            image_path = f"{onion_addr}/images/index.png"
        elif os.path.exists(onion_image_path):
            image_path = f"{onion_addr}/images/{onion_addr}.png"
        else:
            image_path = ""

        site_data[onion_addr] = {
            'title': title,
            'connected_onions': list(all_onion_addresses),
            'image_path': image_path
        }

    nodes = []
    links = []
    addr_to_idx = {}

    for idx, (addr, data) in enumerate(site_data.items()):
        addr_to_idx[addr] = idx
        nodes.append({
            'id': addr,
            'name': f"http://{addr}.onion",
            'title': data['title'],
            'image': data['image_path'],
            'group': 1
        })

    for source_addr, data in site_data.items():
        if source_addr in addr_to_idx:
            source_idx = addr_to_idx[source_addr]
            for connected_addr in data['connected_onions']:
                pure_connected_addr = connected_addr.replace('.onion', '')
                if pure_connected_addr in addr_to_idx:
                    dest_idx = addr_to_idx[pure_connected_addr]
                    if source_idx != dest_idx:
                        links.append({
                            'source': source_idx,
                            'target': dest_idx,
                            'value': 1
                        })

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Global Onion Network Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; background-color: #fafafa; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }}
        #tooltip {{
            position: absolute; padding: 10px; background: white;
            border: 1px solid #ddd; border-radius: 8px; pointer-events: none;
            opacity: 0; transition: opacity 0.2s; z-index: 100; box-shadow: 0 4px 12px rgba(0,0,0,0.1);
        }}
        .link {{ stroke: #999; stroke-opacity: 0.4; stroke-width: 1.2px; }}
        #title, #legend {{ position: absolute; background: rgba(255, 255, 255, 0.9); padding: 12px; border: 1px solid #eee; border-radius: 8px; z-index: 10; backdrop-filter: blur(4px); }}
        #title {{ top: 20px; left: 20px; font-weight: bold; font-size: 18px; }}
        #legend {{ bottom: 20px; left: 20px; font-size: 13px; color: #555; line-height: 1.6; }}
        #controls {{ position: absolute; top: 20px; right: 20px; z-index: 10; display: flex; flex-direction: column; gap: 8px; }}
        .control-btn {{ background: white; border: 1px solid #ccc; padding: 10px; cursor: pointer; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); transition: all 0.2s; }}
        .control-btn:hover {{ background: #f0f0f0; border-color: #999; }}
    </style>
</head>
<body>
    <div id="title">Global Onion Network <span style="font-weight: normal; color: #666;">({len(nodes)} sites)</span></div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()" title="Zoom In"><b>+</b></button>
        <button class="control-btn" onclick="zoomOut()" title="Zoom Out"><b>−</b></button>
        <button class="control-btn" onclick="resetView()" title="Reset View">↺</button>
    </div>
    <div id="tooltip"></div>
    <div id="legend">
        <strong>Network Guide:</strong><br/>
        • Nodes represent .onion sites<br/>
        • Arrows indicate outbound links<br/>
        • Drag nodes to reorganize<br/>
        • Click node to view screenshot
    </div>
    <script>
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};

        // Pre-position nodes to prevent "explosion" from center
        const width = window.innerWidth;
        const height = window.innerHeight;
        nodes.forEach((d, i) => {{
            d.x = width / 2 + (Math.random() - 0.5) * 100;
            d.y = height / 2 + (Math.random() - 0.5) * 100;
        }});

        const svg = d3.select("body").append("svg")
            .attr("width", "100%")
            .attr("height", "100vh")
            .attr("viewBox", [0, 0, width, height]);

        const g = svg.append("g");
        const zoom = d3.zoom().scaleExtent([0.05, 10]).on("zoom", (e) => g.attr("transform", e.transform));
        svg.call(zoom);

        function zoomIn() {{ svg.transition().duration(400).call(zoom.scaleBy, 1.5); }}
        function zoomOut() {{ svg.transition().duration(400).call(zoom.scaleBy, 0.6); }}
        function resetView() {{ svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity); }}

        // Define arrowhead marker
        g.append("defs").append("marker")
            .attr("id", "arrowhead")
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 10)
            .attr("refY", 0)
            .attr("orient", "auto")
            .attr("markerWidth", 5)
            .attr("markerHeight", 5)
            .append("path")
            .attr("d", "M0,-5 L10,0 L0,5")
            .attr("fill", "#999");

        const simulation = d3.forceSimulation(nodes)
            .alphaDecay(0.04)
            .force("link", d3.forceLink(links).id((d, i) => i).distance(180).strength(0.3))
            .force("charge", d3.forceManyBody().strength(-300).distanceMax(600))
            .force("x", d3.forceX(width / 2).strength(0.08))
            .force("y", d3.forceY(height / 2).strength(0.08))
            .force("collision", d3.forceCollide().radius(d => d.image ? 55 : 20));

        const link = g.append("g")
            .selectAll("line")
            .data(links)
            .join("line")
            .attr("class", "link")
            .attr("marker-end", "url(#arrowhead)");

        const node = g.append("g")
            .selectAll("g")
            .data(nodes)
            .join("g")
            .attr("cursor", "move")
            .on("click", (e, d) => d.image && window.open(d.image, '_blank'))
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

        // Images for screenshot nodes
        node.filter(d => d.image)
            .append("circle")
            .attr("r", 40)
            .attr("fill", "#fff")
            .attr("stroke", "#ddd");

        node.filter(d => d.image)
            .append("image")
            .attr("xlink:href", d => d.image)
            .attr("x", -40).attr("y", -40).attr("width", 80).attr("height", 80)
            .attr("clip-path", "circle(38px at 40px 40px)");

        // Circles for text-only nodes
        node.filter(d => !d.image)
            .append("circle")
            .attr("r", 10)
            .attr("fill", "#333");

        const label = g.append("g")
            .selectAll("text")
            .data(nodes)
            .join("text")
            .text(d => d.title.length > 20 ? d.title.substring(0, 18) + '...' : d.title)
            .attr("font-size", "11px")
            .attr("fill", "#444")
            .attr("dx", 15)
            .attr("dy", 4)
            .attr("paint-order", "stroke")
            .attr("stroke", "#fff")
            .attr("stroke-width", "3px");

        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => {{
                    const radius = d.target.image ? 45 : 12;
                    const dx = d.target.x - d.source.x;
                    const dy = d.target.y - d.source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    return d.target.x - (dx * radius / dist);
                }})
                .attr("y2", d => {{
                    const radius = d.target.image ? 45 : 12;
                    const dx = d.target.x - d.source.x;
                    const dy = d.target.y - d.source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    return d.target.y - (dy * radius / dist);
                }});

            node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
            label.attr("x", d => d.x).attr("y", d => d.y);
        }});

        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}
        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            // Keep nodes fixed where they're dropped (no spring back)
            d.fx = d.x;
            d.fy = d.y;
        }}
    </script>
</body>
</html>"""

    output_file = os.path.join(scraped_data_dir, "global_network_visualization.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Visualization created at {output_file}")
    return output_file

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
