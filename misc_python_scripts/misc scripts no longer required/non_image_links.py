#!/usr/bin/env python3
"""
Onion Status Dashboard - Advanced Visualization
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
        # Check if folder name looks like an onion address
        if item.is_dir() and 16 <= len(item.name) <= 56 and all(c in 'abcdefghijklmnopqrstuvwxyz234567' for c in item.name):
            timestamp = datetime.fromtimestamp(item.stat().st_mtime)
            date_str = timestamp.strftime('%Y-%m-%d')
            
            img_dir = item / 'images'
            success = False
            if img_dir.exists():
                images = list(img_dir.glob('index.*'))
                if images:
                    success = True
            
            stats.append({
                'onion': f"http://{item.name}.onion",
                'date': date_str,
                'status': 'active' if success else 'failed'
            })
    
    return stats

def save_non_image_links(stats, output_dir):
    """Saves links that did not result in an image to a text file."""
    non_image_links = [s['onion'] for s in stats if s['status'] == 'failed']
    output_path = Path(output_dir) / "non_image_links1.txt"
    
    with open(output_path, 'w') as f:
        for link in sorted(set(non_image_links)):
            f.write(f"{link}\n")
    
    print(f"Non-image links saved to: {output_path}")

def generate_visualization(stats, output_file):
    # Aggregate data
    daily_data = defaultdict(lambda: {'active': 0, 'failed': 0})
    for entry in stats:
        daily_data[entry['date']][entry['status']] += 1
    
    sorted_dates = sorted(daily_data.keys())
    active_counts = [daily_data[d]['active'] for d in sorted_dates]
    failed_counts = [daily_data[d]['failed'] for d in sorted_dates]
    
    total_active = sum(active_counts)
    total_failed = sum(failed_counts)

    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>DeepScan | Status Intelligence</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0a0a0c;
            --panel: #141417;
            --accent-green: #00ffaa;
            --accent-red: #ff3366;
            --text-main: #e0e0e6;
            --text-dim: #80808a;
        }}
        body {{ 
            font-family: 'Inter', sans-serif; 
            background: var(--bg); 
            color: var(--text-main); 
            margin: 0; padding: 40px;
            display: flex; flex-direction: column; align-items: center;
        }}
        .dashboard-header {{ text-align: left; width: 100%; max-width: 1100px; margin-bottom: 30px; }}
        h1 {{ font-family: 'Orbitron', sans-serif; letter-spacing: 2px; color: var(--accent-green); margin: 0; font-size: 1.5rem; }}
        .subtitle {{ color: var(--text-dim); font-size: 0.9rem; }}
        
        .grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            width: 100%;
            max-width: 1100px;
        }}
        .card {{
            background: var(--panel);
            border-radius: 12px;
            padding: 25px;
            border: 1px solid #ffffff0a;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }}
        .stat-val {{ font-size: 2rem; font-weight: 700; font-family: 'Orbitron'; }}
        .stat-label {{ color: var(--text-dim); font-size: 0.8rem; text-transform: uppercase; }}
    </style>
</head>
<body>
    <div class="dashboard-header">
        <h1>ONION_SURVEILLANCE_METRICS</h1>
        <div class="subtitle">Temporal data analysis of scraping operations</div>
    </div>

    <div class="grid">
        <div class="card">
            <div class="stat-label">Activity Over Time</div>
            <canvas id="timelineChart" height="150"></canvas>
        </div>
        <div class="card" style="display: flex; flex-direction: column; justify-content: center; align-items: center;">
            <div class="stat-label">Health Distribution</div>
            <canvas id="healthChart"></canvas>
            <div style="margin-top: 20px; text-align: center;">
                <div class="stat-val" style="color: var(--accent-green)">{total_active}</div>
                <div class="stat-label">Successful Nodes</div>
            </div>
        </div>
    </div>

    <script>
        // Common Styles
        Chart.defaults.color = '#80808a';
        Chart.defaults.font.family = "'Inter'";

        // Timeline Area Chart
        const ctxTimeline = document.getElementById('timelineChart').getContext('2d');
        const greenGrad = ctxTimeline.createLinearGradient(0, 0, 0, 400);
        greenGrad.addColorStop(0, 'rgba(0, 255, 170, 0.2)');
        greenGrad.addColorStop(1, 'rgba(0, 255, 170, 0)');

        const redGrad = ctxTimeline.createLinearGradient(0, 0, 0, 400);
        redGrad.addColorStop(0, 'rgba(255, 51, 102, 0.2)');
        redGrad.addColorStop(1, 'rgba(255, 51, 102, 0)');

        new Chart(ctxTimeline, {{
            type: 'line',
            data: {{
                labels: {json.dumps(sorted_dates)},
                datasets: [
                    {{
                        label: 'Successful Scrapes',
                        data: {json.dumps(active_counts)},
                        borderColor: '#00ffaa',
                        backgroundColor: greenGrad,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointBackgroundColor: '#00ffaa'
                    }},
                    {{
                        label: 'Non-Image / Failed',
                        data: {json.dumps(failed_counts)},
                        borderColor: '#ff3366',
                        backgroundColor: redGrad,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ grid: {{ display: false }}, ticks: {{ maxRotation: 0 }} }},
                    y: {{ grid: {{ color: '#ffffff05' }}, beginAtZero: true }}
                }}
            }}
        }});

        // Circular Health Chart
        const ctxHealth = document.getElementById('healthChart').getContext('2d');
        new Chart(ctxHealth, {{
            type: 'doughnut',
            data: {{
                labels: ['Active', 'Failed'],
                datasets: [{{
                    data: [{total_active}, {total_failed}],
                    backgroundColor: ['#00ffaa', '#ff3366'],
                    borderWidth: 0,
                    hoverOffset: 10
                }}]
            }},
            options: {{
                cutout: '80%',
                plugins: {{ legend: {{ display: false }} }}
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
        
    # Requirement 1: Save non-image links to txt
    save_non_image_links(stats, args.input_dir)
    
    # Requirement 2: Generate professional viz
    generate_visualization(stats, args.output)

if __name__ == "__main__":
    main()
