#!/usr/bin/env python3
"""
t-SNE Text Clustering Visualization

Creates a visualization that groups similar onion site texts using t-SNE dimensionality reduction.
Uses only website titles from website_identity/index_title.txt.
"""

import os
import json
import re
import numpy as np
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from sentence_transformers import SentenceTransformer
import argparse
from pathlib import Path

# Onion address pattern: 1-56 base32 characters
ONION_PATTERN = re.compile(r'[a-z2-7]{1,56}')


def extract_text_from_website_title(title_file_path):
    """
    Extract title text from website_identity/index_title.txt.
    Format: [TITLE] -> http://...onion
    Returns just "TITLE" without brackets.
    """
    try:
        with open(title_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        titles = []
        for line in content.split('\n'):
            line = line.strip()
            # Extract text between [ and ]
            if line.startswith('[') and ']' in line:
                end_idx = line.find(']')
                title = line[1:end_idx].strip()
                if title:
                    titles.append(title)
        return ' '.join(titles)
    except Exception as e:
        print(f"Error reading {title_file_path}: {str(e)}")
        return ""


def extract_text_embeddings(texts, model_name='all-MiniLM-L6-v2'):
    """
    Extract embeddings from texts using a sentence transformer model.
    """
    print(f"Loading sentence transformer model: {model_name}")
    model = SentenceTransformer(model_name)

    embeddings = []
    print(f"Extracting embeddings from {len(texts)} texts...")
    for i, text in enumerate(texts):
        try:
            embedding = model.encode([text])[0]
            embeddings.append(embedding)

            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(texts)} texts")

        except Exception as e:
            print(f"Error processing text: {str(e)}")
            embeddings.append(np.zeros(model.get_sentence_embedding_dimension()))
            continue

    return np.array(embeddings)


def find_all_website_title_files(scraped_data_dir):
    """
    Find all website_identity/index_title.txt files in the scraped data directory.
    """
    title_paths = []
    for root, dirs, files in os.walk(scraped_data_dir):
        if 'website_identity' in root and 'index_title.txt' in files:
            title_paths.append(os.path.join(root, 'index_title.txt'))
    return title_paths


def apply_tsne(features, perplexity=30, n_iterations=1000):
    """
    Apply t-SNE to reduce features to 2D coordinates.
    """
    print(f"Applying t-SNE with {features.shape[0]} samples...")

    # Adjust perplexity if it's greater than or equal to the number of samples
    adjusted_perplexity = min(perplexity, features.shape[0] - 1)
    if adjusted_perplexity != perplexity:
        print(f"Adjusted perplexity from {perplexity} to {adjusted_perplexity} (must be < n_samples)")

    # Optional: Use PCA first to reduce dimensions if there are many features
    if features.shape[1] > 50:
        print("Using PCA to reduce dimensions before t-SNE...")
        pca = PCA(n_components=min(50, features.shape[0], features.shape[1]))
        features = pca.fit_transform(features)

    # Apply t-SNE - using the parameter name compatible with the installed sklearn version
    tsne = TSNE(n_components=2, perplexity=adjusted_perplexity, max_iter=n_iterations, random_state=42, verbose=1)
    tsne_coords = tsne.fit_transform(features)

    return tsne_coords


def generate_d3_visualization(coords, text_data, output_file):
    """
    Generate HTML with D3 visualization for t-SNE clustered text data.
    """
    # Normalize coordinates to 0-1 range
    coords_min = coords.min(axis=0)
    coords_max = coords.max(axis=0)

    # Check if all coordinates are the same (would cause division by zero)
    coord_ranges = coords_max - coords_min
    if np.any(coord_ranges == 0):
        # If coordinates are the same, use the original coords directly
        # and set a default range to avoid division by zero
        coords_normalized = coords.copy()
        # Normalize to a default range (e.g., 0 to 1)
        for i in range(coords.shape[0]):
            coords_normalized[i][0] = i * 0.5  # Space them out horizontally
            coords_normalized[i][1] = 0.5  # Center vertically
    else:
        coords_normalized = (coords - coords_min) / coord_ranges

    # Scale to a larger canvas (e.g., 1000x1000)
    canvas_size = 1000
    coords_scaled = coords_normalized * canvas_size

    # Prepare text data for the visualization
    text_vis_data = []
    for i, text_info in enumerate(text_data):
        # Get a preview of the text for display
        text_preview = text_info['text'][:200] + "..." if len(text_info['text']) > 200 else text_info['text']
        
        # Build image path - look for index.png in the onion's images folder
        onion_addr = text_info['onion_address']
        image_path = f"{onion_addr}/images/index.png" if onion_addr else ""

        text_vis_data.append({
            'x': float(coords_scaled[i][0]),
            'y': float(coords_scaled[i][1]),
            'title': text_info['title'],
            'filename': text_info['filename'],
            'text_preview': text_preview,
            'onion_address': text_info['onion_address'],
            'source_type': text_info.get('source_type', 'unknown'),
            'image': image_path
        })

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>t-SNE Text Clustering Visualization</title>
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
            max-width: 400px;
            z-index: 100;
        }}
        .text-node {{
            cursor: pointer;
            transition: all 0.2s;
        }}
        .text-node:hover {{
            stroke: #ff6b6b;
            stroke-width: 2px;
            z-index: 10;
        }}
        #title {{
            position: absolute;
            top: 10px;
            left: 10px;
            color: black;
            font-size: 18px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.8);
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
        }}
        #legend {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.9);
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid #ddd;
            font-size: 13px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 5px;
        }}
        .legend-color {{
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 8px;
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
        #info {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            color: black;
            font-size: 12px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.8);
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div id="title">t-SNE Text Clustering Visualization</div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()">+</button>
        <button class="control-btn" onclick="zoomOut()">-</button>
        <button class="control-btn" onclick="resetView()">↺</button>
    </div>
    <div id="info">Displaying {len(text_vis_data)} text documents clustered by semantic similarity</div>
    <div id="legend">
        <div class="legend-item">
            <div class="legend-color" style="background-color: #3498db;"></div>
            <span>Website Title</span>
        </div>
    </div>
    <div id="tooltip"></div>
    <script>
        // Text data
        const textData = {json.dumps(text_vis_data)};

        // Chart dimensions
        const width = window.innerWidth;
        const height = window.innerHeight;

        // Create the container SVG
        const svg = d3.select("body")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .attr("style", "max-width: 100%; height: 100vh;");

        // Add zoom functionality
        const zoom = d3.zoom()
            .scaleExtent([0.05, 10])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});
        svg.call(zoom);

        // Create zoom functions
        function zoomIn() {{
            svg.transition().duration(750).call(zoom.scaleBy, 1.5);
        }}

        function zoomOut() {{
            svg.transition().duration(750).call(zoom.scaleBy, 0.5);
        }}

        function resetView() {{
            svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity);
        }}

        // Create a group for zooming
        const g = svg.append("g");

        // Calculate bounds to fit all nodes in view initially
        const allX = textData.map(d => d.x);
        const allY = textData.map(d => d.y);
        const minX = Math.min(...allX), maxX = Math.max(...allX);
        const minY = Math.min(...allY), maxY = Math.max(...allY);
        const rangeX = maxX - minX || 1000;
        const rangeY = maxY - minY || 1000;
        
        // Calculate initial scale to fit all nodes
        const initialScale = Math.min(
            (width * 0.8) / rangeX,
            (height * 0.8) / rangeY,
            1  // Don't zoom in, only out
        );
        
        // Calculate initial translate to center the view
        const initialX = (width / 2) - ((minX + maxX) / 2) * initialScale;
        const initialY = (height / 2) - ((minY + maxY) / 2) * initialScale;

        // Apply initial transform
        svg.call(zoom.transform, d3.zoomIdentity.translate(initialX, initialY).scale(initialScale));

        // Add circles to represent text documents
        const textNodes = g.selectAll(".text-node")
            .data(textData)
            .enter()
            .append("circle")
            .attr("class", "text-node")
            .attr("cx", d => d.x)
            .attr("cy", d => d.y)
            .attr("r", 8)
            .attr("fill", "#3498db")
            .attr("stroke", "#2980b9")
            .attr("stroke-width", 1.5)
            .on("mouseover", function(event, d) {{
                tooltip.transition()
                    .duration(200)
                    .style("opacity", .95);
                let html = `<div style="font-weight:bold;margin-bottom:8px;">${{d.title}}</div>`;
                if (d.image) {{
                    html += `<img src="${{d.image}}" style="width:100%;max-width:200px;height:auto;border-radius:4px;margin-bottom:8px;" onerror="this.style.display='none'">`;
                }}
                html += `<div style="font-size:12px;color:#666;">${{d.onion_address}}</div>`;
                tooltip.html(html)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            }})
            .on("mouseout", function(d) {{
                tooltip.transition()
                    .duration(500)
                    .style("opacity", 0);
            }})
            .on("click", function(event, d) {{
                // Create a modal or new window to show full text
                const modal = document.createElement('div');
                modal.style.position = 'fixed';
                modal.style.top = '50%';
                modal.style.left = '50%';
                modal.style.transform = 'translate(-50%, -50%)';
                modal.style.width = '80%';
                modal.style.height = '80%';
                modal.style.background = 'white';
                modal.style.padding = '20px';
                modal.style.border = '1px solid #ccc';
                modal.style.borderRadius = '8px';
                modal.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
                modal.style.overflow = 'auto';
                modal.style.zIndex = '1000';
                modal.style.display = 'flex';
                modal.style.flexDirection = 'column';

                const title = document.createElement('h3');
                title.textContent = d.title;
                title.style.marginTop = '0';

                const sourceType = document.createElement('div');
                sourceType.textContent = 'Source Type: ' + d.source_type;
                sourceType.style.fontWeight = 'bold';
                sourceType.style.marginBottom = '5px';

                const onionAddr = document.createElement('div');
                onionAddr.textContent = 'Onion: ' + d.onion_address;
                onionAddr.style.fontWeight = 'bold';
                onionAddr.style.marginBottom = '10px';

                const textContent = document.createElement('pre');
                textContent.textContent = d.text_preview.replace('...', '');
                textContent.style.whiteSpace = 'pre-wrap';
                textContent.style.wordWrap = 'break-word';
                textContent.style.flexGrow = '1';
                textContent.style.overflow = 'auto';
                textContent.style.backgroundColor = '#f9f9f9';
                textContent.style.padding = '10px';
                textContent.style.borderRadius = '4px';

                const closeButton = document.createElement('button');
                closeButton.textContent = 'Close';
                closeButton.style.alignSelf = 'flex-end';
                closeButton.style.marginTop = '10px';
                closeButton.style.padding = '8px 16px';
                closeButton.onclick = function() {{
                    document.body.removeChild(modal);
                }};

                modal.appendChild(title);
                modal.appendChild(sourceType);
                modal.appendChild(onionAddr);
                modal.appendChild(textContent);
                modal.appendChild(closeButton);

                document.body.appendChild(modal);
            }});

        // Create tooltip
        const tooltip = d3.select("#tooltip");

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

    # Write the HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"t-SNE text visualization created at {output_file}")


def find_all_website_title_files(scraped_data_dir):
    """
    Find all website_identity/index_title.txt files in the scraped data directory.
    """
    title_paths = []
    for root, dirs, files in os.walk(scraped_data_dir):
        if 'website_identity' in root and 'index_title.txt' in files:
            title_paths.append(os.path.join(root, 'index_title.txt'))
    return title_paths


def extract_text_from_website_title(title_file_path):
    """
    Extract title text from website_identity/index_title.txt.
    Format: [TITLE] -> http://...onion
    Returns just "TITLE" without brackets.
    """
    try:
        with open(title_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        titles = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('[') and ']' in line:
                end_idx = line.find(']')
                title = line[1:end_idx].strip()
                if title:
                    titles.append(title)
        return ' '.join(titles)
    except Exception as e:
        print(f"Error reading {title_file_path}: {str(e)}")
        return ""


def main():
    parser = argparse.ArgumentParser(description='Create t-SNE clustering visualization for onion site website titles')

    script_dir = Path(__file__).parent
    default_input = script_dir / "../scraped_data"
    default_output = script_dir / "../scraped_data/tsne_text_clusters.html"

    parser.add_argument('--input-dir', default=str(default_input),
                        help='Directory containing scraped data')
    parser.add_argument('--output', default=str(default_output),
                        help='Output HTML file path')
    parser.add_argument('--sample-size', type=int, default=None,
                        help='Number of documents to sample randomly (default: use all)')
    parser.add_argument('--perplexity', type=int, default=30,
                        help='t-SNE perplexity parameter (default: 30)')
    parser.add_argument('--iterations', type=int, default=1000,
                        help='t-SNE iterations (default: 1000)')
    parser.add_argument('--model', default='all-MiniLM-L6-v2',
                        help='Sentence transformer model (default: all-MiniLM-L6-v2)')

    args = parser.parse_args()

    # Find all website title files
    print(f"Searching for website title files in {args.input_dir}...")
    website_title_paths = find_all_website_title_files(args.input_dir)

    if not website_title_paths:
        print(f"No website title files found in {args.input_dir}/website_identity/")
        return

    print(f"Found {len(website_title_paths)} website title files")

    # Sample if requested
    if args.sample_size and args.sample_size < len(website_title_paths):
        print(f"Sampling {args.sample_size} website title documents randomly...")
        indices = np.random.choice(len(website_title_paths), args.sample_size, replace=False)
        website_title_paths = [website_title_paths[i] for i in indices]

    print(f"Processing {len(website_title_paths)} website title documents for t-SNE clustering...")

    # Extract text content from website title files
    text_data = []
    for i, title_path in enumerate(website_title_paths):
        # Extract onion address from the path
        path_parts = title_path.split('/')
        onion_address = ''
        for part in path_parts:
            if ONION_PATTERN.match(part):
                onion_address = part
                break

        # Extract text from website title file
        text_content = extract_text_from_website_title(title_path)
        if text_content.strip():
            website_title = text_content.strip()

            text_data.append({
                'text': text_content,
                'title': website_title,
                'filename': os.path.basename(title_path),
                'onion_address': onion_address,
                'path': title_path,
                'source_type': 'website_title'
            })

        if (i + 1) % 10 == 0:
            print(f"Processed {i + 1}/{len(website_title_paths)} website title files")

    if not text_data:
        print("No valid text content could be extracted")
        return

    print(f"Extracted text from {len(text_data)} documents total")

    # Extract embeddings from texts
    texts = [item['text'] for item in text_data]
    embeddings = extract_text_embeddings(texts, model_name=args.model)

    if embeddings.shape[0] == 0:
        print("No valid embeddings could be generated")
        return

    # Apply t-SNE
    coords = apply_tsne(embeddings, perplexity=args.perplexity, n_iterations=args.iterations)

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    os.makedirs(output_dir, exist_ok=True)

    # Generate D3 visualization
    generate_d3_visualization(coords, text_data, args.output)

    print(f"t-SNE text clustering visualization complete!")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()