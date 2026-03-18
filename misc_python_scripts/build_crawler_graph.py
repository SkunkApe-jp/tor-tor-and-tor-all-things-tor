#!/usr/bin/env python3
"""
Build adjacency list JSON from crawler data for visualization.py
"""
import os
import json
import re
from pathlib import Path
from collections import defaultdict


def extract_onion_address(url):
    """Extract onion address from URL."""
    match = re.search(r'([a-z2-7]{16,56}\.onion)', url)
    return match.group(1) if match else None


def build_graph_from_crawler_data(scraped_data_dir):
    """
    Build adjacency list from scraped data.
    Returns dict: {source_onion: [target_onions...]}
    """
    graph = defaultdict(set)
    scraped_data_path = Path(scraped_data_dir)
    
    if not scraped_data_path.exists():
        print(f"Error: Directory {scraped_data_dir} does not exist")
        return {}
    
    # Iterate through all onion directories
    for onion_dir in scraped_data_path.iterdir():
        if not onion_dir.is_dir():
            continue
            
        # Ensure onion address in the key has .onion suffix
        onion_addr = onion_dir.name
        if not onion_addr.endswith(".onion"):
            onion_addr_with_suffix = f"{onion_addr}.onion"
        else:
            onion_addr_with_suffix = onion_addr
            
        # Initialize node even if no links found later
        if onion_addr_with_suffix not in graph:
            graph[onion_addr_with_suffix] = set()
        
        # Look for discovered links
        links_dir = onion_dir / "discovered_links"
        if not links_dir.exists():
            continue
            
        # Read all link files
        for links_file in links_dir.glob("*_links.txt"):
            with open(links_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Extract target onion address
                    target_onion = extract_onion_address(line)
                    # Don't add if it's the same site
                    if target_onion and target_onion != onion_addr_with_suffix:
                        graph[onion_addr_with_suffix].add(target_onion)
    
    # Convert sets to lists for JSON serialization
    return {k: list(v) for k, v in graph.items()}


def main():
    # Paths
    script_dir = Path(__file__).parent.parent
    scraped_data_dir = script_dir / "scraped_data"
    output_file = script_dir / "scraped_data" / "crawler_graph.json"
    
    print(f"[INFO] Building graph from: {scraped_data_dir}")
    
    # Build the graph
    graph = build_graph_from_crawler_data(scraped_data_dir)
    
    if not graph:
        print("[WARN] No graph data generated. Check if scraped_data contains onion directories.")
        return
    
    # Save to JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(graph, f, indent=2)
    
    print(f"[OK] Graph saved to: {output_file}")
    print(f"[INFO] Nodes: {len(graph)}")
    total_edges = sum(len(v) for v in graph.values())
    print(f"[INFO] Edges: {total_edges}")


if __name__ == "__main__":
    main()
