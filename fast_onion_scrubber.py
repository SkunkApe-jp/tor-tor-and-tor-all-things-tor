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
import signal
import math
import hashlib
import heapq
import base64
try:
    import mmh3
except ImportError:
    mmh3 = None
from urllib.parse import urlparse
from datetime import datetime, timezone
import sys
import struct

# Standard settings for Tor (SOCKS5 proxy via httpx)
TOR_PROXY = "socks5://127.0.0.1:9050"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0"
}


async def init_db(db_path):
    """Initialize the SQLite database schema with extended fields."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA temp_store=MEMORY")
        await db.execute("PRAGMA busy_timeout=5000")
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                run_id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT,
                input_file TEXT,
                input_hash TEXT,
                ports TEXT,
                concurrency INTEGER,
                rps REAL,
                connect_timeout_s REAL,
                read_timeout_s REAL,
                write_timeout_s REAL,
                pool_timeout_s REAL,
                max_retries INTEGER
            )
        """
        )
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sites (
                url TEXT PRIMARY KEY,
                last_run_id INTEGER,
                last_checked_at TEXT,
                last_status INTEGER,
                last_latency_s REAL,
                last_title TEXT,
                last_error_type TEXT,
                last_error_message TEXT,
                last_final_url TEXT,
                last_redirect_chain_len INTEGER,
                last_content_hash TEXT,
                last_server_header TEXT,
                last_powered_by TEXT,
                last_content_type TEXT,
                last_content_length INTEGER,
                last_external_links INTEGER,
                last_internal_links INTEGER,
                last_meta_description TEXT,
                last_meta_keywords TEXT,
                last_cert_subject TEXT,
                last_cert_issuer TEXT,
                last_cert_not_after TEXT,
                last_is_captcha INTEGER,
                last_favicon_hash TEXT,
                last_cms_fingerprint TEXT,
                last_open_ports TEXT
            )
        """)
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS site_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER,
                url TEXT,
                checked_at TEXT,
                port TEXT,
                status INTEGER,
                latency_s REAL,
                title TEXT,
                error_type TEXT,
                error_message TEXT,
                final_url TEXT,
                redirect_chain_len INTEGER,
                content_hash TEXT,
                server_header TEXT,
                powered_by TEXT,
                content_type TEXT,
                content_length INTEGER,
                external_links INTEGER,
                internal_links INTEGER,
                meta_description TEXT,
                meta_keywords TEXT,
                cert_subject TEXT,
                cert_issuer TEXT,
                cert_not_after TEXT,
                is_captcha INTEGER,
                favicon_hash TEXT,
                cms_fingerprint TEXT,
                open_ports TEXT
            )
        """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_site_checks_run_id ON site_checks(run_id)"
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_site_checks_url_checked_at ON site_checks(url, checked_at)"
        )
        
        # safely attempt to add newly added columns for backwards compatibility
        try:
            await db.execute("ALTER TABLE sites ADD COLUMN last_is_captcha INTEGER")
        except:
            pass
        try:
            await db.execute("ALTER TABLE site_checks ADD COLUMN is_captcha INTEGER")
        except:
            pass
        try:
            await db.execute("ALTER TABLE sites ADD COLUMN last_favicon_hash TEXT")
            await db.execute("ALTER TABLE sites ADD COLUMN last_cms_fingerprint TEXT")
            await db.execute("ALTER TABLE site_checks ADD COLUMN favicon_hash TEXT")
            await db.execute("ALTER TABLE site_checks ADD COLUMN cms_fingerprint TEXT")
        except:
            pass
        try:
            await db.execute("ALTER TABLE sites ADD COLUMN last_open_ports TEXT")
            await db.execute("ALTER TABLE site_checks ADD COLUMN open_ports TEXT")
        except:
            pass
            
        await db.commit()


async def get_processed_urls(db, final_statuses):
    """Fetch already processed URLs to support resuming."""
    placeholders = ",".join(["?"] * len(final_statuses))
    query = f"SELECT url FROM sites WHERE last_status IN ({placeholders})"
    async with db.execute(query, tuple(final_statuses)) as cursor:
        rows = await cursor.fetchall()
        return {row[0] for row in rows}


def compute_input_hash(file_path):
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_title(html_content):
    """Robust regex-based title extraction."""
    if not html_content:
        return "No Title Found"
    match = re.search(
        r"<title[^>]*>([^<]+)</title>", html_content, re.IGNORECASE | re.DOTALL
    )
    if match:
        t = html.unescape(match.group(1).strip())
        return re.sub(r"\s+", " ", t)
    return "No Title Found"


def extract_meta_tag(html_content, name):
    """Extract meta tag content by name (description, keywords, etc)."""
    if not html_content:
        return None
    # Try name attribute
    pattern = rf'<meta[^>]+name=["\']?{re.escape(name)}["\']?[^>]+content=["\']([^"\']+)["\']'
    match = re.search(pattern, html_content, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1).strip())
    # Try property attribute (OpenGraph)
    pattern = rf'<meta[^>]+property=["\']?{re.escape(name)}["\']?[^>]+content=["\']([^"\']+)["\']'
    match = re.search(pattern, html_content, re.IGNORECASE)
    if match:
        return html.unescape(match.group(1).strip())
    return None


def extract_links(html_content, base_url):
    """Extract and categorize internal/external links."""
    if not html_content:
        return 0, 0
    
    base_domain = urlparse(base_url).netloc.lower()
    
    # Find all href attributes
    href_pattern = r'href=["\']([^"\']+)["\']'
    matches = re.findall(href_pattern, html_content, re.IGNORECASE)
    
    internal = 0
    external = 0
    
    for href in matches:
        href = href.strip()
        if not href or href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
            continue
        if href.startswith('http'):
            parsed = urlparse(href)
            if parsed.netloc.lower() == base_domain:
                internal += 1
            else:
                external += 1
        else:
            internal += 1
    
    return internal, external


def compute_content_hash(content):
    """Compute SHA256 hash of content for change detection."""
    if not content:
        return None
    return hashlib.sha256(content.encode('utf-8', errors='ignore')).hexdigest()[:32]


def extract_cert_info(response):
    """Extract certificate info from TLS connection if available."""
    cert_info = {"subject": None, "issuer": None, "not_after": None}
    try:
        if hasattr(response, 'extensions') and response.extensions:
            # httpx doesn't expose cert directly, but we can try to get it
            pass
        # Alternative: check if we have transport with ssl context
        if hasattr(response, '_raw_response') and response._raw_response:
            raw = response._raw_response
            if hasattr(raw, 'connection') and raw.connection:
                conn = raw.connection
                if hasattr(conn, 'ssl_object') and conn.ssl_object:
                    ssl_obj = conn.ssl_object
                    if hasattr(ssl_obj, 'getpeercert'):
                        cert = ssl_obj.getpeercert()
                        if cert:
                            cert_info["subject"] = str(cert.get('subject'))
                            cert_info["issuer"] = str(cert.get('issuer'))
                            cert_info["not_after"] = cert.get('notAfter')
    except Exception:
        pass
    return cert_info


def shodan_favicon_hash(data):
    """Compute Shodan-compatible mmh3 hash of favicon."""
    if not mmh3 or not data:
        return None
    try:
        # Shodan encodes as base64 with 76 char line-wrapping
        b64 = base64.encodebytes(data)
        return str(mmh3.hash(b64))
    except Exception:
        return None


def detect_cms(html_content, headers, title):
    """Simple checks for common CMS and panel footprints."""
    if not html_content:
        return None
    html_lower = html_content.lower()
    
    # Check headers
    server = headers.get("server", "").lower()
    powered_by = headers.get("x-powered-by", "").lower()
    if "php/5" in powered_by or "php/7" in powered_by or "php/8" in powered_by:
        pass # just PHP

    if "wordpress" in html_lower or "wp-content" in html_lower or "wp-includes" in html_lower:
        return "WordPress"
    if "phpbb" in html_lower or "style=\"phpbb" in html_lower:
        return "phpBB"
    if "joomla" in html_lower or "jdocs" in html_lower or "joomla!" in html_lower:
        return "Joomla"
    if "vbulletin" in html_lower:
        return "vBulletin"
    if "mybb" in html_lower:
        return "MyBB"
    if "simple machines forum" in html_lower or "smf" in html_lower:
        return "SMF"
    if "drupal.org" in html_lower or "drupal" in html_lower:
        return "Drupal"
    if "magento" in html_lower:
        return "Magento"
    if "mediawiki" in html_lower:
        return "MediaWiki"
    if "laravel" in html_lower:
        return "Laravel"
        
    return None


def detect_captcha(html_content, title):
    """Detect common Captcha or Anti-DDoS screens."""
    html_lower = (html_content or "").lower()
    title_lower = (title or "").lower()
    
    # Common Anti-DDoS / Captcha titles
    captcha_titles = [
        "just a moment...",
        "attention required!",
        "cloudflare",
        "ddos protection",
        "please verify you are a human",
        "security check",
        "anti-ddos",
        "captcha verification",
        "checking your browser",
        "verify yourself"
    ]
    
    for ct in captcha_titles:
        if ct in title_lower:
            return 1
            
    # Common HTML signatures
    captcha_signatures = [
        "g-recaptcha",
        "h-captcha",
        "name=\"captcha\"",
        "id=\"captcha\"",
        "ddos-guard",
        "anti-bot",
        "prove you're human",
        "math captcha",
        "solve the captcha"
    ]
    for sig in captcha_signatures:
        if sig in html_lower:
            return 1
            
    return 0


async def check_port_via_socks(onion_host, target_port, proxy_host="127.0.0.1", proxy_port=9050, timeout=5.0):
    """OPSEC Port Scanner checking arbitrary TCP ports against the onion service via Tor SOCKS5."""
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(proxy_host, proxy_port), timeout=timeout)
        
        # SOCKS5 greeting
        writer.write(b'\x05\x01\x00')
        await writer.drain()
        greeting_resp = await asyncio.wait_for(reader.readexactly(2), timeout=timeout)
        if greeting_resp[0] != 0x05:
            writer.close()
            return False
            
        # SOCKS5 CONNECT
        addr = onion_host.encode('ascii')
        req = b'\x05\x01\x00\x03' + bytes([len(addr)]) + addr + struct.pack('>H', int(target_port))
        writer.write(req)
        await writer.drain()
        
        reply = await asyncio.wait_for(reader.readexactly(4), timeout=timeout)
        success = (reply[1] == 0x00)
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return success
    except Exception:
        return False


class RateLimiter:
    def __init__(self, rps):
        self._rps = float(rps) if rps else 0.0
        self._lock = asyncio.Lock()
        self._tokens = 0.0
        self._last = time.monotonic()

    async def acquire(self):
        if self._rps <= 0:
            return
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self._last = now
                self._tokens = min(self._rps, self._tokens + elapsed * self._rps)
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                need = (1.0 - self._tokens) / self._rps
            await asyncio.sleep(min(need, 0.25))


def make_client(port, headers, limits, timeout):
    transport = httpx.AsyncHTTPTransport(proxy=f"socks5://127.0.0.1:{port}")
    return httpx.AsyncClient(
        transport=transport,
        headers=headers,
        limits=limits,
        timeout=timeout,
        follow_redirects=True,
        verify=False,
    )


def classify_error(exc):
    if isinstance(exc, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.WriteTimeout, httpx.PoolTimeout)):
        return exc.__class__.__name__, str(exc)
    if isinstance(exc, httpx.RemoteProtocolError):
        return exc.__class__.__name__, str(exc)
    if isinstance(exc, httpx.RequestError):
        return exc.__class__.__name__, str(exc)
    return exc.__class__.__name__, str(exc)


def is_transient_status(status_code):
    return status_code in (408, 429, 503, 504) or (500 <= status_code <= 599)


async def db_writer(db, queue, batch_size, flush_interval_s, stop_event):
    pending = []
    last_flush = time.monotonic()
    while True:
        timeout = max(0.0, flush_interval_s - (time.monotonic() - last_flush))
        try:
            item = await asyncio.wait_for(queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            item = None

        if item is None:
            if pending:
                await _flush_db(db, pending)
                pending.clear()
                last_flush = time.monotonic()
            if stop_event.is_set() and queue.empty():
                break
            continue

        pending.append(item)
        if len(pending) >= batch_size:
            await _flush_db(db, pending)
            pending.clear()
            last_flush = time.monotonic()


async def _flush_db(db, items):
    await db.executemany(
        """
        INSERT INTO site_checks (
            run_id, url, checked_at, port, status, latency_s, title, error_type, error_message,
            final_url, redirect_chain_len, content_hash, server_header, powered_by, content_type,
            content_length, external_links, internal_links, meta_description, meta_keywords,
            cert_subject, cert_issuer, cert_not_after, is_captcha, favicon_hash, cms_fingerprint, open_ports
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        [
            (
                i.get("run_id"),
                i.get("url"),
                i.get("checked_at"),
                i.get("port"),
                i.get("status"),
                i.get("latency_s"),
                i.get("title"),
                i.get("error_type"),
                i.get("error_message"),
                i.get("final_url"),
                i.get("redirect_chain_len"),
                i.get("content_hash"),
                i.get("server_header"),
                i.get("powered_by"),
                i.get("content_type"),
                i.get("content_length"),
                i.get("external_links"),
                i.get("internal_links"),
                i.get("meta_description"),
                i.get("meta_keywords"),
                i.get("cert_subject"),
                i.get("cert_issuer"),
                i.get("cert_not_after"),
                i.get("is_captcha", 0),
                i.get("favicon_hash"),
                i.get("cms_fingerprint"),
                i.get("open_ports"),
            )
            for i in items
        ],
    )
    await db.executemany(
        """
        INSERT INTO sites (
            url, last_run_id, last_checked_at, last_status, last_latency_s, last_title,
            last_error_type, last_error_message, last_final_url, last_redirect_chain_len,
            last_content_hash, last_server_header, last_powered_by, last_content_type,
            last_content_length, last_external_links, last_internal_links,
            last_meta_description, last_meta_keywords, last_cert_subject, last_cert_issuer, last_cert_not_after, last_is_captcha, last_favicon_hash, last_cms_fingerprint, last_open_ports
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            last_run_id=excluded.last_run_id,
            last_checked_at=excluded.last_checked_at,
            last_status=excluded.last_status,
            last_latency_s=excluded.last_latency_s,
            last_title=excluded.last_title,
            last_error_type=excluded.last_error_type,
            last_error_message=excluded.last_error_message,
            last_final_url=excluded.last_final_url,
            last_redirect_chain_len=excluded.last_redirect_chain_len,
            last_content_hash=excluded.last_content_hash,
            last_server_header=excluded.last_server_header,
            last_powered_by=excluded.last_powered_by,
            last_content_type=excluded.last_content_type,
            last_content_length=excluded.last_content_length,
            last_external_links=excluded.last_external_links,
            last_internal_links=excluded.last_internal_links,
            last_meta_description=excluded.last_meta_description,
            last_meta_keywords=excluded.last_meta_keywords,
            last_cert_subject=excluded.last_cert_subject,
            last_cert_issuer=excluded.last_cert_issuer,
            last_cert_not_after=excluded.last_cert_not_after,
            last_is_captcha=excluded.last_is_captcha,
            last_favicon_hash=excluded.last_favicon_hash,
            last_cms_fingerprint=excluded.last_cms_fingerprint,
            last_open_ports=excluded.last_open_ports
    """,
        [
            (
                i.get("url"),
                i.get("run_id"),
                i.get("checked_at"),
                i.get("status"),
                i.get("latency_s"),
                i.get("title"),
                i.get("error_type"),
                i.get("error_message"),
                i.get("final_url"),
                i.get("redirect_chain_len"),
                i.get("content_hash"),
                i.get("server_header"),
                i.get("powered_by"),
                i.get("content_type"),
                i.get("content_length"),
                i.get("external_links"),
                i.get("internal_links"),
                i.get("meta_description"),
                i.get("meta_keywords"),
                i.get("cert_subject"),
                i.get("cert_issuer"),
                i.get("cert_not_after"),
                i.get("is_captcha", 0),
                i.get("favicon_hash"),
                i.get("cms_fingerprint"),
                i.get("open_ports"),
            )
            for i in items
        ],
    )
    await db.commit()


async def check_site(url, clients, semaphore, counter, rate_limiter, db_queue, results_queue, run_id, stop_event, max_retries, extra_ports):
    """Worker task for a single onion URL with port rotation."""
    async with semaphore:
        # Avoid hammering Tor too hard at the exact same millisecond
        await asyncio.sleep(random.uniform(0.1, 0.5))

        if stop_event.is_set():
            return

        if not url.startswith("http"):
            url = "http://" + url

        # Select client based on round-robin rotation
        port_index = counter[0] % len(clients)
        client, port = clients[port_index]
        counter[0] += 1

        result = {
            "url": url,
            "port": port,
            "status": 0,
            "title": "Error",
            "latency_s": 0,
            "success": False,
            "is_captcha": 0,
            "favicon_hash": None,
            "cms_fingerprint": None,
            "open_ports": None,
            "error_type": None,
            "error_message": None,
            "final_url": None,
            "redirect_chain_len": 0,
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run_id,
        }

        try:
            while True:
                try:
                    await rate_limiter.acquire()
                    start_time = time.perf_counter()
                    response = await client.get(url)
                    end_time = time.perf_counter()
                    result["latency_s"] = round(end_time - start_time, 2)
                    result["status"] = response.status_code
                    result["final_url"] = str(response.url)
                    if getattr(response, "history", None) is not None:
                        result["redirect_chain_len"] = len(response.history)

                    html_content = response.text
                    result["title"] = extract_title(html_content)
                    result["is_captcha"] = detect_captcha(html_content, result["title"])
                    result["success"] = response.status_code == 200
                    result["cms_fingerprint"] = detect_cms(html_content, response.headers, result["title"])

                    if result["success"]:
                        try:
                            parsed = urlparse(result["final_url"] or url)
                            fav_url = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
                            fav_resp = await client.get(fav_url, timeout=3.0)
                            if fav_resp.status_code == 200 and fav_resp.content:
                                result["favicon_hash"] = shodan_favicon_hash(fav_resp.content)
                        except Exception:
                            pass

                    result["server_header"] = response.headers.get("server")
                    result["powered_by"] = response.headers.get("x-powered-by")
                    ct = response.headers.get("content-type")
                    result["content_type"] = ct.split(";")[0] if ct else None
                    result["content_length"] = len(html_content) if html_content else 0
                    result["content_hash"] = compute_content_hash(html_content)

                    result["meta_description"] = extract_meta_tag(html_content, "description") or extract_meta_tag(
                        html_content, "og:description"
                    )
                    result["meta_keywords"] = extract_meta_tag(html_content, "keywords")

                    internal, external = extract_links(html_content, result["final_url"] or url)
                    result["internal_links"] = internal
                    result["external_links"] = external

                    cert_info = extract_cert_info(response)
                    result["cert_subject"] = cert_info["subject"]
                    result["cert_issuer"] = cert_info["issuer"]
                    result["cert_not_after"] = cert_info["not_after"]

                    if result["status"] and is_transient_status(result["status"]) and attempt < max_retries:
                        backoff = (0.5 * (2 ** attempt)) + random.uniform(0, 0.25)
                        attempt += 1
                        await asyncio.sleep(min(backoff, 10.0))
                        continue
                        
                    # Target OPSEC Port scan
                    if extra_ports:
                        found_ports = []
                        parsed_node = urlparse(result["final_url"] or url).netloc or url.replace('http://', '').replace('https://', '').split('/')[0]
                        for ep in extra_ports:
                            if await check_port_via_socks(parsed_node, ep, proxy_port=int(port), timeout=3.0):
                                found_ports.append(str(ep))
                        result["open_ports"] = ",".join(found_ports) if found_ports else None

                    break
                except Exception as e:
                    et, em = classify_error(e)
                    result["error_type"] = et
                    result["error_message"] = em
                    result["title"] = em
                    if attempt >= max_retries:
                        break
                    if isinstance(e, (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.RemoteProtocolError, httpx.PoolTimeout, httpx.WriteTimeout)):
                        backoff = (0.5 * (2 ** attempt)) + random.uniform(0, 0.25)
                        attempt += 1
                        await asyncio.sleep(min(backoff, 10.0))
                        continue
                    break
        finally:
            await db_queue.put(result)
            await results_queue.put(result)
        return


async def main_async():
    parser = argparse.ArgumentParser(
        description="Fast Async Onion Scrubber (httpx + aiosqlite)"
    )
    parser.add_argument("--input", required=True, help="Input file with onion URLs")
    parser.add_argument("--db", default="onion_results.db", help="SQLite database path")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Max concurrent requests (Tor friendly)",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Skip already successful URLs in DB"
    )
    parser.add_argument(
        "--resume-final",
        default="200,301,302,401,403",
        help="Comma-separated status codes considered final for --resume",
    )
    parser.add_argument(
        "--ports",
        default="9050",
        help="Comma-separated Tor SOCKS ports for batch proxying (e.g. 9050,9051,9052)",
    )
    parser.add_argument(
        "--rps",
        type=float,
        default=0.0,
        help="Global max requests/sec (0 disables)",
    )
    parser.add_argument("--connect-timeout", type=float, default=15.0)
    parser.add_argument("--read-timeout", type=float, default=60.0)
    parser.add_argument("--write-timeout", type=float, default=30.0)
    parser.add_argument("--pool-timeout", type=float, default=30.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--extra-ports", default="22,21,3306,8080,3389", help="Comma-separated OPSEC ports to scan (default: 22,21,3306,8080,3389). Pass empty string to disable.")

    args = parser.parse_args()

    ports = [p.strip() for p in args.ports.split(",")]
    extra_ports = [int(p.strip()) for p in args.extra_ports.split(",") if p.strip().isdigit()]

    if not os.path.exists(args.input):
        print(f"[!] Error: {args.input} not found.")
        return

    # Ensure UTF-8 output for Windows terminals
    if sys.platform == "win32":
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)

    # Load and sanitize URLs
    with open(args.input, "r", encoding="utf-8") as f:
        raw_lines = [
            line.strip() for line in f if line.strip() and not line.startswith("#")
        ]

    onion_pattern = re.compile(r"([a-zA-Z0-9_-]+\.onion)", re.I)
    urls = []
    seen = set()
    for line in raw_lines:
        line = line.strip()
        # Find all onion addresses in the line, not just the first search result
        found_onions = onion_pattern.findall(line)
        for onion in found_onions:
            u = onion.lower()
            if u not in seen:
                urls.append(u)
                seen.add(u)

    if not urls:
        print("[!] No onions found in input.")
        return

    await init_db(args.db)

    timeout = httpx.Timeout(
        connect=args.connect_timeout,
        read=args.read_timeout,
        write=args.write_timeout,
        pool=args.pool_timeout,
    )

    stop_event = asyncio.Event()

    def _handle_stop(*_args):
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, _handle_stop)
        signal.signal(signal.SIGTERM, _handle_stop)
    except Exception:
        pass

    async with aiosqlite.connect(args.db) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA temp_store=MEMORY")
        await db.execute("PRAGMA busy_timeout=5000")

        run_started_at = datetime.now(timezone.utc).isoformat()
        input_hash = compute_input_hash(args.input)
        await db.execute(
            """
            INSERT INTO runs (
                started_at, input_file, input_hash, ports, concurrency, rps,
                connect_timeout_s, read_timeout_s, write_timeout_s, pool_timeout_s, max_retries
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                run_started_at,
                args.input,
                input_hash,
                args.ports,
                args.concurrency,
                args.rps,
                args.connect_timeout,
                args.read_timeout,
                args.write_timeout,
                args.pool_timeout,
                args.max_retries,
            ),
        )
        await db.commit()
        async with db.execute("SELECT last_insert_rowid()") as cursor:
            run_id = (await cursor.fetchone())[0]

        if args.resume:
            final_statuses = [int(x.strip()) for x in args.resume_final.split(",") if x.strip().isdigit()]
            processed = await get_processed_urls(db, final_statuses)
            original_count = len(urls)
            urls = [
                u
                for u in urls
                if (u if u.startswith("http") else "http://" + u) not in processed
            ]
            if len(urls) < original_count:
                print(
                    f"[*] Resuming: Skipping {original_count - len(urls)} already processed sites."
                )

        print(
            f"[*] Starting Async Scrubber | Run: {run_id} | Targets: {len(urls)} | Concurrency: {args.concurrency} | Ports: {args.ports} | RPS: {args.rps}"
        )

        semaphore = asyncio.Semaphore(args.concurrency)
        per_port_conn = max(1, math.ceil(args.concurrency / max(1, len(ports))))
        limits = httpx.Limits(
            max_keepalive_connections=per_port_conn,
            max_connections=per_port_conn,
        )

        clients = []
        for port in ports:
            clients.append((make_client(port, HEADERS, limits, timeout), port))

        db_queue = asyncio.Queue(maxsize=max(1000, args.concurrency * 50))
        results_queue = asyncio.Queue(maxsize=max(1000, args.concurrency * 50))
        rate_limiter = RateLimiter(args.rps)

        async def progress_consumer(total):
            completed = 0
            counts = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "timeouts": 0, "other": 0}
            lat_sum = 0.0
            lat_n = 0
            slowest = []
            while True:
                try:
                    res = await asyncio.wait_for(results_queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    if stop_event.is_set() and results_queue.empty():
                        break
                    if completed >= total and total > 0:
                        break
                    continue

                completed += 1
                status = res.get("status") or 0
                if res.get("error_type") in ("ConnectTimeout", "ReadTimeout", "PoolTimeout", "WriteTimeout"):
                    counts["timeouts"] += 1
                elif 200 <= status <= 299:
                    counts["2xx"] += 1
                elif 300 <= status <= 399:
                    counts["3xx"] += 1
                elif 400 <= status <= 499:
                    counts["4xx"] += 1
                elif 500 <= status <= 599:
                    counts["5xx"] += 1
                else:
                    counts["other"] += 1

                if res.get("latency_s"):
                    lat_sum += float(res["latency_s"])
                    lat_n += 1
                    heapq.heappush(slowest, (float(res["latency_s"]), res.get("url")))
                    if len(slowest) > 10:
                        heapq.heappop(slowest)

                if res.get("is_captcha"):
                    status_icon = "🛡️"
                else:
                    status_icon = "✓" if res.get("success") else "✗"
                latency_str = f"{res['latency_s']}s" if res.get("latency_s") else "N/A"
                desc = res.get("meta_description", "") or ""
                server = res.get("server_header", "") or "Unknown"
                cms = f"[{res['cms_fingerprint']}] " if res.get("cms_fingerprint") else ""
                links = f"L:{res.get('internal_links', 0)}+{res.get('external_links', 0)}"
                captcha_str = " [CAPTCHA]" if res.get("is_captcha") else ""
                ports_str = f" [OPEN:{res.get('open_ports')}]" if res.get("open_ports") else ""
                
                try:
                    print(
                        f" [{completed}/{total}] {status_icon} [{latency_str}] [Port {res.get('port')}] {res.get('url')}{captcha_str}{ports_str} {cms}- {str(res.get('title',''))[:35]} | {server[:15]} | {links} | {desc[:30]}...",
                        flush=True
                    )
                except UnicodeEncodeError:
                    # Fallback for non-UTF8 terminals
                    safe_icon = "C" if res.get("is_captcha") else ("OK" if res.get("success") else "ER")
                    print(
                        f" [{completed}/{total}] {safe_icon} [{latency_str}] [Port {res.get('port')}] {res.get('url')}{captcha_str}{ports_str} {cms}- {str(res.get('title','')).encode('ascii', 'ignore').decode()[:35]}...",
                        flush=True
                    )

            avg_lat = (lat_sum / lat_n) if lat_n else 0.0
            slowest_sorted = sorted(slowest, reverse=True)
            print("\n[=] Summary")
            print(f"  2xx={counts['2xx']} 3xx={counts['3xx']} 4xx={counts['4xx']} 5xx={counts['5xx']} timeouts={counts['timeouts']} other={counts['other']}")
            print(f"  avg_latency={avg_lat:.2f}s")
            if slowest_sorted:
                print("  slowest:")
                for lat, u in slowest_sorted[:5]:
                    print(f"    {lat:.2f}s {u}")

        try:
            start_time = time.time()
            rotation_counter = [0]
            writer_task = asyncio.create_task(
                db_writer(db, db_queue, batch_size=50, flush_interval_s=1.0, stop_event=stop_event)
            )
            progress_task = asyncio.create_task(progress_consumer(len(urls)))

            async with asyncio.TaskGroup() as tg:
                for url in urls:
                    if stop_event.is_set():
                        break
                    tg.create_task(
                        check_site(
                            url,
                            clients,
                            semaphore,
                            rotation_counter,
                            rate_limiter,
                            db_queue,
                            results_queue,
                            run_id,
                            stop_event,
                            args.max_retries,
                            extra_ports,
                        )
                    )

            stop_event.set()

            # Give the progress consumer up to 10s to finish draining
            try:
                await asyncio.wait_for(progress_task, timeout=10.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                progress_task.cancel()

            # Give the db writer up to 5s to flush remaining writes, then kill it
            try:
                await asyncio.wait_for(writer_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                writer_task.cancel()
                try:
                    await writer_task
                except asyncio.CancelledError:
                    pass

            duration = time.time() - start_time
            processed = len(urls)
            print(
                f"\n[✓] Done! Processed {processed} targets in {duration:.2f} seconds ({processed / duration:.2f} targets/sec)."
            )
            print(f"[✓] Data persisted to {args.db}")
        finally:
            for client, _ in clients:
                try:
                    await asyncio.wait_for(client.aclose(), timeout=2.0)
                except Exception:
                    pass


if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[!] Aborted by user.")
