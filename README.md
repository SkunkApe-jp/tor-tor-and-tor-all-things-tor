# Tor Scraper Project

This project contains several Go-based web scrapers designed to work over a Tor proxy.

## Important Note on Executable Location
The Go scrapers in this project (like `unified_scraper.go`) are hardcoded to look for their configuration files (like `targets.yaml` and `scraped_data/`) **two directories up** by default (`../../`). 

**CRITICAL:** If you build the `.exe` file, it **MUST** remain in its original script directory (e.g., `go_scripts/playwright/`) if you run it without flags. If you move the `.exe` to the root folder or a `bin/` folder without specifying the `-targets` and `-output` flags manually, the scraper will fail to find your targets list or create outputs in the wrong place!

---

## 🪟 Windows Build Instructions

1. **Install Go**: If you haven't already, install Go from [go.dev/dl](https://go.dev/dl/).
2. **Build the Scraper**:
   Open PowerShell at the project root (`c:\scraper1`) and run:
   ```powershell
   cd go_scripts\playwright
   go build -o unified_scraper.exe unified_scraper.go
   ```
3. **Install Browser Drivers (Required Once)**:
   The scraper uses Playwright to drive Firefox. You must install the Playwright dependencies:
   ```powershell
   go run github.com/playwright-community/playwright-go/cmd/playwright@latest install --with-deps
   ```
4. **Run the Scraper**:
   To run the newly built executable from its correct location:
   ```powershell
   cd go_scripts\playwright
   .\unified_scraper.exe
   ```

*(Optional)* If you decide you *want* to run the executable from the root folder, you must explicitly pass the paths:
```powershell
.\unified_scraper.exe -targets .\targets.yaml -output .\scraped_data
```

---

## 🐧 Linux / macOS Build Instructions

*(Legacy instructions from `/home/kappa/...`)*

From the project root:

```bash
# Build chromedp scripts
cd go_scripts/chromedp
go build -o main main.go
go build -o index index.go
go build -o failed_scraper failed_scraper.go

# Build playwright scripts
cd ../playwright
go build -o playwright_scraper playwright_scraper.go
go build -o title_scraper title_scraper.go
go build -o link_only_scraper link_only_scraper.go
go build -o unified_scraper unified_scraper.go
```

---

## Credits
Special thanks to the original contributors and developers:
- **Taro** (@taro544)
- **Darkspider**
