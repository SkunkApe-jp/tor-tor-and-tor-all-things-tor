#!/usr/bin/env python3
import os
import re
from collections import Counter

# Branded prefixes that indicate a high-value/professional site
VANITY_LABELS = {
    'wiki': 10, 'torch': 10, 'market': 10, 'forum': 10, 'chat': 10, 
    'bank': 10, 'mixer': 10, 'btc': 10, 'coin': 10, 'dark': 5, 
    'hidden': 5, 'index': 5, 'links': 5, 'secure': 5, 'anon': 5
}

def get_onion_priority(addr):
    """Calculate a priority score for an onion address."""
    score = 0
    # Vanity Check
    for word, bonus in VANITY_LABELS.items():
        if addr.lower().startswith(word):
            score += bonus
            break
            
    # Pattern Check (e.g., aaaaa, 2222)
    if re.match(r'^([a-z2-7])\1{3,}', addr.lower()):
        score += 8
        
    return score

def generate_priority_queue(scraped_data_dir):
    all_discovered = []
    scraped_onions = set()
    
    print("🔍 Harvesting all discovered links across the network...")

    for root, dirs, files in os.walk(scraped_data_dir):
        # Keep track of who we already crawled
        if "htmls" in dirs:
            scraped_onions.add(os.path.basename(root))
            
        # Collect links from discovery files
        for f in files:
            if f.endswith('_links.txt'):
                try:
                    with open(os.path.join(root, f), 'r', encoding='utf-8', errors='ignore') as lf:
                        found = re.findall(r'([a-z2-7]{16,56})\.onion', lf.read())
                        all_discovered.extend(found)
                except:
                    continue

    # 1. Calculate "Frequency" (How many times is it mentioned?)
    mention_counts = Counter(all_discovered)
    
    # 2. Filter out what we already have
    unscraped = [addr for addr in mention_counts if addr not in scraped_onions]
    
    # 3. Create Ranked List
    ranked_queue = []
    for addr in unscraped:
        mentions = mention_counts[addr]
        vanity_bonus = get_onion_priority(addr)
        # Total Score = (Mentions * 2) + (Vanity Bonus)
        total_score = (mentions * 2) + vanity_bonus
        
        ranked_queue.append({
            'address': addr,
            'score': total_score,
            'mentions': mentions,
            'is_vanity': vanity_bonus > 0
        })

    # Sort by total score
    ranked_queue.sort(key=lambda x: x['score'], reverse=True)

    # 4. Save to a file for the crawler
    output_path = os.path.join(scraped_data_dir, "priority_crawl_queue.txt")
    with open(output_path, 'w') as out:
        for item in ranked_queue:
            tag = "[VANITY]" if item['is_vanity'] else "[COMMON]"
            out.write(f"{item['address']}.onion | Score: {item['score']} | {tag}\n")

    print(f"\n✅ Created priority queue with {len(ranked_queue)} unique targets.")
    print(f"📍 Location: {output_path}")
    
    # Show Top 10
    print("\n--- TOP 10 PRIORITY TARGETS ---")
    for i, item in enumerate(ranked_queue[:10]):
        print(f"{i+1}. {item['address']}.onion (Score: {item['score']}, Mentions: {item['mentions']})")

if __name__ == "__main__":
    generate_priority_queue("../scraped_data")
