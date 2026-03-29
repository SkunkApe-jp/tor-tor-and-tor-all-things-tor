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
	"path"
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
	optHTML           bool // Save raw HTML
	optSaveSite       bool // Save as Webpage Complete (HTML + assets rewritten)
	optAllowJS        bool // ALLOW dangerous JS (Default: False)
	optInterSiteDelay int  // Inter-site delay in minutes (default: 8-15 Gaussian)
	optIntraPageDelay int  // Intra-page "reading" delay in seconds (default: 60-120)
	optWorkerCount    int  // Number of parallel workers
	optFastMode       bool // Fast mode: reduce all stealth delays (inter-site to 5-15s, intra-page to 5-10s)
	optDepth          int  // Scrape depth (default 1)
	optPageLoadWait   int  // Post-Goto render wait in seconds (default: 45s, 8s in fast mode)
	optSaveClearweb   bool // Save clearweb (non-onion) links
	optResume         bool // Resume from log (skip already successful onions)
	optCrossOrigin    bool // Save cross-origin assets (external domains)
)

type ScrapedData struct {
	pageTitle     string
	htmlContent   string // Raw HTML
	screenshot    []byte
	links         []string
	clearwebLinks []string // Non-onion links
	titles        map[string]string
	// Save-as-complete fields
	siteHTML      string            // Rewritten HTML for offline use
	siteResources map[string][]byte // original URL -> raw bytes
	siteFilenames map[string]string // original URL -> local mirrored path
}

func init() {
	flag.StringVar(&optTargetsFile, "targets", "../targets.yaml", "Path to targets file")
	flag.StringVar(&optOutputDir, "output", "../scraped_data", "Directory to save results")
	flag.StringVar(&optLogFile, "log", "../logs/unified_scraper.log", "Path to unified log file")
	flag.StringVar(&optPorts, "ports", "9050", "Comma-separated Tor SOCKS ports (e.g. 9050,9051,9052)")

	flag.BoolVar(&optScreenshot, "screenshot", true, "Capture full-page screenshots")
	flag.BoolVar(&optLinks, "links", true, "Extract onion links")
	flag.BoolVar(&optTitles, "titles", true, "Extract links with titles")
	flag.BoolVar(&optHTML, "html", false, "Download and save full HTML source")
	flag.BoolVar(&optSaveSite, "save-site", true, "Save page as Webpage Complete (HTML + all assets locally rewritten)")
	flag.BoolVar(&optAllowJS, "allow-js", false, "ALLOW dangerous JavaScript to be saved (Risk: Redirects/Tracking)")
	flag.IntVar(&optInterSiteDelay, "inter-delay", 0, "Inter-site delay: 0=Gaussian 8-15min, or set custom mean (min)")
	flag.IntVar(&optIntraPageDelay, "intra-delay", 0, "Intra-page reading delay: 0=60-120sec, or set custom (sec)")
	flag.IntVar(&optWorkerCount, "workers", 1, "Number of parallel workers (default: 1)")
	flag.BoolVar(&optFastMode, "fast", false, "Fast mode: reduce all stealth delays (inter-site to 5-15s, intra-page to 5-10s)")
	flag.IntVar(&optDepth, "depth", 1, "Scrape depth (default 1 = single page, 2 = all links on page, etc.)")
	flag.IntVar(&optPageLoadWait, "page-load-wait", 0, "Seconds to wait after page load for JS render (0=auto: 45s normal, 8s fast)")
	flag.BoolVar(&optSaveClearweb, "clearweb", true, "Save discovered clearweb (non-onion) links")
	flag.BoolVar(&optResume, "resume", false, "Resume from log (skip already successful onions)")
	flag.BoolVar(&optCrossOrigin, "cross-origin", true, "Save cross-origin assets from external domains (may be large)")
}

func main() {
	flag.Parse()

	// Parse ports
	ports := parsePorts(optPorts)
	if len(ports) == 0 {
		ports = []string{"9050"}
	}

	// Create output directory if it doesn't exist
	if err := os.MkdirAll(optOutputDir, 0755); err != nil {
		fmt.Printf("[ERROR] Could not create output directory: %v\n", err)
		return
	}

	// Default to all options if none specified
	if !optScreenshot && !optLinks && !optTitles && !optHTML && !optSaveSite {
		optScreenshot = true
		optLinks = true
		optTitles = true
		optSaveSite = true
		// Standalone HTML is redundant when save-site is active
	}

	// If both are true, disable standalone HTML saving to avoid redundancy
	if optSaveSite && optHTML {
		fmt.Println("[CONFIG] Redundant: Standalone HTML disabled because SaveSite is active.")
		optHTML = false
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
		workers = 10 // Default (Reduced for better stability and lower resource usage)
	}

	fmt.Println("[CHECK] Starting unified scraper v1.2...")
	fmt.Printf("[CONFIG] Workers: %d | Ports: %v | Screenshot: %v | Links: %v | Titles: %v | HTML: %v | SaveSite: %v | CrossOrigin: %v\n", workers, ports, optScreenshot, optLinks, optTitles, optHTML, optSaveSite, optCrossOrigin)
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
	// Each request will use a different port via round-robin
	browser, err := pw.Firefox.Launch(playwright.BrowserTypeLaunchOptions{
		Headless: playwright.Bool(true),
		Args:     []string{"--proxy-remote-dns"},
	})
	if err != nil {
		fmt.Printf("[THREAD %d] Could not launch firefox: %v\n", id, err)
		return
	}
	defer browser.Close()

	for job := range jobs {
		targetURL := job.URL
		currentDepth := job.Depth

		// Ensure URL has a protocol scheme (only for clearweb, not onion)
		if !strings.HasPrefix(targetURL, "http://") && !strings.HasPrefix(targetURL, "https://") && !strings.Contains(targetURL, ".onion") {
			targetURL = "https://" + targetURL
		}

		// Global seen check to avoid loops
		seenMu.Lock()
		if seenURLs[targetURL] {
			seenMu.Unlock()
			taskWg.Done()
			continue
		}
		seenURLs[targetURL] = true
		seenMu.Unlock()

		// Select port via round-robin
		portIdx := portCounter.Next(len(ports))
		selectedPort := ports[portIdx]
		proxyServer := fmt.Sprintf("socks5://127.0.0.1:%s", selectedPort)

		// Inter-site delay with Gaussian distribution (human-like)
		delay := getInterSiteDelay()
		fmt.Printf("\n[THREAD %d] (Depth %d) [Port %s] Waiting %v for %s\n", id, currentDepth, selectedPort, delay, targetURL)
		time.Sleep(delay)

		data, err := processURL(browser, targetURL, proxyServer)
		if err != nil {
			fmt.Printf("[ERROR] [%s]: %v\n", targetURL, err)
			appendLog(targetURL, "FAIL", err.Error(), nil)
			taskWg.Done()
			continue
		}

		onionAddr := extractOnionAddress(targetURL)

		// -------------------------------------------------------------
		// Handle Depth Discovery (Crawl within site)
		// -------------------------------------------------------------
		if currentDepth < optDepth && len(data.links) > 0 {
			targetParsed, _ := url.Parse(targetURL)
			added := 0
			for _, link := range data.links {
				linkParsed, err := url.Parse(link)
				if err != nil {
					continue
				}

				// Only crawl links on the same onion hostname to avoid leaving the target
				if linkParsed.Host == targetParsed.Host && linkParsed.Host != "" {
					seenMu.Lock()
					alreadySeen := seenURLs[link]
					if !alreadySeen {
						added++
						taskWg.Add(1)
						go func(l string, d int) {
							jobs <- ScrapingJob{URL: l, Depth: d}
						}(link, currentDepth+1)
					}
					seenMu.Unlock()
				}
			}
			if added > 0 {
				fmt.Printf("[CRAWL] Discovered %d new internal links on %s (New jobs queued)\n", added, onionAddr)
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

		// Save HTML (only if site-saving is disabled to avoid duplicates)
		if optHTML && !optSaveSite && data.htmlContent != "" {
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

		// Save clearweb links
		if optSaveClearweb && len(data.clearwebLinks) > 0 {
			if err := saveClearwebLinks(onionAddr, targetURL, data.clearwebLinks); err != nil {
				fmt.Printf("[ERROR] Saving clearweb links [%s]: %v\n", targetURL, err)
			} else {
				fmt.Printf("[OK] Clearweb links saved: %s (%d links)\n", onionAddr, len(data.clearwebLinks))
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

		// Save as Webpage Complete
		if optSaveSite && data.siteHTML != "" {
			if err := saveSiteComplete(onionAddr, targetURL, data); err != nil {
				fmt.Printf("[ERROR] Saving site [%s]: %v\n", targetURL, err)
			} else {
				fmt.Printf("[OK] Site saved complete: %s (%d assets)\n", onionAddr, len(data.siteResources))
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
		Proxy: &playwright.Proxy{
			Server: proxyServer,
		},
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

	// -------------------------------------------------------------------
	// Resource interception for "Save as Webpage Complete" mode
	// -------------------------------------------------------------------
	var resMu sync.Mutex
	var resWg sync.WaitGroup
	capturedResources := make(map[string][]byte) // originalURL -> raw bytes

	if optSaveSite {
		page.On("response", func(response playwright.Response) {
			resURL := response.URL()

			// --- SECURITY BLOCK ---
			// Reject JS files immediately if not explicitly allowed
			if !optAllowJS && (strings.Contains(strings.ToLower(resURL), ".js") || strings.Contains(strings.ToLower(resURL), ".mjs")) {
				return
			}

			// Skip the main HTML document itself and data: URIs
			if resURL == fullURL || strings.HasPrefix(resURL, "data:") {
				return
			}
			status := response.Status()
			if status < 200 || status >= 400 {
				return
			}
			resWg.Add(1)
			go func() {
				defer resWg.Done()
				body, err := response.Body()
				if err != nil || len(body) == 0 {
					return
				}
				resMu.Lock()
				capturedResources[resURL] = body
				resMu.Unlock()
			}()
		})
	}

	fmt.Printf("[LOAD] %s\n", fullURL)
	if _, err := page.Goto(fullURL); err != nil {
		return nil, err
	}

	// Wait for network to go idle (all in-flight requests finished).
	// On slow onion connections this is the most reliable signal that the
	// page is truly done loading. Timeout is generous — 3 minutes.
	if err := page.WaitForLoadState(playwright.PageWaitForLoadStateOptions{
		State:   playwright.LoadStateNetworkidle,
		Timeout: playwright.Float(180000), // 3 min
	}); err != nil {
		// Non-fatal: page might still be usable, log and continue
		fmt.Printf("[WARN] networkidle timeout for %s: %v\n", fullURL, err)
	}

	// Render wait: give JS frameworks time to paint after network idle.
	// Default: 45s normal mode, 8s fast mode. Override with --page-load-wait.
	renderWait := optPageLoadWait
	if renderWait <= 0 {
		if optFastMode {
			renderWait = 8
		} else {
			renderWait = 45
		}
	}
	fmt.Printf("[RENDER] Waiting %ds for JS render...\n", renderWait)
	time.Sleep(time.Duration(renderWait) * time.Second)

	// Scroll to trigger lazy-loaded images/assets, then wait half the render time
	_, _ = page.Evaluate(`window.scrollTo(0, document.body.scrollHeight)`)
	time.Sleep(time.Duration(renderWait/2) * time.Second)

	// Intra-page "reading" delay - simulate human browsing (stealth only)
	readingDelay := getIntraPageDelay()
	fmt.Printf("[READ] Simulating human reading: %v\n", readingDelay)
	time.Sleep(readingDelay)

	// Wait for all resource-fetching goroutines to finish before processing capturedResources
	resWg.Wait()

	data := &ScrapedData{
		links:  []string{},
		titles: make(map[string]string),
	}

	// Get main page title
	pageTitle, _ := page.Title()
	data.pageTitle = pageTitle

	// Capture raw HTML and aggressively Fetch missing assets (XML, Favicons, etc.)
	if optHTML || optSaveSite {
		html, err := page.Content()
		if err == nil {
			if optHTML {
				data.htmlContent = html
			}
			if optSaveSite {
				// --- PROACTIVE ASSET DISCOVERY (Parallelized) ---
				// Video: mp4, webm, mkv, mov, m4v, avi, flv, wmv, mpg/mpeg, ogv, 3gp/3g2, ts, m3u8 (HLS), f4v, rm/rmvb, divx, xvid, asf, vob
				// Audio: mp3, ogg, opus, aac, flac, wav, wma, m4a, aiff, aif, alac
				// Docs/Archives/Fonts/Images as before
				extensions := "png|jpg|jpeg|gif|ico|svg|css|xml|json|woff2?|ttf|otf|bin|pdf|epub|mobi|azw|zip|rar|webp|avif|" +
					"mp4|webm|mkv|mov|m4v|avi|flv|wmv|mpg|mpeg|ogv|3gp|3g2|ts|m3u8|m3u|f4v|rm|rmvb|divx|xvid|asf|vob|" +
					"mp3|ogg|opus|aac|flac|wav|wma|m4a|aiff|aif|alac"
				if optAllowJS {
					extensions += "|js"
				}
				// Match src, href, url(), data-src, data-lazy-src, data-original
				assetRegex := regexp.MustCompile(`(?i)(?:src|href|data-src|data-lazy-src|data-original)=['"]([^'"]+\.(?:` + extensions + `))(?:\?[^'"]*)?['"]`)
				potentialAssets := assetRegex.FindAllStringSubmatch(html, -1)

				// Also find CSS background images: url('...') or url("...")
				bgRegex := regexp.MustCompile(`(?i)url\(['"]?([^'"]+\.(?:` + extensions + `))(?:\?[^'"]*)?['"]?\)`)
				bgAssets := bgRegex.FindAllStringSubmatch(html, -1)
				potentialAssets = append(potentialAssets, bgAssets...)

				baseURLParsed, _ := url.Parse(fullURL)

				// Use a worker pool for assets to speed up deep pages
				assetJobs := make(chan string, len(potentialAssets))
				assetWg := sync.WaitGroup{}
				assetWorkers := 5
				if optFastMode {
					assetWorkers = 10
				}

				var completedMu sync.Mutex
				completedCount := 0
				totalCount := len(potentialAssets)

				for i := 0; i < assetWorkers; i++ {
					assetWg.Add(1)
					go func() {
						defer assetWg.Done()
						for assetPath := range assetJobs {
							assetURLObj, err := baseURLParsed.Parse(assetPath)
							if err != nil {
								completedMu.Lock()
								completedCount++
								printProgress(completedCount, totalCount)
								completedMu.Unlock()
								continue
							}
							assetURL := assetURLObj.String()

							if strings.HasPrefix(assetURL, "data:") {
								completedMu.Lock()
								completedCount++
								printProgress(completedCount, totalCount)
								completedMu.Unlock()
								continue
							}

							resMu.Lock()
							_, alreadyCaptured := capturedResources[assetURL]
							resMu.Unlock()

							// Check if asset is from same host or if cross-origin is enabled
							isAssetSameHost := assetURLObj.Host == baseURLParsed.Host || strings.HasSuffix(assetURLObj.Host, "."+baseURLParsed.Host) || assetURLObj.Host == ""
							if !alreadyCaptured && (isAssetSameHost || optCrossOrigin) {
								time.Sleep(100 * time.Millisecond) // Protective delay

								// Use browser evaluation to fetch the resource
								fetchScript := fmt.Sprintf(`fetch("%s").then(r => r.arrayBuffer()).then(b => Array.from(new Uint8Array(b))).catch(e => null)`, assetURL)
								if rawArr, err := page.Evaluate(fetchScript); err == nil && rawArr != nil {
									if resSlice, ok := rawArr.([]interface{}); ok {
										body := make([]byte, len(resSlice))
										for i, v := range resSlice {
											switch val := v.(type) {
											case float64:
												body[i] = byte(val)
											case int:
												body[i] = byte(val)
											case int64:
												body[i] = byte(val)
											}
										}
										resMu.Lock()
										capturedResources[assetURL] = body
										resMu.Unlock()
									}
								}
							}
							completedMu.Lock()
							completedCount++
							printProgress(completedCount, totalCount)
							completedMu.Unlock()
						}
					}()
				}

				for _, match := range potentialAssets {
					if len(match) >= 2 {
						assetJobs <- match[1]
					}
				}
				close(assetJobs)
				assetWg.Wait()
				fmt.Println("\n[ASSETS] Completed discovery and processing.")
				// --- END PROACTIVE ASSET DISCOVERY ---

				// Build filename map and rewrite HTML
				data.siteResources = capturedResources
				data.siteFilenames = make(map[string]string)
				parsedURL, _ := url.Parse(fullURL)
				baseHost := ""
				if parsedURL != nil {
					baseHost = parsedURL.Host
				}
				for resURL := range capturedResources {
					local := resourceRelativePath(resURL, baseHost)
					data.siteFilenames[resURL] = local
				}
				data.siteFilenames[fullURL] = "index.html"

				data.siteHTML = rewriteHTML(html, fullURL, data.siteFilenames)
			}
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

		// Extract onion links
		onionRegex := regexp.MustCompile(`https?://[a-z2-7]{56}\.onion[^\s"']*`)
		seenOnionLinks := make(map[string]bool)
		// Extract clearweb links (all other http/https URLs)
		clearwebRegex := regexp.MustCompile(`https?://[a-zA-Z0-9][-a-zA-Z0-9]*\.[a-zA-Z]{2,}[^\s"']*`)
		seenClearwebLinks := make(map[string]bool)

		if linkObjects, ok := rawLinks.([]interface{}); ok {
			for _, obj := range linkObjects {
				entry, ok := obj.(map[string]interface{})
				if !ok {
					continue
				}
				linkStr := fmt.Sprintf("%v", entry["href"])
				titleStr := strings.TrimSpace(fmt.Sprintf("%v", entry["text"]))

				// Check if it's an onion link
				if onionRegex.MatchString(linkStr) && !seenOnionLinks[linkStr] {
					seenOnionLinks[linkStr] = true
					data.links = append(data.links, linkStr)

					if optTitles {
						if titleStr == "" {
							titleStr = "[No Text]"
						}
						titleStr = strings.ReplaceAll(titleStr, "\n", " ")
						data.titles[linkStr] = titleStr
					}
				} else if optSaveClearweb && clearwebRegex.MatchString(linkStr) && !seenClearwebLinks[linkStr] {
					// It's a clearweb link and we're saving those
					seenClearwebLinks[linkStr] = true
					if data.clearwebLinks == nil {
						data.clearwebLinks = []string{}
					}
					data.clearwebLinks = append(data.clearwebLinks, linkStr)
				}
			}
		}
	}

	return data, nil
}

// resourceRelativePath generates a local path that preserves the original URL's directory structure.
// For cross-origin assets, includes the hostname as a prefix to avoid conflicts.
func resourceRelativePath(resURL string, baseHost string) string {
	u, err := url.Parse(resURL)
	if err != nil {
		return "resource_bin.bin"
	}

	// Preserve full directory structure (e.g. static/images/...)
	cleanPath := strings.TrimLeft(u.Path, "/")
	if cleanPath == "" {
		cleanPath = "root_resource.bin"
	}

	// For cross-origin assets, prefix with hostname to avoid conflicts
	if u.Host != "" && u.Host != baseHost && !strings.HasSuffix(u.Host, "."+baseHost) {
		cleanPath = u.Host + "/" + cleanPath
	}

	// Sanitise individual components while keeping hierarchical structure
	parts := strings.Split(cleanPath, "/")
	for i, p := range parts {
		parts[i] = strings.Map(func(r rune) rune {
			if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') ||
				(r >= '0' && r <= '9') || r == '.' || r == '-' || r == '_' {
				return r
			}
			return '_'
		}, p)
		// Limit length to avoid Windows MAX_PATH issues while remaining professional
		if len(parts[i]) > 120 {
			parts[i] = parts[i][:120]
		}
	}

	finalName := strings.Join(parts, "/")

	// If it has no extension, give it a default to avoid ambiguous filenames
	if !strings.Contains(path.Base(finalName), ".") {
		finalName += ".bin"
	}

	return finalName
}

// rewriteHTML replaces all resource URLs with mirrored local paths.
// Optimized with a single-pass Replacer to minimize CPU and RAM usage.
func rewriteHTML(html string, baseURL string, filenameMap map[string]string) string {
	base, err := url.Parse(baseURL)
	if err != nil {
		return html
	}

	var replaces []string

	for origURL, localName := range filenameMap {
		// Assets are saved in a shared folder, so we must adjust the relative path
		localRef := localName
		if localName == "index.html" {
			localRef = "index.html"
		} else {
			// All pages are saved in saved_site/<pageName>/index.html
			// Shared assets are in saved_site/_assets/
			// So relative link is ../_assets/<localName>
			localRef = "../_assets/" + localName
		}

		targetURL, err := url.Parse(origURL)
		if err != nil {
			continue
		}

		var matches []string
		matches = append(matches, origURL)

		// 1. Root-relative paths and Sub-domain paths
		isSameHost := targetURL.Host == base.Host || strings.HasSuffix(targetURL.Host, "."+base.Host) || targetURL.Host == ""
		if isSameHost || optCrossOrigin {
			matches = append(matches, targetURL.Path)
			if targetURL.RawQuery != "" {
				matches = append(matches, targetURL.Path+"?"+targetURL.RawQuery)
			}

			// 2. Relative paths (same-folder) - only for same host
			if isSameHost {
				baseDir := path.Dir(base.Path)
				if baseDir == "." {
					baseDir = "/"
				}
				if strings.HasPrefix(targetURL.Path, baseDir) {
					rel := strings.TrimPrefix(targetURL.Path, baseDir)
					rel = strings.TrimPrefix(rel, "/")
					if rel != "" {
						matches = append(matches, rel)
						if targetURL.RawQuery != "" {
							matches = append(matches, rel+"?"+targetURL.RawQuery)
						}
					}
				}
			}
		}

		// Use single-pass replacer approach for performance
		for _, q := range []string{`"`, `'`} {
			for _, m := range matches {
				if m == "" || m == "/" {
					continue
				}
				replaces = append(replaces, q+m+q, q+localRef+q)
			}
		}
		for _, m := range matches {
			if m == "" || m == "/" {
				continue
			}
			replaces = append(replaces, "url("+m+")", "url("+localRef+")")
			replaces = append(replaces, "url('"+m+"')", "url('"+localRef+"')")
			replaces = append(replaces, "url(\""+m+"\")", "url(\""+localRef+"\")")
		}
	}

	// Execute all replacements in a single O(N) pass
	replacer := strings.NewReplacer(replaces...)
	html = replacer.Replace(html)

	// --- FIX LAZY-LOADED IMAGES ---
	// Replace data-src and data-srcset attributes that still point to external URLs
	for origURL, localName := range filenameMap {
		if localName == "index.html" {
			continue
		}
		localRef := "../_assets/" + localName

		// Replace data-src="origURL"
		dataSrcPattern := regexp.MustCompile(`(?i)data-src=["']` + regexp.QuoteMeta(origURL) + `["']`)
		html = dataSrcPattern.ReplaceAllString(html, `src="`+localRef+`" data-src="`+localRef+`"`)

		// Replace data-srcset containing origURL
		dataSrcsetPattern := regexp.MustCompile(`(?i)data-srcset=["'][^"']*` + regexp.QuoteMeta(origURL) + `[^"']*["']`)
		html = dataSrcsetPattern.ReplaceAllStringFunc(html, func(match string) string {
			// Replace the URL within the srcset value
			newMatch := strings.Replace(match, origURL, localRef, -1)
			// Also change data-srcset to srcset so it loads immediately
			newMatch = regexp.MustCompile(`(?i)data-srcset`).ReplaceAllString(newMatch, "srcset")
			return newMatch
		})
	}

	// Neutralize <base> tags to fix local relative resolution
	reBase := regexp.MustCompile(`(?i)<base\s+[^>]*>`)
	html = reBase.ReplaceAllString(html, "<!-- base removed -->")

	// --- NO-JS MODE (DEFAULT) ---
	// Completly strip all <script> tags and active handlers for total safety
	if !optAllowJS {
		reScripts := regexp.MustCompile(`(?i)<script\b[^>]*>[\s\S]*?</script>|<script\b[^>]*>`)
		html = reScripts.ReplaceAllString(html, "<!-- script stripped for safety -->")

		// Also strip inline "on..." event handlers (onclick, onload, etc.)
		reEvents := regexp.MustCompile(`(?i)\s+on[a-z]+\s*=\s*['"][^'"]+['"]`)
		html = reEvents.ReplaceAllString(html, " /* security purge: JS handler removed */")
	}

	// --- ANTI-MIRROR NEUTRALIZER ---
	// 1. Remove Ahmia's blackout CSS that triggers on non-onion domains
	reBlackout := regexp.MustCompile(`(?i)<link[^>]+href="data:text/css;base64,[^"]+"[^>]*>`)
	html = reBlackout.ReplaceAllString(html, "<!-- anti-clone css removed -->")

	// 2. Neutralize JavaScript redirects (window.location = ...)
	// This makes the local file stay local instead of jumping to the clearnet
	reRedirect := regexp.MustCompile(`(?i)window\.location(?:\.href)?\s*=\s*['"][^'"]+['"]`)
	html = reRedirect.ReplaceAllString(html, "/* redirect blocked */")
	// --- END NEUTRALIZER ---

	return html
}

// saveSiteComplete writes index.html and recreates the site's mirrored directory structure.
func saveSiteComplete(onionAddr, fullURL string, data *ScrapedData) error {
	pageName := generateFilenameForFile(fullURL)

	// Build paths WITHOUT \\?\ prefix so filepath.Join never mangles it.
	// windowsFriendlyPath is applied only at the point of the actual OS call.
	siteDir := filepath.Join(optOutputDir, onionAddr, "saved_site", pageName)

	// Create the base site directory
	if err := os.MkdirAll(windowsFriendlyPath(siteDir), 0755); err != nil {
		return err
	}

	// Write rewritten HTML
	htmlPath := filepath.Join(siteDir, "index.html")
	if err := os.WriteFile(windowsFriendlyPath(htmlPath), []byte(data.siteHTML), 0644); err != nil {
		return err
	}

	// Write every captured asset into a shared '_assets' folder to avoid
	// path duplication and Windows MAX_PATH issues.
	assetsBaseDir := filepath.Join(optOutputDir, onionAddr, "saved_site", "_assets")
	for origURL, body := range data.siteResources {
		localRelativePath, ok := data.siteFilenames[origURL]
		if !ok || localRelativePath == "index.html" {
			continue
		}

		// Skip .js assets if not explicitly allowed
		if !optAllowJS && strings.Contains(strings.ToLower(localRelativePath), ".js") {
			continue
		}

		// Save to the SHARED assets folder
		assetPath := filepath.Join(assetsBaseDir, localRelativePath)
		assetDir := filepath.Dir(assetPath)
		os.MkdirAll(windowsFriendlyPath(assetDir), 0755)

		if err := os.WriteFile(windowsFriendlyPath(assetPath), body, 0644); err != nil {
			fmt.Printf("[WARN] Could not save asset %s: %v\n", localRelativePath, err)
		}
	}

	fmt.Printf("[SITE] Professional mirror saved to %s (%d assets)\n", windowsFriendlyPath(siteDir), len(data.siteResources))
	return nil
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

func saveClearwebLinks(onionAddr, fullURL string, links []string) error {
	if len(links) == 0 {
		return nil
	}

	linkDir := filepath.Join(optOutputDir, onionAddr, "discovered_links")
	if err := os.MkdirAll(linkDir, 0755); err != nil {
		return err
	}

	filename := generateFilenameForFile(fullURL)
	filePath := filepath.Join(linkDir, filename+"_clearweb_links.txt")
	return os.WriteFile(filePath, []byte(strings.Join(links, "\n")), 0644)
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
	if len(data.siteResources) > 0 {
		parts = append(parts, fmt.Sprintf("site_assets=%d", len(data.siteResources)))
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

	if optFastMode {
		mean = 10 // 10 seconds for testing/fast scratching
		stdDev = 2
	} else if optInterSiteDelay == 0 {
		// PRODUCTION: Gaussian 8-15 MINUTES
		mean = 11.5   // (8+15)/2
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

	// PRODUCTION: Convert to duration (minutes for normal, seconds for fast)
	var delay time.Duration
	if optFastMode {
		delay = time.Duration(seconds) * time.Second
	} else {
		delay = time.Duration(seconds*60) * time.Second
	}

	fmt.Printf("[STEALTH] Inter-site delay: %v\n", delay)
	return delay
}

// getIntraPageDelay returns a Gaussian-distributed "reading" delay for intra-page waits.
// Default: 60-120 seconds (mean=90, stdDev=15)
// Custom: optIntraPageDelay ± 25%
func getIntraPageDelay() time.Duration {
	var mean, stdDev float64

	if optFastMode {
		mean = 10
		stdDev = 2
	} else if optIntraPageDelay == 0 {
		// Stealth default: 60-120 sec reading time
		mean = 90   // (60+120)/2
		stdDev = 15 // (120-60)/4
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
	// First try to find onion address
	re := regexp.MustCompile(`([a-z0-9.-]+\.onion)`)
	matches := re.FindStringSubmatch(fullURL)
	if len(matches) > 1 {
		return strings.TrimSuffix(matches[1], ".onion")
	}

	// For clearweb URLs, extract the hostname
	u, err := url.Parse(fullURL)
	if err == nil && u.Host != "" {
		host := strings.ToLower(u.Host)
		// Remove port if present
		if colonIdx := strings.LastIndex(host, ":"); colonIdx != -1 {
			host = host[:colonIdx]
		}
		// Remove www. prefix for cleaner folder names
		host = strings.TrimPrefix(host, "www.")
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

	// If path is excessively long, hash it to ensure it fits in Windows filenames
	if len(safe) > 100 {
		hash := sha256.Sum256([]byte(safe))
		return hex.EncodeToString(hash[:16]) // Short hash for stability
	}

	safe = strings.ReplaceAll(safe, "/", "_")
	if len(safe) > 50 {
		safe = safe[:50]
	}
	return safe
}

// windowsFriendlyPath handles Windows MAX_PATH by prefixing with \\?\ for absolute paths
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

func printProgress(current, total int) {
	width := 30
	percent := float64(current) / float64(total)
	filled := int(percent * float64(width))
	if filled > width {
		filled = width
	}
	if current > total {
		current = total
	}

	bar := "["
	for i := 0; i < width; i++ {
		if i < filled {
			bar += "="
		} else {
			bar += " "
		}
	}
	bar += "]"

	fmt.Printf("\r[ASSETS] %s %d/%d (%.0f%%) ", bar, current, total, percent*100)
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
