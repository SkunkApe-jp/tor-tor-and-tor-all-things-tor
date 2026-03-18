#!/usr/bin/env python3
"""
Onion Network Radar Profiler

Calculates metrics for site categories and generates a Radar (Spider) chart 
to compare the characteristics of different communities.
"""

import os
import json
import re
from collections import defaultdict

def get_category(title):
    title = title.lower()
    mapping = {
        "Marketplace": ["market", "shop", "store", "vendor", "buy", "sell", "escrow", "carding"],
        "Directory/Wiki": ["wiki", "links", "directory", "index", "list", "hidden", "library"],
        "Forum/Social": ["forum", "chat", "board", "social", "community", "chan", "talk"],
        "Financial": ["crypto", "wallet", "mixer", "bitcoin", "btc", "tumbler", "finance", "coin"],
        "Tech/Privacy": ["host", "node", "server", "git", "cloud", "mail", "dev", "tech", "vpn", "proxy"]
    }
    for cat, keywords in mapping.items():
        if any(kw in title for kw in keywords): return cat
    return "Other"

def generate_radar_data(scraped_data_dir):
    site_metrics = {}
    inbound_counts = defaultdict(int)
    
    onion_dirs = [d for d in os.listdir(scraped_data_dir) 
                  if os.path.isdir(os.path.join(scraped_data_dir, d)) and len(d) >= 16]

    print(f"Analyzing {len(onion_dirs)} sites for fingerprints...")

    # Pass 1: Build popularity map (Inbound Links)
    for onion in onion_dirs:
        urls_path = os.path.join(scraped_data_dir, onion, "urls")
        if os.path.exists(urls_path):
            for f in os.listdir(urls_path):
                try:
                    with open(os.path.join(urls_path, f), 'r') as file:
                        found = re.findall(r'([a-z2-7]{16,56})\.onion', file.read())
                        for ref in set(found): inbound_counts[ref] += 1
                except: pass

    # Pass 2: Calculate specific metrics
    for onion in onion_dirs:
        path = os.path.join(scraped_data_dir, onion)
        
        # 1. Category
        title = ""
        title_file = os.path.join(path, "website_titles", f"{onion}.txt")
        if os.path.exists(title_file):
            with open(title_file, 'r') as f: title = f.read().strip()
        cat = get_category(title)

        # 2. Connectivity (Internal link files)
        conn = len(os.listdir(os.path.join(path, "urls"))) if os.path.exists(os.path.join(path, "urls")) else 0
        
        # 3. Discovery (New onions found)
        disc = 0
        disc_path = os.path.join(path, "discovered_links")
        if os.path.exists(disc_path):
            for f in os.listdir(disc_path):
                with open(os.path.join(disc_path, f), 'r') as file:
                    disc += len(re.findall(r'\.onion', file.read()))

        # 4. Visual richness (Screenshots)
        imgs = len(os.listdir(os.path.join(path, "images"))) if os.path.exists(os.path.join(path, "images")) else 0

        # 5. Content Density (HTML Size)
        size = 0
        html_path = os.path.join(path, "htmls")
        if os.path.exists(html_path):
            for f in os.listdir(html_path): size += os.path.getsize(os.path.join(html_path, f))

        site_metrics[onion] = {
            "cat": cat,
            "Connectivity": conn,
            "Discovery": disc,
            "Visuals": imgs,
            "Content": size / 1024, # KB
            "Reputation": inbound_counts[onion]
        }

    # Aggregate by category
    cat_averages = defaultdict(lambda: defaultdict(list))
    for m in site_metrics.values():
        for key in ["Connectivity", "Discovery", "Visuals", "Content", "Reputation"]:
            cat_averages[m["cat"]][key].append(m[key])

    final_data = []
    for cat, metrics in cat_averages.items():
        if cat == "Other" and len(metrics) > 10: continue # Optional: filter 'Other' if too noisy
        row = {"className": cat}
        axes = []
        for key, vals in metrics.items():
            avg = sum(vals) / len(vals)
            axes.append({"axis": key, "value": avg})
        row["axes"] = axes
        final_data.append(row)

    return final_data

def generate_radar_html(data, output_path):
    # Normalize data for the chart (0-100 scale)
    max_vals = defaultdict(float)
    for entry in data:
        for ax in entry['axes']:
            if ax['value'] > max_vals[ax['axis']]: max_vals[ax['axis']] = ax['value']
    
    for entry in data:
        for ax in entry['axes']:
            if max_vals[ax['axis']] > 0:
                ax['value'] = (ax['value'] / max_vals[ax['axis']]) * 100

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Network Community Profiles</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ background: #0f0f12; color: #fff; font-family: sans-serif; display: flex; flex-direction: column; align-items: center; }}
        .axis line {{ stroke: #444; }}
        .axis text {{ fill: #aaa; font-size: 12px; }}
        .area {{ fill-opacity: 0.3; stroke-width: 3px; }}
        .area:hover {{ fill-opacity: 0.7; }}
        #legend {{ display: flex; gap: 20px; margin-top: 20px; flex-wrap: wrap; justify-content: center; }}
        .legend-item {{ display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; }}
        .dot {{ width: 12px; height: 12px; border-radius: 50%; }}
        #title {{ margin-top: 40px; text-align: center; }}
    </style>
</head>
<body>
    <div id="title">
        <h1>Community Fingerprints</h1>
        <p style="opacity:0.5">Comparing site categories across network metrics</p>
    </div>
    <div id="chart"></div>
    <div id="legend"></div>

    <script>
        const data = {json.dumps(data)};
        const width = 500, height = 500;
        const radius = Math.min(width, height) / 2 - 50;
        const colors = d3.scaleOrdinal(d3.schemeCategory10);

        const svg = d3.select("#chart").append("svg")
            .attr("width", width).attr("height", height)
            .append("g").attr("transform", `translate(${{width/2}}, ${{height/2}})`);

        const axes = data[0].axes.map(d => d.axis);
        const angleSlice = (Math.PI * 2) / axes.length;

        // Draw grid
        const levels = 5;
        for(let j=0; j<levels; j++) {{
            const r = (radius / levels) * (j + 1);
            svg.selectAll(".grid")
                .data([1]).enter()
                .append("circle")
                .attr("r", r).attr("fill", "none").attr("stroke", "#222");
        }}

        // Draw Axes
        const axisWrapper = svg.selectAll(".axis").data(axes).enter().append("g").attr("class", "axis");
        axisWrapper.append("line")
            .attr("x1", 0).attr("y1", 0)
            .attr("x2", (d, i) => radius * Math.cos(angleSlice * i - Math.PI/2))
            .attr("y2", (d, i) => radius * Math.sin(angleSlice * i - Math.PI/2));

        axisWrapper.append("text")
            .attr("text-anchor", "middle").attr("dy", "0.35em")
            .attr("x", (d, i) => (radius + 25) * Math.cos(angleSlice * i - Math.PI/2))
            .attr("y", (d, i) => (radius + 25) * Math.sin(angleSlice * i - Math.PI/2))
            .text(d => d);

        // Draw Areas
        const rScale = d3.scaleLinear().domain([0, 100]).range([0, radius]);
        const radarLine = d3.lineRadial()
            .radius(d => rScale(d.value))
            .angle((d, i) => i * angleSlice)
            .curve(d3.curveLinearClosed);

        data.forEach((d, i) => {{
            svg.append("path")
                .attr("class", "area")
                .attr("d", radarLine(d.axes))
                .style("fill", colors(i)).style("stroke", colors(i))
                .on("mouseover", function() {{
                    d3.selectAll(".area").style("opacity", 0.1);
                    d3.select(this).style("opacity", 1);
                }})
                .on("mouseout", () => d3.selectAll(".area").style("opacity", 1));

            // Legend
            const item = d3.select("#legend").append("div").attr("class", "legend-item");
            item.append("div").attr("class", "dot").style("background", colors(i));
            item.append("span").text(d.className);
        }});
    </script>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    # Use absolute path relative to script location
    from pathlib import Path
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()
    output_path = script_dir / "../scraped_data/community_radar_profiles.html"
    
    data = generate_radar_data(str(scraped_data_path))
    generate_radar_html(data, str(output_path))
    print(f"Radar profiling complete. Output: {output_path}")
