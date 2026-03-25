import os
import re
import json
from pathlib import Path

# --- CONFIGURATION ---
SCRAPED_DATA_DIR = "./scraped_data"
FORCEGRAPH_FILE = "./scraped_data/forcegraph_nodes_only.html"
ECHART_FILE = "./scraped_data/echarts_visualization.html"
CRAWLER_GRAPH_JSON = "./scraped_data/crawler_graph.json"

def get_real_data():
    nodes = []
    links = []
    visited_onions = set()
    base_path = Path(SCRAPED_DATA_DIR)
    if not base_path.exists(): return {"nodes": [], "links": []}

    for item in base_path.iterdir():
        if item.is_dir() and (len(item.name) == 16 or len(item.name) == 56):
            addr = item.name
            visited_onions.add(addr)
            title = addr 
            title_file = item / "website_identity" / "index_title.txt"
            if title_file.exists():
                try:
                    content = title_file.read_text(encoding='utf-8').strip()
                    title_match = re.search(r'\[(.*?)\]', content)
                    if title_match: title = title_match.group(1).strip()
                except: pass
            img_rel_path = f"{addr}/images/index.png"
            img_full_path = item / "images" / "index.png"
            img_val = img_rel_path if img_full_path.exists() else ""
            nodes.append({"id": addr, "name": title, "img": img_val, "val": 20})

    if os.path.exists(CRAWLER_GRAPH_JSON):
        try:
            with open(CRAWLER_GRAPH_JSON, 'r', encoding='utf-8') as f:
                crawl_data = json.load(f)
                for source, targets in crawl_data.items():
                    src_addr = source.replace(".onion", "").strip("/")
                    if src_addr in visited_onions:
                        for target in targets:
                            tar_addr = target.replace(".onion", "").strip("/")
                            if tar_addr in visited_onions:
                                links.append({"source": src_addr, "target": tar_addr})
        except: pass
    return {"nodes": nodes, "links": links}

def update_forcegraph(real_data):
    if not os.path.exists(FORCEGRAPH_FILE): return
    content = open(FORCEGRAPH_FILE, 'r', encoding='utf-8').read()
    json_str = json.dumps(real_data)
    # Direct search and replace to avoid regex backslash issues
    pattern = re.compile(r"const gData\s*=\s*.*?;", re.DOTALL)
    content = pattern.sub(lambda _: f"const gData = {json_str};", content)
    content = re.sub(r"<p>\d+\s+sites discovered.*?</p>", f"<p>{len(real_data['nodes'])} sites discovered — REAL DATA</p>", content)
    with open(FORCEGRAPH_FILE, 'w', encoding='utf-8') as f: f.write(content)
    print(f"[SUCCESS] Updated ForceGraph: {FORCEGRAPH_FILE}")

def update_echarts(real_data):
    if not os.path.exists(ECHART_FILE): return
    content = open(ECHART_FILE, 'r', encoding='utf-8').read()
    echart_nodes = []
    for n in real_data['nodes']:
        node_obj = {"id": n['id'], "name": n['name'], "symbolSize": 30 if n['img'] else 15, "itemStyle": {"color": "#5470c6"}}
        if n['img']:
            node_obj["symbol"] = f"image://{n['img']}"
            node_obj["value"] = n['img']
        echart_nodes.append(node_obj)
    
    nodes_json = json.dumps(echart_nodes)
    links_json = json.dumps(real_data['links'])
    
    pattern_nodes = re.compile(r"const nodes\s*=\s*\[.*?\];", re.DOTALL)
    content = pattern_nodes.sub(lambda _: f"const nodes = {nodes_json};", content)
    pattern_links = re.compile(r"const links\s*=\s*\[.*?\];", re.DOTALL)
    content = pattern_links.sub(lambda _: f"const links = {links_json};", content)
    
    content = re.sub(r"<p.*?>\d+\s+nodes, \d+\s+links</p>", f'<p style="opacity:0.6; font-size:12px;">{len(echart_nodes)} nodes, {len(real_data["links"])} links — REAL DATA</p>', content)
    with open(ECHART_FILE, 'w', encoding='utf-8') as f: f.write(content)
    print(f"[SUCCESS] Updated ECharts: {ECHART_FILE}")

if __name__ == "__main__":
    real_data = get_real_data()
    update_forcegraph(real_data)
    update_echarts(real_data)
