# Unified Scraper - Epoch Automation

This README explains how to automate your scraper using Windows Task Scheduler.

## Quick Start

### Prerequisites
- Tor Browser or Tor Expert Bundle running (port 9050)
- Python and required packages installed
- `split_output` folder with target files

### Automated Daily Runs

Use `automate_scraper.ps1` to update targets and run the scraper:

```powershell
python "c:\scraper1\verymoist\moist.py"
& "c:\scraper1\bin\unified_scraper.exe" -targets "c:\scraper1\targets.yaml" -workers 40 -screenshot=true -links=true -titles=true -html=true
```

## Task Scheduler Setup

### GUI Method
1. Press `Win + R`, type `taskschd.msc`, press Enter
2. Click **Create Basic Task...**
3. Name: `Unified Scraper - Epoch Run`
4. Trigger: **Daily** at your preferred time (e.g., 2:00 AM)
5. Action: **Start a program**
   - Program: `powershell.exe`
   - Arguments: `-ExecutionPolicy Bypass -File "c:\scraper1\automate_scraper.ps1"`
   - Start in: `c:\scraper1`

### Command Line Method
```powershell
$Action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-ExecutionPolicy Bypass -File "c:\scraper1\automate_scraper.ps1"' -WorkingDirectory 'c:\scraper1'
$Trigger = New-ScheduledTaskTrigger -DailyAt '2am'
Register-ScheduledTask -Action $Action -Trigger $Trigger -TaskName "UnifiedScraperEpoch" -Description "Daily scraper run following targets epoch"
```

## Key Notes

- **Tor Connection**: The scraper requires Tor on port 9050. Without it, the scraper will abort with `NOT CONNECTED TO TOR!`
- **Epoch**: `moist.py` defaults Day 0 to `2026-02-20`. Change this in `verymoist/moist.py` if needed
- **Stealth Delays**: Default 8-15 min between sites. With 40 workers and 10,000 targets, expect ~40 hours to complete
- **Speed Up**: Add `-inter-delay 1` (minutes) to reduce delays (increases blocking risk)
