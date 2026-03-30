package main

import (
	"bufio"
	"crypto/sha256"
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
	optInterSiteDelay int  // Inter-site delay in minutes
	optIntraPageDelay int  // Intra-page "reading" delay in seconds
	optWorkerCount    int  // Number of parallel workers
	optFastMode       bool // Fast mode: reduce all stealth delays
	optDepth          int  // Scrape depth (default 1)
	optPageLoadWait   int  // Post-Goto render wait in seconds
	optResume         bool // Resume from log
	optCrossOrigin    bool // Save cross-origin assets (external domains)
	optNoJS           bool
	optEnableJS       bool
)

type ScrapedData struct {
	pageTitle     string
	videoURLs      []string          // URLs to download
	videoFilenames map[string]string // original URL -> local mirrored path
}

func init() {
	flag.StringVar(&optTargetsFile, "targets", "../video_targets.yaml", "Path to targets file")
	flag.StringVar(&optOutputDir, "output", "../scraped_videos", "Directory to save results")
	flag.StringVar(&optLogFile, "log", "../logs/video_scraper.log", "Path to video log file")
	flag.StringVar(&optPorts, "ports", "9050", "Comma-separated Tor SOCKS ports (e.g. 9050,9051,9052)")

	flag.IntVar(&optInterSiteDelay, "inter-delay", 0, "Inter-site delay: 0=Gaussian 8-15min, or set custom mean (min)")
	flag.IntVar(&optIntraPageDelay, "intra-delay", 0, "Intra-page reading delay: 0=60-120sec, or set custom (sec)")
	flag.IntVar(&optWorkerCount, "workers", 1, "Number of parallel workers (default: 1)")
	flag.BoolVar(&optFastMode, "fast", false, "Fast mode: reduce all stealth delays")
	flag.IntVar(&optDepth, "depth", 1, "Scrape depth")
	flag.IntVar(&optPageLoadWait, "page-load-wait", 0, "Seconds to wait after page load for JS render")
	flag.BoolVar(&optResume, "resume", false, "Resume from log")
	flag.BoolVar(&optCrossOrigin, "cross-origin", true, "Save cross-origin videos from external domains")
	flag.BoolVar(&optNoJS, "no-js", true, "Disable JavaScript execution (default: true for safety/speed)")
	flag.BoolVar(&optEnableJS, "js", false, "Enable JavaScript execution if needed for dynamic sites")
}

func main() {
	flag.Parse()

	ports := parsePorts(optPorts)
	if len(ports) == 0 {
		ports = []string{"9050"}
	}

	if err := os.MkdirAll(optOutputDir, 0755); err != nil {
		fmt.Printf("[ERROR] Could not create output directory: %v\n", err)
		return
	}

	rand.Seed(time.Now().UnixNano())

	fmt.Println("[CHECK] Verifying Tor connection...")
	if !checkTorConnection() {
		fmt.Println("NOT CONNECTED TO TOR! Aborting.")
		return
	}

	workers := optWorkerCount
	if workers <= 0 {
		workers = 5 // Reduced for video heavy scraping
	}

	fmt.Println("[CHECK] Starting Video Scraper v1.0...")
	fmt.Printf("[CONFIG] Workers: %d | Ports: %v | Depth: %d | CrossOrigin: %v\n", workers, ports, optDepth, optCrossOrigin)

	targets, err := readTargets(optTargetsFile)
	if err != nil {
		log.Fatalf("could not read targets: %v", err)
	}

	if len(targets) == 0 {
		fmt.Println("No targets found in", optTargetsFile)
		return
	}

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
		}
	}

	jobQueue := make(chan ScrapingJob, 5000)
	var workerWg sync.WaitGroup
	var taskWg sync.WaitGroup
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

	go func() {
		taskWg.Wait()
		close(jobQueue)
	}()

	workerWg.Wait()
	fmt.Println("\n[DONE] Video scraping complete!")
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

		if !strings.HasPrefix(targetURL, "http://") && !strings.HasPrefix(targetURL, "https://") && !strings.Contains(targetURL, ".onion") {
			targetURL = "https://" + targetURL
		}

		seenMu.Lock()
		if seenURLs[targetURL] {
			seenMu.Unlock()
			taskWg.Done()
			continue
		}
		seenURLs[targetURL] = true
		seenMu.Unlock()

		portIdx := portCounter.Next(len(ports))
		selectedPort := ports[portIdx]
		proxyServer := fmt.Sprintf("socks5://127.0.0.1:%s", selectedPort)

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

		// Depth Crawling
		if currentDepth < optDepth {
			// Extract links from page content to find more videos
			// (Simplified crawling logic for focus on videos)
		}

		// Download Videos
		if len(data.videoURLs) > 0 {
			if err := downloadVideos(onionAddr, data, proxyServer); err != nil {
				fmt.Printf("[ERROR] Downloading videos [%s]: %v\n", targetURL, err)
			} else {
				fmt.Printf("[OK] Downloaded %d videos from %s\n", len(data.videoURLs), onionAddr)
			}
		}

		appendLog(targetURL, "SUCCESS", fmt.Sprintf("videos=%d", len(data.videoURLs)), data)
		taskWg.Done()
	}
}

func processURL(browser playwright.Browser, fullURL string, proxyServer string) (*ScrapedData, error) {
	context, err := browser.NewContext(playwright.BrowserNewContextOptions{
		UserAgent:         playwright.String(TorUA),
		Viewport:          &playwright.Size{Width: 1400, Height: 900},
		IgnoreHttpsErrors: playwright.Bool(true),
		Proxy:             &playwright.Proxy{Server: proxyServer},
		JavaScriptEnabled: playwright.Bool(!optNoJS || optEnableJS),
	})
	if err != nil {
		return nil, err
	}
	defer context.Close()

	page, err := context.NewPage()
	if err != nil {
		return nil, err
	}
	page.SetDefaultTimeout(300000) // 5 min timeout for video pages

	var resMu sync.Mutex
	capturedVideos := make(map[string]bool)

	videoExtensions := []string{".mp4", ".webm", ".mkv", ".mov", ".m4v", ".avi", ".flv", ".wmv", ".mpg", ".mpeg", ".ogv", ".3gp", ".3g2", ".ts", ".m3u8", ".f4v"}

	page.On("response", func(response playwright.Response) {
		resURL := response.URL()
		lowerURL := strings.ToLower(resURL)
		
		isVideo := false
		for _, ext := range videoExtensions {
			if strings.Contains(lowerURL, ext) {
				isVideo = true
				break
			}
		}

		if isVideo {
			status := response.Status()
			if status >= 200 && status < 400 {
				resMu.Lock()
				capturedVideos[resURL] = true
				resMu.Unlock()
			}
		}
	})

	fmt.Printf("[LOAD] %s\n", fullURL)
	if _, err := page.Goto(fullURL); err != nil {
		return nil, err
	}

	_ = page.WaitForLoadState(playwright.PageWaitForLoadStateOptions{
		State:   playwright.LoadStateNetworkidle,
		Timeout: playwright.Float(60000),
	})

	renderWait := optPageLoadWait
	if renderWait <= 0 {
		renderWait = 15
	}
	time.Sleep(time.Duration(renderWait) * time.Second)

	// Scroll to trigger lazy video loads
	_, _ = page.Evaluate(`window.scrollTo(0, document.body.scrollHeight)`)
	time.Sleep(5 * time.Second)

	data := &ScrapedData{
		videoFilenames: make(map[string]string),
	}
	
	pageTitle, _ := page.Title()
	data.pageTitle = pageTitle

	// Proactive Video Discovery in HTML
	html, _ := page.Content()
	videoRegex := regexp.MustCompile(`(?i)(?:src|href|data-src)=['"]([^'"]+\.(?:mp4|webm|mkv|mov|m4v|avi|flv|wmv|mpg|mpeg|ogv|3gp|ts|m3u8))(?:\?[^'"]*)?['"]`)
	matches := videoRegex.FindAllStringSubmatch(html, -1)
	
	baseURLParsed, _ := url.Parse(fullURL)
	for _, match := range matches {
		if len(match) < 2 {
			continue
		}
		assetURLObj, err := baseURLParsed.Parse(match[1])
		if err != nil {
			continue
		}
		assetURL := assetURLObj.String()
		
		resMu.Lock()
		capturedVideos[assetURL] = true
		resMu.Unlock()
	}

	for resURL := range capturedVideos {
		data.videoURLs = append(data.videoURLs, resURL)
		data.videoFilenames[resURL] = resourceRelativePath(resURL, baseURLParsed.Host)
	}

	return data, nil
}

func downloadVideos(onionAddr string, data *ScrapedData, proxyServer string) error {
	baseDir := filepath.Join(optOutputDir, onionAddr, "videos")
	
	// Setup Tor Proxy Client
	proxyURL, err := url.Parse(proxyServer)
	if err != nil {
		return fmt.Errorf("invalid proxy URL: %v", err)
	}
	dialer, err := proxy.FromURL(proxyURL, proxy.Direct)
	if err != nil {
		return fmt.Errorf("could not create proxy dialer: %v", err)
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
		Timeout:   60 * time.Minute,
	}

	for _, origURL := range data.videoURLs {
		localPath := data.videoFilenames[origURL]
		fullPath := windowsFriendlyPath(filepath.Join(baseDir, localPath))
		
		if err := os.MkdirAll(baseDir, 0755); err != nil {
			fmt.Printf("[WARN] Failed to create directory %s: %v\n", baseDir, err)
			continue
		}

		req, err := http.NewRequest("GET", origURL, nil)
		if err != nil {
			fmt.Printf("[WARN] Failed to create request for %s: %v\n", origURL, err)
			continue
		}
		req.Header.Set("User-Agent", TorUA)

		resp, err := client.Do(req)
		if err != nil {
			fmt.Printf("[WARN] Failed to download %s: %v\n", origURL, err)
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode != http.StatusOK {
			fmt.Printf("[WARN] Non-200 status for %s: %s\n", origURL, resp.Status)
			continue
		}

		out, err := os.Create(fullPath)
		if err != nil {
			fmt.Printf("[WARN] Failed to create file %s: %v\n", fullPath, err)
			continue
		}
		
		pw := &ProgressWriter{
			Total:    resp.ContentLength,
			Filename: filepath.Base(localPath),
		}
		
		_, err = io.Copy(out, io.TeeReader(resp.Body, pw))
		out.Close()
		fmt.Println() // New line after progress bar
		if err != nil {
			fmt.Printf("[WARN] Error during copy for %s: %v\n", origURL, err)
		}
	}
	return nil
}

type ProgressWriter struct {
	Total      int64
	Downloaded int64
	Filename   string
}

func (pw *ProgressWriter) Write(p []byte) (int, error) {
	n := len(p)
	pw.Downloaded += int64(n)
	pw.printProgress()
	return n, nil
}

func (pw *ProgressWriter) printProgress() {
	if pw.Total <= 0 {
		fmt.Printf("\r[STREAM] %s: %d KB downloaded...", pw.Filename, pw.Downloaded/1024)
		return
	}
	percent := float64(pw.Downloaded) / float64(pw.Total) * 100
	width := 25
	filled := int(float64(width) * float64(pw.Downloaded) / float64(pw.Total))
	if filled > width { filled = width }
	bar := strings.Repeat("=", filled) + strings.Repeat(" ", width-filled)
	fmt.Printf("\r[STREAM] %s: [%s] %.1f%% (%d/%d KB)", pw.Filename, bar, percent, pw.Downloaded/1024, pw.Total/1024)
}

func resourceRelativePath(resURL string, baseHost string) string {
	u, err := url.Parse(resURL)
	if err != nil {
		return "video_file.bin"
	}
	cleanPath := strings.TrimLeft(u.Path, "/")
	if cleanPath == "" {
		cleanPath = "video_" + fmt.Sprintf("%x", sha256.Sum256([]byte(resURL)))[:8]
	}
	if u.Host != "" && u.Host != baseHost {
		cleanPath = u.Host + "/" + cleanPath
	}
	parts := strings.Split(cleanPath, "/")
	for i, p := range parts {
		parts[i] = strings.Map(func(r rune) rune {
			if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '.' || r == '-' || r == '_' {
				return r
			}
			return '_'
		}, p)
	}
	return strings.Join(parts, "/")
}

func getInterSiteDelay() time.Duration {
	if optFastMode {
		return time.Duration(rand.Intn(10)+5) * time.Second
	}
	if optInterSiteDelay > 0 {
		return time.Duration(optInterSiteDelay) * time.Minute
	}
	return time.Duration(rand.Intn(7)+8) * time.Minute
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
	f, _ := os.OpenFile(optLogFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if f == nil { return }
	defer f.Close()
	logLine := fmt.Sprintf("[%s] %s | Status: %s | Msg: %s\n", time.Now().Format("2006-01-02 15:04:05"), url, status, msg)
	f.WriteString(logLine)
}

func extractOnionAddress(fullURL string) string {
	re := regexp.MustCompile(`([a-z0-9.-]+\.onion)`)
	matches := re.FindStringSubmatch(fullURL)
	if len(matches) > 1 {
		return strings.TrimSuffix(matches[1], ".onion")
	}
	u, _ := url.Parse(fullURL)
	if u != nil && u.Host != "" {
		return strings.TrimPrefix(u.Host, "www.")
	}
	return "unknown"
}

func windowsFriendlyPath(path string) string {
	if runtime.GOOS != "windows" { return path }
	abs, _ := filepath.Abs(path)
	if !strings.HasPrefix(abs, `\\?\`) { return `\\?\` + abs }
	return abs
}

func checkTorConnection() bool {
	dialer, _ := proxy.SOCKS5("tcp", "127.0.0.1:9050", nil, proxy.Direct)
	if dialer == nil { return false }
	transport := &http.Transport{Dial: dialer.Dial}
	client := &http.Client{Transport: transport, Timeout: 15 * time.Second}
	resp, err := client.Get("https://check.torproject.org")
	if err != nil { return false }
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)
	return strings.Contains(string(body), "Congratulations") || strings.Contains(string(body), "successfully")
}
