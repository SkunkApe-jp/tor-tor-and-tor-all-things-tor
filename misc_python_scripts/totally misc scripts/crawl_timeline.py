#!/usr/bin/env python3
"""
Crawl Timeline - Temporal Scrape History

Shows when sites were scraped (based on file modification times)
and visualizes the crawl progression over time.
"""

import os
import json
import re
from pathlib import Path
from datetime import datetime
from collections import defaultdict


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
                    return ' '.join(title_match.group(1).strip().split())[:25]
        except Exception:
            pass
    return None


def get_file_mtime(filepath):
    """Get file modification time."""
    if os.path.exists(filepath):
        return datetime.fromtimestamp(os.path.getmtime(filepath))
    return None


def generate_crawl_timeline(scraped_data_dir):
    """Generate a crawl timeline visualization."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to analyze")
    
    # Collect timestamps and metrics
    site_data = []
    timestamps = []
    
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        
        # Get title
        html_file = os.path.join(site_dir, 'htmls', f"{onion_addr}.html")
        title = extract_title_from_html(html_file) or onion_addr[:20]
        
        # Get timestamps
        html_mtime = get_file_mtime(html_file)
        
        # Get image info
        has_image = False
        image_mtime = None
        for img_name in ["index.png", f"{onion_addr}.png"]:
            img_path = os.path.join(site_dir, 'images', img_name)
            if os.path.exists(img_path):
                has_image = True
                image_mtime = get_file_mtime(img_path)
                break
        
        # Count links
        outbound = 0
        discovered = 0
        
        urls_dir = os.path.join(site_dir, 'urls')
        if os.path.exists(urls_dir):
            for f in os.listdir(urls_dir):
                if f.endswith('_links.txt'):
                    with open(os.path.join(urls_dir, f), 'r') as lf:
                        outbound += sum(1 for line in lf if '.onion' in line)
        
        disc_dir = os.path.join(site_dir, 'discovered_links')
        if os.path.exists(disc_dir):
            for f in os.listdir(disc_dir):
                if f.endswith('_links.txt'):
                    with open(os.path.join(disc_dir, f), 'r') as lf:
                        discovered += sum(1 for line in lf if '.onion' in line)
        
        # Use HTML mtime as primary timestamp
        crawl_time = html_mtime or image_mtime
        if crawl_time:
            timestamps.append(crawl_time)
        
        site_data.append({
            'addr': onion_addr,
            'title': title,
            'crawl_time': crawl_time.isoformat() if crawl_time else None,
            'has_image': has_image,
            'outbound': outbound,
            'discovered': discovered,
            'total_links': outbound + discovered
        })
    
    # Sort by time
    site_data.sort(key=lambda x: x['crawl_time'] or '')
    
    # Calculate time range
    if timestamps:
        min_time = min(timestamps)
        max_time = max(timestamps)
        time_range = (max_time - min_time).total_seconds()
    else:
        min_time = datetime.now()
        max_time = datetime.now()
        time_range = 0
    
    print(f"\nCrawl Timeline Data:")
    print(f"  Sites: {len(site_data)}")
    print(f"  Time range: {min_time} to {max_time}")
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Crawl Timeline</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ margin: 0; overflow: auto; background: #0a0a0f; font-family: 'Segoe UI', sans-serif; }}
        #tooltip {{
            position: fixed; padding: 12px; background: rgba(30,30,40,0.95);
            border: 1px solid #444; border-radius: 8px; pointer-events: none;
            opacity: 0; z-index: 100; color: #eee; max-width: 300px;
            transition: opacity 0.2s; font-size: 12px;
        }}
        #header {{
            position: fixed; top: 0; left: 0; right: 0;
            background: rgba(10,10,15,0.95); padding: 15px 20px;
            border-bottom: 1px solid #222; z-index: 10;
        }}
        #header h1 {{ margin: 0; color: #fff; font-size: 18px; }}
        #stats {{
            position: fixed; top: 60px; left: 20px;
            background: rgba(30,30,40,0.9); padding: 12px;
            border-radius: 8px; border: 1px solid #222; z-index: 10;
            color: #aaa; font-size: 11px;
        }}
        .bar {{ cursor: pointer; }}
        .bar:hover {{ opacity: 0.8; }}
        .axis {{ stroke: #30363d; }}
        .axis-label {{ fill: #8b949e; font-size: 11px; }}
        .grid-line {{ stroke: #21262d; stroke-width: 0.5; }}
    </style>
</head>
<body>
    <div id="header"><h1>Crawl Timeline - Temporal Scrape History</h1></div>
    <div id="stats" id="stats"></div>
    <div id="tooltip"></div>

    <script>
        const sites = {json.dumps(site_data)};
        const minTime = new Date("{min_time.isoformat()}");
        const maxTime = new Date("{max_time.isoformat()}");
        
        const margin = {{top: 40, right: 250, bottom: 60, left: 100}};
        const width = Math.max(1200, window.innerWidth - 50);
        const height = Math.max(600, sites.length * 35 + margin.top + margin.bottom);
        
        const svg = d3.select("body").append("svg")
            .attr("width", width)
            .attr("height", height);
        
        const g = svg.append("g")
            .attr("transform", `translate(${{margin.left}},${{margin.top}})`);
        
        const innerWidth = width - margin.left - margin.right;
        const innerHeight = height - margin.top - margin.bottom;
        
        // Time scale
        const timeScale = d3.scaleTime()
            .domain([minTime, maxTime])
            .range([0, innerWidth]);
        
        // Y scale for sites
        const yScale = d3.scaleBand()
            .domain(sites.map((d, i) => i))
            .range([0, innerHeight])
            .padding(0.2);
        
        // Color scale for link count
        const maxLinks = d3.max(sites, d => d.total_links) || 1;
        const colorScale = d3.scaleSequential(d3.interpolateViridis)
            .domain([0, maxLinks]);
        
        // Draw grid lines
        const timeTicks = timeScale.ticks(d3.timeDay.every(1) || d3.timeHour.every(6));
        timeTicks.forEach(t => {{
            g.append("line")
                .attr("class", "grid-line")
                .attr("x1", timeScale(t))
                .attr("y1", 0)
                .attr("x2", timeScale(t))
                .attr("y2", innerHeight);
        }});
        
        // Draw axes
        g.append("g")
            .attr("class", "axis")
            .attr("transform", `translate(0,${{innerHeight}})`)
            .call(d3.axisBottom(timeScale)
                .ticks(d3.timeDay.every(1) || d3.timeHour.every(4))
                .tickFormat(d3.timeFormat("%b %d %H:%M")))
            .selectAll("text")
            .attr("transform", "rotate(-45)")
            .style("text-anchor", "end");
        
        // Draw bars
        const barHeight = Math.min(25, yScale.bandwidth());
        
        const bars = g.selectAll(".bar")
            .data(sites)
            .join("g")
            .attr("class", "bar")
            .attr("transform", (d, i) => `translate(0,${{yScale(i)}})`);
        
        // Bar rectangles
        bars.append("rect")
            .attr("x", d => {{
                const t = d.crawl_time ? new Date(d.crawl_time) : minTime;
                return timeScale(t);
            }})
            .attr("y", (innerHeight / sites.length - barHeight) / 2)
            .attr("width", d => {{
                const t = d.crawl_time ? new Date(d.crawl_time) : minTime;
                return Math.max(3, timeScale(t) - timeScale(minTime) + 5);
            }})
            .attr("height", barHeight)
            .attr("fill", d => colorScale(d.total_links))
            .attr("rx", 3);
        
        // Site labels
        bars.append("text")
            .attr("x", -10)
            .attr("y", barHeight / 2 + 4)
            .attr("text-anchor", "end")
            .attr("class", "axis-label")
            .attr("font-weight", "500")
            .text(d => d.title.length > 20 ? d.title.substring(0, 17) + "..." : d.title);
        
        // Link count labels
        bars.append("text")
            .attr("x", d => {{
                const t = d.crawl_time ? new Date(d.crawl_time) : minTime;
                return timeScale(t) + Math.max(3, timeScale(t) - timeScale(minTime) + 5) + 8;
            }})
            .attr("y", barHeight / 2 + 4)
            .attr("class", "axis-label")
            .attr("fill", "#4ade80")
            .text(d => d.total_links > 0 ? `${{d.total_links}} links` : '');
        
        // Image indicator
        bars.filter(d => d.has_image)
            .append("text")
            .attr("x", d => {{
                const t = d.crawl_time ? new Date(d.crawl_time) : minTime;
                return timeScale(t) + Math.max(3, timeScale(t) - timeScale(minTime) + 5) + 80;
            }})
            .attr("y", barHeight / 2 + 4)
            .attr("fill", "#fbbf24")
            .attr("font-size", "12px")
            .text("📸");
        
        // Tooltip
        bars.on("mouseover", (e, d) => {{
            const timeStr = d.crawl_time ? new Date(d.crawl_time).toLocaleString() : 'Unknown';
            d3.select("#tooltip")
                .style("opacity", 1)
                .html(`
                    <div style="font-weight: bold; color: #fff;">${{d.title}}</div>
                    <div style="color: #888; font-size: 10px; word-break: break-all;">${{d.addr}}</div>
                    <div style="margin-top: 8px;">
                        <div style="color: #aaa;">Crawled: <span style="color: #fff">${{timeStr}}</span></div>
                        <div style="color: #4ade80;">Outbound: ${{d.outbound}}</div>
                        <div style="color: #60a5fa;">Discovered: ${{d.discovered}}</div>
                        ${{d.has_image ? '<div style="color: #fbbf24;">📸 Has screenshot</div>' : ''}}
                    </div>
                `)
                .style("left", (e.pageX + 15) + "px")
                .style("top", (e.pageY - 15) + "px");
            
            d3.select(e.currentTarget).select("rect").attr("opacity", 0.7);
        }})
        .on("mouseout", (e) => {{
            d3.select("#tooltip").style("opacity", 0);
            d3.select(e.currentTarget).select("rect").attr("opacity", 1);
        }});
        
        // Update stats
        const withTime = sites.filter(s => s.crawl_time).length;
        const withImages = sites.filter(s => s.has_image).length;
        const totalLinks = sites.reduce((sum, s) => sum + s.total_links, 0);
        
        d3.select("#stats").html(`
            <strong>Crawl Statistics:</strong><br/>
            Sites crawled: ${{withTime}}/${{sites.length}}<br/>
            With screenshots: ${{withImages}}<br/>
            Total links found: ${{totalLinks}}<br/>
            Time span: ${{Math.round((maxTime - minTime) / (1000 * 60 * 60))}} hours
        `);
        
        // Add "now" line
        const now = new Date();
        if (now > maxTime) {{
            g.append("line")
                .attr("x1", timeScale(now))
                .attr("y1", 0)
                .attr("x2", timeScale(now))
                .attr("y2", innerHeight)
                .attr("stroke", "#ef4444")
                .attr("stroke-width", 2)
                .attr("stroke-dasharray", "5,5");
            
            g.append("text")
                .attr("x", timeScale(now) + 5)
                .attr("y", 15)
                .attr("fill", "#ef4444")
                .attr("font-size", "10px")
                .text("Now");
        }}
    </script>
</body>
</html>"""
    
    output_file = os.path.join(scraped_data_dir, "crawl_timeline.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\nCrawl Timeline created at {output_file}")
    return output_file


def main():
    scraped_data_dir = "../scraped_data"
    
    if not os.path.exists(scraped_data_dir):
        scraped_data_dir = "scraped_data"
        if not os.path.exists(scraped_data_dir):
            print("Error: scraped_data directory not found")
            return
    
    generate_crawl_timeline(scraped_data_dir)


if __name__ == "__main__":
    main()
