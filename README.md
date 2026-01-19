# MGIK Scraper

Election committee news monitor with predictive scheduling and RSS feed generation.

## Overview

A web scraper for the Moscow City Election Commission (MosGorIzbirKom) that monitors news publications, predicts when new content will appear, and serves the data via RSS. Built to handle intermittent website availability.

## Features

### Core Functionality
- **Smart Scraping**: Fetches JSON news data with automatic pagination
- **Change Detection**: Tracks all versions of news items (updates, deletions)
- **Predictive Scheduling**: Analyzes publication patterns to anticipate new content
- **Adaptive Polling**: Adjusts check frequency from 8 hours (idle) to 10 minutes (active)
- **RSS Feed**: Serves news as an RSS stream for feed readers
- **Attachment Management**: Downloads and retries PDF attachments until successful

### Current Status
✅ Implemented:
- JSON API scraping with pagination
- SQLite database with versioning
- Duplicate detection
- Proxy support (SOCKS5)
- Environment-based configuration
- PDF URL construction

⏳ Planned:
- Predictive scheduling based on historical patterns
- Adaptive check frequency
- RSS feed generation
- Background daemon mode
- Attachment retry logic

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
# Required: API endpoint
MGIK_NEWS_URL=https://example.com/api

# Required: HTTP headers (JSON format)
MGIK_HEADERS={ "User-Agent": "Mozilla/5.0...", "Accept": "application/json" }

# Required: Database path
MGIK_DB_PATH=/path/to/database.db

# Optional: Request timeout (default: 30)
REQUEST_TIMEOUT=30

# Optional: Stop pagination at this date
MGIK_EARLIEST_DATE=2025-01-01

# Optional: SOCKS5 proxy (all 4 required if using proxy)
MGIK_PROXY_HOST=proxy.example.com
MGIK_PROXY_PORT=1080
MGIK_PROXY_USER=username
MGIK_PROXY_PASS=password123
```

### Running

```bash
# Single run (fetches latest news)
python mgik_scraper.py

# Enable attachment downloads (uncomment in mgik_scraper.py first)
# python mgik_scraper.py
```

## Architecture

### Components

**[mgik_scraper.py](mgik_scraper.py)** - Main entry point
- Orchestrates the scraping and processing workflow

**[mgik_website_worker.py](mgik_website_worker.py)** - Core scraping logic
- `fetch_mgik_news()`: HTTP fetching with proxy/timeout support
- `load_decisions_from_web_to_database()`: Paginated API scraping
- `process_attachments()`: PDF download manager

**[datastore.py](datastore.py)** - Database layer
- `DecisionsDatabase`: SQLite wrapper with versioning
- Automatic deduplication via UNIQUE constraints
- Full history tracking (all versions preserved)

### Data Flow

```
API Endpoint → fetch_mgik_news() → JSON Response
                                      ↓
                                  Pagination
                                      ↓
                              save_to_database()
                                      ↓
                              SQLite Database
                                      ↓
                          process_attachments()
                                      ↓
                            attachments/*.pdf
```

### Database Schema

```sql
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mgik_id TEXT,
    name TEXT,
    number TEXT,
    date TEXT,
    file TEXT,
    UNIQUE(mgik_id, name, number, date, file)
)
```

## Use Case

The Moscow City Election Commission publishes news as JSON via a React-based website. The site frequently goes offline after publishing batches of news. This scraper:

1. **Monitors** the API endpoint for new publications
2. **Predicts** when new content will appear based on historical patterns
3. **Adapts** its checking frequency to catch updates quickly
4. **Preserves** all versions of news items (handles updates/deletions)
5. **Downloads** PDF attachments, retrying when the site is unavailable
6. **Serves** the aggregated news as an RSS feed for readers

## Development

### Requirements
- Python 3.13+
- Dependencies listed in [requirements.txt](requirements.txt)

### Project Structure
```
mgik-scraper/
├── mgik_scraper.py          # Entry point
├── mgik_website_worker.py   # Scraping logic
├── datastore.py             # Database layer
├── requirements.txt         # Python dependencies
├── .env                     # Configuration (gitignored)
├── .env.example             # Configuration template
├── mgik_news.db            # SQLite database
├── attachments/            # Downloaded PDFs
└── tests/                  # Test suite (planned)
```

### Testing
```bash
# Run tests (when implemented)
pytest

# Manual test script
python test_process_attachments.py
```

### Known Issues
- SSL verification disabled (`verify=False`) - exercise caution
- No automated tests yet (pytest installed but tests/ empty)
- Attachment processing currently disabled in main script
- Uses `print()` instead of `logging` module

## Roadmap

### Phase 1: Core Stability
- [ ] Enable and test attachment downloads
- [ ] Add proper logging framework
- [ ] Write pytest test suite
- [ ] Enable SSL verification or document why it's disabled

### Phase 2: Smart Scheduling
- [ ] Implement publication pattern analysis
- [ ] Build predictive model for next publish time
- [ ] Add adaptive polling frequency (8h ↔ 10min)
- [ ] Create background daemon mode

### Phase 3: RSS & Distribution
- [ ] Generate RSS feed from database
  - RSS items based on: name, number, date
  - Include both original MGIK URL and mirror URL in description
- [ ] Add HTTP server for RSS endpoint
- [ ] Implement attachment retry logic
- [ ] SSH upload for downloaded attachments
  - Upload PDFs to predefined SSH location with external HTTP server
  - Configure URL pattern mapping (e.g., `CustomDocument12345.pdf` → `http://server1.domain1/path1/CustomDocument12345.pdf`)
  - Dual-URL listing to avoid committee blacklisting
- [ ] Add health check/monitoring

## Contributing

Contributions welcome! Please ensure:
- Code follows existing style
- Type hints are properly used
- Tests are added for new features
- Documentation is updated

## License

This project is licensed under the GNU General Public License v3.0 (GPL-3.0) - see below for details.

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.

## Contact

t.me/raopheefah, x.com/raopheefah
