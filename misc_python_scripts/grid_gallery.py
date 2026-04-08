#!/usr/bin/env python3
"""
Image Gallery Search Engine

Creates a searchable grid gallery that displays index images from scraped onion sites.
Shows website titles from website_identity/index_title.txt and includes search functionality.
"""

import os
import json
import re
import argparse
from pathlib import Path

# Pre-compiled regex for onion address validation (v2: 16 chars, v3: 56 chars, or vanity: <=56 chars)
ONION_PATTERN = re.compile(r'^[a-z2-7]{1,56}$')
# Regex to extract title from index_title.txt format: [Title] -> http://...
TITLE_PATTERN = re.compile(r'^\[([^\]]+)\]\s*->')


def get_website_title(onion_dir, scraped_data_dir):
    """Extract website title from website_identity/index_title.txt if available."""
    title_file = os.path.join(scraped_data_dir, onion_dir, 'website_identity', 'index_title.txt')
    if os.path.exists(title_file):
        try:
            with open(title_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read().strip()
                match = TITLE_PATTERN.match(content)
                if match:
                    return match.group(1).strip()
        except Exception:
            pass
    return None


def find_index_images_in_scraped_data(scraped_data_dir):
    """Find index images and their website titles from onion directories."""
    image_data = []

    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)

        if os.path.isdir(item_path) and ONION_PATTERN.match(item):
            img_dir = os.path.join(item_path, 'images')
            if os.path.exists(img_dir):
                for file in os.listdir(img_dir):
                    if file.lower() in ('index.png', 'index.jpg', 'index.jpeg'):
                        img_path = os.path.join(img_dir, file)
                        title = get_website_title(item, scraped_data_dir)
                        image_data.append({
                            'path': img_path,
                            'filename': file,
                            'onion_site': item,
                            'title': title if title else file  # Fallback to filename
                        })

    return image_data


def generate_grid_gallery(image_data, scraped_data_dir, output_file):
    """Generate HTML grid gallery with search engine functionality."""

    # Prepare data for gallery - calculate relative paths
    gallery_data = []
    for item in image_data:
        rel_path = os.path.relpath(item['path'], os.path.dirname(output_file))
        gallery_data.append({
            'path': rel_path.replace("\\", "/"),
            'filename': item['filename'],
            'onion_site': item['onion_site'],
            'title': item['title']
        })

    image_data_json = json.dumps(gallery_data, separators=(',', ':'))
    total_images = len(gallery_data)
    unique_sites = len(set(item['onion_site'] for item in gallery_data))

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Image Gallery</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-primary: #0a0a0f;
            --bg-secondary: #12121a;
            --bg-tertiary: #1a1a25;
            --text-primary: #ffffff;
            --text-secondary: #a0a0b0;
            --text-muted: #6a6a7a;
            --accent-primary: #6366f1;
            --accent-secondary: #818cf8;
            --accent-glow: rgba(99, 102, 241, 0.3);
            --card-bg: linear-gradient(145deg, rgba(26, 26, 37, 0.95), rgba(18, 18, 26, 0.98));
            --card-border: rgba(255, 255, 255, 0.08);
            --card-border-hover: rgba(99, 102, 241, 0.4);
            --card-height: 360px;
            --card-width: 340px;
            --gap: 24px;
            --header-height: 160px;
            --radius-lg: 16px;
            --radius-md: 12px;
            --radius-sm: 8px;
            --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.3);
            --shadow-md: 0 4px 16px rgba(0, 0, 0, 0.4);
            --shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.5);
            --shadow-glow: 0 8px 32px rgba(99, 102, 241, 0.2);
        }}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body, html {{
            min-height: 100vh;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}

        body {{
            background-image: 
                radial-gradient(ellipse at top, rgba(99, 102, 241, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at bottom, rgba(129, 140, 248, 0.04) 0%, transparent 50%);
            background-attachment: fixed;
        }}

        .header {{
            position: sticky;
            top: 0;
            padding: 24px 32px;
            background: rgba(10, 10, 15, 0.85);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            z-index: 1000;
            border-bottom: 1px solid var(--card-border);
        }}

        .header-content {{
            max-width: 1600px;
            margin: 0 auto;
        }}

        .header-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 20px;
        }}

        .branding h1 {{
            font-size: 1.75rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--text-primary) 0%, var(--accent-secondary) 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            letter-spacing: -0.02em;
        }}

        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 8px;
        }}

        .stat-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 500;
        }}

        .stat-item .stat-value {{
            color: var(--accent-secondary);
            font-weight: 600;
        }}

        .search-container {{
            display: flex;
            gap: 12px;
            max-width: 560px;
            flex-grow: 1;
        }}

        .search-wrapper {{
            position: relative;
            flex-grow: 1;
        }}

        .search-icon {{
            position: absolute;
            left: 16px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            pointer-events: none;
            transition: color 0.2s;
        }}

        .search-box {{
            width: 100%;
            padding: 14px 16px 14px 48px;
            border: 1px solid var(--card-border);
            border-radius: var(--radius-md);
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-primary);
            font-size: 0.95rem;
            font-family: inherit;
            outline: none;
            transition: all 0.2s ease;
        }}

        .search-box:focus {{
            border-color: var(--accent-primary);
            background: rgba(255, 255, 255, 0.05);
            box-shadow: 0 0 0 3px var(--accent-glow);
        }}

        .search-box:focus + .search-icon {{
            color: var(--accent-secondary);
        }}

        .search-box::placeholder {{
            color: var(--text-muted);
        }}

        .clear-btn {{
            padding: 14px 24px;
            background: var(--bg-tertiary);
            border: 1px solid var(--card-border);
            border-radius: var(--radius-md);
            color: var(--text-secondary);
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            font-family: inherit;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }}

        .clear-btn:hover {{
            background: rgba(99, 102, 241, 0.15);
            border-color: var(--accent-primary);
            color: var(--text-primary);
        }}

        .clear-btn:active {{
            transform: scale(0.98);
        }}

        .main-container {{
            padding: 32px;
            max-width: 1800px;
            margin: 0 auto;
        }}

        .grid-container {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(var(--card-width), 1fr));
            gap: var(--gap);
        }}

        .image-card {{
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: var(--radius-lg);
            overflow: hidden;
            box-shadow: var(--shadow-md);
            display: flex;
            flex-direction: column;
            height: var(--card-height);
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            position: relative;
        }}

        .image-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: var(--radius-lg);
            padding: 1px;
            background: linear-gradient(145deg, rgba(99, 102, 241, 0.3), transparent);
            -webkit-mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            mask: linear-gradient(#fff 0 0) content-box, linear-gradient(#fff 0 0);
            -webkit-mask-composite: xor;
            mask-composite: exclude;
            opacity: 0;
            transition: opacity 0.3s ease;
        }}

        .image-card:hover {{
            transform: translateY(-6px);
            box-shadow: var(--shadow-lg), var(--shadow-glow);
            border-color: var(--card-border-hover);
        }}

        .image-card:hover::before {{
            opacity: 1;
        }}

        .image-wrapper {{
            position: relative;
            width: 100%;
            height: 220px;
            overflow: hidden;
            background: var(--bg-secondary);
        }}

        .image-wrapper img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        }}

        .image-card:hover .image-wrapper img {{
            transform: scale(1.08);
        }}

        .image-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: linear-gradient(to bottom, transparent 0%, rgba(0, 0, 0, 0.4) 100%);
            opacity: 0;
            transition: opacity 0.3s ease;
        }}

        .image-card:hover .image-overlay {{
            opacity: 1;
        }}

        .image-info {{
            padding: 18px;
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}

        .title {{
            font-size: 0.95rem;
            font-weight: 600;
            color: var(--text-primary);
            word-break: break-word;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            line-height: 1.4;
        }}

        .filename {{
            font-size: 0.8rem;
            color: var(--text-muted);
            word-break: break-all;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
        }}

        .metadata {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: auto;
            flex-wrap: wrap;
        }}

        .onion-tag {{
            background: rgba(99, 102, 241, 0.15);
            color: var(--accent-secondary);
            padding: 6px 12px;
            border-radius: var(--radius-sm);
            font-size: 0.75rem;
            font-family: 'JetBrains Mono', 'Consolas', monospace;
            font-weight: 500;
            border: 1px solid rgba(99, 102, 241, 0.2);
            transition: all 0.2s ease;
        }}

        .onion-tag:hover {{
            background: rgba(99, 102, 241, 0.25);
            border-color: var(--accent-primary);
        }}

        .no-results {{
            text-align: center;
            padding: 100px 20px;
            color: var(--text-secondary);
            grid-column: 1 / -1;
        }}

        .no-results-icon {{
            font-size: 4rem;
            margin-bottom: 20px;
            opacity: 0.5;
        }}

        .no-results h2 {{
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: 8px;
        }}

        .no-results p {{
            color: var(--text-muted);
            font-size: 1rem;
        }}

        .loading {{
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 60px;
            grid-column: 1 / -1;
        }}

        .spinner {{
            width: 40px;
            height: 40px;
            border: 3px solid var(--card-border);
            border-top-color: var(--accent-primary);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
        }}

        @keyframes spin {{
            to {{ transform: rotate(360deg); }}
        }}

        @keyframes fadeIn {{
            from {{
                opacity: 0;
                transform: translateY(20px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}

        .image-card {{
            animation: fadeIn 0.4s ease forwards;
        }}

        @media (max-width: 1024px) {{
            :root {{
                --card-width: 300px;
                --card-height: 340px;
            }}
            .header {{
                padding: 20px 24px;
            }}
            .main-container {{
                padding: 24px;
            }}
        }}

        @media (max-width: 768px) {{
            :root {{
                --card-width: 280px;
                --card-height: 320px;
                --gap: 16px;
            }}
            .header {{
                padding: 16px 20px;
            }}
            .header-top {{
                flex-direction: column;
                align-items: stretch;
            }}
            .search-container {{
                max-width: none;
            }}
            .stats {{
                flex-direction: column;
                gap: 8px;
            }}
            .branding h1 {{
                font-size: 1.5rem;
            }}
            .main-container {{
                padding: 16px;
            }}
        }}

        @media (max-width: 480px) {{
            :root {{
                --card-width: 100%;
                --card-height: 300px;
            }}
            .grid-container {{
                grid-template-columns: 1fr;
            }}
            .clear-btn span {{
                display: none;
            }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <div class="header-top">
                <div class="branding">
                    <h1>🔍 Image Gallery</h1>
                    <div class="stats">
                        <div class="stat-item">
                            <span class="stat-value" id="totalImages">{total_images}</span>
                            <span>images</span>
                        </div>
                        <div class="stat-item">
                            <span class="stat-value" id="totalSites">{unique_sites}</span>
                            <span>sites</span>
                        </div>
                    </div>
                </div>
                <div class="search-container">
                    <div class="search-wrapper">
                        <input type="text" class="search-box" id="searchBox" placeholder="Search titles, filenames, or addresses..." autofocus>
                        <svg class="search-icon" width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M14.5 14.5L18 18M16.5 9.5C16.5 13.0899 13.5899 16 10 16C6.41015 16 3.5 13.0899 3.5 9.5C3.5 5.91015 6.41015 3 10 3C13.5899 3 16.5 5.91015 16.5 9.5Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                    </div>
                    <button class="clear-btn" id="clearBtn" title="Clear search">
                        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
                            <path d="M13.5 4.5L4.5 13.5M4.5 4.5L13.5 13.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                        </svg>
                        <span>Clear</span>
                    </button>
                </div>
            </div>
        </div>
    </div>

    <div class="main-container">
        <div class="grid-container" id="gridContainer">
            <div class="loading">
                <div class="spinner"></div>
            </div>
        </div>
    </div>

    <script>
        (function() {{
            'use strict';

            const imageData = {image_data_json};
            const totalImages = imageData.length;

            const gridContainer = document.getElementById('gridContainer');
            const searchBox = document.getElementById('searchBox');
            const clearBtn = document.getElementById('clearBtn');
            const totalImagesEl = document.getElementById('totalImages');
            const totalSitesEl = document.getElementById('totalSites');

            let filteredData = [...imageData];

            function createCard(data, index) {{
                const card = document.createElement('div');
                card.className = 'image-card';
                card.style.animationDelay = `${{index * 0.03}}s`;
                card.innerHTML = `
                    <div class="image-wrapper">
                        <img src="${{data.path}}" alt="${{data.title}}" loading="lazy">
                        <div class="image-overlay"></div>
                    </div>
                    <div class="image-info">
                        <div class="title">${{data.title}}</div>
                        <div class="filename">${{data.filename}}</div>
                        <div class="metadata">
                            ${{data.onion_site ? `<div class="onion-tag">${{data.onion_site}}.onion</div>` : ''}}
                        </div>
                    </div>
                `;
                return card;
            }}

            function renderGrid() {{
                gridContainer.innerHTML = '';

                if (filteredData.length === 0) {{
                    gridContainer.innerHTML = `
                        <div class="no-results">
                            <div class="no-results-icon">🔎</div>
                            <h2>No results found</h2>
                            <p>Try adjusting your search terms</p>
                        </div>
                    `;
                    return;
                }}

                filteredData.forEach((data, index) => {{
                    gridContainer.appendChild(createCard(data, index));
                }});

                totalImagesEl.textContent = filteredData.length;
            }}

            function filterData(query) {{
                const q = query.toLowerCase().trim();
                if (!q) {{
                    filteredData = [...imageData];
                }} else {{
                    filteredData = imageData.filter(item =>
                        item.title.toLowerCase().includes(q) ||
                        item.filename.toLowerCase().includes(q) ||
                        item.onion_site.toLowerCase().includes(q)
                    );
                }}
                renderGrid();
            }}

            searchBox.addEventListener('input', (e) => {{
                filterData(e.target.value);
            }});

            clearBtn.addEventListener('click', () => {{
                searchBox.value = '';
                filterData('');
                searchBox.focus();
            }});

            // Initial render with slight delay for smooth loading
            setTimeout(() => {{
                renderGrid();
            }}, 50);
        }})();
    </script>
</body>
</html>"""

    output_dir = os.path.dirname(output_file)
    os.makedirs(output_dir, exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"Search engine gallery created at {output_file}")
    print(f"Total: {len(image_data)} images from {len(set(item['onion_site'] for item in image_data))} sites")


def main():
    parser = argparse.ArgumentParser(description='Create fast grid gallery with search for index images from scraped onion sites')
    parser.add_argument('--input-dir', default='../scraped_data',
                        help='Directory containing scraped data with images (default: ../scraped_data)')
    parser.add_argument('--output', default='../scraped_data/grid_gallery.html',
                        help='Output HTML file path (default: ../scraped_data/grid_gallery.html)')

    args = parser.parse_args()

    print(f"Searching for index images in {args.input_dir}...")
    image_data = find_index_images_in_scraped_data(args.input_dir)

    if not image_data:
        print(f"No index.png or index.jpg images found in {args.input_dir}/[onion_address]/images/")
        return

    print(f"Found {len(image_data)} index images from {len(set(item['onion_site'] for item in image_data))} sites")

    generate_grid_gallery(image_data, args.input_dir, args.output)

    print(f"Grid gallery complete!")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()