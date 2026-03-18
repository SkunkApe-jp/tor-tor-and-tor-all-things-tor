#!/usr/bin/env python3
"""
Adjacency Matrix - Grid Heatmap of Connections

Shows site-to-site connections as a grid heatmap.
Great for finding isolated vs highly-connected sites at a glance.
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
                    return ' '.join(title_match.group(1).strip().split())[:20]
        except Exception:
            pass
    return None


def generate_adjacency_matrix(scraped_data_dir):
    """Generate an adjacency matrix heatmap."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to analyze")
    
    # Build link matrix
    site_data = {}
    matrix = []
    
    for i, source_addr in enumerate(onion_sites):
        site_dir = os.path.join(scraped_data_dir, source_addr)
        
        # Get title and image
        html_file = os.path.join(site_dir, 'htmls', f"{source_addr}.html")
        title = extract_title_from_html(html_file) or source_addr[:16]
        
        image_path = ""
        for img_name in ["index.png", f"{source_addr}.png"]:
            img_path = os.path.join(site_dir, 'images', img_name)
            if os.path.exists(img_path):
                image_path = f"{source_addr}/images/{img_name}"
                break
        
        # Count outbound links to each target
        row = []
        outbound_total = 0
        for target_addr in onion_sites:
            count = 0
            if source_addr != target_addr:
                for d in ['urls', 'discovered_links']:
                    path = os.path.join(site_dir, d)
                    if os.path.exists(path):
                        for f in os.listdir(path):
                            if f.endswith('_links.txt'):
                                with open(os.path.join(path, f), 'r') as lf:
                                    for line in lf:
                                        if target_addr in line and '.onion' in line:
                                            count += 1
            row.append(count)
            outbound_total += count
        
        # Count inbound links
        inbound_total = 0
        for other_addr in onion_sites:
            if other_addr != source_addr:
                other_dir = os.path.join(scraped_data_dir, other_addr)
                for d in ['urls', 'discovered_links']:
                    path = os.path.join(other_dir, d)
                    if os.path.exists(path):
                        for f in os.listdir(path):
                            if f.endswith('_links.txt'):
                                with open(os.path.join(path, f), 'r') as lf:
                                    for line in lf:
                                        if source_addr in line and '.onion' in line:
                                            inbound_total += 1
        
        site_data[source_addr] = {
            'title': title,
            'image': image_path,
            'outbound': outbound_total,
            'inbound': inbound_total
        }
        matrix.append(row)
    
    print(f"\nMatrix Data:")
    print(f"  Sites: {len(onion_sites)}")
    print(f"  Matrix: {len(matrix)}x{len(matrix[0])}")
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Adjacency Matrix - Connection Heatmap</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; background: #0d1117; font-family: 'Segoe UI', sans-serif; }}
        #container {{ }}
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
        #legend {{
            position: fixed; bottom: 20px; left: 20px;
            background: rgba(30,30,40,0.9); padding: 12px;
            border-radius: 8px; border: 1px solid #333; z-index: 10;
            color: #aaa; font-size: 12px; line-height: 1.8;
        }}
        #legend strong {{ color: #fff; }}
        #controls {{ position: absolute; top: 20px; right: 20px; z-index: 10; display: flex; flex-direction: column; gap: 8px; }}
        .control-btn {{ background: rgba(30,30,40,0.9); border: 1px solid #444; padding: 10px; cursor: pointer; border-radius: 6px; color: #fff; transition: all 0.2s; }}
        .control-btn:hover {{ background: rgba(50,50,60,0.9); border-color: #666; }}
        .cell {{ stroke: #1f2937; stroke-width: 0.5px; }}
        .cell:hover {{ stroke: #fff; stroke-width: 2px; }}
        .axis-label {{ fill: #8b949e; font-size: 9px; }}
        .axis-label.highlight {{ fill: #fff; font-weight: bold; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Adjacency Matrix - Site Connection Heatmap</h1>
        <div id="stats">{len(site_data)} sites × {len(site_data)} matrix</div>
    </div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()">+</button>
        <button class="control-btn" onclick="zoomOut()">−</button>
        <button class="control-btn" onclick="resetView()">↺</button>
    </div>
    <div id="legend">
        <strong>How to read:</strong><br/>
        • Row = Source site (who links)<br/>
        • Column = Target site (who is linked)<br/>
        • Bright cell = Many links<br/>
        • Dark cell = No/few links<br/>
        • Scroll to zoom, drag to pan
    </div>
    <div id="tooltip"></div>
    <div id="container"></div>

    <script>
        const sites = {json.dumps(onion_sites)};
        const siteData = {json.dumps(site_data)};
        const matrix = {json.dumps(matrix)};

        const width = window.innerWidth;
        const height = window.innerHeight;
        const cellSize = 20;
        const labelWidth = 100;
        const labelHeight = 60;
        const matrixSize = sites.length * cellSize;
        const totalWidth = labelWidth + matrixSize;
        const totalHeight = labelHeight + matrixSize;

        const svg = d3.select("#container")
            .append("svg")
            .attr("width", "100%")
            .attr("height", "100vh")
            .attr("viewBox", [0, 0, width, height]);

        // Center the entire matrix (including labels)
        const offsetX = (width - totalWidth) / 2;
        const offsetY = (height - totalHeight) / 2;

        const centerG = svg.append("g")
            .attr("transform", `translate(${{offsetX}}, ${{offsetY}})`);

        const zoomG = centerG.append("g");

        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .translateExtent([[-labelWidth, -labelHeight], [totalWidth, totalHeight]])
            .on("zoom", (e) => zoomG.attr("transform", e.transform));
        svg.call(zoom);

        function zoomIn() {{ svg.transition().duration(400).call(zoom.scaleBy, 1.5, [width/2, height/2]); }}
        function zoomOut() {{ svg.transition().duration(400).call(zoom.scaleBy, 0.6, [width/2, height/2]); }}
        function resetView() {{ svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity); }}

        // Color scale for link count
        const maxLinks = Math.max(...matrix.flat());
        const colorScale = d3.scaleSequential(d3.interpolateYlOrRd)
            .domain([0, Math.max(maxLinks, 1)]);

        // Draw cells - positioned relative to label area
        const cells = zoomG.selectAll("rect")
            .data(matrix.flat())
            .join("rect")
            .attr("class", "cell")
            .attr("x", (d, i) => {{
                const col = i % sites.length;
                return labelWidth + col * cellSize;
            }})
            .attr("y", (d, i) => {{
                const row = Math.floor(i / sites.length);
                return labelHeight + row * cellSize;
            }})
            .attr("width", cellSize)
            .attr("height", cellSize)
            .attr("fill", d => colorScale(d))
            .on("mouseover", (e, d) => {{
                const i = matrix.flat().indexOf(d);
                const row = Math.floor(i / sites.length);
                const col = i % sites.length;
                const source = sites[row];
                const target = sites[col];

                d3.select("#tooltip")
                    .style("opacity", 1)
                    .html(`
                        <div style="font-weight: bold; color: #fff;">${{source}} → ${{target}}</div>
                        <div style="margin-top: 5px;">
                            <span style="color: #fbbf24;">${{d}}</span> links
                        </div>
                        <div style="margin-top: 8px; font-size: 10px; color: #888;">
                            Source outbound: ${{siteData[source].outbound}}<br/>
                            Target inbound: ${{siteData[target].inbound}}
                        </div>
                    `)
                    .style("left", (e.pageX + 15) + "px")
                    .style("top", (e.pageY - 15) + "px");
                
                // Highlight row and column
                d3.selectAll(".row-" + row).attr("stroke", "#fff").attr("stroke-width", 1);
                d3.selectAll(".col-" + col).attr("stroke", "#fff").attr("stroke-width", 1);
                d3.selectAll(".axis-label").classed("highlight", l => l === row || l === col);
            }})
            .on("mouseout", (e, d) => {{
                d3.select("#tooltip").style("opacity", 0);
                d3.selectAll("rect").attr("stroke", "#1f2937").attr("stroke-width", 0.5);
                d3.selectAll(".axis-label").classed("highlight", false);
            }});
        
        // Add row labels (Y-axis - Source)
        sites.forEach((site, i) => {{
            zoomG.append("text")
                .attr("class", "axis-label")
                .attr("x", labelWidth - 5)
                .attr("y", labelHeight + i * cellSize + cellSize / 2 + 4)
                .attr("text-anchor", "end")
                .text(siteData[site].title.length > 12 ? siteData[site].title.substring(0, 10) + "..." : siteData[site].title);
            
            // Add screenshot indicator
            if (siteData[site].image) {{
                zoomG.append("text")
                    .attr("x", labelWidth - 5)
                    .attr("y", labelHeight + i * cellSize + cellSize / 2 - 5)
                    .attr("text-anchor", "end")
                    .attr("font-size", "8px")
                    .attr("fill", "#4ade80")
                    .text("📸");
            }}
        }});

        // Add column labels (X-axis - Target)
        sites.forEach((site, i) => {{
            zoomG.append("text")
                .attr("class", "axis-label")
                .attr("x", labelWidth + i * cellSize + cellSize / 2)
                .attr("y", labelHeight - 5)
                .attr("text-anchor", "middle")
                .attr("transform", `rotate(-45, ${{labelWidth + i * cellSize + cellSize / 2}}, ${{labelHeight - 5}})`)
                .text(siteData[site].title.length > 12 ? siteData[site].title.substring(0, 10) + "..." : siteData[site].title);
        }});

        // Add axis titles
        zoomG.append("text")
            .attr("class", "axis-label")
            .attr("x", 10)
            .attr("y", labelHeight / 2)
            .attr("font-size", "11px")
            .attr("font-weight", "bold")
            .text("Source ↓");

        zoomG.append("text")
            .attr("class", "axis-label")
            .attr("x", labelWidth + matrixSize / 2)
            .attr("y", 15)
            .attr("text-anchor", "middle")
            .attr("font-size", "11px")
            .attr("font-weight", "bold")
            .text("Target →");

        // Add diagonal line indicator (self-links would be here)
        zoomG.append("line")
            .attr("x1", labelWidth)
            .attr("y1", labelHeight)
            .attr("x2", labelWidth + sites.length * cellSize)
            .attr("y2", labelHeight + sites.length * cellSize)
            .attr("stroke", "#4b5563")
            .attr("stroke-width", 1)
            .attr("stroke-dasharray", "3,3");
    </script>
</body>
</html>"""
    
    output_file = os.path.join(scraped_data_dir, "adjacency_matrix.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\nAdjacency Matrix created at {output_file}")
    return output_file


def main():
    scraped_data_dir = "../scraped_data"
    
    if not os.path.exists(scraped_data_dir):
        scraped_data_dir = "scraped_data"
        if not os.path.exists(scraped_data_dir):
            print("Error: scraped_data directory not found")
            return
    
    generate_adjacency_matrix(scraped_data_dir)


if __name__ == "__main__":
    main()
