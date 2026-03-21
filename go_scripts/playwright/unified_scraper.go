package main

import (
	"bufio"
	"flag"
	"fmt"
	"io"
	"log"
	"math/rand"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/playwright-community/playwright-go"
	"golang.org/x/net/proxy"
)

const (
	TorProxyServer = "socks5://127.0.0.1:9050"
	TorUA          = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0"
)

// Configurable paths (set via flags)
var (
	optTargetsFile  string
	optOutputDir    string
	optLogFile      string
)

// Scraping options
var (
	optScreenshot       bool
	optLinks            bool
	optTitles           bool
	optHTML             bool  // New option: Save HTML content
	optInterSiteDelay   int   // Inter-site delay in minutes (default: 8-15 Gaussian)
	optIntraPageDelay   int   // Intra-page "reading" delay in seconds (default: 60-120)
	optWorkerCount      int   // Number of parallel workers
)


type ScrapedData struct {
	pageTitle   string
	htmlContent string  // New field: Full HTML content
	screenshot  []byte
	links       []string
	titles      map[string]string
}

func init() {
	flag.StringVar(&optTargetsFile, "targets", "../../targets.yaml", "Path to targets file")
	flag.StringVar(&optOutputDir, "output", "../../scraped_data", "Directory to save results")
	flag.StringVar(&optLogFile, "log", "../../logs/unified_scraper.log", "Path to unified log file")

	flag.BoolVar(&optScreenshot, "screenshot", false, "Capture full-page screenshots")
	flag.BoolVar(&optLinks, "links", false, "Extract onion links")
	flag.BoolVar(&optTitles, "titles", false, "Extract links with titles")
	flag.BoolVar(&optHTML, "html", false, "Download and save full HTML source")
	flag.IntVar(&optInterSiteDelay, "inter-delay", 0, "Inter-site delay: 0=Gaussian 8-15min, or set custom mean (min)")
	flag.IntVar(&optIntraPageDelay, "intra-delay", 0, "Intra-page reading delay: 0=60-120sec, or set custom (sec)")
	flag.IntVar(&optWorkerCount, "workers", 40, "Number of parallel workers (default: 40)")
}

func main() {
	flag.Parse()

	// Create output directory if it doesn't exist
	if err := os.MkdirAll(optOutputDir, 0755); err != nil {
		fmt.Printf("[ERROR] Could not create output directory: %v\n", err)
		return
	}

	// Default to all options if none specified
	if !optScreenshot && !optLinks && !optTitles && !optHTML {
		optScreenshot = true
		optLinks = true
		optTitles = true
		optHTML = true
	}

	rand.Seed(time.Now().UnixNano())

	fmt.Println("[CHECK] Verifying Tor connection...")
	if !checkTorConnection() {
		fmt.Println("NOT CONNECTED TO TOR! Aborting.")
		return
	}

	// Set defaults if not specified
	workers := optWorkerCount
	if workers <= 0 {
		workers = 40 // Default
	}

	fmt.Println("[CHECK] Starting unified scraper...")
	fmt.Printf("[CONFIG] Workers: %d | Screenshot: %v | Links: %v | Titles: %v | HTML: %v\n", workers, optScreenshot, optLinks, optTitles, optHTML)
	if optInterSiteDelay == 0 {
		fmt.Println("[STEALTH] Inter-site delay: Gaussian 8-15 min (human-like)")
	} else {
		fmt.Printf("[CONFIG] Inter-site delay: %d±%d min\n", optInterSiteDelay, optInterSiteDelay/2)
	}
	if optIntraPageDelay == 0 {
		fmt.Println("[STEALTH] Intra-page delay: 60-120 sec (reading time)")
	} else {
		fmt.Printf("[CONFIG] Intra-page delay: %d sec\n", optIntraPageDelay)
	}

	pw, err := playwright.Run()
	if err != nil {
		log.Fatalf("could not start playwright: %v", err)
	}
	defer pw.Stop()

	browser, err := pw.Firefox.Launch(playwright.BrowserTypeLaunchOptions{
		Headless: playwright.Bool(true),
		Proxy: &playwright.Proxy{
			Server: TorProxyServer,
		},
		Args: []string{"--proxy-remote-dns"},
	})
	if err != nil {
		log.Fatalf("could not launch firefox: %v", err)
	}
	defer browser.Close()

	targets, err := readTargets(optTargetsFile)
	if err != nil {
		log.Fatalf("could not read targets: %v", err)
	}

	if len(targets) == 0 {
		fmt.Println("No targets found in", optTargetsFile)
		return
	}

	fmt.Printf("[INFO] Loaded %d targets\n", len(targets))

	jobs := make(chan string, len(targets))
	var wg sync.WaitGroup

	for i := 1; i <= workers; i++ {
		wg.Add(1)
		go worker(i, browser, jobs, &wg)
	}

	for _, u := range targets {
		jobs <- u
	}
	close(jobs)
	wg.Wait()

	fmt.Println("\n[DONE] All targets processed!")
}

func worker(id int, browser playwright.Browser, jobs <-chan string, wg *sync.WaitGroup) {
	defer wg.Done()

	for targetURL := range jobs {
		// Inter-site delay with Gaussian distribution (human-like)
		delay := getInterSiteDelay()
		fmt.Printf("\n[THREAD %d] Waiting %v for %s\n", id, delay, targetURL)
		time.Sleep(delay)

		data, err := processURL(browser, targetURL)
		if err != nil {
			fmt.Printf("[ERROR] [%s]: %v\n", targetURL, err)
			appendLog(targetURL, "FAIL", err.Error(), nil)
			continue
		}

		onionAddr := extractOnionAddress(targetURL)

		// Save screenshot
		if optScreenshot && len(data.screenshot) > 0 {
			if err := saveScreenshot(onionAddr, targetURL, data.screenshot); err != nil {
				fmt.Printf("[ERROR] Saving screenshot [%s]: %v\n", targetURL, err)
			} else {
				fmt.Printf("[OK] Screenshot saved: %s\n", onionAddr)
			}
		}

		// Save HTML
		if optHTML && data.htmlContent != "" {
			if err := saveHTML(onionAddr, targetURL, data.htmlContent); err != nil {
				fmt.Printf("[ERROR] Saving HTML [%s]: %v\n", targetURL, err)
			} else {
				fmt.Printf("[OK] HTML saved: %s\n", onionAddr)
			}
		}

		// Save links
		if optLinks && len(data.links) > 0 {
			if err := saveLinks(onionAddr, targetURL, data.links); err != nil {
				fmt.Printf("[ERROR] Saving links [%s]: %v\n", targetURL, err)
			} else {
				fmt.Printf("[OK] Links saved: %s (%d links)\n", onionAddr, len(data.links))
			}
		}

		// Save titles
		if optTitles && len(data.titles) > 0 {
			if err := saveTitles(onionAddr, targetURL, data.titles); err != nil {
				fmt.Printf("[ERROR] Saving titles [%s]: %v\n", targetURL, err)
			} else {
				fmt.Printf("[OK] Titles saved: %s (%d titles)\n", onionAddr, len(data.titles))
			}
		}

		// Save main page title
		if optTitles && data.pageTitle != "" {
			if err := saveMainPageTitle(onionAddr, targetURL, data.pageTitle); err != nil {
				fmt.Printf("[ERROR] Saving main page title [%s]: %v\n", targetURL, err)
			} else {
				fmt.Printf("[OK] Main page title saved: %s\n", onionAddr)
			}
		}

		logMsg := formatResults(data)
		appendLog(targetURL, "SUCCESS", logMsg, data)
	}
}

func processURL(browser playwright.Browser, fullURL string) (*ScrapedData, error) {
	context, err := browser.NewContext(playwright.BrowserNewContextOptions{
		UserAgent: playwright.String(TorUA),
		Viewport:  &playwright.Size{Width: 1400, Height: 900},
		IgnoreHttpsErrors: playwright.Bool(true),
		ExtraHttpHeaders: map[string]string{
			"Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
			"Accept-Language": "en-US,en;q=0.5",
			"Sec-Fetch-Dest":  "document",
			"Sec-Fetch-Mode":  "navigate",
			"Sec-Fetch-Site":  "none",
			"Sec-Fetch-User":  "?1",
		},
	})
	if err != nil {
		return nil, err
	}
	defer context.Close()

	scriptContent := `Object.defineProperty(navigator, 'webdriver', {get: () => undefined})`
	_ = context.AddInitScript(playwright.Script{Content: &scriptContent})

	page, err := context.NewPage()
	if err != nil {
		return nil, err
	}
	page.SetDefaultTimeout(1800000)

	fmt.Printf("[LOAD] %s\n", fullURL)
	if _, err := page.Goto(fullURL); err != nil {
		return nil, err
	}

	// Wait for page render and scroll for lazy-loaded content
	time.Sleep(5 * time.Second)
	_, _ = page.Evaluate(`window.scrollTo(0, document.body.scrollHeight)`)
	time.Sleep(3 * time.Second)

	// Intra-page "reading" delay - simulate human browsing
	readingDelay := getIntraPageDelay()
	fmt.Printf("[READ] Simulating human reading: %v\n", readingDelay)
	time.Sleep(readingDelay)

	data := &ScrapedData{
		links:  []string{},
		titles: make(map[string]string),
	}

	// Get main page title
	pageTitle, _ := page.Title()
	data.pageTitle = pageTitle

	// Capture HTML if enabled
	if optHTML {
		html, err := page.Content()
		if err == nil {
			data.htmlContent = html
		}
	}

	// Capture screenshot if enabled
	if optScreenshot {
		screenshot, err := page.Screenshot(playwright.PageScreenshotOptions{
			FullPage: playwright.Bool(true),
		})
		if err == nil {
			data.screenshot = screenshot
		}
	}

	// Extract links and titles if enabled
	if optLinks || optTitles {
		rawLinks, err := page.Evaluate(`() => Array.from(document.querySelectorAll('a')).map(a => ({
			href: a.href,
			text: a.innerText.trim()
		}))`)
		if err != nil {
			return nil, err
		}

		onionRegex := regexp.MustCompile(`https?://[a-z2-7]{56}\.onion[^\s"']*`)
		seenLinks := make(map[string]bool)

		if linkObjects, ok := rawLinks.([]interface{}); ok {
			for _, obj := range linkObjects {
				entry := obj.(map[string]interface{})
				linkStr := fmt.Sprintf("%v", entry["href"])
				titleStr := strings.TrimSpace(fmt.Sprintf("%v", entry["text"]))

				if onionRegex.MatchString(linkStr) && !seenLinks[linkStr] {
					seenLinks[linkStr] = true
					data.links = append(data.links, linkStr)

					if optTitles {
						if titleStr == "" {
							titleStr = "[No Text]"
						}
						titleStr = strings.ReplaceAll(titleStr, "\n", " ")
						data.titles[linkStr] = titleStr
					}
				}
			}
		}
	}

	return data, nil
}

func saveScreenshot(onionAddr, fullURL string, screenshot []byte) error {
	imgDir := filepath.Join(optOutputDir, onionAddr, "images")
	if err := os.MkdirAll(imgDir, 0755); err != nil {
		return err
	}

	filename := generateFilenameForFile(fullURL)
	imgPath := filepath.Join(imgDir, filename+".png")
	return os.WriteFile(imgPath, screenshot, 0644)
}

func saveLinks(onionAddr, fullURL string, links []string) error {
	if len(links) == 0 {
		return nil
	}

	linkDir := filepath.Join(optOutputDir, onionAddr, "discovered_links")
	if err := os.MkdirAll(linkDir, 0755); err != nil {
		return err
	}

	filename := generateFilenameForFile(fullURL)
	filePath := filepath.Join(linkDir, filename+"_links.txt")
	return os.WriteFile(filePath, []byte(strings.Join(links, "\n")), 0644)
}

func saveTitles(onionAddr, fullURL string, titles map[string]string) error {
	if len(titles) == 0 {
		return nil
	}

	titlesDir := filepath.Join(optOutputDir, onionAddr, "discovered_links")
	if err := os.MkdirAll(titlesDir, 0755); err != nil {
		return err
	}

	filename := generateFilenameForFile(fullURL)
	filePath := filepath.Join(titlesDir, filename+"_titles.txt")

	var lines []string
	for link, title := range titles {
		lines = append(lines, fmt.Sprintf("[%s] -> %s", title, link))
	}

	return os.WriteFile(filePath, []byte(strings.Join(lines, "\n")), 0644)
}


func saveMainPageTitle(onionAddr, fullURL string, pageTitle string) error {
	if pageTitle == "" {
		return nil
	}

	// Create a specific directory for the site identity
	titlesDir := filepath.Join(optOutputDir, onionAddr, "website_identity")
	if err := os.MkdirAll(titlesDir, 0755); err != nil {
		return err
	}

	// Use filename to ensure uniqueness (e.g., index_title.txt vs login_title.txt)
	filename := generateFilenameForFile(fullURL)
	filePath := filepath.Join(titlesDir, filename+"_title.txt")
	
	// Formatting it as [Title] -> URL
	content := fmt.Sprintf("[%s] -> %s\n", pageTitle, fullURL)
	return os.WriteFile(filePath, []byte(content), 0644)
}

func saveHTML(onionAddr, fullURL string, htmlContent string) error {
	htmlDir := filepath.Join(optOutputDir, onionAddr, "htmls")
	if err := os.MkdirAll(htmlDir, 0755); err != nil {
		return err
	}

	filename := generateFilenameForFile(fullURL)
	filePath := filepath.Join(htmlDir, filename+".html")
	return os.WriteFile(filePath, []byte(htmlContent), 0644)
}
func formatResults(data *ScrapedData) string {
	var parts []string
	if len(data.screenshot) > 0 {
		parts = append(parts, fmt.Sprintf("screenshot=%dKB", len(data.screenshot)/1024))
	}
	if len(data.links) > 0 {
		parts = append(parts, fmt.Sprintf("links=%d", len(data.links)))
	}
	if len(data.titles) > 0 {
		parts = append(parts, fmt.Sprintf("titles=%d", len(data.titles)))
	}
	if data.htmlContent != "" {
		parts = append(parts, fmt.Sprintf("html=%dKB", len(data.htmlContent)/1024))
	}
	if len(parts) == 0 {
		return "no data"
	}
	return strings.Join(parts, ", ")
}

// ---------------------------------------------------------
// Helper Functions
// ---------------------------------------------------------

// getInterSiteDelay returns a Gaussian-distributed delay for inter-site waits.
// PRODUCTION MODE: 8-15 minutes (mean=11.5, stdDev=1.75) - stealthy, human-like
func getInterSiteDelay() time.Duration {
	var mean, stdDev float64

	if optInterSiteDelay == 0 {
		// PRODUCTION: Gaussian 8-15 MINUTES
		mean = 11.5  // (8+15)/2
		stdDev = 1.75 // (15-8)/4
	} else {
		// Custom: mean ± 50%
		mean = float64(optInterSiteDelay)
		stdDev = mean / 4.0
	}

	// Generate normal distribution value
	seconds := (rand.NormFloat64() * stdDev) + mean

	// Clamp to minimum (mean - 2*stdDev to avoid negative/very low values)
	minSeconds := mean - 2*stdDev
	if seconds < minSeconds {
		seconds = minSeconds
	}
	if seconds < 1 {
		seconds = 1
	}

	// PRODUCTION: Convert to minutes
	delay := time.Duration(seconds * 60) * time.Second

	fmt.Printf("[STEALTH] Inter-site delay: %v\n", delay)
	return delay
}

// getIntraPageDelay returns a Gaussian-distributed "reading" delay for intra-page waits.
// Default: 60-120 seconds (mean=90, stdDev=15)
// Custom: optIntraPageDelay ± 25%
func getIntraPageDelay() time.Duration {
	var mean, stdDev float64
	
	if optIntraPageDelay == 0 {
		// Stealth default: 60-120 sec reading time
		mean = 90    // (60+120)/2
		stdDev = 15  // (120-60)/4
	} else {
		// Custom: mean ± 25%
		mean = float64(optIntraPageDelay)
		stdDev = mean / 4.0
	}
	
	// Generate normal distribution value
	seconds := (rand.NormFloat64() * stdDev) + mean
	
	// Clamp to minimum
	minSeconds := mean - 2*stdDev
	if seconds < minSeconds {
		seconds = minSeconds
	}
	if seconds < 10 {
		seconds = 10
	}
	
	delay := time.Duration(seconds) * time.Second
	return delay
}

func readTargets(filePath string) ([]string, error) {
	file, err := os.Open(filePath)
	if err != nil {
		return nil, err
	}
	defer file.Close()

	var urls []string
	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "urls:") {
			continue
		}
		line = strings.TrimPrefix(line, "- ")
		if line != "" {
			urls = append(urls, line)
		}
	}
	return urls, scanner.Err()
}

func appendLog(url, status, msg string, data *ScrapedData) {
	logDir := filepath.Dir(optLogFile)
	if err := os.MkdirAll(logDir, 0755); err != nil {
		fmt.Printf("[ERROR] Could not create log directory: %v\n", err)
		return
	}

	f, err := os.OpenFile(optLogFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		fmt.Printf("[ERROR] Could not open log file: %v\n", err)
		return
	}
	defer f.Close()

	// Extract details for the unified log entry
	onionAddr := extractOnionAddress(url)
	hasScreenshot := data != nil && len(data.screenshot) > 0
	linksCount := 0
	titlesCount := 0
	if data != nil {
		linksCount = len(data.links)
		titlesCount = len(data.titles)
	}

	// Create a single, data-rich line
	// Format: [Time] URL | Onion: abc | Status: OK | Screenshot: T | Links: 10 | Titles: 5 | Msg: ...
	logLine := fmt.Sprintf("[%s] %s | Onion: %s | Status: %s | Scrn: %v | Links: %d | Titles: %d | Msg: %s\n",
		time.Now().Format("2006-01-02 15:04:05"),
		url,
		onionAddr,
		status,
		hasScreenshot,
		linksCount,
		titlesCount,
		msg,
	)
	f.WriteString(logLine)
}

func extractOnionAddress(fullURL string) string {
	re := regexp.MustCompile(`([a-z2-7]{54,})\.onion`)
	matches := re.FindStringSubmatch(fullURL)
	if len(matches) > 1 {
		return matches[1]
	}
	return "unknown"
}

func generateFilenameForFile(urlStr string) string {
	u, err := url.Parse(urlStr)
	if err != nil || u.Path == "" || u.Path == "/" {
		return "index"
	}
	safe := strings.Trim(u.Path, "/")
	safe = strings.ReplaceAll(safe, "/", "_")
	if len(safe) > 50 {
		safe = safe[:50]
	}
	return safe
}

func checkTorConnection() bool {
	dialer, err := proxy.SOCKS5("tcp", "127.0.0.1:9050", nil, proxy.Direct)
	if err != nil {
		fmt.Printf("Proxy setup error: %v\n", err)
		return false
	}

	transport := &http.Transport{Dial: dialer.Dial}
	client := &http.Client{Transport: transport, Timeout: 15 * time.Second}
	resp, err := client.Get("https://check.torproject.org")
	if err != nil {
		fmt.Printf("Tor connection error: %v\n", err)
		return false
	}
	defer resp.Body.Close()

	body, _ := io.ReadAll(resp.Body)
	bodyStr := string(body)

	if strings.Contains(bodyStr, "Sorry. You are not using Tor") {
		return false
	}
	return strings.Contains(bodyStr, "Congratulations") || strings.Contains(bodyStr, "successfully")
}
