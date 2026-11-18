# PDF Lab local worker

The GitHub Pages interface is static. This companion worker performs the network crawl, extracts PDF text, applies filename wildcards and content expressions, and stores matched PDFs in a local SQLite-backed library.

## Start (Linux/macOS)

```bash
cd pdf-lab/worker
chmod +x run.sh
./run.sh
```

Then open **http://127.0.0.1:8787/**. The worker serves the interface and API from the same origin, avoiding browser mixed-content / cross-origin failures. Keep the terminal running while searching.

- API health: http://127.0.0.1:8787/api/health
- Interactive API docs: http://127.0.0.1:8787/docs
- Stored PDFs and SQLite catalog: `pdf-lab/worker/data/` (back this directory up)

## Crawl controls

- **Start URL**: a website or directory landing page.
- **Filename patterns**: comma/newline-separated glob patterns, e.g. `*.pdf, *manual*, *technical*`.
- **Content expression**: case-insensitive words/quoted phrases with `AND`, `OR`, `NOT`, and parentheses. Example: `("flight control" OR autopilot) AND NOT obsolete`.
- **Depth**: link hops from the start URL (0 means only the start URL).
- **Same-domain**: on by default; subdomains are included. Add explicitly allowed external domains when needed.
- **Respect robots.txt**: on by default.
- **Limits**: page count, PDF count, max bytes per PDF, and request delay.

The crawler follows ordinary HTML links and direct PDF URLs. It does not bypass authentication, paywalls, CAPTCHAs, robots exclusions, or access controls. It refuses localhost and non-public IP targets to reduce SSRF risk. JavaScript-only portals may require a rendered crawler such as WebGrep/Katana; this worker intentionally stays lightweight and auditable.

## Intelligent grep and path discovery

The unified search switch includes two additional engines:

- Intelligent grep (POST /api/grep): regular expressions or literal phrases across extracted PDF text; optional case sensitivity, whole-word matching, filename glob, hit counts, and configurable context lines. Results include line-numbered snippets.
- Directory / wordlist discovery (POST /api/discover-paths): bounded, concurrent, same-host path probing with a built-in starter wordlist or user-supplied paths. It uses HEAD requests first and a one-byte range fallback, reports interesting HTTP statuses and PDF candidates, and respects robots.txt when enabled. This is an ffuf-style native probe, not a wrapper that silently assumes ffuf is installed.

The worker reports installed tool availability at GET /api/tools. It detects ffuf, feroxbuster, dirsearch, gobuster, dirb, katana, hakrawler, gau, waybackurls, rg, and pdftotext. Detection is informational at this stage: the current path-probe engine is native Python and does not execute those third-party binaries. This avoids silently launching aggressive scans or relying on tools that may not be installed. Use them only against systems you own or are explicitly authorized to test.

## Global wildcard discovery

The interface also queries recent Common Crawl URL indexes, so a search does not need a seed website. Examples:

- `*.edu/**/*.pdf`
- `*.gov/**/budget*.pdf`
- `*.org/**/*manual*.pdf`

The URL matcher supports recursive globs (`*`, `**`, `?`) or full Python regular expressions against complete URLs. A single `*` stays within one path segment; `**` crosses path separators, and `**/` can match zero or more directories. Common Crawl provides broad candidates, then the complete pattern is applied locally. Optional bounded live recursion follows same-host HTML links from up to five discovered host roots, with configurable depth/page caps and robots.txt enforcement. The index is historical and not exhaustive; discovered URLs may be stale or unavailable. Use the result selector to fetch, inspect, and store matching PDFs. The same filename and content filters apply.

Global discovery currently expects a recognizable public suffix such as `.edu`, `.gov`, or `.org`, or a literal host. It does not enumerate the entire live DNS namespace.

## API

- `POST /api/discover` search Common Crawl URL indexes with a full-URL glob or regex, optionally adding bounded recursive live-link discovery\n- `POST /api/import-urls` fetch, inspect, and store selected discovered PDFs\n- `POST /api/jobs` create recursive site crawl
- `GET /api/jobs/{id}` job status, counters, matches, and log
- `GET /api/documents?q=...` list/search indexed documents
- `POST /api/search` full-text boolean search
- `GET /api/documents/{id}/download` retrieve a locally stored PDF

## Data and privacy

Files are downloaded only to the machine running this worker. The static GitHub Pages site does not receive your PDFs. The worker binds to loopback by default. Do not expose it to the public internet without authentication, TLS, and a deliberate access-control design.


### PDF size limits

The import and crawl worker cap each PDF at 250,000,000 bytes. The interface exposes a compatible maximum of 238 MiB (binary MiB), preventing UI values from exceeding the backend byte cap.
