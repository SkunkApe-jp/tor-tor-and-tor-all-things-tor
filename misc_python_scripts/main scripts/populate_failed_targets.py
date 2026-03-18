#!/usr/bin/env python3
"""
Utility to extract failed URLs from unified_scraper.log and populate failed_targets.yaml

Logic:
- Only add URLs that NEVER succeeded (all attempts failed)
- If a URL succeeded at least once, don't add it (it's already been crawled)
"""

import re
import yaml
import os
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def analyze_log(log_file="../logs/unified_scraper.log"):
    """
    Analyze log and categorize URLs by success/failure history.
    Returns URLs that have NEVER succeeded.
    """
    url_status = defaultdict(lambda: {'success': 0, 'fail': 0, 'errors': []})

    if not os.path.exists(log_file):
        print(f"Log file {log_file} not found!")
        return []

    with open(log_file, 'r') as f:
        for line in f:
            # Extract URL and status
            # Pattern: [timestamp] URL -> SUCCESS/FAIL (message)
            match = re.search(r'\[.*?\] (http[s]?://[^\s]+) -> (SUCCESS|FAIL) ', line)
            if match:
                url = match.group(1)
                status = match.group(2)
                
                if status == 'SUCCESS':
                    url_status[url]['success'] += 1
                else:
                    url_status[url]['fail'] += 1
                    # Extract error message
                    error_match = re.search(r'-> FAIL \((.+)\)', line)
                    if error_match:
                        url_status[url]['errors'].append(error_match.group(1).strip())

    # Only return URLs that NEVER succeeded (0 successes, 1+ failures)
    never_succeeded = []
    for url, stats in url_status.items():
        if stats['success'] == 0 and stats['fail'] > 0:
            never_succeeded.append({
                'url': url,
                'failures': stats['fail'],
                'last_error': stats['errors'][-1] if stats['errors'] else 'Unknown'
            })

    # Sort by failure count (most failures first)
    never_succeeded.sort(key=lambda x: -x['failures'])

    return never_succeeded

def create_failed_targets_yaml(failed_urls, output_file="../config/failed_targets.yaml"):
    """Create or update failed_targets.yaml with the failed URLs."""
    data = {
        'urls': [item['url'] for item in failed_urls],
        'generated': datetime.now().isoformat(),
        'total': len(failed_urls)
    }

    with open(output_file, 'w') as f:
        yaml.dump(data, f, default_flow_style=False)

    print(f"Created {output_file} with {len(failed_urls)} failed URLs")

def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    logs_path = script_dir / "../logs/unified_scraper.log"
    config_path = script_dir / "../config/failed_targets.yaml"
    
    print("="*60)
    print("POPULATE FAILED TARGETS")
    print("="*60)
    print(f"\nAnalyzing {logs_path}...")
    
    never_succeeded = analyze_log(str(logs_path))

    if not never_succeeded:
        print("\n✅ No URLs found that never succeeded!")
        print("   (All URLs either succeeded at least once or have no failures)")
        return

    print(f"\n📊 Found {len(never_succeeded)} URLs that NEVER succeeded:\n")
    
    for item in never_succeeded[:20]:  # Show top 20
        print(f"  ❌ {item['url']}")
        print(f"     Failures: {item['failures']}x | Last error: {item['last_error'][:50]}...")
    
    if len(never_succeeded) > 20:
        print(f"\n  ... and {len(never_succeeded) - 20} more")

    create_failed_targets_yaml(never_succeeded, str(config_path))

    print("\n" + "="*60)
    print("✅ Failed targets updated!")
    print("="*60)
    print(f"\nOutput: {config_path}")
    print("\nRun failed scraper with:")
    print("  ./failed_scraper")

if __name__ == "__main__":
    main()
