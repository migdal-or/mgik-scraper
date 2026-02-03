# MGIK Scraper

Election committee news monitor with predictive scheduling and RSS feed generation.

## Overview

A web scraper for the Moscow City Election Commission (MosGorIzbirKom) that monitors news publications, predicts when new content will appear, and serves the data via RSS. Built to handle intermittent website availability.

## Features

- **Background daemon** with adaptive scheduling
  - Exponential backoff on complete failures
  - Normal interval on partial success (attachments downloaded)
- **RSS 2.0 feed generation**
  - Generated when new records OR new attachments
  - Skipped only when no new content (optimization)
- **Smart PDF attachment downloads**
  - Consecutive failure threshold
  - Runs regardless of fetch result
- **Memory monitoring** with suicide threshold (automatic restart)
- **Change detection** and version tracking
- **Logging** with file rotation
- **SOCKS5 proxy** support
- **Fail-fast configuration** (no defaults)

## Quick Start

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd mgik-scraper

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings
```

### Configuration

Create a `.env` file with the following variables:

```bash
# API Configuration
MGIK_NEWS_URL=https://example.com/api
MGIK_HEADERS={ "User-Agent": "Mozilla/5.0...", "Accept": "application/json" }
MGIK_DB_PATH=./mgik_news.db
REQUEST_TIMEOUT=30
MGIK_EARLIEST_DATE=2025-01-01

# Proxy Configuration (optional - all 4 required if using proxy)
MGIK_PROXY_HOST=
MGIK_PROXY_PORT=
MGIK_PROXY_USER=
MGIK_PROXY_PASS=

# Scheduler Configuration
SCHEDULER_DEFAULT_INTERVAL=28800  # 8 hours in seconds
SCHEDULER_MAX_INTERVAL=28800
SCHEDULER_MAX_MEMORY_MB=500

# RSS Feed Configuration
OUTPUT_PATH=./mgik-feed.xml
OUTPUT_MAX_ITEMS=100
MGIK_BASE_URL=https://www.mosgorizbirkom.ru
RSS_FEED_TITLE=MGIK Decisions Feed
RSS_FEED_DESCRIPTION=Moscow City Election Commission decisions

# Attachment Configuration
ATTACHMENTS_DIR=./attachments
ATTACHMENTS_MAX_FAILURES=3

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=./mgik-scraper.log
LOG_MAX_BYTES=10485760  # 10 MB
LOG_BACKUP_COUNT=5
```

### Manual database intervention
`sqlite3 mgik_news.db "DELETE FROM decisions WHERE mgik_id IN ('1', '2');"`

### Running

```bash
# Daemon mode (background loop with scheduler)
python daemon.py

# Or with nohup
nohup python daemon.py &

# Legacy CLI mode (one-shot scrape)
python mgik_scraper.py
```

### Daemon Workflow

The daemon executes the following cycle:

1. **Fetch news** from API → database (returns new record count or None on error)
2. **Download attachments** - runs regardless of fetch result (returns download count)
3. **Generate RSS feed** - only when new records > 0 OR new attachments > 0
4. **Update interval** - reset to default, then apply exponential backoff if fetch failed AND 0 attachments
5. **Memory check** - exit if threshold exceeded (suicide pattern for external restart)
6. **Sleep** - wait until next cycle with adaptive interval

## Documentation

- **Technical Details**: See [claude.md](claude.md) for architecture, implementation details, and development guide
- **Roadmap**: See [claude.md](claude.md#development-roadmap) for planned features and implementation phases

## Contributing

Contributions welcome! Please ensure:
- Code follows existing style
- Type hints are properly used
- Tests are added for new features
- Documentation is updated

See [claude.md](claude.md) for detailed technical context and development guidelines.

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0).

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.

## Contact

t.me/raopheefah, x.com/raopheefah
