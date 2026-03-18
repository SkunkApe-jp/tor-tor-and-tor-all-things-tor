# setup_scraper_win.ps1
# This script builds the Tor Unified Scraper for Windows.

$projectRoot = $PSScriptRoot
$scraperSource = "$projectRoot\go_scripts\playwright\unified_scraper.go"
$outputExe = "$projectRoot\bin\unified_scraper.exe"

# 1. Ensure bin directory exists
if (!(Test-Path "$projectRoot\bin")) {
    New-Item -ItemType Directory -Path "$projectRoot\bin" | Out-Null
    Write-Host "[INFO] Created bin/ directory." -ForegroundColor Cyan
}

# 2. Check for Go Compiler
Write-Host "[CHECK] Checking for Go Compiler..." -ForegroundColor Yellow
$goInstalled = Get-Command go -ErrorAction SilentlyContinue

if (!$goInstalled) {
    Write-Host "[ERROR] Go Compiler NOT found!" -ForegroundColor Red
    Write-Host "To build the scraper for Windows, you need to install Go."
    Write-Host "1. Download it from: https://go.dev/dl/"
    Write-Host "2. Install it and RESTART your terminal/IDE."
    Write-Host "3. Run this script again."
    exit
}

Write-Host "[OK] Go found: $($goInstalled.Definition)" -ForegroundColor Green

# 3. Build the Windows Executable
Write-Host "[BUILD] Building unified_scraper.exe..." -ForegroundColor Yellow
Set-Location $projectRoot
go build -o "$outputExe" "$scraperSource"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[SUCCESS] Scraper built: $outputExe" -ForegroundColor Green
    Write-Host "You can now run it using: .\bin\unified_scraper.exe" -ForegroundColor Gray
} else {
    Write-Host "[FAIL] Build failed. Check errors above." -ForegroundColor Red
}

# 4. Optional Run (uncomment to run immediately after build)
# .\bin\unified_scraper.exe -targets "$projectRoot\targets.yaml" -screenshot=true -output "$projectRoot\scraped_data"
