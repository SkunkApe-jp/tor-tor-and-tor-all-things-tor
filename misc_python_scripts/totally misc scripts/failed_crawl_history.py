#!/usr/bin/env python3
"""
Failed Crawl History Visualizer

Parses log files to show failed crawl attempts over time.
Displays failures in a timeline with error breakdown.
"""

import os
import json
import re
from collections import defaultdict
from pathlib import Path

# Log format: [YYYY-MM-DD HH:MM:SS] http://xxx.onion -> FAIL (error)
LOG_PATTERN = r'\[(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}\].*?->\s*(FAIL|FAILED|ERROR)'
ERROR_EXTRACT = r'-> FAIL \((.+?)\)'

def parse_failed_crawls(log_file_path):
    """Parse log file for failed crawl attempts."""
    history = defaultdict(lambda: {"count": 0, "errors": defaultdict(int)})
    
    if not os.path.exists(log_file_path):
        print(f"Log file not found: {log_file_path}")
        return None
    
    print(f"Parsing failures from: {log_file_path}")
    
    with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = re.search(LOG_PATTERN, line, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                
                # Extract error type
                error_match = re.search(ERROR_EXTRACT, line, re.IGNORECASE)
                error_type = error_match.group(1).strip()[:30] if error_match else "Unknown"
                
                history[date_str]["count"] += 1
                history[date_str]["errors"][error_type] += 1
    
    # Convert to list
    formatted_data = []
    for date in sorted(history.keys()):
        formatted_data.append({
            "date": date,
            "failures": history[date]["count"],
            "top_error": max(history[date]["errors"].items(), key=lambda x: x[1])[0] if history[date]["errors"] else "Unknown"
        })
    
    return formatted_data, history


def generate_failed_crawl_html(data, error_history, output_path):
    """Generate HTML visualization for failed crawls."""
    if not data:
        print("No failure data to visualize.")
        return
    
    total_failures = sum(d["failures"] for d in data)
    
    # Aggregate all errors
    all_errors = defaultdict(int)
    for date_data in error_history.values():
        for error, count in date_data["errors"].items():
            all_errors[error] += count
    
    top_errors = sorted(all_errors.items(), key=lambda x: -x[1])[:5]
    
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Failed Crawl History</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            background: #0a0a0f;
            color: #eee;
            font-family: 'Segoe UI', sans-serif;
            padding: 40px 20px;
        }}
        h1 {{
            text-align: center;
            color: #EF8A62;
            margin-bottom: 10px;
        }}
        .subtitle {{
            text-align: center;
            color: #888;
            margin-bottom: 30px;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            justify-content: center;
            margin-bottom: 40px;
        }}
        .stat-box {{
            background: #1a1a2e;
            padding: 20px 30px;
            border-radius: 10px;
            text-align: center;
            border: 1px solid #333;
        }}
        .stat-value {{
            font-size: 36px;
            font-weight: bold;
            color: #EF8A62;
        }}
        .stat-label {{
            font-size: 12px;
            color: #888;
            text-transform: uppercase;
            margin-top: 5px;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 30px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 20px;
        }}
        .card h2 {{
            color: #fff;
            font-size: 16px;
            margin: 0 0 20px 0;
            border-bottom: 1px solid #333;
            padding-bottom: 15px;
        }}
        .chart-container {{
            position: relative;
            height: 300px;
        }}
        .error-list {{
            list-style: none;
            padding: 0;
            margin: 0;
        }}
        .error-item {{
            display: flex;
            justify-content: space-between;
            padding: 12px 0;
            border-bottom: 1px solid #222;
        }}
        .error-name {{
            color: #ccc;
            font-size: 14px;
        }}
        .error-count {{
            color: #EF8A62;
            font-weight: bold;
        }}
        .bar {{
            fill: #EF8A62;
        }}
        .bar:hover {{
            fill: #ff9f7a;
        }}
    </style>
</head>
<body>
    <h1>❌ Failed Crawl History</h1>
    <p class="subtitle">Tracking crawl failures over time</p>
    
    <div class="stats">
        <div class="stat-box">
            <div class="stat-value">{total_failures}</div>
            <div class="stat-label">Total Failures</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{len(data)}</div>
            <div class="stat-label">Days with Failures</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{len(all_errors)}</div>
            <div class="stat-label">Error Types</div>
        </div>
    </div>
    
    <div class="grid">
        <div class="card">
            <h2>📉 Failures Over Time</h2>
            <div class="chart-container">
                <canvas id="timelineChart"></canvas>
            </div>
        </div>
        
        <div class="card">
            <h2>⚠️ Top Error Types</h2>
            <ul class="error-list">
                {''.join(f'''
                <li class="error-item">
                    <span class="error-name">{error[:40]}</span>
                    <span class="error-count">{count}</span>
                </li>
                ''' for error, count in top_errors)}
            </ul>
        </div>
        
        <div class="card" style="grid-column: span 2;">
            <h2>📊 Daily Failure Distribution</h2>
            <div class="chart-container">
                <canvas id="barChart"></canvas>
            </div>
        </div>
    </div>

    <script>
        const data = {json.dumps(data)};
        
        Chart.defaults.color = '#888';
        Chart.defaults.borderColor = '#333';
        
        // Timeline chart
        new Chart(document.getElementById('timelineChart'), {{
            type: 'line',
            data: {{
                labels: data.map(d => d.date),
                datasets: [{{
                    label: 'Failures',
                    data: data.map(d => d.failures),
                    borderColor: '#EF8A62',
                    backgroundColor: 'rgba(239, 138, 98, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    x: {{ grid: {{ display: false }} }},
                    y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }}
                }}
            }}
        }});
        
        // Bar chart
        new Chart(document.getElementById('barChart'), {{
            type: 'bar',
            data: {{
                labels: data.map(d => d.date),
                datasets: [{{
                    label: 'Failures',
                    data: data.map(d => d.failures),
                    backgroundColor: '#EF8A62',
                    borderColor: '#ff9f7a',
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    x: {{ grid: {{ display: false }} }},
                    y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"Failed crawl visualization created: {output_path}")


def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    logs_path = script_dir / "../logs"
    output_path = script_dir / "../scraped_data/failed_crawl_history.html"
    
    log_file = logs_path / "scan_report.log"
    
    print(f"Looking for logs in: {logs_path}")
    print(f"Parsing: {log_file}")
    
    data, error_history = parse_failed_crawls(str(log_file))
    
    if data:
        generate_failed_crawl_html(data, error_history, str(output_path))
    else:
        print("No failure data found to visualize.")


if __name__ == "__main__":
    main()
