# Scheduler Script for Unified Scraper
# This script:
# 1. Updates targets.yaml using moist.py (the epoch calculator)
# 2. Runs the unified scraper

$projectRoot = "c:\scraper1"
$moistScript = "$projectRoot\verymoist\moist.py"
$scraperExe = "$projectRoot\bin\unified_scraper.exe"
$targetsFile = "$projectRoot\targets.yaml"
$outputDir = "$projectRoot\scraped_data"
$logFile = "$projectRoot\logs\unified_scraper.log"

# Optional: You can set a custom epoch here (YYYY-MM-DD)
# $epoch = "2026-03-22"
# $moistArgs = "--epoch $epoch"
$moistArgs = ""

Write-Host "--- [$(Get-Date)] Starting Scraper Schedule ---" -ForegroundColor Cyan

# 1. Run moist.py to update targets.yaml
Write-Host "[1/2] Updating targets.yaml..." -ForegroundColor Yellow
python "$moistScript" $moistArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] moist.py failed. Aborting scraper run." -ForegroundColor Red
    exit 1
}

# 2. Run the Unified Scraper
Write-Host "[2/2] Launching Unified Scraper..." -ForegroundColor Yellow
# Adjust workers and scrapers as needed
& "$scraperExe" `
    -targets "$targetsFile" `
    -output "$outputDir" `
    -log "$logFile" `
    -workers 1 `
    -screenshot=true `
    -links=true `
    -titles=true `
    -html=false

Write-Host "--- [$(Get-Date)] Cycle Complete ---" -ForegroundColor Green
