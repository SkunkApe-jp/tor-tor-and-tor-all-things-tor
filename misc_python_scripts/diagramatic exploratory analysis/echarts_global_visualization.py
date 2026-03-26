#!/usr/bin/env python3
"""
ECharts High-Performance Network Visualization
Uses Canvas rendering for smooth interaction with thousands of nodes.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path

def extract_onion_addresses_from_file(file_path):
    onion_addresses = set()
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                url_matches = re.findall(r'https?://([a-z2-7]{16,56})\.onion[^\s\'\"<>]*', content)
                for addr in url_matches:
                    onion_addresses.add(addr)
        except: pass
    return list(onion_addresses)

def get_onion_sites(scraped_data_dir):
    if not os.path.exists(scraped_data_dir):
        return []
    onion_dirs = []
    for item in os.listdir(scraped_data_dir):
        item_path = os.path.join(scraped_data_dir, item)
        if os.path.isdir(item_path) and 16 <= len(item) <= 60:
            onion_dirs.append(item)
    return onion_dirs

def extract_title_from_html(html_file_path):
    if os.path.exists(html_file_path):
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                title_match = re.search(r'<title[^>]*>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    return ' '.join(title_match.group(1).strip().split())
        except: pass
    return None

def extract_title_from_identity(identity_dir):
    if os.path.exists(identity_dir):
        for file_name in os.listdir(identity_dir):
            if file_name.endswith('_title.txt'):
                try:
                    with open(os.path.join(identity_dir, file_name), 'r', encoding='utf-8') as f:
                        line = f.readline()
                        match = re.search(r'\[(.*?)\] ->', line)
                        if match: return match.group(1).strip()
                except: pass
    return None

def generate_echarts_viz(scraped_data_dir):
    onion_sites = get_onion_sites(scraped_data_dir)
    print(f"Found {len(onion_sites)} onion sites for ECharts")

    nodes = []
    links = []
    site_data = {}

    for addr in onion_sites:
        site_dir = os.path.join(scraped_data_dir, addr)
        title = extract_title_from_html(os.path.join(site_dir, 'htmls', f"{addr}.html"))
        if not title:
            title = extract_title_from_identity(os.path.join(site_dir, 'website_identity'))
        if not title:
            title = f"{addr}.onion"
        
        # Check for site image
        img_path_rel = f"{addr}/images/index.png"
        img_path_abs = os.path.join(scraped_data_dir, addr, 'images', 'index.png')
        has_image = os.path.exists(img_path_abs)
        
        connected_onions = set()
        for d in ['discovered_links', 'urls']:
            d_path = os.path.join(site_dir, d)
            if os.path.exists(d_path):
                for f in os.listdir(d_path):
                    if f.endswith('_links.txt'):
                        connected_onions.update(extract_onion_addresses_from_file(os.path.join(d_path, f)))
        
        node_entry = {
            "id": addr,
            "name": title,
            "symbolSize": 30 if has_image else 15,
            "itemStyle": {"color": "#5470c6"}
        }
        
        if has_image:
            # Note: We use the relative path so it works when served
            node_entry["symbol"] = f"image://{img_path_rel}"
            node_entry["value"] = img_path_rel # For tooltip access
        
        nodes.append(node_entry)
        site_data[addr] = list(connected_onions)

    for source, targets in site_data.items():
        for target in targets:
            pure_target = target.replace('.onion', '')
            if pure_target in site_data and source != pure_target:
                links.append({"source": source, "target": pure_target})

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>ECharts Onion Network</title>
    <script src="../../../echarts.min.js"></script>
    <style>
        body, #main {{ width: 100vw; height: 100vh; margin: 0; background: #100c2a; overflow: hidden; }}
        #ui {{ position: absolute; top: 20px; left: 20px; z-index: 10; color: #fff; pointer-events: none; }}
        .tooltip-card {{ padding: 10px; min-width: 200px; }}
        .tooltip-img {{ max-width: 100%; max-height: 150px; width: auto; height: auto; border-radius: 4px; margin-top: 5px; border: 1px solid #444; display: block; }}
    </style>
</head>
<body>
    <div id="ui">
        <h2 style="margin:0; font-family:sans-serif; color:#7ce7ffd6;">ECharts Canvas Engine</h2>
        <p style="opacity:0.6; font-size:12px;">{len(nodes)} nodes, {len(links)} links</p>
    </div>
    <div id="main"></div>
    <script>
        const chart = echarts.init(document.getElementById('main'), 'dark');
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};

        const option = {{
            backgroundColor: '#100c2a',
            tooltip: {{
                trigger: 'item',
                formatter: function(params) {{
                    if (params.dataType === 'node') {{
                        let res = '<div class="tooltip-card">';
                        res += '<span style="color:#58a6ff; font-weight:bold;">' + params.name + '</span><br/>';
                        res += '<span style="font-size:11px; opacity:0.7;">' + params.data.id + '.onion</span>';
                        if (params.data.value) {{
                            res += '<br/><img src="' + params.data.value + '" class="tooltip-img" />';
                        }}
                        res += '</div>';
                        return res;
                    }}
                    return params.name;
                }},
                backgroundColor: 'rgba(13, 17, 23, 0.9)',
                borderColor: '#30363d',
                textStyle: {{ color: '#fff' }}
            }},
            series: [
                {{
                    type: 'graph',
                    layout: 'force',
                    data: nodes,
                    links: links,
                    roam: true,
                    draggable: true,
                    edgeSymbol: ['none', 'arrow'],
                    edgeSymbolSize: [4, 10],
                    label: {{
                        show: true,
                        position: 'bottom',
                        color: '#aaa',
                        fontSize: 10,
                        formatter: '{{b}}'
                    }},
                    force: {{
                        repulsion: 300,
                        edgeLength: 100,
                        gravity: 0.1
                    }},
                    lineStyle: {{
                        color: 'source',
                        curveness: 0.1,
                        opacity: 0.4
                    }},
                    emphasis: {{
                        focus: 'adjacency',
                        lineStyle: {{
                            width: 3
                        }}
                    }}
                }}
            ]
        }};

        chart.setOption(option);
        window.addEventListener('resize', () => chart.resize());
    </script>
</body>
</html>"""

    out = os.path.join(scraped_data_dir, "echarts_visualization.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"ECharts visualization saved to {out}")

if __name__ == "__main__":
    import sys
    # Default path is hardcoded here - can be overridden via command-line argument
    # Use "../scraped_data" when running from misc_python_scripts subfolder
    DEFAULT_SCRAPED_DATA_PATH = "../scraped_data"
    path = DEFAULT_SCRAPED_DATA_PATH if not len(sys.argv) > 1 else sys.argv[1]
    if os.path.exists(path):
        generate_echarts_viz(path)
    else:
        print(f"Path {path} not found.")
