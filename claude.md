# MGIK Scraper - Technical Documentation

This document provides comprehensive technical context for AI assistants and developers working on the MGIK scraper codebase.

## System Overview

The MGIK Scraper is a web scraping system designed to monitor the Moscow City Election Commission's news API. It handles intermittent website availability through predictive scheduling, maintains full version history of all news items, and will eventually serve aggregated data via RSS with mirrored PDF attachments.

**Key Design Principle**: Resilience against source website downtime through prediction-based polling and retry mechanisms.

## Core Components

### [daemon.py](daemon.py) - Daemon Entry Point
Main entry point for background execution.

**Functions:**
- `load_config()` - Loads configuration from .env (no defaults, fail-fast)
- `setup_logging()` - Configures logging with file rotation
- `main()` - Creates DaemonScheduler and runs main loop

### [scheduler.py](scheduler.py) - Core Scheduler
Main daemon loop that orchestrates all components in strict sequential order.

**Execution order:**
1. Fetch news (load_decisions_from_web_to_database)
2. Download attachments (even if fetch failed)
3. Generate RSS output (only if fetch succeeded)
4. Memory check and suicide if threshold exceeded
5. Sleep until next interval

**Features:**
- Adaptive intervals with exponential backoff on failures
- Memory monitoring with psutil
- No signal handling (SIGTERM, SIGINT removed)

### [attachments.py](attachments.py) - Attachment Manager
Manages PDF attachment downloads with failure threshold.

**Features:**
- Compares database URLs with local files to find missing attachments
- Downloads with consecutive failure threshold (stops after N failures)
- Reuses fetch_attachment() from mgik_website_worker
- No SSH upload (moved to backlog)

### [output.py](output.py) - RSS Generator
Generates RSS 2.0 XML feed from decisions database.

**Features:**
- Reads all decisions from database
- Sorts by date descending
- Takes most recent N items
- Atomic file writes (temp file + rename)
- XML escaping for special characters

### [mgik_scraper.py](mgik_scraper.py) - CLI Entry Point (legacy)
Original one-shot scraper (still functional for manual runs).

### [mgik_website_worker.py](mgik_website_worker.py) - Core Scraping Logic

**Key Functions:**

#### `fetch_mgik_news(url: str) -> dict`
HTTP client with proxy and timeout support.

- **Returns**: `{"status": "success"/"error", "data": response_json, "error": error_msg}`
- **Features**:
  - SOCKS5 proxy support (if all 4 proxy env vars are set)
  - Configurable timeout
  - SSL verification disabled (`verify=False`)
  - Custom headers from environment
- **Logging**: Uses logging module with lazy formatting

#### `fetch_attachment(url: str, save_path: str) -> dict`
Download PDF attachment using existing proxy/timeout/header configuration.

- **Returns**: `{"status": "success"/"error", "error": error_msg}`
- **Features**:
  - Reuses global PROXIES, mgik_headers, request_timeout
  - Streaming download with 8KB chunks
  - Specific exception handling (Timeout, ConnectionError, HTTPError, OSError, IOError)

#### `load_decisions_from_web_to_database() -> int`
Paginated API scraping with smart stopping conditions.

- **Returns**: Total number of new (non-duplicate) records inserted across all pages
- **Pagination**: Follows `meta.next` links from API responses
- **Stops when**:
  1. No `meta.next` link found
  2. No items in response
  3. `oldest_date_in_items < MGIK_EARLIEST_DATE`
  4. No new records inserted (all duplicates)
- **Error handling**: Raises RuntimeError on fetch failure (enables proper backoff)
- **Logging**: Uses logging module throughout, logs total new records at completion
- **Date filtering**: Extracts oldest date from each page to avoid fetching ancient data

#### `process_attachments() -> list`
Legacy PDF download function (replaced by AttachmentManager).

- **Status**: Still exists but superseded by attachments.py
- Returns list of failed downloads

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

**Current daemon workflow:**
1. **Fetch news** from API → database (returns new record count or None on error)
2. **Download attachments** - runs regardless of fetch result (returns download count)
3. **Generate RSS feed** - only when new records > 0 OR new attachments > 0
   - Skipped when both counts are 0 (optimization to avoid unnecessary I/O)
   - Generated even when fetch fails but attachments succeed
4. **Update interval** - reset to default, then apply exponential backoff if fetch failed AND 0 attachments
   - Partial success (attachments downloaded) keeps normal interval
5. **Memory check** - exit if threshold exceeded (suicide pattern)
6. **Sleep** - wait until next cycle with adaptive interval

**Future flow additions (backlog):**
- Publication pattern analysis → predictive scheduler (#todo)
- SSH uploader → remote mirror server (#todo)

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
├── daemon.py                # Daemon entry point
├── scheduler.py             # Core scheduler with memory monitoring
├── attachments.py           # Attachment manager
├── output.py                # RSS generator
├── mgik_scraper.py          # Legacy CLI entry point
├── mgik_website_worker.py   # Scraping logic with fetch_attachment
├── datastore.py             # Database layer
├── requirements.txt         # 5 dependencies (requests, dotenv, pytest, pytest-mock, psutil)
├── .env                     # Configuration (gitignored)
├── .env.example             # Configuration template
├── mgik_news.db             # SQLite database
├── attachments/             # Downloaded PDFs
├── tests/                   # Test suite directory
├── .venv/                   # Python virtual environment
└── README.md                # User-facing documentation
```

## Development Environment Setup

**Python version**: This project uses `python3` (Python 3.13.5).

**Virtual environment**: This project uses a virtual environment located in `.venv/`.

**IMPORTANT**: Always activate the virtual environment before running any Python commands:
```bash
source .venv/bin/activate
```

After activation, you can use `python` and `pip` directly (they will point to the virtual environment).

**Running tests**:
```bash
source venv/bin/activate
pytest tests/test_scheduler.py -v
```

## Implementation Status

### ✅ Implemented Features

- **Background daemon mode**
  - Continuous operation with sleep intervals
  - Adaptive intervals with exponential backoff on complete failures
  - Backoff only applies when fetch fails AND no attachments downloaded
  - Partial success (attachments downloaded) keeps normal interval
  - Memory monitoring with suicide threshold (psutil)
  - No signal handling (removed SIGTERM, SIGINT)

- **RSS feed generation**
  - Generates RSS 2.0 XML from database
  - Generated when new records > 0 OR new attachments > 0
  - Skipped only when both counts are 0 (optimization)
  - Generated even when fetch fails but attachments succeed
  - Atomic file writes (temp + rename)
  - XML escaping for special characters
  - Configurable max items

- **Attachment downloads with failure threshold**
  - Identifies missing files (database vs local)
  - Downloads with consecutive failure threshold
  - Runs regardless of fetch result (even on fetch failure)
  - Returns count of successfully downloaded files
  - Reuses fetch_attachment() from mgik_website_worker

- **Logging framework**
  - Uses logging module throughout
  - Lazy formatting with %s placeholders
  - File rotation with RotatingFileHandler
  - No print() statements

- **JSON API scraping with pagination**
  - Follows `meta.next` links
  - Handles missing/malformed responses gracefully
  - Early stopping on date threshold
  - Specific exception handling (no broad exceptions)

- **SQLite database with versioning**
  - Automatic deduplication
  - Full history preservation
  - `fetched_at` timestamp tracking

- **Proxy support (SOCKS5)**
  - Configured via 4 environment variables
  - All-or-nothing (must set all 4 or none)

- **Fail-fast configuration**
  - No defaults in config loading
  - Direct dictionary access (no .get() with defaults)
  - Fails immediately if required values missing

### ⏳ Backlog Features

- **Config validation** (#todo)
  - Validate configuration on startup
  - Check numeric values are in valid ranges (positive intervals, reasonable memory limits)
  - Verify paths are writable
  - Fail fast with clear error messages

- **Error recovery improvements** (#todo)
  - Uncomment sleep in scheduler exception handler (line 112 in scheduler.py)
  - Add retry limits with exponential backoff for persistent errors
  - Prevent infinite error loops (e.g., disk full, permission denied)

- **RSS validation** (#todo)
  - Parse generated RSS XML with `ET.fromstring()` before writing
  - Catch malformed XML early to prevent corrupted feed files
  - Add test to verify RSS validates against RSS 2.0 spec

- **RSS feed improvements** (#todo)
  - Add RSS XML validation before writing to catch formatting issues
  - Consider adding more metadata (author, category, etc.)

- **Attachment download improvements** (#todo)
  - Add retry logic for failed downloads
  - Track failed downloads in database and retry in future cycles
  - Limit attachment file size (max 50MB) to prevent service hangs from extremely large files
  - Add timeout for individual file downloads

- **Health monitoring** (#todo)
  - Add simple HTTP health endpoint or status file
  - Report last successful fetch timestamp, record count, download stats
  - Enable external monitoring

- **Database optimization** (#todo)
  - Consider connection pooling or persistent connections
  - Add indexes on frequently queried columns (date, fetched_at)

- **Predictive scheduling** (#todo)
  - Analyze `fetched_at` timestamps to find publication patterns
  - Build statistical model (time-of-day, day-of-week, intervals)
  - Predict next publish window
  - Adaptive coefficient (1-32) for interval calculation
  - Feedback loop: server unreachable → adjust coefficient

- **SSH upload** (#todo)
  - Upload downloaded PDFs to remote server
  - URL mapping configuration
  - Dual-URL RSS items (original + mirror)
  - Batch upload after downloads complete

## Known Issues & Technical Debt

### Security/Safety
- **SSL verification disabled** (`verify=False` in requests calls)
  - **Rationale**: Intentionally disabled for this use case
  - The scraper monitors a public government website for news announcements
  - Content is public information, not sensitive data
  - We trust the source domain (mosgorizbirkom.ru)
  - Risk of MITM attack is acceptable: worst case is receiving fake news items, which is not a security concern for this application
  - Full browser-style certificate validation is unnecessary complexity for this scraper
  - If malicious content is injected, it's equivalent to the website being compromised (which we can't prevent anyway)
  - **Trade-off**: Simplicity and reliability vs. defense against unlikely MITM attacks on public data
  - Status: Accepted as-is, no action needed

### Testing
- **Comprehensive test suite implemented** ✅
  - All core modules have pytest tests
  - 18 passing tests in test_scheduler.py
  - Database isolation using tmp_path and patch.object()
  - Proper mocking of external dependencies
  - Test coverage includes success paths, error handling, and edge cases

### Configuration
- **.env expressions not supported**
  - Cannot use `8*3600` in .env file
  - Must use actual numbers (28800)
  - Expressions only work in Python, not in .env parsing

### Error Handling
- **Fetch failures now properly propagate**
  - Fixed: `load_decisions_from_web_to_database()` now raises RuntimeError on fetch failure
  - This enables proper backoff behavior in scheduler
  - Previously: failures were silently caught and treated as success

## Configuration Details

### Environment Variables

All configuration via `.env` file loaded with python-dotenv. **No defaults** - configuration fails immediately if required values are missing.

#### Required Variables

- **MGIK_NEWS_URL**: API endpoint for JSON news feed
- **MGIK_DB_PATH**: Path to SQLite database file
- **MGIK_HEADERS**: HTTP headers as JSON string

#### Scheduler Configuration

- **SCHEDULER_DEFAULT_INTERVAL**: Default check interval in seconds (e.g., 28800 for 8 hours)
- **SCHEDULER_MAX_INTERVAL**: Maximum interval in seconds
- **SCHEDULER_MAX_MEMORY_MB**: Memory suicide threshold in MB

#### RSS Feed Configuration

- **OUTPUT_PATH**: Path to RSS XML output file
- **OUTPUT_MAX_ITEMS**: Maximum number of items in RSS feed
- **MGIK_BASE_URL**: Base URL for MGIK website
- **RSS_FEED_TITLE**: RSS feed title
- **RSS_FEED_DESCRIPTION**: RSS feed description

#### Attachments Configuration

- **ATTACHMENTS_DIR**: Directory for downloaded PDFs
- **ATTACHMENTS_MAX_FAILURES**: Consecutive failure threshold

#### Logging Configuration

- **LOG_LEVEL**: Logging level (INFO, DEBUG, WARNING, ERROR)
- **LOG_FILE**: Path to log file
- **LOG_MAX_BYTES**: Max log file size before rotation
- **LOG_BACKUP_COUNT**: Number of backup log files

#### Optional Proxy Variables

- **MGIK_PROXY_HOST**: SOCKS5 proxy hostname
- **MGIK_PROXY_PORT**: SOCKS5 proxy port
- **MGIK_PROXY_USER**: SOCKS5 proxy username
- **MGIK_PROXY_PASS**: SOCKS5 proxy password
  - All 4 required if using proxy

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

### Test Writing Standards

**Import Formatting:**
- Split multiple imports from the same module into separate lines for clarity
- Order: standard library → third-party → local imports
- Example:
  ```python
  # Good
  import os
  from unittest.mock import Mock
  from unittest.mock import patch
  import pytest
  from attachments import AttachmentManager

  # Bad
  import os
  import pytest
  from unittest.mock import Mock, patch  # Don't combine
  from attachments import AttachmentManager
  ```

**Database Testing:**
- NEVER use the real database (`mgik_news.db`) in tests
- Always use `tmp_path` fixture for temporary databases
- Patch module-level variables with `patch.object(module, "variable", value)`
- Example:
  ```python
  def test_something(self, tmp_path):
      import datastore
      db_path = tmp_path / "test.db"
      with patch.object(datastore, "db_path", str(db_path)):
          # Test code here
  ```

**File Operations:**
- Always specify `encoding="utf-8"` when opening text files
- Use `tmp_path` fixture for temporary files/directories
- Let pytest handle cleanup automatically

**Mocking:**
- Mock external dependencies (HTTP requests, database, filesystem)
- Use `@patch` decorator for patching functions/classes
- Use `Mock(return_value=...)` instead of `lambda:` for callable mocks
- Prefix intentionally unused parameters with underscore: `_mock_param`

**Test Structure:**
- Group related tests in classes
- Use descriptive test names that explain what is being tested
- Include docstrings for non-obvious test cases
- Test both success and failure paths

### Unit Tests (pytest)

**File**: `tests/test_mgik_website_worker.py`
- `TestFetchMgikNews` - HTTP client with various error conditions
- `TestFetchAttachment` - PDF download with error handling
- `TestSaveToDatabase` - Database operations with real temp DB
- `TestLoadDecisionsFromWebToDatabase` - Pagination logic with mocking

**File**: `tests/test_datastore.py`
- Tests for database operations, versioning, URL building
- Uses temporary in-memory SQLite databases

**File**: `tests/test_attachments.py`
- Tests for AttachmentManager with failure thresholds
- Mocked database, real temporary filesystem

**File**: `tests/test_output.py`
- Tests for RSS generation and XML formatting
- Validates XML structure and escaping

**File**: `tests/test_scheduler.py`
- Tests for daemon scheduler workflow and backoff logic
- All components mocked

### Test Fixtures

**Shared fixtures** (`tests/conftest.py`):
- `setup_test_env` - Sets up environment variables automatically
- `sample_api_response` - Valid API response with items
- `sample_api_response_last_page` - Last page (no next link)
- `sample_api_response_empty` - Empty response
- `sample_decisions` - Sample decision list
- `mock_pdf_content` - Mock PDF file content

**File fixtures** (`tests/fixtures/`):
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
