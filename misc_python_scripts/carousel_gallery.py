#!/usr/bin/env python3
"""
Full-Screen Carousel Gallery with Glassmorphism

Creates a full-screen carousel gallery that displays images from scraped onion sites
with glassmorphism effects and minimal design.
"""

import os
import json
import re
import argparse
from pathlib import Path

# Pre-compiled regex for onion address validation (v2: 16 chars, v3: 56 chars, or vanity: <=56 chars)
ONION_PATTERN = re.compile(r'^[a-z2-7]{1,56}$')


def find_images_in_scraped_data(scraped_data_dir):
    """Find all image files in the images subdirectory of each onion directory."""
    image_paths = []

    # Look for onion directories in the scraped_data_dir
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)

        # Check if it's a directory that looks like an onion address (<=56 chars with valid base32)
        if os.path.isdir(item_path) and ONION_PATTERN.match(item):
            # Look for an images subdirectory
            img_dir = os.path.join(item_path, 'images')
            if os.path.exists(img_dir):
                # Find all image files in the images directory and subdirectories
                for root, dirs, files in os.walk(img_dir):
                    for file in files:
                        if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp')):
                            img_path = os.path.join(root, file)
                            image_paths.append(img_path)

    return image_paths


def generate_carousel_gallery(image_paths, scraped_data_dir, output_file):
    """Generate HTML carousel gallery with glassmorphism effects."""

    # Prepare data for gallery
    image_data = []
    for img_path in image_paths:
        # Calculate relative path from output file location
        rel_path = os.path.relpath(img_path, os.path.dirname(output_file))

        # Extract onion site and filename info
        path_parts = img_path.split('/')
        onion_site = None
        for part in path_parts:
            if ONION_PATTERN.match(part):
                onion_site = part
                break

        image_data.append({
            'path': rel_path.replace("\\", "/"),  # Normalize path separators
            'filename': os.path.basename(img_path),
            'onion_site': onion_site
        })

    # Convert image_data to JSON string for JavaScript
    import json
    image_data_json = json.dumps(image_data)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carousel Gallery</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --glass-bg: rgba(30, 30, 30, 0.3);
            --glass-border: rgba(255, 255, 255, 0.1);
            --text-primary: #f0f0f0;
            --text-secondary: #b0b0b0;
            --accent: #a0a0a0;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body, html {{
            height: 100%;
            width: 100%;
            overflow: hidden;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #000;
            color: var(--text-primary);
        }}
        
        .carousel-container {{
            position: relative;
            width: 100%;
            height: 100vh;
            overflow: hidden;
            background: #000;
        }}
        
        .carousel-slide {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            transition: opacity 0.8s ease-in-out;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        
        .carousel-slide.active {{
            opacity: 1;
        }}
        
        .slide-image {{
            max-width: 95%;
            max-height: 90%;
            object-fit: contain;
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }}
        
        .top-bar {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            z-index: 100;
            backdrop-filter: blur(10px);
            background: var(--glass-bg);
            border-bottom: 1px solid var(--glass-border);
        }}
        
        .image-info {{
            font-size: 1.1rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }}
        
        .onion-tag {{
            background: rgba(255, 255, 255, 0.1);
            color: var(--accent);
            padding: 0.3rem 0.8rem;
            border-radius: 20px;
            font-size: 0.7rem;
            font-family: monospace;
            word-break: break-word;
            max-width: 100%;
            display: inline-block;
            margin-left: 0.5rem;
            vertical-align: middle;
            line-height: 1.4;
        }}
        
        .nav-controls {{
            display: flex;
            gap: 1rem;
        }}
        
        .nav-btn {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 50%;
            width: 50px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            color: var(--text-primary);
            font-size: 1.2rem;
            transition: all 0.3s ease;
            backdrop-filter: blur(10px);
        }}
        
        .nav-btn:hover {{
            background: var(--glass-border);
            transform: scale(1.1);
        }}
        
        .counter {{
            position: fixed;
            bottom: 2rem;
            left: 50%;
            transform: translateX(-50%);
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 50px;
            padding: 0.8rem 1.5rem;
            font-size: 1rem;
            backdrop-filter: blur(10px);
            z-index: 100;
        }}
        
        .progress-container {{
            position: fixed;
            bottom: 0;
            left: 0;
            width: 100%;
            height: 5px;
            background: rgba(255, 255, 255, 0.1);
            z-index: 100;
        }}
        
        .progress-bar {{
            height: 100%;
            width: 0%;
            background: var(--accent);
            transition: width 0.1s linear;
        }}
        
        .fullscreen-indicator {{
            position: fixed;
            top: 1rem;
            right: 1rem;
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 8px;
            padding: 0.5rem;
            font-size: 0.9rem;
            backdrop-filter: blur(10px);
            z-index: 100;
            display: none;
        }}
        
        .keyboard-hint {{
            position: fixed;
            bottom: 6rem;
            left: 50%;
            transform: translateX(-50%);
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 8px;
            padding: 0.8rem 1.2rem;
            font-size: 0.9rem;
            backdrop-filter: blur(10px);
            z-index: 100;
            opacity: 0.7;
            transition: opacity 0.3s;
        }}
        
        .keyboard-hint:hover {{
            opacity: 1;
        }}
    </style>
</head>
<body>
    <div class="carousel-container" id="carousel">
        {"".join([
            f'''<div class="carousel-slide" id="slide-{i}">
                <img src="{item["path"]}" alt="{item["filename"]}" class="slide-image">
            </div>'''
            for i, item in enumerate(image_data)
        ])}
    </div>
    
    <div class="top-bar">
        <div class="image-info" id="imageInfo">
            {image_data[0]["filename"] if image_data else "No images"}
            {f'<span class="onion-tag">{image_data[0]["onion_site"]}.onion</span>' if image_data and image_data[0]["onion_site"] else ''}
        </div>
        <div class="nav-controls">
            <div class="nav-btn" id="prevBtn" title="Previous">
                <i class="fas fa-chevron-left"></i>
            </div>
            <div class="nav-btn" id="nextBtn" title="Next">
                <i class="fas fa-chevron-right"></i>
            </div>
        </div>
    </div>
    
    <div class="counter" id="counter">
        <span id="current">1</span> / <span id="total">{len(image_data)}</span>
    </div>
    
    <div class="progress-container">
        <div class="progress-bar" id="progressBar"></div>
    </div>
    
    <div class="keyboard-hint">
        <i class="fas fa-keyboard"></i> Keyboard: ← → to navigate
    </div>
    
    <script>
        // Carousel functionality
        let currentIndex = 0;
        const slides = document.querySelectorAll('.carousel-slide');
        const totalSlides = slides.length;
        const progressBar = document.getElementById('progressBar');
        const currentSpan = document.getElementById('current');
        const totalSpan = document.getElementById('total');
        const imageInfo = document.getElementById('imageInfo');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const fullscreenBtn = document.getElementById('fullscreenBtn');
        const fullscreenIndicator = document.getElementById('fullscreenIndicator');
        
        // Image data for display
        const imageData = {image_data_json};
        
        // Initialize carousel
        if (slides.length > 0) {{
            slides[currentIndex].classList.add('active');
        }}
        
        // Update counter and info
        function updateDisplay() {{
            if (slides.length === 0) return;
            
            // Update active slide
            slides.forEach((slide, index) => {{
                slide.classList.toggle('active', index === currentIndex);
            }});
            
            // Update counter
            currentSpan.textContent = currentIndex + 1;
            totalSpan.textContent = totalSlides;
            
            // Update image info
            if (imageData[currentIndex]) {{
                imageInfo.innerHTML = imageData[currentIndex].filename +
                    (imageData[currentIndex].onion_site ? 
                     `<span class='onion-tag'>${{imageData[currentIndex].onion_site}}.onion</span>` : '');
            }}
            
            // Reset and start progress bar
            progressBar.style.width = '0%';
            setTimeout(() => {{
                progressBar.style.width = '100%';
            }}, 10);
        }}
        
        // Navigation functions
        function nextSlide() {{
            currentIndex = (currentIndex + 1) % totalSlides;
            updateDisplay();
        }}
        
        function prevSlide() {{
            currentIndex = (currentIndex - 1 + totalSlides) % totalSlides;
            updateDisplay();
        }}
        
        // Event listeners
        nextBtn.addEventListener('click', nextSlide);
        prevBtn.addEventListener('click', prevSlide);
        
        // Auto-advance every 10 seconds
        setInterval(nextSlide, 10000);
        
        // Keyboard navigation
        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowRight') {{
                nextSlide();
            }} else if (e.key === 'ArrowLeft') {{
                prevSlide();
            }}
        }});
        
        // Initialize progress bar
        if (totalSlides > 0) {{
            progressBar.style.transition = 'width 10s linear';
            progressBar.style.width = '100%';
        }}
    </script>
</body>
</html>"""

    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(output_file)
    os.makedirs(output_dir, exist_ok=True)

    # Write the HTML file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Full-screen carousel gallery created at {output_file}")
    print(f"Embedded {len(image_data)} images")


def main():
    parser = argparse.ArgumentParser(description='Create full-screen carousel gallery for images from scraped onion sites')
    parser.add_argument('--input-dir', default='../scraped_data',
                        help='Directory containing scraped data with images (default: ../scraped_data)')
    parser.add_argument('--output', default='../scraped_data/carousel_gallery.html',
                        help='Output HTML file path (default: ../scraped_data/carousel_gallery.html)')

    args = parser.parse_args()

    # Find all image files in the images subdirectories of onion directories
    print(f"Searching for images in {args.input_dir}...")
    image_paths = find_images_in_scraped_data(args.input_dir)

    if not image_paths:
        print(f"No images found in {args.input_dir}/[onion_address]/images/")
        return

    print(f"Found {len(image_paths)} images")

    # Generate carousel gallery
    generate_carousel_gallery(image_paths, args.input_dir, args.output)

    print(f"Carousel gallery complete!")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()