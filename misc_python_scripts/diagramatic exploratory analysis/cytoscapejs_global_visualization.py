#!/usr/bin/env python3
"""
Global Network Visualization Generator - Improved Stability Version

Creates a comprehensive visualization showing all onion sites and their interconnections.
Optimized physics to prevent nodes from flying off-screen or failing to settle.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path

def extract_onion_addresses_from_file(file_path):
    """Extract all unique onion addresses from a links file."""
    onion_addresses = set()
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # Support both v2 and v3 onion addresses
            url_matches = re.findall(r'https?://[^\s\'\"<>]+', content)
            for match in url_matches:
                try:
                    parsed = urllib.parse.urlparse(match)
                    if parsed.scheme and parsed.netloc:
                        onion_match = re.search(r'([a-z2-7]{16,56}\.onion)|([a-z2-7]{52}\.b32\.i2p)', match)
                        if onion_match:
                            onion_addr = next(g for g in onion_match.groups() if g is not None)
                            onion_addresses.add(onion_addr)
                except:
                    continue
    return list(onion_addresses)

def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    if not os.path.exists(scraped_data_dir):
        return []
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        # Match v3 addresses (56 chars) or v2 (16 chars)
        if os.path.isdir(item_path) and re.match(r'^[a-z2-7]{16,56}$', item):
            onion_dirs.append(item)
    return onion_dirs

def extract_title_from_html(html_file_path):
    """Extract title from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    title = ' '.join(title.split())
                    return title
        except Exception as e:
            print(f"Error reading {html_file_path}: {str(e)}")
    return None

def generate_global_visualization(scraped_data_dir):
    """Generate a global visualization with improved physics and stability."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to visualize")

    site_data = {}
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        urls_dir = os.path.join(site_dir, 'urls')
        htmls_dir = os.path.join(site_dir, 'htmls')
        images_dir = os.path.join(site_dir, 'images')

        all_onion_addresses = set()
        # Check standard urls folder
        if os.path.exists(urls_dir):
            for file_name in os.listdir(urls_dir):
                if file_name.endswith('_links.txt'):
                    links_file_path = os.path.join(urls_dir, file_name)
                    all_onion_addresses.update(extract_onion_addresses_from_file(links_file_path))

        # Also check discovered_links folder
        discovered_links_dir = os.path.join(site_dir, 'discovered_links')
        if os.path.exists(discovered_links_dir):
            for file_name in os.listdir(discovered_links_dir):
                if file_name.endswith('_links.txt'):
                    links_file_path = os.path.join(discovered_links_dir, file_name)
                    all_onion_addresses.update(extract_onion_addresses_from_file(links_file_path))

        main_html_file = os.path.join(htmls_dir, f"{onion_addr}.html")
        title = extract_title_from_html(main_html_file)
        if not title:
            title = f"{onion_addr}.onion"

        index_image_path = os.path.join(images_dir, "index.png")
        onion_image_path = os.path.join(images_dir, f"{onion_addr}.png")
        
        if os.path.exists(index_image_path):
            image_path = f"{onion_addr}/images/index.png"
        elif os.path.exists(onion_image_path):
            image_path = f"{onion_addr}/images/{onion_addr}.png"
        else:
            image_path = ""

        site_data[onion_addr] = {
            'title': title,
            'connected_onions': list(all_onion_addresses),
            'image_path': image_path
        }

    elements = []
    addr_to_idx = {}
    existing_nodes = set()

    for idx, (addr, data) in enumerate(site_data.items()):
        if addr not in existing_nodes:
            node_data = {
                'id': addr,
                'name': f"http://{addr}.onion",
                'title': data['title'],
            }
            if data['image_path']:
                node_data['image'] = data['image_path']
            
            elements.append({'data': node_data})
            existing_nodes.add(addr)

    for source_addr, data in site_data.items():
        for connected_addr in data['connected_onions']:
            pure_connected_addr = connected_addr.replace('.onion', '')
            # Ensure the target node exists in our site_data before creating a link
            if pure_connected_addr in site_data and source_addr != pure_connected_addr:
                elements.append({
                    'data': {
                        'source': source_addr,
                        'target': pure_connected_addr
                    }
                })

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Global Onion Network (Cytoscape)</title>
    <script src="../../../cytoscape.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; background-color: #1a1a1a; font-family: 'Segoe UI', sans-serif; color: #eee; }}
        #cy {{ width: 100vw; height: 100vh; display: block; }}
        #ui {{ position: absolute; top: 20px; left: 20px; background: rgba(30, 30, 35, 0.9); padding: 15px; border: 1px solid #333; border-radius: 10px; z-index: 10; backdrop-filter: blur(8px); box-shadow: 0 4px 20px rgba(0,0,0,0.5); }}
        h1 {{ margin: 0 0 10px 0; font-size: 16px; color: #00f2ff; }}
        .stats {{ font-size: 12px; color: #888; margin-bottom: 10px; }}
        input {{ background: #2a2a2a; border: 1px solid #444; color: #fff; padding: 5px 10px; border-radius: 4px; width: 180px; font-size: 12px; }}
        #loading {{ position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.8); padding: 20px; border-radius: 10px; z-index: 1000; display: none; }}
    </style>
</head>
<body>
    <div id="loading">🚀 Calculating Layout... Please wait.</div>
    <div id="ui">
        <h1>Onion Network Explorer</h1>
        <div class="stats">Nodes: {len(existing_nodes)} | Edges: {len(elements) - len(existing_nodes)}</div>
        <input type="text" id="search" placeholder="Search Title or Address...">
    </div>
    <div id="cy"></div>
    <script>
        const elements = {json.dumps(elements)};
        const loading = document.getElementById('loading');

        if (elements.length > 500) loading.style.display = 'block';

        document.addEventListener('DOMContentLoaded', function() {{
            const cy = window.cy = cytoscape({{
                container: document.getElementById('cy'),
                elements: elements,
                wheelSensitivity: 0.2,
                style: [
                    {{
                        selector: 'node',
                        style: {{
                            'background-color': '#007bff',
                            'label': 'data(title)',
                            'font-size': '8px',
                            'color': '#ccc',
                            'text-valign': 'bottom',
                            'text-margin-y': '4px',
                            'width': '12px',
                            'height': '12px',
                            'text-wrap': 'ellipsis',
                            'text-max-width': '80px'
                        }}
                    }},
                    {{
                        selector: 'node[image]',
                        style: {{
                            'background-image': 'data(image)',
                            'background-fit': 'cover',
                            'width': '30px',
                            'height': '30px',
                            'border-width': 1,
                            'border-color': '#00f2ff'
                        }}
                    }},
                    {{
                        selector: 'edge',
                        style: {{
                            'width': 1,
                            'line-color': '#444',
                            'target-arrow-color': '#444',
                            'target-arrow-shape': 'triangle',
                            'curve-style': 'haystack', // Faster for many edges
                            'opacity': 0.4
                        }}
                    }},
                    {{
                        selector: 'node:selected',
                        style: {{
                            'background-color': '#ff0055',
                            'border-width': 2,
                            'border-color': '#fff'
                        }}
                    }}
                ],
                layout: {{
                    name: 'cose',
                    animate: false, // Huge performance boost
                    randomize: true,
                    componentSpacing: 100,
                    nodeRepulsion: 400000,
                    nestingFactor: 5,
                    numIter: 1000,
                    initialTemp: 200,
                    coolingFactor: 0.95,
                    minTemp: 1.0,
                    ready: () => loading.style.display = 'none'
                }}
            }});

            // Search functionality
            document.getElementById('search').addEventListener('input', (e) => {{
                const term = e.target.value.toLowerCase();
                if (!term) {{
                    cy.elements().style('opacity', 1);
                    return;
                }}
                cy.elements().forEach(el => {{
                    const title = (el.data('title') || '').toLowerCase();
                    const id = (el.data('id') || '').toLowerCase();
                    if (title.includes(term) || id.includes(term)) {{
                        el.style('opacity', 1);
                    }} else {{
                        el.style('opacity', 0.1);
                    }}
                }});
            }});

            cy.on('tap', 'node', function(evt){{
                const node = evt.target;
                const imageUrl = node.data('image');
                if (imageUrl) window.open(imageUrl, '_blank');
            }});
        }});
    </script>
</body>
</html>"""

    output_file = os.path.join(scraped_data_dir, "global_network_visualization.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Visualization created at {output_file}")
    return output_file

def main():
    scraped_data_dir = "../scraped_data"

    if not os.path.exists(scraped_data_dir):
        scraped_data_dir = "scraped_data"
        if not os.path.exists(scraped_data_dir):
            print(f"Error: scraped_data directory not found")
            return

    generate_global_visualization(scraped_data_dir)

if __name__ == "__main__":
    main()
