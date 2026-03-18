#!/usr/bin/env python3
"""
Main entry point for running visualization on crawler data.
"""
import os
import sys
import json
import logging
from pathlib import Path

# Add parent directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

# Ensure we're using the correct Python environment
venv_lib = "/home/kappa/aifiles/tor_scraper1/venv/lib/python3.12/site-packages"
if venv_lib not in sys.path:
    sys.path.insert(0, venv_lib)

from visualization import Visualization


def setup_logging(output_dir):
    """Setup logging configuration."""
    log_file = output_dir / "visualization.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)


def main():
    """Main entry point."""
    # Paths
    script_dir = Path(__file__).parent
    scraped_data_dir = script_dir.parent / "scraped_data"
    json_file = scraped_data_dir / "crawler_graph.json"
    output_dir = scraped_data_dir / "visualizations"
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if JSON file exists
    if not json_file.exists():
        print(f"[ERROR] JSON file not found: {json_file}")
        print("[INFO] Please run build_crawler_graph.py first to generate the graph data.")
        sys.exit(1)
    
    # Setup logging
    logger = setup_logging(output_dir)
    logger.info(f"Loading graph data from: {json_file}")
    
    # Load and verify JSON data
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not data:
        logger.error("Empty graph data. Nothing to visualize.")
        sys.exit(1)
    
    logger.info(f"Graph loaded: {len(data)} nodes")
    
    # Create visualization
    viz = Visualization(json_file, str(output_dir), logger)
    viz_dir = output_dir / "figures"
    viz_dir.mkdir(parents=True, exist_ok=True)
    
    # Run all visualizations
    print("\n[INFO] Generating visualizations...")
    
    try:
        import matplotlib.pyplot as plt
        
        # 1. Basic visualization
        logger.info("Generating: Basic visualization")
        viz.visualize()
        plt.savefig(viz_dir / "graph_visualization.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        # 2. Indegree plot
        logger.info("Generating: Indegree plot")
        viz.indegree_plot()
        plt.savefig(viz_dir / "indegree_plot.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        # 3. Indegree bar
        logger.info("Generating: Indegree bar")
        viz.indegree_bar()
        plt.savefig(viz_dir / "indegree_bar.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        # 4. Outdegree plot
        logger.info("Generating: Outdegree plot")
        viz.outdegree_plot()
        plt.savefig(viz_dir / "outdegree_plot.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        # 5. Outdegree bar
        logger.info("Generating: Outdegree bar")
        viz.outdegree_bar()
        plt.savefig(viz_dir / "outdegree_bar.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        # 6. Eigenvector centrality bar
        logger.info("Generating: Eigenvector centrality bar")
        viz.eigenvector_centrality_bar()
        plt.savefig(viz_dir / "eigenvector_centrality.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        # 7. PageRank bar
        logger.info("Generating: PageRank bar")
        viz.pagerank_bar()
        plt.savefig(viz_dir / "pagerank.png", dpi=150, bbox_inches='tight')
        plt.close()
        
        print("\n[OK] All visualizations generated successfully!")
        print(f"[INFO] Output directory: {viz_dir}")
        
    except Exception as e:
        logger.error(f"Error generating visualizations: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
