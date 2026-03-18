#!/usr/bin/env python3
"""
Advanced Sigma.js Global Network Visualization
Includes Community Detection (Clustering) and PageRank (Importance)
"""

import os
import json
import re
import math
import urllib.parse
from pathlib import Path

# Try to import networkx for advanced analysis
try:
    import networkx as nx
    from networkx.algorithms import community
    HAS_NX = True
except ImportError:
    HAS_NX = False

def extract_onion_addresses_from_file(file_path):
    onion_addresses = set()
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                url_matches = re.findall(r'https?://([a-z2-7]{16,56})\.onion[^\s\'\"<>]*', content)
                for addr in url_matches:
                    onion_addresses.add(addr)
        except: pass
    return list(onion_addresses)

def extract_title_from_html(html_file_path):
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    return ' '.join(title_match.group(1).strip().split())
        except: pass
    return None

def extract_title_from_identity(identity_dir):
    if os.path.exists(identity_dir):
        for file_name in os.listdir(identity_dir):
            if file_name.endswith('_title.txt'):
                try:
                    with open(os.path.join(identity_dir, file_name), 'r', encoding='utf-8') as f:
                        line = f.readline()
                        match = re.search(r'\[(.*?)\] ->', line)
                        if match: return match.group(1).strip()
                except: pass
    return None

def generate_mock_data(node_count=2000):
    import random
    nodes = []
    edges = []
    for i in range(node_count):
        addr = f"v3site{i}mock" + "a" * (56-len(str(i))-7)
        nodes.append({
            "key": addr,
            "attributes": {
                "label": f"Site {i}.onion",
                "x": random.uniform(-1000, 1000),
                "y": random.uniform(-1000, 1000),
                "size": 10,
                "color": "#333",
                "image": ""
            }
        })
    for i in range(node_count):
        source = nodes[i]["key"]
        for _ in range(random.randint(1, 2)):
            target_idx = random.randint(0, node_count - 1)
            target = nodes[target_idx]["key"]
            if target != source:
                edges.append({
                    "key": f"e{i}_{target_idx}",
                    "source": source,
                    "target": target
                })
    return nodes, edges

def generate_advanced_viz(scraped_data_dir, mock=False):
    if mock:
        print("Generating mock data (2000 nodes)...")
        nodes, edges = generate_mock_data(2000)
    else:
        onion_sites = []
        if os.path.exists(scraped_data_dir):
            onion_sites = [d for d in os.listdir(scraped_data_dir) 
                           if os.path.isdir(os.path.join(scraped_data_dir, d)) and 16 <= len(d) <= 60]
        
        print(f"Found {len(onion_sites)} onion sites in {scraped_data_dir}")
        site_data = {}
        for onion_addr in onion_sites:
            site_dir = os.path.join(scraped_data_dir, onion_addr)
            title = extract_title_from_html(os.path.join(site_dir, 'htmls', f"{onion_addr}.html"))
            if not title:
                title = extract_title_from_identity(os.path.join(site_dir, 'website_identity'))
            if not title:
                title = f"{onion_addr}.onion"
            
            image_path = ""
            for img in ["index.png", f"{onion_addr}.png"]:
                if os.path.exists(os.path.join(site_dir, 'images', img)):
                    image_path = f"{onion_addr}/images/{img}"
                    break
            
            connected_onions = set()
            for d in ['discovered_links', 'urls']:
                d_path = os.path.join(site_dir, d)
                if os.path.exists(d_path):
                    for f in os.listdir(d_path):
                        if f.endswith('_links.txt'):
                            connected_onions.update(extract_onion_addresses_from_file(os.path.join(d_path, f)))
            
            site_data[onion_addr] = {
                'label': title,
                'onions': list(connected_onions),
                'image': image_path
            }

        nodes = []
        edges = []
        all_sites = list(site_data.keys())
        for i, addr in enumerate(all_sites):
            data = site_data[addr]
            angle = (i / len(site_data)) * 2 * math.pi if len(site_data) > 0 else 0
            radius = 1000
            nodes.append({
                "key": addr,
                "attributes": {
                    "label": data['label'],
                    "x": math.cos(angle) * radius,
                    "y": math.sin(angle) * radius,
                    "size": 10,
                    "color": "#333",
                    "image": data['image']
                }
            })

        edge_id = 0
        for source_addr, data in site_data.items():
            for target in data['onions']:
                if target in site_data and source_addr != target:
                    edges.append({
                        "key": f"e{edge_id}",
                        "source": source_addr,
                        "target": target
                    })
                    edge_id += 1

    if HAS_NX and nodes:
        print("Calculating PageRank and Communities...")
        G = nx.Graph()
        for n in nodes: G.add_node(n["key"])
        for e in edges: G.add_edge(e["source"], e["target"])
        try:
            if G.number_of_nodes() > 0:
                pr = nx.pagerank(G, alpha=0.85)
                communities = list(community.greedy_modularity_communities(G))
                colors = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#46f0f0", "#f032e6", "#bcf60c", "#fabebe"]
                node_map = {n["key"]: n for n in nodes}
                for i, comm in enumerate(communities):
                    color = colors[i % len(colors)]
                    for node_key in comm:
                        if node_key in node_map:
                            node_map[node_key]["attributes"]["color"] = color
                            node_map[node_key]["attributes"]["size"] = 5 + (pr.get(node_key, 0) * 10000)
        except Exception as e:
            print(f"Analysis failed: {e}")

    graph_data = {"nodes": nodes, "edges": edges}

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Advanced Network Analysis (Sigma.js + WebGL)</title>
    <script src="https://cdn.jsdelivr.net/npm/graphology@0.25.1/dist/graphology.min.js"></script>
    <script src="https://unpkg.com/sigma@2.4.0/build/sigma.min.js"></script>
    <style>
        body, #container {{ width: 100vw; height: 100vh; margin: 0; background: #0b0e14; color: #fff; font-family: sans-serif; overflow: hidden; }}
        #ui {{ position: absolute; top: 20px; left: 20px; z-index: 10; background: rgba(13, 17, 23, 0.9); padding: 20px; border-radius: 12px; border: 1px solid #30363d; box-shadow: 0 8px 32px rgba(0,0,0,0.5); backdrop-filter: blur(8px); }}
        h1 {{ margin: 0 0 10px 0; font-size: 18px; color: #58a6ff; }}
        .stat {{ font-size: 14px; opacity: 0.8; margin-bottom: 5px; color: #8b949e; }}
        hr {{ border: 0; border-top: 1px solid #30363d; margin: 15px 0; }}
        .legend {{ font-size:12px; opacity:0.6; line-height: 1.5; }}
    </style>
</head>
<body>
    <div id="ui">
        <h1>Onion Graph Analyzer (WebGL)</h1>
        <div class="stat">Nodes: {len(nodes)}</div>
        <div class="stat">Edges: {len(edges)}</div>
        <hr>
        <div class="legend">
            • <b>Scroll</b> to Zoom, <b>Drag</b> to Pan<br>
            • <b>Node Size</b> = PageRank Importance<br>
            • <b>Images</b> = Site Screenshots<br>
            • <b>Click Node</b> to open screenshot
        </div>
    </div>
    <div id="container"></div>
    <script>
        const container = document.getElementById("container");
        
        let GraphologyLibrary = window.graphology || window.Graphology;
        if (!GraphologyLibrary && window.graphologyLibrary) GraphologyLibrary = window.graphologyLibrary;

        const graph = new GraphologyLibrary.Graph();
        const data = {json.dumps(graph_data)};
        
        data.nodes.forEach(n => {{
            if (!n.attributes.color || n.attributes.color === "#333") n.attributes.color = "#58a6ff";
            n.attributes.x = parseFloat(n.attributes.x) || 0;
            n.attributes.y = parseFloat(n.attributes.y) || 0;
            // Add type for image rendering if image exists
            if (n.attributes.image) n.attributes.type = "image";
            graph.addNode(n.key, n.attributes);
        }});
        
        data.edges.forEach(e => {{
            graph.addEdge(e.source, e.target, {{
                type: "arrow",
                size: 3,
                color: "#666"
            }});
        }});

        const renderer = new Sigma(graph, container, {{
            allowInvalidContainer: true,
            defaultEdgeType: "arrow",
            labelColor: {{ color: "#c9d1d9" }},
            labelSizeRatio: 2,
            labelThreshold: 0,
            edgeProgramClasses: {{
                arrow: Sigma.WebGL.Programs.EdgeArrow
            }},
            // Enable image rendering
            nodeProgramClasses: {{
                image: Sigma.WebGL.Programs.NodeImage
            }}
        }});

        renderer.on("clickNode", ({{ node }}) => {{
            const img = graph.getNodeAttribute(node, "image");
            if (img) window.open(img, "_blank");
        }});

        setTimeout(() => {{
            renderer.refresh();
            if (graph.order > 0) renderer.getCamera().animatedReset();
        }}, 500);
    </script>
</body>
</html>"""

    out = "advanced_sigma_analysis.html"
    with open(out, 'w', encoding='utf-8') as f: f.write(html_content)
    print(f"Visualization saved to {out}")

if __name__ == "__main__":
    import sys
    path = "scraped_data" if not len(sys.argv) > 1 else sys.argv[1]
    mock = not os.path.exists(path)
    generate_advanced_viz(path, mock=mock)
