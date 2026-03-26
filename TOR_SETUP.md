# 🧅 Tor Configuration for High-Performance Scraping

To get the most out of your **Unified Scraper** and **Fast Async Scrubber**, you must optimize your Tor background process (`torrc`) to handle high-concurrency requests and long handshakes.

---

## 🚀 1. How to Enable Batch Proxying (High Throughput)
By default, Tor only opens a single "pipe" on Port 9050. For async scrubbing, you should open multiple independent SOCKS ports. Your scripts will rotate between them to maximize bandwidth and prevent circuit congestion.

### **Modify your `torrc` File:**
Locate your `torrc` file (e.g., `C:\tor-expert-bundle...\Data\torrc`) and add these lines:

```text
# Enable Batch Proxying (Multi-Port rotation)
SocksPort 127.0.0.1:9050
SocksPort 127.0.0.1:9051
SocksPort 127.0.0.1:9052
SocksPort 127.0.0.1:9053
SocksPort 127.0.0.1:9054
```

---

## 🛡️ 2. Critical: Timing & Performance Tweaks
Onion sites are often slow or located on high-latency relays. Use these settings to prevent "TTL Expired" or "General SOCKS failure" errors.

```text
# 1. Match SOCKS handshake timeout to your script's timeout (360s)
SocksTimeout 360

# 2. Increase circuit build time for slow v3 onions
CircuitBuildTimeout 60
LearnCircuitBuildTimeout 0

# 3. Keep circuits alive longer to avoid reconnect overhead
MaxCircuitDirtiness 600
```

---

## 🛠️ 3. Windows Service Fix (Important!)
If Tor is running as a Windows Service, it often ignores the `Data\torrc` file by default. You must explicitly point the service to your configuration file.

**Run this in Administrator PowerShell:**
```powershell
# Update the service binPath to point to your torrc
sc.exe config tor binPath= "`"C:\tor-expert-bundle-windows-x86_64-15.0.7\tor\tor.exe`" --nt-service -f `"C:\tor-expert-bundle-windows-x86_64-15.0.7\Data\torrc`""

# Restart to apply
Restart-Service tor
```

---

## ✅ 4. How to Verify
After restarting the service, verify that all ports are listening:

```powershell
Get-NetTCPConnection -LocalPort 9050, 9051, 9052, 9053, 9054
```
*If you see "Listen" for all five ports, you are ready to scrape!*

---

## 🚀 5. Launch the Scrubber
Run the script with the `--ports` flag to enable rotation:
```powershell
python .\fast_onion_scrubber.py --input targets.txt --ports 9050,9051,9052,9053,9054 --concurrency 30 --resume
```

---
*Created with 🧅 by Antigravity AI*
