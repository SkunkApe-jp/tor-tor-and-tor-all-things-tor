#!/usr/bin/env python3
"""
Onion Network Intelligence Report V2

Analyzes the network for:
- Mirror/Clone sites (same title + similar HTML size)
- Unexplored Leads (onions found in links but not yet scraped)
- Title-based duplicates
"""

import os
import re
from collections import Counter, defaultdict
from pathlib import Path


def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and re.match(r'^[a-z2-7]{16,56}$', item):
            onion_dirs.append(item)
    return onion_dirs


def calculate_vanity_score(onion_addr):
    """Checks if the onion starts with a recognizable keyword (Vanity)."""
    for word in BRAND_KEYWORDS:
        if onion_addr.startswith(word):
            return word
    return None


def extract_title_from_file(title_path):
    """Extract title from website_titles file."""
    if os.path.exists(title_path):
        try:
            with open(title_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except:
            pass
    return ""


def extract_title_from_html(html_path):
    """Extract title from HTML file."""
    if os.path.exists(html_path):
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    return ' '.join(title_match.group(1).strip().split())[:50]
        except:
            pass
    return ""


def collect_discovered_links(site_dir):
    """Collect all discovered onion links from a site."""
    discovered = []
    
    for folder in ['urls', 'discovered_links']:
        folder_path = os.path.join(site_dir, folder)
        if os.path.exists(folder_path):
            for f in os.listdir(folder_path):
                if f.endswith('_links.txt'):
                    try:
                        with open(os.path.join(folder_path, f), 'r') as lf:
                            content = lf.read()
                            found = re.findall(r'([a-z2-7]{16,56})\.onion', content)
                            discovered.extend(found)
                    except:
                        pass
    
    return discovered


def generate_intelligence_report(scraped_data_dir):
    """Generate comprehensive network intelligence report."""
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"\nPerforming Network Intelligence Analysis on {len(onion_sites)} sites...")

    site_fingerprints = []
    all_discovered = []
    titles_map = {}

    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)

        # 1. Capture Fingerprint (Size + Title)
        html_size = 0
        html_path = os.path.join(site_dir, 'htmls', f"{addr}.html")
        if os.path.exists(html_path):
            html_size = os.path.getsize(html_path)

        # Try website_titles first, then HTML
        title = extract_title_from_file(os.path.join(site_dir, 'website_titles', f"{addr}.txt"))
        if not title:
            title = extract_title_from_html(html_path)

        titles_map[addr] = title

        site_fingerprints.append({
            'addr': addr,
            'title': title,
            'size': html_size
        })
        
        # 3. Collect Discovery Leads
        discovered = collect_discovered_links(site_dir)
        all_discovered.extend(discovered)
    
    # --- ANALYSIS 1: Find Mirrors (Title + Size) ---
    mirrors = []
    seen = set()
    for i, s1 in enumerate(site_fingerprints):
        if s1['addr'] in seen:
            continue
        group = [s1['addr']]
        for j, s2 in enumerate(site_fingerprints[i+1:], i+1):
            # If title is the same and size is within 500 bytes
            if s1['title'] == s2['title'] and s1['title'] != "" and abs(s1['size'] - s2['size']) < 500:
                group.append(s2['addr'])
                seen.add(s2['addr'])
        if len(group) > 1:
            mirrors.append(group)
    
    # --- ANALYSIS 2: Title-based Duplicates ---
    title_counts = Counter(titles_map.values())
    duplicate_titles = [t for t, count in title_counts.items() if count > 1 and t != ""]
    
    # --- ANALYSIS 3: Lead Generation ---
    unscraped = [addr for addr in all_discovered if addr not in onion_sites]
    top_leads = Counter(unscraped).most_common(20)
    
    # --- OUTPUT REPORT ---
    print("\n" + "="*60)
    print("           ONION NETWORK INTELLIGENCE REPORT")
    print("="*60)

    print(f"\n[👯] POTENTIAL MIRRORS/CLONES: {len(mirrors)} groups")
    for i, m in enumerate(mirrors[:5], 1):
        title = titles_map.get(m[0], 'Unknown')[:30]
        print(f"  Group {i}: '{title}'")
        print(f"    Sites: {', '.join([a[:12] for a in m])}...")

    print(f"\n[📋] TITLE DUPLICATES (Shared Titles): {len(duplicate_titles)}")
    for t in duplicate_titles[:5]:
        sites = [a[:12] for a, title in titles_map.items() if title == t]
        print(f"  - '{t[:40]}': {len(sites)} sites")

    print(f"\n[🚀] TOP UNEXPLORED LEADS (Next to crawl): {len(top_leads)}")
    for addr, count in top_leads[:15]:
        print(f"  - {addr}.onion (Found {count} times)")

    print("\n" + "="*60)

    return {
        'mirrors': mirrors,
        'duplicate_titles': duplicate_titles,
        'top_leads': top_leads,
        'total_sites': len(onion_sites),
        'total_discovered': len(all_discovered),
        'unique_discovered': len(set(all_discovered))
    }


def generate_intelligence_html(report_data, scraped_data_dir, titles_map):
    """Generate HTML intelligence report."""
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Network Intelligence Report</title>
    <style>
        :root {{ --bg: #0a0a0c; --card: #15151e; --blue: #3b82f6; --green: #10b981; --gold: #f59e0b; --red: #ef4444; }}
        body {{ background: var(--bg); color: #ccc; font-family: 'Inter', sans-serif; padding: 40px; }}
        .header {{ text-align: center; margin-bottom: 40px; }}
        .header h1 {{ color: #fff; margin: 0; }}
        .stats {{ display: flex; gap: 20px; justify-content: center; margin: 20px 0; }}
        .stat {{ background: var(--card); padding: 20px; border-radius: 8px; text-align: center; min-width: 150px; }}
        .stat-val {{ font-size: 28px; font-weight: bold; color: #fff; }}
        .stat-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 25px; }}
        .card {{ background: var(--card); padding: 25px; border-radius: 12px; border: 1px solid #222; }}
        h2 {{ color: #fff; font-size: 1.1rem; margin-top: 0; border-bottom: 1px solid #333; padding-bottom: 15px; display: flex; align-items: center; gap: 10px; }}
        .row {{ padding: 12px 0; border-bottom: 1px solid #1f1f1f; }}
        .row-title {{ color: #eee; font-size: 14px; }}
        .row-meta {{ font-size: 11px; color: #555; margin-top: 4px; }}
        .tag {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: bold; }}
        .tag-mirror {{ background: var(--gold); color: #000; }}
        .tag-lead {{ background: var(--green); color: #fff; }}
        .addr {{ font-family: monospace; font-size: 11px; color: #666; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🕵️ Onion Network Intelligence</h1>
        <div class="stats">
            <div class="stat">
                <div class="stat-val">{report_data['total_sites']}</div>
                <div class="stat-label">Sites Analyzed</div>
            </div>
            <div class="stat">
                <div class="stat-val">{len(report_data['mirrors'])}</div>
                <div class="stat-label">Mirror Groups</div>
            </div>
            <div class="stat">
                <div class="stat-val">{len(report_data['duplicate_titles'])}</div>
                <div class="stat-label">Duplicate Titles</div>
            </div>
            <div class="stat">
                <div class="stat-val">{len(report_data['top_leads'])}</div>
                <div class="stat-label">Top Leads</div>
            </div>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h2>👯 Mirror / Clone Groups</h2>
            {''.join(f'''
            <div class="row">
                <div class="row-title"><span class="tag tag-mirror">GROUP {i+1}</span></div>
                <div class="row-meta">
                    {''.join(f'<div class="addr">{a}</div>' for a in group[:5])}
                </div>
            </div>
            ''' for i, group in enumerate(report_data['mirrors'][:10]))}
        </div>

        <div class="card">
            <h2>🚀 Top Unexplored Leads</h2>
            {''.join(f'''
            <div class="row">
                <div class="row-title"><span class="tag tag-lead">{count}x</span> {addr[:20]}...</div>
                <div class="row-meta addr">{addr}.onion</div>
            </div>
            ''' for addr, count in report_data['top_leads'][:15])}
        </div>

        <div class="card">
            <h2>📋 Duplicate Titles</h2>
            {''.join(f'''
            <div class="row">
                <div class="row-title">{title[:50]}</div>
                <div class="row-meta">Shared by multiple sites</div>
            </div>
            ''' for title in report_data['duplicate_titles'][:10])}
        </div>
    </div>
</body>
</html>"""
    
    output_path = os.path.join(scraped_data_dir, "intelligence_report.html")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"\nHTML Report: {output_path}")
    return output_path


def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()
    
    if not os.path.exists(scraped_data_path):
        print(f"Error: scraped_data directory not found at {scraped_data_path}")
        return
    
    # Generate report
    report_data = generate_intelligence_report(str(scraped_data_path))
    
    # Build titles map for HTML
    titles_map = {}
    for addr in get_onion_sites(str(scraped_data_path)):
        site_dir = os.path.join(scraped_data_path, addr)
        title = extract_title_from_file(os.path.join(site_dir, 'website_titles', f"{addr}.txt"))
        if not title:
            title = extract_title_from_html(os.path.join(site_dir, 'htmls', f"{addr}.html"))
        titles_map[addr] = title
    
    # Generate HTML
    generate_intelligence_html(report_data, str(scraped_data_path), titles_map)


if __name__ == "__main__":
    main()
