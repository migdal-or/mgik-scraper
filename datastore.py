import sqlite3
import json
from typing import List, Dict
from datetime import datetime
from datetime import timezone
import os
from dotenv import load_dotenv


load_dotenv()
db_path = os.getenv("MGIK_DB_PATH", "mgik_decisions.db")


class DecisionsDatabase:
    def __init__(self):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
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
                    fetched_at TEXT
                )
                """
            )

    def save_decisions(self, decisions: List[Dict]) -> None:
        """Insert decision only if an identical row does not already exist."""
        fetched_at = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            for item in decisions:
                mgik_id = str(item.get("id"))
                name = item.get("name")
                number = item.get("number")
                date = item.get("date")
                file = item.get("file")

                cur = conn.execute(
                    """
                    SELECT 1 FROM decisions
                    WHERE mgik_id = ?
                      AND name = ?
                      AND number = ?
                      AND date = ?
                      AND file = ?
                    LIMIT 1
                    """,
                    (mgik_id, name, number, date, file),
                )
                if cur.fetchone():
                    continue  # exact same decision version already stored
                else:
                    conn.execute(
                        """
                    INSERT INTO decisions
                    (mgik_id, name, number, date, file, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                        (mgik_id, name, number, date, file, fetched_at),
                    )
            conn.commit()
