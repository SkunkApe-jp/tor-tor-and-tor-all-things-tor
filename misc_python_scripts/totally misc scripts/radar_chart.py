#!/usr/bin/env python3
"""
Radar Chart - Site Comparison

Compare top sites across multiple metrics using a radar/spider chart.
Shows the top 8 sites by total connections.
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


def generate_radar_chart(scraped_data_dir):
    """Generate radar chart comparison for top sites."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to analyze")

    # Collect metrics for each site
    site_metrics = []

    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)

        # Get title
        html_file = os.path.join(site_dir, 'htmls', f"{onion_addr}.html")
        title = extract_title_from_html(html_file) or onion_addr[:20]

        # Count outbound links
        outbound = 0
        for d in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, d)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        with open(os.path.join(path, f), 'r') as lf:
                            outbound += sum(1 for line in lf if '.onion' in line)

        # Count inbound links
        inbound = 0
        for other_addr in onion_sites:
            if other_addr != onion_addr:
                other_dir = os.path.join(scraped_data_dir, other_addr)
                for d in ['urls', 'discovered_links']:
                    path = os.path.join(other_dir, d)
                    if os.path.exists(path):
                        for f in os.listdir(path):
                            if f.endswith('_links.txt'):
                                with open(os.path.join(path, f), 'r') as lf:
                                    if any(onion_addr in line for line in lf):
                                        inbound += 1

        # Check for image
        has_image = 0
        for img_name in ["index.png", f"{onion_addr}.png"]:
            if os.path.exists(os.path.join(site_dir, 'images', img_name)):
                has_image = 1
                break

        # Count titles discovered
        titles_count = 0
        titles_dir = os.path.join(site_dir, 'discovered_links')
        if os.path.exists(titles_dir):
            for f in os.listdir(titles_dir):
                if f.endswith('_titles.txt'):
                    with open(os.path.join(titles_dir, f), 'r') as tf:
                        titles_count += sum(1 for line in tf if '->' in line)

        site_metrics.append({
            'addr': onion_addr,
            'title': title,
            'outbound': outbound,
            'inbound': inbound,
            'has_image': has_image,
            'titles': titles_count,
            'total': outbound + inbound
        })

    # Sort by total connections and take top 8
    site_metrics.sort(key=lambda x: -x['total'])
    top_sites = site_metrics[:8]

    # Normalize metrics to 0-1 scale
    max_outbound = max(s['outbound'] for s in top_sites) or 1
    max_inbound = max(s['inbound'] for s in top_sites) or 1
    max_titles = max(s['titles'] for s in top_sites) or 1

    for site in top_sites:
        site['norm_outbound'] = site['outbound'] / max_outbound
        site['norm_inbound'] = site['inbound'] / max_inbound
        site['norm_titles'] = site['titles'] / max_titles
        site['norm_image'] = site['has_image']
        site['norm_discovery'] = (site['norm_outbound'] + site['norm_inbound'] + site['norm_titles']) / 3

    print(f"\nRadar Chart Data:")
    print(f"  Comparing {len(top_sites)} top sites")

    # D3 color scheme
    colors = ['#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e91e63', '#00bcd4']

    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Radar Chart - Top Sites Comparison</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; background: #0a0a0f; font-family: 'Segoe UI', sans-serif; }}
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
            border-radius: 8px; border: 1px solid #333; z-index: 10;
            color: #aaa; font-size: 12px; line-height: 1.8;
        }}
        #legend strong {{ color: #fff; }}
        #site-legend {{
            position: fixed; top: 80px; right: 20px;
            background: rgba(30,30,40,0.9); padding: 12px;
            border-radius: 8px; border: 1px solid #333; z-index: 10;
            color: #aaa; font-size: 11px; max-height: 60vh; overflow-y: auto;
        }}
        .legend-item {{ display: flex; align-items: center; margin: 8px 0; }}
        .legend-color {{ width: 16px; height: 16px; border-radius: 50%; margin-right: 10px; border: 2px solid #fff; }}
        .legend-text {{ max-width: 200px; }}
        .legend-title {{ color: #fff; font-size: 11px; font-weight: bold; }}
        .legend-addr {{ color: #666; font-size: 9px; word-break: break-all; }}
        #controls {{ position: absolute; top: 20px; right: 20px; z-index: 10; display: flex; flex-direction: column; gap: 8px; }}
        .btn {{ background: rgba(30,30,40,0.9); border: 1px solid #444; padding: 10px; cursor: pointer; border-radius: 6px; color: #fff; }}
        .btn:hover {{ background: rgba(50,50,60,0.9); }}
        svg {{ overflow: visible; }}
        .axis {{ stroke: #30363d; }}
        .axis-label {{ fill: #8b949e; font-size: 11px; font-weight: bold; }}
        .radar-area {{ fill-opacity: 0.2; stroke-width: 2; transition: all 0.2s; }}
        .radar-area:hover {{ fill-opacity: 0.4; stroke-width: 3; }}
        .grid-circle {{ fill: none; stroke: #222; stroke-width: 1; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Radar Chart - Top Sites Comparison</h1>
        <div id="stats">{len(top_sites)} sites compared across 5 metrics</div>
    </div>
    <div id="controls">
        <button class="btn" onclick="zoomIn()">+</button>
        <button class="btn" onclick="zoomOut()">−</button>
        <button class="btn" onclick="resetView()">↺</button>
    </div>
    <div id="legend">
        <strong>Metrics:</strong><br/>
        • Outbound = Links to other sites<br/>
        • Inbound = Links from other sites<br/>
        • Titles = Discovered link titles<br/>
        • Screenshot = Has screenshot (0/1)<br/>
        • Discovery = Combined score
    </div>
    <div id="site-legend">
        <strong style="color: #fff;">Sites (colored):</strong>
        {''.join(f"""
        <div class="legend-item">
            <div class="legend-color" style="background: {colors[i % len(colors)]}"></div>
            <div class="legend-text">
                <div class="legend-title">{site['title']}</div>
                <div class="legend-addr">{site['addr'][:30]}...</div>
            </div>
        </div>
        """ for i, site in enumerate(top_sites))}
    </div>

    <script>
        const sites = {json.dumps(top_sites)};
        const metrics = ['norm_outbound', 'norm_inbound', 'norm_titles', 'norm_image', 'norm_discovery'];
        const metricLabels = ['Outbound', 'Inbound', 'Titles', 'Screenshot', 'Discovery'];
        const colors = {json.dumps(colors)};

        const width = window.innerWidth;
        const height = window.innerHeight;
        const radius = Math.min(width, height) * 0.35;
        const angleSlice = (Math.PI * 2) / metrics.length;

        const svg = d3.select("body").append("svg")
            .attr("width", "100%")
            .attr("height", "100vh")
            .attr("viewBox", [-width/2, -height/2, width, height]);

        const rootGroup = svg.append("g");

        // Zoom
        const zoom = d3.zoom()
            .scaleExtent([0.3, 4])
            .on("zoom", (e) => rootGroup.attr("transform", e.transform));
        svg.call(zoom);

        function zoomIn() {{ svg.transition().duration(400).call(zoom.scaleBy, 1.5, [width/2, height/2]); }}
        function zoomOut() {{ svg.transition().duration(400).call(zoom.scaleBy, 0.6, [width/2, height/2]); }}
        function resetView() {{ svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity); }}

        // Draw circular grid
        const levels = 4;
        for (let i = 1; i <= levels; i++) {{
            const r = radius * i / levels;
            rootGroup.append("circle")
                .attr("class", "grid-circle")
                .attr("r", r);
        }}

        // Draw axis lines
        for (let i = 0; i < metrics.length; i++) {{
            const angle = angleSlice * i - Math.PI / 2;
            const x = Math.cos(angle) * radius;
            const y = Math.sin(angle) * radius;
            
            rootGroup.append("line")
                .attr("class", "axis")
                .attr("x1", 0).attr("y1", 0)
                .attr("x2", x).attr("y2", y);
            
            // Axis labels
            const labelX = Math.cos(angle) * (radius + 40);
            const labelY = Math.sin(angle) * (radius + 40);
            
            rootGroup.append("text")
                .attr("class", "axis-label")
                .attr("x", labelX)
                .attr("y", labelY)
                .attr("text-anchor", "middle")
                .attr("dominant-baseline", "middle")
                .text(metricLabels[i]);
        }}

        // Draw radar areas for each site
        const radarLine = d3.lineRadial()
            .radius(d => d.value)
            .angle((d, i) => i * angleSlice)
            .curve(d3.curveLinearClosed);

        sites.forEach((site, idx) => {{
            const data = metrics.map(m => ({{ value: site[m] * radius }}));
            
            rootGroup.append("path")
                .attr("class", "radar-area")
                .attr("d", radarLine(data))
                .attr("fill", colors[idx])
                .attr("stroke", colors[idx])
                .on("mouseover", () => {{
                    d3.selectAll(".radar-area").attr("fill-opacity", 0.05);
                    d3.selectAll(".radar-area")[idx].attr("fill-opacity", 0.3);
                    d3.select("#site-legend .legend-item:nth-child(" + (idx + 2) + ")").style("opacity", 1);
                }})
                .on("mouseout", () => {{
                    d3.selectAll(".radar-area").attr("fill-opacity", 0.2);
                    d3.select("#site-legend .legend-item:nth-child(" + (idx + 2) + ")").style("opacity", 1);
                }});
        }});

        // Draw points at each metric
        sites.forEach((site, idx) => {{
            metrics.forEach((m, mi) => {{
                const angle = angleSlice * mi - Math.PI / 2;
                const r = site[m] * radius;
                const x = Math.cos(angle) * r;
                const y = Math.sin(angle) * r;
                
                rootGroup.append("circle")
                    .attr("cx", x)
                    .attr("cy", y)
                    .attr("r", 4)
                    .attr("fill", colors[idx])
                    .attr("stroke", "#fff")
                    .attr("stroke-width", 1);
            }});
        }});
    </script>
</body>
</html>"""

    output_file = os.path.join(scraped_data_dir, "radar_chart.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"\nRadar Chart created at {output_file}")
    return output_file


def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()
    
    if not os.path.exists(scraped_data_path):
        print(f"Error: scraped_data directory not found at {scraped_data_path}")
        return

    generate_radar_chart(str(scraped_data_path))


if __name__ == "__main__":
    main()
