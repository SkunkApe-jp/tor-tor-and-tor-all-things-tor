#!/usr/bin/env python3
"""
Generic Word Cloud Generator using D3.js
Creates a standalone HTML file with a proper word cloud where font size scales with frequency.
"""

import os
import json
import re
from pathlib import Path
from collections import Counter

def extract_words(text, min_length=3):
    """Extract words from text, filtering stop words."""
    stop_words = {
        'the', 'and', 'that', 'this', 'with', 'for', 'are', 'was', 'were', 'been',
        'have', 'has', 'had', 'will', 'would', 'could', 'should', 'from', 'into',
        'about', 'there', 'their', 'they', 'them', 'which', 'while', 'where', 'when',
        'what', 'who', 'some', 'such', 'very', 'just', 'also', 'more', 'most',
        'click', 'page', 'like', 'one', 'two', 'get', 'all', 'out', 'other', 'new'
    }
    words = re.findall(r'\b[a-zA-Z]{' + str(min_length) + r',}\b', text.lower())
    return [w for w in words if w not in stop_words]

def generate_word_cloud(words_dict, output_path="word_cloud.html"):
    """
    Generate a standalone word cloud HTML.
    
    Args:
        words_dict: dict of {word: count} or list of words
        output_path: path to output HTML file
    """
    # Convert list to frequency dict if needed
    if isinstance(words_dict, list):
        words_dict = dict(Counter(words_dict))
    
    # Sort by frequency and take top 100
    sorted_words = sorted(words_dict.items(), key=lambda x: x[1], reverse=True)[:100]
    words_json = json.dumps([{"text": k, "size": v} for k, v in sorted_words])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Word Cloud</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }}
        #container {{
            width: 100%;
            max-width: 1200px;
            height: 80vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .word {{
            font-weight: bold;
            cursor: default;
            transition: opacity 0.2s;
        }}
        .word:hover {{
            opacity: 0.7;
        }}
        #title {{
            position: absolute;
            top: 20px;
            color: #eee;
            font-size: 24px;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div id="title">Word Cloud</div>
    <div id="container"></div>
    
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://unpkg.com/d3-cloud@1.2.5/build/d3-cloud.min.js"></script>
    <script>
        const words = {words_json};
        
        // Color palette
        const colors = d3.scaleOrdinal()
            .domain(d3.range(words.length))
            .range(['#e63946', '#f4a261', '#2a9d8f', '#e9c46a', '#264653', '#a8dadc', '#457b9d', '#1d3557']);
        
        // Power scale for dramatic size difference
        const minCount = d3.min(words, d => d.size);
        const maxCount = d3.max(words, d => d.size);
        
        const fontSize = d3.scalePow()
            .exponent(2.5)
            .domain([minCount, maxCount])
            .range([14, 140]);
        
        // Spiral type: 'archimedean' for circular, 'rectangular' for boxy
        const layout = d3.layout.cloud()
            .size([1000, 600])
            .words(words.map(d => ({{ text: d.text, size: fontSize(d.size) }})))
            .padding(3)
            .rotate(() => (Math.random() > 0.85 ? 90 : 0))
            .font('Impact')
            .fontSize(d => d.size)
            .spiral('archimedean')
            .on('end', draw);
        
        layout.start();
        
        function draw(placedWords) {{
            const svg = d3.select('#container').append('svg')
                .attr('width', '100%')
                .attr('height', '100%')
                .attr('viewBox', '0 0 1000 600')
                .attr('preserveAspectRatio', 'xMidYMid meet')
                .append('g')
                .attr('transform', 'translate(500,300)');
            
            svg.selectAll('text')
                .data(placedWords)
                .enter().append('text')
                .attr('class', 'word')
                .style('font-size', d => d.size + 'px')
                .style('font-family', 'Impact, sans-serif')
                .style('fill', (d, i) => colors(i))
                .style('stroke', '#fff')
                .style('stroke-width', '0.8px')
                .attr('text-anchor', 'middle')
                .attr('transform', d => `translate(${{d.x}},${{d.y}}) rotate(${{d.rotate}})`)
                .text(d => d.text)
                .append('title')
                .text(d => `${{d.text}}: ${{words.find(w => w.text === d.text).size}}`);
        }}
    </script>
</body>
</html>"""
    
    output = Path(output_path)
    output.write_text(html, encoding='utf-8')
    print(f"Created word cloud at: {output.absolute()}")
    return str(output.absolute())

if __name__ == "__main__":
    # Example usage with sample data
    sample_text = """
    Python is a programming language. Python is great for data science.
    Machine learning and deep learning are popular fields.
    Data science uses Python extensively. Programming requires practice.
    Learning Python is fun. Machine learning models need data.
    Deep learning neural networks are powerful. Python libraries help developers.
    """
    
    words = extract_words(sample_text)
    generate_word_cloud(words, "sample_word_cloud.html")
