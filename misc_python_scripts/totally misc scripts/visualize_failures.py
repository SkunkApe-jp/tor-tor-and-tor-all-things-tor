#!/usr/bin/env python3
"""
Onion Status Timeline - Visualizes Success vs Failure over time
"""

import os
import json
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

def collect_stats(scraped_dir):
    """Scan directories and collect status/time data."""
    stats = []
    base_path = Path(scraped_dir)
    
    if not base_path.exists():
        print(f"Error: {scraped_dir} not found.")
        return []

    for item in base_path.iterdir():
        # Check if folder name looks like an onion address (16-56 chars, base32)
        if item.is_dir() and 16 <= len(item.name) <= 56 and all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in item.name):
            # Get timestamp from folder modification time
            timestamp = datetime.fromtimestamp(item.stat().st_mtime)
            date_str = timestamp.strftime('%Y-%m-%d')
            
            # Determine status: Success if index image exists, else Failed
            img_dir = item / 'images'
            success = False
            if img_dir.exists():
                images = list(img_dir.glob('index.*'))
                if images:
                    success = True
            
            stats.append({
                'date': date_str,
                'status': 'active' if success else 'failed'
            })
    
    return stats

def generate_visualization(stats, output_file):
    # Aggregate data by date
    daily_data = defaultdict(lambda: {'active': 0, 'failed': 0})
    for entry in stats:
        daily_data[entry['date']][entry['status']] += 1
    
    # Sort dates
    sorted_dates = sorted(daily_data.keys())
    active_counts = [daily_data[d]['active'] for d in sorted_dates]
    failed_counts = [daily_data[d]['failed'] for d in sorted_dates]
    
    # Also write failed targets to txt file
    script_dir = Path(__file__).parent
    failed_txt_path = script_dir / "../scraped_data/failed_targets.txt"
    
    failed_urls = []
    base_path = Path(output_file).parent
    for item in base_path.iterdir():
        if item.is_dir() and 16 <= len(item.name) <= 56 and all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in item.name):
            img_dir = item / 'images'
            has_image = img_dir.exists() and list(img_dir.glob('index.*'))
            if not has_image:
                failed_urls.append(f"http://{item.name}.onion")
    
    with open(str(failed_txt_path), 'w') as f:
        for url in sorted(failed_urls):
            f.write(f"{url}\n")
    
    print(f"Failed targets list: {failed_txt_path}")

    html_template = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Onion Status Timeline</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: sans-serif; background: #121212; color: white; padding: 40px; }}
        .container {{ max-width: 1000px; margin: auto; background: #1e1e1e; padding: 20px; border-radius: 8px; }}
        h1 {{ text-align: center; color: #a0a0a0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Onion Scraping Status Over Time</h1>
        <canvas id="statusChart"></canvas>
    </div>

    <script>
        const ctx = document.getElementById('statusChart').getContext('2d');
        new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {json.dumps(sorted_dates)},
                datasets: [
                    {{
                        label: 'Successful Scrapes',
                        data: {json.dumps(active_counts)},
                        borderColor: '#4caf50',
                        backgroundColor: 'rgba(76, 175, 80, 0.1)',
                        fill: true,
                        tension: 0.3
                    }},
                    {{
                        label: 'Failed Onions',
                        data: {json.dumps(failed_counts)},
                        borderColor: '#f44336',
                        backgroundColor: 'rgba(244, 67, 54, 0.1)',
                        fill: true,
                        tension: 0.3
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ labels: {{ color: 'white' }} }}
                }},
                scales: {{
                    x: {{ grid: {{ color: '#333' }}, ticks: {{ color: '#aaa' }} }},
                    y: {{ grid: {{ color: '#333' }}, ticks: {{ color: '#aaa' }}, beginAtZero: true }}
                }}
            }}
        }});
    </script>
</body>
</html>
"""
    with open(output_file, 'w') as f:
        f.write(html_template)
    print(f"Visualization created at: {output_file}")

def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    default_input = script_dir / "../scraped_data"
    default_output = script_dir / "../scraped_data/status_timeline.html"
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', default=str(default_input))
    parser.add_argument('--output', default=str(default_output))
    args = parser.parse_args()

    stats = collect_stats(args.input_dir)
    if not stats:
        print("No data to visualize.")
        return
        
    generate_visualization(stats, args.output)

if __name__ == "__main__":
    main()
