# Visualization Scripts

This directory contains high-performance visualization scripts for analyzing scraped onion site data.

## Overview

These scripts generate interactive HTML visualizations using various JavaScript libraries (ECharts, Cytoscape, Sigma.js, Force-Graph, Cosmograph) to visualize:
- t-SNE embeddings of site content
- Network graphs of onion site relationships
- Global onion network topology

## Quick Start

```cmd
# Run from project root
cd c:\scraper1

# Generate a visualization
python misc_python_scripts\diagramatic exploratory analysis\echarts_tsne_embeddings.py
```

Output files are saved to `scraped_data/` directory.

## Available Visualizations

| Script | Library | Description |
|--------|---------|-------------|
| `echarts_tsne_embeddings.py` | ECharts | Scatter plot of t-SNE embeddings with search |
| `echarts_global_visualization.py` | ECharts | Global network visualization |
| `echarts_nodes_only.py` | ECharts | Nodes-only network view |
| `cytoscapejs_global_visualization.py` | Cytoscape.js | Interactive network graph |
| `forcegraph_global_visualization.py` | Force-Graph | WebGL-powered graph |
| `cosmograph_global_visualization.py` | Cosmograph | High-performance graph rendering |
| `advanced_sigma_analysis.py` | Sigma.js + Graphology | Advanced network analysis with WebGL |
| `circular_network.py` | D3.js | Circular network layout |
| `grand_visualization1.py` | Multiple | Combined visualization |

## Offline Mode

All scripts work **offline** without internet. Libraries are pre-downloaded to:
- Project root: `*.min.js` files

When running scripts, ensure `.min.js` files are in the project root directory.

## Requirements

```txt
numpy
scikit-learn
sentence-transformers
```

Install with:
```cmd
pip install -r misc_python_scripts/requirements.txt
```

## Input Data

Scripts expect scraped data in `scraped_data/` with structure:
```
scraped_data/
└── <onion_address>/
    └── website_identity/
        └── index_title.txt
```

## Output

HTML files are generated in `scraped_data/`:
- `echarts_tsne_embeddings.html`
- `global_visualization.html`
- etc.

Open in any modern browser to view.
