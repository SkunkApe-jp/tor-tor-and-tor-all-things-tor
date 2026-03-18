#!/usr/bin/env python3
"""
Onion Network Influence Diverging Chart

Visualizes which sites are "Authorities" (Destinations) 
vs "Hubs" (Directories) using a Diverging Bar Chart.
"""

import os
import json
import re
from collections import defaultdict

def generate_diverging_data(scraped_data_dir):
    onion_dirs = [d for d in os.listdir(scraped_data_dir) 
                  if os.path.isdir(os.path.join(scraped_data_dir, d)) and len(d) >= 16]

    inbound = defaultdict(int)
    outbound = defaultdict(int)
    titles = {}

    # Calculate Outbound and get Titles
    for onion in onion_dirs:
        # Get Title
        titles[onion] = onion[:16] # Default
        title_path = os.path.join(scraped_data_dir, onion, "website_titles", f"{onion}.txt")
        if os.path.exists(title_path):
            with open(title_path, 'r') as f: titles[onion] = f.read().strip()[:30]

        # Count Outbound
        path = os.path.join(scraped_data_dir, onion, "urls")
        if os.path.exists(path):
            unique_links = set()
            for f in os.listdir(path):
                with open(os.path.join(path, f), 'r') as file:
                    found = re.findall(r'([a-z2-7]{16,56})\.onion', file.read())
                    for link in found:
                        if link != onion: 
                            unique_links.add(link)
                            inbound[link] += 1
            outbound[onion] = len(unique_links)

    # Compile the "Influence Score"
    # Influence = Outbound - Inbound
    # Negative = Authority (Destination)
    # Positive = Hub (Navigator)
    influence_data = []
    for onion in onion_dirs:
        score = outbound[onion] - inbound[onion]
        influence_data.append({
            "name": titles[onion],
            "value": score,
            "in": inbound[onion],
            "out": outbound[onion]
        })

    # Sort by value
    influence_data.sort(key=lambda x: x["value"])
    return influence_data

def generate_diverging_html(data, output_path):
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Network Influence: Authority vs Hub</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{ background: #fff; font-family: 'Segoe UI', sans-serif; display: flex; flex-direction: column; align-items: center; }}
        .bar.negative {{ fill: #ff7f50; }}
        .bar.positive {{ fill: #4682b4; }}
        .axis text {{ font-size: 11px; }}
        .label {{ font-size: 12px; font-weight: bold; }}
        #chart-container {{ margin-top: 50px; }}
        .tooltip {{
            position: absolute; padding: 10px; background: rgba(0,0,0,0.8);
            color: white; border-radius: 4px; pointer-events: none; opacity: 0;
        }}
    </style>
</head>
<body>
    <h1>Network Influence Profile</h1>
    <p style="color: #666;">&larr; Authority (Destination) | Hub (Navigator) &rarr;</p>
    <div id="chart-container"></div>
    <div class="tooltip" id="tooltip"></div>

    <script>
        const data = {json.dumps(data)};
        const margin = {{top: 30, right: 60, bottom: 40, left: 200}};
        const width = 900 - margin.left - margin.right;
        const height = (data.length * 25);

        const svg = d3.select("#chart-container").append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g").attr("transform", `translate(${{margin.left}},${{margin.top}})`);

        const x = d3.scaleLinear()
            .domain([d3.min(data, d => d.value), d3.max(data, d => d.value)])
            .range([0, width]);

        const y = d3.scaleBand()
            .domain(data.map(d => d.name))
            .range([0, height])
            .padding(0.2);

        // Draw Bars
        svg.selectAll(".bar")
            .data(data).enter().append("rect")
            .attr("class", d => "bar " + (d.value < 0 ? "negative" : "positive"))
            .attr("x", d => x(Math.min(0, d.value)))
            .attr("y", d => y(d.name))
            .attr("width", d => Math.abs(x(d.value) - x(0)))
            .attr("height", y.bandwidth())
            .on("mouseover", (e, d) => {{
                d3.select("#tooltip").style("opacity", 1)
                    .html(`Inbound: ${{d.in}}<br/>Outbound: ${{d.out}}<br/>Net: ${{d.value}}`)
                    .style("left", (e.pageX + 10) + "px").style("top", (e.pageY - 10) + "px");
            }})
            .on("mouseout", () => d3.select("#tooltip").style("opacity", 0));

        // Add Names
        svg.append("g")
            .attr("class", "y axis")
            .attr("transform", `translate(${{x(0)}}, 0)`)
            .call(d3.axisLeft(y).tickSize(0).tickPadding(10))
            .selectAll("text")
            .attr("text-anchor", d => {{
                const item = data.find(i => i.name === d);
                return item.value < 0 ? "start" : "end";
            }})
            .attr("dx", d => {{
                const item = data.find(i => i.name === d);
                return item.value < 0 ? 10 : -10;
            }});

        // Add X Axis
        svg.append("g")
            .attr("transform", `translate(0,${{height}})`)
            .call(d3.axisBottom(x));

        // Center line
        svg.append("line")
            .attr("x1", x(0)).attr("x2", x(0))
            .attr("y1", 0).attr("y2", height)
            .attr("stroke", "#000").attr("stroke-width", 1);

    </script>
</body>
</html>"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

if __name__ == "__main__":
    data = generate_diverging_data("../scraped_data")
    generate_diverging_html(data, "../scraped_data/network_influence_diverging.html")
    print("Diverging chart generated.")
