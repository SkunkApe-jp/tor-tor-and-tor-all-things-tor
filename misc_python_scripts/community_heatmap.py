#!/usr/bin/env python3
"""
Community Heatmap Generator

Creates heatmaps and statistical visualizations showing connection patterns
between communities in the onion network.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import networkx as nx

def generate_community_heatmap(G, communities, scraped_data_dir):
    """Generate a heatmap showing connection patterns between communities."""
    
    print("Generating community connection heatmap...")
    
    # Build community-to-node mapping
    community_nodes = {}
    for i, comm in enumerate(communities):
        community_nodes[i] = list(comm)
    
    # Create adjacency matrix between communities
    num_communities = len(communities)
    connection_matrix = np.zeros((num_communities, num_communities))
    
    # Count connections between communities
    for edge in G.edges():
        node1, node2 = edge
        
        # Find which communities each node belongs to
        comm1 = None
        comm2 = None
        
        for comm_id, nodes in community_nodes.items():
            if node1 in nodes:
                comm1 = comm_id
            if node2 in nodes:
                comm2 = comm_id
        
        if comm1 is not None and comm2 is not None:
            connection_matrix[comm1][comm2] += 1
            connection_matrix[comm2][comm1] += 1  # Symmetric for undirected graph
    
    # Create community labels with sizes
    community_labels = []
    for i in range(num_communities):
        size = len(community_nodes[i])
        community_labels.append(f"C{i}\n({size} nodes)")
    
    # Create heatmap
    plt.figure(figsize=(12, 10))
    
    # Use seaborn for better heatmap
    sns.heatmap(
        connection_matrix,
        annot=True,
        fmt='g',
        cmap='YlOrRd',
        xticklabels=community_labels,
        yticklabels=community_labels,
        cbar_kws={'label': 'Number of Connections'}
    )
    
    plt.title('Community Connection Heatmap\n(Darker = More connections between communities)', fontsize=14)
    plt.xlabel('Target Community')
    plt.ylabel('Source Community')
    plt.tight_layout()
    
    # Save heatmap
    heatmap_file = os.path.join(scraped_data_dir, "community_heatmap.png")
    plt.savefig(heatmap_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Community heatmap saved to {heatmap_file}")
    
    # Also create a summary statistics visualization
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
    
    # 1. Community sizes
    community_sizes = [len(comm) for comm in communities]
    ax1.bar(range(num_communities), community_sizes)
    ax1.set_title('Community Sizes')
    ax1.set_xlabel('Community ID')
    ax1.set_ylabel('Number of Nodes')
    
    # 2. Connection density per community
    internal_connections = []
    for i in range(num_communities):
        internal_connections.append(int(connection_matrix[i][i]))
    
    ax2.bar(range(num_communities), internal_connections)
    ax2.set_title('Internal Connections per Community')
    ax2.set_xlabel('Community ID')
    ax2.set_ylabel('Internal Connections')
    
    # 3. External connections (sum of off-diagonal)
    external_connections = []
    for i in range(num_communities):
        external = np.sum(connection_matrix[i]) - connection_matrix[i][i]
        external_connections.append(int(external))
    
    ax3.bar(range(num_communities), external_connections)
    ax3.set_title('External Connections per Community')
    ax3.set_xlabel('Community ID')
    ax3.set_ylabel('External Connections')
    
    # 4. Connection ratio (internal vs external)
    ratios = []
    for i in range(num_communities):
        internal = connection_matrix[i][i]
        external = np.sum(connection_matrix[i]) - internal
        ratio = internal / (external + 1)  # +1 to avoid division by zero
        ratios.append(ratio)
    
    ax4.bar(range(num_communities), ratios)
    ax4.set_title('Internal/External Connection Ratio')
    ax4.set_xlabel('Community ID')
    ax4.set_ylabel('Ratio (higher = more self-contained)')
    
    plt.tight_layout()
    
    # Save statistics
    stats_file = os.path.join(scraped_data_dir, "community_statistics.png")
    plt.savefig(stats_file, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Community statistics saved to {stats_file}")
    
    return heatmap_file, stats_file

if __name__ == "__main__":
    # This can be run standalone for testing
    print("Heatmap generator ready - import and use generate_community_heatmap()")
