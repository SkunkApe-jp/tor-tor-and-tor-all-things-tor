#!/usr/bin/env python3
"""
VAE (Variational Autoencoder) Text Clustering Visualization

Creates a visualization that groups similar text documents using a VAE for dimensionality reduction.
Generative model alternative to t-SNE and UMAP with reversible mapping.
"""

import os
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # Force CPU-only mode

import json
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.preprocessing import StandardScaler
from tensorflow.keras import layers, models, backend
import argparse
from pathlib import Path
import time

# Pre-compiled regex for onion address validation (v2: 16 chars, v3: 56 chars, or vanity: <=56 chars)
ONION_PATTERN = re.compile(r'^[a-z2-7]{1,56}$')


def load_text_documents(input_dir):
    """
    Load text documents from the scraped data directory.
    """
    documents = []

    for item in os.listdir(input_dir):
        item_path = os.path.join(input_dir, item)

        # Check if it's a directory that looks like an onion address (<=56 chars with valid base32)
        if os.path.isdir(item_path) and ONION_PATTERN.match(item):
            title_file = os.path.join(item_path, 'website_identity', 'index_title.txt')
            if os.path.exists(title_file):
                try:
                    with open(title_file, 'r', encoding='utf-8') as f:
                        title = f.read().strip()
                    
                    documents.append({
                        'text': title,
                        'title': title,
                        'filename': 'index_title.txt',
                        'onion_address': item,
                        'source_type': 'website_title',
                        'image': f'{item}/images/index.png'
                    })
                except Exception as e:
                    print(f"Error reading {title_file}: {e}")
            
            content_file = os.path.join(item_path, 'website_identity', 'index_content.txt')
            if os.path.exists(content_file):
                try:
                    with open(content_file, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                    
                    documents.append({
                        'text': content,
                        'title': f'Content from {item[:16]}...',
                        'filename': 'index_content.txt',
                        'onion_address': item,
                        'source_type': 'website_content',
                        'image': f'{item}/images/index.png'
                    })
                except Exception as e:
                    print(f"Error reading {content_file}: {e}")
    
    return documents


def extract_text_features(documents, max_features=1000):
    """
    Extract TF-IDF features from text documents.
    """
    texts = [doc['text'] for doc in documents]
    
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        stop_words='english',
        ngram_range=(1, 2),
        min_df=1
    )
    
    features = vectorizer.fit_transform(texts).toarray()
    return features


class VAE:
    """
    Variational Autoencoder for dimensionality reduction.
    """
    
    def __init__(self, input_dim, latent_dim=2, hidden_dims=[256, 128, 64]):
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        self.hidden_dims = hidden_dims
        self.encoder = None
        self.decoder = None
        self.vae = None
        
    def build_encoder(self):
        """Build the encoder network."""
        inputs = layers.Input(shape=(self.input_dim,))
        x = inputs
        
        for hidden_dim in self.hidden_dims:
            x = layers.Dense(hidden_dim, activation='relu')(x)
            x = layers.Dropout(0.3)(x)
        
        z_mean = layers.Dense(self.latent_dim, name='z_mean')(x)
        z_log_var = layers.Dense(self.latent_dim, name='z_log_var')(x)
        
        def sampling(args):
            z_mean, z_log_var = args
            batch_size = backend.shape(z_mean)[0]
            epsilon = backend.random_normal(shape=(batch_size, self.latent_dim))
            return z_mean + backend.exp(0.5 * z_log_var) * epsilon
        
        z = layers.Lambda(sampling, name='z')([z_mean, z_log_var])
        
        self.encoder = models.Model(inputs, [z_mean, z_log_var, z], name='encoder')
        return self.encoder
    
    def build_decoder(self):
        """Build the decoder network."""
        inputs = layers.Input(shape=(self.latent_dim,))
        x = inputs
        
        for hidden_dim in reversed(self.hidden_dims):
            x = layers.Dense(hidden_dim, activation='relu')(x)
            x = layers.Dropout(0.3)(x)
        
        outputs = layers.Dense(self.input_dim, activation='linear')(x)
        
        self.decoder = models.Model(inputs, outputs, name='decoder')
        return self.decoder
    
    def build_vae(self):
        """Build the complete VAE model."""
        if self.encoder is None:
            self.build_encoder()
        if self.decoder is None:
            self.build_decoder()
        
        inputs = self.encoder.input
        outputs = self.decoder(self.encoder(inputs)[2])
        
        self.vae = models.Model(inputs, outputs, name='vae')
        
        def vae_loss(x, x_decoded):
            reconstruction_loss = backend.mean(backend.square(x - x_decoded))
            reconstruction_loss *= self.input_dim
            
            z_mean = self.encoder(inputs)[0]
            z_log_var = self.encoder(inputs)[1]
            kl_loss = -0.5 * backend.mean(
                1 + z_log_var - backend.square(z_mean) - backend.exp(z_log_var)
            )
            
            return reconstruction_loss + kl_loss
        
        self.vae.compile(optimizer='adam', loss=vae_loss)
        return self.vae
    
    def fit(self, X, epochs=50, batch_size=32, validation_split=0.1, verbose=1):
        """Train the VAE."""
        if self.vae is None:
            self.build_vae()
        
        history = self.vae.fit(
            X, X,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            verbose=verbose
        )
        return history
    
    def encode(self, X):
        """Encode data to latent space."""
        return self.encoder.predict(X, verbose=0)[2]
    
    def decode(self, Z):
        """Decode from latent space."""
        return self.decoder.predict(Z, verbose=0)
    
    def fit_transform(self, X, epochs=50, batch_size=32):
        """Fit and transform in one step."""
        self.fit(X, epochs=epochs, batch_size=batch_size, verbose=0)
        return self.encode(X)


def apply_vae(features, latent_dim=2, hidden_dims=[128, 64, 32], epochs=100, batch_size=16):
    """
    Apply VAE to reduce features to 2D coordinates.
    """
    print(f"Applying VAE with {features.shape[0]} samples...")

    # Standardize features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # Handle edge case: too few samples
    if features_scaled.shape[0] < 3:
        print("Too few samples for VAE, using simple layout...")
        coords = np.zeros((features_scaled.shape[0], 2))
        for i in range(features_scaled.shape[0]):
            coords[i][0] = 500 + i * 200
            coords[i][1] = 500
        return coords

    # Create and train VAE
    start_time = time.time()
    vae = VAE(
        input_dim=features_scaled.shape[1],
        latent_dim=latent_dim,
        hidden_dims=hidden_dims
    )
    
    print(f"Training VAE for {epochs} epochs...")
    vae_coords = vae.fit_transform(features_scaled, epochs=epochs, batch_size=batch_size)
    elapsed = time.time() - start_time

    print(f"VAE completed in {elapsed:.3f} seconds")
    return vae_coords


def generate_d3_visualization(coords, documents, output_file, method_name='VAE'):
    """
    Generate HTML with D3 visualization for clustered text documents.
    """
    coords_min = coords.min(axis=0)
    coords_max = coords.max(axis=0)
    coords_normalized = (coords - coords_min) / (coords_max - coords_min)

    canvas_size = 1000
    coords_scaled = coords_normalized * canvas_size

    text_data = []
    for i, doc in enumerate(documents):
        text_data.append({
            'x': float(coords_scaled[i][0]),
            'y': float(coords_scaled[i][1]),
            'title': doc.get('title', 'Unknown'),
            'filename': doc.get('filename', 'unknown.txt'),
            'text_preview': doc.get('text', '')[:200] + '...' if len(doc.get('text', '')) > 200 else doc.get('text', ''),
            'onion_address': doc.get('onion_address', ''),
            'source_type': doc.get('source_type', 'unknown'),
            'image': doc.get('image', '')
        })

    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <title>{method_name} Text Clustering Visualization</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {{
            margin: 0;
            overflow: hidden;
            background-color: #f8f9fa;
            font-family: Arial, sans-serif;
        }}
        #tooltip {{
            position: absolute;
            text-align: left;
            padding: 10px;
            font-size: 14px;
            background: rgba(255, 255, 255, 0.95);
            color: black;
            border: 1px solid #ccc;
            border-radius: 4px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            max-width: 400px;
            z-index: 100;
        }}
        .text-node {{
            cursor: pointer;
            transition: all 0.2s;
        }}
        .text-node:hover {{
            stroke: #ff6b6b;
            stroke-width: 2px;
            z-index: 10;
        }}
        #title {{
            position: absolute;
            top: 10px;
            left: 10px;
            color: black;
            font-size: 18px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.8);
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
        }}
        #legend {{
            position: absolute;
            bottom: 20px;
            right: 20px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.9);
            padding: 12px 16px;
            border-radius: 8px;
            border: 1px solid #ddd;
            font-size: 13px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 5px;
        }}
        .legend-color {{
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        #controls {{
            position: absolute;
            top: 10px;
            right: 10px;
            z-index: 10;
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        .control-btn {{
            background: rgba(255, 255, 255, 0.8);
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 8px 12px;
            cursor: pointer;
            font-size: 14px;
            color: black;
            text-align: center;
            min-width: 40px;
            user-select: none;
        }}
        .control-btn:hover {{
            background: rgba(240, 240, 240, 0.9);
        }}
        #info {{
            position: absolute;
            bottom: 10px;
            left: 10px;
            color: black;
            font-size: 12px;
            z-index: 10;
            background: rgba(255, 255, 255, 0.8);
            padding: 5px 10px;
            border-radius: 4px;
            border: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div id="title">{method_name} Text Clustering Visualization</div>
    <div id="controls">
        <button class="control-btn" onclick="zoomIn()">+</button>
        <button class="control-btn" onclick="zoomOut()">-</button>
        <button class="control-btn" onclick="resetView()">↺</button>
    </div>
    <div id="info">Displaying {len(text_data)} text documents clustered by semantic similarity</div>
    <div id="legend">
        <div class="legend-item">
            <div class="legend-color" style="background-color: #9b59b6;"></div>
            <span>Website Title</span>
        </div>
    </div>
    <div id="tooltip"></div>
    <script>
        const textData = {json.dumps(text_data)};
        const width = window.innerWidth;
        const height = window.innerHeight;

        const svg = d3.select("body")
            .append("svg")
            .attr("width", width)
            .attr("height", height)
            .attr("style", "max-width: 100%; height: 100vh;");

        const zoom = d3.zoom()
            .scaleExtent([0.05, 10])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});
        svg.call(zoom);

        function zoomIn() {{
            svg.transition().duration(750).call(zoom.scaleBy, 1.5);
        }}
        function zoomOut() {{
            svg.transition().duration(750).call(zoom.scaleBy, 0.5);
        }}
        function resetView() {{
            svg.transition().duration(750).call(zoom.transform, d3.zoomIdentity);
        }}

        const g = svg.append("g");

        const allX = textData.map(d => d.x);
        const allY = textData.map(d => d.y);
        const minX = Math.min(...allX), maxX = Math.max(...allX);
        const minY = Math.min(...allY), maxY = Math.max(...allY);
        const rangeX = maxX - minX || 1000;
        const rangeY = maxY - minY || 1000;

        const initialScale = Math.min(
            (width * 0.8) / rangeX,
            (height * 0.8) / rangeY,
            1
        );
        const initialX = (width / 2) - ((minX + maxX) / 2) * initialScale;
        const initialY = (height / 2) - ((minY + maxY) / 2) * initialScale;
        svg.call(zoom.transform, d3.zoomIdentity.translate(initialX, initialY).scale(initialScale));

        const tooltip = d3.select("#tooltip");

        const textNodes = g.selectAll(".text-node")
            .data(textData)
            .enter()
            .append("circle")
            .attr("class", "text-node")
            .attr("cx", d => d.x)
            .attr("cy", d => d.y)
            .attr("r", 8)
            .attr("fill", "#9b59b6")
            .attr("stroke", "#8e44ad")
            .attr("stroke-width", 1.5)
            .on("mouseover", function(event, d) {{
                tooltip.transition()
                    .duration(200)
                    .style("opacity", .95);
                tooltip.html(`<div><strong>${{d.title}}</strong></div><div style="font-size:11px;color:#666;">${{d.onion_address}}</div><div style="margin-top:8px;font-size:12px;">${{d.text_preview}}</div>`)
                    .style("left", (event.pageX + 10) + "px")
                    .style("top", (event.pageY - 28) + "px");
            }})
            .on("mouseout", function(d) {{
                tooltip.transition()
                    .duration(500)
                    .style("opacity", 0);
            }})
            .on("click", function(event, d) {{
                if (d.onion_address) {{
                    const onionUrl = `http://${{d.onion_address}}.onion`;
                    navigator.clipboard.writeText(onionUrl).then(() => {{
                        const notification = document.createElement('div');
                        notification.textContent = 'Copied: ' + onionUrl;
                        notification.style.position = 'fixed';
                        notification.style.bottom = '20px';
                        notification.style.left = '50%';
                        notification.style.transform = 'translateX(-50%)';
                        notification.style.backgroundColor = '#4CAF50';
                        notification.style.color = 'white';
                        notification.style.padding = '10px 20px';
                        notification.style.borderRadius = '5px';
                        notification.style.zIndex = '1000';
                        document.body.appendChild(notification);
                        setTimeout(() => document.body.removeChild(notification), 3000);
                    }});
                }}
            }});

        window.addEventListener("resize", () => {{
            const newWidth = window.innerWidth;
            const newHeight = window.innerHeight;
            svg.attr("width", newWidth).attr("height", newHeight);
        }});
    </script>
</body>
</html>"""

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"{method_name} visualization created at {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Create VAE clustering visualization for text documents')

    script_dir = Path(__file__).parent
    default_input = script_dir / "../scraped_data"
    default_output = script_dir / "../scraped_data/vae_text_clusters.html"

    parser.add_argument('--input-dir', default=str(default_input),
                        help='Directory containing scraped data with text files')
    parser.add_argument('--output', default=str(default_output),
                        help='Output HTML file path')
    parser.add_argument('--max-features', type=int, default=1000,
                        help='Maximum TF-IDF features (default: 1000)')
    parser.add_argument('--latent-dim', type=int, default=2,
                        help='VAE latent space dimension (default: 2)')
    parser.add_argument('--hidden-dims', type=str, default='128,64,32',
                        help='VAE hidden layer dimensions comma-separated (default: 128,64,32)')
    parser.add_argument('--epochs', type=int, default=100,
                        help='VAE training epochs (default: 100)')
    parser.add_argument('--batch-size', type=int, default=16,
                        help='VAE batch size (default: 16)')

    args = parser.parse_args()

    print(f"Loading text documents from {args.input_dir}...")
    documents = load_text_documents(args.input_dir)

    if not documents:
        print(f"No text documents found in {args.input_dir}")
        return

    print(f"Found {len(documents)} text documents")

    print(f"Extracting TF-IDF features...")
    features = extract_text_features(documents, max_features=args.max_features)
    print(f"Feature matrix shape: {features.shape}")

    hidden_dims = [int(x) for x in args.hidden_dims.split(',')]
    coords = apply_vae(
        features,
        latent_dim=args.latent_dim,
        hidden_dims=hidden_dims,
        epochs=args.epochs,
        batch_size=args.batch_size
    )

    output_dir = os.path.dirname(args.output)
    os.makedirs(output_dir, exist_ok=True)

    generate_d3_visualization(coords, documents, args.output, method_name='VAE')

    print(f"VAE text clustering visualization complete!")
    print(f"Output saved to: {args.output}")


if __name__ == "__main__":
    main()
