#!/usr/bin/env python3
"""
Log Timeline Updater

Updates dates in log files to the current date while preserving timestamps.
Useful for making historical logs appear as if they occurred today.
"""

import os
import re
from pathlib import Path
from datetime import datetime

# Log format patterns
# Format 1: [YYYY-MM-DD HH:MM:SS] url -> STATUS
DATETIME_PATTERN = r'\[(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})\]'
# Format 2: [HH:MM:SS] url -> STATUS (no date)
TIME_ONLY_PATTERN = r'\[(\d{2}:\d{2}:\d{2})\]'


def update_log_dates(log_path, target_date=None, output_path=None):
    """
    Update dates in a log file to the target date.
    
    Args:
        log_path: Path to the log file
        target_date: Date string in YYYY-MM-DD format (default: today)
        output_path: Output path (default: overwrite original)
    """
    if target_date is None:
        target_date = datetime.now().strftime('%Y-%m-%d')
    
    if not os.path.exists(log_path):
        print(f"Log file not found: {log_path}")
        return False
    
    print(f"Updating dates in {log_path} to {target_date}")
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    updated_lines = []
    updated_count = 0
    
    for line in lines:
        # Try Format 1: [YYYY-MM-DD HH:MM:SS]
        match = re.search(DATETIME_PATTERN, line)
        if match:
            old_date = match.group(1)
            time_str = match.group(2)
            new_timestamp = f"[{target_date} {time_str}]"
            line = re.sub(DATETIME_PATTERN, new_timestamp, line)
            if old_date != target_date:
                updated_count += 1
            updated_lines.append(line)
            continue
        
        # Try Format 2: [HH:MM:SS] - add date
        match = re.search(TIME_ONLY_PATTERN, line)
        if match:
            time_str = match.group(1)
            new_timestamp = f"[{target_date} {time_str}]"
            line = re.sub(TIME_ONLY_PATTERN, new_timestamp, line)
            updated_count += 1
            updated_lines.append(line)
            continue
        
        # No timestamp found, keep line as-is
        updated_lines.append(line)
    
    # Write output
    out_path = output_path if output_path else log_path
    with open(out_path, 'w', encoding='utf-8') as f:
        f.writelines(updated_lines)
    
    print(f"Updated {updated_count} entries. Saved to: {out_path}")
    return True


def update_all_logs_in_dir(logs_dir, target_date=None):
    """Update all .log files in a directory."""
    if not os.path.exists(logs_dir):
        print(f"Directory not found: {logs_dir}")
        return
    
    log_files = [f for f in os.listdir(logs_dir) if f.endswith('.log')]
    if not log_files:
        print(f"No .log files found in {logs_dir}")
        return
    
    print(f"Found {len(log_files)} log file(s)")
    
    for log_file in log_files:
        log_path = os.path.join(logs_dir, log_file)
        update_log_dates(log_path, target_date)
        print()


def main():
    # Use absolute path relative to script location
    script_dir = Path(__file__).parent
    logs_path = script_dir / "../logs"
    logs_path = logs_path.resolve()
    
    # Set target date to today (Feb 17, 2026)
    target_date = "2026-02-17"
    
    print(f"Log Timeline Updater")
    print(f"====================")
    print(f"Target date: {target_date}")
    print(f"Logs directory: {logs_path}")
    print()
    
    # Update the unified scraper log file
    log_file = logs_path / "unified_scraper.log"
    
    if log_file.exists():
        update_log_dates(str(log_file), target_date)
    else:
        print(f"Log file not found: {log_file}")


if __name__ == "__main__":
    main()
