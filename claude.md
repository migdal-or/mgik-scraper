# MGIK Scraper
Web scraper monitoring Moscow City Election Commission's news API. Daemon with adaptive intervals, version history, PDF downloads, RSS generation.

This project relies on python virtual environment.
Always activate venv to run tests or the code itself.

## Tests
```bash
source .venv/bin/activate
pytest tests/ -v
```

**Standards**:
- Separate imports: `from unittest.mock import Mock` + `from unittest.mock import patch`
- Database: always `tmp_path`, patch with `patch.object(datastore, "db_path", str(db_path))`
- Files: specify `encoding="utf-8"`
- Unused params: prefix with `_`
- No complex expressions in curly brackets, calculate them on the previous line.

## Quick Reference

### Core Components

**[daemon.py](daemon.py)** - Entry point
- `load_config()` - no defaults, fail-fast
- `setup_logging()` - file rotation
- `main()` - validate config → setup logging → run scheduler

**[config_validator.py](config_validator.py)** - Startup validation
- Required strings, positive integers, reasonable ranges
- Path writability, URL protocols, log levels
- Reports all errors at once
- Runs before logging setup

**[scheduler.py](scheduler.py)** - Main loop
1. Fetch news → database
2. Download attachments
3. Generate RSS (when new records OR new attachments)
4. Memory check (suicide if exceeded)
5. Sleep until next interval

Adaptive intervals: exponential backoff on fetch failure AND zero attachments. Partial success keeps normal interval.

**[mgik_website_worker.py](mgik_website_worker.py)** - Scraping
- `fetch_mgik_news()` - HTTP with SOCKS5 proxy, returns `{"status": "success"/"error", "data": ..., "error": ...}`
- `fetch_attachment()` - size limit (checks Content-Length), custom timeout, streaming download
- `load_decisions_from_web_to_database()` - pagination via meta.next, stops on: no next link, empty items, old dates, zero new records

**[attachments.py](attachments.py)** - Downloads
- Compare DB vs local files
- Download missing with consecutive failure threshold
- Size limit (50MB), timeout (10min)

**[output.py](output.py)** - RSS generation
- OutputManager orchestrates generators
- RSSGenerator: RSS 2.0 XML from DB
- Feedparser semantic validation (fail-fast)
- Atomic writes (temp → rename)
- XML escaping

**[datastore.py](datastore.py)** - Database
- `save_decisions()` - INSERT OR IGNORE, returns count of new records
- `get_all_files()` - DISTINCT file URLs
- `get_all()` - ORDER BY fetched_at DESC

## Config (.env)

- Some variables are Required

- Some are Optional (SOCKS5 proxy)
All 4 required if using proxy:
```bash
MGIK_PROXY_HOST=
MGIK_PROXY_PORT=
MGIK_PROXY_USER=
MGIK_PROXY_PASS=
```

## Data Flow

```
API → fetch_mgik_news() → JSON → Pagination (meta.next)
  → save_to_database() (INSERT OR IGNORE)
  → SQLite
    ├→ get_all_files() → process_attachments() → attachments/*.pdf
    └→ get_all() → RSSGenerator → output.rss
```

Daemon workflow:
1. Fetch → DB (returns new count or None)
2. Download attachments (always runs, returns count)
3. Generate RSS (when new_records > 0 OR new_attachments > 0)
4. Update interval (backoff if fetch failed AND zero attachments)
5. Memory check → exit if over threshold
6. Sleep


## Implementation Status

### Done
- Daemon with adaptive intervals, memory monitoring
- RSS generation with feedparser validation, atomic writes
- Attachment downloads with size/timeout limits
- Config validation on startup
- Logging framework (no print statements)
- Pagination with smart stopping
- Database versioning via UNIQUE constraint + fetched_at
- SOCKS5 proxy support
- Indexes on fetched_at, date, file

### Backlog
- Predictive scheduling (analyze fetched_at patterns)
- SSH upload for mirrors
- Health monitoring endpoint/file
- Error recovery improvements (retry limits, backoff)

## Known Issues

**SSL verification disabled** (`verify=False`)
- Rationale: public data, trust source domain, MITM risk acceptable
- Status: accepted as-is

**No .env expressions**
- Cannot use `8*3600` in .env
- Must use `28800`
