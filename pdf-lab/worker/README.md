# PDF Lab local worker

The GitHub Pages interface is static. This companion worker performs the network crawl, extracts PDF text, applies filename wildcards and content expressions, and stores matched PDFs in a local SQLite-backed library.

## Start (Linux/macOS)

```bash
cd pdf-lab/worker
chmod +x run.sh
./run.sh
```

Then open the PDF Lab page and set **Worker API** to `http://127.0.0.1:8787`. Keep the worker running while using Crawl, Search, and Library.

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

## API

- `POST /api/jobs` create crawl
- `GET /api/jobs/{id}` job status, counters, matches, and log
- `GET /api/documents?q=...` list/search indexed documents
- `POST /api/search` full-text boolean search
- `GET /api/documents/{id}/download` retrieve a locally stored PDF

## Data and privacy

Files are downloaded only to the machine running this worker. The static GitHub Pages site does not receive your PDFs. The worker binds to loopback by default. Do not expose it to the public internet without authentication, TLS, and a deliberate access-control design.
