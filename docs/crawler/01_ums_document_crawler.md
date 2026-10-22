# UMS Document Crawler — Design

> **Status**: Designed, not implemented. Requires authorization confirmation before building.
> **Companion document**: `02_rms_taxonomy_extractor.md` covers the RMS form specifically.

---

## Purpose

The UMS Document Crawler is a **read-only, authorized document discovery tool** that:

- Discovers and collects institution-wide documents authorized for the SMART-RMS knowledge base
- Requires a human account owner to authenticate manually — never automates login
- Operates only within an explicit allowlist of approved domains and paths
- Runs in DISCOVERY mode by default — no files downloaded until a human reviews the report

**What it collects**: Official circulars, academic calendars, examination schedules, placement notices, FAQs, public policies, syllabi, hostel guidelines.

**What it never collects**: Personal student records, individual grades, fee balances, personal contact details, private messages, or any information requiring elevated privilege.

---

## Prerequisites (Must Complete Before Any Code is Written)

- [ ] Written authorization from LPU IT or administration for automated document collection
- [ ] Google Drive API credentials created, scoped to target folder only, stored in `.secrets/` (gitignored)
- [ ] `.gitignore` confirms `.playwright_session/` and `.secrets/` are excluded

---

## Crawler Modes

| Mode | Command flag | Behavior |
|---|---|---|
| Login | `--mode=login` | Opens browser for human login; saves session |
| Discovery | `--mode=discovery` (default) | Traverses links, reports findings, downloads nothing |
| Download | `--mode=download --approved-list=path/to/urls.txt` | Downloads only URLs in the reviewed approved list |

---

## Module Responsibilities

| Module | File | Job |
|---|---|---|
| Config | `src/crawler/config.py` | Allowlists, limits, delays, MIME types |
| Session Manager | `src/crawler/session_manager.py` | Save/load Playwright browser context |
| Frontier | `src/crawler/frontier.py` | Visited-URL tracking, depth enforcement |
| Link Extractor | `src/crawler/link_extractor.py` | Extract all links from a page |
| Document Detector | `src/crawler/document_detector.py` | MIME + magic bytes check |
| Allowlist Guard | `src/crawler/allowlist.py` | Domain + path enforcement |
| Downloader | `src/crawler/downloader.py` | Fetch bytes, SHA-256, safe filename |
| Drive Uploader | `src/crawler/drive_uploader.py` | Upload to Google Drive via API v3 |
| Metadata Writer | `src/crawler/metadata_writer.py` | Write to document_index.csv + PostgreSQL |
| Discovery Reporter | `src/crawler/discovery_reporter.py` | Generate HTML/CSV dry-run report |
| Error Logger | `src/crawler/error_logger.py` | Structured JSON error log |
| Engine | `src/crawler/engine.py` | Orchestrate all modules |

---

## Configuration (`config/crawler_config.yaml`)

```yaml
crawler:
  mode: "discovery"
  start_urls:
    - "https://ums.lpu.in/"
  allowed_domains:
    - "ums.lpu.in"
  allowed_path_prefixes:
    - "/lpuums/"
  max_depth: 3
  max_pages: 200
  max_file_size_mb: 50
  concurrency: 1
  polite_delay_seconds: 2.0
  retry_limit: 3
  session_path: ".playwright_session/"

  eligible_mime_types:
    - "application/pdf"
    - "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    - "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    - "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    - "text/plain"
    - "text/html"

  eligible_extensions: [".pdf", ".docx", ".xlsx", ".pptx", ".txt"]

  excluded_url_patterns:
    - "/payment"
    - "/fee"
    - "/submit"
    - "/profile"
    - "/edit"
    - "/delete"
    - "/logout"
    - "/api/"
    - "/grade"
    - "/attendance"

google_drive:
  target_folder_id: "1o31DA1NLrK1vTFcgUMZ0Qb1y_FXBXM71"
  credentials_path: ".secrets/gdrive_service_account.json"

document_categories:
  - circulars
  - academic_calendar
  - exam_schedule
  - placement_notices
  - faqs
  - policies
  - syllabi
  - hostel_guidelines
  - uncategorized
```

---

## Document Index Schema

See the full 20-column schema in `docs/database/01_postgresql_schema.md` under `knowledge.documents`.

Additional CSV-specific fields written to `data/metadata/document_index.csv`:

| Column | Notes |
|---|---|
| `drive_file_id` | Google Drive file ID |
| `drive_url` | Shareable link |
| `crawl_run_id` | Links to per-run manifest in `data/crawler/manifests/` |

---

## Safety Constraints (Hard Rules)

1. **Concurrency = 1 by default** — one request at a time; never parallel crawling
2. **Polite delay ≥ 2 seconds** between requests
3. **Retry limit = 3** — after 3 failures, skip and log; never loop infinitely
4. **Maximum depth = 3** — does not spider recursively without limit
5. **Maximum pages = 200** — hard stop; never crawls an entire portal blindly
6. **No POST, PATCH, DELETE requests** — read-only; only GET
7. **No form submission** — even if a form is encountered
8. **File signature check** — MIME type must match actual magic bytes
9. **SHA-256 deduplication** — never downloads the same content twice
10. **Session expiry detection** — if login session expires, pause and prompt human
