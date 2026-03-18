#!/usr/bin/env python3
"""
Community Hub Visualization Generator

Groups onion sites into "neighborhoods" based on keywords found in titles.
Uses clustered force layouts to keep similar sites together.
"""

import os
import json
import re
from pathlib import Path

def get_category(title):
    """Assign a category based on the title text."""
    title = title.lower()
    categories = {
        "Marketplace": ["market", "shop", "store", "vendor", "darknet", "buy", "sell", "escrow"],
        "Directory/Wiki": ["wiki", "links", "directory", "index", "list", "hidden", "library"],
        "Forum/Social": ["forum", "chat", "board", "social", "community", "chan", "talk"],
        "Financial/Crypto": ["crypto", "wallet", "mixer", "bitcoin", "btc", "tumbler", "finance", "coin"],
        "Hosting/Tech": ["host", "node", "server", "git", "cloud", "mail", "dev", "tech"],
        "Media/Leads": ["leak", "news", "press", "media", "radio", "gallery", "archive"]
    }
    
    for cat, keywords in categories.items():
        if any(kw in title for kw in keywords):
            return cat
    return "Others/General"

def extract_title(onion_addr, scraped_data_dir):
    """Attempt to find the title from website_titles or htmls folder."""
    # 1. Check website_titles folder
    title_path = os.path.join(scraped_data_dir, onion_addr, "website_titles", f"{onion_addr}.txt")
    if os.path.exists(title_path):
        try:
            with open(title_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except: pass

    # 2. Fallback to htmls folder
    html_path = os.path.join(scraped_data_dir, onion_addr, "htmls", f"{onion_addr}.html")
    if os.path.exists(html_path):
        try:
            with open(html_path, 'r', encoding='utf-8') as f:
                content = f.read()
                match = re.search(r'<title[^>]*>(.*?)</title>', content, re.I | re.S)
                if match: return ' '.join(match.group(1).strip().split())
        except: pass

    return f"{onion_addr}.onion"

def generate_community_visualization(scraped_data_dir):
    onion_dirs = [d for d in os.listdir(scraped_data_dir) 
                  if os.path.isdir(os.path.join(scraped_data_dir, d)) and len(d) >= 16]
    
    nodes = []
    links = []
    addr_to_idx = {}
    
    # Category definition for the legend
    cat_list = ["Marketplace", "Directory/Wiki", "Forum/Social", "Financial/Crypto", "Hosting/Tech", "Media/Leads", "Others/General"]
    cat_to_id = {name: i for i, name in enumerate(cat_list)}

    print(f"Aggregating data for {len(onion_dirs)} sites...")

    for onion_addr in onion_dirs:
        title = extract_title(onion_addr, scraped_data_dir)
        category = get_category(title)
        
        # Check for image
        img_path = ""
        for name in ["index.png", f"{onion_addr}.png"]:
            if os.path.exists(os.path.join(scraped_data_dir, onion_addr, "images", name)):
                img_path = f"{onion_addr}/images/{name}"
                break

        addr_to_idx[onion_addr] = len(nodes)
        nodes.append({
            "id": onion_addr,
            "title": title,
            "category": category,
            "group": cat_to_id[category],
            "image": img_path
        })

    # Build links
    for onion_addr in onion_dirs:
        urls_file = os.path.join(scraped_data_dir, onion_addr, "urls", f"{onion_addr}_links.txt")
        if os.path.exists(urls_file):
            try:
                with open(urls_file, 'r') as f:
                    content = f.read()
                    found_onions = set(re.findall(r'([a-z2-7]{16,56})\.onion', content))
                    for found in found_onions:
                        if found in addr_to_idx and found != onion_addr:
                            links.append({
                                "source": addr_to_idx[onion_addr],
                                "target": addr_to_idx[found]
                            })
            except: pass

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Onion Community Hub Map</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; background: #0a0a0c; font-family: 'Segoe UI', sans-serif; color: white; }}
        #tooltip {{ 
            position: absolute; padding: 15px; background: rgba(20,20,25,0.95); 
            border: 1px solid #444; border-radius: 8px; opacity: 0; pointer-events: none; 
            z-index: 100; box-shadow: 0 10px 30px rgba(0,0,0,0.5); width: 250px;
        }}
        .node-circle {{ stroke: #fff; stroke-width: 1.5px; transition: stroke-width 0.2s; }}
        .link {{ stroke: #444; stroke-opacity: 0.2; stroke-width: 1px; fill: none; }}
        #legend {{ 
            position: absolute; bottom: 30px; left: 30px; 
            background: rgba(0,0,0,0.7); padding: 20px; border-radius: 12px; border: 1px solid #333;
        }}
        .legend-item {{ display: flex; align-items: center; margin-bottom: 8px; font-size: 13px; }}
        .legend-color {{ width: 14px; height: 14px; border-radius: 50%; margin-right: 10px; }}
        #header {{ position: absolute; top: 30px; left: 30px; pointer-events: none; }}
        h1 {{ margin: 0; font-size: 24px; letter-spacing: 1px; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Onion Community Hub</h1>
        <div style="opacity: 0.6">Clustered by Site Category</div>
    </div>
    <div id="tooltip"></div>
    <div id="legend">
        <strong style="display:block; margin-bottom: 10px;">Communities</strong>
    </div>

    <script>
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};
        const categories = {json.dumps(cat_list)};
        const colors = d3.schemeTableau10;

        const width = window.innerWidth, height = window.innerHeight;
        
        // Setup legend
        const legend = d3.select("#legend");
        categories.forEach((cat, i) => {{
            const div = legend.append("div").attr("class", "legend-item");
            div.append("div").attr("class", "legend-color").style("background", colors[i]);
            div.append("span").text(cat);
        }});

        const svg = d3.select("body").append("svg").attr("width", width).attr("height", height);
        const g = svg.append("g");
        const zoom = d3.zoom().scaleExtent([0.1, 8]).on("zoom", (e) => g.attr("transform", e.transform));
        svg.call(zoom);

        // Community Centers (Circular Arrangement)
        const centers = categories.map((_, i) => {{
            const angle = (i / categories.length) * 2 * Math.PI;
            const radius = Math.min(width, height) * 0.35;
            return {{
                x: width / 2 + Math.cos(angle) * radius,
                y: height / 2 + Math.sin(angle) * radius
            }};
        }});

        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id((d, i) => i).distance(50).strength(0.1))
            .force("charge", d3.forceManyBody().strength(-120))
            .force("x", d3.forceX(d => centers[d.group].x).strength(0.15))
            .force("y", d3.forceY(d => centers[d.group].y).strength(0.15))
            .force("collide", d3.forceCollide().radius(d => d.image ? 45 : 15))
            .alphaDecay(0.02);

        const link = g.append("g").selectAll("line").data(links).join("line").attr("class", "link");

        const node = g.append("g").selectAll("g").data(nodes).join("g")
            .attr("cursor", "pointer")
            .call(d3.drag().on("start", dragstarted).on("drag", dragged).on("end", dragended));

        // Background glows
        node.append("circle")
            .attr("r", d => d.image ? 40 : 10)
            .attr("fill", d => colors[d.group])
            .attr("fill-opacity", 0.15);

        // Actual circles/images
        node.filter(d => d.image).append("image")
            .attr("xlink:href", d => d.image)
            .attr("x", -35).attr("y", -35).attr("width", 70).attr("height", 70)
            .attr("clip-path", "circle(35px at 35px 35px)");

        node.filter(d => !d.image).append("circle")
            .attr("r", 8)
            .attr("fill", d => colors[d.group])
            .attr("stroke", "#fff").attr("stroke-width", 1);

        node.on("mouseover", (e, d) => {{
            d3.select("#tooltip").style("opacity", 1)
                .html(`<div style="color:${{colors[d.group]}}; font-weight:bold; margin-bottom:5px;">${{d.category}}</div>
                       <div style="font-size:16px;">${{d.title}}</div>
                       <div style="font-size:11px; opacity:0.5; margin-top:5px; word-break:break-all;">${{d.id}}.onion</div>`)
                .style("left", (e.pageX + 20) + "px")
                .style("top", (e.pageY - 20) + "px");
        }}).on("mouseout", () => d3.select("#tooltip").style("opacity", 0));

        simulation.on("tick", () => {{
            link.attr("x1", d => d.source.x).attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
            node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }});

        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.2).restart();
            d.fx = d.x; d.fy = d.y;
        }}
        function dragged(event, d) {{ d.fx = event.x; d.fy = event.y; }}
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
        }}
    </script>
</body>
</html>"""

    output = os.path.join(scraped_data_dir, "community_hub_map.html")
    with open(output, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Community map created at {output}")


if __name__ == "__main__":
    # Use absolute path relative to script location
    from pathlib import Path
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()
    generate_community_visualization(str(scraped_data_path))
