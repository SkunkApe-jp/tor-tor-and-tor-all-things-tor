#!/usr/bin/env python3
"""
UMAP Index Image Clustering Visualization

Creates a visualization that groups onion site index images using UMAP dimensionality reduction.
"""

import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Force CPU-only mode

import json
import re
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.applications.resnet50 import preprocess_input
from tensorflow.keras.preprocessing import image as keras_image
import argparse
from pathlib import Path

# Pre-compiled regex for onion address validation (v2: 16 chars, v3: 56 chars, or vanity: <=56 chars)
ONION_PATTERN = re.compile(r'^[a-z2-7]{1,56}$')
import umap


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
        verbose=True
    )
    umap_coords = reducer.fit_transform(features_scaled)
    
    return umap_coords


def find_root_images(scraped_data_dir):
    """
    Find root images (index images) in each onion directory.
    """
    image_paths = []

    # Look for onion directories in the scraped_data_dir
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)

        # Check if it's a directory that looks like an onion address (<=56 chars with valid base32)
        if os.path.isdir(item_path) and ONION_PATTERN.match(item):
            # Look for images subdirectory
            images_dir = os.path.join(item_path, 'images')
            if os.path.exists(images_dir):
                # Look for index images (index.png, index.jpg, or [onion_address].png)
                for file in os.listdir(images_dir):
                    if file.lower() in ['index.png', 'index.jpg', 'index.jpeg'] or file.lower() == f"{item}.png":
                        img_path = os.path.join(images_dir, file)
                        image_paths.append(img_path)
    
    return image_paths


def generate_d3_visualization(coords, image_paths, output_file):
    """
    Generate HTML with D3 visualization for UMAP clustered index images.
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
    <title>UMAP Index Image Clustering Visualization</title>
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
            max-width: 300px;
            z-index: 100;
        }}
        .image-node {{
            cursor: pointer;
            transition: opacity 0.2s;
        }}
        .image-node:hover {{
            opacity: 0.8;
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
    <div id="title">UMAP Index Image Clustering Visualization</div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()">+</button>
        <button class="control-btn" onclick="zoomOut()">-</button>
        <button class="control-btn" onclick="resetView()">↺</button>
    </div>
    <div id="info">Displaying {len(image_data)} root images clustered by visual similarity</div>
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
                // Extract the onion address from the image path
                const pathParts = d.src.split('/');
                let onionAddress = '';

                // Look for the onion address in the path (1-56 character base32 string)
                for (let i = 0; i < pathParts.length; i++) {{
                    if (pathParts[i].length >= 1 && pathParts[i].length <= 56 && /^[a-z2-7]+$/.test(pathParts[i])) {{
                        onionAddress = pathParts[i];
                        break;
                    }}
                }}
                
                if (onionAddress) {{
                    const onionUrl = `http://${{onionAddress}}.onion`;
                    
                    // Copy the URL to clipboard
                    navigator.clipboard.writeText(onionUrl).then(function() {{
                        console.log('Copied to clipboard: ' + onionUrl);
                        
                        // Show a temporary notification
                        const notification = document.createElement('div');
                        notification.textContent = 'Copied to clipboard: ' + onionUrl;
                        notification.style.position = 'fixed';
                        notification.style.bottom = '20px';
                        notification.style.left = '50%';
                        notification.style.transform = 'translateX(-50%)';
                        notification.style.backgroundColor = '#4CAF50';
                        notification.style.color = 'white';
                        notification.style.padding = '10px 20px';
                        notification.style.borderRadius = '5px';
                        notification.style.zIndex = '1000';
                        notification.style.fontSize = '14px';
                        document.body.appendChild(notification);
                        
                        // Remove the notification after 3 seconds
                        setTimeout(function() {{
                            document.body.removeChild(notification);
                        }}, 3000);
                    }}).catch(function(err) {{
                        console.error('Could not copy text: ', err);
                    }});
                }}
                
                // Also open the image in a new tab when clicked
                window.open(d.src, '_blank');
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

    print(f"UMAP visualization created at {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Create UMAP clustering visualization for onion site index images')
    
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    default_input = script_dir / "../scraped_data"
    default_output = script_dir / "../scraped_data/umap_index_clusters.html"
    
    parser.add_argument('--input-dir', default=str(default_input),
                        help='Directory containing scraped data with images')
    parser.add_argument('--output', default=str(default_output),
                        help='Output HTML file path')
    parser.add_argument('--n-neighbors', type=int, default=15,
                        help='UMAP n_neighbors parameter (default: 15)')
    parser.add_argument('--min-dist', type=float, default=0.1,
                        help='UMAP min_dist parameter (default: 0.1)')

    args = parser.parse_args()
    
    # Find all root images in the images subdirectories of onion directories
    print(f"Searching for root images in {args.input_dir}...")
    image_paths = find_root_images(args.input_dir)
    
    if not image_paths:
        print(f"No root images found in {args.input_dir}/[onion_address]/images/")
        return
    
    print(f"Found {len(image_paths)} root images")
    
    # Extract features from images
    features, valid_paths = extract_features_with_resnet(image_paths)
    
    if len(valid_paths) == 0:
        print("No valid images could be processed")
        return
    
    if len(valid_paths) != len(image_paths):
        print(f"Warning: Only {len(valid_paths)} out of {len(image_paths)} images could be processed")
    
    # Apply UMAP
    coords = apply_umap(features, n_neighbors=args.n_neighbors, min_dist=args.min_dist)
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate D3 visualization
    generate_d3_visualization(coords, valid_paths, args.output)
    
    print(f"UMAP clustering visualization complete!")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()