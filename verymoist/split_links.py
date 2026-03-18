#!/usr/bin/env python3
"""
Script to split a list of links into separate files with up to 10,000 links each.
"""

import os
import sys
from pathlib import Path


def split_links_file(input_file, chunk_size=10000):
    """
    Split a text file containing links into multiple files with up to chunk_size links each.
    
    Args:
        input_file (str): Path to the input file containing links (one per line)
        chunk_size (int): Maximum number of links per output file (default 10000)
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        print(f"Error: Input file '{input_file}' does not exist.")
        return
    
    # Read all links from the input file
    with open(input_path, 'r', encoding='utf-8') as f:
        links = [line.strip() for line in f if line.strip()]
    
    print(f"Found {len(links)} total links in '{input_file}'")
    
    # Calculate number of output files needed
    num_chunks = (len(links) + chunk_size - 1) // chunk_size  # Ceiling division
    print(f"Splitting into {num_chunks} file(s) with max {chunk_size} links each")
    
    # Create output directory if it doesn't exist
    output_dir = input_path.parent / "split_output"
    output_dir.mkdir(exist_ok=True)
    
    # Split links into chunks and write to separate files
    for i in range(num_chunks):
        start_idx = i * chunk_size
        end_idx = min((i + 1) * chunk_size, len(links))
        
        chunk = links[start_idx:end_idx]
        
        # Create output filename
        stem = input_path.stem
        output_filename = output_dir / f"{stem}_part_{i+1:03d}.txt"
        
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(chunk) + '\n')
        
        print(f"Created '{output_filename}' with {len(chunk)} links")
    
    print(f"All done! Output files are in '{output_dir}'")


def main():
    if len(sys.argv) < 2:
        print("Usage: python split_links.py <input_file.txt> [chunk_size]")
        print("Example: python split_links.py links.txt          # Split into files of 10000 links each")
        print("         python split_links.py links.txt 5000     # Split into files of 5000 links each")
        sys.exit(1)
    
    input_file = sys.argv[1]
    chunk_size = 10000  # Default chunk size
    
    if len(sys.argv) > 2:
        try:
            chunk_size = int(sys.argv[2])
            if chunk_size <= 0:
                raise ValueError("Chunk size must be positive")
        except ValueError:
            print(f"Error: Invalid chunk size '{sys.argv[2]}'. Please provide a positive integer.")
            sys.exit(1)
    
    split_links_file(input_file, chunk_size)


if __name__ == "__main__":
    main()