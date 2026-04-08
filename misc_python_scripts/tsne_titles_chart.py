#!/usr/bin/env python3
"""
t-SNE Title Clustering from titles.txt

Reads titles from a simple text file (one per line) and creates 
an interactive clustering visualization using t-SNE dimensionality reduction.
"""

import os
import sys
import json
import argparse
import numpy as np
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from pathlib import Path
from datetime import datetime


def read_titles(titles_file_path):
    """Read titles from a text file, one per line."""
    try:
        with open(titles_file_path, 'r', encoding='utf-8-sig') as f:
            titles = []
            for line in f:
                line = line.strip()
                if line:
                    titles.append(line)
        return titles
    except FileNotFoundError:
        print(f"Error: File not found: {titles_file_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading {titles_file_path}: {e}", file=sys.stderr)
        sys.exit(1)


def extract_embeddings(texts, llama_server_url):
    """Extract embeddings from texts using llama-server API."""
    import requests

    embeddings = []
    print(f"Using llama-server at: {llama_server_url}")
    print(f"Extracting embeddings from {len(texts)} texts...")

    for i, text in enumerate(texts):
        try:
            response = requests.post(
                f"{llama_server_url}/embedding",
                json={"content": text},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            # Handle llama-server format: [{"index":0,"embedding":[[...]]}]
            if isinstance(result, list) and len(result) > 0:
                emb_data = result[0].get('embedding', [])
                if isinstance(emb_data, list) and len(emb_data) > 0 and isinstance(emb_data[0], list):
                    embedding = emb_data[0]  # Flatten [[...]] -> [...]
                else:
                    embedding = emb_data
            elif isinstance(result, dict):
                embedding = result.get('embedding', [])
            else:
                embedding = []
            embeddings.append(embedding)

            if (i + 1) % 10 == 0 or (i + 1) == len(texts):
                print(f"  Processed {i + 1}/{len(texts)} texts")

        except Exception as e:
            print(f"  Warning: Error processing text '{text[:50]}...': {str(e)}")
            # Use zero embedding as fallback (dimension will be set later)
            embeddings.append(None)

    # Filter out failed embeddings
    valid_embeddings = [e for e in embeddings if e is not None]
    if not valid_embeddings:
        print("Error: No valid embeddings could be generated", file=sys.stderr)
        sys.exit(1)
    
    # Get embedding dimension from first valid embedding
    emb_dim = len(valid_embeddings[0])
    
    # Replace None with zero vectors
    embeddings = [e if e is not None else [0.0] * emb_dim for e in embeddings]
    
    return np.array(embeddings)


def apply_tsne(features, perplexity=30, n_iterations=1000):
    """Apply t-SNE to reduce features to 2D coordinates."""
    print(f"Applying t-SNE with {features.shape[0]} samples...")

    # Adjust perplexity if it's >= number of samples
    adjusted_perplexity = min(perplexity, features.shape[0] - 1)
    if adjusted_perplexity != perplexity:
        print(f"Adjusted perplexity from {perplexity} to {adjusted_perplexity}")

    # Optional: Use PCA first to reduce dimensions if there are many features
    if features.shape[1] > 50:
        print("Using PCA to reduce dimensions before t-SNE...")
        n_components = min(50, features.shape[0], features.shape[1])
        pca = PCA(n_components=n_components)
        features = pca.fit_transform(features)
        print(f"PCA reduced to {n_components} dimensions")

    # Apply t-SNE
    tsne = TSNE(
        n_components=2, 
        perplexity=adjusted_perplexity, 
        max_iter=n_iterations, 
        random_state=42, 
        verbose=1
    )
    tsne_coords = tsne.fit_transform(features)

    print("t-SNE complete!")
    return tsne_coords


def generate_d3_visualization(coords, titles, output_file):
    """Generate HTML with D3 visualization for clustered titles."""
    
    # Normalize coordinates to 0-1 range
    coords_min = coords.min(axis=0)
    coords_max = coords.max(axis=0)
    coord_ranges = coords_max - coords_min
    
    # Handle case where all coords are the same
    if np.any(coord_ranges == 0):
        coords_normalized = coords.copy()
        for i in range(coords.shape[0]):
            coords_normalized[i][0] = i * 0.5
            coords_normalized[i][1] = 0.5
    else:
        coords_normalized = (coords - coords_min) / coord_ranges

    # Scale to canvas
    canvas_size = 1000
    coords_scaled = coords_normalized * canvas_size

    # Prepare data for visualization
    vis_data = []
    for i, title in enumerate(titles):
        vis_data.append({
            'x': float(coords_scaled[i][0]),
            'y': float(coords_scaled[i][1]),
            'title': title,
            'id': i
        })

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>t-SNE Title Clustering</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            margin: 0;
            overflow: hidden;
            background-color: #f8f9fa;
            font-family: Arial, sans-serif;
        }}
        #tooltip {{
            position: absolute;
            text-align: left;
            padding: 12px;
            font-size: 14px;
            background: rgba(255, 255, 255, 0.95);
            color: #333;
            border: 1px solid #ddd;
            border-radius: 8px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            max-width: 400px;
            z-index: 100;
        }}
        .title-node {{
            cursor: pointer;
            transition: all 0.2s;
        }}
        .title-node:hover {{
            stroke: #ff6b6b;
            stroke-width: 3px;
            filter: drop-shadow(0 0 6px rgba(255, 107, 107, 0.6));
        }}
        #title {{
            position: absolute;
            top: 15px;
            left: 15px;
            color: #333;
            font-size: 20px;
            font-weight: 600;
            z-index: 10;
            background: rgba(255, 255, 255, 0.9);
            padding: 10px 16px;
            border-radius: 8px;
            border: 1px solid #ddd;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        #controls {{
            position: absolute;
            top: 15px;
            right: 15px;
            z-index: 10;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }}
        .control-btn {{
            background: rgba(255, 255, 255, 0.9);
            border: 1px solid #ddd;
            border-radius: 6px;
            padding: 10px 14px;
            cursor: pointer;
            font-size: 16px;
            color: #333;
            text-align: center;
            min-width: 44px;
            user-select: none;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .control-btn:hover {{
            background: #f0f0f0;
        }}
        #info {{
            position: absolute;
            bottom: 15px;
            left: 15px;
            color: #666;
            font-size: 13px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.9);
            padding: 8px 14px;
            border-radius: 6px;
            border: 1px solid #ddd;
        }}
        #searchContainer {{
            position: absolute;
            top: 15px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 10;
            display: flex;
            gap: 8px;
            align-items: center;
        }}
        #searchBox {{
            padding: 12px 18px;
            width: 360px;
            border: 2px solid #ddd;
            border-radius: 8px;
            font-size: 14px;
            outline: none;
            transition: all 0.2s;
            background: rgba(255, 255, 255, 0.95);
        }}
        #searchBox:focus {{
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }}
        #clearSearch {{
            padding: 12px 18px;
            background: #f0f0f0;
            border: 2px solid #ddd;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
            color: #666;
            transition: all 0.2s;
        }}
        #clearSearch:hover {{
            background: #e0e0e0;
            border-color: #999;
        }}
        #matchCount {{
            position: absolute;
            top: 60px;
            left: 50%;
            transform: translateX(-50%);
            z-index: 10;
            background: rgba(99, 102, 241, 0.9);
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 13px;
            font-weight: 500;
            display: none;
        }}
        .highlighted {{
            filter: drop-shadow(0 0 10px rgba(255, 107, 107, 0.9)) !important;
        }}
    </style>
</head>
<body>
    <div id="title">t-SNE Title Clustering</div>
    
    <div id="searchContainer">
        <input type="text" id="searchBox" placeholder="🔍 Search titles...">
        <button id="clearSearch">✕ Clear</button>
    </div>
    
    <div id="matchCount">0 matches</div>
    
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()">+</button>
        <button class="control-btn" onclick="zoomOut()">−</button>
        <button class="control-btn" onclick="resetView()">⟲</button>
    </div>
    
    <div id="info">{len(vis_data)} titles clustered by semantic similarity</div>
    <div id="tooltip"></div>
    
    <script>
        const titleData = {json.dumps(vis_data)};
        const canvasSize = {canvas_size};
        
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        const svg = d3.select("body")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .attr("style", "max-width: 100%; height: 100vh;");
        
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});
        svg.call(zoom);
        
        function zoomIn() {{
            svg.transition().duration(750).call(zoom.scaleBy, 1.5);
        }}
        
        function zoomOut() {{
            svg.transition().duration(750).call(zoom.scaleBy, 0.5);
        }}
        
        function resetView() {{
            svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity);
        }}
        
        const g = svg.append("g");
        
        // Calculate initial zoom to fit all nodes
        const allX = titleData.map(d => d.x);
        const allY = titleData.map(d => d.y);
        const minX = Math.min(...allX), maxX = Math.max(...allX);
        const minY = Math.min(...allY), maxY = Math.max(...allY);
        const rangeX = maxX - minX || 1000;
        const rangeY = maxY - minY || 1000;
        
        const initialScale = Math.min(
            (width * 0.85) / rangeX,
            (height * 0.85) / rangeY,
            1
        );
        const initialX = (width / 2) - ((minX + maxX) / 2) * initialScale;
        const initialY = (height / 2) - ((minY + maxY) / 2) * initialScale;
        
        svg.call(zoom.transform, d3.zoomIdentity.translate(initialX, initialY).scale(initialScale));
        
        // Color scale based on position
        const colorScale = d3.scaleSequential(d3.interpolateViridis)
            .domain([0, canvasSize]);
        
        // Draw nodes
        const titleNodes = g.selectAll(".title-node")
            .data(titleData)
            .enter()
            .append("circle")
            .attr("class", "title-node")
            .attr("cx", d => d.x)
            .attr("cy", d => d.y)
            .attr("r", 10)
            .attr("fill", d => colorScale(d.x))
            .attr("stroke", "#333")
            .attr("stroke-width", 1.5)
            .attr("opacity", 0.85)
            .on("mouseover", function(event, d) {{
                tooltip.transition().duration(200).style("opacity", 0.95);
                tooltip.html(`<div style="font-weight:bold;">${{d.title}}</div>`)
                    .style("left", (event.pageX + 12) + "px")
                    .style("top", (event.pageY - 28) + "px");
            }})
            .on("mouseout", function() {{
                tooltip.transition().duration(300).style("opacity", 0);
            }});
        
        const tooltip = d3.select("#tooltip");
        
        // Search functionality
        const searchBox = document.getElementById('searchBox');
        const clearSearch = document.getElementById('clearSearch');
        const matchCount = document.getElementById('matchCount');
        const totalNodes = titleData.length;
        
        function performSearch() {{
            const query = searchBox.value.toLowerCase().trim();
            
            if (!query) {{
                titleNodes.each(function() {{
                    d3.select(this)
                        .classed('highlighted', false)
                        .attr('r', 10)
                        .attr('opacity', 0.85);
                }});
                matchCount.style.display = 'none';
                return;
            }}
            
            let matches = 0;
            titleNodes.each(function(d) {{
                const isMatch = d.title.toLowerCase().includes(query);
                
                d3.select(this)
                    .classed('highlighted', isMatch)
                    .attr('r', isMatch ? 16 : 8)
                    .attr('opacity', isMatch ? 1 : 0.4);
                
                if (isMatch) matches++;
            }});
            
            matchCount.textContent = `${{matches}} / ${{totalNodes}} matches`;
            matchCount.style.display = 'block';
            matchCount.style.backgroundColor = matches > 0 ? 'rgba(99, 102, 241, 0.9)' : 'rgba(255, 100, 100, 0.9)';
        }}
        
        searchBox.addEventListener('input', performSearch);
        
        clearSearch.addEventListener('click', () => {{
            searchBox.value = '';
            performSearch();
            searchBox.focus();
        }});
        
        window.addEventListener("resize", () => {{
            const newWidth = window.innerWidth;
            const newHeight = window.innerHeight;
            svg.attr("width", newWidth).attr("height", newHeight);
        }});
    </script>
</body>
</html>"""

    # Write HTML file
    os.makedirs(os.path.dirname(os.path.abspath(output_file)) or '.', exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Visualization saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Create t-SNE clustering visualization from titles.txt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -f titles.txt
  %(prog)s -f titles.txt -o chart.html --llama-server http://localhost:8080
  %(prog)s -f titles.txt --perplexity 15 --iterations 500
        """
    )

    parser.add_argument(
        '-f', '--file',
        default='titles.txt',
        help='Input file containing titles (one per line) [default: titles.txt]'
    )
    parser.add_argument(
        '-o', '--output',
        default='tsne_titles_chart.html',
        help='Output HTML file [default: tsne_titles_chart.html]'
    )
    parser.add_argument(
        '--llama-server',
        default='http://localhost:8080',
        help='llama-server URL for embeddings [default: http://localhost:8080]'
    )
    parser.add_argument(
        '--perplexity',
        type=int,
        default=30,
        help='t-SNE perplexity [default: 30]'
    )
    parser.add_argument(
        '--iterations',
        type=int,
        default=1000,
        help='t-SNE iterations [default: 1000]'
    )

    args = parser.parse_args()

    # Read titles
    print(f"Reading titles from: {args.file}")
    titles = read_titles(args.file)
    print(f"Loaded {len(titles)} titles")

    if len(titles) < 2:
        print("Error: Need at least 2 titles for clustering", file=sys.stderr)
        sys.exit(1)

    # Get embeddings
    embeddings = extract_embeddings(titles, args.llama_server)
    print(f"Embeddings shape: {embeddings.shape}")

    # Apply t-SNE
    coords = apply_tsne(embeddings, perplexity=args.perplexity, n_iterations=args.iterations)

    # Generate visualization
    generate_d3_visualization(coords, titles, args.output)

    print("\nComplete! Open the HTML file in a browser to view the chart.")


if __name__ == "__main__":
    main()
