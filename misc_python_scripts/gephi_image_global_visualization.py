#!/usr/bin/env python3
"""
Global Network Visualization Generator - Static Image Version

Creates a high-resolution static image of the network using NetworkX and Matplotlib.
Optimized for large datasets (10k+ nodes) where interactive web visualizations fail.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path
import matplotlib.pyplot as plt
import networkx as nx

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

def generate_global_visualization(scraped_data_dir, export_gexf=True):
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

    print(f"Building Graph for {len(site_data)} nodes...")
    G = nx.Graph()

    # Add nodes first
    for addr, data in site_data.items():
        # Add attributes so they show up in Gephi or analysis
        G.add_node(addr, title=data['title'], image=data['image_path'])

    # Add edges
    for source_addr, data in site_data.items():
        for connected_addr in data['connected_onions']:
            pure_connected_addr = connected_addr.replace('.onion', '')
            if pure_connected_addr in site_data and source_addr != pure_connected_addr:
                G.add_edge(source_addr, pure_connected_addr)

    print("Detecting communities (clusters)...")
    # This algorithm finds groups of nodes that are more connected to each other than to the rest of the network.
    from networkx.algorithms import community
    communities = list(community.greedy_modularity_communities(G))
    
    # Create a color map for communities
    community_map = {}
    for i, comm in enumerate(communities):
        for node in comm:
            community_map[node] = i
    
    # Assign community ID and color to each node. This data will also be in the GEXF file for Gephi.
    for node in G.nodes():
        G.nodes[node]['community'] = community_map.get(node, -1)
    node_colors = [community_map.get(node, -1) for node in G.nodes()]

    print("Calculating PageRank (Identifying key nodes)...")
    # This ranks nodes by influence. Key for visualizing "important" sites.
    try:
        pagerank = nx.pagerank(G, alpha=0.85)
        # Scale pagerank for visibility (min size 10, plus importance factor)
        node_sizes = [10 + (pagerank.get(n, 0) * 5000) for n in G.nodes()]
    except Exception as e:
        print(f"PageRank calculation failed: {e}. Defaulting to uniform size.")
        node_sizes = 15

    print("Calculating layout (this may take time for 10k+ nodes)...")
    # k value controls spacing (larger = more spread out). iterations affects quality vs speed.
    pos = nx.spring_layout(G, k=0.15, iterations=50, seed=42)

    print("Drawing image...")
    plt.figure(figsize=(40, 40), dpi=100)  # High resolution canvas (4000x4000px)
    plt.axis('off')
    
    # Draw nodes and edges
    # Use lower alpha and size for large networks to reduce clutter
    nx.draw_networkx_edges(G, pos, alpha=0.1, edge_color='#999999', width=0.5)
    
    # Draw nodes sized by importance and colored by community
    nx.draw_networkx_nodes(G, pos, node_size=node_sizes, node_color=node_colors, cmap=plt.cm.jet, alpha=0.7)
    
    plt.title(f"Global Onion Network ({G.number_of_nodes()} sites)", fontsize=24)

    output_file = os.path.join(scraped_data_dir, "global_network_map.png")
    plt.savefig(output_file, bbox_inches='tight', pad_inches=0.5)
    plt.close()

    print(f"Visualization created at {output_file}")

    if export_gexf:
        gexf_file = os.path.join(scraped_data_dir, "global_network.gexf")
        print(f"Exporting Gephi file to {gexf_file}...")
        try:
            nx.write_gexf(G, gexf_file)
            print("Export successful! Open this .gexf file in Gephi for 3D/Interactive analysis.")
        except Exception as e:
            print(f"GEXF export failed: {e}")

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
