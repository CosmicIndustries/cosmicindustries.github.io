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

## Global wildcard discovery

The interface also queries recent Common Crawl URL indexes, so a search does not need a seed website. Examples:

- `*.edu/**/*.pdf`
- `*.gov/**/budget*.pdf`
- `*.org/**/*manual*.pdf`

The URL glob is applied to the complete discovered URL. Escaped stars are normalized. The Common Crawl query is narrowed using the domain suffix (for example, `*.edu/*`) and then filtered locally against the full glob. The index is historical and not exhaustive; discovered URLs may be stale or unavailable. Use the result selector to fetch, inspect, and store matching PDFs. The same filename and content filters apply.

Global discovery currently expects a recognizable public suffix such as `.edu`, `.gov`, or `.org`, or a literal host. It does not enumerate the entire live DNS namespace.

## API

- `POST /api/discover` search Common Crawl URL indexes with a full-URL wildcard\n- `POST /api/import-urls` fetch, inspect, and store selected discovered PDFs\n- `POST /api/jobs` create recursive site crawl
- `GET /api/jobs/{id}` job status, counters, matches, and log
- `GET /api/documents?q=...` list/search indexed documents
- `POST /api/search` full-text boolean search
- `GET /api/documents/{id}/download` retrieve a locally stored PDF

## Data and privacy

Files are downloaded only to the machine running this worker. The static GitHub Pages site does not receive your PDFs. The worker binds to loopback by default. Do not expose it to the public internet without authentication, TLS, and a deliberate access-control design.
