#!/usr/bin/env python3
"""
Master Network Analysis Suite - The "Big Daddy"

Comprehensive visualization and analysis tool for onion networks.
Combines all 20+ visualization techniques into one unified system.
"""

import os
import json
import re
import urllib.parse
from pathlib import Path
import matplotlib.pyplot as plt
import networkx as nx
import seaborn as sns
import numpy as np
import pandas as pd
from collections import Counter, defaultdict
import time
import sys

# Import all our specialized modules
from community_heatmap import generate_community_heatmap
from anomaly_detection import detect_anomalies
from advanced_visualizations import generate_all_advanced_visualizations


class MasterNetworkAnalyzer:
    """Comprehensive network analysis suite."""

    def __init__(self, scraped_data_dir):
        self.scraped_data_dir = scraped_data_dir
        self.G = None
        self.communities = None
        self.onion_sites = []
        self.analysis_results = {}

    def read_links_file(self, links_file_path):
        """Read links from the scraped links file."""
        links = []
        if os.path.exists(links_file_path):
            with open(links_file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and ".onion" in line:
                        links.append(line)
        return links

    def extract_onion_addresses_from_file(self, file_path):
        """Extract all unique onion addresses from a links file."""
        onion_addresses = set()
        if os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                url_matches = re.findall(r"https?://[^\s\'\"<>]+", content)
                for match in url_matches:
                    try:
                        parsed = urllib.parse.urlparse(match)
                        if (
                            parsed.scheme
                            and parsed.netloc
                            and ".onion" in parsed.netloc
                        ):
                            onion_match = re.search(r"([a-z2-7]{54,}\.onion)", match)
                            if onion_match:
                                onion_addresses.add(onion_match.group(1))
                    except:
                        continue
        return list(onion_addresses)

    def get_onion_sites(self, scraped_data_dir):
        """Get all onion sites from the directory structure."""
        onion_dirs = []
        for item in os.listdir(scraped_data_dir):
            item_path = os.path.join(scraped_data_dir, item)
            if os.path.isdir(item_path) and len(item) >= 50:
                if re.match(r"^[a-z2-7]{50,}$", item):
                    onion_dirs.append(item)
        return onion_dirs

    def extract_title_from_html(self, html_file_path):
        """Extract title from HTML file."""
        if os.path.exists(html_file_path):
            try:
                with open(html_file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    title_match = re.search(
                        r"<title[^>]*>(.*?)</title>", content, re.IGNORECASE | re.DOTALL
                    )
                    if title_match:
                        title = title_match.group(1).strip()
                        title = " ".join(title.split())
                        return title
            except Exception as e:
                print(f"Error reading {html_file_path}: {str(e)}")
        return None

    def find_screenshot_path(self, full_url):
        """Find the appropriate screenshot for a URL."""
        parsed = urllib.parse.urlparse(full_url)
        onion_match = re.search(r"([a-z2-7]{54,})\.onion", full_url)

        if not onion_match:
            return "", None

        onion_address = onion_match.group(1)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        image_dir = os.path.join(self.scraped_data_dir, onion_address, "images")

        for part in path_parts[:-1]:
            image_dir = os.path.join(image_dir, part)

        if path_parts:
            last_part = path_parts[-1]
            if "." in last_part:
                clean_last_part = last_part.replace(".", "_")
                expected_filename = f"{clean_last_part}.png"
            else:
                expected_filename = f"{last_part}.png"

            expected_path = os.path.join(image_dir, expected_filename)
            if os.path.exists(expected_path):
                rel_path = os.path.relpath(expected_path, self.scraped_data_dir)
                return rel_path.replace("\\", "/"), self.get_image_dimensions(
                    expected_path
                )
        else:
            index_path = os.path.join(image_dir, "index.png")
            if os.path.exists(index_path):
                rel_path = os.path.relpath(index_path, self.scraped_data_dir)
                return rel_path.replace("\\", "/"), self.get_image_dimensions(
                    index_path
                )

            onion_path = os.path.join(image_dir, f"{onion_address}.png")
            if os.path.exists(onion_path):
                rel_path = os.path.relpath(onion_path, self.scraped_data_dir)
                return rel_path.replace("\\", "/"), self.get_image_dimensions(
                    onion_path
                )

        return "", None

    def get_image_dimensions(self, image_path):
        """Get the dimensions of an image file."""
        if os.path.exists(image_path):
            try:
                from PIL import Image

                with Image.open(image_path) as img:
                    return img.size
            except Exception:
                pass
        return None

    def build_network(self):
        """Build the main network graph."""
        print("=== BUILDING NETWORK ===")
        start_time = time.time()

        self.onion_sites = self.get_onion_sites(self.scraped_data_dir)
        print(f"Found {len(self.onion_sites)} onion sites")

        print("Building Graph...")
        self.G = nx.Graph()

        for onion_addr in self.onion_sites:
            site_dir = os.path.join(self.scraped_data_dir, onion_addr)
            urls_dir = os.path.join(site_dir, "urls")
            htmls_dir = os.path.join(site_dir, "htmls")

            root_url = f"http://{onion_addr}.onion"
            root_html_file = os.path.join(htmls_dir, f"{onion_addr}.html")
            root_title = self.extract_title_from_html(root_html_file)
            if not root_title:
                root_title = root_url

            outbound_links = []

            if os.path.exists(urls_dir):
                for file_name in os.listdir(urls_dir):
                    if file_name.endswith("_links.txt"):
                        links_file_path = os.path.join(urls_dir, file_name)
                        file_links = self.read_links_file(links_file_path)
                        outbound_links.extend(file_links)

            discovered_links_dir = os.path.join(site_dir, "discovered_links")
            if os.path.exists(discovered_links_dir):
                for file_name in os.listdir(discovered_links_dir):
                    if file_name.endswith("_links.txt"):
                        links_file_path = os.path.join(discovered_links_dir, file_name)
                        file_links = self.read_links_file(links_file_path)
                        outbound_links.extend(file_links)

            root_image_path, root_image_dims = self.find_screenshot_path(root_url)
            self.G.add_node(root_url, title=root_title, image=root_image_path, group=1)

            for link in outbound_links:
                onion_match = re.search(r"([a-z2-7]{54,})\.onion", link)
                if onion_match:
                    linked_onion = onion_match.group(1)
                    link_html_file = os.path.join(
                        self.scraped_data_dir,
                        linked_onion,
                        "htmls",
                        f"{linked_onion}.html",
                    )
                    link_title = self.extract_title_from_html(link_html_file)
                    if not link_title:
                        link_title = link

                    image_path, image_dims = self.find_screenshot_path(link)
                    self.G.add_node(link, title=link_title, image=image_path, group=2)
                    self.G.add_edge(root_url, link)

        elapsed = time.time() - start_time
        print(f"Network built in {elapsed:.2f} seconds")
        print(
            f"Graph: {self.G.number_of_nodes()} nodes, {self.G.number_of_edges()} edges"
        )

    def detect_communities(self):
        """Detect communities with progress tracking."""
        print("\n=== DETECTING COMMUNITIES ===")

        node_count = self.G.number_of_nodes()
        edge_count = self.G.number_of_edges()
        print(f"Graph size: {node_count} nodes, {edge_count} edges")

        start_time = time.time()

        if node_count > 5000:
            print("Large graph detected - using Label Propagation algorithm")
            from networkx.algorithms import community

            self.communities = list(community.label_propagation_communities(self.G))
        elif node_count > 1000:
            print("Medium graph detected - using Louvain algorithm")
            from networkx.algorithms import community

            self.communities = list(community.louvain_communities(self.G, seed=42))
        else:
            print("Small graph detected - using Greedy Modularity algorithm")
            from networkx.algorithms import community

            self.communities = list(community.greedy_modularity_communities(self.G))

        elapsed = time.time() - start_time
        print(
            f"Community detection completed in {elapsed:.2f} seconds, found {len(self.communities)} communities"
        )

        # Create community mapping
        community_map = {}
        for i, comm in enumerate(self.communities):
            for node in comm:
                community_map[node] = i

        for node in self.G.nodes():
            self.G.nodes[node]["community"] = community_map.get(node, -1)

    def calculate_network_metrics(self):
        """Calculate comprehensive network metrics."""
        print("\n=== CALCULATING NETWORK METRICS ===")

        metrics = {}

        # Basic metrics
        metrics["nodes"] = self.G.number_of_nodes()
        metrics["edges"] = self.G.number_of_edges()
        metrics["density"] = nx.density(self.G)
        metrics["communities"] = len(self.communities)

        # Centrality measures
        print("Calculating centrality measures...")
        metrics["degree_centrality"] = nx.degree_centrality(self.G)
        metrics["betweenness_centrality"] = nx.betweenness_centrality(self.G)
        metrics["closeness_centrality"] = nx.closeness_centrality(self.G)
        undirected = self.G.to_undirected()
        if nx.is_connected(undirected):
            metrics["eigenvector_centrality"] = nx.eigenvector_centrality(
                self.G, max_iter=1000
            )
        else:
            largest_cc = max(nx.connected_components(undirected), key=len)
            subgraph = self.G.subgraph(largest_cc).copy()
            metrics["eigenvector_centrality"] = nx.eigenvector_centrality(
                subgraph, max_iter=1000
            )
        metrics["pagerank"] = nx.pagerank(self.G, alpha=0.85)

        # Clustering
        print("Calculating clustering coefficients...")
        metrics["clustering"] = nx.clustering(self.G)
        metrics["avg_clustering"] = nx.average_clustering(self.G)

        # Connectivity
        print("Analyzing connectivity...")
        metrics["is_connected"] = nx.is_connected(self.G)
        if metrics["is_connected"]:
            metrics["diameter"] = nx.diameter(self.G)
            metrics["avg_shortest_path"] = nx.average_shortest_path_length(self.G)
        else:
            metrics["components"] = nx.number_connected_components(self.G)
            largest_cc = max(nx.connected_components(self.G), key=len)
            metrics["largest_component_size"] = len(largest_cc)

        # Degree distribution
        degrees = [self.G.degree(n) for n in self.G.nodes()]
        metrics["avg_degree"] = np.mean(degrees)
        metrics["degree_std"] = np.std(degrees)
        metrics["max_degree"] = max(degrees)
        metrics["min_degree"] = min(degrees)

        self.analysis_results["metrics"] = metrics
        print(f"Metrics calculated: {len(metrics)} key metrics")

    def generate_all_visualizations(self):
        """Generate all visualization types."""
        print("\n=== GENERATING ALL VISUALIZATIONS ===")

        viz_files = {}

        # 1. Standard Network Visualization
        viz_files["network"] = self.generate_standard_network()

        # 2. Community Heatmap
        viz_files["heatmap"] = generate_community_heatmap(
            self.G, self.communities, self.scraped_data_dir
        )

        # 3. Anomaly Detection
        viz_files["anomalies"] = detect_anomalies(
            self.G, self.communities, self.scraped_data_dir
        )

        # 4. Alternative Layouts
        viz_files["circular"] = self.generate_circular_layout()
        viz_files["hierarchical"] = self.generate_hierarchical_layout()

        # 5. Centrality Visualizations
        viz_files["centrality"] = self.generate_centrality_visualizations()

        # 6. Degree Distribution Analysis
        viz_files["degree_analysis"] = self.generate_degree_analysis()

        # 7. Temporal Analysis (if timestamp data available)
        viz_files["temporal"] = self.generate_temporal_analysis()

        # 8. Subgraph Analysis
        viz_files["subgraphs"] = self.generate_subgraph_analysis()

        # 9. Network Statistics Dashboard
        viz_files["dashboard"] = self.generate_network_dashboard()

        # 10. Export for External Tools
        viz_files["exports"] = self.generate_network_exports()

        # 11. Advanced Visualizations (8 more techniques)
        viz_files["advanced"] = generate_all_advanced_visualizations(
            self.G, self.communities, self.scraped_data_dir
        )

        return viz_files

    def generate_standard_network(self):
        """Generate standard network visualization."""
        print("Generating standard network visualization...")

        # Calculate PageRank for node sizes
        pagerank = self.analysis_results["metrics"]["pagerank"]
        node_sizes = [10 + (pagerank.get(n, 0) * 3000) for n in self.G.nodes()]

        # Community colors
        community_map = {}
        for i, comm in enumerate(self.communities):
            for node in comm:
                community_map[node] = i
        node_colors = [community_map.get(node, -1) for node in self.G.nodes()]

        # Layout
        pos = nx.spring_layout(self.G, k=0.15, iterations=50, seed=42)

        # Draw
        plt.figure(figsize=(40, 40), dpi=100)
        plt.axis("off")

        nx.draw_networkx_edges(self.G, pos, alpha=0.1, edge_color="#999999", width=0.5)
        nx.draw_networkx_nodes(
            self.G,
            pos,
            node_size=node_sizes,
            node_color=node_colors,
            cmap=plt.cm.jet,
            alpha=0.7,
        )

        plt.title(
            f"Grand Onion Network ({self.G.number_of_nodes()} nodes, {len(self.communities)} communities)",
            fontsize=24,
        )

        output_file = os.path.join(self.scraped_data_dir, "master_network_map.png")
        plt.savefig(output_file, bbox_inches="tight", pad_inches=0.5)
        plt.close()

        print(f"Standard network visualization saved to {output_file}")
        return output_file

    def generate_circular_layout(self):
        """Generate circular layout visualization."""
        print("Generating circular layout...")

        # Calculate betweenness for node sizes
        betweenness = self.analysis_results["metrics"]["betweenness_centrality"]
        node_sizes = [50 + (betweenness.get(n, 0) * 5000) for n in self.G.nodes()]

        # Community colors
        community_map = {}
        for i, comm in enumerate(self.communities):
            for node in comm:
                community_map[node] = i
        node_colors = [community_map.get(node, -1) for node in self.G.nodes()]

        # Circular layout
        pos = nx.circular_layout(self.G)

        plt.figure(figsize=(30, 30), dpi=100)
        plt.axis("off")

        nx.draw_networkx_edges(self.G, pos, alpha=0.2, edge_color="#999999", width=1)
        nx.draw_networkx_nodes(
            self.G,
            pos,
            node_size=node_sizes,
            node_color=node_colors,
            cmap=plt.cm.Set3,
            alpha=0.8,
        )

        plt.title(
            f"Circular Network Layout ({self.G.number_of_nodes()} nodes)", fontsize=20
        )

        output_file = os.path.join(self.scraped_data_dir, "circular_network.png")
        plt.savefig(output_file, bbox_inches="tight")
        plt.close()

        print(f"Circular layout saved to {output_file}")
        return output_file

    def generate_hierarchical_layout(self):
        """Generate hierarchical/community-based layout."""
        print("Generating hierarchical layout...")

        # Create community-based positions
        pos = {}
        community_centers = {}

        # Position communities in a grid
        grid_size = int(np.ceil(np.sqrt(len(self.communities))))
        for i, comm in enumerate(self.communities):
            row = i // grid_size
            col = i % grid_size
            community_centers[i] = (col * 2, -row * 2)

        # Position nodes within their communities
        for i, comm in enumerate(self.communities):
            center_x, center_y = community_centers[i]
            subgraph = self.G.subgraph(comm)
            sub_pos = nx.spring_layout(subgraph, center=(center_x, center_y), scale=0.8)
            pos.update(sub_pos)

        # Node sizes by degree
        degrees = dict(self.G.degree())
        node_sizes = [20 + degrees.get(n, 0) * 5 for n in self.G.nodes()]

        # Community colors
        community_map = {}
        for i, comm in enumerate(self.communities):
            for node in comm:
                community_map[node] = i
        node_colors = [community_map.get(node, -1) for node in self.G.nodes()]

        plt.figure(figsize=(30, 30), dpi=100)
        plt.axis("off")

        nx.draw_networkx_edges(self.G, pos, alpha=0.1, edge_color="#999999", width=0.5)
        nx.draw_networkx_nodes(
            self.G,
            pos,
            node_size=node_sizes,
            node_color=node_colors,
            cmap=plt.cm.tab20,
            alpha=0.7,
        )

        plt.title(
            f"Hierarchical Community Layout ({len(self.communities)} communities)",
            fontsize=20,
        )

        output_file = os.path.join(self.scraped_data_dir, "hierarchical_network.png")
        plt.savefig(output_file, bbox_inches="tight")
        plt.close()

        print(f"Hierarchical layout saved to {output_file}")
        return output_file

    def generate_centrality_visualizations(self):
        """Generate centrality comparison visualizations."""
        print("Generating centrality visualizations...")

        fig, axes = plt.subplots(2, 2, figsize=(20, 20))

        # Get centrality measures
        degree_cent = self.analysis_results["metrics"]["degree_centrality"]
        between_cent = self.analysis_results["metrics"]["betweenness_centrality"]
        close_cent = self.analysis_results["metrics"]["closeness_centrality"]
        eigen_cent = self.analysis_results["metrics"]["eigenvector_centrality"]

        # Degree centrality
        degree_values = list(degree_cent.values())
        axes[0, 0].hist(
            degree_values, bins=50, alpha=0.7, color="blue", edgecolor="black"
        )
        axes[0, 0].set_title("Degree Centrality Distribution")
        axes[0, 0].set_xlabel("Degree Centrality")
        axes[0, 0].set_ylabel("Frequency")

        # Betweenness centrality
        between_values = list(between_cent.values())
        axes[0, 1].hist(
            between_values, bins=50, alpha=0.7, color="red", edgecolor="black"
        )
        axes[0, 1].set_title("Betweenness Centrality Distribution")
        axes[0, 1].set_xlabel("Betweenness Centrality")
        axes[0, 1].set_ylabel("Frequency")
        axes[0, 1].set_yscale("log")

        # Closeness centrality
        close_values = list(close_cent.values())
        axes[1, 0].hist(
            close_values, bins=50, alpha=0.7, color="green", edgecolor="black"
        )
        axes[1, 0].set_title("Closeness Centrality Distribution")
        axes[1, 0].set_xlabel("Closeness Centrality")
        axes[1, 0].set_ylabel("Frequency")

        # Eigenvector centrality
        eigen_values = list(eigen_cent.values())
        axes[1, 1].hist(
            eigen_values, bins=50, alpha=0.7, color="purple", edgecolor="black"
        )
        axes[1, 1].set_title("Eigenvector Centrality Distribution")
        axes[1, 1].set_xlabel("Eigenvector Centrality")
        axes[1, 1].set_ylabel("Frequency")

        plt.tight_layout()

        output_file = os.path.join(self.scraped_data_dir, "centrality_analysis.png")
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"Centrality analysis saved to {output_file}")
        return output_file

    def generate_degree_analysis(self):
        """Generate comprehensive degree analysis."""
        print("Generating degree analysis...")

        fig, axes = plt.subplots(2, 2, figsize=(20, 20))

        degrees = [self.G.degree(n) for n in self.G.nodes()]

        # Degree distribution
        axes[0, 0].hist(degrees, bins=50, alpha=0.7, color="orange", edgecolor="black")
        axes[0, 0].set_title("Degree Distribution")
        axes[0, 0].set_xlabel("Degree")
        axes[0, 0].set_ylabel("Frequency")
        axes[0, 0].set_xscale("log")
        axes[0, 0].set_yscale("log")

        # Cumulative degree distribution
        sorted_degrees = sorted(degrees, reverse=True)
        cumulative = np.arange(1, len(sorted_degrees) + 1) / len(sorted_degrees)
        axes[0, 1].plot(sorted_degrees, cumulative, "b-", linewidth=2)
        axes[0, 1].set_title("Cumulative Degree Distribution")
        axes[0, 1].set_xlabel("Degree")
        axes[0, 1].set_ylabel("Cumulative Probability")
        axes[0, 1].set_xscale("log")
        axes[0, 1].set_yscale("log")

        # Degree vs clustering
        clustering = self.analysis_results["metrics"]["clustering"]
        degree_clustering_pairs = [
            (self.G.degree(n), clustering[n]) for n in self.G.nodes()
        ]
        degrees_only, clustering_only = zip(*degree_clustering_pairs)
        axes[1, 0].scatter(degrees_only, clustering_only, alpha=0.5, s=10)
        axes[1, 0].set_title("Degree vs Clustering Coefficient")
        axes[1, 0].set_xlabel("Degree")
        axes[1, 0].set_ylabel("Clustering Coefficient")
        axes[1, 0].set_xscale("log")

        # Top degree nodes
        degree_dict = dict(self.G.degree())
        top_nodes = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)[:10]
        node_names, node_degrees = zip(*top_nodes)
        axes[1, 1].bar(range(len(node_names)), node_degrees)
        axes[1, 1].set_title("Top 10 Nodes by Degree")
        axes[1, 1].set_xlabel("Node Rank")
        axes[1, 1].set_ylabel("Degree")
        axes[1, 1].set_xticks(range(len(node_names)))
        axes[1, 1].set_xticklabels(
            [f"#{i + 1}" for i in range(len(node_names))], rotation=45
        )

        plt.tight_layout()

        output_file = os.path.join(self.scraped_data_dir, "degree_analysis.png")
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"Degree analysis saved to {output_file}")
        return output_file

    def generate_temporal_analysis(self):
        """Generate temporal evolution analysis (placeholder)."""
        print("Generating temporal analysis...")

        fig, axes = plt.subplots(2, 2, figsize=(20, 20))

        # Placeholder temporal visualizations
        axes[0, 0].text(
            0.5,
            0.5,
            "Temporal Analysis\n(Timestamp data not available)",
            ha="center",
            va="center",
            transform=axes[0, 0].transAxes,
            fontsize=16,
        )
        axes[0, 0].set_title("Network Growth Over Time")

        axes[0, 1].text(
            0.5,
            0.5,
            "Community Evolution\n(Historical data needed)",
            ha="center",
            va="center",
            transform=axes[0, 1].transAxes,
            fontsize=16,
        )
        axes[0, 1].set_title("Community Evolution")

        axes[1, 0].text(
            0.5,
            0.5,
            "Node Lifecycle\n(Timestamp data required)",
            ha="center",
            va="center",
            transform=axes[1, 0].transAxes,
            fontsize=16,
        )
        axes[1, 0].set_title("Node Lifecycle Analysis")

        axes[1, 1].text(
            0.5,
            0.5,
            "Connection Patterns\n(Time series data needed)",
            ha="center",
            va="center",
            transform=axes[1, 1].transAxes,
            fontsize=16,
        )
        axes[1, 1].set_title("Temporal Connection Patterns")

        plt.tight_layout()

        output_file = os.path.join(self.scraped_data_dir, "temporal_analysis.png")
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"Temporal analysis saved to {output_file}")
        return output_file

    def generate_subgraph_analysis(self):
        """Generate subgraph/community analysis."""
        print("Generating subgraph analysis...")

        # Analyze top communities
        community_sizes = [(i, len(comm)) for i, comm in enumerate(self.communities)]
        top_communities = sorted(community_sizes, key=lambda x: x[1], reverse=True)[:6]

        fig, axes = plt.subplots(2, 3, figsize=(30, 20))
        axes = axes.flatten()

        for idx, (comm_id, size) in enumerate(top_communities):
            if idx >= 6:
                break

            comm_nodes = list(self.communities[comm_id])
            subgraph = self.G.subgraph(comm_nodes)

            # Layout for subgraph
            pos = nx.spring_layout(subgraph, seed=42)

            # Node sizes by degree within community
            degrees = dict(subgraph.degree())
            node_sizes = [50 + degrees.get(n, 0) * 20 for n in subgraph.nodes()]

            # Draw subgraph
            axes[idx].axis("off")
            nx.draw_networkx_edges(
                subgraph, pos, ax=axes[idx], alpha=0.3, edge_color="gray", width=0.5
            )
            nx.draw_networkx_nodes(
                subgraph,
                pos,
                ax=axes[idx],
                node_size=node_sizes,
                node_color="lightblue",
                alpha=0.8,
            )

            axes[idx].set_title(
                f"Community {comm_id}\n({size} nodes, {subgraph.number_of_edges()} edges)",
                fontsize=12,
            )

        plt.tight_layout()

        output_file = os.path.join(self.scraped_data_dir, "subgraph_analysis.png")
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"Subgraph analysis saved to {output_file}")
        return output_file

    def generate_network_dashboard(self):
        """Generate comprehensive network dashboard."""
        print("Generating network dashboard...")

        fig = plt.figure(figsize=(24, 16))

        # Create grid layout
        gs = fig.add_gridspec(3, 4, hspace=0.3, wspace=0.3)

        # Title
        fig.suptitle(
            "Master Network Analysis Dashboard", fontsize=20, fontweight="bold"
        )

        # Basic metrics
        ax1 = fig.add_subplot(gs[0, 0])
        metrics_data = ["Nodes", "Edges", "Communities", "Density"]
        metrics_values = [
            self.G.number_of_nodes(),
            self.G.number_of_edges(),
            len(self.communities),
            self.analysis_results["metrics"]["density"],
        ]
        colors = ["blue", "green", "red", "orange"]
        bars = ax1.bar(metrics_data, metrics_values, color=colors)
        ax1.set_title("Basic Network Metrics")
        ax1.set_ylabel("Count")
        # Add value labels
        for bar, val in zip(bars, metrics_values):
            height = bar.get_height()
            ax1.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + height * 0.01,
                f"{val:.1f}" if val < 10 else f"{val}",
                ha="center",
                va="bottom",
            )

        # Degree distribution
        ax2 = fig.add_subplot(gs[0, 1])
        degrees = [self.G.degree(n) for n in self.G.nodes()]
        ax2.hist(degrees, bins=30, alpha=0.7, color="purple", edgecolor="black")
        ax2.set_title("Degree Distribution")
        ax2.set_xlabel("Degree")
        ax2.set_ylabel("Frequency")
        ax2.set_yscale("log")

        # Community sizes
        ax3 = fig.add_subplot(gs[0, 2])
        community_sizes = [len(comm) for comm in self.communities]
        ax3.hist(community_sizes, bins=20, alpha=0.7, color="brown", edgecolor="black")
        ax3.set_title("Community Size Distribution")
        ax3.set_xlabel("Community Size")
        ax3.set_ylabel("Number of Communities")

        # Centrality comparison
        ax4 = fig.add_subplot(gs[0, 3])
        centrality_types = ["Degree", "Betweenness", "Closeness", "Eigenvector"]
        centrality_means = [
            np.mean(
                list(self.analysis_results["metrics"]["degree_centrality"].values())
            ),
            np.mean(
                list(
                    self.analysis_results["metrics"]["betweenness_centrality"].values()
                )
            ),
            np.mean(
                list(self.analysis_results["metrics"]["closeness_centrality"].values())
            ),
            np.mean(
                list(
                    self.analysis_results["metrics"]["eigenvector_centrality"].values()
                )
            ),
        ]
        bars = ax4.bar(
            centrality_types, centrality_means, color=["red", "blue", "green", "orange"]
        )
        ax4.set_title("Average Centrality Measures")
        ax4.set_ylabel("Average Value")
        ax4.tick_params(axis="x", rotation=45)

        # Clustering analysis
        ax5 = fig.add_subplot(gs[1, 0])
        clustering_values = list(
            self.analysis_results["metrics"]["clustering"].values()
        )
        ax5.hist(clustering_values, bins=30, alpha=0.7, color="cyan", edgecolor="black")
        ax5.set_title("Clustering Coefficient Distribution")
        ax5.set_xlabel("Clustering Coefficient")
        ax5.set_ylabel("Frequency")

        # Network connectivity
        ax6 = fig.add_subplot(gs[1, 1])
        if self.analysis_results["metrics"]["is_connected"]:
            ax6.text(
                0.5,
                0.7,
                "Network is CONNECTED",
                ha="center",
                va="center",
                transform=ax6.transAxes,
                fontsize=14,
                fontweight="bold",
                color="green",
            )
            ax6.text(
                0.5,
                0.5,
                f"Diameter: {self.analysis_results['metrics']['diameter']}",
                ha="center",
                va="center",
                transform=ax6.transAxes,
                fontsize=12,
            )
            ax6.text(
                0.5,
                0.3,
                f"Avg Path Length: {self.analysis_results['metrics']['avg_shortest_path']:.2f}",
                ha="center",
                va="center",
                transform=ax6.transAxes,
                fontsize=12,
            )
        else:
            ax6.text(
                0.5,
                0.7,
                "Network is DISCONNECTED",
                ha="center",
                va="center",
                transform=ax6.transAxes,
                fontsize=14,
                fontweight="bold",
                color="red",
            )
            ax6.text(
                0.5,
                0.5,
                f"Components: {self.analysis_results['metrics']['components']}",
                ha="center",
                va="center",
                transform=ax6.transAxes,
                fontsize=12,
            )
            ax6.text(
                0.5,
                0.3,
                f"Largest Component: {self.analysis_results['metrics']['largest_component_size']} nodes",
                ha="center",
                va="center",
                transform=ax6.transAxes,
                fontsize=12,
            )
        ax6.set_title("Network Connectivity")
        ax6.axis("off")

        # Top nodes by different metrics
        ax7 = fig.add_subplot(gs[1, 2])
        degree_dict = dict(self.G.degree())
        top_degree_nodes = sorted(
            degree_dict.items(), key=lambda x: x[1], reverse=True
        )[:5]
        node_labels = [f"Node {i + 1}" for i in range(len(top_degree_nodes))]
        node_degrees = [deg for _, deg in top_degree_nodes]
        bars = ax7.bar(node_labels, node_degrees, color="red")
        ax7.set_title("Top 5 Nodes by Degree")
        ax7.set_ylabel("Degree")
        # Add value labels
        for bar, val in zip(bars, node_degrees):
            height = bar.get_height()
            ax7.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + height * 0.01,
                str(val),
                ha="center",
                va="bottom",
            )

        # PageRank distribution
        ax8 = fig.add_subplot(gs[1, 3])
        pagerank_values = list(self.analysis_results["metrics"]["pagerank"].values())
        ax8.hist(
            pagerank_values, bins=30, alpha=0.7, color="magenta", edgecolor="black"
        )
        ax8.set_title("PageRank Distribution")
        ax8.set_xlabel("PageRank")
        ax8.set_ylabel("Frequency")
        ax8.set_yscale("log")

        # Summary statistics table
        ax9 = fig.add_subplot(gs[2, :])
        ax9.axis("off")

        # Create summary text
        summary_text = f"""
        NETWORK SUMMARY STATISTICS
        ===========================
        Total Nodes: {self.G.number_of_nodes():,}
        Total Edges: {self.G.number_of_edges():,}
        Network Density: {self.analysis_results["metrics"]["density"]:.6f}
        Number of Communities: {len(self.communities)}
        Average Degree: {self.analysis_results["metrics"]["avg_degree"]:.2f}
        Degree Std Dev: {self.analysis_results["metrics"]["degree_std"]:.2f}
        Max Degree: {self.analysis_results["metrics"]["max_degree"]}
        Min Degree: {self.analysis_results["metrics"]["min_degree"]}
        Average Clustering: {self.analysis_results["metrics"]["avg_clustering"]:.4f}
        Network Connected: {"Yes" if self.analysis_results["metrics"]["is_connected"] else "No"}
        """

        if self.analysis_results["metrics"]["is_connected"]:
            summary_text += f"""
        Network Diameter: {self.analysis_results["metrics"]["diameter"]}
        Average Path Length: {self.analysis_results["metrics"]["avg_shortest_path"]:.2f}
        """
        else:
            summary_text += f"""
        Number of Components: {self.analysis_results["metrics"]["components"]}
        Largest Component Size: {self.analysis_results["metrics"]["largest_component_size"]:,}
        """

        ax9.text(
            0.05,
            0.95,
            summary_text,
            transform=ax9.transAxes,
            fontsize=12,
            verticalalignment="top",
            fontfamily="monospace",
        )

        output_file = os.path.join(self.scraped_data_dir, "network_dashboard.png")
        plt.savefig(output_file, dpi=150, bbox_inches="tight")
        plt.close()

        print(f"Network dashboard saved to {output_file}")
        return output_file

    def generate_network_exports(self):
        """Generate network exports for external tools."""
        print("Generating network exports...")

        exports = {}

        # GEXF for Gephi
        gexf_file = os.path.join(self.scraped_data_dir, "master_network.gexf")
        try:
            nx.write_gexf(self.G, gexf_file)
            print(f"GEXF exported to {gexf_file}")
            exports["gexf"] = gexf_file
        except Exception as e:
            print(f"GEXF export failed: {e}")

        # GraphML for other tools
        graphml_file = os.path.join(self.scraped_data_dir, "master_network.graphml")
        try:
            nx.write_graphml(self.G, graphml_file)
            print(f"GraphML exported to {graphml_file}")
            exports["graphml"] = graphml_file
        except Exception as e:
            print(f"GraphML export failed: {e}")

        # JSON for web visualization
        json_file = os.path.join(self.scraped_data_dir, "master_network.json")
        try:
            data = nx.node_link_data(self.G)
            with open(json_file, "w") as f:
                json.dump(data, f, indent=2)
            print(f"JSON exported to {json_file}")
            exports["json"] = json_file
        except Exception as e:
            print(f"JSON export failed: {e}")

        # Edge list
        edges_file = os.path.join(self.scraped_data_dir, "master_network_edges.txt")
        try:
            with open(edges_file, "w") as f:
                for edge in self.G.edges():
                    f.write(f"{edge[0]}\t{edge[1]}\n")
            print(f"Edge list exported to {edges_file}")
            exports["edges"] = edges_file
        except Exception as e:
            print(f"Edge list export failed: {e}")

        # Adjacency matrix (sparse format for large networks)
        adj_file = os.path.join(self.scraped_data_dir, "master_network_adjacency.npz")
        try:
            adj_matrix = nx.adjacency_matrix(self.G)
            import scipy.sparse

            scipy.sparse.save_npz(adj_file, adj_matrix)
            print(f"Adjacency matrix exported to {adj_file}")
            exports["adjacency"] = adj_file
        except Exception as e:
            print(f"Adjacency matrix export failed: {e}")

        return exports

    def generate_comprehensive_report(self):
        """Generate a comprehensive text report."""
        print("Generating comprehensive report...")

        report_file = os.path.join(self.scraped_data_dir, "master_analysis_report.txt")

        with open(report_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write("MASTER NETWORK ANALYSIS REPORT\n")
            f.write("=" * 80 + "\n\n")

            f.write(f"Analysis Date: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Data Directory: {self.scraped_data_dir}\n\n")

            # Network Overview
            f.write("NETWORK OVERVIEW\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Nodes: {self.G.number_of_nodes():,}\n")
            f.write(f"Total Edges: {self.G.number_of_edges():,}\n")
            f.write(
                f"Network Density: {self.analysis_results['metrics']['density']:.6f}\n"
            )
            f.write(f"Number of Communities: {len(self.communities)}\n")
            f.write(
                f"Average Degree: {self.analysis_results['metrics']['avg_degree']:.2f}\n"
            )
            f.write(
                f"Degree Standard Deviation: {self.analysis_results['metrics']['degree_std']:.2f}\n"
            )
            f.write(
                f"Maximum Degree: {self.analysis_results['metrics']['max_degree']}\n"
            )
            f.write(
                f"Minimum Degree: {self.analysis_results['metrics']['min_degree']}\n"
            )
            f.write(
                f"Average Clustering Coefficient: {self.analysis_results['metrics']['avg_clustering']:.4f}\n\n"
            )

            # Connectivity Analysis
            f.write("CONNECTIVITY ANALYSIS\n")
            f.write("-" * 40 + "\n")
            if self.analysis_results["metrics"]["is_connected"]:
                f.write(f"Network Status: CONNECTED\n")
                f.write(
                    f"Network Diameter: {self.analysis_results['metrics']['diameter']}\n"
                )
                f.write(
                    f"Average Shortest Path Length: {self.analysis_results['metrics']['avg_shortest_path']:.2f}\n"
                )
            else:
                f.write(f"Network Status: DISCONNECTED\n")
                f.write(
                    f"Number of Connected Components: {self.analysis_results['metrics']['components']}\n"
                )
                f.write(
                    f"Largest Component Size: {self.analysis_results['metrics']['largest_component_size']:,}\n"
                )
            f.write("\n")

            # Community Analysis
            f.write("COMMUNITY ANALYSIS\n")
            f.write("-" * 40 + "\n")
            community_sizes = [len(comm) for comm in self.communities]
            f.write(f"Number of Communities: {len(self.communities)}\n")
            f.write(f"Average Community Size: {np.mean(community_sizes):.2f}\n")
            f.write(f"Largest Community Size: {max(community_sizes):,}\n")
            f.write(f"Smallest Community Size: {min(community_sizes):,}\n")
            f.write(f"Community Size Std Dev: {np.std(community_sizes):.2f}\n\n")

            # Top Communities
            f.write("TOP 10 COMMUNITIES BY SIZE\n")
            f.write("-" * 40 + "\n")
            community_sizes = [
                (i, len(comm)) for i, comm in enumerate(self.communities)
            ]
            top_communities = sorted(community_sizes, key=lambda x: x[1], reverse=True)[
                :10
            ]
            for i, (comm_id, size) in enumerate(top_communities, 1):
                f.write(f"{i:2d}. Community {comm_id}: {size:,} nodes\n")
            f.write("\n")

            # Centrality Analysis
            f.write("CENTRALITY ANALYSIS\n")
            f.write("-" * 40 + "\n")

            # Top degree nodes
            degree_dict = dict(self.G.degree())
            top_degree = sorted(degree_dict.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
            f.write("Top 10 Nodes by Degree:\n")
            for i, (node, degree) in enumerate(top_degree, 1):
                f.write(f"{i:2d}. {node}: {degree}\n")
            f.write("\n")

            # Top betweenness nodes
            betweenness = self.analysis_results["metrics"]["betweenness_centrality"]
            top_betweenness = sorted(
                betweenness.items(), key=lambda x: x[1], reverse=True
            )[:10]
            f.write("Top 10 Nodes by Betweenness Centrality:\n")
            for i, (node, cent) in enumerate(top_betweenness, 1):
                f.write(f"{i:2d}. {node}: {cent:.6f}\n")
            f.write("\n")

            # Top PageRank nodes
            pagerank = self.analysis_results["metrics"]["pagerank"]
            top_pagerank = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
            f.write("Top 10 Nodes by PageRank:\n")
            for i, (node, pr) in enumerate(top_pagerank, 1):
                f.write(f"{i:2d}. {node}: {pr:.6f}\n")
            f.write("\n")

            # Generated Files
            f.write("GENERATED FILES\n")
            f.write("-" * 40 + "\n")
            f.write("Visualizations:\n")
            f.write("  - master_network_map.png (Main network visualization)\n")
            f.write("  - circular_network.png (Circular layout)\n")
            f.write("  - hierarchical_network.png (Community-based layout)\n")
            f.write("  - network_dashboard.png (Comprehensive dashboard)\n")
            f.write("  - centrality_analysis.png (Centrality distributions)\n")
            f.write("  - degree_analysis.png (Degree analysis)\n")
            f.write("  - subgraph_analysis.png (Top communities)\n")
            f.write("  - temporal_analysis.png (Temporal patterns)\n")
            f.write("  - node_embeddings_tsne.png (Node embeddings)\n")
            f.write("  - 3d_network.png (3D visualization)\n")
            f.write("  - adjacency_matrix.png (Adjacency heatmap)\n")
            f.write("  - interactive_network.html (Interactive viz)\n")
            f.write("  - network_evolution.png (Growth simulation)\n")
            f.write("  - ml_classification.png (ML classification)\n")
            f.write("  - geographic_distribution.png (Geographic mapping)\n")
            f.write("  - realtime_dashboard.png (Real-time dashboard)\n")
            f.write("\n")
            f.write("Analysis Files:\n")
            f.write("  - community_heatmap.png (Community connection heatmap)\n")
            f.write("  - community_statistics.png (Community statistics)\n")
            f.write("  - anomaly_analysis.png (Anomaly detection results)\n")
            f.write("  - anomaly_report.txt (Detailed anomaly report)\n")
            f.write("  - master_analysis_report.txt (This comprehensive report)\n")
            f.write("\n")
            f.write("Export Files:\n")
            f.write("  - master_network.gexf (Gephi format)\n")
            f.write("  - master_network.graphml (GraphML format)\n")
            f.write("  - master_network.json (JSON format)\n")
            f.write("  - master_network_edges.txt (Edge list)\n")
            f.write("  - master_network_adjacency.npz (Adjacency matrix)\n")
            f.write("\n")

            # Analysis Summary
            f.write("ANALYSIS SUMMARY\n")
            f.write("-" * 40 + "\n")
            f.write(
                f"This analysis examined a network of {self.G.number_of_nodes():,} onion sites\n"
            )
            f.write(
                f"connected by {self.G.number_of_edges():,} links, revealing {len(self.communities)}\n"
            )
            f.write(
                f"distinct communities. The network density is {self.analysis_results['metrics']['density']:.6f},\n"
            )
            f.write(
                f"indicating a {'sparse' if self.analysis_results['metrics']['density'] < 0.01 else 'moderate' if self.analysis_results['metrics']['density'] < 0.1 else 'dense'}\n"
            )
            f.write(f"connection structure.\n\n")

            if self.analysis_results["metrics"]["is_connected"]:
                f.write(
                    f"The network is fully connected with a diameter of {self.analysis_results['metrics']['diameter']}\n"
                )
                f.write(
                    f"and average path length of {self.analysis_results['metrics']['avg_shortest_path']:.2f},\n"
                )
                f.write(
                    f"suggesting {'small-world' if self.analysis_results['metrics']['avg_shortest_path'] < 6 else 'large-world'} characteristics.\n"
                )
            else:
                f.write(
                    f"The network consists of {self.analysis_results['metrics']['components']} disconnected components,\n"
                )
                f.write(
                    f"with the largest component containing {self.analysis_results['metrics']['largest_component_size']:,} nodes.\n"
                )

            f.write(
                f"\nCommunity detection revealed a modular structure with community sizes ranging\n"
            )
            f.write(
                f"from {min(community_sizes)} to {max(community_sizes)} nodes, suggesting varying levels\n"
            )
            f.write(f"of organization and specialization across the onion network.\n\n")

            f.write("=" * 80 + "\n")
            f.write("END OF REPORT\n")
            f.write("=" * 80 + "\n")

        print(f"Comprehensive report saved to {report_file}")
        return report_file

    def run_complete_analysis(self):
        """Run the complete master analysis suite."""
        print("=" * 80)
        print("MASTER NETWORK ANALYSIS SUITE")
        print("=" * 80)
        print(f"Analyzing onion network data in: {self.scraped_data_dir}")
        print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        total_start_time = time.time()

        try:
            # Step 1: Build network
            self.build_network()

            # Step 2: Detect communities
            self.detect_communities()

            # Step 3: Calculate metrics
            self.calculate_network_metrics()

            # Step 4: Generate all visualizations
            visualization_files = self.generate_all_visualizations()

            # Step 5: Generate comprehensive report
            report_file = self.generate_comprehensive_report()

            total_elapsed = time.time() - total_start_time

            print("\n" + "=" * 80)
            print("ANALYSIS COMPLETE!")
            print("=" * 80)
            print(f"Total analysis time: {total_elapsed:.2f} seconds")
            print(
                f"Network analyzed: {self.G.number_of_nodes():,} nodes, {self.G.number_of_edges():,} edges"
            )
            print(f"Communities detected: {len(self.communities)}")
            print(f"Visualizations generated: {len(visualization_files)}")
            print(f"Report saved: {report_file}")
            print("=" * 80)

            return {
                "success": True,
                "analysis_time": total_elapsed,
                "network_stats": {
                    "nodes": self.G.number_of_nodes(),
                    "edges": self.G.number_of_edges(),
                    "communities": len(self.communities),
                },
                "visualizations": visualization_files,
                "report": report_file,
            }

        except Exception as e:
            print(f"\nERROR during analysis: {str(e)}")
            import traceback

            traceback.print_exc()
            return {
                "success": False,
                "error": str(e),
                "analysis_time": time.time() - total_start_time,
            }


def main():
    """Main entry point for the master analysis suite."""
    scraped_data_dir = "../scraped_data"

    if not os.path.exists(scraped_data_dir):
        print(f"Error: {scraped_data_dir} directory not found")
        return

    # Create and run the master analyzer
    analyzer = MasterNetworkAnalyzer(scraped_data_dir)
    results = analyzer.run_complete_analysis()

    if results["success"]:
        print("\n🎉 Master analysis completed successfully!")
        print(f"📊 Generated {len(results['visualizations'])} visualization files")
        print(
            f"📈 Network: {results['network_stats']['nodes']:,} nodes, {results['network_stats']['edges']:,} edges"
        )
        print(f"🏘️  Communities: {results['network_stats']['communities']}")
        print(f"⏱️  Total time: {results['analysis_time']:.2f} seconds")
    else:
        print(f"\n❌ Analysis failed: {results['error']}")


if __name__ == "__main__":
    main()
