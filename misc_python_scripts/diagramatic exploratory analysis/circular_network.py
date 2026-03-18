#!/usr/bin/env python3
"""
Circular Network - Nodes Arranged in Circle with Chord Links

Shows all sites arranged in a circle with links as internal chords.
Symmetrical view that makes it easy to see connection patterns.
"""

import os
import json
import re
from pathlib import Path
from collections import defaultdict


def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and re.match(r'^[a-z2-7]{16,56}$', item):
            onion_dirs.append(item)
    return onion_dirs


def extract_title_from_html(html_file_path):
    """Extract title from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    return ' '.join(title_match.group(1).strip().split())[:25]
        except Exception:
            pass
    return None


def generate_circular_network(scraped_data_dir):
    """Generate a circular network visualization."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to analyze")
    
    # Build site data and links
    site_data = {}
    links = []
    
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        
        # Get title
        html_file = os.path.join(site_dir, 'htmls', f"{onion_addr}.html")
        title = extract_title_from_html(html_file) or onion_addr[:20]
        
        # Get image
        image_path = ""
        for img_name in ["index.png", f"{onion_addr}.png"]:
            img_path = os.path.join(site_dir, 'images', img_name)
            if os.path.exists(img_path):
                image_path = f"{onion_addr}/images/{img_name}"
                break
        
        # Count links
        outbound = 0
        for d in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, d)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        with open(os.path.join(path, f), 'r') as lf:
                            outbound += sum(1 for line in lf if '.onion' in line)
        
        site_data[onion_addr] = {
            'title': title,
            'image': image_path,
            'outbound': outbound
        }
    
    # Build link matrix
    link_matrix = defaultdict(lambda: defaultdict(int))
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        for d in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, d)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        with open(os.path.join(path, f), 'r') as lf:
                            for line in lf:
                                for target in onion_sites:
                                    if target != onion_addr and target in line:
                                        link_matrix[onion_addr][target] += 1
    
    # Create link list with bidirectional detection
    seen_pairs = set()
    for source in onion_sites:
        for target in onion_sites:
            if source != target and link_matrix[source][target] > 0:
                # Check if reverse link exists (bidirectional)
                is_bidirectional = link_matrix[target][source] > 0
                pair_key = tuple(sorted([source, target]))
                
                # Only add each pair once for bidirectional, but mark it
                if pair_key not in seen_pairs or not is_bidirectional:
                    links.append({
                        'source': source,
                        'target': target,
                        'count': link_matrix[source][target],
                        'bidirectional': is_bidirectional
                    })
                    if is_bidirectional:
                        seen_pairs.add(pair_key)
    
    print(f"\nCircular Network Data:")
    print(f"  Sites: {len(onion_sites)}")
    print(f"  Links: {len(links)}")
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Circular Network</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; background: #0a0a0f; font-family: 'Segoe UI', sans-serif; }}
        #tooltip {{
            position: fixed; padding: 12px; background: rgba(30,30,40,0.95);
            border: 1px solid #444; border-radius: 8px; pointer-events: none;
            opacity: 0; z-index: 100; color: #eee; max-width: 450px;
            transition: opacity 0.2s; font-size: 12px;
            word-break: break-word; white-space: normal;
        }}
        #header {{
            position: fixed; top: 0; left: 0; right: 0;
            background: rgba(10,10,15,0.95); padding: 15px 20px;
            border-bottom: 1px solid #222; z-index: 10;
            display: flex; justify-content: space-between; align-items: center;
        }}
        #header h1 {{ margin: 0; color: #fff; font-size: 18px; }}
        #stats {{ color: #888; font-size: 13px; }}
        #legend {{
            position: fixed; bottom: 20px; left: 20px;
            background: rgba(30,30,40,0.9); padding: 12px;
            border: 1px solid #333; border-radius: 8px;
            z-index: 10; color: #aaa; font-size: 12px;
            line-height: 1.8;
        }}
        #legend strong {{ color: #fff; }}
        .link-solid {{ stroke-dasharray: 0; }}
        .link-dashed {{ stroke-dasharray: 4,4; stroke-opacity: 0.5; }}
        #controls {{ position: absolute; top: 20px; right: 20px; z-index: 10; display: flex; flex-direction: column; gap: 8px; }}
        .control-btn {{ background: rgba(30,30,40,0.9); border: 1px solid #444; padding: 10px; cursor: pointer; border-radius: 6px; color: #fff; transition: all 0.2s; }}
        .control-btn:hover {{ background: rgba(50,50,60,0.9); border-color: #666; }}
        .node {{ cursor: pointer; }}
        .node:hover {{ opacity: 0.8; }}
        .link {{ stroke-opacity: 0.4; }}
        .link:hover {{ stroke-opacity: 0.9; stroke-width: 2px; filter: drop-shadow(0 0 4px currentColor); }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Circular Network - Site Connections</h1>
        <div id="stats">{len(site_data)} sites | {len(links)} directed links</div>
    </div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()" title="Zoom In"><b>+</b></button>
        <button class="control-btn" onclick="zoomOut()" title="Zoom Out"><b>−</b></button>
        <button class="control-btn" onclick="resetView()" title="Reset View">↺</button>
    </div>
    <div id="legend">
        <strong>Network Guide:</strong><br/>
        • Nodes arranged in circle<br/>
        • Chords show connections<br/>
        • Blue nodes have screenshots<br/>
        • <span style="color:#fff;">Line color</span> = source node group<br/>
        • <span style="color:#fff;">Solid line</span> = one-way link<br/>
        • <span style="color:#fff;">Dashed line</span> = mutual link (both sites link to each other)<br/>
        • <span style="color:#fff;">Line width</span> = number of links<br/>
        • Scroll to zoom, drag to pan
    </div>
    <div id="tooltip"></div>

    <script>
        const sites = {json.dumps(list(site_data.keys()))};
        const siteData = {json.dumps(site_data)};
        const links = {json.dumps(links)};

        const width = window.innerWidth;
        const height = window.innerHeight;
        const radius = Math.min(width, height) * 0.4;
        const centerX = width / 2;
        const centerY = height / 2;

        const svg = d3.select("body").append("svg")
            .attr("width", "100%")
            .attr("height", "100vh")
            .attr("viewBox", [-width/2, -height/2, width, height]);

        // Center group - no translate needed since viewBox is centered
        const zoomG = svg.append("g");

        // Zoom with pan
        const zoom = d3.zoom()
            .scaleExtent([0.2, 4])
            .on("zoom", (e) => zoomG.attr("transform", e.transform));
        svg.call(zoom);

        function zoomIn() {{ svg.transition().duration(400).call(zoom.scaleBy, 1.5); }}
        function zoomOut() {{ svg.transition().duration(400).call(zoom.scaleBy, 0.6); }}
        function resetView() {{ svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity); }}
        
        // Position nodes in circle
        const angleStep = (2 * Math.PI) / sites.length;
        const nodePositions = {{}};
        
        sites.forEach((site, i) => {{
            const angle = i * angleStep - Math.PI / 2;
            nodePositions[site] = {{
                x: radius * Math.cos(angle),
                y: radius * Math.sin(angle),
                angle: angle
            }};
        }});
        
        // Generate vibrant random colors for each site
        // Uses golden ratio distribution for maximum color variety
        const goldenRatio = 0.618033988749895;
        let hue = Math.random(); // Start at random hue
        
        const colorScale = d3.scaleOrdinal()
            .domain(sites)
            .range(sites.map((_, i) => {{
                hue = (hue + goldenRatio) % 1; // Increment by golden ratio
                const saturation = 0.65 + Math.random() * 0.2; // 65-85%
                const lightness = 0.45 + Math.random() * 0.2; // 45-65%
                return d3.color(`hsl(${{hue * 360}}, ${{saturation * 100}}%, ${{lightness * 100}}%)`).formatHex();
            }}));
        
        // Draw links as bezier curves
        const linkGroup = zoomG.append("g");
        
        links.forEach(link => {{
            const source = nodePositions[link.source];
            const target = nodePositions[link.target];
            
            // Calculate control point for bezier curve
            const midX = (source.x + target.x) / 2;
            const midY = (source.y + target.y) / 2;
            // Offset control point toward center for curved effect
            const dist = Math.sqrt(midX * midX + midY * midY);
            const offset = Math.min(dist * 0.3, 100);
            const controlX = midX * (1 - offset / dist);
            const controlY = midY * (1 - offset / dist);
            
            const path = d3.path();
            path.moveTo(source.x, source.y);
            path.quadraticCurveTo(controlX, controlY, target.x, target.y);
            
            linkGroup.append("path")
                .attr("class", link.bidirectional ? "link link-dashed" : "link link-solid")
                .attr("d", path.toString())
                .attr("stroke", colorScale(link.source))
                .attr("stroke-width", Math.min(link.count, 5))
                .attr("fill", "none")
                .attr("stroke-opacity", 0.5)
                .on("mouseover", (e) => {{
                    d3.select("#tooltip")
                        .style("opacity", 1)
                        .html(`
                            <div style="font-weight: bold; color: #fff;">${{link.source}} → ${{link.target}}</div>
                            <div style="color: #4ade80; margin-top: 5px;">${{link.count}} link(s)</div>
                        `)
                        .style("left", (e.pageX + 15) + "px")
                        .style("top", (e.pageY - 15) + "px");
                    d3.select(e.target).attr("stroke-opacity", 0.8);
                }})
                .on("mouseout", (e) => {{
                    d3.select("#tooltip").style("opacity", 0);
                    d3.select(e.target).attr("stroke-opacity", 0.3);
                }});
        }});
        
        // Draw nodes
        const nodeGroup = zoomG.append("g");
        
        const nodes = nodeGroup.selectAll("g")
            .data(sites)
            .join("g")
            .attr("class", "node")
            .attr("transform", d => `translate(${{nodePositions[d].x}},${{nodePositions[d].y}})`);
        
        // Node circles
        nodes.append("circle")
            .attr("r", d => siteData[d].image ? 30 : 18)
            .attr("fill", d => siteData[d].image ? "#1f6feb" : "#30363d")
            .attr("stroke", d => colorScale(d))
            .attr("stroke-width", 3)
            .on("mouseover", (e, d) => {{
                const data = siteData[d];
                d3.select("#tooltip")
                    .style("opacity", 1)
                    .html(`
                        <div style="font-weight: bold; color: #fff;">${{data.title}}</div>
                        <div style="color: #888; font-size: 10px; word-break: break-all;">${{d}}</div>
                        <div style="margin-top: 8px; color: #4ade80;">${{data.outbound}} outbound links</div>
                        ${{data.image ? '<div style="color: #aaa; margin-top: 5px;">📸 Has screenshot</div>' : ''}}
                    `)
                    .style("left", (e.pageX + 15) + "px")
                    .style("top", (e.pageY - 15) + "px");
                d3.select(e.target).attr("opacity", 0.7);
            }})
            .on("mouseout", (e) => {{
                d3.select("#tooltip").style("opacity", 0);
                d3.select(e.target).attr("opacity", 1);
            }})
            .on("click", (e, d) => {{
                if (siteData[d].image) window.open(siteData[d].image, '_blank');
            }});
        
        // Node labels
        nodes.append("text")
            .attr("dy", d => {{
                const pos = nodePositions[d];
                const angle = pos.angle;
                // Labels outside circle
                if (angle > -Math.PI/2 && angle < Math.PI/2) {{
                    return 45;
                }} else if (angle > Math.PI/2 || angle < -Math.PI/2) {{
                    return -35;
                }}
                return 40;
            }})
            .attr("dx", d => {{
                const pos = nodePositions[d];
                const angle = pos.angle;
                if (Math.abs(angle) < Math.PI/6 || Math.abs(angle) > 5*Math.PI/6) {{
                    return 0;
                }} else if (angle > 0) {{
                    return 40;
                }} else {{
                    return -40;
                }}
            }})
            .attr("text-anchor", "middle")
            .attr("fill", "#8b949e")
            .attr("font-size", "10px")
            .text(d => siteData[d].title);
        
        // Add link count badges
        nodes.filter(d => siteData[d].outbound > 0)
            .append("text")
            .attr("text-anchor", "middle")
            .attr("fill", "#4ade80")
            .attr("font-size", "11px")
            .attr("font-weight", "bold")
            .attr("dy", -8)
            .text(d => siteData[d].outbound);
        
        // Draw outer circle
        zoomG.append("circle")
            .attr("cx", 0)
            .attr("cy", 0)
            .attr("r", radius)
            .attr("fill", "none")
            .attr("stroke", "#30363d")
            .attr("stroke-width", 2)
            .attr("stroke-dasharray", "5,5");
    </script>
</body>
</html>"""
    
    output_file = os.path.join(scraped_data_dir, "circular_network.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\nCircular Network created at {output_file}")
    return output_file


def main():
    scraped_data_dir = "../scraped_data"
    
    if not os.path.exists(scraped_data_dir):
        scraped_data_dir = "scraped_data"
        if not os.path.exists(scraped_data_dir):
            print("Error: scraped_data directory not found")
            return
    
    generate_circular_network(scraped_data_dir)


if __name__ == "__main__":
    main()
