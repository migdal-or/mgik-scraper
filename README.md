# MGIK Scraper

Election committee news monitor with predictive scheduling and RSS feed generation.

## Overview

A web scraper for the Moscow City Election Commission (MosGorIzbirKom) that monitors news publications, predicts when new content will appear, and serves the data via RSS. Built to handle intermittent website availability.

## Features

- Smart JSON news scraping with automatic pagination
- Change detection and version tracking
- Predictive scheduling (planned)
- RSS feed generation (planned)
- PDF attachment management
- SOCKS5 proxy support

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
