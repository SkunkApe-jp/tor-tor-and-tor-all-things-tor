# Tor Scraper and Visualization Suite

A comprehensive toolset for scraping onion sites via Tor and visualizing the network connections between them.

## Overview

This suite consists of:
- `main.go` - The core Tor scraper that captures screenshots and links from onion sites
- Multiple visualization scripts to explore the scraped data
- A discovery script to find new onion sites from scraped links

## Prerequisites

- Go 1.16+
- Tor service running locally (socks5://127.0.0.1:9050)
- Python 3.6+

## Setup

1. Install Go dependencies:
   ```bash
   go mod tidy
   ```

2. Ensure Tor is running:
   ```bash
   sudo systemctl start tor  # On most Linux systems
   ```

3. Configure your target onion sites in `targets.yaml`:
   ```yaml
   urls:
     - http://exampleonionaddress.onion
   ```

## Usage

### 1. Scraping Onion Sites

Run the main scraper:
```bash
go run main.go
```

This will:
- Connect to Tor
- Scrape all sites listed in `targets.yaml`
- Capture screenshots of each page
- Save HTML content and links
- Organize data by onion address in `scraped_data/`

### 2. Visualizing Networks

Several visualization options are available:

#### Global Visualization
Shows all scraped sites and their connections:
```bash
python3 global_visualization.py
```

#### Grand Visualization
Alternative network view:
```bash
python3 grand_visualization.py
```

#### Individual Site Visualizations
Create visualizations for specific onion sites:
```bash
python3 visualize_onions.py <onion_address>.onion
python3 minimal_visualize_onions.py <onion_address>.onion
```

### 3. Discovering New Sites

Find new onion sites from the links discovered during scraping:
```bash
python3 discover_onions.py
```

This will scan all `_links.txt` files in the scraped data and output:
- `discovered_onions.yaml` - New onion sites in targets.yaml format
- `discovered_onions.txt` - Simple list of new onion sites

Add these to your `targets.yaml` to scrape them in the next run.

## Data Structure

After scraping, the data is organized as:
```
scraped_data/
├── <onion_address_1>/
│   ├── htmls/
│   ├── images/
│   │   ├── <page_path>/
│   │   └── <onion_address_1>.png
│   └── urls/
│       └── <onion_address_1>_links.txt
├── <onion_address_2>/
└── ...
```

## How It Works

### Main Scraper (main.go)
- Connects to onion sites through Tor proxy
- Captures screenshots and HTML content
- Extracts links from each page
- Only follows sub-paths within the same onion site (not root pages of different onion sites)
- Organizes data by onion address

### Visualization Scripts
- Parse the `_links.txt` files to understand site connections
- Create interactive D3 visualizations
- Show screenshots as node images when available
- Support zooming and panning

### Discovery Script
- Scans all `_links.txt` files in scraped data
- Identifies root URLs of other onion sites that weren't processed
- Outputs new targets for future scraping
- Filters out already-scraped and already-targeted sites

## Notes

- The scraper only follows sub-paths within the same onion site by design (to avoid infinite crawling)
- Links to root pages of different onion sites are discovered but not processed
- Use the discovery script to find these unprocessed links and add them to your targets
- Screenshots are saved with the onion address as the filename for root pages, or with the path structure for sub-pages

## Credits

This project incorporates and builds upon the following open-source contributions:

- **Network Visualization & Graph Logic:** Parts of the `build_crawler_graph.py` and graph analysis logic are derived from [DarkSpider](https://github.com/PROxZIMA/DarkSpider.git) by PROxZIMA.

We are grateful to the open-source community for these foundational tools.