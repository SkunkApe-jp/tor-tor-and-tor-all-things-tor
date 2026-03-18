#!/usr/bin/env python3
"""
Anomaly Detection for Onion Networks

Identifies unusual patterns, potential honeypots, exit nodes, and outliers
in the onion network structure.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import networkx as nx
from collections import Counter
import seaborn as sns

def detect_anomalies(G, communities, scraped_data_dir):
    """Detect various types of anomalies in the network."""
    
    print("Detecting network anomalies...")
    
    anomalies = {
        'degree_outliers': [],
        'betweenness_outliers': [],
        'community_bridges': [],
        'isolated_hubs': [],
        'suspicious_patterns': []
    }
    
    # 1. Degree Outliers (unusually high/low connectivity)
    degrees = dict(G.degree())
    degree_values = list(degrees.values())
    degree_mean = np.mean(degree_values)
    degree_std = np.std(degree_values)
    
    # High degree outliers (potential hubs/exit nodes)
    high_threshold = degree_mean + 2 * degree_std
    for node, degree in degrees.items():
        if degree > high_threshold:
            anomalies['degree_outliers'].append({
                'node': node,
                'degree': degree,
                'type': 'high_degree_hub',
                'z_score': (degree - degree_mean) / degree_std
            })
    
    # 2. Betweenness Centrality Outliers (potential bridges/bottlenecks)
    betweenness = nx.betweenness_centrality(G)
    betweenness_values = list(betweenness.values())
    betweenness_mean = np.mean(betweenness_values)
    betweenness_std = np.std(betweenness_values)
    
    high_betweenness_threshold = betweenness_mean + 2 * betweenness_std
    for node, centrality in betweenness.items():
        if centrality > high_betweenness_threshold:
            anomalies['betweenness_outliers'].append({
                'node': node,
                'betweenness': centrality,
                'type': 'critical_bridge',
                'z_score': (centrality - betweenness_mean) / betweenness_std
            })
    
    # 3. Community Bridges (nodes connecting multiple communities)
    community_nodes = {}
    for i, comm in enumerate(communities):
        community_nodes[i] = list(comm)
    
    node_communities = {}
    for comm_id, nodes in community_nodes.items():
        for node in nodes:
            if node not in node_communities:
                node_communities[node] = []
            node_communities[node].append(comm_id)
    
    # Find nodes with connections to multiple communities
    for node, node_comms in node_communities.items():
        if len(node_comms) > 1:
            # Check if this node actually bridges communities (has edges to other communities)
            bridges_to = set()
            for neighbor in G.neighbors(node):
                if neighbor in node_communities:
                    bridges_to.update(node_communities[neighbor])
            
            if len(bridges_to) > 1:
                anomalies['community_bridges'].append({
                    'node': node,
                    'communities': node_comms,
                    'bridges_to': list(bridges_to),
                    'degree': degrees.get(node, 0)
                })
    
    # 4. Isolated Hubs (high degree but low clustering)
    clustering = nx.clustering(G)
    for node in anomalies['degree_outliers']:
        node_name = node['node']
        cluster_coeff = clustering.get(node_name, 0)
        if cluster_coeff < 0.1:  # Low clustering coefficient
            anomalies['isolated_hubs'].append({
                'node': node_name,
                'degree': node['degree'],
                'clustering': cluster_coeff,
                'type': 'isolated_hub'
            })
    
    # 5. Suspicious Patterns (potential honeypots)
    # Very high degree + very low clustering + high betweenness
    for node_name in G.nodes():
        deg = degrees.get(node_name, 0)
        cluster = clustering.get(node_name, 0)
        betw = betweenness.get(node_name, 0)
        
        if (deg > high_threshold and 
            cluster < 0.05 and 
            betw > high_betweenness_threshold):
            anomalies['suspicious_patterns'].append({
                'node': node_name,
                'degree': deg,
                'clustering': cluster,
                'betweenness': betw,
                'type': 'potential_honeypot'
            })
    
    # Generate anomaly visualizations
    generate_anomaly_plots(G, anomalies, scraped_data_dir)
    
    # Save anomaly report
    save_anomaly_report(anomalies, scraped_data_dir)
    
    return anomalies

def generate_anomaly_plots(G, anomalies, scraped_data_dir):
    """Create visualizations of detected anomalies."""
    
    print("Generating anomaly visualizations...")
    
    # 1. Anomaly Overview Plot
    fig, axes = plt.subplots(2, 3, figsize=(18, 12))
    axes = axes.flatten()
    
    # Degree distribution with outliers
    degrees = [G.degree(n) for n in G.nodes()]
    axes[0].hist(degrees, bins=50, alpha=0.7, color='blue', edgecolor='black')
    outlier_degrees = [a['degree'] for a in anomalies['degree_outliers']]
    if outlier_degrees:
        axes[0].hist(outlier_degrees, bins=20, alpha=0.7, color='red', edgecolor='black')
    axes[0].set_title('Degree Distribution\n(Red = Outliers)')
    axes[0].set_xlabel('Degree')
    axes[0].set_ylabel('Frequency')
    axes[0].set_yscale('log')
    
    # Betweenness distribution
    betweenness = list(nx.betweenness_centrality(G).values())
    axes[1].hist(betweenness, bins=50, alpha=0.7, color='green', edgecolor='black')
    outlier_betweenness = [a['betweenness'] for a in anomalies['betweenness_outliers']]
    if outlier_betweenness:
        axes[1].hist(outlier_betweenness, bins=20, alpha=0.7, color='red', edgecolor='black')
    axes[1].set_title('Betweenness Centrality\n(Red = Outliers)')
    axes[1].set_xlabel('Betweenness')
    axes[1].set_ylabel('Frequency')
    axes[1].set_yscale('log')
    
    # Clustering coefficient distribution
    clustering = list(nx.clustering(G).values())
    axes[2].hist(clustering, bins=50, alpha=0.7, color='orange', edgecolor='black')
    axes[2].set_title('Clustering Coefficient Distribution')
    axes[2].set_xlabel('Clustering Coefficient')
    axes[2].set_ylabel('Frequency')
    
    # Anomaly counts
    anomaly_types = ['Degree Outliers', 'Betweenness Outliers', 'Community Bridges', 
                    'Isolated Hubs', 'Suspicious Patterns']
    anomaly_counts = [
        len(anomalies['degree_outliers']),
        len(anomalies['betweenness_outliers']),
        len(anomalies['community_bridges']),
        len(anomalies['isolated_hubs']),
        len(anomalies['suspicious_patterns'])
    ]
    
    bars = axes[3].bar(anomaly_types, anomaly_counts, color=['red', 'blue', 'green', 'orange', 'purple'])
    axes[3].set_title('Detected Anomalies by Type')
    axes[3].set_ylabel('Count')
    axes[3].tick_params(axis='x', rotation=45)
    
    # Add value labels on bars
    for bar, count in zip(bars, anomaly_counts):
        if count > 0:
            axes[3].text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                        str(count), ha='center', va='bottom')
    
    # Degree vs Betweenness scatter plot
    all_degrees = [G.degree(n) for n in G.nodes()]
    all_betweenness = list(nx.betweenness_centrality(G).values())
    axes[4].scatter(all_degrees, all_betweenness, alpha=0.5, s=10, color='blue')
    
    # Highlight anomalies
    if anomalies['degree_outliers']:
        outlier_nodes = [a['node'] for a in anomalies['degree_outliers']]
        outlier_degrees = [G.degree(n) for n in outlier_nodes]
        outlier_betweenness = [nx.betweenness_centrality(G)[n] for n in outlier_nodes]
        axes[4].scatter(outlier_degrees, outlier_betweenness, 
                       color='red', s=50, alpha=0.7, label='Degree Outliers')
    
    axes[4].set_xlabel('Degree')
    axes[4].set_ylabel('Betweenness Centrality')
    axes[4].set_title('Degree vs Betweenness Centrality')
    axes[4].set_xscale('log')
    axes[4].set_yscale('log')
    axes[4].legend()
    
    # Community bridge analysis
    bridge_counts = [len(a['communities']) for a in anomalies['community_bridges']]
    if bridge_counts:
        axes[5].hist(bridge_counts, bins=range(1, max(bridge_counts)+2), 
                     alpha=0.7, color='purple', edgecolor='black')
        axes[5].set_title('Community Bridge Analysis')
        axes[5].set_xlabel('Number of Communities Connected')
        axes[5].set_ylabel('Number of Nodes')
    else:
        axes[5].text(0.5, 0.5, 'No Community Bridges Found', 
                    ha='center', va='center', transform=axes[5].transAxes)
        axes[5].set_title('Community Bridge Analysis')
    
    plt.tight_layout()
    
    # Save anomaly overview
    anomaly_plot_file = os.path.join(scraped_data_dir, "anomaly_analysis.png")
    plt.savefig(anomaly_plot_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Anomaly analysis plot saved to {anomaly_plot_file}")

def save_anomaly_report(anomalies, scraped_data_dir):
    """Save detailed anomaly report to text file."""
    
    report_file = os.path.join(scraped_data_dir, "anomaly_report.txt")
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("=== ONION NETWORK ANOMALY DETECTION REPORT ===\n\n")
        
        f.write(f"Total anomalies detected: {sum(len(v) for v in anomalies.values() if isinstance(v, list))}\n\n")
        
        # Degree Outliers
        f.write("=== DEGREE OUTLIERS (Potential Hubs/Exit Nodes) ===\n")
        for anomaly in sorted(anomalies['degree_outliers'], key=lambda x: x['degree'], reverse=True)[:10]:
            f.write(f"Node: {anomaly['node']}\n")
            f.write(f"  Degree: {anomaly['degree']} (Z-score: {anomaly['z_score']:.2f})\n")
            f.write(f"  Type: {anomaly['type']}\n\n")
        
        # Betweenness Outliers
        f.write("=== BETWEENNESS OUTLIERS (Critical Bridges) ===\n")
        for anomaly in sorted(anomalies['betweenness_outliers'], key=lambda x: x['betweenness'], reverse=True)[:10]:
            f.write(f"Node: {anomaly['node']}\n")
            f.write(f"  Betweenness: {anomaly['betweenness']:.4f} (Z-score: {anomaly['z_score']:.2f})\n")
            f.write(f"  Type: {anomaly['type']}\n\n")
        
        # Community Bridges
        f.write("=== COMMUNITY BRIDGES ===\n")
        for anomaly in sorted(anomalies['community_bridges'], key=lambda x: len(x['communities']), reverse=True)[:10]:
            f.write(f"Node: {anomaly['node']}\n")
            f.write(f"  Communities: {anomaly['communities']}\n")
            f.write(f"  Bridges to: {anomaly['bridges_to']}\n")
            f.write(f"  Degree: {anomaly['degree']}\n\n")
        
        # Isolated Hubs
        f.write("=== ISOLATED HUBS (Low Clustering) ===\n")
        for anomaly in sorted(anomalies['isolated_hubs'], key=lambda x: x['degree'], reverse=True)[:10]:
            f.write(f"Node: {anomaly['node']}\n")
            f.write(f"  Degree: {anomaly['degree']}\n")
            f.write(f"  Clustering: {anomaly['clustering']:.4f}\n")
            f.write(f"  Type: {anomaly['type']}\n\n")
        
        # Suspicious Patterns
        f.write("=== SUSPICIOUS PATTERNS (Potential Honeypots) ===\n")
        for anomaly in anomalies['suspicious_patterns']:
            f.write(f"Node: {anomaly['node']}\n")
            f.write(f"  Degree: {anomaly['degree']}\n")
            f.write(f"  Clustering: {anomaly['clustering']:.4f}\n")
            f.write(f"  Betweenness: {anomaly['betweenness']:.4f}\n")
            f.write(f"  Type: {anomaly['type']}\n\n")
    
    print(f"Anomaly report saved to {report_file}")

if __name__ == "__main__":
    print("Anomaly detection module ready - import and use detect_anomalies()")
