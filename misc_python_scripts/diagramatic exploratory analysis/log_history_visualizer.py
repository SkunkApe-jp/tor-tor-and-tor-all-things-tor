#!/usr/bin/env python3
"""
Log-Based Run History Visualizer

Parses text log files from the logs/ directory to extract Success/Fail stats over time.
Displays them in a diverging bar chart.
"""

import os
import json
import re
from collections import defaultdict
from pathlib import Path

# Log format: [YYYY-MM-DD HH:MM:SS] http://xxx.onion -> SUCCESS/FAIL (...)
LOG_PATTERN = r'\[(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\].*?->\s*(SUCCESS|FAIL|FAILED|ERROR|200 OK|404|Timeout)'
SUCCESS_KEYWORDS = ['SUCCESS', '200 OK']
FAILURE_KEYWORDS = ['FAIL', 'FAILED', 'ERROR', '404', 'Timeout', 'Exception']


def parse_log_file(log_path):
    """Extracts success/fail counts per day from a text log."""
    history = defaultdict(lambda: {"success": 0, "fail": 0})
    
    if not os.path.exists(log_path):
        print(f"Log file not found at {log_path}")
        return None

    print(f"Parsing log file: {log_path}...")
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = re.search(LOG_PATTERN, line, re.IGNORECASE)
            if match:
                status = match.group(2).upper()
                
                if any(k in status for k in SUCCESS_KEYWORDS):
                    history["today"]["success"] += 1
                elif any(k in status for k in FAILURE_KEYWORDS):
                    history["today"]["fail"] += 1

    # Convert to list format for D3
    formatted_data = []
    for date in sorted(history.keys()):
        formatted_data.append({
            "date": date,
            "success": history[date]["success"],
            "fail": -history[date]["fail"]
        })
    return formatted_data


def parse_all_logs_in_dir(logs_dir):
    """Parse all .log files in the logs directory, grouping by date."""
    history = defaultdict(lambda: {"success": 0, "fail": 0})
    
    if not os.path.exists(logs_dir):
        print(f"Logs directory not found at {logs_dir}")
        return None
    
    log_files = [f for f in os.listdir(logs_dir) if f.endswith('.log')]
    if not log_files:
        print(f"No .log files found in {logs_dir}")
        return None
    
    print(f"Found {len(log_files)} log file(s) in {logs_dir}")
    
    for log_file in log_files:
        log_path = os.path.join(logs_dir, log_file)
        print(f"  Parsing: {log_file}")
        
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Try to extract date from filename or content
                # Format: [HH:MM:SS] url -> STATUS
                time_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', line)
                status_match = re.search(r'->\s*(SUCCESS|FAIL|FAILED|ERROR)', line, re.IGNORECASE)
                
                if time_match and status_match:
                    # Use a placeholder date since logs don't have dates
                    # Group all entries as "today" or use file modification date
                    status = status_match.group(1).upper()
                    
                    if any(k in status for k in SUCCESS_KEYWORDS):
                        history["today"]["success"] += 1
                    elif any(k in status for k in FAILURE_KEYWORDS):
                        history["today"]["fail"] += 1
    
    # Convert to list
    formatted_data = []
    for date in sorted(history.keys()):
        formatted_data.append({
            "date": date,
            "success": history[date]["success"],
            "fail": -history[date]["fail"]
        })
    return formatted_data


def parse_logs_with_dates(logs_dir, single_file=None):
    """
    Parse logs and extract dates from log entries.
    
    Args:
        logs_dir: Directory containing log files
        single_file: If specified, only parse this file (not all .log files)
    """
    history = defaultdict(lambda: {"success": 0, "fail": 0})
    
    if not os.path.exists(logs_dir):
        return None
    
    if single_file:
        log_files = [single_file] if os.path.exists(os.path.join(logs_dir, single_file)) else []
    else:
        log_files = sorted([f for f in os.listdir(logs_dir) if f.endswith('.log')])
    
    if not log_files:
        return None
    
    print(f"Parsing {len(log_files)} log file(s)...")
    
    for log_file in log_files:
        log_path = os.path.join(logs_dir, log_file)
        
        with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Match: [YYYY-MM-DD HH:MM:SS] url -> STATUS
                match = re.search(LOG_PATTERN, line, re.IGNORECASE)
                if match:
                    date_str = match.group(1)
                    status = match.group(2).upper()
                    
                    if any(k in status for k in SUCCESS_KEYWORDS):
                        history[date_str]["success"] += 1
                    elif any(k in status for k in FAILURE_KEYWORDS):
                        history[date_str]["fail"] += 1
    
    # Convert to sorted list
    formatted_data = []
    for date in sorted(history.keys()):
        formatted_data.append({
            "date": date,
            "success": history[date]["success"],
            "fail": -history[date]["fail"]
        })
    
    return formatted_data


def generate_history_html(data, output_path):
    """Generate the diverging bar chart HTML."""
    if not data:
        print("No data found to visualize.")
        return

    total_success = sum(d["success"] for d in data)
    total_fail = sum(-d["fail"] for d in data)
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Crawler Log History</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            background: #f5f5f5;
            font-family: 'Segoe UI', sans-serif;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 40px 20px;
        }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        .subtitle {{ color: #666; margin-bottom: 30px; }}
        .stats {{
            display: flex;
            gap: 30px;
            margin-bottom: 30px;
        }}
        .stat-box {{
            background: white;
            padding: 15px 25px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-value {{ font-size: 28px; font-weight: bold; }}
        .stat-label {{ font-size: 12px; color: #888; text-transform: uppercase; }}
        .stat-success {{ color: #67A9CF; }}
        .stat-fail {{ color: #EF8A62; }}
        .bar-success {{ fill: #67A9CF; }} 
        .bar-fail {{ fill: #EF8A62; }}
        .date-label {{ font-size: 11px; fill: #333; font-weight: 500; }}
        .value-label {{ font-size: 10px; fill: #666; }}
        .grid line {{ stroke: #e0e0e0; }}
        .axis line {{ stroke: #ccc; }}
        #chart {{
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.08);
            padding: 20px;
        }}
    </style>
</head>
<body>
    <h1>Crawler Run History</h1>
    <p class="subtitle">Parsed from logs/ directory | Success &rarr; | &larr; Failed</p>
    
    <div class="stats">
        <div class="stat-box">
            <div class="stat-value stat-success">{total_success}</div>
            <div class="stat-label">Successful</div>
        </div>
        <div class="stat-box">
            <div class="stat-value stat-fail">{total_fail}</div>
            <div class="stat-label">Failed</div>
        </div>
    </div>
    
    <div id="chart"></div>

    <script>
        const data = {json.dumps(data)};
        const margin = {{top: 20, right: 80, bottom: 40, left: 120}};
        const barHeight = 35;
        const width = 800 - margin.left - margin.right;
        const height = Math.max(data.length * barHeight, 200);

        const svg = d3.select("#chart").append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g").attr("transform", `translate(${{margin.left}},${{margin.top}})`);

        const maxVal = d3.max(data, d => Math.max(Math.abs(d.fail), d.success)) || 10;
        const x = d3.scaleLinear().domain([-maxVal * 1.1, maxVal * 1.1]).range([0, width]);
        const y = d3.scaleBand().domain(data.map(d => d.date)).range([0, height]).padding(0.4);

        // Grid lines
        svg.append("g").attr("class", "grid")
            .call(d3.axisBottom(x).ticks(10).tickSize(-height).tickFormat(""));

        // Zero line (center spine)
        svg.append("line")
            .attr("x1", x(0)).attr("x2", x(0))
            .attr("y1", 0).attr("y2", height)
            .attr("stroke", "#333").attr("stroke-width", 2);

        // Success bars (right side)
        svg.selectAll(".bar-success").data(data).enter().append("rect")
            .attr("class", "bar-success")
            .attr("x", x(0))
            .attr("y", d => y(d.date))
            .attr("width", d => x(d.success) - x(0))
            .attr("height", y.bandwidth())
            .attr("rx", 3);

        // Fail bars (left side)
        svg.selectAll(".bar-fail").data(data).enter().append("rect")
            .attr("class", "bar-fail")
            .attr("x", d => x(d.fail))
            .attr("y", d => y(d.date))
            .attr("width", d => x(0) - x(d.fail))
            .attr("height", y.bandwidth())
            .attr("rx", 3);

        // Success value labels
        svg.selectAll(".label-success").data(data).enter().append("text")
            .attr("class", "value-label")
            .attr("x", d => x(d.success) + 5)
            .attr("y", d => y(d.date) + y.bandwidth() / 2)
            .attr("dominant-baseline", "middle")
            .text(d => d.success > 0 ? d.success : "");

        // Fail value labels
        svg.selectAll(".label-fail").data(data).enter().append("text")
            .attr("class", "value-label")
            .attr("x", d => x(d.fail) - 5)
            .attr("y", d => y(d.date) + y.bandwidth() / 2)
            .attr("dominant-baseline", "middle")
            .attr("text-anchor", "end")
            .text(d => d.fail < 0 ? Math.abs(d.fail) : "");

        // Y axis (date labels)
        svg.append("g").attr("class", "axis")
            .call(d3.axisLeft(y).tickSize(0).tickPadding(10))
            .selectAll("text").attr("class", "date-label");

        // X axis
        svg.append("g").attr("class", "axis")
            .attr("transform", `translate(0,${{height}})`)
            .call(d3.axisBottom(x).ticks(10).tickFormat(d => Math.abs(d)));
    </script>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Visualization created: {output_path}")


def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    
    # Only look in the logs directory
    logs_path = script_dir / "../logs"
    logs_path = logs_path.resolve()
    
    # Output to scraped_data directory
    output_path = script_dir / "../scraped_data/crawl_history.html"
    output_path = output_path.resolve()
    
    # Only parse the root/main log file (scan_report.log)
    log_file = logs_path / "scan_report.log"
    
    print(f"Looking for logs in: {logs_path}")
    print(f"Parsing log file: {log_file}")
    
    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        return
    
    # Parse the single log file
    run_history = parse_logs_with_dates(str(logs_path), single_file="unified_scraper.log")
    
    if run_history:
        generate_history_html(run_history, str(output_path))
    else:
        print("No log data found.")


if __name__ == "__main__":
    main()
