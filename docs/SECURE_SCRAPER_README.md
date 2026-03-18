# Secure Onion Scraper

This script provides privacy-focused methods for scraping onion sites while maintaining anonymity and avoiding browser fingerprinting issues.

## Features

1. **Option 1: Chrome with JavaScript Disabled** - Uses Chrome with JS disabled and proper User-Agent
2. **Option 2: Tor Browser Integration** - Uses actual Tor Browser with proper configuration
3. **Option 4: Requests with Tor Proxy** - Pure HTTP requests without JavaScript execution (most private)

## Installation

Make sure you have Tor running on port 9050 before using this script.

## Usage

```bash
# Method 1: Chrome with JavaScript disabled
python3 secure_onion_scraper.py http://example.onion --method chrome-no-js

# Method 2: Using Tor Browser (requires path to Tor Browser installation)
python3 secure_onion_scraper.py http://example.onion --method tor-browser

# Method 4: Requests with Tor proxy (default, most private)
python3 secure_onion_scraper.py http://example.onion --method requests

# Specify custom output directory
python3 secure_onion_scraper.py http://example.onion --method requests --output-dir ./my_secure_scrapes
```

## Privacy Benefits

- Uses Tor Browser-like User-Agent strings
- Prevents JavaScript execution in most methods
- Maintains proper Tor anonymity
- Follows Tor Project recommendations for privacy

## Important Notes

- Make sure Tor service is running before executing the script
- The "requests" method is the most privacy-preserving as it doesn't execute JavaScript
- For the Tor Browser method, you may need to specify the path to your Tor Browser installation
- Always be mindful of the legal and ethical implications of scraping onion sites