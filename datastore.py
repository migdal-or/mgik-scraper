"""
Decisions database for versioning scraped content.

Stores every decision snapshot with fetch timestamps to detect changes.
Supports deduplication of identical versions across multiple scrapes.
"""

import sqlite3
from typing import List, Dict
from datetime import datetime
from datetime import timezone
import os
from urllib.parse import urlparse
from urllib.parse import urljoin
from dotenv import load_dotenv


def build_pdf_url(news_url: str, file_path: str) -> str:
    """
    Builds full PDF URL from base news URL and file path.
    """
    parsed = urlparse(news_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"

    return urljoin(base_domain, file_path.lstrip("/"))


load_dotenv()
db_path = os.getenv("MGIK_DB_PATH")
_mgik_news_url = os.getenv("MGIK_NEWS_URL")
if not _mgik_news_url:
    raise ValueError("MGIK_NEWS_URL variable must be set in a .env file")
mgik_news_url: str = _mgik_news_url


class DecisionsDatabase:
    """
    SQLite database for storing MosGorIzbirKom decisions with full versioning.

    - Persists every unique decision version (mgik_id + content fields)
    - Deduplicates identical decisions across fetches
    - Tracks UTC fetch timestamps for temporal analysis
    - Provides ordered access to decision history
    """

    def __init__(self):
        if not db_path:
            raise ValueError("MGIK_DB_PATH variable must be set in a .env file")
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database connection and create decisions table if needed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mgik_id TEXT,
                    name TEXT,
                    number TEXT,
                    date TEXT,
                    file TEXT,
                    fetched_at TEXT,
                    UNIQUE(mgik_id, name, number, date, file)
                )
                """
            )

    def save_decisions(self, decisions: List[Dict]) -> int:
        """
        Save new decision versions, skipping exact duplicates.
        Args:
            decisions: List of decision dicts from API with 'id', 'name', 'number', 'date', 'file'

        Returns:
            int: Number of new records inserted (duplicates skipped).

        Deduplication handled by UNIQUE constraint with INSERT OR IGNORE.
        """

        fetched_at = datetime.now(timezone.utc).isoformat()

        rows = []
        for item in decisions:
            mgik_id = str(item.get("id"))
            name = str(item.get("name"))
            number = str(item.get("number"))
            date = str(item.get("date"))
            file = str(item.get("file"))
            pdf_url = build_pdf_url(mgik_news_url, file)

            rows.append((mgik_id, name, number, date, pdf_url, fetched_at))

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.executemany(
                """
                INSERT OR IGNORE INTO decisions
                (mgik_id, name, number, date, file, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
            conn.commit()
            return cursor.rowcount

    def get_all_files(self) -> List[str]:
        """
        Fetch all unique decision file URLs.

        Returns:
            List of unique file URLs.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT DISTINCT file
                FROM decisions
                """
            )
            return [row[0] for row in cursor.fetchall()]

    def get_all(self) -> List[Dict]:
        """
        Fetch all decision versions ordered by newest first.

        Returns:
            List of dicts with internal_id, mgik_id, name, number, date, file, fetched_at
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """
                SELECT internal_id, mgik_id, name, number, date, file, fetched_at
                FROM decisions
                ORDER BY fetched_at DESC
                """
            )
            return [
                {
                    "internal_id": row[0],
                    "mgik_id": row[1],
                    "name": row[2],
                    "number": row[3],
                    "date": row[4],
                    "file": row[5],
                    "fetched_at": row[6],
                }
                for row in cursor.fetchall()
            ]
