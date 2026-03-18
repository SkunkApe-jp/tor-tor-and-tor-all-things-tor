#!/usr/bin/env python3
"""
Intelligence Vanity Filter (Dictionary Edition)

Identifies high-value targets by checking if the start of an onion 
address contains real English words, indicating a "Proof of Work" creation.
"""

import re
import os

# We can use a simple set of common words to keep it lightweight.
# In a pro version, you could load an entire dictionary file.
COMMON_WORDS = {
    'bank', 'shop', 'store', 'market', 'wiki', 'chan', 'mail', 'cash', 'pay',
    'vault', 'save', 'safe', 'host', 'node', 'chat', 'talk', 'post', 'news',
    'tech', 'dev', 'code', 'git', 'book', 'silk', 'road', 'alpha', 'omega',
    'search', 'find', 'seek', 'torch', 'duck', 'gram', 'link', 'list', 'base',
    'data', 'file', 'box', 'cloud', 'crypt', 'coin', 'bit', 'btc', 'eth',
    'gold', 'silver', 'mix', 'blend', 'hub', 'port', 'gate', 'wall', 'dark'
}

def detect_vanity_intelligence(onion_addr):
    """
    Analyzes the 'DNA' of an onion address for high-effort branding.
    """
    addr = onion_addr.lower()
    
    # 1. Check for 4-letter words at the very start
    # Most vanity addresses aim for 4-6 chars because the math gets too hard after that.
    prefix_4 = addr[:4]
    if prefix_4 in COMMON_WORDS:
        return f"High (4-char word: '{prefix_4}')"
    
    # 2. Check for 5-letter words
    prefix_5 = addr[:5]
    if any(prefix_5.startswith(w) for w in COMMON_WORDS if len(w) >= 5):
        return f"Very High (5-char word: '{prefix_5}')"

    # 3. Repeat Pattern Check (The 'Cheap' Vanity)
    # If someone can't afford a word, they often generate 'aaaa...' or '2222...'
    pattern_match = re.match(r'^([a-z2-7])\1{3,}', addr)
    if pattern_match:
        return f"Pattern (Repeat: {pattern_match.group(1)})"

    # 4. Long Sequence of Numbers
    # Random addresses usually have a mix. 5+ numbers at the start is rare/intentional.
    if re.match(r'^[2-7]{5,}', addr):
        return "Numerical Prefix"

    return None

def process_discovered_links(file_path):
    if not os.path.exists(file_path):
        print("File not found.")
        return

    targets = []
    print(f"--- Analyzing Potential High-Value Targets in {file_path} ---")

    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        # Extract all onions
        onions = set(re.findall(r'([a-z2-7]{16,56})\.onion', f.read()))
        
        for addr in onions:
            status = detect_vanity_intelligence(addr)
            if status:
                targets.append((addr, status))

    # Sort by "High" first
    targets.sort(key=lambda x: x[1], reverse=True)

    for addr, status in targets:
        print(f"[{status:^25}] http://{addr}.onion")

if __name__ == "__main__":
    # Check your discovered_links or any logs you have
    process_discovered_links("all_links.txt")
