# MGIK Scraper
Election committee news monitor with prediction-based scheduling.

## Features
- JSON news scraping with change detection
- Publication timing prediction
- RSS feed generation
- Attachment downloading

## Quick Start
```bash
pip install -r requirements.txt
python -m election_monitor
```

## Description

I have an election committee website.
They publish their news with something like react as a json file available on direct link with headers, and links to actual news articles and downloadable attachments.
They like to publish a bunch of news and poweroff their website.
I want a customizable web scraper which would do the following:
Analyze the news history and come up with a probability on when the new articles would appear, and increase the fetch checks number for that period of time.
Maintain regular checks between minimum one in 8 hours and maximum one in 10 minutes.
Store the retrieved data in a local database file, aggregating changed versions together with old and deleted ones.
Serve the retrieved newsfeed as an RSS stream available for rss readers.
Maintain a database of attachments and schedule a downloader to try to fetch them when the source website is online and retry attempts until succeeded.

Config must be stored in a env file.