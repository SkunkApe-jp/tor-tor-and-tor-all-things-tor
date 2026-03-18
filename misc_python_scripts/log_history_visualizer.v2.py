#!/usr/bin/env python3
"""
DeepScan | Discovery Reconciliation - Monochrome Edition
High-contrast Black & White visualization for target tracking.
"""

import os
import json
import re
from pathlib import Path

# Identify the onion hash to link yaml lines to folders
HASH_REGEX = r'[a-z2-7]{14,56}'

def main():
    script_dir = Path(__file__).parent
    scraped_dir = (script_dir / "../scraped_data").resolve()
    yaml_path = (script_dir / "../targets.yaml").resolve()
    output_html = scraped_dir / "target_coverage.html"

    # 1. Parse targets from YAML
    target_links = []
    if yaml_path.exists():
        content = yaml_path.read_text().splitlines()
        target_links = [line.strip().strip('- ').strip('"').strip("'") for line in content if '.onion' in line.lower()]

    # 2. Reconcile results
    folders = list(scraped_dir.iterdir()) if scraped_dir.exists() else []
    
    present_list, no_image_list, missing_list = [], [], []
    
    for link in target_links:
        match = re.search(HASH_REGEX, link.lower())
        hash_part = match.group(0) if match else None
        
        found_folder = None
        if hash_part:
            for f in folders:
                if f.is_dir() and hash_part in f.name.lower():
                    found_folder = f
                    break
        
        if found_folder:
            img_dir = found_folder / "images"
            if img_dir.exists() and list(img_dir.glob("index.*")):
                present_list.append(link)
            else:
                no_image_list.append(link)
        else:
            missing_list.append(link)

    # 3. Write files to disk
    (scraped_dir / "present_links.txt").write_text("\n".join(present_list))
    (scraped_dir / "non_image_links.txt").write_text("\n".join(no_image_list))
    (scraped_dir / "missing_targets.txt").write_text("\n".join(missing_list))

    # 4. Prepare dashboard data
    files_data = {
        "missing": "\n".join(missing_list) if missing_list else "ZERO_MISSING_TARGETS",
        "present": "\n".join(present_list) if present_list else "ZERO_SUCCESSFUL_CAPTURES",
        "noimg": "\n".join(no_image_list) if no_image_list else "ZERO_EMPTY_FOLDERS",
        "targets": "\n".join(target_links)
    }

    c_present, c_no_image, c_missing = len(present_list), len(no_image_list), len(missing_list)

    html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>DeepScan | Monochrome Terminal</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Inter:wght@400;600&family=Fira+Code:wght@400&display=swap" rel="stylesheet">
    <style>
        :root {{ 
            --bg: #000000; 
            --panel: #0a0a0a; 
            --accent: #284b63; 
            --dim: #000000; 
            --mid: #888888; 
            --text: #284b63; 
        }}
        body {{ 
            font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); 
            margin: 0; padding: 40px; display: flex; flex-direction: column; align-items: center; 
        }}
        .header {{ width: 100%; max-width: 1000px; margin-bottom: 30px; border-left: 4px solid var(--accent); padding-left: 20px; }}
        .card {{ background: var(--panel); border: 1px solid var(--dim); border-radius: 0; padding: 25px; width: 100%; max-width: 1000px; text-align: center; margin-bottom: 20px; }}
        .terminal {{ background: #000; border: 1px solid var(--dim); width: 100%; max-width: 1000px; overflow: hidden; }}
        .term-nav {{ background: #0a0a0a; padding: 10px; display: flex; gap: 5px; border-bottom: 1px solid var(--dim); }}
        .term-btn {{ 
            background: transparent; border: 1px solid var(--dim); color: var(--mid); 
            padding: 8px 15px; cursor: pointer; font-family: 'Orbitron'; font-size: 0.65rem; text-transform: uppercase;
        }}
        .term-btn.active {{ border-color: var(--accent); color: var(--accent); background: #111; }}
        #term-body {{ 
            padding: 20px; height: 350px; overflow-y: auto; font-family: 'Fira Code', monospace; 
            color: var(--accent); white-space: pre; text-align: left; font-size: 0.8rem; 
        }}
        h2 {{ font-family: 'Orbitron'; font-size: 0.7rem; color: var(--mid); margin-bottom: 20px; letter-spacing: 2px; }}
        ::-webkit-scrollbar {{ width: 5px; }}
        ::-webkit-scrollbar-thumb {{ background: var(--dim); }}
    </style>
</head>
<body>
    <div class="header">
        <h1 style="font-family: 'Orbitron'; color: var(--accent); margin:0; font-size: 1.8rem; letter-spacing: 4px;">RECON_RECONCILIATION</h1>
        <div style="color: var(--mid); font-family: 'Orbitron'; font-size: 0.7rem; margin-top: 5px;">
            TOTAL_TARGETS: {len(target_links)} | POSITIVE: {c_present} | NEGATIVE: {c_missing + c_no_image}
        </div>
    </div>

    <div class="card">
        <h2>Diverging Analysis (Positive vs Gap)</h2>
        <canvas id="divergingChart" height="60"></canvas>
    </div>

    <div class="terminal">
        <div class="term-nav">
            <button class="term-btn active" onclick="show('missing', event)">missing_targets.txt</button>
            <button class="term-btn" onclick="show('noimg', event)">non_image_links.txt</button>
            <button class="term-btn" onclick="show('present', event)">present_links.txt</button>
            <button class="term-btn" onclick="show('targets', event)">targets.yaml</button>
        </div>
        <div id="term-body"></div>
    </div>

    <script>
        const ctx = document.getElementById('divergingChart').getContext('2d');
        new Chart(ctx, {{
            type: 'bar',
            data: {{
                labels: ['System State'],
                datasets: [
                    {{ label: 'Missing', data: [-{c_missing}], backgroundColor: '#495057' }},
                    {{ label: 'No Content', data: [-{c_no_image}], backgroundColor: '#212529' }},
                    {{ label: 'Successful', data: [{c_present}], backgroundColor: '#adb5bd' }}
                ]
            }},
            options: {{
                indexAxis: 'y',
                maintainAspectRatio: true,
                plugins: {{ 
                    legend: {{ display: true, labels: {{ color: '#888888', font: {{ family: 'Orbitron', size: 9 }} }} }},
                    tooltip: {{ callbacks: {{ label: (c) => Math.abs(c.raw) }} }}
                }},
                scales: {{
                    x: {{ stacked: true, grid: {{ color: '#111111' }}, ticks: {{ callback: v => Math.abs(v), color: '#444444' }} }},
                    y: {{ stacked: true, display: false }}
                }}
            }}
        }});

        const data = {json.dumps(files_data)};
        function show(k, e) {{
            document.getElementById('term-body').innerText = data[k];
            document.querySelectorAll('.term-btn').forEach(b => b.classList.remove('active'));
            if(e) e.target.classList.add('active');
        }}
        window.onload = () => show('missing');
    </script>
</body>
</html>
"""
    output_html.write_text(html_template)
    print(f"[*] Monochrome Reconciliation Complete.")
    print(f"[*] Dashboard: {output_html}")

if __name__ == "__main__":
    main()
