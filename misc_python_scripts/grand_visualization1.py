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

# Pre-compiled regex for onion address validation (v2: 16 chars, v3: 56 chars, or vanity: <=56 chars)
ONION_PATTERN = re.compile(r'[a-z2-7]{1,56}')
ONION_DIR_PATTERN = re.compile(r'^[a-z2-7]{1,56}$')

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
                        onion_match = ONION_PATTERN.search(match)
                        if onion_match:
                            onion_addresses.add(onion_match.group(0) + '.onion')
                except:
                    continue
    return list(onion_addresses)

def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and ONION_DIR_PATTERN.match(item):
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
    # Extract onion address from URL
    import urllib.parse
    parsed = urllib.parse.urlparse(full_url)
    onion_match = ONION_PATTERN.search(full_url)

    if not onion_match:
        return "", None

    onion_address = onion_match.group(0)

    # Build the path based on URL structure
    path_parts = [p for p in parsed.path.strip('/').split('/') if p]

    # Start with the base image directory
    image_dir = os.path.join(scraped_data_dir, onion_address, 'images')

    # Build the subdirectory path based on URL path
    for part in path_parts[:-1]:  # All parts except the last one form the directory structure
        image_dir = os.path.join(image_dir, part)

    # Create the expected filename based on the URL
    if path_parts:  # If there are path parts
        last_part = path_parts[-1]  # The last part of the path
        # Create filename similar to how the Go app generates it
        if '.' in last_part:
            # If it's a file with extension, replace dots with underscores
            clean_last_part = last_part.replace('.', '_')
            expected_filename = f"{clean_last_part}.png"
        else:
            # If it's a directory path
            expected_filename = f"{last_part}.png"

        # Full path to the expected image
        expected_path = os.path.join(image_dir, expected_filename)

        # Check if the file exists
        if os.path.exists(expected_path):
            # Calculate relative path from visualization file to the image
            # Visualization is in scraped_data root
            viz_dir = scraped_data_dir

            # Path from viz_dir to the image file
            rel_path = os.path.relpath(expected_path, viz_dir)
            full_path = os.path.join(scraped_data_dir, rel_path)
            dimensions = get_image_dimensions(full_path)
            return rel_path.replace('\\', '/'), dimensions  # Normalize path separators
    else:
        # Root page - check for both possible naming schemes
        # First check for index.png
        index_path = os.path.join(image_dir, "index.png")
        if os.path.exists(index_path):
            # Calculate relative path from visualization file to the image
            viz_dir = scraped_data_dir
            rel_path = os.path.relpath(index_path, viz_dir)
            full_path = os.path.join(scraped_data_dir, rel_path)
            dimensions = get_image_dimensions(full_path)
            return rel_path.replace('\\', '/'), dimensions  # Normalize path separators

        # Then check for onion_address.png
        onion_path = os.path.join(image_dir, f"{onion_address}.png")
        if os.path.exists(onion_path):
            # Calculate relative path from visualization file to the image
            viz_dir = scraped_data_dir
            rel_path = os.path.relpath(onion_path, viz_dir)
            full_path = os.path.join(scraped_data_dir, rel_path)
            dimensions = get_image_dimensions(full_path)
            return rel_path.replace('\\', '/'), dimensions  # Normalize path separators

    return "", None


def generate_grand_visualization(scraped_data_dir):
    """Generate a grand visualization showing cross-site relationships with sub-nodes."""

    # Get all onion sites
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to visualize")

    # Create nodes and links for the visualization
    nodes = []
    links = []

    # Create a mapping from URL to node index
    url_to_idx = {}

    # Process each onion site
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        urls_dir = os.path.join(site_dir, 'urls')
        htmls_dir = os.path.join(site_dir, 'htmls')
        images_dir = os.path.join(site_dir, 'images')

        # Get title for the root node
        root_url = f"http://{onion_addr}.onion"
        root_html_file = os.path.join(htmls_dir, f"{onion_addr}.html")
        root_title = extract_title_from_html(root_html_file)
        if not root_title:
            root_title = root_url  # fallback to URL if no title found

        # Read links for this onion site from all available links files
        outbound_links = []

        # Get all links files in the urls directory for this onion site
        if os.path.exists(urls_dir):
            for file_name in os.listdir(urls_dir):
                if file_name.endswith('_links.txt'):
                    links_file_path = os.path.join(urls_dir, file_name)
                    file_links = read_links_file(links_file_path)
                    outbound_links.extend(file_links)

        # Also get all links files in the discovered_links directory for this onion site
        discovered_links_dir = os.path.join(site_dir, 'discovered_links')
        if os.path.exists(discovered_links_dir):
            for file_name in os.listdir(discovered_links_dir):
                if file_name.endswith('_links.txt'):
                    links_file_path = os.path.join(discovered_links_dir, file_name)
                    file_links = read_links_file(links_file_path)
                    outbound_links.extend(file_links)

        # Add root node for this onion site
        root_image_path, root_image_dims = find_screenshot_path(root_url, scraped_data_dir)
        root_node = {
            'id': root_url,
            'name': root_url,
            'title': root_title,
            'image': root_image_path,
            'group': 1  # Root nodes have group 1
        }
        
        # Add root node to nodes list and map
        url_to_idx[root_url] = len(nodes)
        nodes.append(root_node)

        # Add outbound links as child nodes
        for link in outbound_links:
            # Extract onion address from link
            onion_match = ONION_PATTERN.search(link)
            if onion_match:
                # Get title from the scraped HTML if it exists
                linked_onion = onion_match.group(0)
                link_html_file = os.path.join(scraped_data_dir, linked_onion, 'htmls', f"{linked_onion}.html")
                link_title = extract_title_from_html(link_html_file)
                if not link_title:
                    link_title = link  # fallback to URL if no title found

                # Find screenshot path using the new function that considers the full URL
                image_path, image_dims = find_screenshot_path(link, scraped_data_dir)

                # Create child node
                child_node = {
                    'id': link,
                    'name': link,
                    'title': link_title,
                    'image': image_path,
                    'group': 2  # Child nodes have group 2
                }
                
                # Add child node to nodes list and map if not already present
                if link not in url_to_idx:
                    url_to_idx[link] = len(nodes)
                    nodes.append(child_node)
                
                # Create link from root to child
                links.append({
                    'source': url_to_idx[root_url],
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

        // Create force simulation
        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id((d, i) => i).distance(120).strength(0.6))
            .force("charge", d3.forceManyBody().strength(-250))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(function(d) {{ return d.image && d.image !== "" ? 50 : 12; }}));

        // Append links
        const link = g.append("g")
            .attr("stroke", "#666")  // Dark gray for B&W theme
            .attr("stroke-opacity", 0.7)
            .selectAll("line")
            .data(links)
            .join("line");

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
            tooltip.transition()
                .duration(200)
                .style("opacity", .95);
            if (d.image && d.image !== "") {{
                tooltip.html(`<div><strong style="word-break: break-all;">${{d.title}}</strong></div><div style="font-size: 12px; color: #666; margin: 5px 0; word-break: break-all;">${{d.name}}</div><img src="${{d.image}}" style="max-width: 200px; max-height: 150px; margin-top: 5px; border: 1px solid #ddd;" onerror="this.parentNode.innerHTML+='<div style=\\'color:red; font-size:12px; word-break: break-all;\\'>${{d.title}}<br/>${{d.name}}<br/>Image not available</div>';">`)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            }} else {{
                tooltip.html(`<div><strong style="word-break: break-all;">${{d.title}}</strong></div><div style="font-size: 12px; color: #666; margin: 5px 0; word-break: break-all;">${{d.name}}</div><div style='color:red; font-size:12px;'>Image not available</div>`)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            }}
        }})
        .on("mouseout", function(d) {{
            tooltip.transition()
                .duration(500)
                .style("opacity", 0);
        }});

        // Update positions on each tick
        simulation.on("tick", function() {{
            link
                .attr("x1", function(d) {{ return nodes[d.source.index].x; }})
                .attr("y1", function(d) {{ return nodes[d.source.index].y; }})
                .attr("x2", function(d) {{ return nodes[d.target.index].x; }})
                .attr("y2", function(d) {{ return nodes[d.target.index].y; }});

            node
                .attr("transform", function(d) {{ return "translate(" + d.x + "," + d.y + ")"; }});

            label
                .attr("x", function(d) {{ return d.x; }})
                .attr("y", function(d) {{ return d.y; }});
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
