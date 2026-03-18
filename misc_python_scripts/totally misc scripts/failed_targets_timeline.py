#!/usr/bin/env python3
"""
Failed Targets Timeline - Visualizes failed crawl attempts over time
Reads from scan_report.log and creates a timeline of failures.
"""

import os
import json
import re
from collections import defaultdict
from pathlib import Path
from datetime import datetime

# Log format: [YYYY-MM-DD HH:MM:SS] URL -> FAIL (error)
FAIL_PATTERN = r'\[(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\].*?->\s*(FAIL|FAILED|ERROR)'

def parse_failures_from_log(log_file):
    """Parse log file and extract failure timeline."""
    failures = defaultdict(lambda: {'count': 0, 'urls': set(), 'errors': defaultdict(int)})
    
    if not os.path.exists(log_file):
        print(f"Log file not found: {log_file}")
        return None
    
    print(f"Parsing failures from: {log_file}")
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            match = re.search(FAIL_PATTERN, line, re.IGNORECASE)
            if match:
                date_str = match.group(1)
                time_str = match.group(2)
                
                # Extract URL
                url_match = re.search(r'\[.*?\] (http[^\s]+) ->', line)
                url = url_match.group(1) if url_match else "Unknown"
                
                # Extract error
                error_match = re.search(r'-> FAIL \((.+?)\)', line, re.IGNORECASE)
                error = error_match.group(1).strip()[:40] if error_match else "Unknown"
                
                failures[date_str]['count'] += 1
                failures[date_str]['urls'].add(url)
                failures[date_str]['errors'][error] += 1
    
    # Convert to list for JSON
    data = []
    for date in sorted(failures.keys()):
        data.append({
            'date': date,
            'failures': failures[date]['count'],
            'unique_urls': len(failures[date]['urls']),
            'top_error': max(failures[date]['errors'].items(), key=lambda x: x[1])[0] if failures[date]['errors'] else 'Unknown'
        })
    
    return data, failures


def generate_timeline_html(data, error_history, output_file):
    """Generate HTML timeline visualization."""
    if not data:
        print("No failure data to visualize.")
        return
    
    total_failures = sum(d['failures'] for d in data)
    total_unique = sum(d['unique_urls'] for d in data)
    
    # Aggregate all errors
    all_errors = defaultdict(int)
    for date_data in error_history.values():
        for error, count in date_data['errors'].items():
            all_errors[error] += count
    
    top_errors = sorted(all_errors.items(), key=lambda x: -x[1])[:5]
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Failed Targets Timeline</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ background: #0a0a0f; color: #eee; font-family: 'Segoe UI', sans-serif; padding: 40px 20px; }}
        h1 {{ text-align: center; color: #EF8A62; margin-bottom: 10px; }}
        .subtitle {{ text-align: center; color: #888; margin-bottom: 30px; }}
        .stats {{ display: flex; gap: 20px; justify-content: center; margin-bottom: 40px; flex-wrap: wrap; }}
        .stat-box {{ background: #1a1a2e; padding: 20px 30px; border-radius: 10px; text-align: center; border: 1px solid #333; min-width: 150px; }}
        .stat-value {{ font-size: 36px; font-weight: bold; color: #EF8A62; }}
        .stat-label {{ font-size: 12px; color: #888; text-transform: uppercase; margin-top: 5px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 30px; max-width: 1400px; margin: 0 auto; }}
        .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 10px; padding: 20px; }}
        .card h2 {{ color: #fff; font-size: 16px; margin: 0 0 20px 0; border-bottom: 1px solid #333; padding-bottom: 15px; }}
        .chart-container {{ position: relative; height: 300px; }}
        .error-list {{ list-style: none; padding: 0; margin: 0; }}
        .error-item {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #222; }}
        .error-name {{ color: #ccc; font-size: 14px; }}
        .error-count {{ color: #EF8A62; font-weight: bold; }}
    </style>
</head>
<body>
    <h1>❌ Failed Targets Timeline</h1>
    <p class="subtitle">Tracking crawl failures over time from scan_report.log</p>
    
    <div class="stats">
        <div class="stat-box">
            <div class="stat-value">{total_failures}</div>
            <div class="stat-label">Total Failures</div>
        </div>
        <div class="stat-box">
            <div class="stat-value">{total_unique}</div>
            <div class="stat-label">Unique URLs Failed</div>
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
                {''.join(f'<li class="error-item"><span class="error-name">{err[:40]}</span><span class="error-count">{cnt}</span></li>' for err, cnt in top_errors)}
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
                plugins: {{ legend: {{ display: false }} }},
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
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ grid: {{ display: false }} }},
                    y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Timeline created: {output_file}")


def main():
    script_dir = Path(__file__).parent
    logs_path = script_dir / "../logs/scan_report.log"
    output_path = script_dir / "../scraped_data/failed_targets_timeline.html"
    
    print("="*60)
    print("FAILED TARGETS TIMELINE")
    print("="*60)
    
    data, error_history = parse_failures_from_log(str(logs_path))
    
    if data:
        generate_timeline_html(data, error_history, str(output_path))
        print("\n✅ Timeline visualization complete!")
    else:
        print("\nNo failure data found.")


if __name__ == "__main__":
    main()
