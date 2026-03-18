#!/usr/bin/env python3
"""
Extract all discovered links from scraped_data directories.
Scans all onion directories and collects links from discovered_links folders.
"""

import re
from pathlib import Path
from datetime import datetime


def extract_links_from_file(file_path):
    """Extract .onion links from a text file."""
    links = set()
    onion_pattern = re.compile(r'https?://[a-z2-7]{16,}\.onion[^\s"\'<>]*', re.IGNORECASE)
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            matches = onion_pattern.findall(content)
            links.update(matches)
    except Exception as e:
        print(f"  Warning: Could not read {file_path}: {e}")
    
    return links


def main():
    scraped_data_dir = Path(__file__).parent / "../scraped_data"
    output_file = Path(__file__).parent / "../config" / "all_discovered_links.txt"
    
    if not scraped_data_dir.exists():
        print(f"Error: {scraped_data_dir} does not exist!")
        return
    
    all_links = set()
    dirs_processed = 0
    files_processed = 0
    
    print(f"Scanning {scraped_data_dir} for discovered_links folders...\n")
    
    # Iterate through all directories in scraped_data
    for item in sorted(scraped_data_dir.iterdir()):
        if not item.is_dir():
            continue
        
        discovered_links_dir = item / "discovered_links"
        
        if not discovered_links_dir.exists():
            continue
        
        dirs_processed += 1
        print(f"Processing: {item.name}")
        
        # Process all files in discovered_links folder
        for link_file in sorted(discovered_links_dir.iterdir()):
            if link_file.is_file() and link_file.suffix == '.txt':
                links = extract_links_from_file(link_file)
                if links:
                    all_links.update(links)
                    files_processed += 1
                    print(f"  - {link_file.name}: {len(links)} links")
    
    print(f"\n{'='*50}")
    print(f"Directories processed: {dirs_processed}")
    print(f"Files processed: {files_processed}")
    print(f"Total unique links found: {len(all_links)}")
    
    # Save to output file
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        for link in sorted(all_links):
            f.write(f"{link}\n")
    
    print(f"\nLinks saved to: {output_file}")
    
    # Also save with timestamp for archival
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_file = Path(__file__).parent / "../config" / f"all_discovered_links_{timestamp}.txt"
    
    with open(archive_file, 'w', encoding='utf-8') as f:
        f.write(f"# Extracted on: {datetime.now().isoformat()}\n")
        f.write(f"# Total links: {len(all_links)}\n\n")
        for link in sorted(all_links):
            f.write(f"{link}\n")
    
    print(f"Archive saved to: {archive_file}")


if __name__ == "__main__":
    main()
