#!/usr/bin/env python3
"""
Force-Graph t-SNE Embeddings Visualization
Displays semantic clustering of onion sites using t-SNE coordinates.
Uses force-graph for modern, high-performance interactive rendering.
"""

import os
import json
import re
import numpy as np
import argparse
from pathlib import Path
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from sentence_transformers import SentenceTransformer

def extract_text_from_website_title(title_file_path):
    try:
        with open(title_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        titles = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('[') and ']' in line:
                end_idx = line.find(']')
                title = line[1:end_idx].strip()
                if title: titles.append(title)
        return ' '.join(titles)
    except: return ""

def extract_text_embeddings(texts, model_name='all-MiniLM-L6-v2'):
    print(f"Loading transformer: {model_name}")
    model = SentenceTransformer(model_name)
    print(f"Embedding {len(texts)} texts...")
    embeddings = model.encode(texts, show_progress_bar=True)
    return np.array(embeddings)

def apply_tsne(features, perplexity=30):
    print(f"Applying t-SNE reduction...")
    adjusted_perplexity = min(perplexity, features.shape[0] - 1)
    if features.shape[1] > 50:
        pca = PCA(n_components=min(50, features.shape[0], features.shape[1]))
        features = pca.fit_transform(features)
    tsne = TSNE(n_components=2, perplexity=adjusted_perplexity, max_iter=1000, random_state=42)
    return tsne.fit_transform(features)

def generate_tsne_forcegraph(tsne_coords, site_data, output_file):
    nodes = []
    # Normalize coordinates for better initial view
    coords = np.array(tsne_coords)
    c_min, c_max = coords.min(axis=0), coords.max(axis=0)
    coords = (coords - c_min) / (c_max - c_min) * 1000 - 500  # Scale to -500 to 500

    for i, (onion_addr, info) in enumerate(site_data.items()):
        img_path_rel = f"{onion_addr}/images/index.png"
        nodes.append({
            "id": onion_addr,
            "name": info.get('title', onion_addr),
            "fx": float(coords[i, 0]),
            "fy": float(coords[i, 1]),
            "img": img_path_rel,
            "val": 15
        })

    graph_data = {"nodes": nodes, "links": []}

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Force-Graph t-SNE Semantics</title>
    <script src="https://unpkg.com/force-graph"></script>
    <style>
        body {{ margin: 0; background: #0b0e14; color: #fff; font-family: 'Outfit', sans-serif; overflow: hidden; }}
        #ui {{ position: absolute; top: 20px; left: 20px; z-index: 10; pointer-events: none; }}
        #ui h1 {{ margin: 0; font-size: 26px; color: #7ce7ff; letter-spacing: -0.5px; }}
        #ui p {{ margin: 5px 0; opacity: 0.5; font-size: 12px; }}
        #searchContainer {{ position: absolute; top: 20px; right: 20px; z-index: 20; display: flex; gap: 8px; align-items: center; }}
        #searchBox {{ padding: 12px 20px; border-radius: 12px; border: 1px solid #2d333b; background: rgba(13,17,23,0.9); color: #fff; font-size: 14px; width: 300px; outline: none; backdrop-filter: blur(10px); transition: border 0.2s, box-shadow 0.2s; }}
        #searchBox:focus {{ border-color: #58a6ff; box-shadow: 0 0 12px rgba(88,166,255,0.25); }}
        #searchBox::placeholder {{ color: #3a4a5a; }}
        #clearBtn {{ padding: 10px 14px; border-radius: 10px; border: 1px solid #2d333b; background: rgba(13,17,23,0.9); color: #aaa; cursor: pointer; font-size: 14px; }}
        #clearBtn:hover {{ color: #fff; border-color: #58a6ff; }}
        #match-count {{ position: absolute; top: 65px; right: 20px; z-index: 20; font-size: 11px; color: #4a7a9a; pointer-events: none; }}
        #graph {{ width: 100vw; height: 100vh; cursor: grab; }}
        #graph:active {{ cursor: grabbing; }}
    </style>
</head>
<body>
    <div id="ui">
        <h1>Semantic Cluster Atlas</h1>
        <p>t-SNE Embeddings via SentenceTransformer | {len(nodes)} nodes</p>
    </div>
    <div id="searchContainer">
        <input type="text" id="searchBox" placeholder="🔍 Search semantic clusters...">
        <button id="clearBtn" onclick="document.getElementById('searchBox').value=''; document.getElementById('searchBox').dispatchEvent(new Event('input')); document.getElementById('searchBox').focus();"✕</button>
    </div>
    <div id="match-count"></div>
    <div id="graph"></div>
    <script>
        const gData = {json.dumps(graph_data)};
        const imgCache = {{}};

        const Graph = ForceGraph()(document.getElementById('graph'))
            .graphData(gData)
            .nodeId('id')
            .nodeLabel('name')
            .nodeAutoColorBy('id')
            .backgroundColor('#0b0e14')
            .cooldownTicks(0)
            .enableNodeDrag(true)
            .enablePanInteraction(true)
            .enableZoomInteraction(true)
            .nodeCanvasObjectMode(() => 'replace')
            .onNodeClick(node => {{
                if (node.img) window.open('../' + node.img, '_blank');
            }});

        Graph.nodeCanvasObject((node, ctx, globalScale) => {{
            // Guard against non-finite coordinates
            if (!Number.isFinite(node.x) || !Number.isFinite(node.y)) return;

            const size = node.val / 1.5;
            const isHighlighted = node.__highlighted;
            const isFaded = node.__faded;

            // Draw Node
            ctx.beginPath();
            ctx.arc(node.x, node.y, size, 0, 2 * Math.PI, false);
            ctx.fillStyle = isFaded ? 'rgba(45, 51, 59, 0.3)' : (isHighlighted ? '#fff' : node.color);
            ctx.fill();

            if (isHighlighted) {{
                ctx.strokeStyle = '#7ce7ff';
                ctx.lineWidth = 3 / globalScale;
                ctx.stroke();
                
                // Glow effect
                ctx.shadowBlur = 15;
                ctx.shadowColor = '#58a6ff';
            }} else {{
                ctx.shadowBlur = 0;
            }}

            // Draw Image
            if (node.img && !isFaded) {{
                if (!imgCache[node.img]) {{
                    const img = new Image();
                    img.src = '../' + node.img;
                    imgCache[node.img] = img;
                }}
                const img = imgCache[node.img];
                if (img.complete) {{
                    ctx.save();
                    ctx.beginPath();
                    ctx.arc(node.x, node.y, size - 0.5, 0, 2 * Math.PI, false);
                    ctx.clip();
                    ctx.drawImage(img, node.x - size, node.y - size, size * 2, size * 2);
                    ctx.restore();
                }}
            }}

            // Labels zoom dependent
            if (globalScale > 2.5 || isHighlighted) {{
                const fontSize = (isHighlighted ? 16 : 10) / globalScale;
                ctx.font = `${{fontSize}}px Sans-Serif`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'top';
                ctx.fillStyle = isHighlighted ? '#fff' : 'rgba(255, 255, 255, 0.6)';
                ctx.fillText(node.name, node.x, node.y + size + 2);
            }}
        }});

        // Search
        let currentQuery = '';
        const searchBox = document.getElementById('searchBox');
        const matchCount = document.getElementById('match-count');

        searchBox.addEventListener('input', e => {{
            currentQuery = e.target.value.trim().toLowerCase();
            if (currentQuery) {{
                const hits = gData.nodes.filter(n =>
                    n.name.toLowerCase().includes(currentQuery) ||
                    n.id.toLowerCase().includes(currentQuery)
                ).length;
                matchCount.textContent = hits ? `${{hits}} match${{hits > 1 ? 'es' : ''}} found` : 'No matches';
            }} else {{
                matchCount.textContent = '';
            }}
            gData.nodes.forEach(node => {{
                node.__highlighted = currentQuery && (
                    node.name.toLowerCase().includes(currentQuery) ||
                    node.id.toLowerCase().includes(currentQuery)
                );
                node.__faded = currentQuery && !node.__highlighted;
            }});
            Graph.refresh();
        }});
    </script>
</body>
</html>"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"t-SNE Force-Graph visualization saved to {output_file}")

def main():
    script_dir = Path(__file__).resolve().parent
    scraped_data_dir = script_dir / "../../scraped_data"
    output_file = scraped_data_dir / "forcegraph_tsne_embeddings.html"
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', type=str, default=str(scraped_data_dir))
    parser.add_argument('--output', type=str, default=str(output_file))
    args = parser.parse_args()
    
    title_files = []
    for root, dirs, files in os.walk(args.input_dir):
        if 'website_identity' in root and 'index_title.txt' in files:
            title_files.append(os.path.join(root, 'index_title.txt'))
    
    if not title_files:
        print("No targets found.")
        return

    texts = []
    site_data = {}
    for tf in title_files:
        onion_addr = Path(tf).parts[-3]
        text = extract_text_from_website_title(tf) or onion_addr
        texts.append(text)
        site_data[onion_addr] = {'title': text}

    embeddings = extract_text_embeddings(texts)
    tsne_coords = apply_tsne(embeddings)
    generate_tsne_forcegraph(tsne_coords, site_data, args.output)

if __name__ == "__main__":
    main()
