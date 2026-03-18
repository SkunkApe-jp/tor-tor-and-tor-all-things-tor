#!/usr/bin/env python3
"""
Word Cloud Gallery - Optimized for dense, center-focused word clouds with outlines.
"""

import os
import json
import re
from pathlib import Path
from collections import Counter

def get_onion_sites(scraped_data_dir):
    if not os.path.exists(scraped_data_dir): return []
    return [d for d in os.listdir(scraped_data_dir) 
            if os.path.isdir(os.path.join(scraped_data_dir, d)) 
            and re.match(r'^[a-z2-7]{16,56}$', d)]

def extract_title_from_line(line):
    match = re.search(r'\[\[([^\]]+)\]\]|\[([^\]]+)\]', line)
    return (match.group(1) or match.group(2)) if match else line.strip()

def extract_titles_from_file(file_path):
    titles = []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if t := extract_title_from_line(line.strip()): titles.append(t)
        except: pass
    return titles

def extract_words(text, min_length=3):
    stop_words = {'the', 'and', 'that', 'this', 'with', 'for', 'are', 'was', 'were', 'been',
                  'have', 'has', 'had', 'will', 'would', 'could', 'should', 'from', 'into', 
                  'about', 'there', 'their', 'they', 'them', 'which', 'while', 'where', 'when', 
                  'what', 'who', 'some', 'such', 'very', 'just', 'also', 'more', 'most', 'click', 'page'}
    words = re.findall(r'\b[a-zA-Z]{' + str(min_length) + r',}\b', text.lower())
    return [w for w in words if w not in stop_words]

def generate_word_cloud_gallery(scraped_data_dir):
    onion_sites = get_onion_sites(scraped_data_dir)
    site_words = {}

    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        all_text = []

        # Gather titles from standard locations
        for p in ['discovered_links/index_titles.txt', 'website_identity/index_title.txt']:
            all_text.extend(extract_titles_from_file(os.path.join(site_dir, p)))

        words = extract_words(' '.join(all_text))
        top_words = Counter(words).most_common(60) # Increased count for density

        image_path = ""
        for img_name in ["index.png", f"{onion_addr}.png"]:
            if os.path.exists(os.path.join(site_dir, 'images', img_name)):
                image_path = f"{onion_addr}/images/{img_name}"
                break

        site_words[onion_addr] = {
            'title': onion_addr[:20],
            'words': [{"text": k, "size": v} for k, v in top_words],
            'image': image_path
        }

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Visual Word Cloud Gallery</title>
    <style>
        body {{ margin: 0; padding: 40px; background: #fdfdfd; font-family: sans-serif; }}
        h1 {{ text-align: center; color: #222; margin-bottom: 40px; font-size: 32px; }}
        #gallery {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(500px, 1fr)); gap: 30px; }}
        .card {{ background: white; border: 1px solid #ddd; border-radius: 4px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); overflow: hidden; }}
        .card-header {{ padding: 12px 16px; border-bottom: 1px solid #eee; display: flex; align-items: center; gap: 10px; font-weight: bold; background: #fafafa; }}
        .card-header img {{ width: 24px; height: 24px; border-radius: 2px; }}
        .card-body {{ height: 350px; display: flex; align-items: center; justify-content: center; }}
        .word-text {{ font-weight: bold; paint-order: stroke fill; cursor: default; }}
    </style>
</head>
<body>
    <h1>Site Summaries</h1>
    <div id="gallery"></div>

    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://unpkg.com/d3-cloud@1.2.5/build/d3-cloud.min.js"></script>
    <script>
        const siteData = {json.dumps(site_words)};
        // Palette inspired by the reference image
        const colors = ['#5b7231', '#d19a2e', '#9b3d22', '#6b4c9a', '#4a7c59', '#c15c37', '#3e5c76'];

        function createCloud(data, containerId) {{
            const words = data.words;
            if (!words.length) return;

            const width = 500, height = 350;
            
            // Power scale: most frequent words get MUCH larger
            const fontSize = d3.scalePow()
                .exponent(2)
                .domain([d3.min(words, d => d.size), d3.max(words, d => d.size)])
                .range([12, 120]);

            const layout = d3.layout.cloud()
                .size([width, height])
                .words(words.map(d => ({{text: d.text, size: fontSize(d.size)}})))
                .padding(2) // Tight padding for density
                .rotate(() => (Math.random() > 0.9 ? 90 : 0)) // Mostly horizontal
                .font("Impact")
                .fontSize(d => d.size)
                .on("end", (placedWords) => {{
                    const svg = d3.select("#" + containerId).append("svg")
                        .attr("width", width).attr("height", height)
                        .append("g")
                        .attr("transform", `translate(${{width/2}},${{height/2}})`);

                    svg.selectAll("text")
                        .data(placedWords)
                        .enter().append("text")
                        .attr("class", "word-text")
                        .style("font-size", d => d.size + "px")
                        .style("font-family", "Impact, sans-serif")
                        .style("fill", (d, i) => colors[i % colors.length])
                        // White outline for readability and pop
                        .style("stroke", "#fff")
                        .style("stroke-width", "1.5px")
                        .attr("text-anchor", "middle")
                        .attr("transform", d => `translate(${{[d.x, d.y]}}) rotate(${{d.rotate}})`)
                        .text(d => d.text);
                }});

            layout.start();
        }}

        Object.entries(siteData).forEach(([addr, data]) => {{
            const id = `cloud-${{addr.replace(/[^a-z0-9]/g, '')}}`;
            const card = document.createElement('div');
            card.className = 'card';
            card.innerHTML = `
                <div class="card-header">
                    ${{data.image ? `<img src="${{data.image}}">` : ''}}
                    <span>${{addr.substring(0, 16)}}...</span>
                </div>
                <div class="card-body" id="${{id}}"></div>`;
            document.getElementById('gallery').appendChild(card);
            createCloud(data, id);
        }});
    </script>
</body>
</html>"""

    output = os.path.join(scraped_data_dir, "word_cloud_gallery.html")
    with open(output, 'w', encoding='utf-8') as f: f.write(html_content)
    print(f"Created gallery at: {output}")

if __name__ == "__main__":
    # Use absolute path relative to script location (scraped_data is at ../scraped_data)
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    generate_word_cloud_gallery(str(scraped_data_path))
