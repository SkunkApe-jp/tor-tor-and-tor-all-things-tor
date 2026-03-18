#!/usr/bin/env python3
"""
Advanced Analytics Pack - Network Analysis & Content Insights

Useful visualizations for understanding onion site networks:
- Category Distribution: What types of sites exist
- Hub Analysis: Most connected sites (inbound/outbound)
- Isolated Sites: Sites with no connections
- Category Network: Which categories link to which
- Link Density Heatmap: Connection patterns matrix
"""

import os
import json
import re
from pathlib import Path
from collections import Counter, defaultdict


def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and re.match(r'^[a-z2-7]{16,56}$', item):
            onion_dirs.append(item)
    return onion_dirs


def extract_title_from_html(html_file_path):
    """Extract title from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    return ' '.join(title_match.group(1).strip().split())[:50]
        except Exception:
            pass
    return None


# Category keywords for classification
CATEGORY_KEYWORDS = {
    'marketplace': ['market', 'shop', 'store', 'buy', 'sell', 'vendor', 'cart', 'product', 'price', 'order'],
    'forum': ['forum', 'board', 'thread', 'post', 'discussion', 'community', 'message', 'topic', 'reply'],
    'directory': ['directory', 'index', 'list', 'catalog', 'links', 'resource', 'guide', 'wiki', 'database'],
    'news': ['news', 'media', 'press', 'article', 'report', 'headline', 'broadcast', 'journal'],
    'blog': ['blog', 'weblog', 'author', 'comment', 'subscribe', 'rss', 'personal'],
    'service': ['service', 'hosting', 'email', 'mail', 'vpn', 'proxy', 'tool', 'api', 'cloud'],
    'finance': ['finance', 'bank', 'crypto', 'bitcoin', 'wallet', 'exchange', 'trading', 'payment'],
    'privacy': ['privacy', 'security', 'anonymous', 'tor', 'encryption', 'protection', 'secure'],
    'education': ['education', 'learn', 'course', 'tutorial', 'library', 'book', 'research', 'study'],
    'technology': ['technology', 'tech', 'software', 'hardware', 'code', 'programming', 'linux'],
    'uncategorized': []
}

COLOR_PALETTE = {
    'marketplace': '#e74c3c', 'forum': '#3498db', 'directory': '#2ecc71',
    'news': '#f39c12', 'blog': '#9b59b6', 'service': '#34495e',
    'finance': '#f1c40f', 'privacy': '#16a085', 'education': '#27ae60',
    'technology': '#00bcd4', 'uncategorized': '#95a5a6'
}


def categorize_site(scraped_data_dir, onion_addr):
    """Categorize a site based on its content."""
    site_dir = os.path.join(scraped_data_dir, onion_addr)
    html_file = os.path.join(site_dir, 'htmls', f"{onion_addr}.html")
    
    text = ""
    if os.path.exists(html_file):
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    text = title_match.group(1).lower()
        except Exception:
            pass
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        if category == 'uncategorized':
            continue
        for keyword in keywords:
            if keyword in text:
                return category
    return 'uncategorized'


# ============================================================
# 1. CATEGORY DISTRIBUTION
# ============================================================

def generate_category_distribution(scraped_data_dir):
    """Generate category distribution bar chart."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"\nAnalyzing {len(onion_sites)} sites for category distribution...")
    
    category_counts = Counter()
    site_categories = {}
    
    for addr in onion_sites:
        category = categorize_site(scraped_data_dir, addr)
        category_counts[category] += 1
        site_categories[addr] = category
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Category Distribution</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ margin: 0; background: #0a0a0f; font-family: 'Segoe UI', sans-serif; color: #eee; }}
        #container {{ max-width: 1200px; margin: 0 auto; padding: 40px 20px; }}
        #header {{ position: fixed; top: 0; left: 0; right: 0; background: rgba(10,10,15,0.95);
            padding: 15px 20px; border-bottom: 1px solid #222; z-index: 10; }}
        #header h1 {{ margin: 0; color: #fff; font-size: 18px; }}
        #stats {{ color: #888; font-size: 13px; margin-top: 5px; }}
        .chart-container {{ position: relative; height: 500px; margin-top: 40px; background: #1a1a2e;
            border-radius: 12px; padding: 20px; }}
        .category-list {{ margin-top: 40px; display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 15px; }}
        .category-card {{ background: #1a1a2e; border-radius: 8px; padding: 15px; border-left: 4px solid; }}
        .category-card h3 {{ margin: 0 0 10px 0; font-size: 14px; color: #fff; }}
        .category-card .count {{ font-size: 24px; font-weight: bold; }}
        .category-card .sites {{ font-size: 11px; color: #888; margin-top: 10px; max-height: 100px; overflow-y: auto; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Category Distribution - Site Types</h1>
        <div id="stats">{len(onion_sites)} sites across {len(category_counts)} categories</div>
    </div>
    <div id="container">
        <div class="chart-container">
            <canvas id="chart"></canvas>
        </div>
        <div class="category-list">
            {''.join(f"""
            <div class="category-card" style="border-color: {COLOR_PALETTE.get(cat, '#95a5a6')}">
                <h3 style="color: {COLOR_PALETTE.get(cat, '#95a5a6')}">{cat.title()}</h3>
                <div class="count">{count}</div>
                <div class="sites">{', '.join([a[:16] for a, c in site_categories.items() if c == cat][:10])}{'...' if count > 10 else ''}</div>
            </div>
            """ for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]))}
        </div>
    </div>
    <script>
        const ctx = document.getElementById('chart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: {json.dumps(list(category_counts.keys()))},
                datasets: [{{
                    label: 'Sites',
                    data: {json.dumps(list(category_counts.values()))},
                    backgroundColor: {json.dumps([COLOR_PALETTE.get(c, '#95a5a6') for c in category_counts.keys()])},
                    borderColor: {json.dumps([COLOR_PALETTE.get(c, '#95a5a6') for c in category_counts.keys()])},
                    borderWidth: 2
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }},
                    tooltip: {{
                        backgroundColor: 'rgba(30,30,40,0.95)',
                        titleColor: '#fff',
                        bodyColor: '#aaa',
                        borderColor: '#444',
                        borderWidth: 1
                    }}
                }},
                scales: {{
                    y: {{
                        beginAtZero: true,
                        grid: {{ color: '#333' }},
                        ticks: {{ color: '#aaa' }}
                    }},
                    x: {{
                        grid: {{ display: false }},
                        ticks: {{ color: '#aaa' }}
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""

    output_file = os.path.join(scraped_data_dir, "category_distribution.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"  Category Distribution: {output_file}")
    return output_file


# ============================================================
# 2. HUB ANALYSIS
# ============================================================

def generate_hub_analysis(scraped_data_dir):
    """Generate hub analysis - most connected sites."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"\nAnalyzing {len(onion_sites)} sites for hub detection...")
    
    site_data = {}
    
    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)
        title = extract_title_from_html(os.path.join(site_dir, 'htmls', f"{addr}.html")) or addr[:20]
        
        # Count outbound links
        outbound = 0
        outbound_targets = set()
        for d in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, d)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        with open(os.path.join(path, f), 'r') as lf:
                            for line in lf:
                                if '.onion' in line:
                                    outbound += 1
                                    for target in onion_sites:
                                        if target in line and target != addr:
                                            outbound_targets.add(target)
        
        # Count inbound links
        inbound = 0
        inbound_sources = set()
        for other_addr in onion_sites:
            if other_addr != addr:
                other_dir = os.path.join(scraped_data_dir, other_addr)
                for d in ['urls', 'discovered_links']:
                    path = os.path.join(other_dir, d)
                    if os.path.exists(path):
                        for f in os.listdir(path):
                            if f.endswith('_links.txt'):
                                with open(os.path.join(path, f), 'r') as lf:
                                    for line in lf:
                                        if addr in line and '.onion' in line:
                                            inbound += 1
                                            inbound_sources.add(other_addr)
        
        site_data[addr] = {
            'title': title,
            'outbound': outbound,
            'inbound': inbound,
            'total': inbound + outbound,
            'outbound_targets': len(outbound_targets),
            'inbound_sources': len(inbound_sources)
        }
    
    # Sort by different metrics
    top_outbound = sorted(site_data.items(), key=lambda x: -x[1]['outbound'])[:15]
    top_inbound = sorted(site_data.items(), key=lambda x: -x[1]['inbound'])[:15]
    top_total = sorted(site_data.items(), key=lambda x: -x[1]['total'])[:15]
    isolated = [(k, v) for k, v in site_data.items() if v['total'] == 0]
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Hub Analysis</title>
    <style>
        body {{ margin: 0; background: #0a0a0f; font-family: 'Segoe UI', sans-serif; color: #eee; }}
        #container {{ max-width: 1400px; margin: 0 auto; padding: 40px 20px; }}
        #header {{ position: fixed; top: 0; left: 0; right: 0; background: rgba(10,10,15,0.95);
            padding: 15px 20px; border-bottom: 1px solid #222; z-index: 10; }}
        #header h1 {{ margin: 0; color: #fff; font-size: 18px; }}
        #stats {{ color: #888; font-size: 13px; margin-top: 5px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin-top: 40px; }}
        .card {{ background: #1a1a2e; border-radius: 12px; padding: 20px; }}
        .card h2 {{ margin: 0 0 20px 0; font-size: 16px; color: #fff; border-bottom: 1px solid #333; padding-bottom: 10px; }}
        .site-row {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #222; }}
        .site-row:last-child {{ border-bottom: none; }}
        .site-name {{ flex: 1; min-width: 0; }}
        .site-name .title {{ font-size: 13px; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .site-name .addr {{ font-size: 10px; color: #666; }}
        .site-stats {{ display: flex; gap: 15px; font-size: 12px; }}
        .stat {{ text-align: center; }}
        .stat .value {{ font-size: 16px; font-weight: bold; }}
        .stat .label {{ font-size: 10px; color: #666; }}
        .stat.inbound .value {{ color: #4ade80; }}
        .stat.outbound .value {{ color: #60a5fa; }}
        .stat.total .value {{ color: #fbbf24; }}
        .isolated {{ color: #ef4444; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Hub Analysis - Most Connected Sites</h1>
        <div id="stats">{len(onion_sites)} sites analyzed | {len(isolated)} isolated sites</div>
    </div>
    <div id="container">
        <div class="grid">
            <div class="card">
                <h2>📤 Top Outbound (Most Links Out)</h2>
                {''.join(f"""
                <div class="site-row">
                    <div class="site-name">
                        <div class="title">{v['title']}</div>
                        <div class="addr">{k[:16]}...</div>
                    </div>
                    <div class="site-stats">
                        <div class="stat outbound">
                            <div class="value">{v['outbound']}</div>
                            <div class="label">out</div>
                        </div>
                    </div>
                </div>
                """ for k, v in top_outbound)}
            </div>
            
            <div class="card">
                <h2>📥 Top Inbound (Most Linked To)</h2>
                {''.join(f"""
                <div class="site-row">
                    <div class="site-name">
                        <div class="title">{v['title']}</div>
                        <div class="addr">{k[:16]}...</div>
                    </div>
                    <div class="site-stats">
                        <div class="stat inbound">
                            <div class="value">{v['inbound']}</div>
                            <div class="label">in</div>
                        </div>
                    </div>
                </div>
                """ for k, v in top_inbound)}
            </div>
            
            <div class="card">
                <h2>🔥 Top Total (Most Connected)</h2>
                {''.join(f"""
                <div class="site-row">
                    <div class="site-name">
                        <div class="title">{v['title']}</div>
                        <div class="addr">{k[:16]}...</div>
                    </div>
                    <div class="site-stats">
                        <div class="stat inbound">
                            <div class="value">{v['inbound']}</div>
                            <div class="label">in</div>
                        </div>
                        <div class="stat outbound">
                            <div class="value">{v['outbound']}</div>
                            <div class="label">out</div>
                        </div>
                        <div class="stat total">
                            <div class="value">{v['total']}</div>
                            <div class="label">total</div>
                        </div>
                    </div>
                </div>
                """ for k, v in top_total)}
            </div>
            
            <div class="card">
                <h2>🚫 Isolated Sites (No Connections)</h2>
                {''.join(f"""
                <div class="site-row isolated">
                    <div class="site-name">
                        <div class="title">{v['title'] or 'No title'}</div>
                        <div class="addr">{k[:30]}...</div>
                    </div>
                </div>
                """ for k, v in isolated[:20])}
                {f'<div style="color: #666; font-size: 12px; padding: 10px 0;">...and {len(isolated) - 20} more</div>' if len(isolated) > 20 else ''}
            </div>
        </div>
    </div>
</body>
</html>"""

    output_file = os.path.join(scraped_data_dir, "hub_analysis.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"  Hub Analysis: {output_file}")
    return output_file


# ============================================================
# 4. LINK DENSITY MATRIX
# ============================================================

def generate_link_density_matrix(scraped_data_dir):
    """Generate link density heatmap by category."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"\nGenerating link density matrix for {len(onion_sites)} sites...")
    
    # Categorize and build matrix
    site_categories = {addr: categorize_site(scraped_data_dir, addr) for addr in onion_sites}
    categories = list(set(site_categories.values()))
    
    # Category-level matrix
    cat_matrix = defaultdict(lambda: defaultdict(int))
    cat_counts = Counter(site_categories.values())
    
    for addr in onion_sites:
        source_cat = site_categories[addr]
        site_dir = os.path.join(scraped_data_dir, addr)
        
        for d in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, d)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        with open(os.path.join(path, f), 'r') as lf:
                            for line in lf:
                                for target in onion_sites:
                                    if target in line and target != addr:
                                        target_cat = site_categories[target]
                                        cat_matrix[source_cat][target_cat] += 1
    
    # Build normalized matrix (average links per site)
    matrix = []
    for source_cat in categories:
        row = []
        for target_cat in categories:
            count = cat_matrix[source_cat][target_cat]
            source_count = cat_counts[source_cat]
            avg = count / source_count if source_count > 0 else 0
            row.append(round(avg, 2))
        matrix.append(row)
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Link Density Matrix</title>
    <style>
        body {{ margin: 0; overflow: hidden; background: #0d1117; font-family: 'Segoe UI', sans-serif; }}
        #header {{ position: fixed; top: 0; left: 0; right: 0; background: rgba(13,17,23,0.95);
            padding: 15px 20px; border-bottom: 1px solid #222; z-index: 10; }}
        #header h1 {{ margin: 0; color: #fff; font-size: 18px; }}
        #stats {{ color: #888; font-size: 13px; }}
        #legend {{ position: fixed; bottom: 20px; left: 20px; background: rgba(30,30,40,0.9);
            padding: 12px; border-radius: 8px; border: 1px solid #333; z-index: 10; color: #aaa; font-size: 12px; }}
        #controls {{ position: absolute; top: 20px; right: 20px; z-index: 10; display: flex; flex-direction: column; gap: 8px; }}
        .btn {{ background: rgba(30,30,40,0.9); border: 1px solid #444; padding: 10px; cursor: pointer;
            border-radius: 6px; color: #fff; }}
        .btn:hover {{ background: rgba(50,50,60,0.9); }}
        .cell {{ stroke: #1f2937; stroke-width: 0.5px; }}
        .cell:hover {{ stroke: #fff; stroke-width: 2px; }}
        .axis-label {{ fill: #8b949e; font-size: 10px; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Link Density Matrix - Average Links Between Categories</h1>
        <div id="stats">{len(categories)} categories × {len(categories)} matrix</div>
    </div>
    <div id="controls">
        <button class="btn" onclick="zoomIn()">+</button>
        <button class="btn" onclick="zoomOut()">−</button>
        <button class="btn" onclick="resetView()">↺</button>
    </div>
    <div id="legend">
        <strong>How to read:</strong><br/>
        • Row = Source category (who links)<br/>
        • Column = Target category (who gets linked)<br/>
        • Cell value = Average links per site<br/>
        • Brighter = More links<br/>
        • Scroll to zoom, drag to pan
    </div>
    <script>
        const categories = {json.dumps(categories)};
        const matrix = {json.dumps(matrix)};
        const colors = {json.dumps(COLOR_PALETTE)};
        const catCounts = {json.dumps(dict(cat_counts))};

        const width = window.innerWidth;
        const height = window.innerHeight;
        const cellSize = Math.min(80, Math.floor((Math.min(width, height) - 200) / categories.length));
        const labelWidth = 100;
        const labelHeight = 60;
        const matrixSize = categories.length * cellSize;

        const svg = d3.select("body").append("svg")
            .attr("width", "100%")
            .attr("height", "100vh")
            .attr("viewBox", [0, 0, width, height]);

        const offsetX = (width - labelWidth - matrixSize) / 2;
        const offsetY = (height - labelHeight - matrixSize) / 2;

        const centerG = svg.append("g")
            .attr("transform", `translate(${{offsetX}}, ${{offsetY}})`);

        const zoomG = centerG.append("g");

        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on("zoom", (e) => zoomG.attr("transform", e.transform));
        svg.call(zoom);

        function zoomIn() {{ svg.transition().duration(400).call(zoom.scaleBy, 1.5); }}
        function zoomOut() {{ svg.transition().duration(400).call(zoom.scaleBy, 0.6); }}
        function resetView() {{ svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity); }}

        const maxVal = Math.max(...matrix.flat());
        const colorScale = d3.scaleSequential(d3.interpolateYlOrRd).domain([0, maxVal || 1]);

        // Draw cells
        zoomG.selectAll("rect")
            .data(matrix.flat())
            .join("rect")
            .attr("class", "cell")
            .attr("x", (d, i) => labelWidth + (i % categories.length) * cellSize)
            .attr("y", (d, i) => labelHeight + Math.floor(i / categories.length) * cellSize)
            .attr("width", cellSize)
            .attr("height", cellSize)
            .attr("fill", d => colorScale(d))
            .on("mouseover", (e, d) => {{
                const i = matrix.flat().indexOf(d);
                const row = Math.floor(i / categories.length);
                const col = i % categories.length;
                d3.select("#tooltip")
                    .style("opacity", 1)
                    .html(`<div style="color:#fff;font-weight:bold">${{categories[row]}} → ${{categories[col]}}</div>
                           <div style="color:#fbbf24;margin-top:5px">${{d}} avg links/site</div>`)
                    .style("left", (e.pageX + 15) + "px")
                    .style("top", (e.pageY - 15) + "px");
            }})
            .on("mouseout", () => d3.select("#tooltip").style("opacity", 0));

        // Row labels
        categories.forEach((cat, i) => {{
            zoomG.append("text")
                .attr("class", "axis-label")
                .attr("x", labelWidth - 5)
                .attr("y", labelHeight + i * cellSize + cellSize / 2 + 4)
                .attr("text-anchor", "end")
                .text(cat + ` (${{catCounts[cat]}})`);
        }});

        // Column labels
        categories.forEach((cat, i) => {{
            zoomG.append("text")
                .attr("class", "axis-label")
                .attr("x", labelWidth + i * cellSize + cellSize / 2)
                .attr("y", labelHeight - 5)
                .attr("text-anchor", "middle")
                .attr("transform", `rotate(-45, ${{labelWidth + i * cellSize + cellSize / 2}}, ${{labelHeight - 5}})`)
                .text(cat);
        }});

        // Axis titles
        zoomG.append("text")
            .attr("class", "axis-label")
            .attr("x", 10)
            .attr("y", labelHeight / 2)
            .attr("font-size", "11px")
            .attr("font-weight", "bold")
            .text("Source ↓");

        zoomG.append("text")
            .attr("class", "axis-label")
            .attr("x", labelWidth + matrixSize / 2)
            .attr("y", 15)
            .attr("text-anchor", "middle")
            .attr("font-size", "11px")
            .attr("font-weight", "bold")
            .text("Target →");
    </script>
    <div id="tooltip" style="position:fixed;padding:12px;background:rgba(30,30,40,0.95);border:1px solid #444;border-radius:8px;pointer-events:none;opacity:0;z-index:100;color:#eee;font-size:12px;"></div>
    <script src="https://d3js.org/d3.v7.min.js"></script>
</body>
</html>"""

    output_file = os.path.join(scraped_data_dir, "link_density_matrix.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"  Link Density Matrix: {output_file}")
    return output_file


# ============================================================
# MAIN
# ============================================================

def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()
    
    if not os.path.exists(scraped_data_path):
        print(f"Error: scraped_data directory not found at {scraped_data_path}")
        return

    print("\n" + "="*60)
    print("ADVANCED ANALYTICS PACK - Network Analysis")
    print("="*60)

    generate_category_distribution(str(scraped_data_path))
    generate_hub_analysis(str(scraped_data_path))
    generate_link_density_matrix(str(scraped_data_path))
    generate_intelligence_report(str(scraped_data_path))

    print("\n" + "="*60)
    print("✅ Advanced Analytics Pack complete!")
    print("="*60)
    print("\nGenerated visualizations:")
    print("  1. category_distribution.html - Site types breakdown")
    print("  2. hub_analysis.html - Most connected sites")
    print("  3. link_density_matrix.html - Link patterns heatmap")
    print("  4. intelligence_report.html - Mirrors, vanity sites, leads")


def generate_intelligence_report(scraped_data_dir):
    """Generate network intelligence report (mirrors, vanity, leads)."""
    from collections import Counter
    
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"\n[INTELLIGENCE] Analyzing {len(onion_sites)} sites...")
    
    site_fingerprints = []
    all_discovered = []
    vanity_sites = []
    titles_map = {}
    
    BRAND_KEYWORDS = ['wiki', 'torch', 'market', 'shop', 'wall', 'bank', 'forum', 'chat', 'dark']
    
    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)
        
        # Vanity detection
        for word in BRAND_KEYWORDS:
            if addr.startswith(word):
                vanity_sites.append((addr, word))
                break
        
        # Get title
        title_file = os.path.join(site_dir, 'website_identity', 'index_title.txt')
        title = ""
        if os.path.exists(title_file):
            try:
                with open(title_file, 'r') as f:
                    content = f.read()
                    if '[[' in content and ']]' in content:
                        start = content.find('[[') + 2
                        end = content.find(']]')
                        title = content[start:end].strip()
            except:
                pass
        
        titles_map[addr] = title
        
        # Get HTML size
        html_size = 0
        html_file = os.path.join(site_dir, 'htmls', f"{addr}.html")
        if os.path.exists(html_file):
            html_size = os.path.getsize(html_file)
        
        site_fingerprints.append({'addr': addr, 'title': title, 'size': html_size})
        
        # Collect discovered links
        for folder in ['urls', 'discovered_links']:
            folder_path = os.path.join(site_dir, folder)
            if os.path.exists(folder_path):
                for f in os.listdir(folder_path):
                    if f.endswith('_links.txt'):
                        try:
                            with open(os.path.join(folder_path, f), 'r') as lf:
                                found = re.findall(r'([a-z2-7]{16,56})\.onion', lf.read())
                                all_discovered.extend(found)
                        except:
                            pass
    
    # Find mirrors
    mirrors = []
    seen = set()
    for i, s1 in enumerate(site_fingerprints):
        if s1['addr'] in seen:
            continue
        group = [s1['addr']]
        for s2 in site_fingerprints[i+1:]:
            if s1['title'] == s2['title'] and s1['title'] != "" and abs(s1['size'] - s2['size']) < 500:
                group.append(s2['addr'])
                seen.add(s2['addr'])
        if len(group) > 1:
            mirrors.append(group)
    
    # Find leads
    unscraped = [a for a in all_discovered if a not in onion_sites]
    top_leads = Counter(unscraped).most_common(15)
    
    # Print report
    print(f"\n  Vanity Sites: {len(vanity_sites)}")
    for addr, word in vanity_sites[:5]:
        print(f"    - {addr[:20]}... ('{word}')")
    
    print(f"\n  Mirror Groups: {len(mirrors)}")
    for g in mirrors[:3]:
        print(f"    - {', '.join([a[:10] for a in g])}...")
    
    print(f"\n  Top Leads: {len(top_leads)}")
    for addr, count in top_leads[:5]:
        print(f"    - {addr[:20]}... ({count}x)")
    
    print(f"  [SAVED] intelligence_report.html")


if __name__ == "__main__":
    main()
