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

# Pre-compiled regex for onion address validation (v3 hashes are 56 chars, legacy 16)
# We allow 50+ chars to capture full v3 addresses and subdomains
ONION_PATTERN = re.compile(r'^[a-z0-9.-]{50,110}$')


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
            # print(f"Error reading {html_file_path}: {str(e)}")
            pass
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


def find_screenshot_path(onion_address, scraped_data_dir, url_path="", parent_onion=""):
    """Find the appropriate screenshot for a URL based on its path structure."""
    import urllib.parse
    
    # Process onion_address and path
    addr_to_use = onion_address if '://' in onion_address else f"http://{onion_address}"
    parsed = urllib.parse.urlparse(addr_to_use)
    
    # If it's a relative link or has no host, use the parent onion address
    host = parsed.netloc
    if not host and parent_onion:
        # Use parent host but ensure it's just the host part
        host = parent_onion.replace('http://', '').replace('https://', '').split('/')[0]
        if '.onion' not in host:
            host += ".onion"
    
    clean_addr = host.replace('.onion', '')
    if not clean_addr:
        return "", None

    # Determine the target path for slugging
    if not url_path:
        url_path = parsed.path
    
    # Base image directory
    image_dir = os.path.join(scraped_data_dir, clean_addr, 'images')
    if not os.path.exists(image_dir):
        return "", None

    viz_dir = os.path.join(scraped_data_dir, clean_addr, 'visualizations')

    # 1. Check for specific {url_path}.png (highest priority)
    if url_path:
        clean_path = url_path.strip('/')
        if clean_path:
            safe_name = clean_path.replace('/', '_').replace('.', '_')
            path_path = os.path.join(image_dir, f"{safe_name}.png")
            if os.path.exists(path_path):
                rel_path = os.path.relpath(path_path, viz_dir)
                return rel_path.replace('\\', '/'), None

    # 2. Check for index.png (root page screenshot) ONLY if looking at the root path or if it's the exact target
    if url_path == "" or url_path == "/":
        index_path = os.path.join(image_dir, "index.png")
        if os.path.exists(index_path):
            rel_path = os.path.relpath(index_path, viz_dir)
            return rel_path.replace('\\', '/'), None

    return "", None


def generate_visualization(target_onion, scraped_data_dir):
    """Generate HTML visualization for a specific onion site."""
    parsed_target = urllib.parse.urlparse(target_onion if '://' in target_onion else f"http://{target_onion}")
    
    # The folder name is just the host (without .onion)
    clean_onion = parsed_target.netloc.replace('.onion', '')
    if not clean_onion:
        return None

    # Prepare paths
    onion_dir = os.path.normpath(os.path.join(scraped_data_dir, clean_onion))
    
    # Validate that the onion directory exists
    if not os.path.exists(onion_dir):
        # Only print error if it's not a known artifact folder like 'visualizations' or 'mirrors.json'
        if ONION_PATTERN.match(clean_onion) and clean_onion != "visualizations":
            print(f"[ERROR] Onion directory not found: {onion_dir}")
        return None
    
    if not os.path.isdir(onion_dir):
        print(f"[ERROR] Path exists but is not a directory: {onion_dir}")
        return None
    
    images_dir = os.path.join(onion_dir, 'images')
    urls_dir = os.path.join(onion_dir, 'urls')
    htmls_dir = os.path.join(onion_dir, 'htmls')

    # Get title for the root node
    url_path = urllib.parse.urlparse(target_onion).path.strip('/')
    path_slug = url_path.replace('/', '_').replace('.', '_')
    html_filename = f"{path_slug}.html" if path_slug else "index.html"
    
    root_html_file = os.path.join(htmls_dir, html_filename)
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
        # Strip query parameters for deduplication and cleaner visualization
        clean_link = link.split('?')[0].rstrip('/')
        if clean_link not in seen:
            seen.add(clean_link)
            unique_outbound_links.append(link) # Keep original for ID but we'll use clean_link for structure

    # 1. Build a Hierarchical Tree Structure from Paths
    # This prevents the "starburst explosion" by grouping nodes into folders
    # Root: onion.onion
    # Child: /archives/ (folder)
    # Grandchild: /archives/books/ (folder)
    # Great-grandchild: /archives/books/index.html (file)
    
    # helper to find/create child in tree
    def get_or_create_node(parent, node_id, name, is_folder=False):
        for child in parent.setdefault("children", []):
            if child["id"] == node_id:
                return child
        new_node = {
            "id": node_id,
            "name": name,
            "title": name,
            "is_folder": is_folder,
            "children": []
        }
        parent["children"].append(new_node)
        return new_node

    root_image_path, _ = find_screenshot_path(target_onion, scraped_data_dir, parent_onion=target_onion)
    root_node = {
        "id": target_onion,
        "name": target_onion,
        "title": root_title,
        "image": root_image_path,
        "is_root": True,
        "children": []
    }

    # Process each link into the tree
    for link in unique_outbound_links:
        parsed = urllib.parse.urlparse(link)
        if parsed.netloc != f"{clean_onion}.onion" and parsed.netloc != "":
            # External link - keep as direct child of root for now or categorize as 'External'
            ext_root = get_or_create_node(root_node, "external_sites", "External Connections", True)
            image_path, _ = find_screenshot_path(link, scraped_data_dir, parent_onion=target_onion)
            ext_root["children"].append({
                "id": link,
                "name": parsed.netloc,
                "title": link,
                "image": image_path,
                "is_external": True
            })
            continue

        # Internal path-based hierarchy
        path = parsed.path.strip('/')
        if not path: continue # Skip root variations
        
        parts = path.split('/')
        current = root_node
        current_path = f"http://{clean_onion}.onion"
        
        for i, part in enumerate(parts):
            current_path += "/" + part
            is_last = (i == len(parts) - 1)
            
            # If it's the last part, it's the actual node
            if is_last:
                # Get title and image for the final node
                image_path, _ = find_screenshot_path(link, scraped_data_dir, parsed.path, parent_onion=target_onion)
                
                # Check for existing node (might have been created as a folder earlier)
                node = None
                for c in current.get("children", []):
                    if c["id"] == link:
                        node = c
                        break
                
                if node:
                    node["image"] = image_path
                    # update title if we find a better one
                else:
                    current.setdefault("children", []).append({
                        "id": link,
                        "name": part,
                        "title": part,
                        "image": image_path
                    })
            else:
                # Intermediate folder node
                current = get_or_create_node(current, current_path, part, True)

    # Clean up empty children arrays to make D3 happy
    def prune_empty_children(node):
        if "children" in node:
            if not node["children"]:
                del node["children"]
            else:
                for child in node["children"]:
                    prune_empty_children(child)
    
    prune_empty_children(root_node)

    # Generate HTML with embedded JavaScript for D3 visualization
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{target_onion} Archive Map</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&family=JetBrains+Mono&display=swap');
        
        body {{
            margin: 0;
            overflow: hidden;
            background-color: #050505;
            color: #eee;
            font-family: 'Inter', sans-serif;
        }}
        
        #tooltip {{
            position: absolute;
            text-align: left;
            padding: 15px;
            font-size: 13px;
            background: rgba(10, 10, 10, 0.9);
            backdrop-filter: blur(10px);
            color: white;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            max-width: 320px;
            z-index: 100;
        }}
        
        #title-overlay {{
            position: absolute;
            top: 25px;
            left: 25px;
            z-index: 10;
        }}
        
        #title-overlay h1 {{
            margin: 0;
            font-size: 1.2rem;
            font-weight: 600;
            letter-spacing: 1px;
            text-transform: uppercase;
            color: #fff;
        }}
        
        #title-overlay p {{
            margin: 5px 0 0 0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            color: #555;
        }}

        #controls {{
            position: absolute;
            bottom: 30px;
            right: 30px;
            z-index: 10;
            display: flex;
            gap: 10px;
        }}
        
        .control-btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 50%;
            width: 45px;
            height: 45px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            color: white;
            transition: 0.2s;
        }}
        
        .control-btn:hover {{
            background: #fff;
            color: #000;
        }}

        .link {{
            stroke: #222;
            stroke-opacity: 0.4;
            stroke-width: 1.5;
        }}
        
        .node circle {{
            stroke: #000;
            stroke-width: 1.5;
        }}
        
        .node text {{
            font-size: 10px;
            fill: #444;
            pointer-events: none;
        }}
    </style>
</head>
<body>
    <div id="title-overlay">
        <h1>{root_title[:40]}{"..." if len(root_title)>40 else ""}</h1>
        <p>{target_onion}</p>
    </div>
    
    <div id="controls">
        <div class="control-btn" onclick="zoomIn()" title="Zoom In">+</div>
        <div class="control-btn" onclick="zoomOut()" title="Zoom Out">-</div>
        <div class="control-btn" onclick="resetView()" title="Reset">↺</div>
    </div>

    <div id="tooltip"></div>

    <script>
        const data = {json.dumps(root_node)};
        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("body").append("svg")
            .attr("width", width)
            .attr("height", height);
        // Define arrowhead marker
        const g = svg.append("g");
        g.append("defs").append("marker")
            .attr("id", "arrowhead")
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 10)
            .attr("refY", 0)
            .attr("orient", "auto")
            .attr("markerWidth", 4)
            .attr("markerHeight", 4)
            .append("path")
            .attr("d", "M0,-5 L10,0 L0,5")
            .attr("fill", "#666");

        const zoom = d3.zoom()
            .scaleExtent([0.1, 8])
            .on("zoom", (event) => g.attr("transform", event.transform));

        svg.call(zoom);

        // Process Hierarchy
        const root = d3.hierarchy(data);
        const links = root.links();
        const nodes = root.descendants();

        // Simulation setup
        const simulation = d3.forceSimulation(nodes)
            .force("link", d3.forceLink(links).id(d => d.id).distance(100).strength(0.5))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(d => d.data.image ? 40 : 20));

        // Draw links
        const link = g.append("g")
            .attr("class", "links")
            .selectAll("line")
            .data(links)
            .join("line")
            .attr("class", "link")
            .attr("marker-end", "url(#arrowhead)");

        // Draw nodes
        const node = g.append("g")
            .selectAll("g")
            .data(nodes)
            .join("g")
            .attr("class", "node")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));        // Node Visuals
        node.each(function(d) {{
            const el = d3.select(this);
            
            if (d.data.image) {{
                // Image node
                el.append("defs")
                  .append("clipPath")
                  .attr("id", "clip-" + d.index)
                  .append("circle")
                  .attr("r", 30);

                el.append("circle")
                  .attr("r", 32)
                  .attr("fill", "none")
                  .attr("stroke", "#fff")
                  .attr("stroke-width", 2);

                el.append("image")
                  .attr("xlink:href", d.data.image)
                  .attr("x", -30)
                  .attr("y", -30)
                  .attr("width", 60)
                  .attr("height", 60)
                  .attr("clip-path", "url(#clip-" + d.index + ")");
            }} else {{
                // Geometric node
                let color = "#333";
                let radius = 5;
                
                if (d.data.is_root) {{ color = "#fff"; radius = 10; }}
                else if (d.data.is_folder) {{ color = "#0078D7"; radius = 7; }}
                else if (d.data.is_external) {{ color = "#ff4d4d"; radius = 6; }}
                
                el.append("circle")
                  .attr("r", radius)
                  .attr("fill", color)
                  .attr("filter", d.data.is_root ? "drop-shadow(0 0 5px rgba(255,255,255,0.5))" : "none");
            }}
            
            // Labels only for significant nodes or when zoomed
            if (d.data.is_root || d.data.is_folder || d.depth < 2) {{
                el.append("text")
                  .attr("dy", d.data.image ? 45 : 15)
                  .attr("text-anchor", "middle")
                  .text(d.data.name.length > 20 ? d.data.name.substring(0, 17) + "..." : d.data.name);
            }}
        }});

        // Tooltip interaction
        node.on("mouseover", (event, d) => {{
            d3.select("#tooltip")
                .style("opacity", 1)
                .html(`
                    <div style="margin-bottom:8px; font-weight:600; color:#fff;">${{d.data.title}}</div>
                    <div style="font-family:monospace; font-size:11px; color:#666; word-break:break-all;">${{d.data.id}}</div>
                    ${{d.data.image ? `<img src="${{d.data.image}}" style="width:100%; margin-top:10px; border:1px solid #222;">` : ''}}
                `)
                .style("left", (event.pageX + 20) + "px")
                .style("top", (event.pageY - 20) + "px");
        }}).on("mouseout", () => {{
            d3.select("#tooltip").style("opacity", 0);
        }});

        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => {{
                    // Logic to make arrow stop at the node's edge
                    let radius = 10; // Default
                    if (d.target.data.image) radius = 35;
                    else if (d.target.data.is_root) radius = 12;
                    else if (d.target.data.is_folder) radius = 9;
                    else if (d.target.data.is_external) radius = 8;
                    
                    const dx = d.target.x - d.source.x;
                    const dy = d.target.y - d.source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    return d.target.x - (dx * radius / dist);
                }})
                .attr("y2", d => {{
                    let radius = 10; // Default
                    if (d.target.data.image) radius = 35;
                    else if (d.target.data.is_root) radius = 12;
                    else if (d.target.data.is_folder) radius = 9;
                    else if (d.target.data.is_external) radius = 8;
                    
                    const dx = d.target.x - d.source.x;
                    const dy = d.target.y - d.source.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    return d.target.y - (dy * radius / dist);
                }});

            node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        }});

        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
        }}
        function dragged(event, d) {{
            d.fx = event.x; d.fy = event.y;
        }}
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
        }}

        function zoomIn() {{ svg.transition().call(zoom.scaleBy, 1.5); }}
        function zoomOut() {{ svg.transition().call(zoom.scaleBy, 0.7); }}
        function resetView() {{ svg.transition().call(zoom.transform, d3.zoomIdentity); }}

    </script>
</body>
</html>"""

    # Create a unique filename based on the target URL path to avoid overwrites
    # library.onion -> library_viz.html
    # library.onion/archives/ -> library_archives_viz.html
    url_path = urllib.parse.urlparse(target_onion).path.strip('/')
    path_slug = url_path.replace('/', '_').replace('.', '_')
    file_prefix = f"{clean_onion}_{path_slug}" if path_slug else clean_onion
    
    # Create web-friendly filename
    viz_filename = f"{file_prefix}_viz.html"

    # Create visualization directory
    viz_dir = os.path.join(scraped_data_dir, clean_onion, 'visualizations')
    os.makedirs(viz_dir, exist_ok=True)

    # Write the HTML file
    output_file = os.path.join(viz_dir, viz_filename)
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
    # (Exclude known system/utility folders)
    excluded_dirs = ["visualizations", "discovered_links"]
    onion_dirs = [d for d in os.listdir(scraped_data_dir)
                  if os.path.isdir(os.path.join(scraped_data_dir, d))
                  and ONION_PATTERN.match(d)
                  and d.lower() not in excluded_dirs]

    if not onion_dirs:
        print(f"No onion directories found in {scraped_data_dir}")
        return

    print(f"Found {len(onion_dirs)} onion directories to visualize")

    for i, onion_addr in enumerate(onion_dirs):
        print(f"\nProcessing ({i+1}/{len(onion_dirs)}): {onion_addr}")

        # Format the onion URL properly for the index root
        target_onion = f"http://{onion_addr}.onion"
        
        # Collect all explicit targets scraped for this onion
        targets_to_visualize = {target_onion} # Use set to avoid duplicates
        identity_dir = os.path.join(scraped_data_dir, onion_addr, "website_identity")
        
        if os.path.exists(identity_dir):
            for title_file in os.listdir(identity_dir):
                if title_file.endswith('_title.txt'):
                    try:
                        with open(os.path.join(identity_dir, title_file), 'r', encoding='utf-8') as f:
                            content = f.read().strip()
                            # Read format: [Title] -> http://url...
                            if '->' in content:
                                sub_url = content.split('->', 1)[1].strip()
                                targets_to_visualize.add(sub_url)
                    except:
                        pass

        for t in targets_to_visualize:
            print(f" -> Mapping Target: {t}")
            try:
                generate_visualization(t, scraped_data_dir)
            except Exception as e:
                print(f"Error processing {t}: {str(e)}")
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