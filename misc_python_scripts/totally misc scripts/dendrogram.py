#!/usr/bin/env python3
"""
Dendrogram - Hierarchical Clustering Tree

Shows sites organized in a hierarchical tree structure based on content similarity.
Uses agglomerative clustering to group similar sites together.
"""

import os
import json
import re
import math
from pathlib import Path
from collections import Counter


def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and re.match(r'^[a-z2-7]{16,56}$', item):
            onion_dirs.append(item)
    return onion_dirs


def extract_text_from_html(html_file_path):
    """Extract text content from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content)
                return content.strip()[:2000]
        except Exception:
            pass
    return ""


def extract_keywords(text):
    """Extract keywords from text."""
    stop_words = {
        'the', 'and', 'that', 'this', 'with', 'for', 'are', 'was', 'were', 'been',
        'have', 'has', 'had', 'will', 'would', 'could', 'should', 'from', 'into',
        'there', 'their', 'they', 'them', 'then', 'than', 'these', 'those',
        'which', 'while', 'where', 'when', 'what', 'who', 'whom', 'such', 'only',
        'other', 'some', 'very', 'just', 'also', 'more', 'most', 'each', 'any',
        'all', 'both', 'few', 'many', 'much', 'no', 'not', 'now', 'here', 'www',
        'http', 'https', 'onion', 'click', 'page', 'home', 'tor', 'dark', 'web'
    }
    words = re.findall(r'\b[a-zA-Z]{4,}\b', text.lower())
    return Counter([w for w in words if w not in stop_words])


def cosine_similarity(v1, v2):
    """Calculate cosine similarity between two vectors."""
    all_terms = set(v1.keys()) | set(v2.keys())
    if not all_terms:
        return 0
    
    dot = sum(v1.get(t, 0) * v2.get(t, 0) for t in all_terms)
    mag1 = math.sqrt(sum(v1.get(t, 0) ** 2 for t in all_terms))
    mag2 = math.sqrt(sum(v2.get(t, 0) ** 2 for t in all_terms))
    
    return dot / (mag1 * mag2) if mag1 > 0 and mag2 > 0 else 0


def hierarchical_clustering(sites, similarities):
    """Perform agglomerative hierarchical clustering."""
    # Initialize clusters
    clusters = {site: {'id': site, 'children': [], 'height': 0} for site in sites}
    active = set(sites)
    
    # Convert similarities to distance matrix
    distances = {}
    for (s1, s2), sim in similarities.items():
        distances[(s1, s2)] = 1 - sim
        distances[(s2, s1)] = 1 - sim
    
    cluster_id = 0
    while len(active) > 1:
        # Find closest pair
        min_dist = float('inf')
        closest_pair = None
        
        for c1 in active:
            for c2 in active:
                if c1 < c2:
                    # Calculate average linkage distance
                    total_dist = 0
                    count = 0
                    for s1 in clusters[c1]['children'] or [c1]:
                        for s2 in clusters[c2]['children'] or [c2]:
                            if s1 != s2:
                                key = (min(s1, s2), max(s1, s2))
                                d = distances.get(key, 0.5)
                                total_dist += d
                                count += 1
                    avg_dist = total_dist / count if count > 0 else 0.5
                    
                    if avg_dist < min_dist:
                        min_dist = avg_dist
                        closest_pair = (c1, c2)
        
        if not closest_pair:
            break
        
        # Merge clusters
        c1, c2 = closest_pair
        cluster_id += 1
        new_cluster = f"_cluster_{cluster_id}"
        
        clusters[new_cluster] = {
            'id': new_cluster,
            'children': [c1, c2],
            'height': min_dist / 2
        }
        
        active.remove(c1)
        active.remove(c2)
        active.add(new_cluster)
    
    # Return root cluster
    if active:
        return clusters[list(active)[0]]
    return None


def generate_dendrogram(scraped_data_dir):
    """Generate a dendrogram visualization."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites for clustering")
    
    if len(onion_sites) < 2:
        print("Need at least 2 sites for clustering")
        return None
    
    # Extract keywords for each site
    site_vectors = {}
    site_titles = {}
    site_images = {}
    
    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)
        
        # Get text
        html_file = os.path.join(site_dir, 'htmls', f"{addr}.html")
        text = extract_text_from_html(html_file)
        site_vectors[addr] = extract_keywords(text)
        
        # Get title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', text, re.IGNORECASE | re.DOTALL)
        site_titles[addr] = ' '.join(title_match.group(1).strip().split())[:20] if title_match else addr[:16]
        
        # Get image
        for img_name in ["index.png", f"{addr}.png"]:
            if os.path.exists(os.path.join(site_dir, 'images', img_name)):
                site_images[addr] = f"{addr}/images/{img_name}"
                break
    
    # Calculate pairwise similarities
    similarities = {}
    for i, s1 in enumerate(onion_sites):
        for s2 in onion_sites[i+1:]:
            sim = cosine_similarity(site_vectors[s1], site_vectors[s2])
            similarities[(s1, s2)] = sim
    
    # Perform clustering
    root = hierarchical_clustering(onion_sites, similarities)
    
    print(f"  Clustering complete")
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Dendrogram - Hierarchical Clustering</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; background: #0a0a0f; font-family: 'Segoe UI', sans-serif; }}
        #tooltip {{
            position: fixed; padding: 12px; background: rgba(30,30,40,0.95);
            border: 1px solid #444; border-radius: 8px; pointer-events: none;
            opacity: 0; z-index: 100; color: #eee; max-width: 450px;
            transition: opacity 0.2s; font-size: 12px;
            word-break: break-word; white-space: normal;
        }}
        #header {{
            position: fixed; top: 0; left: 0; right: 0;
            background: rgba(10,10,15,0.95); padding: 15px 20px;
            border-bottom: 1px solid #222; z-index: 10;
            display: flex; justify-content: space-between; align-items: center;
        }}
        #header h1 {{ margin: 0; color: #fff; font-size: 18px; }}
        #stats {{ color: #888; font-size: 13px; }}
        #legend {{
            position: fixed; bottom: 20px; left: 20px;
            background: rgba(30,30,40,0.9); padding: 12px;
            border-radius: 8px; border: 1px solid #222; z-index: 10;
            color: #aaa; font-size: 11px;
            line-height: 1.8;
        }}
        #legend strong {{ color: #fff; }}
        #controls {{ position: absolute; top: 20px; right: 20px; z-index: 10; display: flex; flex-direction: column; gap: 8px; }}
        .control-btn {{ background: rgba(30,30,40,0.9); border: 1px solid #444; padding: 10px; cursor: pointer; border-radius: 6px; color: #fff; transition: all 0.2s; }}
        .control-btn:hover {{ background: rgba(50,50,60,0.9); border-color: #666; }}
        .node circle {{ fill: #1f6feb; stroke: #58a6ff; stroke-width: 2px; }}
        .node--internal circle {{ fill: #30363d; stroke: #8b949e; }}
        .node text {{ fill: #c9d1d9; font-size: 11px; }}
        .link {{ fill: none; stroke: #444; stroke-width: 1.5px; }}
        .cluster {{ cursor: pointer; }}
        .cluster:hover {{ opacity: 0.7; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Dendrogram - Hierarchical Content Clustering</h1>
        <div id="stats">{len(onion_sites)} sites clustered</div>
    </div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()" title="Zoom In"><b>+</b></button>
        <button class="control-btn" onclick="zoomOut()" title="Zoom Out"><b>−</b></button>
        <button class="control-btn" onclick="resetView()" title="Reset View">↺</button>
    </div>
    <div id="legend">
        <strong>How to read:</strong><br/>
        • Leaves = Individual sites<br/>
        • Branches = Similarity clusters<br/>
        • Branch height = Dissimilarity<br/>
        • Scroll to zoom, drag to pan<br/>
        • Click leaf to view screenshot
    </div>
    <div id="tooltip"></div>

    <script>
        const treeData = {json.dumps(root if root else {'id': 'empty', 'children': []})};

        const width = window.innerWidth;
        const height = window.innerHeight;
        const nodeCount = {len(onion_sites)};
        
        // Calculate tree dimensions
        const treeHeight = Math.max(nodeCount * 35, 400);
        const treeWidth = width - 300;

        const svg = d3.select("body").append("svg")
            .attr("width", "100%")
            .attr("height", "100vh")
            .attr("viewBox", [0, 0, width, height]);

        // Center the dendrogram
        const offsetX = 80;
        const offsetY = (height - treeHeight) / 2;

        const zoomG = svg.append("g")
            .attr("transform", `translate(${{offsetX}}, ${{offsetY}})`);

        // Zoom with pan
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (e) => zoomG.attr("transform", e.transform));
        svg.call(zoom);

        function zoomIn() {{ svg.transition().duration(400).call(zoom.scaleBy, 1.5); }}
        function zoomOut() {{ svg.transition().duration(400).call(zoom.scaleBy, 0.6); }}
        function resetView() {{ svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity); }}

        const tree = d3.tree().size([treeHeight, treeWidth]);

        const root = d3.hierarchy(treeData, d => d.children);

        // Calculate similarity-based distances
        root.each(d => {{
            d.data.similarity = d.height ? (1 - d.height) : 1;
        }});

        tree(root);

        // Site data for labels
        const sites = {json.dumps(list(site_titles.keys()))};
        const titles = {json.dumps(site_titles)};
        const images = {json.dumps(site_images)};

        // Draw links
        const link = zoomG.selectAll(".link")
            .data(root.links())
            .join("path")
            .attr("class", "link")
            .attr("d", d3.linkHorizontal()
                .x(d => d.y)
                .y(d => d.x));

        // Draw nodes
        const node = zoomG.selectAll(".node")
            .data(root.descendants())
            .join("g")
            .attr("class", d => "node" + (d.children ? " node--internal" : ""))
            .attr("transform", d => `translate(${{d.y}},${{d.x}})`);
        
        node.append("circle")
            .attr("r", d => d.children ? 8 : 10);

        // Label internal nodes (clusters)
        node.filter(d => d.children)
            .append("text")
            .attr("dy", -15)
            .attr("dx", 0)
            .attr("text-anchor", "middle")
            .attr("font-size", "10px")
            .attr("fill", "#aaa")
            .text(d => d.data.id.replace('_cluster_', 'Cluster '));

        // Label leaf nodes (sites)
        node.filter(d => !d.children)
            .append("text")
            .attr("dy", 4)
            .attr("dx", 15)
            .attr("text-anchor", "start")
            .attr("font-size", "11px")
            .attr("fill", "#c9d1d9")
            .text(d => {{
                const title = titles[d.data.id] || d.data.id;
                return title.length > 30 ? title.substring(0, 28) + "..." : title;
            }});

        // Add site info for leaf nodes - tooltips and click handlers
        node.filter(d => !d.children)
            .on("mouseover", (e, d) => {{
                const addr = d.data.id;
                const title = titles[addr] || addr;
                const hasImage = images[addr] ? '📸 Has screenshot' : '';
                d3.select("#tooltip")
                    .style("opacity", 1)
                    .html(`
                        <div style="font-weight: bold; color: #fff;">${{title}}</div>
                        <div style="color: #888; font-size: 10px; word-break: break-all;">${{addr}}</div>
                        ${{hasImage ? `<div style="color: #aaa; margin-top: 5px;">${{hasImage}}</div>` : ''}}
                    `)
                    .style("left", (e.pageX + 15) + "px")
                    .style("top", (e.pageY - 15) + "px");
            }})
            .on("mouseout", () => d3.select("#tooltip").style("opacity", 0))
            .on("click", (e, d) => {{
                const addr = d.data.id;
                if (images[addr]) window.open(images[addr], '_blank');
            }});

        // Add similarity labels on branches
        const linkLabels = zoomG.selectAll(".link-label")
            .data(root.links())
            .join("text")
            .attr("class", "link-label")
            .attr("x", d => (d.source.y + d.target.y) / 2)
            .attr("y", d => (d.source.x + d.target.x) / 2 - 5)
            .attr("text-anchor", "middle")
            .attr("font-size", "9px")
            .attr("fill", "#666")
            .text(d => d.target.data.similarity ? (d.target.data.similarity * 100).toFixed(0) + '%' : '');
    </script>
</body>
</html>"""
    
    output_file = os.path.join(scraped_data_dir, "dendrogram.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\nDendrogram created at {output_file}")
    return output_file


def main():
    scraped_data_dir = "../scraped_data"
    
    if not os.path.exists(scraped_data_dir):
        scraped_data_dir = "scraped_data"
        if not os.path.exists(scraped_data_dir):
            print("Error: scraped_data directory not found")
            return
    
    generate_dendrogram(scraped_data_dir)


if __name__ == "__main__":
    main()
