#!/usr/bin/env python3
"""
Vanity Onion Link Filter

Reads a text file and extracts onion addresses that appear to be 
"Vanity" (Branded/Non-random) based on their prefix.
"""

import re
import os

# Keywords often used for branding on the dark web
VANITY_KEYWORDS = [
    'wiki', 'torch', 'market', 'store', 'shop', 'chan', 'forum', 'bank', 
    'mail', 'mixer', 'btc', 'coin', 'hidden', 'dark', 'vault', 'escrow',
    'onion', 'tor', 'search', 'index', 'links', 'alpha', 'dreadd', 'silk',
    'road', 'card', 'cash', 'pay', 'v3', 'anon', 'secure', 'private'
]

def is_vanity(onion_addr):
    """
    Checks if an onion address looks like a vanity address.
    1. Starts with a known keyword.
    2. Starts with a repeating pattern (e.g., 'aaaaa').
    """
    addr = onion_addr.lower()
    
    # Check for keywords at the start
    for word in VANITY_KEYWORDS:
        if addr.startswith(word):
            return f"Keyword: {word}"
            
    # Check for repeating character patterns (e.g., 'bbb', '222')
    # Finding 4 of the same character in a row at the start is a vanity sign
    match = re.match(r'^([a-z2-7])\1{3,}', addr)
    if match:
        return f"Pattern: {match.group(1)}..."

    return None

def filter_vanity_links(input_file):
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    vanity_results = []
    total_found = 0

    print(f"Scanning {input_file} for Vanity Addresses...")
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        # Find all onion addresses
        onions = set(re.findall(r'([a-z2-7]{16,56})\.onion', content))
        total_found = len(onions)

        for addr in onions:
            reason = is_vanity(addr)
            if reason:
                vanity_results.append((addr, reason))

    # Print Results
    print("\n" + "="*60)
    print(f"VANITY LINK ANALYSIS (Found {len(vanity_results)} out of {total_found})")
    print("="*60)
    
    if not vanity_results:
        print("No vanity addresses detected.")
    else:
        # Sort by the reason for better organization
        for addr, reason in sorted(vanity_results, key=lambda x: x[1]):
            print(f"[{reason: <15}] {addr}.onion")

    print("="*60)

if __name__ == "__main__":
    # Point this to any of your links.txt or discovered_links files
    target_file = "all_links.txt" 
    
    if os.path.exists(target_file):
        filter_vanity_links(target_file)
    else:
        print(f"Please put a file named '{target_file}' in this folder or change the script path.")
