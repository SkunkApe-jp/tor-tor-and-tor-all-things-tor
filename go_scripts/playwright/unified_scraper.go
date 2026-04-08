package main

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
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
	"runtime"
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
	optTargetsFile string
	optOutputDir   string
	optLogFile     string
	optPorts       string // Comma-separated Tor SOCKS ports
)

// Scraping options
var (
	optScreenshot     bool
	optLinks          bool
	optTitles         bool
	optSaveClearweb   bool
	optResume         bool
	optCrossOrigin    bool
	optNoJS           bool
	optEnableJS       bool
	optHTML           bool // Save raw HTML
	optDownloadFiles  bool // Download categorized files
	optInterSiteDelay int  // Inter-site delay in minutes (default: 8-15 Gaussian)
	optIntraPageDelay int  // Intra-page "reading" delay in seconds (default: 60-120)
	optWorkerCount    int  // Number of parallel workers
	optFastMode       bool // Fast mode: reduce all stealth delays (inter-site to 5-15s, intra-page to 5-10s)
	optDepth          int  // Scrape depth (default 1)
	optPageLoadWait   int  // Post-Goto render wait in seconds (default: 45s, 8s in fast mode)
	optStayUnderPath  bool // Only crawl URLs under the starting path
	optMaxPages       int  // Maximum pages to crawl per target
)

var fileCategories = map[string][]string{
	"videos": {
		".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".flv", ".wmv",
		".mpg", ".mpeg", ".ogv", ".3gp", ".3g2", ".ts", ".m3u8", ".f4v",
	},
	"documents": {
		".pdf", ".epub", ".mobi", ".azw", ".azw3", ".djvu", ".djv",
		".txt", ".rtf", ".doc", ".docx", ".odt", ".chm", ".cbr", ".cbz",
		".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".md", ".tex",
	},
	"archives": {
		".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso",
		".tgz", ".tbz", ".txz", ".lz", ".lzma",
	},
	"audio": {
		".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma", ".opus",
		".aiff", ".au", ".ra", ".ram",
	},
	"images": {
		".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
		".ico", ".tiff", ".tif", ".raw", ".cr2", ".nef", ".heic",
	},
	"code": {
		".css", ".js", ".json", ".xml", ".yaml", ".yml",
		".py", ".go", ".c", ".cpp", ".h", ".java", ".rb", ".php",
		".sh", ".bat", ".ps1", ".sql", ".log",
	},
	"executables": {
		".exe", ".msi", ".dmg", ".pkg", ".deb", ".rpm", ".appimage",
		".bin", ".run",
	},
}

type FileInfo struct {
	URL      string
	Category string
	Filename string
}

type ScrapedData struct {
	pageTitle     string
	htmlContent   string // Raw HTML
	screenshot    []byte
	links         []string
	clearwebLinks []string // Non-onion links
	titles        map[string]string
	files         []FileInfo // Files to download
}

func init() {
	flag.StringVar(&optTargetsFile, "targets", "../targets.yaml", "Path to targets file")
	flag.StringVar(&optOutputDir, "output", "../scraped_data", "Directory to save results")
	flag.StringVar(&optLogFile, "log", "../logs/unified_scraper.log", "Path to unified log file")
	flag.StringVar(&optPorts, "ports", "9050", "Comma-separated Tor SOCKS ports (e.g. 9050,9051,9052)")

	flag.BoolVar(&optScreenshot, "screenshot", true, "Capture full-page screenshots")
	flag.BoolVar(&optLinks, "links", true, "Extract onion links")
	flag.BoolVar(&optTitles, "titles", true, "Extract links with titles")
	flag.BoolVar(&optHTML, "html", true, "Download and save full HTML source")
	flag.BoolVar(&optDownloadFiles, "files", true, "Download categorized files (images, videos, etc.)")
	flag.IntVar(&optInterSiteDelay, "inter-delay", 0, "Inter-site delay: 0=Gaussian 8-15min, or set custom mean (min)")
	flag.IntVar(&optIntraPageDelay, "intra-delay", 0, "Intra-page reading delay: 0=60-120sec, or set custom (sec)")
	flag.IntVar(&optWorkerCount, "workers", 1, "Number of parallel workers (default: 1)")
	flag.BoolVar(&optFastMode, "fast", false, "Fast mode: reduce all stealth delays (inter-site to 5-15s, intra-page to 5-10s)")
	flag.IntVar(&optDepth, "depth", 1, "Outbound crawl depth: 1=single site only (subdirs auto-crawled), 2=1 hop to other onions, etc.")
	flag.IntVar(&optPageLoadWait, "page-load-wait", 0, "Seconds to wait after page load for JS render (0=auto: 45s normal, 8s fast)")
	flag.BoolVar(&optStayUnderPath, "stay-under-path", true, "Only crawl URLs under the starting path")
	flag.IntVar(&optMaxPages, "max-pages", 200, "Maximum pages to crawl per target")
	flag.BoolVar(&optSaveClearweb, "clearweb", true, "Save discovered clearweb (non-onion) links")
	flag.BoolVar(&optResume, "resume", false, "Resume from log (skip already successful onions)")
	flag.BoolVar(&optCrossOrigin, "cross-origin", true, "Save cross-origin files from external domains")
	flag.BoolVar(&optNoJS, "no-js", true, "Disable JavaScript execution (default: true for safety/speed)")
	flag.BoolVar(&optEnableJS, "js", false, "Enable JavaScript execution if needed for dynamic sites")
}

func main() {
	flag.Parse()

	// Parse ports
	ports := parsePorts(optPorts)
	if len(ports) == 0 {
		ports = []string{"9050"}
	}

	// Skip category subdirectory creation - files go directly under domain folders
	// Subfolders are created per URL path as needed during download

	fmt.Println("[CHECK] Verifying Tor connection...")
	if !checkTorConnection() {
		fmt.Println("NOT CONNECTED TO TOR! Aborting.")
		return
	}

	// Set defaults if not specified
	workers := optWorkerCount
	if workers <= 0 {
		workers = 10
	}

	fmt.Println("[CHECK] Starting unified scraper v2.0 (Hybrid All-in-One)...")
	fmt.Printf("[CONFIG] Workers: %d | Ports: %v | Screenshot: %v | Links: %v | Files: %v\n", workers, ports, optScreenshot, optLinks, optDownloadFiles)

	targets, err := readTargets(optTargetsFile)
	if err != nil {
		log.Fatalf("could not read targets: %v", err)
	}

	if len(targets) == 0 {
		fmt.Println("No targets found in", optTargetsFile)
		return
	}

	fmt.Printf("[INFO] Loaded %d targets\n", len(targets))

	// Resuming logic: Read already processed sites from log
	processedOnions := make(map[string]bool)
	if optResume {
		if file, err := os.Open(optLogFile); err == nil {
			scanner := bufio.NewScanner(file)
			for scanner.Scan() {
				line := scanner.Text()
				if strings.Contains(line, "Status: SUCCESS") {
					onion := extractOnionAddress(line)
					if onion != "unknown" {
						processedOnions[onion] = true
					}
				}
			}
			file.Close()
			if len(processedOnions) > 0 {
				fmt.Printf("[RESUME] Skipping %d already processed onion identities\n", len(processedOnions))
			}
		}
	}

	jobQueue := make(chan ScrapingJob, 5000)
	var workerWg sync.WaitGroup
	var taskWg sync.WaitGroup

	// Rotation counter for port round-robin
	portCounter := &PortCounter{}

	for i := 1; i <= workers; i++ {
		workerWg.Add(1)
		go worker(i, jobQueue, &workerWg, &taskWg, ports, portCounter)
	}

	for _, u := range targets {
		onion := extractOnionAddress(u)
		if optResume && processedOnions[onion] {
			continue
		}
		taskWg.Add(1)
		jobQueue <- ScrapingJob{URL: u, Depth: 1}
	}

	// Dynamic wait: Close jobQueue only when all tasks (including discovered ones) are done
	go func() {
		taskWg.Wait()
		close(jobQueue)
	}()

	workerWg.Wait()

	fmt.Println("\n[DONE] All targets processed!")
}

type ScrapingJob struct {
	URL   string
	Depth int
}
type PortCounter struct {
	mu    sync.Mutex
	count int
}

func (pc *PortCounter) Next(total int) int {
	pc.mu.Lock()
	defer pc.mu.Unlock()
	idx := pc.count % total
	pc.count++
	return idx
}

func parsePorts(portsStr string) []string {
	parts := strings.Split(portsStr, ",")
	var ports []string
	for _, p := range parts {
		p = strings.TrimSpace(p)
		if p != "" {
			ports = append(ports, p)
		}
	}
	return ports
}

var (
	seenURLs = make(map[string]bool)
	seenMu   sync.Mutex
)

func worker(id int, jobs chan ScrapingJob, workerWg *sync.WaitGroup, taskWg *sync.WaitGroup, ports []string, portCounter *PortCounter) {
	defer workerWg.Done()

	pw, err := playwright.Run()
	if err != nil {
		fmt.Printf("[THREAD %d] Could not start playwright: %v\n", id, err)
		return
	}
	defer pw.Stop()

	// Create one browser instance per worker
	browser, err := pw.Firefox.Launch(playwright.BrowserTypeLaunchOptions{
		Headless: playwright.Bool(true),
		Args:     []string{"--proxy-remote-dns"},
	})
	if err != nil {
		fmt.Printf("[THREAD %d] Could not launch firefox: %v\n", id, err)
		return
	}
	defer browser.Close()

	// Track base paths and page counts per target domain
	basePaths := make(map[string]string)
	pageCounts := make(map[string]int)
	basePathMu := sync.Mutex{}

	for job := range jobs {
		targetURL := job.URL
		currentDepth := job.Depth

		if !strings.HasPrefix(targetURL, "http://") && !strings.HasPrefix(targetURL, "https://") && !strings.Contains(targetURL, ".onion") {
			targetURL = "https://" + targetURL
		}

		// Normalize URL for duplicate checking (strip query params and fragment)
		normalizedURL := targetURL
		if idx := strings.Index(normalizedURL, "?"); idx != -1 {
			normalizedURL = normalizedURL[:idx]
		}
		if idx := strings.Index(normalizedURL, "#"); idx != -1 {
			normalizedURL = normalizedURL[:idx]
		}
		// Ensure trailing / for directory URLs
		if strings.HasSuffix(targetURL, "/") && !strings.HasSuffix(normalizedURL, "/") {
			normalizedURL = normalizedURL + "/"
		}

		seenMu.Lock()
		if seenURLs[normalizedURL] {
			seenMu.Unlock()
			taskWg.Done()
			continue
		}
		seenURLs[normalizedURL] = true
		seenMu.Unlock()

		// Set basePath for new targets
		targetParsed, _ := url.Parse(targetURL)
		domainKey := ""
		if targetParsed != nil {
			domainKey = targetParsed.Host
		}
		basePathMu.Lock()
		if domainKey != "" && basePaths[domainKey] == "" {
			basePath := targetParsed.Path
			if basePath != "" && !strings.HasSuffix(basePath, "/") {
				basePath = basePath + "/"
			}
			basePaths[domainKey] = basePath
			pageCounts[domainKey] = 0
			fmt.Printf("[DEBUG] Starting crawl for %s with basePath=%s depth=%d max-pages=%d\n", domainKey, basePath, optDepth, optMaxPages)
		}
		// Check max pages limit
		if domainKey != "" && pageCounts[domainKey] >= optMaxPages {
			fmt.Printf("[LIMIT] Reached max-pages (%d) for %s, skipping %s\n", optMaxPages, domainKey, targetURL)
			basePathMu.Unlock()
			taskWg.Done()
			continue
		}
		pageCounts[domainKey]++
		currentPageCount := pageCounts[domainKey]
		basePath := basePaths[domainKey]
		basePathMu.Unlock()

		portIdx := portCounter.Next(len(ports))
		selectedPort := ports[portIdx]
		proxyServer := fmt.Sprintf("socks5://127.0.0.1:%s", selectedPort)

		delay := getInterSiteDelay()
		fmt.Printf("\n[THREAD %d] (Depth %d, Page %d/%d) [Port %s] Waiting %v for %s\n", id, currentDepth, currentPageCount, optMaxPages, selectedPort, delay, targetURL)
		time.Sleep(delay)

		data, err := processURL(browser, targetURL, proxyServer)
		if err != nil {
			fmt.Printf("[ERROR] [%s]: %v\n", targetURL, err)
			appendLog(targetURL, "FAIL", err.Error(), nil)
			taskWg.Done()
			continue
		}

		onionAddr := extractOnionAddress(targetURL)

		// Dive deeper (recursive crawl)
		// Separate same-domain (subdirectory) crawling from outbound (cross-domain) crawling
		if len(data.links) > 0 {
			addedSameDomain := 0
			addedCrossDomain := 0
			for _, link := range data.links {
				linkParsed, err := url.Parse(link)
				if err != nil {
					continue
				}

				// Normalize link URL
				normalizedLink := link
				if idx := strings.Index(normalizedLink, "?"); idx != -1 {
					normalizedLink = normalizedLink[:idx]
				}
				if idx := strings.Index(normalizedLink, "#"); idx != -1 {
					normalizedLink = normalizedLink[:idx]
				}
				if strings.HasSuffix(link, "/") && !strings.HasSuffix(normalizedLink, "/") {
					normalizedLink = normalizedLink + "/"
				}

				if linkParsed.Host == targetParsed.Host && linkParsed.Host != "" {
					// Same domain - check path constraint
					lowerURL := strings.ToLower(normalizedLink)
					if detectCategory(lowerURL) != "" {
						continue // Skip file URLs
					}

					// Check stay-under-path constraint
					if optStayUnderPath && basePath != "" {
						linkPath := linkParsed.Path
						if !strings.HasSuffix(linkPath, "/") {
							linkPath = linkPath + "/"
						}
						if !strings.HasPrefix(linkPath, basePath) {
							fmt.Printf("[DEBUG] Rejected (outside path): linkPath=%s basePath=%s\n", linkPath, basePath)
							continue
						}
					}

					seenMu.Lock()
					alreadySeen := seenURLs[normalizedLink]
					if !alreadySeen {
						addedSameDomain++
						taskWg.Add(1)
						go func(l string, d int) {
							jobs <- ScrapingJob{URL: l, Depth: d}
						}(normalizedLink, currentDepth)
					}
					seenMu.Unlock()
				} else if currentDepth < optDepth {
					// Cross domain - only follow if within depth limit
					if linkParsed.Host == "" {
						continue
					}
					lowerURL := strings.ToLower(normalizedLink)
					if detectCategory(lowerURL) != "" {
						continue // Skip file URLs
					}

					seenMu.Lock()
					alreadySeen := seenURLs[normalizedLink]
					if !alreadySeen {
						addedCrossDomain++
						taskWg.Add(1)
						go func(l string, d int) {
							jobs <- ScrapingJob{URL: l, Depth: d}
						}(normalizedLink, currentDepth+1)
					}
					seenMu.Unlock()
				}
			}
			if addedSameDomain > 0 || addedCrossDomain > 0 {
				fmt.Printf("[CRAWL] Same-domain: %d | Cross-domain (depth %d/%d): %d on %s\n", 
					addedSameDomain, currentDepth, optDepth, addedCrossDomain, onionAddr)
			}
		}

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
			}
		}

		// Save titles
		if optTitles && len(data.titles) > 0 {
			if err := saveTitles(onionAddr, targetURL, data.titles); err != nil {
				fmt.Printf("[ERROR] Saving titles [%s]: %v\n", targetURL, err)
			}
		}

		// Save main page title
		if optTitles && data.pageTitle != "" {
			saveMainPageTitle(onionAddr, targetURL, data.pageTitle)
		}

		// Save categorized files (the All-in-One logic)
		if optDownloadFiles && len(data.files) > 0 {
			err := downloadAllFiles(onionAddr, data, proxyServer)
			if err != nil {
				fmt.Printf("[ERROR] Failed to download files from %s: %v\n", onionAddr, err)
			} else {
				fmt.Printf("[OK] Categorized files processed for %s\n", onionAddr)
			}
		}

		logMsg := formatResults(data)
		appendLog(targetURL, "SUCCESS", logMsg, data)
		taskWg.Done()
	}
}

func processURL(browser playwright.Browser, fullURL string, proxyServer string) (*ScrapedData, error) {
	context, err := browser.NewContext(playwright.BrowserNewContextOptions{
		UserAgent:         playwright.String(TorUA),
		Viewport:          &playwright.Size{Width: 1400, Height: 900},
		IgnoreHttpsErrors: playwright.Bool(true),
		JavaScriptEnabled: playwright.Bool(!optNoJS || optEnableJS),
		Proxy: &playwright.Proxy{Server: proxyServer},
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

	data := &ScrapedData{
		titles: make(map[string]string),
		files:  []FileInfo{},
	}

	var resMu sync.Mutex
	capturedFiles := make(map[string]bool)

	onionAddr := extractOnionAddress(fullURL)

	if optDownloadFiles {
		page.On("response", func(response playwright.Response) {
			resURL := response.URL()
			lowerURL := strings.ToLower(resURL)

			resMu.Lock()
			if capturedFiles[resURL] {
				resMu.Unlock()
				return
			}
			resMu.Unlock()

			if !optCrossOrigin && !strings.Contains(resURL, onionAddr) {
				return
			}

			category := detectCategory(lowerURL)
			if category == "" {
				return
			}

			resMu.Lock()
			capturedFiles[resURL] = true
			resMu.Unlock()

			filename := generateFilename(resURL, category)
			data.files = append(data.files, FileInfo{
				URL:      resURL,
				Category: category,
				Filename: filename,
			})
			fmt.Printf("[DETECTED] [%s] %s\n", category, filepath.Base(filename))
		})
	}

	fmt.Printf("[LOAD] %s\n", fullURL)
	if _, err := page.Goto(fullURL); err != nil {
		return nil, err
	}

	// Wait for network to go idle
	page.WaitForLoadState(playwright.PageWaitForLoadStateOptions{
		State:   playwright.LoadStateNetworkidle,
		Timeout: playwright.Float(180000), // 3 min
	})

	data.pageTitle, _ = page.Title()

	if optScreenshot {
		data.screenshot, _ = page.Screenshot(playwright.PageScreenshotOptions{
			FullPage: playwright.Bool(true),
		})
	}

	if optLinks || optTitles || optDownloadFiles {
		links, err := page.Locator("a").All()
		if err == nil {
			baseParsed, _ := url.Parse(fullURL)
			for _, link := range links {
				href, _ := link.GetAttribute("href")
				if href == "" {
					continue
				}

				// Resolve relative URLs to absolute
				var absoluteURL string
				if strings.HasPrefix(href, "http://") || strings.HasPrefix(href, "https://") {
					absoluteURL = href
				} else if baseParsed != nil {
					// Handle relative URLs
					rel, err := url.Parse(href)
					if err != nil {
						continue
					}
					resolved := baseParsed.ResolveReference(rel)
					absoluteURL = resolved.String()
				} else {
					absoluteURL = href
				}

				// Check if same domain (for crawling)
				linkParsed, _ := url.Parse(absoluteURL)
				isSameDomain := false
				if linkParsed != nil && baseParsed != nil && linkParsed.Host == baseParsed.Host {
					isSameDomain = true
				}

				// Unified Scraper Logic: Add .onion links OR same-domain links
				if strings.Contains(absoluteURL, ".onion") || isSameDomain {
					data.links = append(data.links, absoluteURL)
				}

				if optTitles {
					title, _ := link.TextContent()
					if title != "" {
						data.titles[absoluteURL] = strings.TrimSpace(title)
					}
				}

				// All-in-One Scraper Logic
				if optDownloadFiles {
					if strings.HasPrefix(href, "javascript:") || strings.HasPrefix(href, "#") {
						continue
					}

					lowerURL := strings.ToLower(absoluteURL)
					resMu.Lock()
					if !capturedFiles[absoluteURL] {
						category := detectCategory(lowerURL)
						if category != "" {
							capturedFiles[absoluteURL] = true
							filename := generateFilename(absoluteURL, category)
							data.files = append(data.files, FileInfo{URL: absoluteURL, Category: category, Filename: filename})
							fmt.Printf("[FOUND] [%s] %s\n", category, filepath.Base(filename))
						}
					}
					resMu.Unlock()
				}
			}
		}
	}

	if optHTML {
		data.htmlContent, _ = page.Content()
	}

	return data, nil
}

// ---------------------------------------------------------
// All-in-One Downloader Logic
// ---------------------------------------------------------

func detectCategory(lowerURL string) string {
	cleanURL := lowerURL
	if idx := strings.Index(cleanURL, "?"); idx != -1 {
		cleanURL = cleanURL[:idx]
	}
	if idx := strings.Index(cleanURL, "#"); idx != -1 {
		cleanURL = cleanURL[:idx]
	}

	for category, extensions := range fileCategories {
		for _, ext := range extensions {
			if strings.HasSuffix(cleanURL, ext) {
				return category
			}
		}
	}
	return ""
}

func generateFilename(resURL, category string) string {
	u, err := url.Parse(resURL)
	if err != nil {
		hash := sha256.Sum256([]byte(resURL))
		return fmt.Sprintf("%s_%s_%x", category, "unknown", hash[:8])
	}

	// Get the directory path and filename
	dir := filepath.Dir(u.Path)
	base := filepath.Base(u.Path)
	
	if base == "" || base == "." || base == "/" {
		hash := sha256.Sum256([]byte(resURL))
		base = fmt.Sprintf("%x_file", hash[:8])
	}

	// Clean filename
	clean := strings.Map(func(r rune) rune {
		if r == '<' || r == '>' || r == ':' || r == '"' || r == '/' ||
			r == '\\' || r == '|' || r == '?' || r == '*' || r == '%' {
			return '_'
		}
		return r
	}, base)

	if len(clean) > 200 {
		clean = clean[:200]
	}

	// Clean the directory path components
	if dir != "" && dir != "." && dir != "/" {
		// Remove leading slash and clean each component
		dir = strings.TrimPrefix(dir, "/")
		components := strings.Split(dir, "/")
		var cleanedComponents []string
		for _, comp := range components {
			if comp == "" || comp == "." {
				continue
			}
			// Clean component of invalid characters
			cleanComp := strings.Map(func(r rune) rune {
				if r == '<' || r == '>' || r == ':' || r == '"' || r == '/' ||
					r == '\\' || r == '|' || r == '?' || r == '*' || r == '%' {
					return '_'
				}
				return r
			}, comp)
			if cleanComp != "" {
				cleanedComponents = append(cleanedComponents, cleanComp)
			}
		}
		if len(cleanedComponents) > 0 {
			return filepath.Join(append(cleanedComponents, clean)...)
		}
	}

	return clean
}

func extractDomainForFolder(urlStr string) string {
	if strings.HasPrefix(urlStr, "http://") || strings.HasPrefix(urlStr, "https://") {
		u, err := url.Parse(urlStr)
		if err == nil && u.Host != "" {
			return strings.TrimPrefix(u.Host, "www.")
		}
	}
	return strings.TrimPrefix(urlStr, "www.")
}

func downloadAllFiles(onionAddr string, data *ScrapedData, proxyServer string) error {
	if len(data.files) == 0 {
		return nil
	}

	domainFolder := extractDomainForFolder(onionAddr)
	var filesToDownload []FileInfo
	skippedCount := 0

	for _, file := range data.files {
		// New structure: optOutputDir/domainFolder/subpath/filename (no category folder)
		baseDir := filepath.Join(optOutputDir, domainFolder)
		fullPath := windowsFriendlyPath(filepath.Join(baseDir, file.Filename))

		if info, err := os.Stat(fullPath); err == nil && info.Size() > 0 {
			fmt.Printf("[SKIP] [%s] %s (already exists, %d KB)\n", file.Category, filepath.Base(file.Filename), info.Size()/1024)
			skippedCount++
			continue
		}
		filesToDownload = append(filesToDownload, file)
	}

	if skippedCount > 0 {
		fmt.Printf("[RESUME] Skipped %d already downloaded files, %d remaining\n", skippedCount, len(filesToDownload))
	}

	if len(filesToDownload) == 0 {
		return nil
	}

	proxyURL, err := url.Parse(proxyServer)
	if err != nil {
		return err
	}
	dialer, err := proxy.FromURL(proxyURL, proxy.Direct)
	if err != nil {
		return err
	}

	transport := &http.Transport{
		Dial:                dialer.Dial,
		IdleConnTimeout:     90 * time.Second,
		DisableKeepAlives:   false,
		MaxIdleConns:        10,
		MaxIdleConnsPerHost: 5,
	}
	client := &http.Client{
		Transport: transport,
		Timeout:   30 * time.Minute,
	}

	categoryCounts := make(map[string]int)
	totalFiles := len(filesToDownload)

	for i, file := range filesToDownload {
		// New structure: optOutputDir/domainFolder/subpath/filename (no category folder)
		baseDir := filepath.Join(optOutputDir, domainFolder)
		fullPath := windowsFriendlyPath(filepath.Join(baseDir, file.Filename))

		// Create all subdirectories including those from the filename path
		dirPath := filepath.Dir(fullPath)
		if err := os.MkdirAll(dirPath, 0755); err != nil {
			fmt.Printf("[WARN] Failed to create directory %s: %v\n", dirPath, err)
			continue
		}

		err := downloadFileWithRetry(client, file, fullPath, 5, i+1, totalFiles)
		if err != nil {
			fmt.Printf("[WARN] Failed to download %s after retries: %v\n", file.URL, err)
			continue
		}

		categoryCounts[file.Category]++
	}

	fmt.Printf("[SUMMARY] Downloaded files: ")
	first := true
	for cat, count := range categoryCounts {
		if !first {
			fmt.Print(" | ")
		}
		fmt.Printf("%s: %d", cat, count)
		first = false
	}
	fmt.Println()

	return nil
}

func downloadFileWithRetry(client *http.Client, file FileInfo, fullPath string, maxRetries int, fileIndex int, totalFiles int) error {
	label := strings.ToUpper(file.Category)
	filename := filepath.Base(file.Filename)

	for attempt := 0; attempt < maxRetries; attempt++ {
		if attempt > 0 {
			time.Sleep(2 * time.Second)
		}

		var startOffset int64 = 0
		if info, err := os.Stat(fullPath); err == nil {
			startOffset = info.Size()
		}

		req, err := http.NewRequest("GET", file.URL, nil)
		if err != nil {
			return err
		}
		req.Header.Set("User-Agent", TorUA)
		if startOffset > 0 {
			req.Header.Set("Range", fmt.Sprintf("bytes=%d-", startOffset))
		}

		resp, err := client.Do(req)
		if err != nil {
			continue
		}

		if startOffset > 0 && resp.StatusCode != http.StatusPartialContent {
			startOffset = 0
			os.Remove(fullPath)
			resp.Body.Close()
			continue
		}

		if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusPartialContent {
			resp.Body.Close()
			return fmt.Errorf("non-200 status")
		}

		flag := os.O_CREATE | os.O_WRONLY
		if startOffset > 0 {
			flag = os.O_APPEND | os.O_WRONLY
		}
		out, err := os.OpenFile(fullPath, flag, 0644)
		if err != nil {
			resp.Body.Close()
			return err
		}

		pw := &ProgressWriter{
			Total:       resp.ContentLength + startOffset,
			Downloaded:  startOffset,
			Filename:    filename,
			Label:       label,
			FileIndex:   fileIndex,
			TotalFiles:  totalFiles,
		}

		_, err = io.Copy(out, io.TeeReader(resp.Body, pw))
		out.Close()
		resp.Body.Close()
		fmt.Println()

		if err != nil {
			continue
		}
		return nil
	}

	return fmt.Errorf("failed after %d attempts", maxRetries)
}

type ProgressWriter struct {
	Total      int64
	Downloaded int64
	Filename   string
	Label      string
	FileIndex  int
	TotalFiles int
}

func (pw *ProgressWriter) Write(p []byte) (int, error) {
	n := len(p)
	pw.Downloaded += int64(n)
	pw.printProgress()
	return n, nil
}

func (pw *ProgressWriter) printProgress() {
	if pw.Total <= 0 {
		fmt.Printf("\r[%s] [File %d/%d] %s: %d KB downloaded...          ", pw.Label, pw.FileIndex, pw.TotalFiles, pw.Filename, pw.Downloaded/1024)
		return
	}
	percent := float64(pw.Downloaded) / float64(pw.Total) * 100
	width := 25
	filled := int(float64(width) * float64(pw.Downloaded) / float64(pw.Total))
	if filled > width {
		filled = width
	}
	bar := strings.Repeat("=", filled) + strings.Repeat(" ", width-filled)
	fmt.Printf("\r[%s] [File %d/%d] %s: [%s] %.1f%% (%d/%d KB)          ", pw.Label, pw.FileIndex, pw.TotalFiles, pw.Filename, bar, percent, pw.Downloaded/1024, pw.Total/1024)
}

// ---------------------------------------------------------
// Original File Savers
// ---------------------------------------------------------

func saveScreenshot(onionAddr, fullURL string, screenshot []byte) error {
	imgDir := filepath.Join(optOutputDir, onionAddr, "images")
	os.MkdirAll(windowsFriendlyPath(imgDir), 0755)
	filename := generateFilenameForFile(fullURL)
	return os.WriteFile(windowsFriendlyPath(filepath.Join(imgDir, filename+".png")), screenshot, 0644)
}

func saveLinks(onionAddr, fullURL string, links []string) error {
	linkDir := filepath.Join(optOutputDir, onionAddr, "discovered_links")
	os.MkdirAll(windowsFriendlyPath(linkDir), 0755)
	filename := generateFilenameForFile(fullURL)
	return os.WriteFile(windowsFriendlyPath(filepath.Join(linkDir, filename+"_links.txt")), []byte(strings.Join(links, "\n")), 0644)
}

func saveTitles(onionAddr, fullURL string, titles map[string]string) error {
	titlesDir := filepath.Join(optOutputDir, onionAddr, "discovered_links")
	os.MkdirAll(windowsFriendlyPath(titlesDir), 0755)
	filename := generateFilenameForFile(fullURL)
	var lines []string
	for link, title := range titles {
		lines = append(lines, fmt.Sprintf("[%s] -> %s", title, link))
	}
	return os.WriteFile(windowsFriendlyPath(filepath.Join(titlesDir, filename+"_titles.txt")), []byte(strings.Join(lines, "\n")), 0644)
}

func saveMainPageTitle(onionAddr, fullURL string, pageTitle string) error {
	titlesDir := filepath.Join(optOutputDir, onionAddr, "website_identity")
	os.MkdirAll(windowsFriendlyPath(titlesDir), 0755)
	filename := generateFilenameForFile(fullURL)
	content := fmt.Sprintf("[%s] -> %s\n", pageTitle, fullURL)
	return os.WriteFile(windowsFriendlyPath(filepath.Join(titlesDir, filename+"_title.txt")), []byte(content), 0644)
}

func saveHTML(onionAddr, fullURL string, htmlContent string) error {
	htmlDir := filepath.Join(optOutputDir, onionAddr, "htmls")
	os.MkdirAll(windowsFriendlyPath(htmlDir), 0755)
	filename := generateFilenameForFile(fullURL)
	return os.WriteFile(windowsFriendlyPath(filepath.Join(htmlDir, filename+".html")), []byte(htmlContent), 0644)
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
	if len(data.files) > 0 {
		parts = append(parts, fmt.Sprintf("files_found=%d", len(data.files)))
	}
	if len(parts) == 0 {
		return "no data"
	}
	return strings.Join(parts, ", ")
}

func getInterSiteDelay() time.Duration {
	var mean, stdDev float64
	if optFastMode {
		mean, stdDev = 10, 2
	} else if optInterSiteDelay == 0 {
		mean, stdDev = 11.5, 1.75
	} else {
		mean = float64(optInterSiteDelay)
		stdDev = mean / 4.0
	}
	seconds := (rand.NormFloat64() * stdDev) + mean
	if seconds < (mean - 2*stdDev) {
		seconds = (mean - 2*stdDev)
	}
	if seconds < 1 {
		seconds = 1
	}
	if optFastMode {
		return time.Duration(seconds) * time.Second
	}
	return time.Duration(seconds*60) * time.Second
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
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		urls = append(urls, strings.TrimPrefix(line, "- "))
	}
	return urls, scanner.Err()
}

func appendLog(url, status, msg string, data *ScrapedData) {
	logDir := filepath.Dir(optLogFile)
	os.MkdirAll(logDir, 0755)
	f, _ := os.OpenFile(optLogFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if f == nil {
		return
	}
	defer f.Close()
	linksCount, titlesCount, filesFound := 0, 0, 0
	if data != nil {
		linksCount, titlesCount, filesFound = len(data.links), len(data.titles), len(data.files)
	}
	f.WriteString(fmt.Sprintf("[%s] %s | Onion: %s | Status: %s | Links: %d | Titles: %d | Files: %d | Msg: %s\n",
		time.Now().Format("2006-01-02 15:04:05"), url, extractOnionAddress(url), status, linksCount, titlesCount, filesFound, msg))
}

func extractOnionAddress(fullURL string) string {
	re := regexp.MustCompile(`([a-z0-9.-]+\.onion)`)
	matches := re.FindStringSubmatch(fullURL)
	if len(matches) > 1 {
		return strings.TrimSuffix(matches[1], ".onion")
	}
	u, err := url.Parse(fullURL)
	if err == nil && u.Host != "" {
		host := strings.ToLower(strings.TrimPrefix(strings.Split(u.Host, ":")[0], "www."))
		if host != "" {
			return host
		}
	}
	return "unknown"
}

func generateFilenameForFile(urlStr string) string {
	u, err := url.Parse(urlStr)
	if err != nil || u.Path == "" || u.Path == "/" {
		return "index"
	}
	safe := strings.Trim(u.Path, "/")
	if len(safe) > 100 {
		hash := sha256.Sum256([]byte(safe))
		return hex.EncodeToString(hash[:16])
	}
	safe = strings.ReplaceAll(safe, "/", "_")
	if len(safe) > 50 {
		safe = safe[:50]
	}
	return safe
}

func windowsFriendlyPath(path string) string {
	if runtime.GOOS != "windows" {
		return path
	}
	abs, err := filepath.Abs(path)
	if err != nil {
		return path
	}
	if !strings.HasPrefix(abs, `\\?\`) {
		return `\\?\` + abs
	}
	return abs
}

func checkTorConnection() bool {
	dialer, err := proxy.SOCKS5("tcp", "127.0.0.1:9050", nil, proxy.Direct)
	if err != nil {
		return false
	}
	transport := &http.Transport{Dial: dialer.Dial}
	client := &http.Client{Transport: transport, Timeout: 15 * time.Second}
	resp, err := client.Get("https://check.torproject.org")
	if err != nil {
		return false
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return strings.Contains(string(body), "Congratulations") || strings.Contains(string(body), "successfully")
}
