# 🧅 Tor Configuration for High-Performance Scraping

To get the most out of your **Unified Scraper** and **Fast Async Scrubber**, you should optimize your Tor background process (`torrc`) to handle multiple parallel connections.

---

## 🚀 1. How to Enable Batch Proxying (High Throughput)
By default, Tor only opens a single "pipe" on Port 9050. To increase speed, you can open multiple independent SOCKS ports. Your scripts will then rotate between them (round-robin) to maximize bandwidth.

### **Modify your `torrc` File:**
Locate your `torrc` file (e.g., in `TorBrowser/Data/Tor/torrc` on Windows or `/etc/tor/torrc` on Linux) and add these lines:

```text
# Enable Batch Proxying (Multi-Port rotation)
SocksPort 9050
SocksPort 9051
SocksPort 9052
SocksPort 9053
SocksPort 9054
```

### **Why this works:**
Each port acts as a separate entry point. When `fast_onion_scrubber.py --ports 9050,9051,9052` runs, it spreads the load across these different ports, effectively bypassing the single-circuit congestion.

---

## 🛡️ 2. Advanced: Circuit Isolation & Performance
To ensure each port uses a **completely different identity/circuit** (better stealth and performance), use the `IsolationDestPort` flag:

```text
# Enhanced isolation for each port
SocksPort 9050 IsolateDestAddr
SocksPort 9051 IsolateDestAddr
SocksPort 9052 IsolateDestAddr
```

### **Other Recommended Settings for Scrapers:**
Add these to your `torrc` to make Tor more responsive for high-volume automated requests:

```text
# Prevent Tor from getting stuck on dead circuits
CircuitBuildTimeout 30
LearnCircuitBuildTimeout 0

# Keep more exit nodes ready for faster initial loads
MaxCircuitDirtiness 60
```

---

## 🛠️ After Modifying:
1.  **Save** the `torrc` file.
2.  **Restart** the Tor Browser or the Tor background service.
3.  **Run the Scrapper:**
    ```powershell
    python .\fast_onion_scrubber.py --input targets.txt --ports 9050,9051,9052,9053,9054
    ```

---
*Created with 🧅 by Antigravity AI*
