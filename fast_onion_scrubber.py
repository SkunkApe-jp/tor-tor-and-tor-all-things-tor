#!/usr/bin/env python3
"""
Fast Async Onion Scrubber v2.0
- High-performance asyncio + httpx engine
- SQLite3 persistent storage
- Semaphore-controlled concurrency for Tor stability
"""

import asyncio
import httpx
import aiosqlite
import argparse
import time
import re
import html
import os
import random
from urllib.parse import urlparse
from datetime import datetime

# Standard settings for Tor (SOCKS5 proxy via httpx)
TOR_PROXY = "socks5://127.0.0.1:9050"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0'
}

async def init_db(db_path):
    """Initialize the SQLite database schema."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS sites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                status INTEGER,
                last_checked TIMESTAMP
            )
        ''')
        await db.commit()

async def get_processed_urls(db_path):
    """Fetch already processed URLs to support resuming."""
    async with aiosqlite.connect(db_path) as db:
        async with db.execute('SELECT url FROM sites WHERE status = 200') as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

def extract_title(html_content):
    """Robust regex-based title extraction."""
    if not html_content: return "No Title Found"
    match = re.search(r'<title[^>]*>([^<]+)</title>', html_content, re.IGNORECASE | re.DOTALL)
    if match:
        t = html.unescape(match.group(1).strip())
        return re.sub(r'\s+', ' ', t)
    return "No Title Found"

async def check_site(url, clients, db_path, semaphore, counter):
    """Worker task for a single onion URL with port rotation."""
    async with semaphore:
        # Avoid hammering Tor too hard at the exact same millisecond
        await asyncio.sleep(random.uniform(0.1, 0.5))
        
        if not url.startswith('http'):
            url = 'http://' + url

        # Select client based on round-robin rotation
        port_index = counter[0] % len(clients)
        client, port = clients[port_index]
        counter[0] += 1
            
        result = {
            "url": url,
            "port": port,
            "status": 0,
            "title": "Error",
            "success": False
        }
        
        try:
            # Note: httpx with socks5 proxy
            response = await client.get(url, timeout=360.0, follow_redirects=True)
            result["status"] = response.status_code
            result["title"] = extract_title(response.text)
            result["success"] = (response.status_code == 200)
        except Exception as e:
            result["title"] = str(e)
            
        # Save to Database
        async with aiosqlite.connect(db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO sites (url, title, status, last_checked)
                VALUES (?, ?, ?, ?)
            ''', (url, result["title"], result["status"], datetime.now()))
            await db.commit()
            
        return result

async def main_async():
    parser = argparse.ArgumentParser(description='Fast Async Onion Scrubber (httpx + aiosqlite)')
    parser.add_argument('--input', required=True, help='Input file with onion URLs')
    parser.add_argument('--db', default='onion_results.db', help='SQLite database path')
    parser.add_argument('--concurrency', type=int, default=20, help='Max concurrent requests (Tor friendly)')
    parser.add_argument('--resume', action='store_true', help='Skip already successful URLs in DB')
    parser.add_argument('--ports', default='9050', help='Comma-separated Tor SOCKS ports for batch proxying (e.g. 9050,9051,9052)')
    
    args = parser.parse_args()
    
    ports = [p.strip() for p in args.ports.split(',')]
    
    if not os.path.exists(args.input):
        print(f"[!] Error: {args.input} not found.")
        return

    # Load and sanitize URLs
    with open(args.input, 'r', encoding='utf-8') as f:
        raw_lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    
    onion_pattern = re.compile(r'([a-zA-Z0-9_-]+\.onion)', re.I)
    urls = []
    for line in raw_lines:
        match = onion_pattern.search(line)
        if match:
            urls.append(match.group(1))

    if not urls:
        print("[!] No onions found in input.")
        return

    await init_db(args.db)
    
    if args.resume:
        processed = await get_processed_urls(args.db)
        original_count = len(urls)
        urls = [u for u in urls if (u if u.startswith('http') else 'http://'+u) not in processed]
        if len(urls) < original_count:
            print(f"[*] Resuming: Skipping {original_count - len(urls)} already processed sites.")

    print(f"[*] Starting Async Scrubber | Targets: {len(urls)} | Concurrency: {args.concurrency} | Ports: {args.ports}")
    
    semaphore = asyncio.Semaphore(args.concurrency)
    limits = httpx.Limits(max_keepalive_connections=args.concurrency, max_connections=args.concurrency)
    
    # We create a pool of clients, one for each Tor port
    clients = []
    for port in ports:
        transport = httpx.AsyncHTTPTransport(proxy=f"socks5://127.0.0.1:{port}")
        clients.append((httpx.AsyncClient(transport=transport, headers=HEADERS, limits=limits, verify=False), port))
    
    try:
        start_time = time.time()
        rotation_counter = [0] # List used for mutable closure reference
        
        # Create tasks
        tasks = [check_site(url, clients, args.db, semaphore, rotation_counter) for url in urls]
        
        completed = 0
        total = len(urls)
        
        for coro in asyncio.as_completed(tasks):
            res = await coro
            completed += 1
            status_icon = "✓" if res["success"] else "✗"
            print(f" [{completed}/{total}] {status_icon} [Port {res['port']}] {res['url']} - {res['title'][:55]}")

        duration = time.time() - start_time
        print(f"\n[✓] Done! Processed {total} sites in {duration:.2f} seconds ({total/duration:.2f} sites/sec).")
        print(f"[✓] Data persisted to {args.db}")
    finally:
        # Close all clients
        for client, _ in clients:
            await client.aclose()

if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")
