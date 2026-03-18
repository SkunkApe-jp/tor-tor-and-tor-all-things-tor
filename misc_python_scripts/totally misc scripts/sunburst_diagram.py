#!/usr/bin/env python3
"""
Sunburst Diagram - Site to Sub-page Hierarchy

Shows the hierarchical structure of each site's scraped pages.
Inner ring = sites, Outer rings = sub-pages.
"""

import os
import json
import re
from pathlib import Path

def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    if not os.path.exists(scraped_data_dir):
        return []
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
                    return ' '.join(title_match.group(1).strip().split())[:40]
        except Exception:
            pass
    return None

def generate_sunburst_diagram(scraped_data_dir):
    """Generate a sunburst diagram showing site hierarchies."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to analyze")
    
    root = {"name": "All Sites", "type": "root", "children": []}
    
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        images_dir = os.path.join(site_dir, 'images')
        htmls_dir = os.path.join(site_dir, 'htmls')
        
        site_node = {
            "name": onion_addr[:16] + "...",
            "addr": onion_addr,
            "type": "site",
            "children": []
        }
        
        # Track pages to avoid duplicates
        pages_added = set()

        # Check for root/home page
        root_html = os.path.join(htmls_dir, f"{onion_addr}.html")
        if os.path.exists(root_html):
            title = extract_title_from_html(root_html) or "Home"
            has_image = os.path.exists(os.path.join(images_dir, f"{onion_addr}.png"))
            
            site_node["children"].append({
                "name": title,
                "type": "page",
                "path": "/",
                "has_image": has_image,
                "url": f"http://{onion_addr}.onion",
                "value": 1  # Base value for D3 layout
            })
            pages_added.add(f"{onion_addr}.html")
        
        # Find other sub-pages in htmls folder
        if os.path.exists(htmls_dir):
            for f in os.listdir(htmls_dir):
                if f.endswith('.html') and f not in pages_added:
                    html_path = os.path.join(htmls_dir, f)
                    title = extract_title_from_html(html_path) or f.replace('.html', '')
                    
                    base_name = f.replace('.html', '')
                    has_image = os.path.exists(os.path.join(images_dir, f"{base_name}.png"))
                    
                    site_node["children"].append({
                        "name": title[:30],
                        "type": "page",
                        "path": f"/{base_name}",
                        "has_image": has_image,
                        "url": f"http://{onion_addr}.onion/{base_name}",
                        "value": 1
                    })
        
        if site_node["children"]:
            root["children"].append(site_node)
    
    total_sites = len(root['children'])
    total_pages = sum(len(s['children']) for s in root['children'])
    
    # HTML generation with fixed D3 logic
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Site Hierarchy Sunburst</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; background: #0f0f12; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica; color: white; overflow: hidden; }}
        #header {{ position: absolute; top: 20px; left: 20px; z-index: 10; pointer-events: none; }}
        #header h1 {{ margin: 0; font-size: 20px; font-weight: 300; letter-spacing: 1px; }}
        #stats {{ font-size: 12px; color: #888; margin-top: 5px; }}
        #tooltip {{
            position: fixed; padding: 10px; background: rgba(20, 20, 25, 0.95);
            border: 1px solid #444; border-radius: 4px; pointer-events: none;
            opacity: 0; z-index: 100; font-size: 12px; transition: opacity 0.1s;
        }}
        .arc {{ cursor: pointer; stroke: #0f0f12; stroke-width: 1px; }}
        .arc:hover {{ opacity: 0.8 !important; }}
        .label {{ pointer-events: none; font-size: 10px; fill: white; text-shadow: 0 1px 2px rgba(0,0,0,0.8); }}
        #controls {{ position: absolute; bottom: 20px; right: 20px; z-index: 10; }}
        .btn {{ 
            background: #222; border: 1px solid #444; color: #ccc; 
            padding: 8px 15px; cursor: pointer; border-radius: 4px; font-size: 12px;
        }}
        .btn:hover {{ background: #333; color: white; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Site Hierarchy Sunburst</h1>
        <div id="stats">{total_sites} Sites • {total_pages} Pages</div>
    </div>
    <div id="controls">
        <button class="btn" onclick="resetZoom()">Reset View</button>
    </div>
    <div id="tooltip"></div>

    <script>
        const data = {json.dumps(root)};
        const width = window.innerWidth;
        const height = window.innerHeight;
        const radius = Math.min(width, height) / 6;

        const colorScale = d3.scaleOrdinal(d3.quantize(d3.interpolateRainbow, data.children.length + 1));

        // Create the hierarchy and calculate values
        const root = d3.hierarchy(data)
            .sum(d => d.value || 0)
            .sort((a, b) => b.value - a.value);

        const partition = d3.partition().size([2 * Math.PI, root.height + 1]);
        partition(root);

        root.each(d => d.current = d);

        const arc = d3.arc()
            .startAngle(d => d.x0)
            .endAngle(d => d.x1)
            .padAngle(d => Math.min((d.x1 - d.x0) / 2, 0.005))
            .padRadius(radius * 1.5)
            .innerRadius(d => d.y0 * radius)
            .outerRadius(d => Math.max(d.y0 * radius, d.y1 * radius - 1));

        const svg = d3.select("body").append("svg")
            .attr("viewBox", [-width / 2, -height / 2, width, height])
            .style("font", "10px sans-serif");

        const g = svg.append("g");

        const path = g.append("g")
            .selectAll("path")
            .data(root.descendants().slice(1))
            .join("path")
            .attr("class", "arc")
            .attr("fill", d => {{
                while (d.depth > 1) d = d.parent;
                return colorScale(d.data.name);
            }})
            .attr("fill-opacity", d => arcVisible(d.current) ? (d.children ? 0.7 : 0.4) : 0)
            .attr("pointer-events", d => arcVisible(d.current) ? "auto" : "none")
            .attr("d", d => arc(d.current))
            .on("mouseover", (e, d) => {{
                d3.select("#tooltip")
                    .style("opacity", 1)
                    .html(`
                        <div style="font-weight:bold">${{d.data.name}}</div>
                        <div style="color:#aaa;font-size:10px">${{d.data.addr || d.data.path || ''}}</div>
                        ${{d.data.type === 'site' ? '<div style="margin-top:5px;color:#4ade80">'+d.children.length+' pages</div>' : ''}}
                        ${{d.data.has_image ? '<div style="color:#60a5fa">📸 Screenshot available</div>' : ''}}
                    `)
                    .style("left", (e.pageX + 15) + "px")
                    .style("top", (e.pageY - 15) + "px");
            }})
            .on("mousemove", (e) => {{
                d3.select("#tooltip")
                    .style("left", (e.pageX + 15) + "px")
                    .style("top", (e.pageY - 15) + "px");
            }})
            .on("mouseout", () => d3.select("#tooltip").style("opacity", 0))
            .on("click", clicked);

        const label = g.append("g")
            .attr("pointer-events", "none")
            .attr("text-anchor", "middle")
            .style("user-select", "none")
            .selectAll("text")
            .data(root.descendants().slice(1))
            .join("text")
            .attr("class", "label")
            .attr("dy", "0.35em")
            .attr("fill-opacity", d => +labelVisible(d.current))
            .attr("transform", d => labelTransform(d.current))
            .text(d => d.data.name);

        const parent = g.append("circle")
            .datum(root)
            .attr("r", radius)
            .attr("fill", "none")
            .attr("pointer-events", "all")
            .on("click", clicked);

        function clicked(event, p) {{
            parent.datum(p.parent || root);

            root.each(d => d.target = {{
                x0: Math.max(0, Math.min(1, (d.x0 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
                x1: Math.max(0, Math.min(1, (d.x1 - p.x0) / (p.x1 - p.x0))) * 2 * Math.PI,
                y0: Math.max(0, d.y0 - p.depth),
                y1: Math.max(0, d.y1 - p.depth)
            }});

            const t = g.transition().duration(750);

            path.transition(t)
                .tween("data", d => {{
                    const i = d3.interpolate(d.current, d.target);
                    return t => d.current = i(t);
                }})
                .filter(function(d) {{
                    return +this.getAttribute("fill-opacity") || arcVisible(d.target);
                }})
                .attr("fill-opacity", d => arcVisible(d.target) ? (d.children ? 0.7 : 0.4) : 0)
                .attr("pointer-events", d => arcVisible(d.target) ? "auto" : "none")
                .attrTween("d", d => () => arc(d.current));

            label.filter(function(d) {{
                return +this.getAttribute("fill-opacity") || labelVisible(d.target);
            }}).transition(t)
                .attr("fill-opacity", d => +labelVisible(d.target))
                .attrTween("transform", d => () => labelTransform(d.current));
        }}

        function resetZoom() {{
            clicked(null, root);
        }}

        function arcVisible(d) {{
            return d.y1 <= 3 && d.y0 >= 1 && d.x1 > d.x0;
        }}

        function labelVisible(d) {{
            return d.y1 <= 3 && d.y0 >= 1 && (d.y1 - d.y0) * (d.x1 - d.x0) > 0.03;
        }}

        function labelTransform(d) {{
            const x = (d.x0 + d.x1) / 2 * 180 / Math.PI;
            const y = (d.y0 + d.y1) / 2 * radius;
            return `rotate(${{x - 90}}) translate(${{y}},0) rotate(${{x < 180 ? 0 : 180}})`;
        }}
    </script>
</body>
</html>"""
    
    output_path = os.path.join(scraped_data_dir, "sunburst_diagram.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"Success! Diagram generated at: {output_path}")
    return output_path

if __name__ == "__main__":
    # Path relative to script location
    target_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scraped_data")
    if not os.path.exists(target_dir):
        # Fallback to local
        target_dir = "scraped_data"
        
    generate_sunburst_diagram(target_dir)
