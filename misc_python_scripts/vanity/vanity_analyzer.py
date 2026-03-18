#!/usr/bin/env python3
"""
Unified Vanity Onion Analyzer

Combines all vanity detection methods into one powerful tool:
- Basic keyword detection (v1)
- Dictionary-based intelligence (v2)
- Priority scoring for crawl queue (v3)

Generates both console report and priority crawl queue.
"""

import os
import re
import json
from collections import Counter
from pathlib import Path
from datetime import datetime


# ============================================================
# CONFIGURATION
# ============================================================

# Tier 1: High-value branded keywords (score: 10)
PREMIUM_KEYWORDS = {
    'wiki', 'torch', 'market', 'forum', 'bank', 'mail', 'mixer',
    'silk', 'road', 'alpha', 'omega', 'dreadd', 'gram', 'duck'
}

# Tier 2: Common service keywords (score: 5)
SERVICE_KEYWORDS = {
    'shop', 'store', 'chan', 'chat', 'post', 'news', 'tech',
    'dev', 'code', 'git', 'book', 'link', 'list', 'base', 'data',
    'file', 'box', 'cloud', 'crypt', 'coin', 'bit', 'btc', 'eth',
    'gold', 'silver', 'mix', 'blend', 'hub', 'port', 'gate', 'wall',
    'dark', 'hidden', 'index', 'links', 'secure', 'anon', 'private',
    'safe', 'vault', 'save', 'host', 'node', 'search', 'find', 'seek',
    'cash', 'pay', 'card', 'escrow', 'v3', 'tor', 'onion', 'alpha'
}

# Tier 3: Pattern detection (score: 8)
PATTERN_BONUS = 8

# Tier 4: Numerical prefix (score: 3)
NUMERICAL_BONUS = 3

# Common English words for 4-5 char detection (v2 intelligence)
DICTIONARY_WORDS = {
    'bank', 'shop', 'store', 'market', 'wiki', 'chan', 'mail', 'cash', 'pay',
    'vault', 'save', 'safe', 'host', 'node', 'chat', 'talk', 'post', 'news',
    'tech', 'dev', 'code', 'git', 'book', 'silk', 'road', 'alpha', 'omega',
    'search', 'find', 'seek', 'torch', 'duck', 'gram', 'link', 'list', 'base',
    'data', 'file', 'box', 'cloud', 'crypt', 'coin', 'bit', 'btc', 'eth',
    'gold', 'silver', 'mix', 'blend', 'hub', 'port', 'gate', 'wall', 'dark',
    'farm', 'club', 'zone', 'den', 'lab', 'net', 'web', 'app', 'api'
}


# ============================================================
# DETECTION FUNCTIONS
# ============================================================

def detect_vanity_type(addr):
    """
    Comprehensive vanity detection with type classification.
    Returns dict with detection info or None if not vanity.
    """
    addr_lower = addr.lower()
    result = {
        'is_vanity': False,
        'type': None,
        'detail': None,
        'score': 0,
        'tier': None
    }
    
    # Check 4-5 letter dictionary words first (highest intelligence value)
    prefix_4 = addr_lower[:4]
    prefix_5 = addr_lower[:5]
    
    if prefix_5 in DICTIONARY_WORDS:
        result.update({
            'is_vanity': True,
            'type': 'dictionary_word',
            'detail': f'5-char word: {prefix_5}',
            'score': 15,
            'tier': '🔥 LEGENDARY'
        })
        return result
    
    if prefix_4 in DICTIONARY_WORDS:
        result.update({
            'is_vanity': True,
            'type': 'dictionary_word',
            'detail': f'4-char word: {prefix_4}',
            'score': 12,
            'tier': '💎 EPIC'
        })
        return result
    
    # Check premium keywords
    for word in PREMIUM_KEYWORDS:
        if addr_lower.startswith(word):
            result.update({
                'is_vanity': True,
                'type': 'premium_keyword',
                'detail': f'Premium: {word}',
                'score': 10,
                'tier': '⭐ PREMIUM'
            })
            return result
    
    # Check service keywords
    for word in SERVICE_KEYWORDS:
        if addr_lower.startswith(word):
            result.update({
                'is_vanity': True,
                'type': 'service_keyword',
                'detail': f'Service: {word}',
                'score': 5,
                'tier': '📌 STANDARD'
            })
            return result
    
    # Check repeating patterns (aaaa, 2222, etc.)
    pattern_match = re.match(r'^([a-z2-7])\1{3,}', addr_lower)
    if pattern_match:
        char = pattern_match.group(1)
        result.update({
            'is_vanity': True,
            'type': 'repeat_pattern',
            'detail': f'Repeat: {char}×4+',
            'score': 8,
            'tier': '🔁 PATTERN'
        })
        return result
    
    # Check numerical prefix (5+ base32 digits)
    if re.match(r'^[2-7]{5,}', addr_lower):
        result.update({
            'is_vanity': True,
            'type': 'numerical',
            'detail': 'Numerical prefix',
            'score': 3,
            'tier': '🔢 NUMERIC'
        })
        return result
    
    return None


def calculate_priority_score(addr, mentions=1):
    """
    Calculate priority score for crawl queue.
    Score = (mentions × 2) + vanity_bonus
    """
    vanity_info = detect_vanity_type(addr)
    vanity_bonus = vanity_info['score'] if vanity_info else 0
    return (mentions * 2) + vanity_bonus


# ============================================================
# ANALYSIS FUNCTIONS
# ============================================================

def analyze_file(file_path):
    """Analyze a single file for vanity addresses."""
    results = []
    
    if not os.path.exists(file_path):
        return results
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            onions = set(re.findall(r'([a-z2-7]{16,56})\.onion', content))
            
            for addr in onions:
                vanity_info = detect_vanity_type(addr)
                if vanity_info:
                    results.append({
                        'address': addr,
                        **vanity_info
                    })
    except Exception as e:
        print(f"  Error reading {file_path}: {e}")
    
    return results


def analyze_directory(scraped_data_dir):
    """
    Analyze entire scraped_data directory.
    Returns comprehensive analysis with mention counts.
    """
    all_discovered = []
    scraped_onions = set()
    vanity_results = []
    
    print(f"🔍 Scanning {scraped_data_dir}...")
    
    for root, dirs, files in os.walk(scraped_data_dir):
        # Track scraped onions
        if 'htmls' in dirs:
            scraped_onions.add(os.path.basename(root))
        
        # Collect from link files
        for f in files:
            if f.endswith('_links.txt'):
                file_path = os.path.join(root, f)
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as lf:
                        content = lf.read()
                        found = re.findall(r'([a-z2-7]{16,56})\.onion', content)
                        all_discovered.extend(found)
                except:
                    continue
    
    # Calculate mention frequency
    mention_counts = Counter(all_discovered)
    
    # Analyze each unique onion
    analyzed = set()
    for addr in mention_counts:
        if addr in analyzed:
            continue
        analyzed.add(addr)
        
        vanity_info = detect_vanity_type(addr)
        mentions = mention_counts[addr]
        
        if vanity_info:
            vanity_results.append({
                'address': addr,
                'mentions': mentions,
                'is_scraped': addr in scraped_onions,
                'priority_score': calculate_priority_score(addr, mentions),
                **vanity_info
            })
    
    # Sort by priority score
    vanity_results.sort(key=lambda x: x['priority_score'], reverse=True)
    
    return {
        'vanity_results': vanity_results,
        'total_discovered': len(all_discovered),
        'unique_onions': len(mention_counts),
        'scraped_count': len(scraped_onions),
        'unscraped_count': len(mention_counts) - len(scraped_onions & mention_counts.keys())
    }


# ============================================================
# OUTPUT FUNCTIONS
# ============================================================

def print_console_report(analysis):
    """Print formatted console report."""
    results = analysis['vanity_results']
    
    print("\n" + "="*70)
    print("           🎯 VANITY ONION ANALYSIS REPORT")
    print("="*70)
    
    print(f"\n📊 SUMMARY:")
    print(f"   Total discovered: {analysis['total_discovered']}")
    print(f"   Unique onions: {analysis['unique_onions']}")
    print(f"   Already scraped: {analysis['scraped_count']}")
    print(f"   Vanity detected: {len(results)}")
    
    # Group by tier
    tiers = {}
    for r in results:
        tier = r['tier']
        if tier not in tiers:
            tiers[tier] = []
        tiers[tier].append(r)
    
    tier_order = ['🔥 LEGENDARY', '💎 EPIC', '⭐ PREMIUM', '🔁 PATTERN', '🔢 NUMERIC']
    
    for tier in tier_order:
        if tier in tiers:
            print(f"\n{tier} ({len(tiers[tier])} found):")
            for r in tiers[tier][:10]:  # Show top 10 per tier
                status = "✅" if r['is_scraped'] else "⏳"
                print(f"  {status} [{r['detail']:<20}] {r['address'][:24]}... (×{r['mentions']})")
            if len(tiers[tier]) > 10:
                print(f"  ... and {len(tiers[tier]) - 10} more")
    
    # Show unscraped priority targets
    unscraped = [r for r in results if not r['is_scraped']]
    if unscraped:
        print(f"\n🚀 TOP UNSCRAPED TARGETS (crawl these next):")
        for r in unscraped[:15]:
            print(f"   Score {r['priority_score']:>3} | {r['address'][:24]}... ({r['tier']})")
    
    print("\n" + "="*70)


def save_priority_queue(analysis, output_path):
    """Save priority crawl queue to file."""
    unscraped = [r for r in analysis['vanity_results'] if not r['is_scraped']]
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("# Priority Crawl Queue\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Total targets: {len(unscraped)}\n")
        f.write("# Format: address.onion | Score | Tier | Detail\n")
        f.write("#" + "="*68 + "\n\n")
        
        for r in unscraped:
            f.write(f"{r['address']}.onion | Score: {r['priority_score']} | {r['tier']} | {r['detail']}\n")
    
    print(f"💾 Priority queue saved: {output_path}")
    return output_path


def save_json_report(analysis, output_path):
    """Save full analysis as JSON."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"📄 JSON report saved: {output_path}")
    return output_path


# ============================================================
# MAIN
# ============================================================

def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    scraped_data_path = script_dir / "../scraped_data"
    scraped_data_path = scraped_data_path.resolve()
    
    if not os.path.exists(scraped_data_path):
        print(f"Error: scraped_data directory not found at {scraped_data_path}")
        return
    
    # Run analysis
    analysis = analyze_directory(str(scraped_data_path))
    
    # Print console report
    print_console_report(analysis)
    
    # Save outputs
    queue_path = scraped_data_path / "priority_crawl_queue.txt"
    save_priority_queue(analysis, str(queue_path))
    
    json_path = scraped_data_path / "vanity_analysis.json"
    save_json_report(analysis, str(json_path))
    
    # Summary
    print(f"\n✅ Analysis complete!")
    print(f"   - Console report: (above)")
    print(f"   - Priority queue: {queue_path}")
    print(f"   - JSON report: {json_path}")


if __name__ == "__main__":
    main()
