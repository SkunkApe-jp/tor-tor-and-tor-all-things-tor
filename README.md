# Onion Recon & Archiving Suite v2.1

A professional-grade toolkit for large-scale onion discovery and high-fidelity site archiving.

---

## 🧅 1. Unified Scraper (Go + Playwright)
Located in: `go_scripts/playwright/unified_scraper.go`

A heavyweight, high-fidelity archiver that renders sites exactly like the Tor Browser.

### 🚀 Key Features
- **Full Rendering:** Handles JavaScript-only sites, markets, and forums.
- **Visual Evidence:** Automatic full-page screenshots.
- **Site Mirroring:** Recreates the site structure locally (`saved_site`) for offline browsing.

### 🆕 New "God-Tier" Upgrades:
- **Stateful Resuming (`-resume`):** Automatically reads `unified_scraper.log`. If it sees an onion was already successful, it skips it.
- **Recursive Crawling (`-depth X`):** Set `-depth 2` to automatically follow and archive all internal links on a page.
- **Parallel Asset Fetching:** Downloads images and styles up to 10x faster using a concurrent worker pool.
- **Windows MAX_PATH Fix:** Uses shared `_assets/` folders and UNC (`\\?\`) prefixing to bypass the 260-character folder limit.
- **Fast Mode (`-fast`):** Reduces "stealth" delays from 15 minutes down to 10 seconds for easier debugging.

### 🛠️ How to Run:
```powershell
# Fast, shallow run (Single page)
go run .\go_scripts\playwright\unified_scraper.go -fast -targets targets.yaml

# Deep, stateful archive (Crawl all internal links)
go run .\go_scripts\playwright\unified_scraper.go -depth 2 -resume
```

---

## ⚡ 2. Fast Async Scrubber (Python + Httpx)
Located in: `fast_onion_scrubber.py`

A lightweight "Scout" engine designed to check thousands of links in seconds.

### 🚀 Key Features
- **Asyncio Engine:** Rewritten for massive throughput using non-blocking I/O.
- **Low Footprint:** No browser needed—just raw HTTP requests.

### 🆕 New "God-Tier" Upgrades:
- **SQLite3 Integration:** Automatically stores results in a persistent database (`onion_results.db`). Perfect for building historical records.
- **Batch Proxying (`--ports`):** Rotate through multiple Tor instances (e.g., ports 9050, 9051) in round-robin fashion to bypass congestion and rate-limits.
- **Database Resuming (`--resume`):** Skips any URL that is already marked as "Status 200" in your SQLite database.

### 🛠️ How to Run:
```powershell
# Basic run with resume
python .\fast_onion_scrubber.py --input targets.txt --resume

# High-performance Batch Proxying (Load-balance across 3 Tor instances)
python .\fast_onion_scrubber.py --input targets.txt --concurrency 50 --ports 9050,9051,9052
```

---

## 📦 Requirements & Installation
- **Go Scraper:** `go get github.com/playwright-community/playwright-go`
- **Python Scrubber:** `pip install aiosqlite httpx[socks] socksio`
- **Tor:** A running Tor instance on port 9050 (and extra ports if using batch proxying).

---
*Created with 🧅 by Antigravity AI*
