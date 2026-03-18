#!/usr/bin/env python3
"""
Fast Grid Gallery - Displays 10 images per page

Creates a fast grid gallery that displays only index.png or index.jpg 
from scraped onion sites with performance optimizations and no glassmorphism effects.
Shows 10 images per page in a responsive grid layout.
"""

import os
import json
import argparse
from pathlib import Path


def find_index_images_in_scraped_data(scraped_data_dir):
    """Find only index.png or index.jpg files in the images subdirectory of each onion directory."""
    image_paths = []
    base_path = Path(scraped_data_dir)

    if not base_path.exists():
        print(f"Error: Directory {scraped_data_dir} does not exist.")
        return []

    # Look for onion directories in the scraped_data_dir (v3 onions are 56 chars)
    for item in base_path.iterdir():
        if item.is_dir() and len(item.name) == 56 and all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in item.name):
            img_dir = item / 'images'
            if img_dir.exists() and img_dir.is_dir():
                # Look for index files specifically
                for file_path in img_dir.iterdir():
                    if file_path.is_file() and file_path.stem.lower() == 'index' and file_path.suffix.lower() in ('.png', '.jpg', '.jpeg'):
                        image_paths.append(str(file_path))

    return image_paths


def generate_grid_gallery(image_paths, scraped_data_dir, output_file):
    """Generate HTML grid gallery with performance optimizations and no glassmorphism."""
    output_path = Path(output_file)
    output_dir = output_path.parent
    
    # Prepare data for gallery
    image_data = []
    for img_path_str in image_paths:
        img_path = Path(img_path_str)
        
        # Calculate relative path from output file location for browser compatibility
        try:
            rel_path = os.path.relpath(img_path, output_dir)
        except ValueError:
            # Handle cases where paths are on different drives on Windows
            rel_path = str(img_path)

        # Extract onion site (the directory name that is 56 chars long)
        onion_site = None
        for part in img_path.parts:
            if len(part) == 56 and all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in part):
                onion_site = part
                break

        image_data.append({
            'path': rel_path.replace("\\", "/"),  # Normalize for web URLs
            'filename': img_path.name,
            'onion_site': onion_site
        })

    # Convert image_data to JSON string for JavaScript
    image_data_json = json.dumps(image_data)

    # Calculate number of pages using Python for the initial header
    images_per_page = 10
    total_pages = max(1, (len(image_data) + images_per_page - 1) // images_per_page)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Grid Gallery - {total_pages} Page{'s' if total_pages != 1 else ''}</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --bg-dark: #000;
            --text-primary: #f0f0f0;
            --text-secondary: #b0b0b0;
            --accent: #a0a0a0;
            --card-bg: rgba(30, 30, 30, 0.8);
            --card-border: rgba(255, 255, 255, 0.1);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body, html {{
            height: 100%;
            width: 100%;
            min-height: 100vh;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--bg-dark);
            color: var(--text-primary);
            padding: 20px;
        }}

        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 20px;
        }}

        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 10px;
        }}

        .pagination-controls {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 15px;
            margin: 20px 0 40px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.5);
            border-radius: 10px;
        }}

        .page-btn {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid var(--card-border);
            border-radius: 5px;
            padding: 8px 15px;
            color: var(--text-primary);
            cursor: pointer;
            transition: all 0.2s ease;
            min-width: 40px;
        }}

        .page-btn:hover:not(:disabled) {{
            background: rgba(255, 255, 255, 0.2);
        }}

        .page-btn.active {{
            background: var(--accent);
            color: var(--bg-dark);
        }}
        
        .page-btn:disabled {{
            opacity: 0.3;
            cursor: not-allowed;
        }}

        .grid-container {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 25px;
            max-width: 1400px;
            margin: 0 auto;
        }}

        .image-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0, 0, 0, 0.3);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            display: flex;
            flex-direction: column;
            height: 100%;
            contain: layout style paint;
        }}

        .image-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
        }}

        .image-wrapper {{
            position: relative;
            width: 100%;
            padding-top: 56.25%; /* 16:9 Aspect Ratio */
            overflow: hidden;
            background: #111;
        }}

        .image-wrapper img {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s ease;
        }}

        .image-card:hover .image-wrapper img {{
            transform: scale(1.05);
        }}

        .image-info {{
            padding: 15px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
        }}

        .filename {{
            font-weight: 500;
            margin-bottom: 8px;
            word-break: break-all;
        }}

        .onion-tag {{
            background: rgba(255, 255, 255, 0.15);
            color: var(--accent);
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 0.8rem;
            font-family: monospace;
            align-self: flex-start;
            max-width: 100%;
            word-break: break-all;
        }}

        .page-indicator {{
            text-align: center;
            margin: 20px 0;
            font-size: 1.2rem;
            color: var(--text-secondary);
        }}

        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            color: var(--text-secondary);
            font-size: 0.9rem;
        }}

        @media (max-width: 768px) {{
            .grid-container {{
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 15px;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Image Gallery</h1>
        <p>{len(image_data)} images found</p>
    </div>

    <div class="pagination-controls">
        <button class="page-btn" id="prevPage" title="Previous page">
            <i class="fas fa-chevron-left"></i>
        </button>
        
        <div id="pageNumbersContainer"></div>
        
        <button class="page-btn" id="nextPage" title="Next page">
            <i class="fas fa-chevron-right"></i>
        </button>
    </div>

    <div class="page-indicator" id="pageIndicator">
        Page <span id="currentPageNum">1</span> of {total_pages}
    </div>

    <div class="grid-container" id="gridContainer"></div>

    <div class="footer">
        <p>Fast Grid Gallery | Showing 10 images per page</p>
    </div>

    <script>
        const imageData = {image_data_json};
        const imagesPerPage = 10;
        const totalPages = Math.max(1, Math.ceil(imageData.length / imagesPerPage));
        let currentPage = 1;

        const gridContainer = document.getElementById('gridContainer');
        const pageNumbersContainer = document.getElementById('pageNumbersContainer');
        const pageIndicator = document.getElementById('pageIndicator');
        const prevPageBtn = document.getElementById('prevPage');
        const nextPageBtn = document.getElementById('nextPage');

        function renderPage(page) {{
            gridContainer.innerHTML = '';
            const startIndex = (page - 1) * imagesPerPage;
            const endIndex = Math.min(startIndex + imagesPerPage, imageData.length);
            
            for (let i = startIndex; i < endIndex; i++) {{
                const img = imageData[i];
                const card = document.createElement('div');
                card.className = 'image-card';
                card.innerHTML = `
                    <div class="image-wrapper">
                        <img src="${{img.path}}" alt="${{img.filename}}" loading="lazy" onerror="this.src='https://placehold.co/600x400?text=Error+Loading+Image'">
                    </div>
                    <div class="image-info">
                        <div class="filename">${{img.filename}}</div>
                        ${{img.onion_site ? `<div class="onion-tag">${{img.onion_site}}.onion</div>` : ''}}
                    </div>
                `;
                gridContainer.appendChild(card);
            }}
            
            // Fix: Added ${{}} to interpolate JS variables correctly
            pageIndicator.innerHTML = `Page <span id="currentPageNum">${{page}}</span> of ${{totalPages}}`;
            updatePaginationControls(page);
            currentPage = page;
            window.scrollTo(0, 0);
        }}

        function updatePaginationControls(page) {{
            pageNumbersContainer.innerHTML = '';
            
            let startPage = Math.max(1, page - 2);
            let endPage = Math.min(totalPages, page + 2);
            
            if (page <= 3) endPage = Math.min(5, totalPages);
            if (page >= totalPages - 2) startPage = Math.max(1, totalPages - 4);
            
            for (let i = startPage; i <= endPage; i++) {{
                const btn = document.createElement('button');
                btn.className = 'page-btn' + (i === page ? ' active' : '');
                btn.textContent = i;
                btn.onclick = () => renderPage(i);
                pageNumbersContainer.appendChild(btn);
            }}
            
            prevPageBtn.disabled = page === 1;
            nextPageBtn.disabled = page === totalPages;
        }}

        prevPageBtn.onclick = () => {{ if (currentPage > 1) renderPage(currentPage - 1); }};
        nextPageBtn.onclick = () => {{ if (currentPage < totalPages) renderPage(currentPage + 1); }};

        document.addEventListener('keydown', (e) => {{
            if (e.key === 'ArrowRight') nextPageBtn.onclick();
            if (e.key === 'ArrowLeft') prevPageBtn.onclick();
        }});

        renderPage(1);
    </script>
</body>
</html>"""

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Gallery created: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Create fast grid gallery')
    parser.add_argument('--input-dir', default='../scraped_data', help='Input directory')
    parser.add_argument('--output', default='../scraped_data/grid_gallery.html', help='Output file')

    args = parser.parse_args()

    print(f"Searching for images in {args.input_dir}...")
    image_paths = find_index_images_in_scraped_data(args.input_dir)

    if not image_paths:
        print("No index images found.")
        return

    generate_grid_gallery(image_paths, args.input_dir, args.output)

if __name__ == "__main__":
    main()
