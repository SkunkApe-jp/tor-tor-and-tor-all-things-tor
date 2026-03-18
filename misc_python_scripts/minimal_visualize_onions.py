#!/usr/bin/env python3
"""
Minimal Onion Network Visualization Generator

Creates a simple force-directed graph visualization for scraped onion sites.
"""

import os
import json
import re
import sys
import urllib.parse
from pathlib import Path

# Pre-compiled regex for onion address validation (v2: 16 chars, v3: 56 chars, or vanity: <=56 chars)
ONION_PATTERN = re.compile(r'^[a-z2-7]{1,56}$')


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


def find_screenshot_path(onion_address, scraped_data_dir, url_path=""):
    """Find the appropriate screenshot for a URL based on its path structure.
    
    Looks in: scraped_data/{onion_address}/images/
    Checks: index.png, {onion_address}.png, or {url_path}.png
    """
    import urllib.parse
    
    # Clean onion address if it's a full URL
    if '://' in onion_address:
        parsed = urllib.parse.urlparse(onion_address)
        onion_match = re.search(r'([a-z2-7]{1,56})\.onion', onion_address)
        if onion_match:
            onion_address = onion_match.group(1)
        url_path = parsed.path

    # Base image directory
    image_dir = os.path.join(scraped_data_dir, onion_address, 'images')
    
    if not os.path.exists(image_dir):
        return "", None

    # Check for index.png (root page screenshot)
    index_path = os.path.join(image_dir, "index.png")
    if os.path.exists(index_path):
        viz_dir = os.path.join(scraped_data_dir, onion_address, 'visualizations')
        rel_path = os.path.relpath(index_path, viz_dir)
        return rel_path.replace('\\', '/'), None

    # Check for {onion_address}.png
    onion_path = os.path.join(image_dir, f"{onion_address}.png")
    if os.path.exists(onion_path):
        viz_dir = os.path.join(scraped_data_dir, onion_address, 'visualizations')
        rel_path = os.path.relpath(onion_path, viz_dir)
        return rel_path.replace('\\', '/'), None

    # Check for {url_path}.png if URL path provided
    if url_path and url_path != '/':
        # Clean the path for filename
        safe_name = url_path.strip('/').replace('/', '_').replace('.', '_')
        path_path = os.path.join(image_dir, f"{safe_name}.png")
        if os.path.exists(path_path):
            viz_dir = os.path.join(scraped_data_dir, onion_address, 'visualizations')
            rel_path = os.path.relpath(path_path, viz_dir)
            return rel_path.replace('\\', '/'), None

    return "", None


def generate_visualization(target_onion, scraped_data_dir):
    """Generate HTML visualization for a specific onion site."""

    # Get the clean onion name for directory and filenames
    clean_onion = target_onion.replace('http://', '').replace('https://', '').replace('.onion', '')

    # Prepare paths
    onion_dir = os.path.join(scraped_data_dir, clean_onion)
    
    # Validate that the onion directory exists
    if not os.path.exists(onion_dir):
        print(f"[ERROR] Onion directory not found: {onion_dir}")
        print(f"[INFO] Expected folder for '{target_onion}' does not exist.")
        return None
    
    if not os.path.isdir(onion_dir):
        print(f"[ERROR] Path exists but is not a directory: {onion_dir}")
        return None
    
    images_dir = os.path.join(onion_dir, 'images')
    urls_dir = os.path.join(onion_dir, 'urls')
    htmls_dir = os.path.join(onion_dir, 'htmls')

    # Get title for the root node
    root_html_file = os.path.join(htmls_dir, f"{clean_onion}.html")
    root_title = extract_title_from_html(root_html_file)
    if not root_title:
        root_title = target_onion  # fallback to URL if no title found

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
    discovered_links_dir = os.path.join(onion_dir, 'discovered_links')
    if os.path.exists(discovered_links_dir):
        for file_name in os.listdir(discovered_links_dir):
            if file_name.endswith('_links.txt'):
                links_file_path = os.path.join(discovered_links_dir, file_name)
                file_links = read_links_file(links_file_path)
                outbound_links.extend(file_links)

    # Remove duplicates while preserving order
    seen = set()
    unique_outbound_links = []
    for link in outbound_links:
        if link not in seen:
            seen.add(link)
            unique_outbound_links.append(link)

    outbound_links = unique_outbound_links

    # Create the root node
    root_image_path, _ = find_screenshot_path(target_onion, scraped_data_dir)
    root_node = {
        "id": target_onion,
        "name": target_onion,
        "title": root_title,
        "image": root_image_path,
        "children": []
    }

    # Add outbound links as children
    for i, link in enumerate(outbound_links):
        # Extract onion address from link
        onion_match = re.search(r'([a-z2-7]{1,56})\.onion', link)
        if onion_match:
            # Check if this is a link to the same onion site (internal sub-page)
            target_onion_clean = target_onion.replace('http://', '').replace('https://', '').replace('.onion', '')
            linked_onion = onion_match.group(1)

            # Get title from the scraped HTML if it exists
            link_html_file = os.path.join(scraped_data_dir, linked_onion, 'htmls', f"{linked_onion}.html")

            # If it's the same onion site, look for the specific HTML file
            if linked_onion == target_onion_clean:
                # For internal links, construct the proper HTML file path based on the URL
                path_parts = [p for p in urllib.parse.urlparse(link).path.strip('/').split('/') if p]

                # Start with the base htmls directory
                html_dir = os.path.join(scraped_data_dir, target_onion_clean, 'htmls')

                # Build the subdirectory path based on URL path
                for part in path_parts[:-1]:  # All parts except the last one form the directory structure
                    html_dir = os.path.join(html_dir, part)

                # Create the expected filename based on the URL
                if path_parts:  # If there are path parts
                    last_part = path_parts[-1]  # The last part of the path
                    # Create filename similar to how the Go app generates it
                    if '.' in last_part:
                        # If it's a file with extension, replace dots with underscores
                        clean_last_part = last_part.replace('.', '_')
                        expected_filename = f"{target_onion_clean}_{clean_last_part}.html"
                    else:
                        # If it's a directory path
                        expected_filename = f"{target_onion_clean}_{last_part}.html"

                    link_html_file = os.path.join(html_dir, expected_filename)
                else:
                    # Root page
                    link_html_file = os.path.join(html_dir, f"{target_onion_clean}.html")

            link_title = extract_title_from_html(link_html_file)
            if not link_title:
                link_title = link  # fallback to URL if no title found

            # Find screenshot path
            image_path, _ = find_screenshot_path(link, scraped_data_dir, urllib.parse.urlparse(link).path)

            child_node = {
                "id": link,
                "name": link,
                "title": link_title,
                "image": image_path,
            }
            root_node["children"].append(child_node)

    # Generate HTML with embedded JavaScript for D3 visualization
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{target_onion} Network Visualization</title>
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
    <div id="title">{target_onion} Network</div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()">+</button>
        <button class="control-btn" onclick="zoomOut()">-</button>
        <button class="control-btn" onclick="resetView()">↺</button>
    </div>
    <div id="tooltip"></div>
    <script>
        // Hierarchical data structure
        const data = {json.dumps(root_node)};

        // Chart dimensions
        const width = window.innerWidth;
        const height = window.innerHeight;

        // Compute the graph and start the force simulation
        const root = d3.hierarchy(data);
        const links = root.links();
        const nodes = root.descendants();

        // Pre-position nodes to prevent "explosion" from center
        nodes.forEach((d, i) => {{
            d.x = width / 2 + (Math.random() - 0.5) * 100;
            d.y = height / 2 + (Math.random() - 0.5) * 100;
        }});

        // Create the container SVG
        const svg = d3.select("body")
            .append("svg")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("viewBox", [0, 0, width, height])
            .attr("style", "max-width: 100%; height: 100vh;");

        // Add zoom functionality with panning
        const zoom = d3.zoom()
            .scaleExtent([0.05, 10])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});
        svg.call(zoom);

        // Create zoom functions
        function zoomIn() {{
            svg.transition().duration(400).call(zoom.scaleBy, 1.5);
        }}

        function zoomOut() {{
            svg.transition().duration(400).call(zoom.scaleBy, 0.6);
        }}

        function resetView() {{
            svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity);
        }}

        // Create a group for zooming
        const g = svg.append("g");

        // Create force simulation with improved stability
        const simulation = d3.forceSimulation(nodes)
            .alphaDecay(0.04)
            .force("link", d3.forceLink(links).id(d => d.data.id).distance(150).strength(0.4))
            .force("charge", d3.forceManyBody().strength(-200).distanceMax(500))
            .force("x", d3.forceX(width / 2).strength(0.06))
            .force("y", d3.forceY(height / 2).strength(0.06))
            .force("collision", d3.forceCollide().radius(function(d) {{ return d.data.image && d.data.image !== "" ? 50 : 12; }}));

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
            .attr("cursor", "move")  // Indicate draggable
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));

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
            if (!event.active) simulation.alphaTarget(0.05);  // Lower alpha for smoother settling
            // Allow releasing the fixed position after a delay if desired
            // Or keep it fixed by leaving d.fx and d.fy as set
        }}

        // Add images for nodes that have screenshots
        node.filter(d => d.data.image && d.data.image !== "")
            .append("image")
            .attr("xlink:href", d => d.data.image)
            .attr("x", d => d.x - (d.depth === 0 ? 40 : 20))  // 10x larger when image is present
            .attr("y", d => d.y - (d.depth === 0 ? 40 : 20))  // 10x larger when image is present
            .attr("width", d => d.depth === 0 ? 80 : 40)  // 10x larger when image is present
            .attr("height", d => d.depth === 0 ? 80 : 40)  // 10x larger when image is present
            .attr("clip-path", "circle()");

        // Add circles for nodes that don't have screenshots
        node.filter(d => !(d.data.image && d.data.image !== ""))
            .append("circle")
            .attr("r", d => d.depth === 0 ? 6 : 2.5)  // Medium root node, smaller others
            .attr("fill", "#000")  // Black fill for B&W theme
            .attr("stroke", "#000")
            .attr("stroke-width", 1.5);

        // Add hover functionality
        node.on("mouseover", function(event, d) {{
            const imgPath = d.data.image;
            tooltip.transition()
                .duration(200)
                .style("opacity", .95);
            if (imgPath && imgPath !== "") {{
                // Show image in tooltip even for root node
                // Construct the full path for the tooltip preview
                const fullPath = imgPath.startsWith('../') || imgPath.startsWith('./') ?
                                 imgPath :
                                 `images/${{imgPath}}`;
                tooltip.html(`<div><strong style="word-break: break-all;">${{d.data.title}}</strong></div><div style="font-size: 12px; color: #666; margin: 5px 0; word-break: break-all;">${{d.data.id}}</div><img src="${{fullPath}}" style="max-width: 200px; max-height: 150px; margin-top: 5px; border: 1px solid #ddd;" onerror="this.parentNode.innerHTML+='<div style=\\'color:red; font-size:12px; word-break: break-all;\\'>${{d.data.title}}<br/>${{d.data.id}}<br/>Image not available</div>';">`)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            }} else {{
                tooltip.html(`<div><strong style="word-break: break-all;">${{d.data.title}}</strong></div><div style="font-size: 12px; color: #666; margin: 5px 0; word-break: break-all;">${{d.data.id}}</div><div style='color:red; font-size:12px;'>Image not available</div>`)
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
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            node
                .attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }});

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

    # Create visualization directory for this onion inside its own directory
    viz_dir = os.path.join(scraped_data_dir, clean_onion, 'visualizations')
    os.makedirs(viz_dir, exist_ok=True)

    # Write the HTML file
    output_file = os.path.join(viz_dir, f"{clean_onion}_viz.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Visualization created for {target_onion} at {output_file}")
    return output_file


def visualize_all_onions(scraped_data_dir):
    """Generate visualizations for all onions in the scraped_data directory."""
    if not os.path.exists(scraped_data_dir):
        print(f"Error: {scraped_data_dir} directory not found")
        return

    # Get all directories in scraped_data_dir that look like onion addresses
    onion_dirs = [d for d in os.listdir(scraped_data_dir)
                  if os.path.isdir(os.path.join(scraped_data_dir, d))
                  and ONION_PATTERN.match(d)]

    if not onion_dirs:
        print(f"No onion directories found in {scraped_data_dir}")
        return

    print(f"Found {len(onion_dirs)} onion directories to visualize")

    for i, onion_addr in enumerate(onion_dirs):
        print(f"\nProcessing ({i+1}/{len(onion_dirs)}): {onion_addr}")

        # Format the onion URL properly
        target_onion = f"http://{onion_addr}.onion"

        try:
            generate_visualization(target_onion, scraped_data_dir)
        except Exception as e:
            print(f"Error processing {onion_addr}: {str(e)}")
            continue

    print("\nAll visualizations completed!")


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 minimal_visualize_onions.py <onion_url|all>")
        print("Example 1: python3 minimal_visualize_onions.py meynethaffeecapsvfphrcnfrx44w2nskgls2juwitibvqctk2plvhqd.onion")
        print("Example 2: python3 minimal_visualize_onions.py all  # Visualizes all onions in scraped_data")
        return

    target_arg = sys.argv[1]
    
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()

    if target_arg.lower() == "all":
        visualize_all_onions(str(scraped_data_path))
    else:
        target_onion = target_arg

        # Ensure the target has the proper format
        if not target_onion.startswith(('http://', 'https://')):
            if '.onion' in target_onion:
                target_onion = f"http://{target_onion}"
            else:
                target_onion = f"http://{target_onion}.onion"

        if not os.path.exists(scraped_data_path):
            print(f"Error: {scraped_data_path} directory not found")
            return

        # Get the clean onion name for directory validation
        clean_onion = target_onion.replace('http://', '').replace('https://', '').replace('.onion', '')

        # Check if the onion directory exists before proceeding
        onion_dir = os.path.join(scraped_data_path, clean_onion)
        if not os.path.exists(onion_dir):
            print(f"[ERROR] No scraped data found for: {clean_onion}")
            print(f"[INFO] Expected directory: {onion_dir}")
            print(f"[INFO] Available onion directories:")
            if os.path.exists(scraped_data_path):
                for d in os.listdir(scraped_data_path):
                    if ONION_PATTERN.match(d):
                        print(f"       - {d}")
            return

        generate_visualization(target_onion, str(scraped_data_path))


if __name__ == "__main__":
    main()