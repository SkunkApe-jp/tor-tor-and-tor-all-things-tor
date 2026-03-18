#!/usr/bin/env python3
"""
Onion Network Hub Analysis V2

Analyzes link graphs to identify:
- Master Hubs (sites that link to many others)
- Authority Sites (sites linked to by many others)
- Influence Ratios (destination vs gateway sites)
"""

import os
import json
import re
from collections import defaultdict
from pathlib import Path


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


def generate_hub_analysis_improved(scraped_data_dir):
    """Generate improved hub analysis with O(N) efficiency."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"\nBuilding Link Map for {len(onion_sites)} sites...")
    
    # --- PHASE 1: PRE-CALCULATE LINK GRAPH (O(N) Efficiency) ---
    # This prevents the nested loop bottleneck
    inbound_map = defaultdict(set)  # {target_onion: set(source_onions)}
    site_data = {}

    for source_addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, source_addr)
        outbound_targets = set()
        
        # Look for links in all folders
        for folder in ['urls', 'discovered_links']:
            path = os.path.join(site_dir, folder)
            if os.path.exists(path):
                for f in os.listdir(path):
                    if f.endswith('_links.txt'):
                        try:
                            with open(os.path.join(path, f), 'r') as lf:
                                content = lf.read()
                                # Find all unique onion addresses in the file
                                found = set(re.findall(r'([a-z2-7]{16,56})\.onion', content))
                                for target in found:
                                    if target != source_addr:  # Ignore self-links
                                        outbound_targets.add(target)
                                        inbound_map[target].add(source_addr)
                        except:
                            pass
        
        # Basic site info
        title = extract_title_from_html(os.path.join(site_dir, 'htmls', f"{source_addr}.html")) or source_addr[:20]
        site_data[source_addr] = {
            'title': title,
            'outbound_unique': len(outbound_targets),
            'inbound_unique': 0,  # Will fill next
            'ratio': 0.0
        }

    # --- PHASE 2: CALCULATE METRICS ---
    for addr in site_data:
        site_data[addr]['inbound_unique'] = len(inbound_map[addr])
        # Reputation Ratio: (Inbound / Outbound)
        # Higher means it's a "Destination", Lower means it's a "Directory"
        out = site_data[addr]['outbound_unique']
        inb = site_data[addr]['inbound_unique']
        site_data[addr]['ratio'] = round(inb / max(1, out), 2)
        site_data[addr]['total'] = inb + out

    # --- PHASE 3: RANKING ---
    top_hubs = sorted(site_data.items(), key=lambda x: -x[1]['outbound_unique'])[:15]
    top_authorities = sorted(site_data.items(), key=lambda x: -x[1]['inbound_unique'])[:15]
    top_ratio = sorted(site_data.items(), key=lambda x: -x[1]['ratio'])[:15]
    isolated = [k for k, v in site_data.items() if v['total'] == 0]

    # Max values for bar scaling in HTML
    max_out = max([v['outbound_unique'] for v in site_data.values()] + [1])
    max_in = max([v['inbound_unique'] for v in site_data.values()] + [1])

    # --- PHASE 4: HTML WITH IMPROVED DATA & CSS ---
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Network Hub Analysis</title>
    <style>
        :root {{ --bg: #0a0a0c; --card: #15151e; --blue: #3b82f6; --green: #10b981; --gold: #f59e0b; }}
        body {{ background: var(--bg); color: #ccc; font-family: 'Inter', sans-serif; padding: 40px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 25px; }}
        .card {{ background: var(--card); padding: 25px; border-radius: 12px; border: 1px solid #222; }}
        h2 {{ color: #fff; font-size: 1.1rem; margin-top: 0; border-bottom: 1px solid #333; padding-bottom: 15px; }}
        .row {{ display: flex; align-items: center; padding: 12px 0; border-bottom: 1px solid #1f1f1f; gap: 15px; }}
        .title-block {{ flex: 1; min-width: 0; }}
        .title {{ color: #eee; font-size: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        .addr {{ font-size: 11px; color: #555; text-transform: lowercase; }}
        
        /* Bar Visualization */
        .bar-container {{ width: 100px; height: 8px; background: #222; border-radius: 4px; overflow: hidden; margin-top: 4px; }}
        .bar-out {{ height: 100%; background: var(--blue); }}
        .bar-in {{ height: 100%; background: var(--green); }}
        
        .stat-val {{ font-family: monospace; font-size: 18px; font-weight: bold; width: 40px; text-align: right; }}
        .stat-out {{ color: var(--blue); }}
        .stat-in {{ color: var(--green); }}
    </style>
</head>
<body>
    <h1>Onion Network Insights</h1>
    <p style="color: #666; margin-bottom: 30px;">
        Analyzed {len(onion_sites)} sites | {len(isolated)} isolated (no links)
    </p>
    <div class="grid">
        <div class="card">
            <h2>🌍 Master Hubs (Mapping the Web)</h2>
            {''.join(f'''
            <div class="row">
                <div class="title-block">
                    <div class="title">{v['title']}</div>
                    <div class="addr">{k[:24]}...</div>
                    <div class="bar-container"><div class="bar-out" style="width:{(v['outbound_unique']/max_out)*100}%"></div></div>
                </div>
                <div class="stat-val stat-out">{v['outbound_unique']}</div>
            </div>
            ''' for k, v in top_hubs)}
        </div>

        <div class="card">
            <h2>🏛 Authority Sites (Most Trusted)</h2>
            {''.join(f'''
            <div class="row">
                <div class="title-block">
                    <div class="title">{v['title']}</div>
                    <div class="addr">{k[:24]}...</div>
                    <div class="bar-container"><div class="bar-in" style="width:{(v['inbound_unique']/max_in)*100}%"></div></div>
                </div>
                <div class="stat-val stat-in">{v['inbound_unique']}</div>
            </div>
            ''' for k, v in top_authorities)}
        </div>

        <div class="card">
            <h2>⚖️ Influence Ratio (In/Out)</h2>
            <p style="font-size: 11px; color: #666; margin-bottom: 15px;">High ratio = Destinations | Low ratio = Gateways</p>
            {''.join(f'''
            <div class="row">
                <div class="title-block">
                    <div class="title">{v['title']}</div>
                    <div class="addr">{k[:24]}...</div>
                </div>
                <div class="stat-val" style="color:var(--gold)">{v['ratio']}</div>
            </div>
            ''' for k, v in top_ratio if v['inbound_unique'] > 1)}
        </div>
    </div>
</body>
</html>"""
    
    output_path = os.path.join(scraped_data_dir, "hub_analysis_v2.html")
    with open(output_path, 'w') as f:
        f.write(html_content)
    print(f"Hub Analysis V2 Complete: {output_path}")
    return output_path


def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()
    
    if not os.path.exists(scraped_data_path):
        print(f"Error: scraped_data directory not found at {scraped_data_path}")
        return
    
    generate_hub_analysis_improved(str(scraped_data_path))


if __name__ == "__main__":
    main()
