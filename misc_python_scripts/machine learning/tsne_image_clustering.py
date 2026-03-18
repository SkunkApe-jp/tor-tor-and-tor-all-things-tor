#!/usr/bin/env python3
"""
t-SNE Image Clustering Visualization

Creates a visualization that groups similar onion site images using t-SNE dimensionality reduction.
"""

import os
import json
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.applications.resnet50 import preprocess_input
from tensorflow.keras.preprocessing import image as keras_image
import argparse
from pathlib import Path


def extract_features_with_resnet(image_paths, target_size=(224, 224)):
    """
    Extract features from images using a pre-trained ResNet50 model.
    """
    print(f"Loading ResNet50 model...")
    model = ResNet50(weights='imagenet', include_top=False, pooling='avg')
    
    features = []
    valid_paths = []
    
    print(f"Extracting features from {len(image_paths)} images...")
    for i, img_path in enumerate(image_paths):
        try:
            # Load and preprocess the image
            img = keras_image.load_img(img_path, target_size=target_size)
            img_array = keras_image.img_to_array(img)
            img_array = np.expand_dims(img_array, axis=0)
            img_array = preprocess_input(img_array)
            
            # Extract features
            feature = model.predict(img_array, verbose=0)
            features.append(feature.flatten())
            valid_paths.append(img_path)
            
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(image_paths)} images")
                
        except Exception as e:
            print(f"Error processing {img_path}: {str(e)}")
            continue
    
    return np.array(features), valid_paths


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


def generate_d3_visualization(coords, image_paths, output_file):
    """
    Generate HTML with D3 visualization for t-SNE clustered images.
    """
    # Normalize coordinates to 0-1 range
    coords_min = coords.min(axis=0)
    coords_max = coords.max(axis=0)
    coords_normalized = (coords - coords_min) / (coords_max - coords_min)
    
    # Scale to a larger canvas (e.g., 1000x1000)
    canvas_size = 1000
    coords_scaled = coords_normalized * canvas_size
    
    # Prepare image data for the visualization
    image_data = []
    for i, img_path in enumerate(image_paths):
        # Calculate relative path from output file location
        rel_path = os.path.relpath(img_path, os.path.dirname(output_file))
        
        # Get original image dimensions to maintain aspect ratio
        try:
            with Image.open(img_path) as img:
                orig_width, orig_height = img.size
                # Scale the image to fit within a max size while maintaining aspect ratio
                max_dimension = 100  # Maximum width or height
                if orig_width > orig_height:
                    width = max_dimension
                    height = (orig_height * max_dimension) / orig_width
                else:
                    height = max_dimension
                    width = (orig_width * max_dimension) / orig_height
        except:
            # Fallback to default size if image can't be opened
            width = 50
            height = 50
        
        image_data.append({
            'x': float(coords_scaled[i][0]),
            'y': float(coords_scaled[i][1]),
            'src': rel_path.replace("\\", "/"),  # Normalize path separators
            'filename': os.path.basename(img_path),
            'width': width,
            'height': height
        })
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>t-SNE Image Clustering Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            margin: 0;
            overflow: hidden;
            background-color: #f0f0f0;
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
            max-width: 300px;
            z-index: 100;
        }}
        .image-node {{
            cursor: pointer;
            border: 2px solid transparent;
            transition: border 0.2s;
        }}
        .image-node:hover {{
            border: 2px solid #ff6b6b;
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
    <div id="title">t-SNE Image Clustering Visualization</div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()">+</button>
        <button class="control-btn" onclick="zoomOut()">-</button>
        <button class="control-btn" onclick="resetView()">↺</button>
    </div>
    <div id="info">Displaying {{len(image_data)}} images clustered by visual similarity</div>
    <div id="tooltip"></div>
    <script>
        // Image data
        const imageData = {json.dumps(image_data)};

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
            .scaleExtent([0.1, 10])
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

        // Create tooltip
        const tooltip = d3.select("#tooltip");

        // Add images to the visualization
        const imageNodes = g.selectAll(".image-node")
            .data(imageData)
            .enter()
            .append("image")
            .attr("class", "image-node")
            .attr("x", d => d.x - d.width/2)  // Center the image at the coordinate
            .attr("y", d => d.y - d.height/2)
            .attr("width", d => d.width)
            .attr("height", d => d.height)
            .attr("xlink:href", d => d.src)
            .attr("clip-path", "circle()")
            .on("mouseover", function(event, d) {{
                tooltip.transition()
                    .duration(200)
                    .style("opacity", .95);
                tooltip.html(`<div><strong>${{d.filename}}</strong></div><img src="${{d.src}}" style="max-width: 200px; max-height: 150px; margin-top: 5px; border: 1px solid #ddd;" onerror="this.parentNode.innerHTML+='<div style=\\'color:red; font-size:12px;\\'>Image not available</div>';">`)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            }})
            .on("mouseout", function(d) {{
                tooltip.transition()
                    .duration(500)
                    .style("opacity", 0);
            }})
            .on("click", function(event, d) {{
                // Open the image in a new tab when clicked
                window.open(d.src, '_blank');
            }});

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

    print(f"t-SNE visualization created at {output_file}")


def find_all_images(scraped_data_dir):
    """
    Find all PNG images in the scraped data directory.
    """
    image_paths = []
    for root, dirs, files in os.walk(scraped_data_dir):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_paths.append(os.path.join(root, file))
    return image_paths


def main():
    parser = argparse.ArgumentParser(description='Create t-SNE clustering visualization for onion site images')
    parser.add_argument('--input-dir', default='../scraped_data', 
                        help='Directory containing scraped data with images (default: ../scraped_data)')
    parser.add_argument('--output', default='../scraped_data/tsne_image_clusters.html',
                        help='Output HTML file path (default: ../scraped_data/tsne_image_clusters.html)')
    parser.add_argument('--sample-size', type=int, default=None,
                        help='Number of images to sample randomly (default: use all images)')
    parser.add_argument('--perplexity', type=int, default=30,
                        help='t-SNE perplexity parameter (default: 30)')
    parser.add_argument('--iterations', type=int, default=1000,
                        help='t-SNE iterations (default: 1000)')
    
    args = parser.parse_args()
    
    # Find all images in the scraped data directory
    print(f"Searching for images in {args.input_dir}...")
    all_image_paths = find_all_images(args.input_dir)
    
    if not all_image_paths:
        print(f"No images found in {args.input_dir}")
        return
    
    print(f"Found {len(all_image_paths)} images")
    
    # Sample images if requested
    if args.sample_size and args.sample_size < len(all_image_paths):
        print(f"Sampling {args.sample_size} images randomly...")
        indices = np.random.choice(len(all_image_paths), args.sample_size, replace=False)
        image_paths = [all_image_paths[i] for i in indices]
    else:
        image_paths = all_image_paths
    
    print(f"Processing {len(image_paths)} images for t-SNE clustering...")
    
    # Extract features from images
    features, valid_paths = extract_features_with_resnet(image_paths)
    
    if len(valid_paths) == 0:
        print("No valid images could be processed")
        return
    
    if len(valid_paths) != len(image_paths):
        print(f"Warning: Only {len(valid_paths)} out of {len(image_paths)} images could be processed")
    
    # Apply t-SNE
    coords = apply_tsne(features, perplexity=args.perplexity, n_iterations=args.iterations)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate D3 visualization
    generate_d3_visualization(coords, valid_paths, args.output)
    
    print(f"t-SNE clustering visualization complete!")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()
