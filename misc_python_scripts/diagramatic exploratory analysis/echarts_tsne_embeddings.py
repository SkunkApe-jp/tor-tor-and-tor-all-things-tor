#!/usr/bin/env python3
"""
ECharts t-SNE Embeddings Visualization
Creates a scatter plot of node embeddings using t-SNE dimensionality reduction.
Uses ECharts for high-performance rendering.
"""

import os
import json
import re
import numpy as np
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from sentence_transformers import SentenceTransformer
from pathlib import Path
import argparse


def extract_text_from_website_title(title_file_path):
    """Extract title text from website_identity/index_title.txt."""
    try:
        with open(title_file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        titles = []
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('[') and ']' in line:
                end_idx = line.find(']')
                title = line[1:end_idx].strip()
                if title:
                    titles.append(title)
        return ' '.join(titles)
    except Exception as e:
        print(f"Error reading {title_file_path}: {str(e)}")
        return ""


def extract_text_embeddings(texts, model_name='all-MiniLM-L6-v2', llama_server_url=None):
    """Extract embeddings from texts using either sentence transformer or llama-server."""
    if llama_server_url:
        import requests
        embeddings = []
        print(f"Using llama-server at: {llama_server_url}")
        print(f"Extracting embeddings from {len(texts)} texts via API...")
        for i, text in enumerate(texts):
            try:
                response = requests.post(
                    f"{llama_server_url}/embedding",
                    json={"content": text},
                    timeout=60
                )
                result = response.json()
                if isinstance(result, list) and len(result) > 0:
                    emb_data = result[0].get('embedding', [])
                    if isinstance(emb_data, list) and len(emb_data) > 0 and isinstance(emb_data[0], list):
                        embedding = emb_data[0]
                    else:
                        embedding = emb_data
                elif isinstance(result, dict):
                    embedding = result.get('embedding', [])
                else:
                    embedding = []
                embeddings.append(embedding)
                if (i + 1) % 10 == 0:
                    print(f"Processed {i + 1}/{len(texts)} texts")
            except Exception as e:
                print(f"Error processing text: {str(e)}")
                embeddings.append([0.0] * 768)
                continue
        return np.array(embeddings)
    else:
        print(f"Loading sentence transformer model: {model_name}")
        model = SentenceTransformer(model_name)
        embeddings = []
        print(f"Extracting embeddings from {len(texts)} texts...")
        for i, text in enumerate(texts):
            try:
                embedding = model.encode([text])[0]
                embeddings.append(embedding)
                if (i + 1) % 10 == 0:
                    print(f"Processed {i + 1}/{len(texts)} texts")
            except Exception as e:
                print(f"Error processing text: {str(e)}")
                embeddings.append(np.zeros(model.get_sentence_embedding_dimension()))
                continue
        return np.array(embeddings)


def find_all_website_title_files(scraped_data_dir):
    """Find all website_identity/index_title.txt files."""
    title_paths = []
    for root, dirs, files in os.walk(scraped_data_dir):
        if 'website_identity' in root and 'index_title.txt' in files:
            title_paths.append(os.path.join(root, 'index_title.txt'))
    return title_paths


def apply_tsne(features, perplexity=30, n_iterations=1000):
    """Apply t-SNE to reduce features to 2D coordinates."""
    print(f"Applying t-SNE with {features.shape[0]} samples...")
    adjusted_perplexity = min(perplexity, features.shape[0] - 1)
    if adjusted_perplexity != perplexity:
        print(f"Adjusted perplexity from {perplexity} to {adjusted_perplexity}")
    if features.shape[1] > 50:
        print("Using PCA to reduce dimensions before t-SNE...")
        pca = PCA(n_components=min(50, features.shape[0], features.shape[1]))
        features = pca.fit_transform(features)
    tsne = TSNE(n_components=2, perplexity=adjusted_perplexity, max_iter=n_iterations, random_state=42, verbose=1)
    tsne_coords = tsne.fit_transform(features)
    return tsne_coords


def generate_echarts_viz(tsne_coords, site_data, output_file):
    """Generate ECharts visualization with search functionality."""
    nodes = []
    for i, (onion_addr, info) in enumerate(site_data.items()):
        img_path_rel = f"{onion_addr}/images/index.png"
        title = info.get('title', onion_addr)
        text = info.get('text', '')
        node_entry = {
            "id": onion_addr,
            "name": title,
            "value": [float(tsne_coords[i][0]), float(tsne_coords[i][1])],
            "symbolSize": 20,
            "itemStyle": {"color": "#6677cc"},
            "text_preview": text[:200] + "..." if len(text) > 200 else text,
            "image": img_path_rel
        }
        nodes.append(node_entry)

    nodes_json = json.dumps(nodes)
    
    html_content = """<!DOCTYPE html>
<html>
<head>
    <title>ECharts t-SNE Embeddings</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        body, #main { width: 100vw; height: 100vh; margin: 0; background: #100c2a; overflow: hidden; }
        #ui { position: absolute; top: 20px; left: 20px; z-index: 10; color: #fff; pointer-events: none; }
        #searchContainer { position: absolute; top: 20px; right: 20px; z-index: 20; display: flex; gap: 8px; }
        #searchBox { padding: 10px 16px; border-radius: 6px; border: 1px solid #30363d; background: rgba(22, 27, 34, 0.9); color: #fff; font-size: 14px; width: 250px; outline: none; }
        #searchBox:focus { border-color: #58a6ff; }
        #searchBox::placeholder { color: #8b949e; }
        #clearSearch { padding: 8px 12px; border-radius: 6px; border: 1px solid #30363d; background: rgba(22, 27, 34, 0.9); color: #fff; cursor: pointer; font-size: 14px; }
        #clearSearch:hover { background: rgba(48, 54, 61, 0.9); }
        .tooltip-card { padding: 10px; min-width: 250px; }
        .tooltip-text { font-size: 11px; opacity: 0.8; margin-top: 5px; max-height: 60px; overflow: hidden; }
    </style>
</head>
<body>
    <div id="ui">
        <h2 style="margin:0; font-family:sans-serif; color:#7ce7ffd6;">ECharts t-SNE Embeddings</h2>
        <p style="opacity:0.6; font-size:12px;">""" + str(len(nodes)) + """ nodes clustered by semantic similarity</p>
    </div>
    <div id="searchContainer">
        <input type="text" id="searchBox" placeholder="🔍 Search by title or onion address...">
        <button id="clearSearch">✕ Clear</button>
    </div>
    <div id="main"></div>
    <script>
        const chart = echarts.init(document.getElementById('main'), 'dark');
        const nodes = """ + nodes_json + """;

        const option = {
            backgroundColor: '#2322bb',
            tooltip: {
                trigger: 'item',
                formatter: function(params) {
                    if (params.data) {
                        let res = '<div class="tooltip-card">';
                        res += '<span style="color:#58a6ff; font-weight:bold;">' + params.name + '</span><br/>';
                        res += '<span style="font-size:11px; opacity:0.7;">' + params.data.id + '.onion</span>';
                        if (params.data.image) {
                            res += '<img class="tooltip-img" src="' + params.data.image + '" onerror="this.style.display=none">';
                        }
                        if (params.data.text_preview) {
                            res += '<div class="tooltip-text">' + params.data.text_preview + '</div>';
                        }
                        res += '</div>';
                        return res;
                    }
                    return params.name;
                },
                backgroundColor: 'rgba(13, 17, 23, 0.9)',
                borderColor: '#30363d',
                textStyle: { color: '#fff' }
            },
            xAxis: { show: false, type: 'value', scale: true },
            yAxis: { show: false, type: 'value', scale: true },
            series: [{
                type: 'scatter',
                symbolSize: 15,
                data: nodes.map(n => ({
                    name: n.name,
                    value: n.value,
                    id: n.id,
                    text_preview: n.text_preview,
                    image: n.image,
                    symbolSize: n.symbolSize,
                    itemStyle: n.itemStyle
                })),
                roam: true,
                emphasis: {
                    focus: 'self',
                    itemStyle: { borderColor: '#fff', borderWidth: 2 }
                }
            }],
            dataZoom: [
                { type: 'inside', xAxisIndex: 0, filterMode: 'none' },
                { type: 'inside', yAxisIndex: 0, filterMode: 'none' }
            ]
        };

        chart.setOption(option);
        
        // Search functionality - preserves zoom state
        const searchBox = document.getElementById('searchBox');
        const clearSearch = document.getElementById('clearSearch');
        
        function performSearch() {
            const query = searchBox.value.toLowerCase().trim();
            
            if (!query) {
                chart.setOption({
                    series: [{
                        data: nodes.map(n => ({
                            name: n.name,
                            value: n.value,
                            id: n.id,
                            text_preview: n.text_preview,
                            symbolSize: n.symbolSize,
                            itemStyle: n.itemStyle
                        }))
                    }]
                }, { notMerge: false });
                return;
            }
            
            const filteredData = nodes.map(n => {
                const matchesTitle = n.name && n.name.toLowerCase().includes(query);
                const matchesId = n.id && n.id.toLowerCase().includes(query);
                const matchesText = n.text_preview && n.text_preview.toLowerCase().includes(query);
                
                if (matchesTitle || matchesId || matchesText) {
                    return {
                        name: n.name,
                        value: n.value,
                        id: n.id,
                        text_preview: n.text_preview,
                        symbolSize: 25,
                        itemStyle: { color: '#d5ff16', borderColor: '#fff', borderWidth: 2 }
                    };
                } else {
                    return {
                        name: n.name,
                        value: n.value,
                        id: n.id,
                        text_preview: n.text_preview,
                        symbolSize: 8,
                        itemStyle: { opacity: 0.3 }
                    };
                }
            });
            
            chart.setOption({
                series: [{ data: filteredData }]
            }, { notMerge: false });
        }
        
        searchBox.addEventListener('input', performSearch);
        clearSearch.addEventListener('click', () => {
            searchBox.value = '';
            performSearch();
            searchBox.focus();
        });
        
        window.addEventListener('resize', () => chart.resize());
    </script>
</body>
</html>"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"ECharts t-SNE visualization saved to {output_file}")


def main():
    script_dir = Path(__file__).parent
    scraped_data_dir = script_dir / "../../scraped_data"
    output_file = scraped_data_dir / "echarts_tsne_embeddings.html"
    
    parser = argparse.ArgumentParser(description='ECharts t-SNE Embeddings')
    parser.add_argument('--input-dir', type=str, default=str(scraped_data_dir))
    parser.add_argument('--output', type=str, default=str(output_file))
    parser.add_argument('--llama-server', type=str, default=None)
    parser.add_argument('--model', type=str, default='all-MiniLM-L6-v2')
    args = parser.parse_args()
    
    scraped_data_dir = Path(args.input_dir)
    output_file = Path(args.output)
    scraped_data_dir = str(scraped_data_dir)
    
    if not os.path.exists(scraped_data_dir):
        print(f"Error: {scraped_data_dir} not found")
        return
    
    title_files = find_all_website_title_files(scraped_data_dir)
    print(f"Found {len(title_files)} onion sites with titles")
    
    if len(title_files) == 0:
        print("No website titles found. Exiting.")
        return
    
    texts = []
    site_data = {}
    
    for title_file in title_files:
        parts = title_file.split(os.sep)
        onion_addr = None
        for i, part in enumerate(parts):
            if part == 'website_identity':
                onion_addr = parts[i-1]
                break
        if not onion_addr:
            continue
        text = extract_text_from_website_title(title_file)
        if not text:
            text = onion_addr
        texts.append(text)
        site_data[onion_addr] = {
            'title': text[:50] + "..." if len(text) > 50 else text,
            'text': text
        }
    
    print(f"Processing {len(texts)} texts...")
    embeddings = extract_text_embeddings(texts, model_name=args.model, llama_server_url=args.llama_server)
    tsne_coords = apply_tsne(embeddings)
    generate_echarts_viz(tsne_coords, site_data, str(output_file))


if __name__ == "__main__":
    main()
