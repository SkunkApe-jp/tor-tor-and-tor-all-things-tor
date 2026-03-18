#!/usr/bin/env python3
"""
Community Hub Map - Clustered Network Visualization

Creates a force-directed graph where nodes are grouped into "islands" or clusters
based on their content category (Marketplaces, Forums, Directories, etc.).
Uses discovered_links and HTML content for categorization.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path
from collections import defaultdict

# Category keywords for classification
CATEGORY_KEYWORDS = {
    'marketplace': ['market', 'shop', 'store', 'buy', 'sell', 'vendor', 'cart', 'product', 'price', 'order', 'commerce', 'trade', 'exchange'],
    'forum': ['forum', 'board', 'thread', 'post', 'discussion', 'community', 'message', 'topic', 'reply', 'member', 'register'],
    'directory': ['directory', 'index', 'list', 'catalog', 'links', 'resource', 'guide', 'wiki', 'database', 'search'],
    'news': ['news', 'media', 'press', 'article', 'report', 'headline', 'broadcast', 'journal', 'magazine', 'daily', 'weekly'],
    'blog': ['blog', 'weblog', 'post', 'article', 'author', 'comment', 'subscribe', 'rss', 'personal'],
    'social': ['social', 'network', 'chat', 'message', 'friend', 'profile', 'connect', 'share', 'follow', 'feed'],
    'service': ['service', 'hosting', 'email', 'mail', 'vpn', 'proxy', 'tool', 'utility', 'api', 'cloud', 'storage'],
    'finance': ['finance', 'bank', 'crypto', 'bitcoin', 'wallet', 'exchange', 'trading', 'investment', 'payment', 'currency'],
    'privacy': ['privacy', 'security', 'anonymous', 'tor', 'encryption', 'protection', 'secure', 'safe'],
    'education': ['education', 'learn', 'course', 'tutorial', 'library', 'book', 'research', 'study', 'university', 'school'],
    'entertainment': ['entertainment', 'game', 'music', 'video', 'movie', 'stream', 'play', 'fun', 'humor', 'art'],
    'technology': ['technology', 'tech', 'software', 'hardware', 'code', 'programming', 'developer', 'linux', 'python', 'github'],
    'political': ['political', 'activism', 'government', 'policy', 'freedom', 'rights', 'democracy', 'revolution', 'whistleblow'],
    'adult': ['adult', 'xxx', 'porn', 'sex', 'nsfw', 'explicit', 'mature', 'erotica'],
}

COLOR_PALETTE = {
    'marketplace': '#e74c3c',  # Red
    'forum': '#3498db',  # Blue
    'directory': '#2ecc71',  # Green
    'news': '#f39c12',  # Orange
    'blog': '#9b59b6',  # Purple
    'social': '#1abc9c',  # Teal
    'service': '#34495e',  # Dark blue
    'finance': '#f1c40f',  # Yellow
    'privacy': '#16a085',  # Dark teal
    'education': '#27ae60',  # Dark green
    'entertainment': '#e91e63',  # Pink
    'technology': '#00bcd4',  # Cyan
    'political': '#c0392b',  # Dark red
    'adult': '#8e44ad',  # Dark purple
    'uncategorized': '#95a5a6',  # Gray
}


def categorize_text(text):
    """Categorize text based on keywords. Returns list of matching categories."""
    if not text:
        return ['uncategorized']
    
    text_lower = text.lower()
    matches = defaultdict(int)
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                matches[category] += 1
    
    if not matches:
        return ['uncategorized']
    
    # Return top category
    top_category = max(matches, key=matches.get)
    return [top_category]


def extract_title_from_html(html_file_path):
    """Extract title from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    return ' '.join(title.split())
        except Exception as e:
            print(f"Error reading {html_file_path}: {str(e)}")
    return None


def extract_meta_keywords(html_file_path):
    """Extract meta keywords from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Look for meta keywords
                meta_match = re.search(r'<meta[^>]*name=["\']?keywords["\']?[^>]*content=["\']([^"\']+)["\']', content, re.IGNORECASE)
                if meta_match:
                    return meta_match.group(1)
                # Also try reversed attribute order
                meta_match = re.search(r'<meta[^>]*content=["\']([^"\']+)["\'][^>]*name=["\']?keywords["\']?', content, re.IGNORECASE)
                if meta_match:
                    return meta_match.group(1)
        except Exception:
            pass
    return None


def read_titles_file(titles_file_path):
    """Read titles from discovered_links file."""
    titles = {}
    if os.path.exists(titles_file_path):
        try:
            with open(titles_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '->' in line:
                        parts = line.split('->', 1)
                        if len(parts) == 2:
                            title = parts[0].strip('[] ').strip()
                            url = parts[1].strip()
                            titles[url] = title
        except Exception:
            pass
    return titles


def read_main_page_title(site_dir):
    """Read main page title from website_identity folder."""
    title_file = os.path.join(site_dir, 'website_identity', 'main_page_title.txt')
    if os.path.exists(title_file):
        try:
            with open(title_file, 'r', encoding='utf-8') as f:
                line = f.readline().strip()
                if '->' in line:
                    parts = line.split('->', 1)
                    if len(parts) == 2:
                        return parts[0].strip('[] ').strip()
        except Exception:
            pass
    return None


def read_links_file(links_file_path):
    """Read links from a links file."""
    links = []
    if os.path.exists(links_file_path):
        with open(links_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and '.onion' in line:
                    links.append(line)
    return links


def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and re.match(r'^[a-z2-7]{16,56}$', item):
            onion_dirs.append(item)
    return onion_dirs


def generate_community_hub_map(scraped_data_dir):
    """Generate a community hub map with clustered nodes by category."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to analyze")

    # Build site data with categories
    site_data = {}
    all_links = set()
    
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        root_url = f"http://{onion_addr}.onion"
        
        # Get title from HTML
        html_file = os.path.join(site_dir, 'htmls', f"{onion_addr}.html")
        title = extract_title_from_html(html_file) or onion_addr
        
        # Get meta keywords
        meta_keywords = extract_meta_keywords(html_file)

        # Get titles from discovered_links folder
        titles_data = {}
        titles_dir = os.path.join(site_dir, 'discovered_links')
        if os.path.exists(titles_dir):
            for f in os.listdir(titles_dir):
                if f.endswith('_titles.txt'):
                    titles_data.update(read_titles_file(os.path.join(titles_dir, f)))

        # Get main page title from website_identity folder
        main_page_title = read_main_page_title(site_dir)

        # Combine text for categorization
        categorization_text = f"{title} {meta_keywords or ''}"
        if main_page_title:
            categorization_text += f" {main_page_title}"
        for url, t in titles_data.items():
            categorization_text += f" {t}"
        
        # Categorize
        category = categorize_text(categorization_text)[0]
        
        # Get outbound links
        outbound_links = []
        for d in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, d)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        outbound_links.extend(read_links_file(os.path.join(path, f)))
        
        all_links.update(outbound_links)
        
        # Get image path
        image_path = ""
        for img_name in ["index.png", f"{onion_addr}.png"]:
            img_path = os.path.join(site_dir, 'images', img_name)
            if os.path.exists(img_path):
                image_path = f"{onion_addr}/images/{img_name}"
                break
        
        site_data[root_url] = {
            'title': title,
            'category': category,
            'image': image_path,
            'outbound_links': list(set(outbound_links))[:30],  # Limit for performance
            'titles_found': len(titles_data)
        }
    
    # Process discovered links that aren't scraped
    for link in all_links:
        if link not in site_data:
            onion_match = re.search(r'([a-z2-7]{16,56})\.onion', link)
            if onion_match:
                linked_addr = onion_match.group(1)
                site_data[link] = {
                    'title': link,
                    'category': 'uncategorized',
                    'image': '',
                    'outbound_links': [],
                    'titles_found': 0,
                    'is_discovered_only': True
                }
    
    # Build nodes and links
    nodes = []
    links = []
    url_to_idx = {}
    category_counts = defaultdict(int)
    
    for url, data in site_data.items():
        url_to_idx[url] = len(nodes)
        category = data['category']
        category_counts[category] += 1
        
        nodes.append({
            'id': url,
            'title': data['title'][:50] + '...' if len(data['title']) > 50 else data['title'],
            'category': category,
            'image': data['image'],
            'is_root': not data.get('is_discovered_only', False),
            'titles_count': data['titles_found']
        })
    
    # Create links
    for url, data in site_data.items():
        if url in url_to_idx:
            source_idx = url_to_idx[url]
            for target_url in data['outbound_links']:
                if target_url in url_to_idx:
                    target_idx = url_to_idx[target_url]
                    if source_idx != target_idx:
                        links.append({'source': source_idx, 'target': target_idx})
    
    # Calculate cluster centers for each category
    categories = list(set(n['category'] for n in nodes))
    
    print(f"\nCategory Distribution:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count} sites")
    
    print(f"\nTotal: {len(nodes)} nodes, {len(links)} links")
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Community Hub Map</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: hidden; background: #0a0a0f; font-family: 'Segoe UI', sans-serif; }}
        #tooltip {{
            position: absolute; padding: 12px; background: rgba(30,30,40,0.95);
            border: 1px solid #444; border-radius: 8px; pointer-events: none; opacity: 0; z-index: 100;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3); max-width: 450px;
            transition: opacity 0.2s; color: #eee; font-size: 12px;
            word-break: break-word; white-space: normal;
        }}
        .link {{ stroke: #333; stroke-opacity: 0.3; stroke-width: 1px; }}
        #legend {{
            position: fixed; bottom: 20px; left: 20px; background: rgba(30,30,40,0.9);
            padding: 12px; border-radius: 8px; border: 1px solid #333; z-index: 10;
            color: #aaa; font-size: 12px; line-height: 1.8; max-height: 60vh; overflow-y: auto;
        }}
        #legend strong {{ color: #fff; }}
        .legend-item {{ display: flex; align-items: center; margin: 5px 0; font-size: 11px; }}
        .legend-color {{ width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; }}
        #controls {{ position: absolute; top: 20px; right: 20px; display: flex; flex-direction: column; gap: 8px; z-index: 10; }}
        .btn {{
            background: rgba(30,30,40,0.9); color: #fff; border: 1px solid #444;
            padding: 10px; cursor: pointer; border-radius: 6px; font-size: 14px;
            transition: all 0.2s;
        }}
        .btn:hover {{ background: rgba(50,50,60,0.9); border-color: #666; }}
        #stats {{
            position: fixed; top: 20px; left: 20px; background: rgba(30,30,40,0.9);
            padding: 12px; border-radius: 8px; border: 1px solid #333; color: #aaa; font-size: 12px; z-index: 10;
        }}
    </style>
</head>
<body>
    <div id="stats">{len(nodes)} nodes | {len(links)} connections | {len(categories)} categories</div>
    <div id="controls">
        <button class="btn" onclick="zoomIn()">+</button>
        <button class="btn" onclick="zoomOut()">−</button>
        <button class="btn" onclick="resetView()">↺</button>
    </div>
    <div id="legend">
        <strong>Community Categories</strong>
        {''.join(f'<div class="legend-item"><div class="legend-color" style="background: {COLOR_PALETTE.get(cat, "#95a5a6")}"></div><span>{cat.title()} ({category_counts.get(cat, 0)})</span></div>' for cat in sorted(categories))}
    </div>
    <div id="tooltip"></div>

    <script>
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};
        const categories = {json.dumps(categories)};
        const categoryColors = {json.dumps(COLOR_PALETTE)};

        const width = window.innerWidth;
        const height = window.innerHeight;

        // Calculate cluster centers (relative to center)
        const clusterRadius = Math.min(width, height) * 0.35;
        const clusterCenters = {{}};
        const angleStep = (2 * Math.PI) / categories.length;

        categories.forEach((cat, i) => {{
            const angle = i * angleStep - Math.PI / 2;
            clusterCenters[cat] = {{
                x: Math.cos(angle) * clusterRadius,
                y: Math.sin(angle) * clusterRadius
            }};
        }});

        // Assign initial positions based on category
        nodes.forEach((d, i) => {{
            const center = clusterCenters[d.category];
            const spread = 80;
            d.x = center.x + (Math.random() - 0.5) * spread;
            d.y = center.y + (Math.random() - 0.5) * spread;
        }});

        const svg = d3.select("body").append("svg")
            .attr("width", "100%")
            .attr("height", "100vh")
            .attr("viewBox", [-width/2, -height/2, width, height]);

        const zoomG = svg.append("g");

        const zoom = d3.zoom()
            .scaleExtent([0.1, 5])
            .on("zoom", (e) => zoomG.attr("transform", e.transform));
        svg.call(zoom);

        function zoomIn() {{ svg.transition().duration(400).call(zoom.scaleBy, 1.3); }}
        function zoomOut() {{ svg.transition().duration(400).call(zoom.scaleBy, 0.7); }}
        function resetView() {{ svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity); }}

        // Draw cluster background circles
        const clusterGroup = zoomG.append("g").attr("class", "clusters");
        categories.forEach(cat => {{
            const center = clusterCenters[cat];
            clusterGroup.append("circle")
                .attr("cx", center.x)
                .attr("cy", center.y)
                .attr("r", 120)
                .attr("fill", categoryColors[cat] || "#95a5a6")
                .attr("opacity", 0.08)
                .attr("stroke", categoryColors[cat] || "#95a5a6")
                .attr("stroke-opacity", 0.2)
                .attr("stroke-dasharray", "5,5");
            
            clusterGroup.append("text")
                .attr("x", center.x)
                .attr("y", center.y - 130)
                .attr("text-anchor", "middle")
                .attr("fill", categoryColors[cat] || "#95a5a6")
                .attr("font-size", "11px")
                .attr("opacity", 0.6)
                .text(cat.toUpperCase());
        }});
        
        const simulation = d3.forceSimulation(nodes)
            .alphaDecay(0.02)
            .force("link", d3.forceLink(links).id((d, i) => i).distance(100).strength(0.3))
            .force("charge", d3.forceManyBody().strength(-150).distanceMax(400))
            .force("collide", d3.forceCollide().radius(d => d.image ? 35 : 12).iterations(2))
            .force("cluster", d3.forceX(d => clusterCenters[d.category].x).strength(0.08))
            .force("clusterY", d3.forceY(d => clusterCenters[d.category].y).strength(0.08))
            .force("center", d3.forceCenter(0, 0).strength(0.02));
        
        const link = zoomG.append("g")
            .selectAll("line")
            .data(links)
            .join("line")
            .attr("class", "link");
        
        const node = zoomG.append("g")
            .selectAll("g")
            .data(nodes)
            .join("g")
            .attr("cursor", "move")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
        
        // Node circles with category color
        node.filter(d => !d.image)
            .append("circle")
            .attr("r", d => d.is_root ? 10 : 6)
            .attr("fill", d => categoryColors[d.category] || "#95a5a6")
            .attr("stroke", "#fff")
            .attr("stroke-width", 1.5)
            .attr("opacity", d => d.is_root ? 0.9 : 0.6);
        
        // Node images
        node.filter(d => d.image)
            .append("circle")
            .attr("r", 35)
            .attr("fill", "#222")
            .attr("stroke", d => categoryColors[d.category] || "#95a5a6")
            .attr("stroke-width", 2);
        
        node.filter(d => d.image)
            .append("image")
            .attr("xlink:href", d => d.image)
            .attr("x", -35)
            .attr("y", -35)
            .attr("width", 70)
            .attr("height", 70)
            .attr("clip-path", "circle(33px at 35px 35px)");
        
        // Labels for root nodes
        const label = zoomG.append("g")
            .selectAll("text")
            .data(nodes.filter(d => d.is_root))
            .join("text")
            .text(d => d.title.length > 25 ? d.title.substring(0, 22) + "..." : d.title)
            .attr("font-size", "9px")
            .attr("fill", "#aaa")
            .attr("dx", d => d.image ? 40 : 15)
            .attr("dy", 4)
            .attr("pointer-events", "none");
        
        // Tooltip
        const tooltip = d3.select("#tooltip");
        
        node.on("mouseover", (e, d) => {{
            tooltip.transition().duration(200).style("opacity", 1);
            tooltip.html(`
                <div style="font-weight: bold; color: #fff; margin-bottom: 5px;">${{d.title}}</div>
                <div style="font-size: 11px; color: #aaa;">
                    <span style="color: ${{categoryColors[d.category] || "#95a5a6"}}">●</span> ${{d.category}}<br/>
                    Type: ${{d.is_root ? "Scraped Site" : "Discovered Link"}}<br/>
                    ${{d.titles_count > 0 ? `Titles found: ${{d.titles_count}}` : ""}}
                </div>
                <div style="font-size: 10px; color: #888; margin-top: 5px; word-break: break-all;">${{d.id}}</div>
            `);
            tooltip.style("left", (e.pageX + 15) + "px").style("top", (e.pageY - 15) + "px");
        }})
        .on("mouseout", () => {{
            tooltip.transition().duration(300).style("opacity", 0);
        }})
        .on("click", (e, d) => {{
            if (d.image) window.open(d.image, '_blank');
        }});
        
        simulation.on("tick", () => {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node.attr("transform", d => `translate(${{d.x}},${{d.y}})`);
            
            label
                .attr("x", d => d.x)
                .attr("y", d => d.y);
        }});
        
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}
        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
    </script>
</body>
</html>"""
    
    output_file = os.path.join(scraped_data_dir, "community_hub_map.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\nCommunity Hub Map created at {output_file}")
    return output_file


def main():
    scraped_data_dir = "../scraped_data"
    
    if not os.path.exists(scraped_data_dir):
        scraped_data_dir = "scraped_data"
        if not os.path.exists(scraped_data_dir):
            print("Error: scraped_data directory not found")
            return
    
    generate_community_hub_map(scraped_data_dir)


if __name__ == "__main__":
    main()
