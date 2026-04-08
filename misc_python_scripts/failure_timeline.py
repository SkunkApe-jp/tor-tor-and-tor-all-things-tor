#!/usr/bin/env python3
import os
import re
import json
import argparse
from collections import defaultdict

def parse_scraper_log(log_path):
    """Parses the unified_scraper.log file into a structured dictionary."""
    if not os.path.exists(log_path):
        return {}

    # Regex captures: [timestamp] url -> STATUS (details)
    # Support v2 (16 chars), v3 (56 chars), and vanity addresses (1-56 chars)
    log_pattern = re.compile(r'\[(.*?)\] (https?://([a-z2-7]{1,56})\.onion/?) -> (\w+) \((.*?)\)')

    onion_history = defaultdict(list)

    if os.path.exists(log_path):
        with open(log_path, 'r') as f:
            for line in f:
                match = log_pattern.search(line)
                if match:
                    timestamp_str, _, onion_addr, status, details = match.groups()
                    onion_history[onion_addr].append({
                        'timestamp': timestamp_str,
                        'status': status,
                        'details': details
                    })
    return onion_history

def generate_html(data, output_file):
    # Filter for only failed onions for the autocomplete list
    failed_onions = [addr for addr, history in data.items() if any(h['status'] == 'FAIL' for h in history)]
    
    json_data = json.dumps(data)
    json_failed_list = json.dumps(failed_onions)
    
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Onion Failure Tracer</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {{
            --bg: #050505;
            --glass: rgba(255, 255, 255, 0.03);
            --border: rgba(255, 255, 255, 0.08);
            --text: #777;
            --accent: #ffffff;
            --success-color: #ffffff;
            --fail-color: #333333;
        }}

        body {{
            margin: 0; padding: 0;
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Inter', system-ui, sans-serif;
            display: flex; flex-direction: column; align-items: center;
            min-height: 100vh; overflow-x: hidden;
        }}

        /* Header & Ultra-Long Search Bar */
        .header {{
            position: sticky; top: 0;
            width: 100%; padding: 40px 0;
            display: flex; flex-direction: column; align-items: center;
            background: linear-gradient(to bottom, var(--bg) 80%, transparent);
            z-index: 2000;
        }}

        .search-wrapper {{
            position: relative;
            width: 90%; max-width: 1300px;
            display: flex; align-items: center;
            background: var(--glass);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border);
            border-radius: 2px;
            padding: 2px 20px;
        }}

        #onionSearch {{
            background: transparent; border: none; outline: none;
            color: #fff; font-size: 1rem; width: 100%; padding: 18px;
            font-family: 'JetBrains Mono', monospace;
        }}

        /* Autocomplete results - Priority Front */
        #autocompleteList {{
            position: absolute; top: 100%; left: -1px; right: -1px;
            background: #0a0a0a; border: 1px solid var(--border);
            z-index: 3000; max-height: 400px; overflow-y: auto; display: none;
            box-shadow: 0 30px 60px rgba(0,0,0,0.9);
        }}

        .autocomplete-item {{
            padding: 18px 25px; cursor: pointer; font-family: monospace;
            border-bottom: 1px solid rgba(255,255,255,0.02);
            font-size: 0.85rem; color: #555; transition: 0.2s;
        }}

        .autocomplete-item:hover {{ background: #111; color: #fff; }}
        .autocomplete-item strong {{ color: #eee; text-decoration: underline; }}

        /* Results Area */
        #resultArea {{
            margin-top: 40px; width: 90%; max-width: 1300px;
            padding: 60px; background: var(--glass);
            border: 1px solid var(--border);
            display: none; margin-bottom: 200px;
        }}

        .stats-header {{
            display: flex; justify-content: space-between; align-items: flex-end;
            margin-bottom: 60px; border-bottom: 1px solid var(--border); padding-bottom: 20px;
        }}

        .onion-title {{ font-family: monospace; color: #fff; font-size: 1.2rem; word-break: break-all; }}
        #statusSummary {{ font-size: 0.7rem; letter-spacing: 2px; opacity: 0.5; text-transform: uppercase; }}

        /* D3 Styles */
        .axis line, .axis path {{ stroke: var(--border); }}
        .axis text {{ fill: #444; font-size: 9px; font-family: monospace; }}
        .dot {{ cursor: help; }}
    </style>
</head>
<body>

    <div class="header">
        <div class="search-wrapper">
            <i class="fas fa-search" style="opacity:0.2"></i>
            <input type="text" id="onionSearch" placeholder="SEARCH FAILED ONIONS..." autocomplete="off">
            <div id="autocompleteList"></div>
        </div>
    </div>

    <div id="resultArea">
        <div class="stats-header">
            <h3 class="onion-title" id="displayOnion"></h3>
            <div id="statusSummary"></div>
        </div>
        <div id="timelineChart" style="width: 100%;"></div>
    </div>

    <script>
        const onionHistoryData = {json_data};
        const failedOnionList = {json_failed_list};
        
        const searchInput = document.getElementById('onionSearch');
        const autocompleteList = document.getElementById('autocompleteList');
        const resultArea = document.getElementById('resultArea');

        searchInput.addEventListener('input', function() {{
            const val = this.value.toLowerCase();
            autocompleteList.innerHTML = '';
            if (!val) {{ autocompleteList.style.display = 'none'; return; }}

            const matches = failedOnionList.filter(addr => addr.toLowerCase().includes(val)).slice(0, 15);
            
            if (matches.length > 0) {{
                autocompleteList.style.display = 'block';
                matches.forEach(match => {{
                    const div = document.createElement('div');
                    div.className = 'autocomplete-item';
                    const idx = match.toLowerCase().indexOf(val);
                    div.innerHTML = `${{match.substring(0, idx)}}<strong>${{match.substring(idx, idx+val.length)}}</strong>${{match.substring(idx+val.length)}}.onion`;
                    div.onclick = () => {{
                        searchInput.value = match;
                        autocompleteList.style.display = 'none';
                        renderTimeline(match);
                    }};
                    autocompleteList.appendChild(div);
                }});
            }} else {{
                autocompleteList.style.display = 'none';
            }}
        }});

        function renderTimeline(address) {{
            const history = onionHistoryData[address];
            if (!history) return;

            resultArea.style.display = 'block';
            document.getElementById('displayOnion').textContent = address + '.onion';
            const chartDiv = document.getElementById('timelineChart');
            chartDiv.innerHTML = '';

            const fails = history.filter(h => h.status === 'FAIL').length;
            document.getElementById('statusSummary').textContent = `History: ${{history.length}} Total | ${{fails}} Failures`;

            const margin = {{top: 50, right: 50, bottom: 120, left: 50}}; // More bottom margin for long dates
            const width = chartDiv.offsetWidth - margin.left - margin.right;
            const height = 400 - margin.top - margin.bottom;

            const svg = d3.select("#timelineChart")
                .append("svg")
                .attr("width", width + margin.left + margin.right)
                .attr("height", height + margin.top + margin.bottom)
                .append("g")
                .attr("transform", `translate(${{margin.left}},${{margin.top}})`);

            const parseTime = d3.timeParse("%Y-%m-%d %H:%M:%S");
            const data = history.map(d => ({{
                date: parseTime(d.timestamp),
                status: d.status,
                details: d.details,
                timestamp: d.timestamp // Correctly preserving string for hover
            }})).sort((a,b) => a.date - b.date);

            const x = d3.scaleTime()
                .domain(d3.extent(data, d => d.date))
                .range([0, width]);

            // Full Time string on axis
            const xAxis = d3.axisBottom(x)
                .ticks(Math.max(2, Math.floor(width/150))) 
                .tickFormat(d3.timeFormat("%Y-%m-%d %H:%M:%S"));

            svg.append("g")
                .attr("class", "axis")
                .attr("transform", `translate(0,${{height}})`)
                .call(xAxis)
                .selectAll("text")
                .attr("transform", "rotate(-45)")
                .style("text-anchor", "end")
                .attr("dx", "-.8em") 
                .attr("dy", ".15em");

            // Base line
            svg.append("line")
                .attr("x1", 0).attr("x2", width).attr("y1", height/2).attr("y2", height/2)
                .attr("stroke", "rgba(255,255,255,0.05)");

            // Plot Dots
            svg.selectAll(".dot")
                .data(data)
                .enter()
                .append("circle")
                .attr("class", "dot")
                .attr("cx", d => x(d.date))
                .attr("cy", height/2)
                .attr("r", 8)
                .style("fill", d => d.status === 'SUCCESS' ? '#fff' : '#222')
                .style("stroke", "var(--border)")
                .append("title")
                .text(d => `STATUS: ${{d.status}}\\nTIME: ${{d.timestamp}}\\nINFO: ${{d.details}}`);
        }}

        // Handle Enter key
        searchInput.onkeydown = (e) => {{
            if(e.key === 'Enter') renderTimeline(searchInput.value.replace('.onion',''));
        }};
    </script>
</body>
</html>"""
    
    with open(output_file, 'w') as f:
        f.write(html_content)
    print(f"Tool updated at: {output_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--log', default='../logs/unified_scraper.log')
    parser.add_argument('--output', default='../scraped_data/failure_timeline.html')
    args = parser.parse_args()
    generate_html(parse_scraper_log(args.log), args.output)
