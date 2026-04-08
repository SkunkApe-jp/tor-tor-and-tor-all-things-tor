#!/usr/bin/env python3
"""
Unified Scraper Lite - HTTP + SOCKS5 version
Fast, lightweight alternative to Playwright for directory listings and static content.

Features:
- HTTP requests through Tor SOCKS5 proxy
- HTML parsing with BeautifulSoup
- Recursive subdirectory crawling
- File categorization and download
- Parallel downloads with progress bar
- Resume partial downloads
- Auto-retry failed files
- Full crawl resume (Ctrl+C saves state, resume later)
- Speed limiting (throttle to be polite)
- Pattern exclusions (skip thumbnails, cache, etc.)
- Same folder structure as unified_scraper.go

Requirements:
    pip install requests requests[socks] beautifulsoup4 tqdm
    (fnmatch and json are built-in Python modules)

Usage:
    python unified_scraper_lite.py -targets ../targets.yaml -depth 10 -max-pages 200
    python unified_scraper_lite.py -targets ../targets.yaml -max-file-workers 10 -fast
    python unified_scraper_lite.py -targets ../targets.yaml -speed-limit 500 -exclude '*thumb*' -exclude '/cache/'
    python unified_scraper_lite.py -targets ../targets.yaml -resume (auto-resumes from previous run)
"""

import argparse
import fnmatch
import hashlib
import json
import os
import random
import re
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
from tqdm import tqdm

import requests
from bs4 import BeautifulSoup

# File categories with extensions
FILE_CATEGORIES = {
    "videos": [".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".flv", ".wmv",
               ".mpg", ".mpeg", ".ogv", ".3gp", ".3g2", ".ts", ".m3u8", ".f4v"],
    "documents": [".pdf", ".epub", ".mobi", ".azw", ".azw3", ".djvu", ".djv",
                  ".txt", ".rtf", ".doc", ".docx", ".odt", ".chm", ".cbr", ".cbz",
                  ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".md", ".tex"],
    "archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
                 ".tgz", ".tbz", ".txz", ".lz", ".lzma"],
    "audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus",
               ".aiff", ".au", ".ra", ".ram"],
    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
                ".ico", ".tiff", ".tif", ".raw", ".cr2", ".nef", ".heic"],
    "code": [".html", ".htm", ".css", ".js", ".json", ".xml", ".yaml", ".yml",
              ".py", ".go", ".c", ".cpp", ".h", ".java", ".rb", ".php",
              ".sh", ".bat", ".ps1", ".sql", ".log"],
    "executables": [".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage",
                    ".bin", ".run", ".sh", ".bat"],
}

# Default user agent
TOR_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0"


class FileInfo:
    def __init__(self, url: str, category: str, filename: str):
        self.url = url
        self.category = category
        self.filename = filename


class ScrapedData:
    def __init__(self):
        self.page_title: str = ""
        self.links: List[str] = []
        self.files: List[FileInfo] = []


def detect_category(url: str) -> Optional[str]:
    """Detect file category based on extension."""
    lower_url = url.lower().split("?")[0].split("#")[0]
    for category, extensions in FILE_CATEGORIES.items():
        for ext in extensions:
            if lower_url.endswith(ext):
                return category
    return None


def generate_filename(res_url: str, category: str) -> str:
    """Generate filename preserving URL path structure."""
    parsed = urlparse(res_url)
    path = parsed.path
    
    if not path or path == "/":
        hash_val = hashlib.sha256(res_url.encode()).hexdigest()[:8]
        return f"{hash_val}_file"
    
    # Get directory and filename
    dir_path = os.path.dirname(path)
    base = os.path.basename(path)
    
    if not base or base == "." or base == "/":
        hash_val = hashlib.sha256(res_url.encode()).hexdigest()[:8]
        base = f"{hash_val}_file"
    
    # Clean filename
    invalid_chars = '<>:"/\\|?*%'
    clean = "".join(c if c not in invalid_chars else "_" for c in base)
    clean = clean[:200]  # Limit length
    
    # Clean directory components
    if dir_path and dir_path not in (".", "/"):
        dir_path = dir_path.lstrip("/")
        components = [c for c in dir_path.split("/") if c and c != "."]
        cleaned_components = []
        for comp in components:
            clean_comp = "".join(c if c not in invalid_chars else "_" for c in comp)
            if clean_comp:
                cleaned_components.append(clean_comp)
        
        if cleaned_components:
            return os.path.join(*cleaned_components, clean)
    
    return clean


def normalize_url(url: str) -> str:
    """Strip query params and fragment, ensure trailing slash for directories."""
    if "?" in url:
        url = url.split("?")[0]
    if "#" in url:
        url = url.split("#")[0]
    return url


def extract_domain_for_folder(url: str) -> str:
    """Extract domain name for folder naming."""
    parsed = urlparse(url)
    if parsed.hostname:
        return parsed.hostname.removeprefix("www.")
    # Fallback: try to extract from string
    match = re.search(r'([a-z0-9.-]+\.onion)', url, re.I)
    if match:
        return match.group(1).removesuffix(".onion")
    return url.replace(":", "_").replace("/", "_")


class TorHTTPClient:
    """HTTP client with Tor SOCKS5 proxy support."""
    
    def __init__(self, proxy_port: str = "9050", timeout: int = 30):
        # Use socks5h:// to force remote DNS resolution through Tor
        # This is required for .onion addresses to resolve correctly
        self.proxies = {
            "http": f"socks5h://127.0.0.1:{proxy_port}",
            "https": f"socks5h://127.0.0.1:{proxy_port}",
        }
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": TOR_UA})
    
    def get(self, url: str, stream: bool = False, retries: int = 3) -> Optional[requests.Response]:
        """Make HTTP GET request through Tor with retries."""
        for attempt in range(retries):
            try:
                return self.session.get(
                    url, 
                    proxies=self.proxies, 
                    timeout=self.timeout,
                    stream=stream,
                    allow_redirects=True
                )
            except requests.exceptions.ConnectionError as e:
                if "SOCKS" in str(e) or "getaddrinfo" in str(e):
                    print(f"[WARN] Tor connection error (attempt {attempt+1}/{retries}): {e}")
                    if attempt < retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                        continue
                return None
            except Exception as e:
                print(f"[ERROR] Request failed: {url} - {e}")
                return None
        return None


def process_page(url: str, client: TorHTTPClient, base_path: str = "", stay_under_path: bool = True) -> Optional[ScrapedData]:
    """Process a single page: fetch, parse, extract links and files."""
    print(f"[LOAD] {url}")
    
    response = client.get(url)
    if not response or response.status_code != 200:
        print(f"[WARN] Failed to load {url}")
        return None
    
    content_type = response.headers.get("Content-Type", "").lower()
    
    # If this is a file (not HTML), just return it for download
    if "text/html" not in content_type:
        data = ScrapedData()
        category = detect_category(url)
        if category:
            filename = generate_filename(url, category)
            data.files.append(FileInfo(url, category, filename))
            print(f"[DETECTED] [{category}] {os.path.basename(filename)}")
        return data
    
    # Parse HTML
    soup = BeautifulSoup(response.text, "html.parser")
    data = ScrapedData()
    
    # Get page title
    title_tag = soup.find("title")
    if title_tag:
        data.page_title = title_tag.get_text(strip=True)
    
    # Extract links
    for link in soup.find_all("a", href=True):
        href = link["href"]
        
        # Skip javascript and anchors
        if href.startswith("javascript:") or href.startswith("#"):
            continue
        
        # Resolve relative URL
        absolute_url = urljoin(url, href)
        
        # Skip non-HTTP URLs
        if not absolute_url.startswith(("http://", "https://")):
            continue
        
        normalized = normalize_url(absolute_url)
        data.links.append(normalized)
        
        # Check if it's a file
        category = detect_category(normalized)
        if category:
            filename = generate_filename(normalized, category)
            data.files.append(FileInfo(normalized, category, filename))
            print(f"[FOUND] [{category}] {os.path.basename(filename)}")
    
    return data


def download_file_with_speed_limit(client: TorHTTPClient, file_info: FileInfo, output_dir: str, domain_folder: str, speed_limit_kbps: float = 0, progress_bar=None) -> bool:
    """Download a single file with resume support, speed limiting, and progress tracking."""
    # Create path: output_dir/domain_folder/subpath/filename
    base_dir = os.path.join(output_dir, domain_folder)
    full_path = os.path.join(base_dir, file_info.filename)
    
    # Create directories
    dir_path = os.path.dirname(full_path)
    try:
        os.makedirs(dir_path, exist_ok=True)
    except Exception as e:
        print(f"[WARN] Failed to create directory {dir_path}: {e}")
        return False
    
    # Check if already exists and complete
    if os.path.exists(full_path):
        existing_size = os.path.getsize(full_path)
        if existing_size > 0:
            # Verify it's not a partial download by checking if we can get file size
            try:
                head_response = client.session.head(file_info.url, proxies=client.proxies, timeout=10)
                if head_response.status_code == 200:
                    total_size = int(head_response.headers.get('content-length', 0))
                    if total_size > 0 and existing_size >= total_size:
                        if progress_bar:
                            progress_bar.update(1)
                        return True  # Already complete
            except:
                pass
            if progress_bar:
                progress_bar.update(1)
            return True
    
    # Resume partial download
    resume_pos = 0
    if os.path.exists(full_path):
        resume_pos = os.path.getsize(full_path)
    
    # Download with retry
    headers = {}
    if resume_pos > 0:
        headers['Range'] = f'bytes={resume_pos}-'
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.session.get(
                file_info.url,
                proxies=client.proxies,
                timeout=300,
                stream=True,
                headers=headers
            )
            
            if response.status_code not in (200, 206):
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return False
            
            # Get total size
            total_size = int(response.headers.get('content-length', 0))
            if resume_pos > 0:
                total_size += resume_pos
            
            # Download with optional speed limiting
            mode = 'ab' if resume_pos > 0 else 'wb'
            downloaded = resume_pos
            chunk_size = 8192
            start_time = time.time()
            
            with open(full_path, mode) as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Speed limiting
                        if speed_limit_kbps > 0:
                            elapsed = time.time() - start_time
                            expected_time = downloaded / (speed_limit_kbps * 1024)
                            if elapsed < expected_time:
                                sleep_time = expected_time - elapsed
                                if sleep_time > 0.001:  # Only sleep if meaningful
                                    time.sleep(sleep_time)
            
            if progress_bar:
                progress_bar.update(1)
            return True
            
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            print(f"[ERROR] Failed to download {file_info.url}: {e}")
            return False
    
    return False


def crawl_target(target_url: str, args, client: TorHTTPClient, resume_file: Optional[str] = None) -> None:
    """Crawl a target URL with depth and page limits. Supports resume."""
    parsed = urlparse(target_url)
    base_host = parsed.hostname
    base_path = parsed.path
    
    if base_path and not base_path.endswith("/"):
        base_path += "/"
    
    # Load resume state if exists
    visited: Set[str] = set()
    completed_files: Set[str] = set()
    domain_folder = extract_domain_for_folder(target_url)
    state_file = resume_file or os.path.join(args.output, f".{domain_folder}_crawl_state.json")
    
    if args.resume and os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                state = json.load(f)
                visited = set(state.get('visited', []))
                completed_files = set(state.get('completed_files', []))
                print(f"[RESUME] Loaded state: {len(visited)} pages visited, {len(completed_files)} files completed")
        except Exception as e:
            print(f"[WARN] Failed to load resume state: {e}")
    
    print(f"[DEBUG] Starting crawl for {base_host} with basePath={base_path} depth={args.depth} max-pages={args.max_pages}")
    
    # Tracking
    queue: List[Tuple[str, int]] = [(target_url, 0)]  # (url, depth)
    page_count = len([v for v in visited if not detect_category(v)])  # Approximate
    category_counts: Dict[str, int] = {}
    failed_files: List[FileInfo] = []
    
    def save_state():
        """Save current crawl state to resume later."""
        state = {
            'target_url': target_url,
            'visited': list(visited),
            'completed_files': list(completed_files),
            'timestamp': datetime.now().isoformat(),
            'category_counts': category_counts
        }
        try:
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"[WARN] Failed to save state: {e}")
    
    # Register cleanup handler
    def signal_handler(signum, frame):
        print(f"\n[INTERRUPT] Saving crawl state to {state_file}...")
        save_state()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    while queue and page_count < args.max_pages:
        current_url, current_depth = queue.pop(0)
        
        # Normalize and check visited
        normalized = normalize_url(current_url)
        if normalized in visited:
            continue
        visited.add(normalized)
        
        page_count += 1
        print(f"\n[CRAWL] Depth {current_depth}, Page {page_count}/{args.max_pages}: {current_url}")
        
        # Process page
        data = process_page(current_url, client, base_path, args.stay_under_path)
        if not data:
            save_state()  # Save progress even on failure
            continue
        
        # Filter files by size and exclusions
        files_to_download = []
        for f in data.files:
            # Check exclusion patterns
            skip = False
            for pattern in args.exclude_patterns:
                if pattern in f.url or fnmatch.fnmatch(f.url.lower(), pattern.lower()):
                    print(f"[EXCLUDE] Skipping {f.filename} (matches {pattern})")
                    skip = True
                    break
            if skip:
                continue
            
            # Check if already completed in previous run
            if f.url in completed_files:
                print(f"[SKIP] {f.filename} (completed in previous run)")
                category_counts[f.category] = category_counts.get(f.category, 0) + 1
                continue
            
            files_to_download.append(f)
        
        # Download files in parallel with progress bar and speed limit
        if files_to_download:
            print(f"[DOWNLOAD] {len(files_to_download)} files found, starting parallel download...")
            
            # Create progress bar
            with tqdm(total=len(files_to_download), desc="Downloading", unit="file") as pbar:
                # Use ThreadPoolExecutor for parallel downloads
                max_workers = min(args.max_file_workers, len(files_to_download))
                
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_file = {
                        executor.submit(download_file_with_speed_limit, client, f, args.output, domain_folder, args.speed_limit, pbar): f 
                        for f in files_to_download
                    }
                    
                    for future in as_completed(future_to_file):
                        file_info = future_to_file[future]
                        try:
                            success = future.result()
                            if success:
                                category_counts[file_info.category] = category_counts.get(file_info.category, 0) + 1
                                completed_files.add(file_info.url)
                            else:
                                failed_files.append(file_info)
                        except Exception as e:
                            print(f"[ERROR] Exception downloading {file_info.filename}: {e}")
                            failed_files.append(file_info)
            
            # Retry failed files
            if failed_files:
                print(f"\n[RETRY] {len(failed_files)} files failed, retrying...")
                for file_info in failed_files[:]:
                    if download_file_with_speed_limit(client, file_info, args.output, domain_folder, args.speed_limit):
                        category_counts[file_info.category] = category_counts.get(file_info.category, 0) + 1
                        completed_files.add(file_info.url)
                        failed_files.remove(file_info)
            
            # Final summary
            if category_counts:
                summary = " | ".join(f"{cat}: {cnt}" for cat, cnt in category_counts.items())
                print(f"[SUMMARY] Downloaded: {summary}")
            
            if failed_files:
                print(f"[FAILED] {len(failed_files)} files could not be downloaded:")
                for f in failed_files[:5]:
                    print(f"  - {f.url}")
        
        # Save state after each page
        save_state()
        
        # Queue new links for next depth level
        if current_depth < args.depth - 1:
            for link in data.links:
                link_parsed = urlparse(link)
                
                # Same domain check
                if link_parsed.hostname != base_host:
                    continue
                
                # Stay under path check
                if args.stay_under_path and base_path:
                    link_path = link_parsed.path
                    if not link_path.endswith("/"):
                        link_path += "/"
                    if not link_path.startswith(base_path):
                        print(f"[DEBUG] Rejected (outside path): linkPath={link_path} basePath={base_path}")
                        continue
                
                # Skip file URLs (only crawl directories/pages)
                if detect_category(link):
                    continue
                
                normalized_link = normalize_url(link)
                if normalized_link not in visited:
                    queue.append((link, current_depth + 1))
                    print(f"[QUEUE] Found subdirectory: {normalized_link}")
    
    if page_count >= args.max_pages:
        print(f"[LIMIT] Reached max-pages ({args.max_pages}), stopping crawl")


def load_targets(filename: str) -> List[str]:
    """Load target URLs from file."""
    targets = []
    try:
        with open(filename, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    targets.append(line.removeprefix("- "))
    except FileNotFoundError:
        print(f"[ERROR] Targets file not found: {filename}")
        sys.exit(1)
    return targets


def check_tor_connection(proxy_port: str = "9050") -> bool:
    """Verify Tor connection through SOCKS5."""
    try:
        client = TorHTTPClient(proxy_port, timeout=15)
        response = client.get("https://check.torproject.org")
        if response and response.status_code == 200:
            if "Congratulations" in response.text or "successfully" in response.text:
                return True
    except Exception:
        pass
    return False


def main():
    parser = argparse.ArgumentParser(
        description="Unified Scraper Lite - HTTP + SOCKS5 Tor scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s -targets ../targets.yaml -depth 10 -max-pages 200
    %(prog)s -targets ../targets.yaml -ports 9050,9051,9052 -workers 3 -fast
        """
    )
    
    parser.add_argument("-targets", default="../targets.yaml", help="Path to targets file")
    parser.add_argument("-output", default="../scraped_data", help="Directory to save downloads")
    parser.add_argument("-log", default="../logs/unified_scraper_lite.log", help="Path to log file")
    parser.add_argument("-ports", default="9050", help="Comma-separated Tor SOCKS ports")
    
    parser.add_argument("-workers", type=int, default=1, help="Number of parallel workers")
    parser.add_argument("-depth", type=int, default=1, help="Crawl depth (default: 1)")
    parser.add_argument("-max-pages", type=int, default=200, help="Maximum pages per target (default: 200)")
    
    parser.add_argument("-stay-under-path", action="store_true", default=True, help="Only crawl under starting path")
    parser.add_argument("-no-stay-under-path", dest="stay_under_path", action="store_false", help="Disable path constraint")
    
    parser.add_argument("-fast", action="store_true", help="Fast mode (reduced delays)")
    parser.add_argument("-inter-delay", type=float, default=0, help="Inter-site delay in seconds (0=auto)")
    parser.add_argument("-timeout", type=int, default=30, help="HTTP timeout in seconds (default: 30)")
    
    parser.add_argument("-max-file-workers", type=int, default=5, help="Max parallel file downloads (default: 5)")
    parser.add_argument("-speed-limit", type=float, default=0, help="Speed limit in KB/s per download (0=unlimited)")
    parser.add_argument("-resume", action="store_true", default=True, help="Resume from previous crawl state")
    parser.add_argument("-no-resume", dest="resume", action="store_false", help="Start fresh, ignore previous state")
    parser.add_argument("-exclude", action="append", default=[], help="Exclude pattern (can use multiple times, e.g., -exclude '*thumb*' -exclude '/cache/')")
    
    args = parser.parse_args()
    
    # Store exclude patterns
    args.exclude_patterns = args.exclude
    
    # Create output directory
    os.makedirs(args.output, exist_ok=True)
    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
    
    # Check Tor
    print("[CHECK] Verifying Tor connection...")
    if not check_tor_connection(args.ports.split(",")[0].strip()):
        print("[ERROR] NOT CONNECTED TO TOR! Aborting.")
        sys.exit(1)
    print("[CHECK] Tor connection verified")
    
    # Load targets
    targets = load_targets(args.targets)
    if not targets:
        print("[ERROR] No targets found")
        sys.exit(1)
    
    print(f"[CHECK] Starting Unified Scraper Lite v1.1...")
    print(f"[CONFIG] Workers: {args.workers} | Depth: {args.depth} | Max-pages: {args.max_pages}")
    print(f"[CONFIG] Stay-under-path: {args.stay_under_path} | Resume: {args.resume} | Speed-limit: {args.speed_limit}KB/s")
    print(f"[CONFIG] Excludes: {args.exclude_patterns if args.exclude_patterns else 'none'}")
    print(f"[LOADED] {len(targets)} target(s) to process")
    
    # Parse ports
    ports = [p.strip() for p in args.ports.split(",") if p.strip()]
    if not ports:
        ports = ["9050"]
    
    # Process targets
    if args.workers == 1:
        # Single-threaded
        client = TorHTTPClient(ports[0], args.timeout)
        for target in targets:
            crawl_target(target, args, client)
            # Inter-site delay
            if not args.fast:
                delay = random.gauss(11.5 * 60, 1.75 * 60)  # ~11.5 min mean
                delay = max(60, delay)  # Minimum 1 min
            else:
                delay = random.uniform(5, 15)
            print(f"\n[SLEEP] Inter-site delay: {delay:.0f}s")
            time.sleep(delay)
    else:
        # Multi-threaded with port rotation
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            future_to_target = {}
            for i, target in enumerate(targets):
                port = ports[i % len(ports)]
                client = TorHTTPClient(port, args.timeout)
                future = executor.submit(crawl_target, target, args, client)
                future_to_target[future] = target
            
            for future in as_completed(future_to_target):
                target = future_to_target[future]
                try:
                    future.result()
                except Exception as e:
                    print(f"[ERROR] Failed to process {target}: {e}")
    
    print("\n[DONE] All targets processed!")


if __name__ == "__main__":
    main()
