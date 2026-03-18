#!/usr/bin/env python3
"""
Fast Full-Screen Carousel Gallery

Creates a fast full-screen carousel gallery that displays only index.png or index.jpg 
from scraped onion sites with performance optimizations and no glassmorphism effects.
"""

import os
import json
import re
import argparse
from pathlib import Path


def find_index_images_in_scraped_data(scraped_data_dir):
    """Find only index.png or index.jpg files in the images subdirectory of each onion directory."""
    image_paths = []

    # Look for onion directories in the scraped_data_dir
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)

        # Check if it's a directory that looks like an onion address (56 characters with valid base32 chars)
        if os.path.isdir(item_path) and len(item) == 56 and all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in item):
            # Look for an images subdirectory
            img_dir = os.path.join(item_path, 'images')
            if os.path.exists(img_dir):
                # Only look for index.png or index.jpg in the images directory (not subdirectories)
                for file in os.listdir(img_dir):
                    if file.lower() in ('index.png', 'index.jpg', 'index.jpeg'):
                        img_path = os.path.join(img_dir, file)
                        image_paths.append(img_path)

    return image_paths


def generate_fast_carousel_gallery(image_paths, scraped_data_dir, output_file):
    """Generate HTML carousel gallery with performance optimizations and no glassmorphism."""

    # Prepare data for gallery
    image_data = []
    for img_path in image_paths:
        # Calculate relative path from output file location
        rel_path = os.path.relpath(img_path, os.path.dirname(output_file))

        # Extract onion site and filename info
        path_parts = img_path.split('/')
        onion_site = None
        for part in path_parts:
            if len(part) == 56 and all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in part):  # Base32 for .onion
                onion_site = part
                break

        image_data.append({
            'path': rel_path.replace("\\", "/"),  # Normalize path separators
            'filename': os.path.basename(img_path),
            'onion_site': onion_site
        })

    # Convert image_data to JSON string for JavaScript
    image_data_json = json.dumps(image_data)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fast Carousel Gallery</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --bg-dark: #000;
            --text-primary: #f0f0f0;
            --text-secondary: #b0b0b0;
            --accent: #a0a0a0;
            --control-bg: rgba(0, 0, 0, 0.7);
            --control-border: rgba(255, 255, 255, 0.2);
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
            background: var(--bg-dark);
            color: var(--text-primary);
        }}

        .carousel-container {{
            position: relative;
            width: 100%;
            height: 100vh;
            overflow: hidden;
            background: var(--bg-dark);
        }}

        .carousel-slide {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            opacity: 0;
            transition: opacity 0.5s ease-in-out;
            display: flex;
            align-items: center;
            justify-content: center;
            /* Lazy loading setup */
            contain: layout style paint;
        }}

        .carousel-slide.active {{
            opacity: 1;
        }}

        .carousel-slide:not(.active) {{
            pointer-events: none;
        }}

        .slide-image {{
            max-width: 95%;
            max-height: 90%;
            object-fit: contain;
            border-radius: 8px;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            /* Enable hardware acceleration */
            will-change: transform;
            transform: translateZ(0);
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
            background: var(--control-bg);
            border-bottom: 1px solid var(--control-border);
        }}

        .image-info {{
            font-size: 1.1rem;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 0.8rem;
        }}

        .onion-tag {{
            background: rgba(255, 255, 255, 0.15);
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
            background: var(--control-bg);
            border: 1px solid var(--control-border);
            border-radius: 50%;
            width: 50px;
            height: 50px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            color: var(--text-primary);
            font-size: 1.2rem;
            transition: all 0.2s ease;
        }}

        .nav-btn:hover {{
            background: rgba(255, 255, 255, 0.2);
            transform: scale(1.1);
        }}

        .counter {{
            position: fixed;
            bottom: 2rem;
            left: 50%;
            transform: translateX(-50%);
            background: var(--control-bg);
            border: 1px solid var(--control-border);
            border-radius: 50px;
            padding: 0.8rem 1.5rem;
            font-size: 1rem;
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

        .keyboard-hint {{
            position: fixed;
            bottom: 6rem;
            left: 50%;
            transform: translateX(-50%);
            background: var(--control-bg);
            border: 1px solid var(--control-border);
            border-radius: 8px;
            padding: 0.8rem 1.2rem;
            font-size: 0.9rem;
            z-index: 100;
            opacity: 0.7;
            transition: opacity 0.3s;
        }}

        .keyboard-hint:hover {{
            opacity: 1;
        }}
        
        /* Performance optimizations */
        .carousel-slide {{
            contain: strict;
        }}
        
        /* Hide non-active slides to improve performance */
        .carousel-slide:not(.active) {{
            visibility: hidden;
            position: absolute;
        }}
    </style>
</head>
<body>
    <div class="carousel-container" id="carousel">
        {"".join([
            f'''<div class="carousel-slide" id="slide-{i}">
                <img src="{item["path"]}" alt="{item["filename"]}" class="slide-image" loading="lazy">
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
        // Carousel functionality with performance optimizations
        let currentIndex = 0;
        const slides = document.querySelectorAll('.carousel-slide');
        const totalSlides = slides.length;
        const progressBar = document.getElementById('progressBar');
        const currentSpan = document.getElementById('current');
        const totalSpan = document.getElementById('total');
        const imageInfo = document.getElementById('imageInfo');
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');

        // Image data for display
        const imageData = {image_data_json};

        // Preload adjacent images for smoother transitions
        function preloadAdjacentImages(index) {{
            const nextIndex = (index + 1) % totalSlides;
            const prevIndex = (index - 1 + totalSlides) % totalSlides;
            
            if (imageData[nextIndex]) {{
                const nextImg = new Image();
                nextImg.src = imageData[nextIndex].path;
            }}
            
            if (imageData[prevIndex]) {{
                const prevImg = new Image();
                prevImg.src = imageData[prevIndex].path;
            }}
        }}

        // Initialize carousel
        if (slides.length > 0) {{
            slides[currentIndex].classList.add('active');
            preloadAdjacentImages(currentIndex);
        }}

        // Update counter and info
        function updateDisplay() {{
            if (slides.length === 0) return;

            // Update active slide
            slides.forEach((slide, index) => {{
                slide.classList.toggle('active', index === currentIndex);
                if (index !== currentIndex) {{
                    slide.classList.remove('active');
                }}
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
            
            // Preload adjacent images
            preloadAdjacentImages(currentIndex);
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

        // Auto-advance every 12 seconds (slightly slower for better UX with preloading)
        const autoAdvance = setInterval(nextSlide, 12000);

        // Pause auto-advance on user interaction, resume after 30 seconds of inactivity
        let userInteractionTimer;
        function resetAutoAdvance() {{
            clearInterval(autoAdvance);
            clearTimeout(userInteractionTimer);
            userInteractionTimer = setTimeout(() => {{
                // Restart auto-advance
            }}, 30000);
        }}

        // Listen for user interactions
        document.addEventListener('keydown', resetAutoAdvance);
        document.addEventListener('click', resetAutoAdvance);
        document.addEventListener('touchstart', resetAutoAdvance);

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
            progressBar.style.transition = 'width 12s linear';
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

    print(f"Fast full-screen carousel gallery created at {output_file}")
    print(f"Embedded {len(image_data)} images")


def main():
    parser = argparse.ArgumentParser(description='Create fast full-screen carousel gallery for index images from scraped onion sites')
    parser.add_argument('--input-dir', default='../scraped_data',
                        help='Directory containing scraped data with images (default: ../scraped_data)')
    parser.add_argument('--output', default='../scraped_data/fast_carousel_gallery.html',
                        help='Output HTML file path (default: ../scraped_data/fast_carousel_gallery.html)')

    args = parser.parse_args()

    # Find only index.png or index.jpg files in the images subdirectories of onion directories
    print(f"Searching for index images in {args.input_dir}...")
    image_paths = find_index_images_in_scraped_data(args.input_dir)

    if not image_paths:
        print(f"No index.png or index.jpg images found in {args.input_dir}/[onion_address]/images/")
        return

    print(f"Found {len(image_paths)} index images")

    # Generate fast carousel gallery
    generate_fast_carousel_gallery(image_paths, args.input_dir, args.output)

    print(f"Fast carousel gallery complete!")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()