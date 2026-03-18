#!/usr/bin/env python3
"""
Arc Diagram - Linear Layout with Connection Arcs

Shows nodes in a straight line with arcs above connecting related sites.
Great for seeing long-range connections clearly.
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


def generate_arc_diagram(scraped_data_dir):
    """Generate an arc diagram showing connections."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to analyze")
    
    # Build site data
    site_data = {}
    links = []
    
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        root_url = f"http://{onion_addr}.onion"
        
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
        outbound_count = 0
        for d in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, d)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        with open(os.path.join(path, f), 'r') as lf:
                            for line in lf:
                                if '.onion' in line:
                                    outbound_count += 1
        
        site_data[onion_addr] = {
            'title': title,
            'image': image_path,
            'outbound': outbound_count
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
                                if '.onion' in line:
                                    for target_addr in onion_sites:
                                        if target_addr != onion_addr and target_addr in line:
                                            link_matrix[onion_addr][target_addr] += 1
    
    # Create link list with bidirectional detection
    seen_pairs = set()
    all_links = []
    for source in onion_sites:
        for target in onion_sites:
            if source != target and link_matrix[source][target] > 0:
                is_bidirectional = link_matrix[target][source] > 0
                pair_key = tuple(sorted([source, target]))
                
                if pair_key not in seen_pairs or not is_bidirectional:
                    all_links.append({
                        'source': source,
                        'target': target,
                        'count': link_matrix[source][target],
                        'bidirectional': is_bidirectional
                    })
                    if is_bidirectional:
                        seen_pairs.add(pair_key)
    
    print(f"\nArc Diagram Data:")
    print(f"  Sites: {len(onion_sites)}")
    print(f"  Links: {len(all_links)}")
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Arc Diagram - Connection Overview</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow-x: auto; background: #0d1117; font-family: 'Segoe UI', sans-serif; }}
        #container {{ min-width: 100%; height: 100vh; }}
        #tooltip {{
            position: fixed; padding: 12px; background: rgba(30,30,40,0.95);
            border: 1px solid #444; border-radius: 8px; pointer-events: none;
            opacity: 0; z-index: 100; color: #eee; max-width: 450px;
            transition: opacity 0.2s; font-size: 12px;
            word-break: break-word; white-space: normal;
        }}
        #header {{
            position: fixed; top: 0; left: 0; right: 0;
            background: rgba(13,17,23,0.95); padding: 15px 20px;
            border-bottom: 1px solid #222; z-index: 10;
            display: flex; justify-content: space-between; align-items: center;
        }}
        #header h1 {{ margin: 0; color: #fff; font-size: 18px; }}
        #stats {{ color: #888; font-size: 13px; }}
        .node {{ cursor: pointer; }}
        .node:hover {{ opacity: 0.8; }}
        .arc {{ fill: none; stroke-opacity: 0.3; }}
        .arc:hover {{ stroke-opacity: 0.8; stroke-width: 2px; }}
        #legend {{
            position: fixed; bottom: 20px; left: 20px;
            background: rgba(30,30,40,0.9); padding: 12px;
            border: 1px solid #333; border-radius: 8px;
            z-index: 10; color: #aaa; font-size: 12px;
            line-height: 1.8;
        }}
        #legend strong {{ color: #fff; }}
        .arc-solid {{ stroke-dasharray: 0; }}
        .arc-dashed {{ stroke-dasharray: 4,4; stroke-opacity: 0.5; }}
        #controls {{ position: absolute; top: 20px; right: 20px; z-index: 10; display: flex; flex-direction: column; gap: 8px; }}
        .control-btn {{ background: rgba(30,30,40,0.9); border: 1px solid #444; padding: 10px; cursor: pointer; border-radius: 6px; color: #fff; transition: all 0.2s; }}
        .control-btn:hover {{ background: rgba(50,50,60,0.9); border-color: #666; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Arc Diagram - Site Connections</h1>
        <div id="stats">{len(site_data)} sites | {len(all_links)} directed links</div>
    </div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()" title="Zoom In"><b>+</b></button>
        <button class="control-btn" onclick="zoomOut()" title="Zoom Out"><b>−</b></button>
        <button class="control-btn" onclick="resetView()" title="Reset View">↺</button>
    </div>
    <div id="legend">
        <strong>Network Guide:</strong><br/>
        • Nodes in linear arrangement<br/>
        • Arcs show connections<br/>
        • Blue nodes have screenshots<br/>
        • <span style="color:#fff;">Arc color</span> = source node group<br/>
        • <span style="color:#fff;">Solid arc</span> = one-way link<br/>
        • <span style="color:#fff;">Dashed arc</span> = mutual link (both link to each other)<br/>
        • <span style="color:#fff;">Arc width</span> = number of links
    </div>
    <div id="tooltip"></div>
    <div id="container"></div>

    <script>
        const sites = {json.dumps(list(site_data.keys()))};
        const siteData = {json.dumps(site_data)};
        const links = {json.dumps(all_links)};

        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("#container")
            .append("svg")
            .attr("width", "100%")
            .attr("height", "100vh")
            .attr("viewBox", [0, 0, width, height]);

        const g = svg.append("g").attr("transform", `translate(50,120)`);

        const innerWidth = width - 100;
        const nodeY = 200;  // Position nodes lower to make room for arcs above

        // Zoom
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (e) => g.attr("transform", e.transform));
        svg.call(zoom);

        function zoomIn() {{ svg.transition().duration(400).call(zoom.scaleBy, 1.5); }}
        function zoomOut() {{ svg.transition().duration(400).call(zoom.scaleBy, 0.6); }}
        function resetView() {{ svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity); }}
        
        // Position nodes along x-axis
        const xScale = d3.scalePoint()
            .domain(sites)
            .range([0, innerWidth]);

        const nodeSpacing = innerWidth / Math.max(sites.length - 1, 1);
        
        // Color scale
        const colorScale = d3.scaleOrdinal()
            .domain(sites)
            .range(d3.schemeTableau10);
        
        // Draw arcs
        const arcGenerator = d3.arc()
            .innerRadius(0)
            .outerRadius(d => Math.sqrt(d.count) * 15)
            .startAngle(0)
            .endAngle(Math.PI);
        
        // Group links by source-target pair for cleaner display
        const linkGroups = {{}};
        links.forEach(link => {{
            const key = `${{link.source}}-${{link.target}}`;
            if (!linkGroups[key]) {{
                linkGroups[key] = {{...link, total: 0}};
            }}
            linkGroups[key].total += link.count;
        }});
        
        // Draw arcs
        Object.values(linkGroups).forEach(link => {{
            const x1 = xScale(link.source) + nodeSpacing / 2;
            const x2 = xScale(link.target) + nodeSpacing / 2;
            const centerX = (x1 + x2) / 2;
            const radius = Math.abs(x2 - x1) / 2;

            if (radius > 5) {{  // Only draw if nodes are far enough apart
                const arc = d3.arc()
                    .innerRadius(radius - 1)
                    .outerRadius(radius)
                    .startAngle(Math.PI)
                    .endAngle(0);

                g.append("path")
                    .attr("class", link.bidirectional ? "arc arc-dashed" : "arc arc-solid")
                    .attr("d", arc)
                    .attr("transform", `translate(${{centerX - radius}},${{nodeY - radius}})`)
                    .attr("stroke", colorScale(link.source))
                    .attr("stroke-width", Math.min(link.total, 5))
                    .on("mouseover", (e) => {{
                        d3.select("#tooltip")
                            .style("opacity", 1)
                            .html(`
                                <div style="font-weight: bold; color: #fff;">${{link.source}} → ${{link.target}}</div>
                                <div style="color: #4ade80; margin-top: 5px;">${{link.total}} link(s)</div>
                            `)
                            .style("left", (e.pageX + 15) + "px")
                            .style("top", (e.pageY - 15) + "px");
                        d3.select(e.target).attr("stroke-opacity", 0.8);
                    }})
                    .on("mouseout", (e) => {{
                        d3.select("#tooltip").style("opacity", 0);
                        d3.select(e.target).attr("stroke-opacity", 0.3);
                    }});
            }}
        }});
        
        // Draw nodes
        const nodeGroup = g.selectAll("g")
            .data(sites)
            .join("g")
            .attr("class", "node")
            .attr("transform", d => `translate(${{xScale(d)}},${{nodeY}})`);
        
        // Node circles
        nodeGroup.append("circle")
            .attr("r", d => siteData[d].image ? 25 : 15)
            .attr("fill", d => siteData[d].image ? "#1f6feb" : "#30363d")
            .attr("stroke", d => colorScale(d))
            .attr("stroke-width", 2)
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
        nodeGroup.append("text")
            .attr("y", 45)
            .attr("text-anchor", "middle")
            .attr("fill", "#8b949e")
            .attr("font-size", "9px")
            .text(d => siteData[d].title.length > 20 ? siteData[d].title.substring(0, 17) + "..." : siteData[d].title)
            .attr("pointer-events", "none");

        // Add link count badges
        nodeGroup.filter(d => siteData[d].outbound > 0)
            .append("text")
            .attr("y", -20)
            .attr("text-anchor", "middle")
            .attr("fill", "#4ade80")
            .attr("font-size", "10px")
            .attr("font-weight", "bold")
            .text(d => siteData[d].outbound);

        // Draw baseline
        g.append("line")
            .attr("x1", 0)
            .attr("x2", innerWidth)
            .attr("y1", 0)
            .attr("y2", 0)
            .attr("stroke", "#333")
            .attr("stroke-width", 1)
            .attr("stroke-dasharray", "2,2");
    </script>
</body>
</html>"""
    
    output_file = os.path.join(scraped_data_dir, "arc_diagram.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\nArc Diagram created at {output_file}")
    return output_file


def main():
    scraped_data_dir = "../scraped_data"
    
    if not os.path.exists(scraped_data_dir):
        scraped_data_dir = "scraped_data"
        if not os.path.exists(scraped_data_dir):
            print("Error: scraped_data directory not found")
            return
    
    generate_arc_diagram(scraped_data_dir)


if __name__ == "__main__":
    main()
