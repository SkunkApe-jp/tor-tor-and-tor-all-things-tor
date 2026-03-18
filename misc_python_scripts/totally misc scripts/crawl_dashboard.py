#!/usr/bin/env python3
"""
Crawl Analytics Dashboard - Stats, Histograms, and Success Rates

Comprehensive dashboard showing crawl statistics, link distributions,
success/failure rates, and site metrics.
"""

import os
import json
import re
from pathlib import Path
from collections import defaultdict, Counter
from datetime import datetime


def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and re.match(r'^[a-z2-7]{16,56}$', item):
            onion_dirs.append(item)
    return onion_dirs


def extract_title_from_html(html_file_path):
    """Extract title from HTML file."""
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    return ' '.join(title_match.group(1).strip().split())[:30]
        except Exception:
            pass
    return None


def parse_log_times(log_file_path):
    """Parse log file to extract time span information."""
    timestamps = []

    if not os.path.exists(log_file_path):
        return None

    try:
        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Match format: [YYYY-MM-DD HH:MM:SS] or [HH:MM:SS]
                match = re.search(r'\[(\d{4}-\d{2}-\d{2})?\s*(\d{2}:\d{2}:\d{2})\]', line)
                if match:
                    date_str = match.group(1)
                    time_str = match.group(2)
                    if date_str:
                        try:
                            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")
                            timestamps.append(dt)
                        except:
                            pass
                    else:
                        # No date, just use today with the time
                        try:
                            today = datetime.now().strftime("%Y-%m-%d")
                            dt = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %H:%M:%S")
                            timestamps.append(dt)
                        except:
                            pass
    except:
        pass

    if not timestamps:
        return None

    timestamps.sort()
    time_span = timestamps[-1] - timestamps[0]
    
    # Calculate mean (average) timestamp
    mean_timestamp = timestamps[0] + (time_span / 2)
    
    # Calculate unique days
    unique_days = len(set(ts.strftime("%Y-%m-%d") for ts in timestamps))
    
    # Calculate average crawls per day
    avg_per_day = len(timestamps) / unique_days if unique_days > 0 else 0

    return {
        'start': timestamps[0],
        'end': timestamps[-1],
        'mean': mean_timestamp,
        'span_hours': time_span.total_seconds() / 3600,
        'unique_days': unique_days,
        'avg_per_day': avg_per_day,
        'total_entries': len(timestamps)
    }


def parse_json_stats(stats_file_path):
    """Parse JSON stats file for more accurate crawl analytics."""
    if not os.path.exists(stats_file_path):
        return None
    
    try:
        with open(stats_file_path, 'r', encoding='utf-8') as f:
            stats = json.load(f)
        
        if not stats:
            return None
        
        timestamps = []
        for entry in stats:
            try:
                # Parse ISO format timestamp
                ts = datetime.fromisoformat(entry['timestamp'].replace('Z', '+00:00'))
                timestamps.append(ts)
            except:
                pass
        
        if not timestamps:
            return None
            
        timestamps.sort()
        time_span = timestamps[-1] - timestamps[0]
        mean_timestamp = timestamps[0] + (time_span / 2)
        unique_days = len(set(ts.strftime("%Y-%m-%d") for ts in timestamps))
        
        # Count successes/failures
        successes = sum(1 for s in stats if s.get('status') == 'SUCCESS')
        failures = sum(1 for s in stats if s.get('status') == 'FAIL')
        
        # Count screenshots
        screenshots = sum(1 for s in stats if s.get('screenshot'))
        
        # Sum links and titles
        total_links = sum(s.get('links_count', 0) for s in stats)
        total_titles = sum(s.get('titles_count', 0) for s in stats)
        
        # Per-site metadata
        site_stats = {}
        for s in stats:
            addr = s.get('onion_addr', 'unknown')
            if addr not in site_stats:
                site_stats[addr] = {
                    'attempts': 0,
                    'successes': 0,
                    'failures': 0,
                    'last_status': '',
                    'last_timestamp': '',
                    'total_links': 0,
                    'total_titles': 0,
                    'has_screenshot': False
                }
            site_stats[addr]['attempts'] += 1
            if s.get('status') == 'SUCCESS':
                site_stats[addr]['successes'] += 1
                site_stats[addr]['has_screenshot'] = s.get('screenshot', False)
                site_stats[addr]['total_links'] += s.get('links_count', 0)
                site_stats[addr]['total_titles'] += s.get('titles_count', 0)
            else:
                site_stats[addr]['failures'] += 1
            site_stats[addr]['last_status'] = s.get('status', '')
            site_stats[addr]['last_timestamp'] = s.get('timestamp', '')
        
        return {
            'start': timestamps[0],
            'end': timestamps[-1],
            'mean': mean_timestamp,
            'span_hours': time_span.total_seconds() / 3600,
            'unique_days': unique_days,
            'avg_per_day': len(timestamps) / unique_days if unique_days > 0 else 0,
            'total_entries': len(timestamps),
            'successes': successes,
            'failures': failures,
            'screenshots': screenshots,
            'total_links': total_links,
            'total_titles': total_titles,
            'site_stats': site_stats
        }
    except Exception as e:
        print(f"Error parsing JSON stats: {e}")
        return None


def generate_crawl_dashboard(scraped_data_dir):
    """Generate a comprehensive crawl analytics dashboard."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites to analyze")
    
    # Try JSON stats first (more accurate), fallback to log parsing
    script_dir = Path(__file__).parent
    stats_file = script_dir / "../logs/crawl_stats.json"
    time_info = parse_json_stats(str(stats_file))
    
    if not time_info:
        # Fallback to unified_scraper.log
        log_file = script_dir / "../logs/unified_scraper.log"
        time_info = parse_log_times(str(log_file))
    
    # Collect metrics
    metrics = {
        'total_sites': len(onion_sites),
        'sites_with_images': 0,
        'sites_with_titles': 0,
        'total_outbound_links': 0,
        'total_discovered_links': 0,
        'outbound_distribution': [],
        'inbound_distribution': [],
        'link_counts': [],
    }
    
    # Add stats from JSON/log
    if time_info:
        metrics['time_span_hours'] = time_info['span_hours']
        metrics['unique_days'] = time_info['unique_days']
        metrics['avg_per_day'] = time_info['avg_per_day']
        metrics['total_log_entries'] = time_info['total_entries']
        metrics['successes'] = time_info.get('successes', 0)
        metrics['failures'] = time_info.get('failures', 0)
        metrics['json_screenshots'] = time_info.get('screenshots', 0)
        metrics['json_links'] = time_info.get('total_links', 0)
        metrics['json_titles'] = time_info.get('total_titles', 0)
        metrics['site_stats'] = time_info.get('site_stats', {})
    else:
        metrics['time_span_hours'] = 0
        metrics['unique_days'] = 0
        metrics['avg_per_day'] = 0
        metrics['total_log_entries'] = 0
        metrics['successes'] = 0
        metrics['failures'] = 0
        metrics['json_screenshots'] = 0
        metrics['json_links'] = 0
        metrics['json_titles'] = 0
        metrics['site_stats'] = {}
    
    # Format time display - show dates if they differ
    if time_info:
        start_date = time_info['start'].strftime("%m/%d")
        end_date = time_info['end'].strftime("%m/%d")
        mean_time = time_info['mean'].strftime("%H:%M")
        
        if start_date == end_date:
            # Same day - just show times
            metrics['time_display'] = f"{time_info['start'].strftime('%H:%M')}-{time_info['end'].strftime('%H:%M')}"
        else:
            # Different days - show date+time
            metrics['time_display'] = f"{start_date} {time_info['start'].strftime('%H:%M')} - {end_date} {time_info['end'].strftime('%H:%M')}"
        
        metrics['mean_time'] = mean_time
    else:
        metrics['time_display'] = "N/A"
        metrics['mean_time'] = "N/A"
    
    site_metrics = []
    
    for onion_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, onion_addr)
        
        # Check for image
        has_image = False
        for img_name in ["index.png", f"{onion_addr}.png"]:
            if os.path.exists(os.path.join(site_dir, 'images', img_name)):
                has_image = True
                metrics['sites_with_images'] += 1
                break
        
        # Check for title
        html_file = os.path.join(site_dir, 'htmls', f"{onion_addr}.html")
        title = extract_title_from_html(html_file)
        if title:
            metrics['sites_with_titles'] += 1
        
        # Count outbound links
        outbound_count = 0
        discovered_count = 0
        
        urls_dir = os.path.join(site_dir, 'urls')
        if os.path.exists(urls_dir):
            for f in os.listdir(urls_dir):
                if f.endswith('_links.txt'):
                    with open(os.path.join(urls_dir, f), 'r') as lf:
                        outbound_count += sum(1 for line in lf if '.onion' in line)
        
        disc_dir = os.path.join(site_dir, 'discovered_links')
        if os.path.exists(disc_dir):
            for f in os.listdir(disc_dir):
                if f.endswith('_links.txt'):
                    with open(os.path.join(disc_dir, f), 'r') as lf:
                        discovered_count += sum(1 for line in lf if '.onion' in line)
        
        metrics['total_outbound_links'] += outbound_count
        metrics['total_discovered_links'] += discovered_count
        metrics['outbound_distribution'].append(outbound_count)
        metrics['link_counts'].append(outbound_count + discovered_count)
        
        site_metrics.append({
            'addr': onion_addr,
            'title': title or onion_addr[:20],
            'has_image': has_image,
            'outbound': outbound_count,
            'discovered': discovered_count,
            'total': outbound_count + discovered_count
        })
    
    # Calculate inbound links for each site
    for i, addr in enumerate(onion_sites):
        inbound = 0
        for other_addr in onion_sites:
            if other_addr != addr:
                other_dir = os.path.join(scraped_data_dir, other_addr)
                for d in ['urls', 'discovered_links']:
                    path = os.path.join(other_dir, d)
                    if os.path.exists(path):
                        for f in os.listdir(path):
                            if f.endswith('_links.txt'):
                                with open(os.path.join(path, f), 'r') as lf:
                                    for line in lf:
                                        if addr in line:
                                            inbound += 1
                                            break
        site_metrics[i]['inbound'] = inbound
        metrics['inbound_distribution'].append(inbound)
    
    # Calculate statistics
    metrics['avg_outbound'] = sum(metrics['outbound_distribution']) / len(metrics['outbound_distribution']) if metrics['outbound_distribution'] else 0
    metrics['max_outbound'] = max(metrics['outbound_distribution']) if metrics['outbound_distribution'] else 0
    metrics['avg_inbound'] = sum(metrics['inbound_distribution']) / len(metrics['inbound_distribution']) if metrics['inbound_distribution'] else 0
    metrics['max_inbound'] = max(metrics['inbound_distribution']) if metrics['inbound_distribution'] else 0
    
    print(f"\nDashboard Metrics:")
    for k, v in metrics.items():
        if not isinstance(v, list):
            print(f"  {k}: {v}")
    
    # Generate HTML
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Crawl Analytics Dashboard</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ margin: 0; padding: 20px; background: #0a0a0f; font-family: 'Segoe UI', sans-serif; }}
        #header {{
            position: fixed; top: 0; left: 0; right: 0;
            background: rgba(10,10,15,0.95); padding: 15px 20px;
            border-bottom: 1px solid #222; z-index: 10;
        }}
        #header h1 {{ margin: 0; color: #fff; font-size: 18px; }}
        #dashboard {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            padding: 80px 20px 20px;
        }}
        .card {{
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 10px;
            padding: 20px;
        }}
        .card h3 {{
            margin: 0 0 15px 0;
            color: #fff;
            font-size: 14px;
            font-weight: 500;
        }}
        .stat-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
        }}
        .stat {{
            text-align: center;
            padding: 15px;
            background: #21262d;
            border-radius: 8px;
        }}
        .stat-value {{
            font-size: 28px;
            font-weight: bold;
            color: #58a6ff;
        }}
        .stat-label {{
            font-size: 11px;
            color: #8b949e;
            margin-top: 5px;
        }}
        .chart-container {{
            position: relative;
            height: 250px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #30363d;
        }}
        th {{ color: #8b949e; font-weight: 500; }}
        td {{ color: #c9d1d9; }}
        .bar {{ fill: #58a6ff; }}
        .bar:hover {{ fill: #79c0ff; }}
    </style>
</head>
<body>
    <div id="header">
        <h1>Crawl Analytics Dashboard</h1>
    </div>
    <div id="dashboard">
        <!-- Summary Stats -->
        <div class="card">
            <h3>📊 Summary Statistics</h3>
            <div class="stat-grid">
                <div class="stat">
                    <div class="stat-value">{metrics['total_sites']}</div>
                    <div class="stat-label">Sites Crawled</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics['json_screenshots'] if metrics['json_screenshots'] > 0 else metrics['sites_with_images']}</div>
                    <div class="stat-label">With Screenshots</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics['successes'] if metrics['successes'] > 0 else metrics['sites_with_titles']}</div>
                    <div class="stat-label">Successful</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics['failures']}</div>
                    <div class="stat-label">Failed</div>
                </div>
            </div>
            <div class="stat-grid" style="margin-top: 15px;">
                <div class="stat">
                    <div class="stat-value">{metrics['unique_days']}</div>
                    <div class="stat-label">Days Active</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics['avg_per_day']:.1f}</div>
                    <div class="stat-label">Avg Crawls/Day</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics['mean_time']}</div>
                    <div class="stat-label">Mean Crawl Time</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics['total_log_entries']}</div>
                    <div class="stat-label">Log Entries</div>
                </div>
            </div>
            <div style="margin-top: 15px; text-align: center; font-size: 12px; color: #8b949e;">
                Period: {metrics['time_display']} | Span: {metrics['time_span_hours']:.1f}h
            </div>
            {f'<div style="margin-top: 10px; text-align: center; font-size: 12px; color: #8b949e;">Links: {metrics["json_links"]} | Titles: {metrics["json_titles"]}</div>' if metrics['json_links'] > 0 else ''}
        </div>
        
        <!-- Link Statistics -->
        <div class="card">
            <h3>🔗 Link Statistics</h3>
            <div class="stat-grid">
                <div class="stat">
                    <div class="stat-value">{metrics['json_links'] if metrics['json_links'] > 0 else metrics['total_outbound_links']}</div>
                    <div class="stat-label">Total Links</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics['json_titles'] if metrics['json_titles'] > 0 else metrics['total_discovered_links']}</div>
                    <div class="stat-label">Total Titles</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics['avg_outbound']:.1f}</div>
                    <div class="stat-label">Avg Outbound/Site</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{metrics['max_outbound']}</div>
                    <div class="stat-label">Max Outbound</div>
                </div>
            </div>
        </div>

        <!-- Per-Site Crawl History -->
        <div class="card" style="grid-column: span 2;">
            <h3>📍 Per-Site Crawl History</h3>
            <table>
                <thead>
                    <tr>
                        <th>Onion Address</th>
                        <th>Attempts</th>
                        <th>Success</th>
                        <th>Fail</th>
                        <th>Links</th>
                        <th>Titles</th>
                        <th>Screenshot</th>
                        <th>Last Status</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f"""<tr>
                        <td style="font-family: monospace; font-size: 11px;">{addr[:20]}...</td>
                        <td>{data['attempts']}</td>
                        <td>{data['successes']}</td>
                        <td>{data['failures']}</td>
                        <td>{data['total_links']}</td>
                        <td>{data['total_titles']}</td>
                        <td>{'📸' if data['has_screenshot'] else '❌'}</td>
                        <td>{data['last_status']}<br><span style="font-size:10px;opacity:0.6">{data['last_timestamp']}</span></td>
                    </tr>""" for addr, data in sorted(metrics['site_stats'].items(), key=lambda x: -x[1]['successes'])[:15])}
                </tbody>
            </table>
        </div>
        
        <!-- Outbound Distribution Chart -->
        <div class="card">
            <h3>📈 Outbound Links Distribution</h3>
            <div class="chart-container">
                <canvas id="outboundChart"></canvas>
            </div>
        </div>
        
        <!-- Inbound Distribution Chart -->
        <div class="card">
            <h3>📉 Inbound Links Distribution</h3>
            <div class="chart-container">
                <canvas id="inboundChart"></canvas>
            </div>
        </div>
        
        <!-- Top Sites Table -->
        <div class="card" style="grid-column: span 2;">
            <h3>🏆 Top Sites by Total Links</h3>
            <table>
                <thead>
                    <tr>
                        <th>Site</th>
                        <th>Outbound</th>
                        <th>Inbound</th>
                        <th>Total</th>
                        <th>Has Image</th>
                    </tr>
                </thead>
                <tbody>
                    {''.join(f"""<tr>
                        <td>{s['title']}</td>
                        <td>{s['outbound']}</td>
                        <td>{s['inbound']}</td>
                        <td>{s['total']}</td>
                        <td>{'📸' if s['has_image'] else '❌'}</td>
                    </tr>""" for s in sorted(site_metrics, key=lambda x: -x['total'])[:10])}
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const outboundData = {json.dumps(metrics['outbound_distribution'])};
        const inboundData = {json.dumps(metrics['inbound_distribution'])};
        
        // Create histogram buckets
        function createHistogram(data, buckets = 10) {{
            const max = Math.max(...data, 1);
            const bucketSize = Math.ceil(max / buckets);
            const histogram = Array(buckets).fill(0);
            
            data.forEach(v => {{
                const bucket = Math.min(Math.floor(v / bucketSize), buckets - 1);
                histogram[bucket]++;
            }});
            
            return {{
                labels: Array.from({{length: buckets}}, (_, i) => 
                    `${{i * bucketSize}}-${{(i + 1) * bucketSize - 1}}`),
                values: histogram
            }};
        }}
        
        const outboundHist = createHistogram(outboundData);
        const inboundHist = createHistogram(inboundData);
        
        // Chart defaults
        Chart.defaults.color = '#8b949e';
        Chart.defaults.borderColor = '#30363d';
        
        // Outbound chart
        new Chart(document.getElementById('outboundChart'), {{
            type: 'bar',
            data: {{
                labels: outboundHist.labels,
                datasets: [{{
                    label: 'Sites',
                    data: outboundHist.values,
                    backgroundColor: 'rgba(88, 166, 255, 0.7)',
                    borderColor: 'rgba(88, 166, 255, 1)',
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
        
        // Inbound chart
        new Chart(document.getElementById('inboundChart'), {{
            type: 'bar',
            data: {{
                labels: inboundHist.labels,
                datasets: [{{
                    label: 'Sites',
                    data: inboundHist.values,
                    backgroundColor: 'rgba(167, 139, 250, 0.7)',
                    borderColor: 'rgba(167, 139, 250, 1)',
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
    
    output_file = os.path.join(scraped_data_dir, "crawl_dashboard.html")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"\nCrawl Dashboard created at {output_file}")
    return output_file


def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()
    
    if not os.path.exists(scraped_data_path):
        print(f"Error: scraped_data directory not found at {scraped_data_path}")
        return

    generate_crawl_dashboard(str(scraped_data_path))


if __name__ == "__main__":
    main()
