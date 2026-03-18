#!/usr/bin/env python3
"""
Discovery Frontier - Sankey/Alluvial Diagram

Shows the "flow" of discovery from seed sites through linked sites to 
unscraped discovered links. Three columns visualize the crawling progress.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path
from collections import defaultdict


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


def extract_title_from_html(html_file_path):
    """Extract title from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()
                    return ' '.join(title.split())[:50]
        except Exception:
            pass
    return None


def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and re.match(r'^[a-z2-7]{16,56}$', item):
            onion_dirs.append(item)
    return onion_dirs


def generate_discovery_frontier(scraped_data_dir):
    """Generate a Sankey diagram showing the discovery flow."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} seed sites to analyze")
    
    # Column 1: Seed sites (scraped)
    # Column 2: Linked sites that were also scraped
    # Column 3: Discovered links (not scraped)
    
    seed_sites = {}  # URL -> {title, outbound_links}
    linked_scraped = {}  # URL -> {title, inbound_count, source_sites}
    discovered_only = {}  # URL -> {inbound_count, source_sites}
    
    # Process each seed site
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        root_url = f"http://{onion_addr}.onion"
        
        # Get title
        html_file = os.path.join(site_dir, 'htmls', f"{onion_addr}.html")
        title = extract_title_from_html(html_file) or f"{onion_addr[:16]}..."
        
        # Get outbound links from both folders
        outbound_links = []
        for d in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, d)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        outbound_links.extend(read_links_file(os.path.join(path, f)))
        
        outbound_links = list(set(outbound_links))
        seed_sites[root_url] = {'title': title, 'outbound_links': outbound_links, 'addr': onion_addr}
        
        # Categorize linked sites
        for link in outbound_links:
            onion_match = re.search(r'([a-z2-7]{16,56})\.onion', link)
            if onion_match:
                linked_addr = onion_match.group(1)
                
                # Check if this linked site was also scraped
                linked_site_dir = os.path.join(scraped_data_dir, linked_addr)
                is_scraped = os.path.exists(linked_site_dir)
                
                if is_scraped:
                    linked_url = f"http://{linked_addr}.onion"
                    if linked_url not in linked_scraped:
                        linked_html = os.path.join(linked_site_dir, 'htmls', f"{linked_addr}.html")
                        linked_title = extract_title_from_html(linked_html) or f"{linked_addr[:16]}..."
                        linked_scraped[linked_url] = {
                            'title': linked_title,
                            'inbound_count': 0,
                            'source_sites': [],
                            'addr': linked_addr
                        }
                    linked_scraped[linked_url]['inbound_count'] += 1
                    linked_scraped[linked_url]['source_sites'].append(root_url)
                else:
                    if link not in discovered_only:
                        discovered_only[link] = {
                            'inbound_count': 0,
                            'source_sites': [],
                            'addr': linked_addr
                        }
                    discovered_only[link]['inbound_count'] += 1
                    discovered_only[link]['source_sites'].append(root_url)
    
    # Build Sankey data
    nodes = []
    links = []
    node_index = {}
    
    # Add seed sites (Column 1)
    col1_x = 100
    for i, (url, data) in enumerate(seed_sites.items()):
        node_index[url] = len(nodes)
        nodes.append({
            'id': url,
            'name': data['title'],
            'column': 0,
            'x': col1_x,
            'y': i * 40 + 50,
            'type': 'seed',
            'addr': data['addr'],
            'outbound_count': len(data['outbound_links'])
        })
    
    # Add linked scraped sites (Column 2)
    col2_x = 400
    for i, (url, data) in enumerate(sorted(linked_scraped.items(), key=lambda x: -x[1]['inbound_count'])[:50]):
        node_index[url] = len(nodes)
        nodes.append({
            'id': url,
            'name': data['title'],
            'column': 1,
            'x': col2_x,
            'y': i * 35 + 50,
            'type': 'linked_scraped',
            'addr': data['addr'],
            'inbound_count': data['inbound_count']
        })
    
    # Add discovered-only sites (Column 3)
    col3_x = 700
    for i, (url, data) in enumerate(sorted(discovered_only.items(), key=lambda x: -x[1]['inbound_count'])[:100]):
        node_index[url] = len(nodes)
        nodes.append({
            'id': url,
            'name': url.split('/')[-1][:30] + '...',
            'column': 2,
            'x': col3_x,
            'y': i * 25 + 50,
            'type': 'discovered',
            'addr': data['addr'],
            'inbound_count': data['inbound_count']
        })
    
    # Create links
    for url, data in seed_sites.items():
        if url not in node_index:
            continue
        source_idx = node_index[url]
        
        for link in data['outbound_links']:
            if link in node_index:
                target_idx = node_index[link]
                links.append({
                    'source': source_idx,
                    'target': target_idx,
                    'value': 1
                })
    
    # Aggregate links to avoid too many paths
    aggregated_links = defaultdict(int)
    for link in links:
        key = (link['source'], link['target'])
        aggregated_links[key] += 1
    
    final_links = []
    for (source, target), value in aggregated_links.items():
        final_links.append({'source': source, 'target': target, 'value': value})
    
    print(f"\nSankey Data:")
    print(f"  Column 1 (Seed Sites): {len(seed_sites)}")
    print(f"  Column 2 (Linked & Scraped): {len(linked_scraped)}")
    print(f"  Column 3 (Discovered Only): {len(discovered_only)}")
    print(f"  Total nodes: {len(nodes)}, Total links: {len(final_links)}")
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Discovery Frontier</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: auto; background: #0d1117; font-family: 'Segoe UI', sans-serif; }}
        #container {{ width: 100%; height: 100vh; overflow: auto; }}
        #tooltip {{
            position: fixed; padding: 12px; background: rgba(30,30,40,0.95);
            border: 1px solid #444; border-radius: 8px; pointer-events: none;
            opacity: 0; z-index: 100; color: #eee; max-width: 350px;
            transition: opacity 0.2s; font-size: 12px;
        }}
        #header {{
            position: fixed; top: 0; left: 0; right: 0;
            background: rgba(13,17,23,0.9); padding: 15px 20px;
            border-bottom: 1px solid #333; z-index: 10;
            display: flex; justify-content: space-between; align-items: center;
        }}
        #header h1 {{ margin: 0; color: #fff; font-size: 18px; }}
        #stats {{ color: #888; font-size: 13px; }}
        .column-label {{
            fill: #888; font-size: 13px; font-weight: bold;
        }}
        .node-rect {{ stroke: #444; stroke-width: 1px; }}
        .link {{ fill: none; stroke-opacity: 0.15; }}
        .link:hover {{ stroke-opacity: 0.4; }}
        #legend {{
            position: fixed; bottom: 20px; left: 20px;
            background: rgba(30,30,40,0.9); padding: 12px;
            border-radius: 8px; border: 1px solid #333; z-index: 10;
        }}
        .legend-item {{ display: flex; align-items: center; margin: 5px 0; font-size: 12px; color: #aaa; }}
        .legend-color {{ width: 14px; height: 14px; margin-right: 8px; border-radius: 3px; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Discovery Frontier - Crawling Progress</h1>
        <div id="stats">{len(nodes)} nodes | {len(final_links)} connections</div>
    </div>
    <div id="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #238636;"></div>
            <span>Seed Sites (Scraped)</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #1f6feb;"></div>
            <span>Linked & Scraped</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #8957e5;"></div>
            <span>Discovered (Not Scraped)</span>
        </div>
    </div>
    <div id="tooltip"></div>
    <div id="container"></div>

    <script>
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};
        
        const margin = {{top: 80, right: 50, bottom: 50, left: 50}};
        const width = Math.max(1200, window.innerWidth - 100);
        const height = Math.max(800, nodes.length * 8 + 200);
        
        const svg = d3.select("#container")
            .append("svg")
            .attr("width", width)
            .attr("height", height);
        
        const g = svg.append("g").attr("transform", `translate(${{margin.left}},${{margin.top}})`);
        
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;
        
        // Column positions
        const columns = [0, 1, 2];
        const columnWidth = innerWidth / 3;
        const columnX = [50, 50 + columnWidth, 50 + columnWidth * 2];
        const columnNames = ["Seed Sites", "Linked & Scraped", "Discovered Only"];
        
        // Column labels
        g.selectAll(".column-label")
            .data(columnNames)
            .join("text")
            .attr("class", "column-label")
            .attr("x", (d, i) => columnX[i])
            .attr("y", -20)
            .attr("text-anchor", "middle")
            .text(d => d);
        
        // Color scale
        const colorScale = d3.scaleOrdinal()
            .domain(['seed', 'linked_scraped', 'discovered'])
            .range(['#238636', '#1f6feb', '#8957e5']);
        
        // Node width
        const nodeWidth = 20;
        
        // Sort nodes by column and position
        nodes.forEach((d, i) => {{
            d.y = d.column * 30 + (i % 50) * 15 + 30;
            d.height = d.type === 'seed' ? 25 : (d.type === 'linked_scraped' ? 20 : 15);
        }});
        
        // Draw links first (behind nodes)
        const linkGroup = g.append("g").attr("class", "links");
        
        links.forEach(link => {{
            const source = nodes[link.source];
            const target = nodes[link.target];
            if (!source || !target) return;
            
            const path = g.append("path")
                .attr("class", "link")
                .attr("d", (() => {{
                    const x1 = source.x + nodeWidth;
                    const y1 = source.y + source.height / 2;
                    const x2 = target.x;
                    const y2 = target.y + target.height / 2;
                    const cx1 = x1 + (x2 - x1) / 2;
                    const cx2 = x1 + (x2 - x1) / 2;
                    return `M${{x1}},${{y1}} C${{cx1}},${{y1}} ${{cx2}},${{y2}} ${{x2}},${{y2}}`;
                }})())
                .attr("stroke", colorScale(source.type))
                .attr("stroke-width", Math.min(link.value * 2, 10))
                .on("mouseover", (e) => {{
                    d3.select(e.target).attr("stroke-opacity", 0.5);
                }})
                .on("mouseout", (e) => {{
                    d3.select(e.target).attr("stroke-opacity", 0.15);
                }});
        }});
        
        // Draw nodes
        const nodeGroup = g.append("g").attr("class", "nodes");
        
        const node = nodeGroup.selectAll("g")
            .data(nodes)
            .join("g")
            .attr("transform", d => `translate(${{d.x}},${{d.y}})`);
        
        node.append("rect")
            .attr("class", "node-rect")
            .attr("width", nodeWidth)
            .attr("height", d => d.height)
            .attr("fill", d => colorScale(d.type))
            .attr("rx", 3)
            .on("mouseover", (e, d) => {{
                const tooltip = d3.select("#tooltip");
                tooltip.transition().duration(200).style("opacity", 1);
                tooltip.html(`
                    <div style="font-weight: bold; color: #fff; margin-bottom: 5px;">${{d.name}}</div>
                    <div style="color: #888; font-size: 11px;">${{d.id}}</div>
                    <div style="margin-top: 8px; color: #aaa;">
                        Type: ${{d.type === 'seed' ? 'Seed Site' : (d.type === 'linked_scraped' ? 'Linked & Scraped' : 'Discovered Only')}}<br/>
                        ${{d.outbound_count ? `Outbound links: ${{d.outbound_count}}` : ''}}
                        ${{d.inbound_count ? `Inbound links: ${{d.inbound_count}}` : ''}}
                    </div>
                `);
                tooltip.style("left", (e.pageX + 15) + "px").style("top", (e.pageY - 15) + "px");
                d3.select(e.target).attr("stroke", "#fff").attr("stroke-width", 2);
            }})
            .on("mouseout", (e, d) => {{
                d3.select("#tooltip").transition().duration(300).style("opacity", 0);
                d3.select(e.target).attr("stroke", "#444").attr("stroke-width", 1);
            }})
            .on("click", (e, d) => {{
                // Open the site's visualization if available
                const addr = d.addr;
                const vizPath = `./${{addr}}/visualizations/${{addr}}_viz.html`;
                window.open(vizPath, '_blank');
            }});
        
        // Node labels
        node.append("text")
            .attr("x", nodeWidth + 5)
            .attr("y", d => d.height / 2 + 4)
            .attr("font-size", "10px")
            .attr("fill", "#aaa")
            .text(d => d.name)
            .attr("pointer-events", "none");
        
        // Add connection count labels on nodes
        node.filter(d => d.inbound_count || d.outbound_count)
            .append("text")
            .attr("x", -5)
            .attr("y", -5)
            .attr("font-size", "9px")
            .attr("fill", "#fff")
            .attr("font-weight", "bold")
            .text(d => d.inbound_count || d.outbound_count || '');
    </script>
</body>
</html>"""
    
    output_file = os.path.join(scraped_data_dir, "discovery_frontier.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\nDiscovery Frontier created at {output_file}")
    return output_file


def main():
    scraped_data_dir = "../scraped_data"
    
    if not os.path.exists(scraped_data_dir):
        scraped_data_dir = "scraped_data"
        if not os.path.exists(scraped_data_dir):
            print("Error: scraped_data directory not found")
            return
    
    generate_discovery_frontier(scraped_data_dir)


if __name__ == "__main__":
    main()
