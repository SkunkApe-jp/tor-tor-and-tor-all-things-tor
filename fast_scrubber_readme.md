# Fast Onion Scrubber

| Port | Service | Why it matters |
|------|---------|----------------|
| `22` | SSH | Direct shell access — biggest OPSEC failure possible |
| `21` | FTP | Unencrypted file transfer, often left open on old servers |
| `3306` | MySQL | Exposed database, may allow unauthenticated login |
| `8080` | HTTP Alt | Admin panels, dev servers, phpMyAdmin often run here |
| `3389` | RDP | Windows Remote Desktop — full GUI shell access |