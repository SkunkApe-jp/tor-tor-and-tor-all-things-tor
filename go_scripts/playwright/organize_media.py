#!/usr/bin/env python3
"""
Reorganize downloaded media files into subfolders based on original URL paths.
Uses metadata files saved by the updated scraper.
"""

import json
import os
import sys
import shutil
import argparse


def load_metadata(metadata_dir):
    """Load all metadata JSON files."""
    metadata_files = []
    
    if not os.path.exists(metadata_dir):
        print(f"[ERROR] Metadata directory not found: {metadata_dir}")
        return []
    
    for f in os.listdir(metadata_dir):
        if f.endswith("_files.json"):
            metadata_files.append(os.path.join(metadata_dir, f))
    
    all_metadata = []
    for meta_file in metadata_files:
        try:
            with open(meta_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                all_metadata.extend(data)
                print(f"[LOADED] {meta_file} - {len(data)} entries")
        except Exception as e:
            print(f"[WARN] Failed to load {meta_file}: {e}")
    
    return all_metadata


def organize_files(output_dir, category, dry_run=False):
    """Organize files based on metadata."""
    metadata_dir = os.path.join(output_dir, "metadata")
    
    print(f"\n[SCAN] Loading metadata from {metadata_dir}...")
    metadata = load_metadata(metadata_dir)
    
    if not metadata:
        print("[ERROR] No metadata found.")
        return 0, 0
    
    # Filter by category
    if category != "all":
        metadata = [m for m in metadata if m.get("category") == category]
    
    print(f"[FILTER] Working with {len(metadata)} {category} files")
    
    moved = 0
    skipped = 0
    errors = 0
    
    print(f"\n[ORGANIZING]{' (DRY RUN)' if dry_run else ''}")
    print("-" * 60)
    
    for entry in metadata:
        filename = entry.get("filename", "")
        rel_path = entry.get("rel_path", "")
        
        if not filename or not rel_path:
            continue
        
        # Old flat path: category/domain/filename.ext
        parts = rel_path.split(os.sep)
        if len(parts) < 3:
            continue
        
        flat_path = os.path.join(output_dir, parts[0], parts[1], os.path.basename(filename))
        new_path = os.path.join(output_dir, rel_path)
        
        # Check if already organized
        if not os.path.exists(flat_path):
            if os.path.exists(new_path):
                skipped += 1
            continue
        
        # Skip if same location
        if flat_path == new_path:
            skipped += 1
            continue
        
        if not dry_run:
            try:
                os.makedirs(os.path.dirname(new_path), exist_ok=True)
                shutil.move(flat_path, new_path)
                print(f"[MOVED] {os.path.basename(filename)} -> {'/'.join(parts[2:])}")
                moved += 1
            except Exception as e:
                print(f"[ERROR] {e}")
                errors += 1
        else:
            print(f"[WOULD MOVE] {flat_path}\n       -> {new_path}")
            moved += 1
    
    print("-" * 60)
    print(f"\n[SUMMARY] Moved: {moved} | Skipped: {skipped} | Errors: {errors}")
    return moved, skipped


def main():
    parser = argparse.ArgumentParser(description="Organize media files into subfolders")
    parser.add_argument("--output", "-o", required=True, help="Output directory path")
    parser.add_argument("--category", "-c", choices=["images", "documents", "videos", "archives", "audio", "code", "executables", "all"], default="images")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Preview without moving")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.output):
        print(f"[ERROR] Directory not found: {args.output}")
        sys.exit(1)
    
    print("=" * 60)
    print("MEDIA FILE ORGANIZER")
    print("=" * 60)
    print(f"Output: {args.output}")
    print(f"Category: {args.category}")
    
    organize_files(args.output, args.category, args.dry_run)
    
    print("\n" + "=" * 60)
    if args.dry_run:
        print("DRY RUN complete. Remove --dry-run to apply.")
    print("Done!")


if __name__ == "__main__":
    main()
