#!/usr/bin/env python3
"""
Fast Multi-Threaded Onion Title Scrubber

An high-performance version of onion_checker_with_title_scrubber.py
that uses multithreading to check hundreds of sites in minutes.
"""

import requests
import csv
import json
import argparse
import time
import re
import html
import os
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# Standard settings for consistency
PROXIES = {
    'http': 'socks5h://127.0.0.1:9050',
    'https': 'socks5h://127.0.0.1:9050'
}
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0'
}

def is_valid_onion_url(url):
    try:
        parsed = urlparse(url)
        return parsed.netloc.endswith('.onion') if parsed.netloc else url.endswith('.onion')
    except:
        return False

def extract_title(html_content):
    if not html_content: return "No Title Found"
    match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE | re.DOTALL)
    return html.unescape(match.group(1).strip()) if match else "No Title Found"

def check_site(url, timeout=30, delay=None):
    """Worker function for checking a single site."""
    # Apply randomized or specified delay
    wait_time = delay if delay is not None else random.uniform(1.0, 5.0)
    time.sleep(wait_time)
    if not url.startswith('http'):
        url = 'http://' + url
        
    try:
        response = requests.get(url, proxies=PROXIES, headers=HEADERS, timeout=timeout, allow_redirects=True)
        title = extract_title(response.text)
        return {
            "url": url,
            "status": response.status_code,
            "title": title,
            "success": response.status_code == 200
        }
    except Exception as e:
        return {
            "url": url,
            "status": 0,
            "title": str(e),
            "success": False
        }

def process_batch(urls, max_workers=5, timeout=60, delay=None):
    """Process URLs in parallel using multithreading."""
    results = []
    total = len(urls)
    completed = 0
    
    delay_info = f"{delay}s" if delay is not None else "random 1-5s"
    print(f"[*] Starting Fast Scrubber with {max_workers} threads and {delay_info} delay...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(check_site, url, timeout, delay): url for url in urls}
        
        for future in as_completed(future_to_url):
            completed += 1
            result = future.result()
            results.append(result)
            
            if result['success']:
                print(f" [{completed}/{total}] ✓ {result['url']} - {result['title'][:50]}")
            else:
                print(f" [{completed}/{total}] ✗ {result['url']} (Failed)")
                
    return results

def main():
    parser = argparse.ArgumentParser(description='Fast Multi-Threaded Onion Scrubber')
    parser.add_argument('--input', help='Input text file with onion URLs')
    parser.add_argument('--threads', type=int, default=15, help='Number of parallel threads')
    parser.add_argument('--delay', type=float, default=None, help='Delay before each request in seconds (default: random 1-5s)')
    parser.add_argument('--output', default='fast_results.json', help='Output JSON file')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"Error: {args.input} not found.")
        return

    with open(args.input, 'r', encoding='utf-8') as f:
        urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        # Extract onion URLs specifically, allowing underscores/hyphens for test clones
        urls = [re.search(r'([a-zA-Z0-9_-]+\.onion)', u, re.I).group(1) for u in urls if ".onion" in u]

    start_time = time.time()
    results = process_batch(urls, max_workers=args.threads, delay=args.delay)
    end_time = time.time()
    
    # Save to JSON
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"\n[✓] Done! Processed {len(urls)} sites in {end_time - start_time:.2f} seconds.")
    print(f"[✓] Results saved to {args.output}")

if __name__ == "__main__":
    main()
