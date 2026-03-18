#!/usr/bin/env python3
"""
Visualization module for network analysis.
Provides various plotting methods for network metrics.
"""

import os
import json
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

class Visualization:
    """Network visualization and analysis class."""
    
    def __init__(self, json_file, output_dir, logger=None):
        self.json_file = Path(json_file)
        self.output_dir = Path(output_dir)
        self.logger = logger
        self.G = self._load_graph()
        
    def _load_graph(self):
        """Load graph from JSON adjacency list."""
        if self.logger:
            self.logger.info(f"Loading graph from {self.json_file}")
            
        with open(self.json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        G = nx.DiGraph()
        for source, targets in data.items():
            G.add_node(source)
            for target in targets:
                G.add_edge(source, target)
        return G

    def visualize(self):
        """Basic graph visualization."""
        plt.figure(figsize=(12, 12))
        pos = nx.spring_layout(self.G, k=0.15, iterations=20)
        nx.draw_networkx_nodes(self.G, pos, node_size=50, node_color='blue', alpha=0.6)
        nx.draw_networkx_edges(self.G, pos, width=0.5, alpha=0.3, arrows=True)
        plt.title(f"Network Visualization ({self.G.number_of_nodes()} nodes)")
        plt.axis('off')

    def indegree_plot(self):
        """Plot in-degree distribution."""
        indegrees = [d for n, d in self.G.in_degree()]
        plt.figure(figsize=(10, 6))
        plt.hist(indegrees, bins=20, color='green', alpha=0.7)
        plt.title("In-degree Distribution")
        plt.xlabel("In-degree")
        plt.ylabel("Frequency")
        plt.grid(True, alpha=0.3)

    def indegree_bar(self):
        """Bar chart of top nodes by in-degree."""
        top_nodes = sorted(self.G.in_degree(), key=lambda x: x[1], reverse=True)[:15]
        nodes, degrees = zip(*top_nodes) if top_nodes else ([], [])
        plt.figure(figsize=(12, 6))
        plt.bar([n[:16] for n in nodes], degrees, color='green', alpha=0.7)
        plt.title("Top 15 Nodes by In-degree")
        plt.xticks(rotation=45, ha='right')
        plt.ylabel("In-degree")
        plt.tight_layout()

    def outdegree_plot(self):
        """Plot out-degree distribution."""
        outdegrees = [d for n, d in self.G.out_degree()]
        plt.figure(figsize=(10, 6))
        plt.hist(outdegrees, bins=20, color='orange', alpha=0.7)
        plt.title("Out-degree Distribution")
        plt.xlabel("Out-degree")
        plt.ylabel("Frequency")
        plt.grid(True, alpha=0.3)

    def outdegree_bar(self):
        """Bar chart of top nodes by out-degree."""
        top_nodes = sorted(self.G.out_degree(), key=lambda x: x[1], reverse=True)[:15]
        nodes, degrees = zip(*top_nodes) if top_nodes else ([], [])
        plt.figure(figsize=(12, 6))
        plt.bar([n[:16] for n in nodes], degrees, color='orange', alpha=0.7)
        plt.title("Top 15 Nodes by Out-degree")
        plt.xticks(rotation=45, ha='right')
        plt.ylabel("Out-degree")
        plt.tight_layout()

    def eigenvector_centrality_bar(self):
        """Bar chart of top nodes by eigenvector centrality."""
        try:
            centrality = nx.eigenvector_centrality_numpy(self.G)
            top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:15]
            nodes, values = zip(*top_nodes) if top_nodes else ([], [])
            plt.figure(figsize=(12, 6))
            plt.bar([n[:16] for n in nodes], values, color='purple', alpha=0.7)
            plt.title("Top 15 Nodes by Eigenvector Centrality")
            plt.xticks(rotation=45, ha='right')
            plt.ylabel("Centrality")
            plt.tight_layout()
        except Exception as e:
            if self.logger:
                self.logger.error(f"Eigenvector centrality failed: {e}")

    def pagerank_bar(self):
        """Bar chart of top nodes by PageRank."""
        try:
            pagerank = nx.pagerank(self.G, alpha=0.85)
            top_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[:15]
            nodes, values = zip(*top_nodes) if top_nodes else ([], [])
            plt.figure(figsize=(12, 6))
            plt.bar([n[:16] for n in nodes], values, color='red', alpha=0.7)
            plt.title("Top 15 Nodes by PageRank")
            plt.xticks(rotation=45, ha='right')
            plt.ylabel("PageRank Value")
            plt.tight_layout()
        except Exception as e:
            if self.logger:
                self.logger.error(f"PageRank failed: {e}")
