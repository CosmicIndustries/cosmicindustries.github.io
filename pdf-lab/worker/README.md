# PDF Lab local worker

The GitHub Pages interface is static. This companion worker performs network discovery/crawling, extracts PDF and supported Office/OpenDocument text, applies filename wildcards and content expressions, and stores matched documents in a local SQLite-backed library.

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
- **Optional limits**: set page count, document count, or maximum bytes to `0` for no configured limit. Request pacing and parser/container safety checks remain enabled.

The crawler follows ordinary HTML links and direct PDF URLs. It does not bypass authentication, paywalls, CAPTCHAs, robots exclusions, or access controls. It refuses localhost and non-public IP targets to reduce SSRF risk. JavaScript-only portals may require a rendered crawler such as WebGrep/Katana; this worker intentionally stays lightweight and auditable.

## Supported document formats and reader

The library accepts and indexes:

- **PDF** (.pdf) — pypdf text extraction and the browser's built-in inline PDF reader.
- **PowerPoint** (.pptx, .ppt) — slide text extraction; modern PPTX is parsed directly from its OOXML package.
- **Word** (.docx, .doc) — paragraph/header/footer text extraction for DOCX.
- **Excel** (.xlsx, .xls) — worksheet cell text extraction for XLSX.
- **OpenDocument** (.odp, .odt, .ods) — presentation, text and spreadsheet text extraction.

The modern PPTX/DOCX/XLSX and ODP/ODT/ODS readers use Python's standard ZIP/XML libraries, so they do not require heavyweight Office packages. Legacy binary PPT/DOC/XLS conversion uses LibreOffice in headless mode when installed; otherwise the worker reports that legacy format as unsupported and continues importing other files. The worker panel reports LibreOffice availability.

The **Library & Indexes** view lists local stored documents, format, size, page/slide/sheet count, source URL and indexing status. **Reader** opens PDFs in an inline browser viewer and presents extracted slide/sheet/paragraph text for Office/OpenDocument files. Search and grep operate on extracted text across all indexed formats.

## Intelligent grep and path discovery

Intelligent grep (POST /api/grep) searches extracted PDF pages with ripgrep when installed, otherwise Python regex. It supports literals, regex, case sensitivity, whole-word matching, filename globs, hit counts, page numbers, and line-numbered context. Page extraction is memoized and document searches run through a bounded worker pool.

Directory / wordlist discovery (POST /api/discover-paths) provides bounded, concurrent, same-host path probing. Archived PDF recovery choices are displayed before live path-probe results, so historical copies remain accessible even when current university URLs return HTML, redirects, or errors. Import tries the live source first and then Arquivo.pt's direct archived file payload, validating the PDF signature on either source.

The **Expand domains & find new documents** action (POST /api/fuzz-indexes) is a two-stage, index-driven expansion workflow. It starts from (1) URLs already stored in the local document library, (2) the current URL-discovery results, (3) editable institutional seeds including MIT (`mit.edu`), University of Georgia (`uga.edu`), Middle Georgia State (`mga.edu`), and other Georgia institutions, and (4) new `.edu` document URLs retrieved from Common Crawl and Arquivo.pt archives. Newly discovered hostnames are merged into the domain set before host/path probing. The fuzzer uses the visible **Document formats to discover** selection for archive expansion, local-index seeds and path probing. It defaults to PDF, PowerPoint, Word, Excel and OpenDocument formats; narrow that field to PDF alone for a PDF-only run. It returns a job ID immediately; poll GET /api/fuzz-indexes/{job_id} for live progress and partial results.\n\nThe fuzzer tests exact indexed URLs first, then derives adjacent year/chapter/part filenames from indexed names (for example, neighboring chapters or annual editions), then probes their known directory ancestors and the configured wordlist. It verifies candidate responses with a small ranged GET and the actual file signature. Only verified document files are preselected for import. Exact-content/version duplicates are skipped; different years, chapters, parts and editions are kept as distinct entries and grouped into ordered series stacks in the Library.\n\nThe default probe budget is `0` (all generated probes). A positive `max_probes` value can be supplied to the API when a deliberate cap is required. The request engine still uses fixed-size worker pools, a global concurrency ceiling, at most two in-flight requests per host, per-host request spacing and robots.txt checks when enabled. There is no configured file-size limit when `max_bytes=0`; available disk, RAM and parser/container safeguards still apply.

The worker reports installed tool availability at GET /api/tools. The path fuzzer is a bounded native Python implementation; ripgrep is executed for PDF text grep when available. Other detected binaries are informational and are not silently launched. Probe only public systems you own or are explicitly authorized to assess.

## Global wildcard discovery

The interface queries Arquivo.pt's full-text PDF index first when a keyword/phrase is supplied, then supplements with Common Crawl, Arquivo.pt CDX, and Internet Archive Wayback CDX. A candidate limit of `0` means all results returned by the configured providers; provider APIs still impose their own per-response caps. Common Crawl index count `0` means all collections advertised by its collection list. URL-only index candidates are explicitly marked as keyword-unverified; the import stage still applies the full local content expression. Examples:

- `*.edu/**/*.pdf`
- `*.gov/**/budget*.pdf`
- `*.org/**/*manual*.pdf`

The URL matcher supports recursive globs (`*`, `**`, `?`) or full Python regular expressions against complete URLs, including optional URL query strings after a matched PDF path. A single `*` stays within one path segment; `**` crosses path separators, and `**/` can match zero or more directories. Common Crawl queries use bounded host/TLD shards, a single bounded response per shard, and a 1.05-second request interval; rate-limit and server-overload responses stop further Common Crawl requests for that run. Arquivo.pt full-text PDF search can narrow results using terms and a site/TLD scope; it supports required terms, quoted phrases, and '-' exclusions. Standalone AND is translated to the archive's implicit AND behavior; OR/NOT/parenthesis expressions remain local import filters. Archived result links are shown separately from original source URLs; archive HTML snippets and titles are converted to plain text before display. Arquivo.pt TextSearch candidates also retain `linkToOriginalFile`, which points to the archived binary payload. The UI offers those PDF copies separately, and import tries the original URL first before falling back to the archived file; both paths must pass the `%PDF-` signature check. Arquivo.pt CDX and Wayback CDX act as independent fallback providers when Common Crawl connectivity or coverage is insufficient. Arquivo.pt is a supplementary web archive with some international coverage beyond Portugal but is not a complete global index; its CDX API returns newline-delimited JSON. Exact glob/regex matching is enforced locally. Provider failures are returned as source-level diagnostics while the endpoint still returns HTTP 200 and any results from other sources. Common Crawl documents temporary IP blocks after excessive CDX use; when the index refuses the connection, allow its recommended 24-hour cooldown before retesting. Optional bounded live recursion follows same-host HTML links from up to five discovered host roots. The **Expand domains & find new documents** workflow seeds from the local library, discovered URLs and institutional domains, discovers new .edu hostnames through global archive indexes, then tests the indexed paths and adjacent year/chapter/part filenames. All archive indexes are historical and incomplete; discovered URLs may be stale or unavailable. Use the result selector to fetch, inspect, and store matching PDFs.

Global discovery currently expects a recognizable public suffix such as `.edu`, `.gov`, or `.org`, or a literal host. It does not enumerate the entire live DNS namespace.

## API

- `POST /api/discover` search Common Crawl, Arquivo.pt, and Wayback CDX indexes with a full-URL glob or regex, optionally adding bounded recursive live-link discovery
- `POST /api/fuzz-indexes` discover new `.edu` domains from the local index and archive indexes, then probe indexed paths; `GET /api/fuzz-indexes/{job_id}` returns live progress, domains, candidate URLs and results
- `POST /api/discover-paths` probe a supplied host with a bounded path wordlist
- `POST /api/import-urls` concurrently fetch, extract, filter, and store selected PDF/Office/OpenDocument files
- `POST /api/jobs` create recursive site crawl
- `GET /api/jobs/{id}` job status, counters, matches, and log
- `GET /api/documents?q=...&format=...&sort=...` list/search indexed documents by query, format and sort order; `limit=0` returns the full local catalogue
- `GET /api/documents/{id}/content` return extracted text and reader metadata
- `GET /api/documents/{id}/view` serve a stored PDF inline for the lightweight reader
- `GET /api/worker/status` report worker health, storage, format counts, and active/recent job progress
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


### File-size and candidate limits

The UI and worker use `0` to mean no configured byte, result, page, document or probe budget. Positive values apply explicit ceilings. A zero size cap does not mean infinite hardware capacity: downloads and extraction still require sufficient disk/RAM, and Office ZIP/XML parsing enforces archive-entry and expanded-size safety checks. Provider APIs also cap individual index responses. The PDF parser checks the `%PDF-` signature before calling pypdf; a `.pdf` filename or MIME header alone is not accepted as proof.


PDF font decoding: the worker pins `pypdf>=6.20,<7` and `fonttools>=4.60,<5`. This enables CFF Type 1 font decoding; pypdf 6.20 includes caching for the embedded CFF font map. Malformed source CMaps may still produce skipped-line warnings, but these are distinct from import/HTTP failures.


## Duplicate handling and version stacks

Documents are deduplicated by SHA-256 and by normalized extracted text plus detected version identifiers. The version detector checks titles, filenames and the opening 3,500 characters of extracted text for years, chapters, parts and editions. Distinct years/chapters/parts/editions remain separate records. The Library can group series and sort by institution, title, year/chapter/part, size, format or date. Archive replay URLs are normalized back to their original institution URL before metadata extraction and local-index seeding.
