"""
Tests for prediction module - timezone-aware hour matching
"""

import sqlite3
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from prediction import PublicationPredictor
from datastore import DecisionsDatabase
import datastore


class TestPredictionTimezone:
    """Tests for timezone-aware prediction logic"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create temporary database for testing"""
        db_path = tmp_path / "test.db"

        with patch.object(datastore, "db_path", str(db_path)):
            with patch.object(
                datastore, "mgik_news_url", "https://www.example.com/api/news"
            ):
                db = DecisionsDatabase()
                yield db

    @pytest.fixture
    def predictor(self, temp_db):
        """Create predictor instance with test database"""
        return PublicationPredictor(temp_db, base_interval=1800)

    def test_current_time_uses_configured_timezone(self, predictor):
        """Test that get_coefficient uses datetime.now(mgik_timezone)"""
        moscow_tz = ZoneInfo("Europe/Moscow")
        mock_time = datetime(2026, 2, 9, 15, 30, 0, tzinfo=moscow_tz)

        with patch("prediction.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_time
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

            # Call get_coefficient - should use mocked Moscow time
            _coefficient = predictor.get_coefficient()

            # Verify datetime.now was called with timezone
            mock_datetime.now.assert_called_once_with(datastore.mgik_timezone)

    def test_moscow_midnight_hour_extraction(self, temp_db, predictor):
        """
        CRITICAL: Test that 00:00 Moscow hour is correctly extracted,
        not confused with 21:00 or 23:00 UTC
        """
        # Insert record with Moscow midnight timestamp
        moscow_tz = ZoneInfo("Europe/Moscow")
        midnight_msk = datetime(2026, 2, 9, 0, 0, 0, tzinfo=moscow_tz)

        # Mock datetime.now to return midnight when saving
        with patch("datastore.datetime") as mock_datetime:
            mock_datetime.now.return_value = midnight_msk
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

            decisions = [
                {
                    "id": "midnight_test",
                    "name": "Midnight Decision",
                    "number": "1/2025",
                    "date": "2026-02-09",
                    "file": "/upload/test.pdf",
                }
            ]
            temp_db.save_decisions(decisions)

        # Analyze patterns - should extract hour 0, not 21 or 23
        patterns = predictor.analyze_patterns()

        # Check fetch patterns (from fetched_at timestamps)
        hour_distribution = patterns["fetch"]["hour"]

        # Hour 0 should have count 1
        assert hour_distribution[0] == 1, "Hour 0 (midnight MSK) should have count 1"

        # Hours 21 and 23 should have count 0 (the bug would put count here)
        assert (
            hour_distribution[21] == 0
        ), "Hour 21 should be 0 (would be 1 if UTC bug exists)"
        assert (
            hour_distribution[23] == 0
        ), "Hour 23 should be 0 (would be 1 if UTC bug exists)"

    def test_hour_matching_same_timezone(self, temp_db, predictor):
        """Test that hour-based pattern matching works in same timezone"""
        moscow_tz = ZoneInfo("Europe/Moscow")

        # Insert records at various Moscow hours
        test_hours = [0, 6, 12, 18, 23]

        for hour in test_hours:
            mock_time = datetime(2026, 2, 9, hour, 0, 0, tzinfo=moscow_tz)

            with patch("datastore.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_time
                mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

                decisions = [
                    {
                        "id": f"test_hour_{hour}",
                        "name": f"Decision at hour {hour}",
                        "number": f"{hour}/2025",
                        "date": "2026-02-09",
                        "file": f"/upload/hour_{hour}.pdf",
                    }
                ]
                temp_db.save_decisions(decisions)

        # Verify all hours are stored correctly
        patterns = predictor.analyze_patterns()
        hour_distribution = patterns["fetch"]["hour"]

        for hour in test_hours:
            assert (
                hour_distribution[hour] == 1
            ), f"Hour {hour} MSK should have count 1, got {hour_distribution[hour]}"

    def test_coefficient_calculation_with_moscow_hours(self, temp_db, predictor):
        """Test that coefficient calculation uses Moscow hours correctly"""
        moscow_tz = ZoneInfo("Europe/Moscow")

        # Insert multiple records at hour 15 Moscow time
        for i in range(5):
            mock_time = datetime(2026, 2, 9 + i, 15, 0, 0, tzinfo=moscow_tz)

            with patch("datastore.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_time
                mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

                decisions = [
                    {
                        "id": f"test_{i}",
                        "name": f"Decision {i}",
                        "number": f"{i}/2025",
                        "date": f"2026-02-{9+i:02d}",
                        "file": f"/upload/test_{i}.pdf",
                    }
                ]
                temp_db.save_decisions(decisions)

        # Now check coefficient at hour 15 Moscow time
        current_time_15h = datetime(2026, 2, 14, 15, 0, 0, tzinfo=moscow_tz)

        # Create custom datetime class that mocks now() but keeps isinstance working
        class DateTimeMeta(type):
            """Metaclass that makes isinstance work with real datetime instances"""

            def __instancecheck__(cls, instance):
                return isinstance(instance, datetime)

        class MockDateTime(datetime, metaclass=DateTimeMeta):
            """Mock datetime class that overrides now() for testing"""

            @classmethod
            def now(cls, tz=None):
                return current_time_15h

            @classmethod
            def fromisoformat(cls, date_string):
                return datetime.fromisoformat(date_string)

        with patch("prediction.datetime", MockDateTime):
            coefficient = predictor.get_coefficient()

            # Should be > 1.0 because hour 15 has activity
            assert coefficient > 1.0, f"Expected coefficient > 1.0, got {coefficient}"

    def test_different_hour_no_match(self, temp_db, predictor):
        """Test that different hours don't incorrectly match"""
        moscow_tz = ZoneInfo("Europe/Moscow")

        # Insert records at hour 10
        mock_time = datetime(2026, 2, 9, 10, 0, 0, tzinfo=moscow_tz)

        with patch("datastore.datetime") as mock_datetime:
            mock_datetime.now.return_value = mock_time
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

            decisions = [
                {
                    "id": "test_10h",
                    "name": "Decision at 10h",
                    "number": "1/2025",
                    "date": "2026-02-09",
                    "file": "/upload/test.pdf",
                }
            ]
            temp_db.save_decisions(decisions)

        # Check coefficient at hour 20 (different hour)
        current_time_20h = datetime(2026, 2, 9, 20, 0, 0, tzinfo=moscow_tz)

        with patch("prediction.datetime") as mock_datetime:
            mock_datetime.now.return_value = current_time_20h
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

            patterns = predictor.analyze_patterns()

            # Hour component of score should be 0 (no hour 20 activity)
            fetch_patterns = patterns["fetch"]
            hour_20_count = fetch_patterns["hour"][20]
            assert hour_20_count == 0, "Hour 20 should have no activity"

    def test_parse_fetched_at_with_timezone_offset(self, temp_db, predictor):
        """Test that fetched_at timestamps with timezone offsets parse correctly"""
        # Manually insert a record with explicit timezone offset
        with sqlite3.connect(temp_db.db_path) as conn:
            conn.execute(
                """
                INSERT INTO decisions (mgik_id, name, number, date, file, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "manual_test",
                    "Manual Decision",
                    "1/2025",
                    "2026-02-09",
                    "https://example.com/test.pdf",
                    "2026-02-09T14:30:00+03:00",  # Explicit +03:00 offset
                ),
            )

        # Analyze patterns - should parse the timestamp correctly
        patterns = predictor.analyze_patterns()

        # Hour should be 14 (from the timestamp)
        hour_distribution = patterns["fetch"]["hour"]
        assert hour_distribution[14] == 1, "Hour 14 should have count 1"

    def test_analyze_patterns_returns_correct_structure(self, predictor):
        """Test that analyze_patterns returns the expected structure"""
        patterns = predictor.analyze_patterns()

        # Check top-level structure
        assert "decision" in patterns
        assert "fetch" in patterns

        # Check decision patterns structure
        assert "hour" in patterns["decision"]
        assert "dow" in patterns["decision"]
        assert "dom" in patterns["decision"]
        assert "month" in patterns["decision"]
        assert "doy" in patterns["decision"]

        # Check fetch patterns structure
        assert "hour" in patterns["fetch"]
        assert len(patterns["fetch"]["hour"]) == 24  # 24 hours

    def test_empty_database_returns_min_coefficient(self, temp_db):
        """Test that empty database returns minimum coefficient of 1.0"""
        predictor = PublicationPredictor(temp_db, base_interval=1800)

        coefficient = predictor.get_coefficient()

        # With no data, coefficient should be 1.0 (minimum)
        assert coefficient == 1.0, f"Expected coefficient 1.0, got {coefficient}"

    def test_utc_midnight_vs_moscow_midnight(self):
        """
        Test that UTC midnight and Moscow midnight are different hours
        This verifies the timezone is being respected
        """
        # Test UTC midnight (which would be 03:00 Moscow time)
        utc_tz = ZoneInfo("UTC")
        moscow_tz = ZoneInfo("Europe/Moscow")

        utc_midnight = datetime(2026, 2, 9, 0, 0, 0, tzinfo=utc_tz)  # 00:00 UTC
        moscow_midnight = datetime(
            2026, 2, 9, 0, 0, 0, tzinfo=moscow_tz
        )  # 00:00 MSK (21:00 UTC)

        # Convert UTC midnight to Moscow time
        utc_midnight_in_moscow = utc_midnight.astimezone(moscow_tz)

        # They should have different hours
        assert utc_midnight_in_moscow.hour != moscow_midnight.hour, (
            f"UTC midnight ({utc_midnight_in_moscow.hour}h MSK) "
            f"should differ from Moscow midnight ({moscow_midnight.hour}h MSK)"
        )

        # UTC midnight should be 03:00 in Moscow (UTC+3)
        assert (
            utc_midnight_in_moscow.hour == 3
        ), f"UTC midnight should be 03:00 MSK, got {utc_midnight_in_moscow.hour}:00"
