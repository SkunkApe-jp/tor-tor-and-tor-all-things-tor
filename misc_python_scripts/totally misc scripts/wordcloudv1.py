#!/usr/bin/env python3
"""
Onion Word Cloud Generator

Analyzes website titles to identify the most common themes across the network.
Generates an interactive HTML word cloud.
"""

import os
import json
import re
from collections import Counter

# Common words to ignore + Darknet specific filler
STOP_WORDS = {
    'the', 'and', 'for', 'your', 'with', 'from', 'this', 'that', 'site', 'website',
    'onion', 'hidden', 'service', 'link', 'links', 'directory', 'index', 'wiki',
    'official', 'home', 'welcome', 'version', 'v3', 'v2', 'tor', 'dark', 'web',
    'best', 'top', 'new', 'private', 'secure', 'anonymous', 'anon', 'online'
}

def extract_words_from_data(scraped_data_dir):
    """Scan website_titles and htmls to build a frequency map of words."""
    words = []
    
    # Iterate through all site folders
    if not os.path.exists(scraped_data_dir):
        return []

    for onion_addr in os.listdir(scraped_data_dir):
        site_path = os.path.join(scraped_data_dir, onion_addr)
        if not os.path.isdir(site_path):
            continue

        title_text = ""
        # 1. Try website_titles folder first
        title_file = os.path.join(site_path, "website_titles", f"{onion_addr}.txt")
        if os.path.exists(title_file):
            try:
                with open(title_file, 'r', encoding='utf-8') as f:
                    title_text = f.read()
            except: pass
        
        # 2. Try htmls as backup
        if not title_text:
            html_file = os.path.join(site_path, "htmls", f"{onion_addr}.html")
            if os.path.exists(html_file):
                try:
                    with open(html_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        match = re.search(r'<title[^>]*>(.*?)</title>', content, re.I | re.S)
                        if match: title_text = match.group(1)
                except: pass

        if title_text:
            # Clean and tokenize
            # Remove non-alphabetic characters (keep only words)
            tokens = re.findall(r'[a-z]{3,}', title_text.lower())
            filtered = [t for t in tokens if t not in STOP_WORDS]
            words.extend(filtered)

    return Counter(words).most_common(150) # Top 150 words

def generate_word_cloud_html(word_counts, output_path):
    # Prepare data for D3 (format: {text: "word", size: frequency})
    # Scale sizes for visualization (max size 100, min 20)
    if not word_counts:
        print("No words found to generate cloud.")
        return

    max_count = word_counts[0][1]
    cloud_data = [
        {"text": word, "size": max(20, (count / max_count) * 100)}
        for word, count in word_counts
    ]

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Onion Network Word Cloud</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3-cloud/1.2.5/d3.layout.cloud.min.js"></script>
    <style>
        body {{ 
            margin: 0; 
            background-color: #050505; 
            color: #eee; 
            font-family: 'Helvetica Neue', Arial, sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            height: 100vh;
            overflow: hidden;
        }}
        #header {{
            padding: 20px;
            text-align: center;
            background: linear-gradient(180deg, #111 0%, transparent 100%);
            width: 100%;
        }}
        #cloud-container {{
            flex-grow: 1;
            width: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .word:hover {{
            fill: #fff !important;
            filter: drop-shadow(0 0 5px #fff);
            cursor: default;
        }}
    </style>
</head>
<body>
    <div id="header">
        <h1 style="margin:0; letter-spacing: 2px;">NETWORK THEMES</h1>
        <p style="opacity: 0.5;">Extracted from {len(cloud_data)} site titles</p>
    </div>
    <div id="cloud-container"></div>

    <script>
        const words = {json.dumps(cloud_data)};
        const width = window.innerWidth;
        const height = window.innerHeight - 100;

        const layout = d3.layout.cloud()
            .size([width, height])
            .words(words)
            .padding(5)
            .rotate(() => (Math.random() > 0.5 ? 0 : 90))
            .font("Impact")
            .fontSize(d => d.size)
            .on("end", draw);

        layout.start();

        function draw(words) {{
            d3.select("#cloud-container").append("svg")
                .attr("width", layout.size()[0])
                .attr("height", layout.size()[1])
                .append("g")
                .attr("transform", "translate(" + layout.size()[0] / 2 + "," + layout.size()[1] / 2 + ")")
                .selectAll("text")
                .data(words)
                .enter().append("text")
                .attr("class", "word")
                .style("font-size", d => d.size + "px")
                .style("font-family", "Impact")
                .style("fill", () => d3.interpolateWarm(Math.random()))
                .attr("text-anchor", "middle")
                .attr("transform", d => "translate(" + [d.x, d.y] + ")rotate(" + d.rotate + ")")
                .text(d => d.text);
        }}

        window.addEventListener('resize', () => location.reload());
    </script>
</body>
</html>"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Word cloud generated at: {output_path}")

def main():
    # Use absolute path relative to script location
    from pathlib import Path
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()
    output_file = scraped_data_path / "network_word_cloud.html"

    print("Analyzing network titles and content...")
    word_counts = extract_words_from_data(str(scraped_data_path))
    generate_word_cloud_html(word_counts, str(output_file))

if __name__ == "__main__":
    main()
