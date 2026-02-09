"""
Tests for datastore module
"""

import importlib
import sqlite3
import time
import os
from pathlib import Path
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
import datastore
from datastore import build_pdf_url

FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestBuildPdfUrl:
    """Tests for build_pdf_url function"""

    def test_build_pdf_url_with_leading_slash(self):
        """Test URL building with leading slash in file path"""
        result = build_pdf_url(
            "https://www.example.com/api/news", "/upload/documents/file.pdf"
        )
        assert result == "https://www.example.com/upload/documents/file.pdf"

    def test_build_pdf_url_without_leading_slash(self):
        """Test URL building without leading slash in file path"""
        result = build_pdf_url(
            "https://www.example.com/api/news", "upload/documents/file.pdf"
        )
        assert result == "https://www.example.com/upload/documents/file.pdf"

    def test_build_pdf_url_preserves_scheme(self):
        """Test that scheme (http/https) is preserved"""
        result = build_pdf_url("http://www.example.com/api/news", "/upload/file.pdf")
        assert result.startswith("http://")

    def test_build_pdf_url_with_port(self):
        """Test URL building with custom port"""
        result = build_pdf_url(
            "https://www.example.com:8080/api/news", "/upload/file.pdf"
        )
        assert result == "https://www.example.com:8080/upload/file.pdf"


class TestDecisionsDatabase:
    """Tests for DecisionsDatabase class"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing"""
        db_path = tmp_path / "test.db"

        # Patch module-level variables directly (cleaner than reload)
        with patch.object(datastore, "db_path", str(db_path)):
            with patch.object(
                datastore, "mgik_news_url", "https://www.example.com/api/news"
            ):
                db = datastore.DecisionsDatabase()
                yield db

    def test_init_db_creates_table(self, temp_db):
        """Test that database initialization creates decisions table"""
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='decisions'"
            )
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "decisions"

    def test_save_decisions_new_records(self, temp_db):
        """Test saving new decisions to database"""
        decisions = [
            {
                "id": "123",
                "name": "Test Decision",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "/upload/test.pdf",
            }
        ]

        count = temp_db.save_decisions(decisions)

        assert count == 1

        # Verify record was saved
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM decisions")
            assert cursor.fetchone()[0] == 1

    def test_save_decisions_duplicates_ignored(self, temp_db):
        """Test that duplicate decisions are ignored"""
        decision = {
            "id": "123",
            "name": "Test Decision",
            "number": "1/2025",
            "date": "2025-01-15",
            "file": "/upload/test.pdf",
        }

        # Insert first time
        count1 = temp_db.save_decisions([decision])
        assert count1 == 1

        # Insert same decision again
        count2 = temp_db.save_decisions([decision])
        assert count2 == 0  # Should be ignored

        # Verify only one record exists
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM decisions")
            assert cursor.fetchone()[0] == 1

    def test_save_decisions_adds_fetched_at(self, temp_db):
        """Test that fetched_at timestamp is added automatically"""
        decisions = [
            {
                "id": "123",
                "name": "Test Decision",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "/upload/test.pdf",
            }
        ]

        temp_db.save_decisions(decisions)

        # Verify fetched_at was added
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT fetched_at FROM decisions")
            fetched_at = cursor.fetchone()[0]
            assert fetched_at is not None
            # Verify it's a valid ISO timestamp
            datetime.fromisoformat(fetched_at)

    def test_save_decisions_builds_full_pdf_url(self, temp_db):
        """Test that relative file paths are converted to full URLs"""
        decisions = [
            {
                "id": "123",
                "name": "Test Decision",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "/upload/test.pdf",
            }
        ]

        temp_db.save_decisions(decisions)

        # Verify full URL was saved
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT file FROM decisions")
            file_url = cursor.fetchone()[0]
            assert file_url.startswith("https://")
            assert "example.com" in file_url
            assert file_url.endswith("/upload/test.pdf")

    def test_get_all_files(self, temp_db):
        """Test retrieving all unique file URLs"""
        decisions = [
            {
                "id": "1",
                "name": "Decision 1",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "/upload/file1.pdf",
            },
            {
                "id": "2",
                "name": "Decision 2",
                "number": "2/2025",
                "date": "2025-01-16",
                "file": "/upload/file2.pdf",
            },
            {
                "id": "3",
                "name": "Decision 3",
                "number": "3/2025",
                "date": "2025-01-17",
                "file": "/upload/file1.pdf",  # Duplicate file
            },
        ]

        temp_db.save_decisions(decisions)
        files = temp_db.get_all_files()

        # Should return unique files only
        assert len(files) == 2
        assert any("file1.pdf" in f for f in files)
        assert any("file2.pdf" in f for f in files)

    def test_get_all_returns_all_fields(self, temp_db):
        """Test get_all returns all decision fields"""
        decisions = [
            {
                "id": "123",
                "name": "Test Decision",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "/upload/test.pdf",
            }
        ]

        temp_db.save_decisions(decisions)
        all_decisions = temp_db.get_all()

        assert len(all_decisions) == 1
        decision = all_decisions[0]
        assert decision["mgik_id"] == "123"
        assert decision["name"] == "Test Decision"
        assert decision["number"] == "1/2025"
        assert decision["date"] == "2025-01-15"
        assert "test.pdf" in decision["file"]
        assert decision["fetched_at"] is not None

    def test_get_all_orders_by_newest_first(self, temp_db):
        """Test get_all returns decisions ordered by fetched_at DESC"""

        # Insert first decision
        temp_db.save_decisions(
            [
                {
                    "id": "1",
                    "name": "Old Decision",
                    "number": "1/2025",
                    "date": "2025-01-15",
                    "file": "/upload/old.pdf",
                }
            ]
        )

        # Wait a bit to ensure different timestamps
        time.sleep(0.1)

        # Insert second decision
        temp_db.save_decisions(
            [
                {
                    "id": "2",
                    "name": "New Decision",
                    "number": "2/2025",
                    "date": "2025-01-16",
                    "file": "/upload/new.pdf",
                }
            ]
        )

        all_decisions = temp_db.get_all()

        # First result should be the newer one
        assert all_decisions[0]["name"] == "New Decision"
        assert all_decisions[1]["name"] == "Old Decision"

    def test_save_multiple_decisions_at_once(self, temp_db):
        """Test saving multiple decisions in one call"""
        decisions = [
            {
                "id": str(i),
                "name": f"Decision {i}",
                "number": f"{i}/2025",
                "date": "2025-01-15",
                "file": f"/upload/file{i}.pdf",
            }
            for i in range(10)
        ]

        count = temp_db.save_decisions(decisions)

        assert count == 10

        # Verify all records were saved
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM decisions")
            assert cursor.fetchone()[0] == 10

    def test_versioning_same_id_different_content(self, temp_db):
        """Test that same ID with different content creates new version"""
        # First version
        temp_db.save_decisions(
            [
                {
                    "id": "123",
                    "name": "Original Name",
                    "number": "1/2025",
                    "date": "2025-01-15",
                    "file": "/upload/test.pdf",
                }
            ]
        )

        # Modified version (same ID, different name)
        temp_db.save_decisions(
            [
                {
                    "id": "123",
                    "name": "Modified Name",
                    "number": "1/2025",
                    "date": "2025-01-15",
                    "file": "/upload/test.pdf",
                }
            ]
        )

        # Both versions should be stored
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM decisions")
            assert cursor.fetchone()[0] == 2


class TestTimezoneConfiguration:
    """Tests for timezone configuration"""

    def test_timezone_loads_from_config(self):
        """Test that timezone from config loads into datastore object"""
        # Save original
        original_tz = str(datastore.mgik_timezone)

        # Test with Moscow
        with patch.dict(os.environ, {"MGIK_TIMEZONE": "Europe/Moscow"}, clear=False):
            importlib.reload(datastore)
            assert datastore.mgik_timezone == ZoneInfo("Europe/Moscow")
            assert str(datastore.mgik_timezone) == "Europe/Moscow"

        # Restore original
        with patch.dict(os.environ, {"MGIK_TIMEZONE": original_tz}, clear=False):
            importlib.reload(datastore)

    def test_different_timezones_load_correctly(self):
        """Test that different timezone names load into datastore object"""
        # Save original
        original_tz = str(datastore.mgik_timezone)

        test_timezones = ["UTC", "America/New_York", "Asia/Tokyo"]

        for tz_name in test_timezones:
            with patch.dict(os.environ, {"MGIK_TIMEZONE": tz_name}, clear=False):
                importlib.reload(datastore)
                # Verify the timezone object is loaded correctly
                assert datastore.mgik_timezone == ZoneInfo(tz_name)
                assert str(datastore.mgik_timezone) == tz_name

        # Restore original
        with patch.dict(os.environ, {"MGIK_TIMEZONE": original_tz}, clear=False):
            importlib.reload(datastore)

    def test_invalid_timezone_fails_on_reload(self):
        """Test that invalid timezone name fails when loading"""
        # Save original
        original_tz = str(datastore.mgik_timezone)

        try:
            with patch.dict(
                os.environ, {"MGIK_TIMEZONE": "Invalid/Timezone"}, clear=False
            ):
                # Should raise exception when reloading with invalid timezone
                with pytest.raises(Exception):  # ZoneInfo error
                    importlib.reload(datastore)
        finally:
            # Restore original
            with patch.dict(os.environ, {"MGIK_TIMEZONE": original_tz}, clear=False):
                importlib.reload(datastore)


class TestTimestampStorage:
    """Tests for timestamp storage in configured timezone"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing"""
        db_path = tmp_path / "test.db"

        with patch.object(datastore, "db_path", str(db_path)):
            with patch.object(
                datastore, "mgik_news_url", "https://www.example.com/api/news"
            ):
                db = datastore.DecisionsDatabase()
                yield db

    def test_fetched_at_stores_moscow_time_not_utc(self, temp_db):
        """Test that fetched_at stores Moscow local time, not UTC"""
        # Mock datetime.now to return a specific Moscow time
        moscow_tz = ZoneInfo("Europe/Moscow")
        mock_time = datetime(2026, 2, 9, 15, 30, 0, tzinfo=moscow_tz)  # 15:30 MSK

        with patch("datastore.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_time
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

            decisions = [
                {
                    "id": "123",
                    "name": "Test Decision",
                    "number": "1/2025",
                    "date": "2025-01-15",
                    "file": "/upload/test.pdf",
                }
            ]

            temp_db.save_decisions(decisions)

        # Verify the stored timestamp reflects Moscow time (hour 15), not UTC
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT fetched_at FROM decisions")
            fetched_at_str = cursor.fetchone()[0]

            # Parse the stored timestamp
            stored_dt = datetime.fromisoformat(fetched_at_str)

            # The hour should be 15 (Moscow), not 12 (UTC)
            assert stored_dt.hour == 15, f"Expected hour 15 (MSK), got {stored_dt.hour}"

    def test_moscow_midnight_stores_as_zero_not_21_or_23(self, temp_db):
        """
        CRITICAL: Test the bug fix - Moscow midnight (00:00) should store as 00:00,
        not as 21:00 or 23:00 (which would be the UTC equivalent)
        """
        # Mock datetime.now to return Moscow midnight
        moscow_tz = ZoneInfo("Europe/Moscow")
        mock_time = datetime(2026, 2, 9, 0, 0, 0, tzinfo=moscow_tz)  # 00:00 MSK

        with patch("datastore.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_time
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

            decisions = [
                {
                    "id": "123",
                    "name": "Midnight Decision",
                    "number": "1/2025",
                    "date": "2025-01-15",
                    "file": "/upload/test.pdf",
                }
            ]

            temp_db.save_decisions(decisions)

        # Verify the stored timestamp has hour 00, not 21 or 23
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT fetched_at FROM decisions")
            fetched_at_str = cursor.fetchone()[0]

            # Parse the stored timestamp
            stored_dt = datetime.fromisoformat(fetched_at_str)

            # CRITICAL: Hour must be 0 (Moscow midnight), not 21 or 23 (UTC)
            assert (
                stored_dt.hour == 0
            ), f"Moscow midnight stored as hour {stored_dt.hour}, not 0 (the bug!)"

    def test_stored_timestamp_parseable_for_hour_extraction(self, temp_db):
        """Test that stored timestamps can be parsed back for hour extraction"""
        decisions = [
            {
                "id": "123",
                "name": "Test Decision",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "/upload/test.pdf",
            }
        ]

        temp_db.save_decisions(decisions)

        # Retrieve and parse the timestamp
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT fetched_at FROM decisions")
            fetched_at_str = cursor.fetchone()[0]

            # Should be parseable
            parsed_dt = datetime.fromisoformat(fetched_at_str)

            # Should be able to extract hour
            assert isinstance(parsed_dt.hour, int)
            assert 0 <= parsed_dt.hour <= 23

    def test_multiple_timezones_store_correctly(self, temp_db):
        """Test that different configured timezones store their local time"""
        test_cases = [
            ("Europe/Moscow", 10, 10),  # 10:00 MSK → stores as 10
            ("UTC", 10, 10),  # 10:00 UTC → stores as 10
            ("America/New_York", 10, 10),  # 10:00 EST → stores as 10
        ]

        for tz_name, input_hour, expected_hour in test_cases:
            with patch.object(datastore, "mgik_timezone", ZoneInfo(tz_name)):
                mock_time = datetime(
                    2026, 2, 9, input_hour, 0, 0, tzinfo=ZoneInfo(tz_name)
                )

                with patch("datastore.datetime") as mock_datetime:
                    mock_datetime.now.return_value = mock_time
                    mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

                    decisions = [
                        {
                            "id": f"test_{tz_name}",
                            "name": f"Decision {tz_name}",
                            "number": "1/2025",
                            "date": "2025-01-15",
                            "file": f"/upload/{tz_name}.pdf",
                        }
                    ]

                    temp_db.save_decisions(decisions)

                    # Verify stored hour matches local time
                    with sqlite3.connect(temp_db.db_path) as conn:
                        cursor = conn.execute(
                            "SELECT fetched_at FROM decisions WHERE mgik_id = ?",
                            (f"test_{tz_name}",),
                        )
                        fetched_at_str = cursor.fetchone()[0]
                        stored_dt = datetime.fromisoformat(fetched_at_str)

                        assert (
                            stored_dt.hour == expected_hour
                        ), f"{tz_name}: Expected hour {expected_hour}, got {stored_dt.hour}"
