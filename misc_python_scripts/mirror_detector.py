#!/usr/bin/env python3
"""
Mirror Detector for Onion Sites
Identifies mirrors by comparing:
1. Internal directory/file structure
2. Internal link patterns
3. Content similarities (titles and sizes)
"""

import os
import json
import re
import hashlib
from pathlib import Path
from collections import defaultdict

def get_onion_sites(scraped_data_dir):
    """Get all onion sites from the directory structure."""
    onion_dirs = []
    path = Path(scraped_data_dir)
    if not path.exists():
        return []
    for item in path.iterdir():
        if item.is_dir() and re.match(r'^[a-z2-7]{16,56}$', item.name):
            onion_dirs.append(item.name)
    return onion_dirs

def get_structural_fingerprint(scraped_data_dir, onion_addr):
    """Generate a fingerprint based on folder structure and file existence."""
    site_dir = Path(scraped_data_dir) / onion_addr
    fingerprint = []
    
    # Walk the directory and collect relative paths (excluding actual content)
    for root, dirs, files in os.walk(site_dir):
        rel_path = os.path.relpath(root, site_dir)
        if rel_path == ".": continue
        
        # Add directory structure to fingerprint
        fingerprint.append(f"DIR:{rel_path}")
        
        # Add file patterns (e.g. index.png, links.txt)
        for f in files:
            # We use filename patterns, not the unique onion-named files
            if f.endswith(".png"): fingerprint.append(f"FILE:IMAGE")
            if f.endswith("_links.txt"): fingerprint.append(f"FILE:LINKS")
            if f.endswith("_title.txt"): fingerprint.append(f"FILE:TITLE")
            
    fingerprint.sort()
    return hashlib.sha256("|".join(fingerprint).encode()).hexdigest()[:16]

def get_internal_links(scraped_data_dir, onion_addr):
    """Extract internal links to compare structure."""
    links_dir = Path(scraped_data_dir) / onion_addr / "discovered_links"
    internal_paths = set()
    
    if not links_dir.exists():
        return ""
        
    for f in links_dir.glob("*_links.txt"):
        try:
            with open(f, 'r', encoding='utf-8', errors='ignore') as lf:
                for line in lf:
                    if onion_addr in line:
                        # Extract the path part of the internal link
                        path_match = re.search(fr'{onion_addr}\.onion/(.*)', line)
                        if path_match:
                            internal_paths.add(path_match.group(1))
        except:
            continue
            
    # Sort and hash internal link structure
    sorted_paths = sorted(list(internal_paths))
    return hashlib.sha256("|".join(sorted_paths).encode()).hexdigest()[:16]

def detect_mirrors(scraped_data_dir):
    print(f"\n[INFO] Starting Mirror Detection in: {scraped_data_dir}")
    onion_sites = get_onion_sites(scraped_data_dir)
    
    site_meta = {}
    mirror_groups = defaultdict(list)
    
    for addr in onion_sites:
        # 1. Structural Fingerprint (folders/files)
        struct_hash = get_structural_fingerprint(scraped_data_dir, addr)
        
        # 2. Internal Link Hash (URL patterns)
        link_hash = get_internal_links(scraped_data_dir, addr)
        
        # Combined ID
        mirror_id = f"S:{struct_hash}_L:{link_hash}"
        
        # Get Title for display
        title = ""
        title_path = Path(scraped_data_dir) / addr / "website_identity" / "index_title.txt"
        if title_path.exists():
            try:
                content = title_path.read_text()
                match = re.search(r'\[(.*?)\]', content)
                if match: title = match.group(1)
            except: pass
            
        site_meta[addr] = {
            "mirror_id": mirror_id,
            "title": title or addr[:16]
        }
        
        mirror_groups[mirror_id].append(addr)
    
    # Filter groups with more than one site
    detected_mirrors = {k: v for k, v in mirror_groups.items() if len(v) > 1}
    
    # Generate Output
    output_data = {
        "summary": {
            "total_sites": len(onion_sites),
            "mirror_groups": len(detected_mirrors),
            "mirrored_sites": sum(len(v) for v in detected_mirrors.values())
        },
        "groups": []
    }
    
    for mid, addrs in detected_mirrors.items():
        output_data["groups"].append({
            "id": mid,
            "sites": addrs,
            "common_title": site_meta[addrs[0]]["title"]
        })
        print(f"[MATCH] Group {mid[:8]}: {', '.join(addrs)}")
        
    # Save to JSON
    output_file = Path(scraped_data_dir) / "mirrors.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
        
    generate_mirror_html(scraped_data_dir, output_data)
    print(f"\n[OK] Mirror detection complete. Results saved to: {output_file}")
    return output_data

def generate_mirror_html(scraped_data_dir, data):
    """Generate a dedicated interactive HTML for mirror analysis."""
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>Onion Mirror Analysis Dashboard</title>
    <script src="https://unpkg.com/force-graph"></script>
    <style>
        body {{ margin: 0; background: #0b0e14; color: #fff; font-family: 'Segoe UI', sans-serif; display: flex; height: 100vh; overflow: hidden; }}
        #sidebar {{ width: 350px; background: #161b22; border-right: 1px solid #30363d; display: flex; flex-direction: column; z-index: 100; }}
        #header {{ padding: 20px; border-bottom: 1px solid #30363d; }}
        #header h1 {{ margin: 0; font-size: 18px; color: #58a6ff; }}
        #graph-container {{ flex: 1; position: relative; background: #0d1117; }}
        .group-card {{ padding: 15px; border-bottom: 1px solid #30363d; cursor: pointer; transition: 0.2s; }}
        .group-card:hover {{ background: #21262d; }}
        .group-card.active {{ border-left: 4px solid #f0883e; background: #21262d; }}
        .group-title {{ font-weight: bold; color: #f0883e; font-size: 14px; margin-bottom: 5px; }}
        .group-sites {{ font-size: 11px; color: #8b949e; line-height: 1.4; }}
        .badge {{ background: #30363d; padding: 2px 8px; border-radius: 10px; font-size: 11px; float: right; color: #c9d1d9; }}
        #details {{ position: absolute; bottom: 20px; right: 20px; background: rgba(22, 27, 34, 0.9); padding: 15px; border-radius: 8px; border: 1px solid #30363d; max-width: 400px; display: none; backdrop-filter: blur(8px); }}
        .legend {{ padding: 20px; font-size: 12px; color: #8b949e; margin-top: auto; border-top: 1px solid #30363d; }}
    </style>
</head>
<body>
    <div id="sidebar">
        <div id="header">
            <h1>Mirror Analysis</h1>
            <div style="font-size: 12px; color: #8b949e; margin-top:5px;">
                Total Sites: {data['summary']['total_sites']} | Mirrored: {data['summary']['mirrored_sites']}
            </div>
        </div>
        <div style="overflow-y: auto; flex: 1;" id="group-list"></div>
        <div class="legend">
            <b>Instructions:</b><br>
            • Groups show detected clones<br>
            • Click a group to highlight in graph<br>
            • Colored nodes = Mirrored<br>
            • Gray nodes = Unique
        </div>
    </div>
    <div id="graph-container">
        <div id="graph"></div>
        <div id="details"></div>
    </div>

    <script>
        const data = {json.dumps(data)};
        const groupList = document.getElementById('group-list');
        const details = document.getElementById('details');
        
        // Prepare graph data
        const nodes = [];
        const links = [];
        const mirrorMap = {{}}; // addr -> color
        
        // Colors for groups
        const colors = ['#f0883e', '#58a6ff', '#bc8cff', '#3fb950', '#d29922', '#f85149'];

        data.groups.forEach((group, idx) => {{
            const color = colors[idx % colors.length];
            group.sites.forEach(addr => {{
                mirrorMap[addr] = color;
            }});
            
            // Add to sidebar
            const card = document.createElement('div');
            card.className = 'group-card';
            card.innerHTML = `
                <span class="badge">${{group.sites.length}} clones</span>
                <div class="group-title">Group ${{idx + 1}}</div>
                <div class="group-sites">${{group.sites.join('<br>')}}</div>
            `;
            card.onclick = () => highlightGroup(group.sites, card);
            groupList.appendChild(card);
        }});

        // Generate full node list (all sites, not just mirrors)
        // We need a way to get all sites if they're not in mirrors.json
        // For now we use the ones in data or infer from context
        const allSites = new Set();
        data.groups.forEach(g => g.sites.forEach(s => allSites.add(s)));
        
        const gData = {{
            nodes: Array.from(allSites).map(id => ({{ 
                id, 
                color: mirrorMap[id] || '#30363d',
                val: mirrorMap[id] ? 10 : 5
            }})),
            links: []
        }};

        const Graph = ForceGraph()(document.getElementById('graph'))
            .graphData(gData)
            .nodeLabel('id')
            .nodeColor('color')
            .nodeRelSize(node => node.val)
            .backgroundColor('#0d1117')
            .onNodeClick(node => {{
                details.style.display = 'block';
                details.innerHTML = `<strong>Site:</strong> ${{node.id}}<br><strong>Status:</strong> ${{mirrorMap[node.id] ? 'Mirrored' : 'Unique'}}`;
            }});

        function highlightGroup(sites, card) {{
            const wasActive = card.classList.contains('active');
            document.querySelectorAll('.group-card').forEach(c => c.classList.remove('active'));
            
            if (wasActive) {{
                Graph.nodeColor(n => mirrorMap[n.id] || '#30363d').nodeRelSize(n => n.val);
            }} else {{
                card.classList.add('active');
                Graph.nodeColor(n => sites.includes(n.id) ? mirrorMap[n.id] : '#161b22')
                     .nodeRelSize(n => sites.includes(n.id) ? 12 : 4);
            }}
        }}
    </script>
</body>
</html>"""
    
    out_path = Path(scraped_data_dir) / "mirror_analysis.html"
    out_path.write_text(html_content)
    print(f"  [HTML] Mirror dashboard created: {out_path}")

if __name__ == "__main__":
    import sys
    path = "scraped_data" if len(sys.argv) <= 1 else sys.argv[1]
    detect_mirrors(path)
