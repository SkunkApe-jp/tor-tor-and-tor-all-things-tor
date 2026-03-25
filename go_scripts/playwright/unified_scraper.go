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
	"path"
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
	optScreenshot     bool
	optLinks          bool
	optTitles         bool
	optHTML           bool // Save raw HTML
	optSaveSite       bool // Save as Webpage Complete (HTML + assets rewritten)
	optAllowJS        bool // ALLOW dangerous JS (Default: False)
	optInterSiteDelay int  // Inter-site delay in minutes (default: 8-15 Gaussian)
	optIntraPageDelay int  // Intra-page "reading" delay in seconds (default: 60-120)
	optWorkerCount    int  // Number of parallel workers
)


type ScrapedData struct {
	pageTitle         string
	htmlContent       string // Raw HTML
	screenshot        []byte
	links             []string
	titles            map[string]string
	// Save-as-complete fields
	siteHTML          string            // Rewritten HTML for offline use
	siteResources     map[string][]byte // original URL -> raw bytes
	siteFilenames     map[string]string // original URL -> local mirrored path
}

func init() {
	flag.StringVar(&optTargetsFile, "targets", "../targets.yaml", "Path to targets file")
	flag.StringVar(&optOutputDir, "output", "../scraped_data", "Directory to save results")
	flag.StringVar(&optLogFile, "log", "../logs/unified_scraper.log", "Path to unified log file")

	flag.BoolVar(&optScreenshot, "screenshot", false, "Capture full-page screenshots")
	flag.BoolVar(&optLinks, "links", false, "Extract onion links")
	flag.BoolVar(&optTitles, "titles", false, "Extract links with titles")
	flag.BoolVar(&optHTML, "html", false, "Download and save full HTML source")
	flag.BoolVar(&optSaveSite, "save-site", false, "Save page as Webpage Complete (HTML + all assets locally rewritten)")
	flag.BoolVar(&optAllowJS, "allow-js", false, "ALLOW dangerous JavaScript to be saved (Risk: Redirects/Tracking)")
	flag.IntVar(&optInterSiteDelay, "inter-delay", 0, "Inter-site delay: 0=Gaussian 8-15min, or set custom mean (min)")
	flag.IntVar(&optIntraPageDelay, "intra-delay", 0, "Intra-page reading delay: 0=60-120sec, or set custom (sec)")
	flag.IntVar(&optWorkerCount, "workers", 1, "Number of parallel workers (default: 1)")
}

func main() {
	flag.Parse()

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
	fmt.Printf("[CONFIG] Workers: %d | Screenshot: %v | Links: %v | Titles: %v | HTML: %v | SaveSite: %v\n", workers, optScreenshot, optLinks, optTitles, optHTML, optSaveSite)
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

	jobs := make(chan string, len(targets))
	var wg sync.WaitGroup

	for i := 1; i <= workers; i++ {
		wg.Add(1)
		go worker(i, jobs, &wg)
	}

	for _, u := range targets {
		jobs <- u
	}
	close(jobs)
	wg.Wait()

	fmt.Println("\n[DONE] All targets processed!")
}

func worker(id int, jobs <-chan string, wg *sync.WaitGroup) {
	defer wg.Done()

	pw, err := playwright.Run()
	if err != nil {
		fmt.Printf("[THREAD %d] Could not start playwright: %v\n", id, err)
		return
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
		fmt.Printf("[THREAD %d] Could not launch firefox: %v\n", id, err)
		return
	}
	defer browser.Close()

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
	}
}

func processURL(browser playwright.Browser, fullURL string) (*ScrapedData, error) {
	context, err := browser.NewContext(playwright.BrowserNewContextOptions{
		UserAgent:         playwright.String(TorUA),
		Viewport:          &playwright.Size{Width: 1400, Height: 900},
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

	// Wait for page render and scroll for lazy-loaded content
	time.Sleep(5 * time.Second)
	_, _ = page.Evaluate(`window.scrollTo(0, document.body.scrollHeight)`)
	time.Sleep(3 * time.Second)

	// Intra-page "reading" delay - simulate human browsing
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
				// --- PROACTIVE ASSET DISCOVERY ---
				// Find anything the browser missed (favicons, opensearch xmls, etc.)
				extensions := "png|jpg|jpeg|gif|ico|svg|css|xml|json|woff2?|ttf|otf|bin|pdf"
				if optAllowJS {
					extensions += "|js"
				}
				assetRegex := regexp.MustCompile(`(?i)(?:src|href|url)=['"]([^'"]+\.(?:` + extensions + `))(?:\?[^'"]*)?['"]`)
				potentialAssets := assetRegex.FindAllStringSubmatch(html, -1)
				
				baseURLParsed, _ := url.Parse(fullURL)
				for _, match := range potentialAssets {
					if len(match) < 2 { continue }
					assetPath := match[1]
					
					// Resolve to absolute URL
					assetURLObj, err := baseURLParsed.Parse(assetPath)
					if err != nil { continue }
					assetURL := assetURLObj.String()
					
					// Skip data URIs or already captured ones
					if strings.HasPrefix(assetURL, "data:") { continue }

					resMu.Lock()
					_, alreadyCaptured := capturedResources[assetURL]
					resMu.Unlock()
					
					if !alreadyCaptured && (assetURLObj.Host == baseURLParsed.Host || assetURLObj.Host == "") {
						// Small artificial delay to avoid hammering the SOCKS proxy too fast
						time.Sleep(100 * time.Millisecond)
						
						// Use browser evaluation to fetch the resource (keeps cookies/headers/proxy)
						fetchScript := fmt.Sprintf(`fetch("%s").then(r => r.arrayBuffer()).then(b => Array.from(new Uint8Array(b))).catch(e => null)`, assetURL)
						if rawArr, err := page.Evaluate(fetchScript); err == nil && rawArr != nil {
							if resSlice, ok := rawArr.([]interface{}); ok {
								body := make([]byte, len(resSlice))
								for i, v := range resSlice {
									// Handle both float64 and int types returned by the browser
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
				}
				// --- END PROACTIVE ASSET DISCOVERY ---

				// Build filename map and rewrite HTML
				data.siteResources = capturedResources
				data.siteFilenames = make(map[string]string)
				for resURL := range capturedResources {
					local := resourceRelativePath(resURL)
					data.siteFilenames[resURL] = local
				}
				// Add the page itself to the map so links to it stay local
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

// resourceRelativePath generates a local path that preserves the original URL's directory structure.
func resourceRelativePath(resURL string) string {
	u, err := url.Parse(resURL)
	if err != nil {
		return "resource_bin.bin"
	}

	// Preserve full directory structure (e.g. static/images/...)
	cleanPath := strings.TrimLeft(u.Path, "/")
	if cleanPath == "" {
		return "root_resource.bin"
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
		localRef := localName // NO "_files/" - preservation of directory structure
		if localName == "index.html" {
			localRef = "index.html"
		}

		targetURL, err := url.Parse(origURL)
		if err != nil {
			continue
		}

		var matches []string
		matches = append(matches, origURL)

		// 1. Root-relative paths
		if targetURL.Host == base.Host {
			matches = append(matches, targetURL.Path)
			if targetURL.RawQuery != "" {
				matches = append(matches, targetURL.Path+"?"+targetURL.RawQuery)
			}
			
			// 2. Relative paths (same-folder)
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

		// Use single-pass replacer approach for performance
		for _, q := range []string{`"`, `'`} {
			for _, m := range matches {
				if m == "" || m == "/" { continue }
				replaces = append(replaces, q+m+q, q+localRef+q)
			}
		}
		for _, m := range matches {
			if m == "" || m == "/" { continue }
			replaces = append(replaces, "url("+m+")", "url("+localRef+")")
			replaces = append(replaces, "url('"+m+"')", "url('"+localRef+"')")
			replaces = append(replaces, "url(\""+m+"\")", "url(\""+localRef+"\")")
		}
	}

	// Execute all replacements in a single O(N) pass
	replacer := strings.NewReplacer(replaces...)
	html = replacer.Replace(html)

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
	siteDir := filepath.Join(optOutputDir, onionAddr, "saved_site", pageName)

	// Create the base site directory
	if err := os.MkdirAll(siteDir, 0755); err != nil {
		return err
	}

	// Write rewritten HTML
	htmlPath := filepath.Join(siteDir, "index.html")
	if err := os.WriteFile(htmlPath, []byte(data.siteHTML), 0644); err != nil {
		return err
	}

	// Write every captured asset into its original mirrored path
	for origURL, body := range data.siteResources {
		localRelativePath, ok := data.siteFilenames[origURL]
		if !ok || localRelativePath == "index.html" {
			continue
		}
		
		// Skip .js assets if not explicitly allowed
		if !optAllowJS && strings.Contains(strings.ToLower(localRelativePath), ".js") {
			continue
		}

		// --- DEEP DEFANGING ---
		// Join with siteDir to build the full local path (e.g. siteDir/static/images/...)
		assetPath := filepath.Join(siteDir, localRelativePath)
		assetDir := filepath.Dir(assetPath)
		os.MkdirAll(assetDir, 0755)
		
		if err := os.WriteFile(assetPath, body, 0644); err != nil {
			fmt.Printf("[WARN] Could not save asset %s: %v\n", localRelativePath, err)
		}
	}

	fmt.Printf("[SITE] Professional mirror saved to %s (%d assets)\n", siteDir, len(data.siteResources))
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
