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

Intelligent grep (POST /api/grep) searches extracted PDF pages with ripgrep when installed, otherwise Python regex. It supports literals, regex, case sensitivity, whole-word matching, filename globs, hit counts, page numbers, and line-numbered context. Page extraction is memoized and document searches run through a bounded worker pool.

Directory / wordlist discovery (POST /api/discover-paths) provides bounded, concurrent, same-host path probing. The **Fuzz indexed hosts** action (POST /api/fuzz-indexes) takes URLs returned by global indexes, deduplicates their hosts, derives known directory prefixes from those URLs, and feeds both the directories and configured wordlist into a bounded async probe pool. Results are relevance-sorted with PDF candidates first and can be sent directly to PDF import. Both probes use HEAD with a one-byte Range fallback and respect robots.txt when enabled. Path work uses fixed-size worker pools rather than one task per wordlist entry. Indexed-host fuzzing has a global concurrency cap, a two-request per-host cap, a per-host request interval, and shares its probe budget across all discovered hosts.

The worker reports installed tool availability at GET /api/tools. The path fuzzer is a bounded native Python implementation; ripgrep is executed for PDF text grep when available. Other detected binaries are informational and are not silently launched. Probe only public systems you own or are explicitly authorized to assess.

## Global wildcard discovery

The interface queries Common Crawl URL indexes, searches Arquivo.pt's full-text PDF index when a keyword/phrase is supplied, then supplements with Arquivo.pt CDX and Internet Archive Wayback CDX when earlier providers are unavailable or return too few candidates, so a search does not need a seed website. Examples:

- `*.edu/**/*.pdf`
- `*.gov/**/budget*.pdf`
- `*.org/**/*manual*.pdf`

The URL matcher supports recursive globs (`*`, `**`, `?`) or full Python regular expressions against complete URLs, including optional URL query strings after a matched PDF path. A single `*` stays within one path segment; `**` crosses path separators, and `**/` can match zero or more directories. Common Crawl queries use bounded host/TLD shards, a single bounded response per shard, and a 1.05-second request interval; rate-limit and server-overload responses stop further Common Crawl requests for that run. Arquivo.pt full-text PDF search can narrow results using terms and a site/TLD scope; it supports required terms, quoted phrases, and '-' exclusions. Standalone AND is translated to the archive's implicit AND behavior; OR/NOT/parenthesis expressions remain local import filters. Archived result links are shown separately from original source URLs. Arquivo.pt CDX and Wayback CDX act as independent fallback providers when Common Crawl connectivity or coverage is insufficient. Arquivo.pt is a supplementary web archive with some international coverage beyond Portugal but is not a complete global index; its CDX API returns newline-delimited JSON. Exact glob/regex matching is enforced locally. Provider failures are returned as source-level diagnostics while the endpoint still returns HTTP 200 and any results from other sources. Common Crawl documents temporary IP blocks after excessive CDX use; when the index refuses the connection, allow its recommended 24-hour cooldown before retesting. Optional bounded live recursion follows same-host HTML links from up to five discovered host roots. Once URL candidates appear, **Fuzz indexed hosts** feeds their origins and known directory ancestors to the path fuzzer. All archive indexes are historical and incomplete; discovered URLs may be stale or unavailable. Use the result selector to fetch, inspect, and store matching PDFs.

Global discovery currently expects a recognizable public suffix such as `.edu`, `.gov`, or `.org`, or a literal host. It does not enumerate the entire live DNS namespace.

## API

- `POST /api/discover` search Common Crawl, Arquivo.pt, and Wayback CDX indexes with a full-URL glob or regex, optionally adding bounded recursive live-link discovery
- `POST /api/fuzz-indexes` use index-discovered URLs as seeds for concurrent same-host directory/path probing
- `POST /api/discover-paths` probe a supplied host with a bounded path wordlist
- `POST /api/import-urls` concurrently fetch, extract, filter, and store selected discovered PDFs
- `POST /api/jobs` create recursive site crawl
- `GET /api/jobs/{id}` job status, counters, matches, and log
- `GET /api/documents?q=...` list/search indexed documents
- `POST /api/search` linguistically normalized full-text search using FTS5 Porter stemming, Unicode diacritic folding, and BM25 relevance ranking
- `POST /api/grep` concurrent ripgrep/Python regex with memoized page-aware PDF extraction
- `GET /api/documents/{id}/download` retrieve a locally stored PDF

## Regression tests

From `pdf-lab/worker/`, run the offline regression suite:

```bash
python -m unittest discover -s tests -v
python -m py_compile app.py
```

The suite checks recursive `.edu` glob matching, Wayback header-row and Arquivo.pt NDJSON parsing, archive query construction, Arquivo.pt text-query translation, result ordering, boolean content expressions, private-address rejection, Porter stemming, and BM25 availability. GitHub Actions runs the same checks when worker files change.

## Data and privacy

Files are downloaded only to the machine running this worker. The static GitHub Pages site does not receive your PDFs. The worker binds to loopback by default. Do not expose it to the public internet without authentication, TLS, and a deliberate access-control design.


### PDF size limits

The import and crawl worker cap each PDF at 250,000,000 bytes. The interface exposes a compatible maximum of 238 MiB (binary MiB), preventing UI values from exceeding the backend byte cap.
