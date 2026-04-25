@echo off
go run .\playwright\unified_scraper.go -html=false -files=false -clearweb=false -ports 9050,9051,9052 -resume -workers 3 -max-pages 1