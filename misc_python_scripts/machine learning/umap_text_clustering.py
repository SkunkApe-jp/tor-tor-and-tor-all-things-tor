#!/usr/bin/env python3
"""
UMAP Text Clustering Visualization

Creates a visualization that groups similar onion site texts using UMAP dimensionality reduction.
"""

import os
import json
import numpy as np
from sklearn.preprocessing import StandardScaler
from sentence_transformers import SentenceTransformer
import argparse
from pathlib import Path
import umap
import re


def extract_text_from_html(html_file_path):
    """
    Extract text content from HTML file.
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Remove HTML tags and extract text
        # Remove script and style elements
        content = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', content, flags=re.DOTALL | re.IGNORECASE)
        # Remove HTML comments
        content = re.sub(r'<!--.*?-->', ' ', content, flags=re.DOTALL)
        # Remove HTML tags
        content = re.sub(r'<[^>]+>', ' ', content)
        # Replace multiple whitespaces with single space
        content = re.sub(r'\s+', ' ', content)
        # Strip leading/trailing whitespace
        content = content.strip()

        return content
    except Exception as e:
        print(f"Error reading {html_file_path}: {str(e)}")
        return ""


def extract_text_from_website_title(title_file_path):
    """
    Extract only the title text between brackets from website_identity/index_title.txt.
    Format: [[TITLE]] -> http://...onion
    Returns just "TITLE" without brackets.
    """
    try:
        with open(title_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        titles = []
        for line in content.split('\n'):
            line = line.strip()
            # Extract text between [[ and ]]
            if line.startswith('[[') and ']]' in line:
                start = 2
                end_idx = line.find(']]')
                title = line[start:end_idx].strip()
                if title:
                    titles.append(title)
            # Also handle single bracket format [TITLE]
            elif line.startswith('[') and ']' in line:
                start = 1
                end_idx = line.find(']')
                title = line[start:end_idx].strip()
                if title:
                    titles.append(title)
        return ' '.join(titles)
    except Exception as e:
        print(f"Error reading {title_file_path}: {str(e)}")
        return ""


def extract_text_from_titles(title_file_path):
    """
    Extract text content from title files, filtering out generic navigation titles.
    Handles both discovered_links/*_titles.txt and website_identity/index_title.txt formats.
    """
    try:
        with open(title_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()

        # Check if this is a website_identity/index_title.txt file
        if 'website_identity' in title_file_path:
            # Format: [[TITLE]] -> http://...onion or just text
            titles = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('[[') and ']]' in line:
                    # Extract title between double brackets
                    end_idx = line.find(']]')
                    title = line[2:end_idx].strip()
                    if not is_generic_navigation_title(title):
                        titles.append(title)
                elif line and not line.startswith('->'):
                    # Plain text title line
                    if not is_generic_navigation_title(line):
                        titles.append(line)
            return ' '.join(titles)
        else:
            # Format: [Title] -> http://abc...onion (discovered_links format)
            lines = content.split('\n')
            titles = []
            for line in lines:
                line = line.strip()
                if line.startswith('[') and '] -> ' in line:
                    # Extract the title part between brackets
                    title_part = line[1:]  # Remove first bracket
                    end_bracket_idx = title_part.find(']')
                    if end_bracket_idx != -1:
                        title = title_part[:end_bracket_idx]
                        # Filter out generic navigation titles
                        if not is_generic_navigation_title(title):
                            titles.append(title)

            # Combine all non-generic titles into a single text
            combined_text = ' '.join(titles)
            return combined_text
    except Exception as e:
        print(f"Error reading {title_file_path}: {str(e)}")
        return ""


def is_generic_navigation_title(title):
    """
    Check if a title is a generic navigation title that should be filtered out.
    """
    generic_terms = {
        'about', 'about us', 'contact', 'contact us', 'home', 'index', 'main', 
        'services', 'products', 'links', 'sitemap', 'faq', 'help', 'support',
        'login', 'register', 'sign in', 'sign up', 'account', 'profile',
        'news', 'blog', 'articles', 'posts', 'categories', 'search',
        'terms', 'privacy', 'policy', 'legal', 'disclaimer', 'copyright',
        'menu', 'navigation', 'more', 'details', 'read more', 'learn more',
        'shop', 'store', 'cart', 'checkout', 'orders', 'wishlist',
        'admin', 'dashboard', 'settings', 'preferences', 'logout',
        'previous', 'next', 'back', 'forward', 'top', 'bottom', 'up', 'down',
        'register now', 'sign up now', 'click here', 'here', 'this page',
        'information', 'page', 'view', 'go', 'all', 'other', 'item', 'items'
    }
    
    normalized_title = title.lower().strip()
    # Remove common punctuation and extra spaces
    import re
    normalized_title = re.sub(r'[^\w\s]', ' ', normalized_title)
    normalized_title = ' '.join(normalized_title.split())
    
    # Check if the entire title matches a generic term
    if normalized_title in generic_terms:
        return True
    
    # Check if ALL words in the title are generic (like "Contact Information" where both words are generic)
    words = normalized_title.split()
    if len(words) > 1:
        all_words_generic = all(word in generic_terms for word in words)
        if all_words_generic:
            return True
    
    return False


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
            # Generate embedding for the text
            embedding = model.encode([text])[0]
            embeddings.append(embedding)

            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(texts)} texts")

        except Exception as e:
            print(f"Error processing text: {str(e)}")
            # Add a zero vector if there's an error
            embeddings.append(np.zeros(model.get_sentence_embedding_dimension()))
            continue

    return np.array(embeddings)


def apply_umap(features, n_neighbors=15, min_dist=0.1, n_components=2):
    """
    Apply UMAP to reduce features to 2D coordinates.
    """
    print(f"Applying UMAP with {features.shape[0]} samples...")

    # If we have fewer than 3 samples, UMAP won't work properly, so return simple coordinates
    if features.shape[0] < 3:
        print("Too few samples for UMAP, using simple layout...")
        coords = np.zeros((features.shape[0], 2))
        for i in range(features.shape[0]):
            coords[i][0] = 500 + i * 150  # Space them out horizontally
            coords[i][1] = 500
        return coords

    # Standardize features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # Adjust n_neighbors if it's too large for the dataset
    adjusted_n_neighbors = min(n_neighbors, features.shape[0] - 1)

    # Apply UMAP
    reducer = umap.UMAP(
        n_neighbors=adjusted_n_neighbors,
        min_dist=min_dist,
        n_components=n_components,
        random_state=42,
        verbose=False
    )
    umap_coords = reducer.fit_transform(features_scaled)

    return umap_coords


def find_all_html_files(scraped_data_dir):
    """
    Find all HTML files in the scraped data directory.
    """
    html_paths = []
    for root, dirs, files in os.walk(scraped_data_dir):
        for file in files:
            if file.lower().endswith('.html'):
                html_paths.append(os.path.join(root, file))
    return html_paths


def find_all_title_files(scraped_data_dir):
    """
    Find all title files in the discovered_links and website_identity subdirectories.
    """
    title_paths = []
    for root, dirs, files in os.walk(scraped_data_dir):
        # Look in discovered_links directories for *_titles.txt
        if os.path.basename(root) == 'discovered_links':
            for file in files:
                if file.lower().endswith('_titles.txt'):
                    title_paths.append(os.path.join(root, file))
        # Look in website_identity directories for index_title.txt
        if os.path.basename(root) == 'website_identity':
            for file in files:
                if file.lower() == 'index_title.txt':
                    title_paths.append(os.path.join(root, file))
    return title_paths


def generate_d3_visualization(coords, text_data, output_file):
    """
    Generate HTML with D3 visualization for UMAP clustered text data.
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
    <title>UMAP Text Clustering Visualization</title>
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
    <div id="title">UMAP Text Clustering Visualization</div>
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

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    os.makedirs(output_dir, exist_ok=True)

    # Write the HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"UMAP text visualization created at {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Create UMAP clustering visualization for onion site text content')
    
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    default_input = script_dir / "../scraped_data"
    default_output = script_dir / "../scraped_data/umap_text_clusters.html"
    
    parser.add_argument('--input-dir', default=str(default_input),
                        help='Directory containing scraped data with HTML files')
    parser.add_argument('--output', default=str(default_output),
                        help='Output HTML file path')
    parser.add_argument('--sample-size', type=int, default=None,
                        help='Number of documents to sample randomly (default: use all documents)')
    parser.add_argument('--n-neighbors', type=int, default=15,
                        help='UMAP n_neighbors parameter (default: 15)')
    parser.add_argument('--min-dist', type=float, default=0.1,
                        help='UMAP min_dist parameter (default: 0.1)')
    parser.add_argument('--model', default='all-MiniLM-L6-v2',
                        help='Sentence transformer model to use (default: all-MiniLM-L6-v2)')
    parser.add_argument('--source', choices=['html', 'titles', 'website_titles', 'both'], default='website_titles',
                        help='Source of text content: html files, title files, website titles (website_identity/index_title.txt), or both')

    args = parser.parse_args()

    text_data = []
    
    # Process HTML files if requested
    if args.source in ['html', 'both']:
        print(f"Searching for HTML files in {args.input_dir}...")
        all_html_paths = find_all_html_files(args.input_dir)
        
        if all_html_paths:
            print(f"Found {len(all_html_paths)} HTML files")
            
            # Sample documents if requested
            if args.sample_size and args.sample_size < len(all_html_paths):
                print(f"Sampling {args.sample_size} HTML documents randomly...")
                indices = np.random.choice(len(all_html_paths), args.sample_size, replace=False)
                html_paths = [all_html_paths[i] for i in indices]
            else:
                html_paths = all_html_paths

            print(f"Processing {len(html_paths)} HTML documents for UMAP clustering...")

            # Extract text content from HTML files
            for i, html_path in enumerate(html_paths):
                # Extract onion address from the path
                path_parts = html_path.split('/')
                onion_address = ''
                for part in path_parts:
                    if len(part) >= 50 and all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in part):
                        onion_address = part
                        break

                # Extract text from HTML
                text_content = extract_text_from_html(html_path)
                if text_content.strip():  # Only add if text is not empty
                    # Extract title from filename or path
                    title = os.path.basename(html_path)
                    if title == 'index.html':
                        # Try to get title from parent directory name
                        parent_dir = os.path.basename(os.path.dirname(html_path))
                        if parent_dir != 'htmls':
                            title = parent_dir

                    text_data.append({
                        'text': text_content,
                        'title': title,
                        'filename': os.path.basename(html_path),
                        'onion_address': onion_address,
                        'path': html_path,
                        'source_type': 'html'
                    })

                if (i + 1) % 10 == 0:
                    print(f"Processed {i + 1}/{len(html_paths)} HTML files")
        else:
            print(f"No HTML files found in {args.input_dir}")

    # Process title files if requested
    if args.source in ['titles', 'both']:
        print(f"Searching for title files in {args.input_dir}...")
        all_title_paths = find_all_title_files(args.input_dir)
        
        if all_title_paths:
            print(f"Found {len(all_title_paths)} title files")
            
            # Adjust sample size if needed
            if args.sample_size and args.sample_size < len(all_title_paths):
                print(f"Sampling {args.sample_size} title documents randomly...")
                indices = np.random.choice(len(all_title_paths), args.sample_size, replace=False)
                title_paths = [all_title_paths[i] for i in indices]
            else:
                title_paths = all_title_paths

            print(f"Processing {len(title_paths)} title documents for UMAP clustering...")

            # Extract text content from title files
            for i, title_path in enumerate(title_paths):
                # Extract onion address from the path
                path_parts = title_path.split('/')
                onion_address = ''
                for j, part in enumerate(path_parts):
                    # Look for the onion address in the parent directory of discovered_links
                    if (j > 0 and part == 'discovered_links' and 
                        len(path_parts[j-1]) >= 50 and 
                        all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in path_parts[j-1])):
                        onion_address = path_parts[j-1]
                        break

                # Extract text from title file
                text_content = extract_text_from_titles(title_path)
                if text_content.strip():  # Only add if text is not empty after filtering
                    # Extract title from filename
                    title = os.path.basename(title_path)
                    
                    text_data.append({
                        'text': text_content,
                        'title': title,
                        'filename': os.path.basename(title_path),
                        'onion_address': onion_address,
                        'path': title_path,
                        'source_type': 'titles'
                    })
                else:
                    print(f"  No meaningful content found in {title_path} after filtering generic titles")

                if (i + 1) % 10 == 0:
                    print(f"Processed {i + 1}/{len(title_paths)} title files")
        else:
            print(f"No title files found in {args.input_dir}/discovered_links/")

    # Process website title files (website_identity/index_title.txt)
    if args.source == 'website_titles':
        # Clear text_data to only include website titles
        text_data = []
        print(f"Searching for website title files in {args.input_dir}...")
        website_title_paths = []
        for root, dirs, files in os.walk(args.input_dir):
            if 'website_identity' in root and 'index_title.txt' in files:
                website_title_paths.append(os.path.join(root, 'index_title.txt'))

        if website_title_paths:
            print(f"Found {len(website_title_paths)} website title files")

            # Adjust sample size if needed
            if args.sample_size and args.sample_size < len(website_title_paths):
                print(f"Sampling {args.sample_size} website title documents randomly...")
                indices = np.random.choice(len(website_title_paths), args.sample_size, replace=False)
                website_title_paths = [website_title_paths[i] for i in indices]

            print(f"Processing {len(website_title_paths)} website title documents for UMAP clustering...")

            # Extract text content from website title files
            for i, title_path in enumerate(website_title_paths):
                # Extract onion address from the path
                path_parts = title_path.split('/')
                onion_address = ''
                for part in path_parts:
                    if len(part) >= 50 and all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in part):
                        onion_address = part
                        break

                # Extract text from website title file
                text_content = extract_text_from_website_title(title_path)
                if text_content.strip():
                    # Use the actual website title content, not filename
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
        else:
            print(f"No website title files found in {args.input_dir}/website_identity/")

    if not text_data:
        print("No valid text content could be extracted from any source")
        return

    print(f"Extracted text from {len(text_data)} documents total")

    # Extract embeddings from texts
    texts = [item['text'] for item in text_data]
    embeddings = extract_text_embeddings(texts, model_name=args.model)

    if embeddings.shape[0] == 0:
        print("No valid embeddings could be generated")
        return

    # Apply UMAP
    coords = apply_umap(embeddings, n_neighbors=args.n_neighbors, min_dist=args.min_dist)

    # Generate D3 visualization
    generate_d3_visualization(coords, text_data, args.output)

    print(f"UMAP text clustering visualization complete!")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()