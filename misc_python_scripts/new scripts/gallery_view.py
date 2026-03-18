#!/usr/bin/env python3
"""
Modern Gallery View with Glassmorphism for HTML Content Viewer

Creates a visualization that embeds HTML content from scraped onion sites in iframes
with a modern, professional gallery view featuring glassmorphism and monochrome styling.
"""

import os
import json
import re
import argparse
from pathlib import Path

# Pre-compiled regex for onion address validation (v2: 16 chars, v3: 56 chars, or vanity: <=56 chars)
ONION_PATTERN = re.compile(r'^[a-z2-7]{1,56}$')


def extract_title_from_html(html_file_path):
    """Extract title from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for title tag in the HTML
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    # Remove extra whitespace and newlines
                    title = ' '.join(title.split())
                    return title
        except Exception as e:
            print(f"Error reading {html_file_path}: {str(e)}")
    return None


def find_visualization_htmls(scraped_data_dir):
    """Find all HTML visualization files in the visualizations subdirectory of each onion directory."""
    html_paths = []

    # Look for onion directories in the scraped_data_dir
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)

        # Check if it's a directory that looks like an onion address (<=56 chars with valid base32)
        if os.path.isdir(item_path) and ONION_PATTERN.match(item):
            # Look for a visualizations subdirectory
            viz_dir = os.path.join(item_path, 'visualizations')
            if os.path.exists(viz_dir):
                # Find all HTML files in the visualizations directory
                for file in os.listdir(viz_dir):
                    if file.lower().endswith('.html'):
                        html_path = os.path.join(viz_dir, file)
                        html_paths.append(html_path)

    return html_paths


def generate_gallery_visualization(html_paths, scraped_data_dir, output_file):
    """Generate HTML visualization with iframes for each HTML file in a modern gallery view."""

    # Prepare data for visualization
    html_data = []
    for html_path in html_paths:
        # Get the title of the HTML file
        title = extract_title_from_html(html_path)
        if not title:
            title = os.path.basename(html_path)

        # Calculate relative path from output file location
        rel_path = os.path.relpath(html_path, os.path.dirname(output_file))

        # Determine the onion site this HTML belongs to
        path_parts = html_path.split('/')
        onion_site = None
        for part in path_parts:
            if ONION_PATTERN.match(part):
                onion_site = part
                break

        html_data.append({
            'path': rel_path.replace("\\", "/"),  # Normalize path separators
            'title': title,
            'basename': os.path.basename(html_path),
            'onion_site': onion_site
        })

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Modern Gallery View - Onion Site Visualizations</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --bg-primary: #121212;
            --bg-secondary: #1e1e1e;
            --card-bg: rgba(30, 30, 30, 0.6);
            --glass-bg: rgba(255, 255, 255, 0.05);
            --glass-border: rgba(255, 255, 255, 0.1);
            --text-primary: #f0f0f0;
            --text-secondary: #b0b0b0;
            --accent: #a0a0a0;
            --hover: #d0d0d0;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(255, 255, 255, 0.03) 0%, transparent 20%),
                radial-gradient(circle at 90% 80%, rgba(255, 255, 255, 0.03) 0%, transparent 20%);
        }}
        
        .header {{
            text-align: center;
            margin-bottom: 2.5rem;
            padding: 1.5rem;
            backdrop-filter: blur(10px);
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 16px;
            max-width: 800px;
            margin-left: auto;
            margin-right: auto;
        }}
        
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(45deg, var(--text-primary), var(--accent));
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            font-weight: 700;
        }}
        
        .subtitle {{
            color: var(--text-secondary);
            font-size: 1.1rem;
            margin-top: 0.5rem;
        }}
        
        .stats {{
            display: flex;
            justify-content: center;
            gap: 2rem;
            margin-top: 1rem;
            flex-wrap: wrap;
        }}
        
        .stat-card {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: 12px;
            padding: 1rem;
            min-width: 150px;
            text-align: center;
            backdrop-filter: blur(10px);
        }}
        
        .stat-value {{
            font-size: 1.8rem;
            font-weight: 700;
            color: var(--hover);
        }}
        
        .stat-label {{
            font-size: 0.9rem;
            color: var(--text-secondary);
        }}
        
        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
            gap: 1.5rem;
            max-width: 1600px;
            margin: 0 auto;
        }}
        
        @media (max-width: 1200px) {{
            .gallery {{
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            }}
        }}
        
        @media (max-width: 768px) {{
            .gallery {{
                grid-template-columns: 1fr;
            }}
            
            body {{
                padding: 1rem;
            }}
        }}
        
        .card {{
            background: var(--card-bg);
            border-radius: 16px;
            overflow: hidden;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
            backdrop-filter: blur(10px);
            border: 1px solid var(--glass-border);
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
            display: flex;
            flex-direction: column;
            height: 100%;
        }}
        
        .card:hover {{
            transform: translateY(-8px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.2);
        }}
        
        .card-header {{
            padding: 1.2rem;
            border-bottom: 1px solid var(--glass-border);
            background: rgba(0, 0, 0, 0.2);
        }}
        
        .card-title {{
            font-size: 1.2rem;
            font-weight: 600;
            margin-bottom: 0.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}
        
        .onion-tag {{
            background: rgba(255, 255, 255, 0.1);
            color: var(--accent);
            padding: 0.2rem 0.6rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-family: monospace;
        }}
        
        .card-meta {{
            display: flex;
            justify-content: space-between;
            color: var(--text-secondary);
            font-size: 0.85rem;
        }}
        
        .iframe-container {{
            flex-grow: 1;
            position: relative;
            min-height: 300px;
        }}
        
        iframe {{
            width: 100%;
            height: 100%;
            min-height: 300px;
            border: none;
            border-radius: 0 0 15px 15px;
        }}
        
        .no-content {{
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100%;
            color: var(--text-secondary);
            font-style: italic;
            padding: 2rem;
            text-align: center;
        }}
        
        .controls {{
            position: fixed;
            top: 2rem;
            right: 2rem;
            display: flex;
            gap: 0.8rem;
            z-index: 1000;
        }}
        
        .control-btn {{
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
        
        .control-btn:hover {{
            background: var(--glass-border);
            transform: scale(1.1);
        }}
        
        .footer {{
            text-align: center;
            margin-top: 3rem;
            padding: 1.5rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
            border-top: 1px solid var(--glass-border);
        }}
        
        .search-bar {{
            max-width: 600px;
            margin: 1.5rem auto;
            position: relative;
        }}
        
        .search-input {{
            width: 100%;
            padding: 1rem 1.5rem;
            border-radius: 50px;
            border: 1px solid var(--glass-border);
            background: var(--glass-bg);
            color: var(--text-primary);
            font-size: 1rem;
            backdrop-filter: blur(10px);
        }}
        
        .search-input:focus {{
            outline: none;
            border-color: var(--accent);
            box-shadow: 0 0 0 2px rgba(160, 160, 160, 0.3);
        }}
        
        .search-icon {{
            position: absolute;
            right: 1.5rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-secondary);
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1><i class="fas fa-globe-americas"></i> Onion Site Gallery</h1>
        <p class="subtitle">Modern visualization of scraped content with glassmorphism design</p>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{len(html_data)}</div>
                <div class="stat-label">Sites</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{len([item for item in html_data if item['onion_site']])}</div>
                <div class="stat-label">Onion Sites</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">Live</div>
                <div class="stat-label">Status</div>
            </div>
        </div>
    </div>
    
    <div class="search-bar">
        <input type="text" class="search-input" id="searchInput" placeholder="Search sites...">
        <i class="fas fa-search search-icon"></i>
    </div>
    
    <div class="controls">
        <div class="control-btn" title="Refresh All" onclick="refreshAll()">
            <i class="fas fa-sync-alt"></i>
        </div>
        <div class="control-btn" title="Toggle Grid" onclick="toggleGrid()">
            <i class="fas fa-th-large"></i>
        </div>
    </div>
    
    <div class="gallery" id="galleryContainer">
        {"".join([
            f'''<div class="card" data-title="{item["title"].lower()}" data-onion="{item["onion_site"].lower() if item["onion_site"] else ""}">
                <div class="card-header">
                    <div class="card-title">
                        <i class="fas fa-link"></i>
                        <span>{item["title"]}</span>
                    </div>
                    <div class="card-meta">
                        <span>{item["basename"]}</span>
                        {f'<span class="onion-tag">{item["onion_site"][:12]}...</span>' if item["onion_site"] else ''}
                    </div>
                </div>
                <div class="iframe-container">
                    {f'<iframe src="{item["path"]}" sandbox="allow-same-origin allow-scripts allow-forms"></iframe>' if os.path.exists(os.path.join(os.path.dirname(output_file), item["path"])) else '<div class="no-content"><i class="fas fa-exclamation-triangle"></i> HTML file not found</div>'}
                </div>
            </div>'''
            for item in html_data
        ])}
    </div>
    
    <div class="footer">
        <p>Modern Gallery View | {len(html_data)} sites visualized | Powered by Glassmorphism Design</p>
    </div>
    
    <script>
        // Search functionality
        document.getElementById('searchInput').addEventListener('input', function(e) {{
            const searchTerm = e.target.value.toLowerCase();
            const cards = document.querySelectorAll('.card');
            
            cards.forEach(card => {{
                const title = card.getAttribute('data-title');
                const onion = card.getAttribute('data-onion');
                
                if (title.includes(searchTerm) || onion.includes(searchTerm)) {{
                    card.style.display = 'flex';
                }} else {{
                    card.style.display = 'none';
                }}
            }});
        }});
        
        function refreshAll() {{
            const iframes = document.querySelectorAll('iframe');
            iframes.forEach(iframe => {{
                iframe.src = iframe.src;
            }});
            
            // Show a temporary notification
            const btn = document.querySelector('.control-btn[title="Refresh All"]');
            btn.innerHTML = '<i class="fas fa-check"></i>';
            setTimeout(() => {{
                btn.innerHTML = '<i class="fas fa-sync-alt"></i>';
            }}, 1000);
        }}
        
        function toggleGrid() {{
            const gallery = document.getElementById('galleryContainer');
            const currentCols = getComputedStyle(gallery).gridTemplateColumns;
            
            if (currentCols.includes('minmax(400px')) {{
                gallery.style.gridTemplateColumns = 'repeat(auto-fill, minmax(600px, 1fr))';
            }} else {{
                gallery.style.gridTemplateColumns = 'repeat(auto-fill, minmax(400px, 1fr))';
            }}
        }}
        
        // Add click to expand functionality to cards
        document.querySelectorAll('.card').forEach(card => {{
            card.addEventListener('click', function(e) {{
                if (e.target.tagName !== 'IFRAME' && !e.target.closest('iframe')) {{
                    const iframe = this.querySelector('iframe');
                    if (iframe) {{
                        // Toggle expanded view
                        this.classList.toggle('expanded');
                        
                        if (this.classList.contains('expanded')) {{
                            this.style.position = 'fixed';
                            this.style.top = '50%';
                            this.style.left = '50%';
                            this.style.transform = 'translate(-50%, -50%)';
                            this.style.width = '90vw';
                            this.style.height = '90vh';
                            this.style.zIndex = '1000';
                            
                            // Add overlay
                            const overlay = document.createElement('div');
                            overlay.style.position = 'fixed';
                            overlay.style.top = '0';
                            overlay.style.left = '0';
                            overlay.style.width = '100%';
                            overlay.style.height = '100%';
                            overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.8)';
                            overlay.style.zIndex = '999';
                            overlay.onclick = () => {{
                                document.body.removeChild(overlay);
                                this.classList.remove('expanded');
                                this.style.position = '';
                                this.style.top = '';
                                this.style.left = '';
                                this.style.transform = '';
                                this.style.width = '';
                                this.style.height = '';
                                this.style.zIndex = '';
                            }};
                            document.body.appendChild(overlay);
                        }}
                    }}
                }}
            }});
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

    print(f"Modern gallery visualization created at {output_file}")
    print(f"Embedded {len(html_data)} HTML files")


def main():
    parser = argparse.ArgumentParser(description='Create modern gallery visualization for HTML content from scraped onion sites')
    parser.add_argument('--input-dir', default='../scraped_data',
                        help='Directory containing scraped data with HTML files (default: ../scraped_data)')
    parser.add_argument('--output', default='../scraped_data/gallery_viewer.html',
                        help='Output HTML file path (default: ../scraped_data/gallery_viewer.html)')

    args = parser.parse_args()

    # Find all visualization HTML files in the visualizations subdirectories of onion directories
    print(f"Searching for visualization HTML files in {args.input_dir}...")
    html_paths = find_visualization_htmls(args.input_dir)

    if not html_paths:
        print(f"No visualization HTML files found in {args.input_dir}/[onion_address]/visualizations/")
        return

    print(f"Found {len(html_paths)} visualization HTML files")

    # Generate gallery visualization
    generate_gallery_visualization(html_paths, args.input_dir, args.output)

    print(f"Gallery visualization complete!")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()