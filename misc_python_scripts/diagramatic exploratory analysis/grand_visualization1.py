#!/usr/bin/env python3
"""
Grand Visualization Generator

Creates a comprehensive visualization showing relationships between different onion sites.
This visualization connects sites that link to each other, showing the network structure
across all scraped onion sites.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path

def read_links_file(links_file_path):
    """Read links from the scraped links file."""
    links = []
    if os.path.exists(links_file_path):
        with open(links_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '.onion' in line:
                    links.append(line)
    return links


def extract_onion_addresses_from_file(file_path):
    """Extract all unique onion addresses from a links file."""
    onion_addresses = set()  # Use set to avoid duplicates
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract all URLs from the file
            url_matches = re.findall(r'https?://[^\s\'\"<>]+', content)
            for match in url_matches:
                try:
                    parsed = urllib.parse.urlparse(match)
                    if parsed.scheme and parsed.netloc and '.onion' in parsed.netloc:
                        # Extract just the onion address part
                        onion_match = re.search(r'([a-z2-7]{54,}\.onion)', match)
                        if onion_match:
                            onion_addresses.add(onion_match.group(1))  # Store just the onion address
                except:
                    continue
    return list(onion_addresses)

def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and len(item) >= 50:  # Minimum length for onion addresses
            # Verify it looks like an onion address (Base32)
            if re.match(r'^[a-z2-7]{50,}$', item):
                onion_dirs.append(item)
    return onion_dirs

def extract_title_from_html(html_file_path):
    """Extract title from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for title tag in the HTML
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    # Remove extra whitespace and newlines
                    title = ' '.join(title.split())
                    return title
        except Exception as e:
            print(f"Error reading {html_file_path}: {str(e)}")
    return None

def get_image_dimensions(image_path):
    """Get the dimensions of an image file."""
    if os.path.exists(image_path):
        try:
            from PIL import Image
            with Image.open(image_path) as img:
                return img.size  # (width, height)
        except Exception:
            pass
    return None


def find_screenshot_path(full_url, scraped_data_dir):
    """Find the appropriate screenshot for a URL based on its path structure."""
    import urllib.parse
    parsed = urllib.parse.urlparse(full_url)
    
    # Extract onion address part
    host = parsed.netloc
    if not host:
        # try to find onion in path
        onion_match = re.search(r'([a-z0-9-]{50,})\.onion', full_url)
        if onion_match:
            host = onion_match.group(0)
    
    if not host or '.onion' not in host:
        return "", None

    onion_address = host.replace('.onion', '')
    url_path = parsed.path

    # Base image directory
    image_dir = os.path.join(scraped_data_dir, onion_address, 'images')
    if not os.path.exists(image_dir):
        return "", None

    viz_dir = scraped_data_dir

    # 1. Check for specific {url_path}.png (highest priority)
    if url_path and url_path != "/":
        clean_path = url_path.strip('/')
        if clean_path:
            safe_name = clean_path.replace('/', '_').replace('.', '_')
            path_path = os.path.join(image_dir, f"{safe_name}.png")
            if os.path.exists(path_path):
                rel_path = os.path.relpath(path_path, viz_dir)
                return rel_path.replace('\\', '/'), None

    # 2. Check for index.png (root page screenshot) ONLY if looking at the root path
    if url_path == "" or url_path == "/":
        index_path = os.path.join(image_dir, "index.png")
        if os.path.exists(index_path):
            rel_path = os.path.relpath(index_path, viz_dir)
            return rel_path.replace('\\', '/'), None

    return "", None


def generate_grand_visualization(scraped_data_dir):
    """Generate a grand visualization showing cross-site relationships with sub-nodes."""

    # Get all onion sites
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to visualize")

    # Create nodes and links for the visualization
    nodes = []
    links = []

    # 1. Build a URL -> Title mapping from website_identity folder
    url_to_title = {}
    for onion_addr in onion_sites:
        identity_dir = os.path.join(scraped_data_dir, onion_addr, 'website_identity')
        if os.path.exists(identity_dir):
            for title_file in os.listdir(identity_dir):
                if title_file.endswith('_title.txt'):
                    try:
                        with open(os.path.join(identity_dir, title_file), 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            if '->' in content:
                                t_part, u_part = content.split('->', 1)
                                t_val = t_part.strip().strip('[]')
                                u_val = u_part.strip().rstrip('/')
                                url_to_title[u_val] = t_val
                                url_to_title[u_val.replace('http://', '').replace('https://', '')] = t_val
                    except: pass

    # Create nodes and links for the visualization
    nodes = []
    links = []

    # Create a mapping from URL to node index
    url_to_idx = {}

    # Process each onion site
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        
        # Get title for the root node
        root_url = f"http://{onion_addr}.onion"
        root_title = url_to_title.get(root_url.rstrip('/')) or url_to_title.get(onion_addr)
        if not root_title:
            root_html_file = os.path.join(site_dir, 'htmls', f"{onion_addr}.html")
            root_title = extract_title_from_html(root_html_file) or root_url

        # Read links
        outbound_links = []
        for d in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, d)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        outbound_links.extend(read_links_file(os.path.join(path, f)))

        # Add root node
        root_image_path, _ = find_screenshot_path(root_url, scraped_data_dir)
        if root_url not in url_to_idx:
            url_to_idx[root_url] = len(nodes)
            nodes.append({
                'id': root_url,
                'name': root_url,
                'title': root_title,
                'image': root_image_path,
                'group': 1
            })
        
        root_idx = url_to_idx[root_url]

        # Add outbound links as child nodes
        for link in set(outbound_links):
            link_title = url_to_title.get(link.rstrip('/'))
            if not link_title:
                # try to extract from HTML if it's another local onion
                onion_match = re.search(r'([a-z2-7]{50,})\.onion', link)
                if onion_match:
                    lo = onion_match.group(1)
                    html_f = os.path.join(scraped_data_dir, lo, 'htmls', f"{lo}.html")
                    link_title = extract_title_from_html(html_f)
            
            if not link_title: link_title = link

            image_path, _ = find_screenshot_path(link, scraped_data_dir)

            if link not in url_to_idx:
                url_to_idx[link] = len(nodes)
                nodes.append({
                    'id': link,
                    'name': link,
                    'title': link_title,
                    'image': image_path,
                    'group': 2
                })
            
            links.append({
                'source': root_idx,
                'target': url_to_idx[link],
                'value': 1
            })

    # Generate HTML with embedded JavaScript for D3 visualization
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Grand Onion Network Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            margin: 0;
            overflow: hidden;
            background-color: white;
            font-family: Arial, sans-serif;
        }}
        #tooltip {{
            position: absolute;
            text-align: left;
            padding: 10px;
            font-size: 14px;
            background: rgba(255, 255, 255, 0.95);
            color: black;
            border: 1px solid #ccc;
            border-radius: 4px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            max-width: 300px;
            z-index: 100;
        }}
        .node {{
            cursor: pointer;
        }}
        .link {{
            stroke: #999;
            stroke-opacity: 0.6;
        }}
        #title {{
            position: absolute;
            top: 10px;
            left: 10px;
            color: black;
            font-size: 16px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.8);
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
        }}
        #controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 10;
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        .control-btn {{
            background: rgba(255, 255, 255, 0.8);
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 8px 12px;
            cursor: pointer;
            font-size: 14px;
            color: black;
            text-align: center;
            min-width: 40px;
            user-select: none;
        }}
        .control-btn:hover {{
            background: rgba(240, 240, 240, 0.9);
        }}
    </style>
</head>
<body>
    <div id="title">Grand Onion Network Visualization ({len(nodes)} nodes, {len(links)} connections)</div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()">+</button>
        <button class="control-btn" onclick="zoomOut()">-</button>
        <button class="control-btn" onclick="resetView()">↺</button>
    </div>
    <div id="tooltip"></div>
    <script>
        // Hierarchical data structure
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};

        // Chart dimensions
        const width = window.innerWidth;
        const height = window.innerHeight;

        // Create the container SVG
        const svg = d3.select("body")
            .append("svg")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("style", "max-width: 100%; height: 100vh;");

        // Add zoom functionality with panning
        const zoom = d3.zoom()
            .scaleExtent([0.1, 8])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});
        svg.call(zoom);

        // Create zoom functions
        function zoomIn() {{
            svg.transition().duration(750).call(zoom.scaleBy, 1.5);
        }}

        function zoomOut() {{
            svg.transition().duration(750).call(zoom.scaleBy, 0.5);
        }}

        function resetView() {{
            svg.transition().duration(750).call(zoom.scaleTo, 1);
        }}

        // Create a group for zooming
        const g = svg.append("g");

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
            .attr("fill", "#666");

        // Create force simulation
        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id((d, i) => i).distance(120).strength(0.6))
            .force("charge", d3.forceManyBody().strength(-250))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(function(d) {{ return d.image && d.image !== "" ? 50 : 12; }}));

        // Append links
        const link = g.append("g")
            .attr("stroke", "#666")
            .attr("stroke-opacity", 0.7)
            .selectAll("line")
            .data(links)
            .join("line")
            .attr("class", "link")
            .attr("marker-end", "url(#arrowhead)");

        // Create tooltip
        const tooltip = d3.select("#tooltip");

        // Create groups for nodes
        const node = g.append("g")
            .selectAll("g")
            .data(nodes)
            .join("g")
            .attr("cursor", "pointer")  // Indicate clickable
            .on("click", function(event, d) {{
                // Open the screenshot in a new tab when clicked (if available)
                if (d.image && d.image !== "") {{
                    window.open(d.image, '_blank');
                }}
            }})
            .call(drag(simulation));

        // Add images for nodes that have screenshots
        node.filter(function(d) {{ return d.image && d.image !== ""; }})
            .append("image")
            .attr("xlink:href", function(d) {{ return d.image; }})
            .attr("x", -40)  // 10x larger when image is present
            .attr("y", -40)  // 10x larger when image is present
            .attr("width", 80)  // 10x larger when image is present
            .attr("height", 80)  // 10x larger when image is present
            .attr("clip-path", "circle()");

        // Add circles for nodes that don't have screenshots
        node.filter(function(d) {{ return !(d.image && d.image !== ""); }})
            .append("circle")
            .attr("r", function(d) {{ return d.group === 1 ? 8 : 4; }})  // Larger for root nodes
            .attr("fill", function(d) {{ return d.group === 1 ? "#000" : "#666"; }})  // Different colors for root vs child
            .attr("stroke", function(d) {{ return d.group === 1 ? "#000" : "#666"; }})
            .attr("stroke-width", 1.5);

        // Add labels to nodes
        const label = g.append("g")
            .selectAll("text")
            .data(nodes)
            .join("text")
            .text(function(d) {{ return d.group === 1 ? d.title.substring(0, 15) + (d.title.length > 15 ? "..." : "") : ""; }})
            .attr("font-size", "10px")
            .attr("dx", 10)
            .attr("dy", 4)
            .attr("fill", "#000");  // Black text for B&W theme

        // Add hover functionality
        node.on("mouseover", function(event, d) {{
            tooltip.transition().duration(200).style("opacity", .95);
            tooltip.html(`<div><strong style="word-break:break-all;">${{d.title}}</strong></div><div style="font-size:11px;color:#666;word-break:break-all;">${{d.id}}</div>${{d.image ? `<img src="${{d.image}}" style="max-width:200px;max-height:150px;margin-top:5px;border:1px solid #ddd;">` : ""}}`)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 28) + "px");
        }})
        .on("mouseout", function(d) {{
            tooltip.transition()
                .duration(500)
                .style("opacity", 0);
        }});

        // Update positions on each tick
        simulation.on("tick", function() {{
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

        // Drag functions
        function drag(simulation) {{
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
                d.fx = d.x;
                d.fy = d.y;
            }}

            return d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended);
        }}

        // Handle window resize
        window.addEventListener("resize", () => {{
            const newWidth = window.innerWidth;
            const newHeight = window.innerHeight;

            svg.attr("width", newWidth)
               .attr("height", newHeight);
        }});
    </script>
</body>
</html>"""

    # Write the HTML file
    output_file = os.path.join(scraped_data_dir, "grand_network_visualization1.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Grand visualization created at {output_file}")
    print(f"Network includes {len(nodes)} nodes and {len(links)} connections")
    return output_file

def main():
    scraped_data_dir = "../scraped_data"
    
    if not os.path.exists(scraped_data_dir):
        print(f"Error: {scraped_data_dir} directory not found")
        return

    generate_grand_visualization(scraped_data_dir)

if __name__ == "__main__":
    main()
