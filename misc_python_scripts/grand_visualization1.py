#!/usr/bin/env python3
"""
Grand Visualization Generator - Static Image Version

Creates a high-resolution static image showing relationships between different onion sites.
This visualization connects sites that link to each other, showing the network structure
across all scraped onion sites.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path
import matplotlib.pyplot as plt
import networkx as nx

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
    # Extract onion address from URL
    import urllib.parse
    parsed = urllib.parse.urlparse(full_url)
    onion_match = re.search(r'([a-z2-7]{54,})\.onion', full_url)

    if not onion_match:
        return "", None

    onion_address = onion_match.group(1)

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

    print(f"Building Graph...")
    G = nx.Graph()

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
        
        # Add root node
        G.add_node(root_url, title=root_title, image=root_image_path, group=1)

        # Add outbound links as child nodes
        for link in outbound_links:
            # Extract onion address from link
            onion_match = re.search(r'([a-z2-7]{54,})\.onion', link)
            if onion_match:
                # Get title from the scraped HTML if it exists
                linked_onion = onion_match.group(1)
                link_html_file = os.path.join(scraped_data_dir, linked_onion, 'htmls', f"{linked_onion}.html")
                link_title = extract_title_from_html(link_html_file)
                if not link_title:
                    link_title = link  # fallback to URL if no title found

                # Find screenshot path using the new function that considers the full URL
                image_path, image_dims = find_screenshot_path(link, scraped_data_dir)

                # Add child node
                G.add_node(link, title=link_title, image=image_path, group=2)
                G.add_edge(root_url, link)

    print("Detecting communities (clusters)...")
    from networkx.algorithms import community
    import time
    import sys
    
    start_time = time.time()
    
    # Progress tracker for community detection
    def track_community_progress():
        """Track progress during community detection with periodic updates"""
        nodes_processed = 0
        total_nodes = G.number_of_nodes()
        last_update = 0
        
        def progress_callback():
            nonlocal nodes_processed, last_update
            nodes_processed += 1
            current_time = time.time()
            
            # Update progress every 2 seconds or every 10% of nodes
            if current_time - last_update > 2 or (nodes_processed % max(1, total_nodes // 10) == 0):
                progress = min(100, (nodes_processed / total_nodes) * 100)
                elapsed = current_time - start_time
                sys.stdout.write(f"\rProgress: {progress:.1f}% ({nodes_processed}/{total_nodes} nodes, {elapsed:.1f}s elapsed)")
                sys.stdout.flush()
                last_update = current_time
        
        return progress_callback
    
    # Create progress tracker
    progress_tracker = track_community_progress()
    
    # Show initial status
    print(f"Processing {G.number_of_nodes()} nodes and {G.number_of_edges()} edges...")
    
    # Use Louvain algorithm for large graphs (much faster but still good quality)
    print("Large graph detected - using Louvain algorithm for faster processing...")
    communities = list(community.louvain_communities(G, seed=42))
    
    # Final progress update
    elapsed = time.time() - start_time
    print(f"\nCommunity detection completed in {elapsed:.2f} seconds, found {len(communities)} communities")
    
    # Create a color map for communities
    community_map = {}
    for i, comm in enumerate(communities):
        for node in comm:
            community_map[node] = i
    
    # Assign community ID to nodes for GEXF export and coloring
    for node in G.nodes():
        G.nodes[node]['community'] = community_map.get(node, -1)
    node_colors = [community_map.get(node, -1) for node in G.nodes()]

    print("Calculating PageRank (Identifying key nodes)...")
    try:
        pagerank = nx.pagerank(G, alpha=0.85)
        # Scale pagerank for visibility
        node_sizes = [10 + (pagerank.get(n, 0) * 3000) for n in G.nodes()]
    except Exception as e:
        print(f"PageRank calculation failed: {e}. Defaulting to uniform size.")
        node_sizes = 10

    print("Calculating layout (this may take time)...")
    pos = nx.spring_layout(G, k=0.15, iterations=50, seed=42)

    print("Drawing image...")
    plt.figure(figsize=(40, 40), dpi=100)
    plt.axis('off')
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, alpha=0.1, edge_color='#999999', width=0.5)
    
    # Draw nodes sized by importance and colored by community
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, cmap=plt.cm.jet, alpha=0.7)
    
    plt.title(f"Grand Onion Network ({G.number_of_nodes()} nodes)", fontsize=24)

    output_file = os.path.join(scraped_data_dir, "grand_network_map.png")
    plt.savefig(output_file, bbox_inches='tight', pad_inches=0.5)
    plt.close()

    print(f"Grand visualization created at {output_file}")
    
    # Export GEXF for Gephi
    gexf_file = os.path.join(scraped_data_dir, "grand_network.gexf")
    print(f"Exporting Gephi file to {gexf_file}...")
    try:
        nx.write_gexf(G, gexf_file)
        print("Export successful!")
    except Exception as e:
        print(f"GEXF export failed: {e}")

    # Generate community heatmap using separate module
    from community_heatmap import generate_community_heatmap
    generate_community_heatmap(G, communities, scraped_data_dir)
    
    # Generate anomaly detection
    from anomaly_detection import detect_anomalies
    detect_anomalies(G, communities, scraped_data_dir)

    return output_file

def main():
    scraped_data_dir = "../scraped_data"
    
    if not os.path.exists(scraped_data_dir):
        print(f"Error: {scraped_data_dir} directory not found")
        return

    generate_grand_visualization(scraped_data_dir)

if __name__ == "__main__":
    main()
