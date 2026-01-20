# MGIK Scraper - Technical Documentation

This document provides comprehensive technical context for AI assistants and developers working on the MGIK scraper codebase.

## System Overview

The MGIK Scraper is a web scraping system designed to monitor the Moscow City Election Commission's news API. It handles intermittent website availability through predictive scheduling, maintains full version history of all news items, and will eventually serve aggregated data via RSS with mirrored PDF attachments.

**Key Design Principle**: Resilience against source website downtime through prediction-based polling and retry mechanisms.

## Core Components

### [mgik_scraper.py](mgik_scraper.py) - Main Entry Point (21 lines)
Orchestrates the scraping and processing workflow.

**Current workflow:**
1. Calls `load_decisions_from_web_to_database()` to fetch and store news
2. ~~Calls `process_attachments()` to download PDFs~~ (currently disabled, line 16)

**Purpose**: Simple orchestration layer for coordinating data fetching and attachment processing.

### [mgik_website_worker.py](mgik_website_worker.py) - Core Scraping Logic (231 lines)

**Key Functions:**

#### `fetch_mgik_news(url: str) -> dict`
HTTP client with proxy and timeout support.

- **Returns**: `{"status": "success"/"error", "data": response_json, "error": error_msg}`
- **Features**:
  - SOCKS5 proxy support (if all 4 proxy env vars are set)
  - Configurable timeout (default: 30s)
  - SSL verification disabled (`verify=False`) - exercise caution
  - Custom headers from environment

#### `load_decisions_from_web_to_database() -> None`
Paginated API scraping with smart stopping conditions.

- **Pagination**: Follows `meta.next` links from API responses
- **Stops when**:
  1. No `meta.next` link found
  2. No items in response
  3. `oldest_date_in_items < MGIK_EARLIEST_DATE`
  4. No new records inserted (all duplicates)
- **Progress tracking**: Prints page count, insert count, duplicate count per page
- **Date filtering**: Extracts oldest date from each page to avoid fetching ancient data

#### `process_attachments() -> None`
PDF download manager with resilience features.

- **Strategy**:
  1. Get all file URLs from database
  2. List existing files in `attachments/` directory
  3. Compute missing files (database - local)
  4. Shuffle download order (randomize to avoid rate limiting patterns)
  5. Stream download with 8KB chunks
- **Error handling**: Tracks failed downloads in `failed_downloads` list
- **Status**: Currently disabled in main script (see known issues)

### [datastore.py](datastore.py) - Database Layer (149 lines)

#### `DecisionsDatabase` Class
SQLite wrapper with automatic versioning.

**Key Methods:**

- `save_decisions(decisions: list) -> int`
  - Inserts records, returns count of new (non-duplicate) records
  - Automatically adds `fetched_at` timestamp to every record
  - Uses `INSERT OR IGNORE` for deduplication

- `get_all_files() -> list[str]`
  - Returns all unique file URLs from database
  - Used by attachment processor to know what to download

- `get_all() -> list[dict]`
  - Returns all decisions with all fields
  - Useful for RSS feed generation

- `build_pdf_url(relative_path: str) -> str`
  - Constructs absolute URL from relative path
  - Example: `"/upload/foo.pdf"` → `"https://www.mosgorizbirkom.ru/upload/foo.pdf"`

## Architecture

### Data Flow

```
API Endpoint (MGIK News JSON)
         ↓
fetch_mgik_news() - HTTP GET with proxy/timeout/headers
         ↓
JSON Response {"items": [...], "meta": {"next": "..."}}
         ↓
Pagination Loop (follows meta.next)
         ↓
Extract oldest_date, check stopping conditions
         ↓
save_to_database() - INSERT OR IGNORE
         ↓
SQLite Database (mgik_news.db)
         ├→ get_all_files()
         ↓
process_attachments() - Download missing PDFs
         ↓
attachments/*.pdf (local filesystem)
```

**Future flow additions:**
- Publication pattern analysis → predictive scheduler
- RSS feed generator ← database
- SSH uploader → remote mirror server

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mgik_id TEXT,
    name TEXT,
    number TEXT,
    date TEXT,
    file TEXT,
    fetched_at TEXT,  -- Added automatically by DecisionsDatabase
    UNIQUE(mgik_id, name, number, date, file)
)
```

**Versioning Strategy:**
- UNIQUE constraint on (mgik_id, name, number, date, file)
- Every fetch attempt inserts new records with fresh `fetched_at` timestamp
- Duplicates are silently ignored (INSERT OR IGNORE)
- Result: Full history of all versions automatically preserved
- Changes detected by comparing `fetched_at` timestamps

**Why this works:**
- If a decision is modified (different name/number/date), it gets a new record
- If a decision is deleted from the API, old records remain in database
- If a decision is unchanged, INSERT OR IGNORE prevents duplicates

## Use Case & Design Rationale

The Moscow City Election Commission publishes news as JSON via a React-based website. The site frequently goes offline after publishing batches of news. This creates several challenges:

1. **Unpredictable uptime**: Website may be down for hours/days after publishing
2. **Batch publishing pattern**: Multiple decisions published at once, then silence
3. **Need for monitoring**: Users want notifications when new decisions appear
4. **Attachment availability**: PDFs may only be accessible during brief uptime windows

**System Response:**

1. **Monitors** the API endpoint for new publications (current: manual runs, planned: daemon)
2. **Predicts** when new content will appear based on historical patterns (planned: Phase 2)
3. **Adapts** its checking frequency to catch updates quickly (planned: Phase 2, 8h → 10min)
4. **Preserves** all versions of news items via database schema (implemented)
5. **Downloads** PDF attachments, retrying when the site is unavailable (implemented but disabled)
6. **Serves** the aggregated news as an RSS feed with mirror URLs (planned: Phase 3)

## Project Structure

```
mgik-scraper/
├── mgik_scraper.py          # Entry point (21 lines)
├── mgik_website_worker.py   # Scraping logic (231 lines)
├── datastore.py             # Database layer (149 lines)
├── test_process_attachments.py  # Manual test script
├── requirements.txt         # 4 dependencies (requests, dotenv, pytest, pytest-mock)
├── .env                     # Configuration (gitignored)
├── .env.example             # Configuration template
├── mgik_news.db            # SQLite database (144 KB, ~1000s of records)
├── solutions.json          # Sample API response (44 KB)
├── attachments/            # Downloaded PDFs
├── tests/                  # Test suite directory (empty, planned)
└── README.md               # User-facing documentation
```

## Implementation Status

### ✅ Implemented Features

- **JSON API scraping with pagination**
  - Follows `meta.next` links
  - Handles missing/malformed responses gracefully
  - Early stopping on date threshold

- **SQLite database with versioning**
  - Automatic deduplication
  - Full history preservation
  - `fetched_at` timestamp tracking

- **Duplicate detection**
  - UNIQUE constraint at database level
  - Returns count of new vs duplicate records

- **Proxy support (SOCKS5)**
  - Configured via 4 environment variables
  - All-or-nothing (must set all 4 or none)

- **Environment-based configuration**
  - .env file with python-dotenv
  - Required: MGIK_NEWS_URL, MGIK_HEADERS, MGIK_DB_PATH
  - Optional: REQUEST_TIMEOUT, MGIK_EARLIEST_DATE, proxy settings

- **PDF URL construction**
  - `build_pdf_url()` converts relative to absolute
  - Base URL: https://www.mosgorizbirkom.ru

### ⏳ Planned Features

- **Predictive scheduling** (Phase 2)
  - Analyze `fetched_at` timestamps to find publication patterns
  - Build statistical model (time-of-day, day-of-week, intervals)
  - Predict next publish window

- **Adaptive check frequency** (Phase 2)
  - Normal: check every 8 hours
  - During predicted publish window: check every 10 minutes
  - Exponential backoff after failed predictions

- **RSS feed generation** (Phase 3)
  - Read from database
  - Generate RSS 2.0 XML
  - Items include: name, number, date, description with dual URLs

- **Background daemon mode** (Phase 2)
  - Continuous operation with sleep intervals
  - Signal handling (SIGTERM, SIGHUP)
  - Systemd service unit file

- **Attachment retry logic** (Phase 3)
  - Track failed downloads in database
  - Retry on next successful API fetch
  - Configurable max retries

- **SSH upload** (Phase 3)
  - Upload downloaded PDFs to remote server
  - URL mapping configuration
  - Dual-URL RSS items (original + mirror)

## Known Issues & Technical Debt

### Security/Safety
- **SSL verification disabled** (`verify=False` in requests calls)
  - Location: [mgik_website_worker.py:60](mgik_website_worker.py#L60), [mgik_website_worker.py:214](mgik_website_worker.py#L214)
  - Reason: Unknown (possibly self-signed certificate on MGIK server?)
  - Action needed: Enable SSL or document why it must be disabled

### Testing
- **No automated tests**
  - `tests/` directory exists but is empty
  - pytest and pytest-mock installed but unused
  - Only manual test script: `test_process_attachments.py`
  - Action needed: Write pytest suite for core functions

### Observability
- **Uses `print()` instead of `logging` module**
  - No log levels (DEBUG, INFO, WARNING, ERROR)
  - No log file output
  - No structured logging
  - Action needed: Implement proper logging framework

### Features
- **Attachment processing disabled**
  - Line 16 in [mgik_scraper.py](mgik_scraper.py#L16) is commented out
  - Reason: Unknown (possibly incomplete/untested?)
  - Action needed: Enable and test, or remove if not needed

## Configuration Details

### Environment Variables

All configuration via `.env` file loaded with python-dotenv.

#### Required Variables

- **MGIK_NEWS_URL**: API endpoint for JSON news feed
  - Example: `https://www.mosgorizbirkom.ru/api/news`
  - Type: String (URL)
  - Used in: `load_decisions_from_web_to_database()` as starting point

- **MGIK_HEADERS**: HTTP headers as JSON string
  - Example: `{ "User-Agent": "Mozilla/5.0...", "Accept": "application/json" }`
  - Type: JSON string (parsed with `json.loads()`)
  - Used in: `fetch_mgik_news()` for all requests
  - Purpose: Mimic browser to avoid bot detection

- **MGIK_DB_PATH**: Path to SQLite database file
  - Example: `/path/to/mgik_news.db` or `mgik_news.db` (relative)
  - Type: String (file path)
  - Used in: `DecisionsDatabase` constructor

#### Optional Variables

- **REQUEST_TIMEOUT**: HTTP request timeout in seconds
  - Default: `30` (if not set or invalid)
  - Type: Integer
  - Used in: `fetch_mgik_news()` for `requests.get(timeout=...)`

- **MGIK_EARLIEST_DATE**: Stop pagination at this date
  - Default: `1970-01-01` (effectively no limit)
  - Format: `YYYY-MM-DD`
  - Type: String (parsed with `datetime.strptime()`)
  - Used in: `load_decisions_from_web_to_database()` to avoid fetching old data
  - Logic: If `oldest_date_in_items < earliest_date`, stop pagination

- **MGIK_PROXY_HOST**: SOCKS5 proxy hostname
- **MGIK_PROXY_PORT**: SOCKS5 proxy port
- **MGIK_PROXY_USER**: SOCKS5 proxy username
- **MGIK_PROXY_PASS**: SOCKS5 proxy password
  - All 4 required if using proxy (checked at runtime)
  - Used to build: `socks5://user:pass@host:port`
  - Used in: `fetch_mgik_news()` as `proxies` parameter

## Error Handling Patterns

### Return Format Convention
All functions that can fail return dict:
```python
{
    "status": "success" | "error",
    "data": <result_data>,      # Present on success
    "error": <error_message>    # Present on error
}
```

### Failure Modes

1. **Network failures** (connection timeout, DNS, socket errors)
   - Caught in `fetch_mgik_news()`
   - Returns `{"status": "error", "error": str(exception)}`
   - Caller prints error and stops

2. **Invalid JSON responses**
   - Caught in `fetch_mgik_news()` during `response.json()`
   - Returns `{"status": "error", ...}`

3. **Missing expected fields** (no "items", no "meta")
   - Handled with `.get()` and early returns
   - Prints warning message
   - Stops pagination gracefully

4. **Database errors** (disk full, permissions, corrupt DB)
   - Not explicitly caught (will raise exception and crash)
   - Action needed: Add try/except around database operations

### Graceful Degradation
- Website downtime treated as temporary, not fatal
- Partial page fetches still saved to database
- Failed attachment downloads tracked but don't stop execution
- No logging framework yet (uses `print()` which is fire-and-forget)

## Development Roadmap

### Phase 1: Core Stability
**Goal**: Make the current implementation production-ready

- [ ] **Enable and test attachment downloads**
  - Uncomment line 16 in [mgik_scraper.py](mgik_scraper.py#L16)
  - Test with real PDFs
  - Verify file integrity (size, content)
  - Add error recovery for corrupted downloads

- [ ] **Add proper logging framework**
  - Replace all `print()` statements with `logging` module
  - Add log levels: DEBUG, INFO, WARNING, ERROR
  - Configure file output with rotation
  - Structured logging for machine parsing

- [ ] **Write pytest test suite**
  - Unit tests for `fetch_mgik_news()` (mock requests)
  - Unit tests for `DecisionsDatabase` (in-memory SQLite)
  - Integration test for pagination logic
  - Test fixtures with sample API responses

- [ ] **Enable SSL verification or document why it's disabled**
  - Try enabling `verify=True`
  - If it fails, capture the SSL error
  - Document whether it's self-signed cert or other issue
  - Consider using `verify='/path/to/ca-bundle.crt'` if needed

### Phase 2: Smart Scheduling
**Goal**: Implement predictive polling to catch updates quickly

- [ ] **Implement publication pattern analysis**
  - Query `fetched_at` timestamps from database
  - Group by time-of-day, day-of-week, month
  - Calculate intervals between new decisions
  - Statistical analysis (mean, median, std dev, percentiles)

- [ ] **Build predictive model for next publish time**
  - Identify publication patterns (e.g., "Mondays at 10 AM", "Last Friday of month")
  - Calculate confidence intervals
  - Use exponentially weighted moving average for recent patterns
  - Store predictions in database or memory

- [ ] **Add adaptive polling frequency (8h ↔ 10min)**
  - Default: check every 8 hours
  - If prediction says "likely in next 2 hours": increase to every 10 minutes
  - After successful fetch: reset to 8 hours
  - After missed prediction: exponential backoff, learn from error

- [ ] **Create background daemon mode**
  - Main loop with `time.sleep()` between checks
  - Signal handlers for graceful shutdown (SIGTERM, SIGINT)
  - Reload configuration on SIGHUP
  - Systemd service unit file with auto-restart
  - PID file to prevent multiple instances

### Phase 3: RSS & Distribution
**Goal**: Serve aggregated data via RSS with mirrored attachments

- [ ] **Generate RSS feed from database**
  - Read all decisions with `get_all()`
  - Generate RSS 2.0 XML format
  - RSS items based on: name, number, date
  - Item description includes both original MGIK URL and mirror URL
  - `<pubDate>` from `fetched_at` timestamp
  - `<guid>` from `mgik_id` for deduplication in readers

- [ ] **Add HTTP server for RSS endpoint**
  - Simple Flask/FastAPI server
  - Route: `/rss` → RSS XML
  - Route: `/health` → health check
  - CORS headers for browser access
  - Cache RSS XML for 5 minutes to avoid DB hammering

- [ ] **Implement attachment retry logic**
  - Add `downloads` table to track download attempts
  - Schema: `(file_url, status, attempts, last_attempt_at, error)`
  - Retry failed downloads on next successful API fetch
  - Configurable max retries (e.g., 5)
  - Exponential backoff between retries

- [ ] **SSH upload for downloaded attachments**
  - Use `paramiko` for SFTP upload
  - Configuration: SSH host, port, user, key path, remote directory
  - Upload after successful download
  - URL pattern mapping:
    - Local: `attachments/CustomDocument12345.pdf`
    - Mirror: `http://server1.domain1/path1/CustomDocument12345.pdf`
  - Store mapping in database for RSS generation
  - Dual-URL listing in RSS to avoid committee blacklisting

- [ ] **Add health check/monitoring**
  - `/health` endpoint with:
    - Last successful API fetch timestamp
    - Database record count
    - Attachment download success rate
    - Current polling frequency
  - Prometheus metrics export (optional)
  - Alert on N consecutive failures

## Testing Strategy

### Unit Tests (pytest)

**File**: `tests/test_worker.py`
- `test_fetch_mgik_news_success()` - Mock successful API response
- `test_fetch_mgik_news_timeout()` - Mock connection timeout
- `test_fetch_mgik_news_invalid_json()` - Mock malformed response
- `test_proxy_configuration()` - Verify proxy URL building

**File**: `tests/test_datastore.py`
- `test_save_decisions_new()` - Insert new records
- `test_save_decisions_duplicates()` - Verify INSERT OR IGNORE
- `test_get_all_files()` - Retrieve unique file URLs
- `test_build_pdf_url()` - URL construction logic

### Integration Tests (pytest)

**File**: `tests/test_integration.py`
- `test_pagination_flow()` - Full pagination with mock API
- `test_date_filtering()` - Stop at MGIK_EARLIEST_DATE
- `test_duplicate_detection()` - Multiple fetches, same data

### Manual Tests

**Current**: `test_process_attachments.py`
- Downloads PDFs to test attachment processing
- Should be converted to proper pytest with mocking

### Test Fixtures

- `sample_api_response.json` - Valid API response with items
- `sample_api_paginated.json` - Response with meta.next
- `sample_api_empty.json` - Response with no items

## Dependencies

```
requests[socks]  # HTTP client with SOCKS proxy support
python-dotenv    # Environment variable management
pytest           # Testing framework
pytest-mock      # Mocking for tests
```

**Future additions**:
- `feedgen` or `PyRSS2Gen` for RSS generation
- `flask` or `fastapi` for HTTP server
- `paramiko` for SSH/SFTP uploads
- `schedule` for cron-like scheduling
- `prometheus_client` for metrics (optional)

## Performance Considerations

### Current
- Single-threaded, synchronous I/O
- No caching (fetches all pages every run)
- No rate limiting (could hammer API during pagination)

### Future Optimizations
- Cache last `meta.next` URL to resume pagination
- Rate limiting: sleep between requests (e.g., 1 second)
- Parallel attachment downloads (thread pool)
- RSS XML caching (regenerate only on DB changes)
- Database indexes on (date, fetched_at) for RSS queries

## API Response Format

**Typical response structure**:
```json
{
  "items": [
    {
      "mgik_id": "12345",
      "name": "Решение о...",
      "number": "123/45-П",
      "date": "2025-01-15",
      "file": "/upload/decisions/2025/document.pdf"
    }
  ],
  "meta": {
    "next": "https://example.com/api/news?page=2",
    "total": 1234
  }
}
```

**Edge cases handled**:
- Missing "items" key → print warning, stop
- Missing "meta" key → no pagination, stop after first page
- Missing "meta.next" → stop pagination
- Empty items array → stop pagination
- Null/invalid date formats → crashes (not currently handled)

## Common Operations

### Running a one-time scrape
```bash
python mgik_scraper.py
```

### Checking database contents
```bash
sqlite3 mgik_news.db "SELECT COUNT(*) FROM decisions"
sqlite3 mgik_news.db "SELECT * FROM decisions ORDER BY fetched_at DESC LIMIT 10"
```

### Testing attachment downloads
```bash
python test_process_attachments.py
```

### Future: Running as daemon
```bash
# systemctl start mgik-scraper
# systemctl enable mgik-scraper
# journalctl -u mgik-scraper -f
```

## Troubleshooting

### Problem: "MGIK_NEWS_URL variable must be set"
**Solution**: Create `.env` file from `.env.example` with actual values

### Problem: Pagination stops immediately
**Possible causes**:
1. `MGIK_EARLIEST_DATE` is too recent (all records older than threshold)
2. API response has no `meta.next` field
3. All records are duplicates (already in database)

**Debug**: Add `print(data)` after `fetch_mgik_news()` to inspect API response

### Problem: SSL errors
**Workaround**: Currently using `verify=False` to bypass SSL verification
**Long-term**: Investigate certificate issue, use proper CA bundle

### Problem: Proxy not working
**Check**:
1. All 4 proxy variables are set in `.env`
2. Proxy format is SOCKS5, not HTTP
3. Credentials are correct
4. Proxy server is reachable

### Problem: Attachments not downloading
**Check**:
1. Line 16 in `mgik_scraper.py` is uncommented
2. `attachments/` directory exists and is writable
3. PDF URLs are valid (check with `build_pdf_url()`)
