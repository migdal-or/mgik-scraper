"""
Integration tests for timezone handling across modules
"""

import sqlite3
from unittest.mock import patch
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from datastore import DecisionsDatabase
from datastore import mgik_timezone as datastore_tz
from prediction import PublicationPredictor
from prediction import mgik_timezone as prediction_tz
import datastore


class TestTimezoneIntegration:
    """End-to-end integration tests for timezone consistency"""

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

    def test_end_to_end_moscow_time_consistency(self, temp_db):
        """
        Test complete flow: save decision → verify stored time → use in prediction
        All times should be in Moscow timezone throughout
        """
        moscow_tz = ZoneInfo("Europe/Moscow")

        # Step 1: Save decision at specific Moscow time
        save_time = datetime(2026, 2, 9, 14, 30, 0, tzinfo=moscow_tz)

        with patch("datastore.datetime") as mock_datetime:
            mock_datetime.now.return_value = save_time
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

            decisions = [
                {
                    "id": "integration_test",
                    "name": "Integration Test Decision",
                    "number": "1/2026",
                    "date": "2026-02-09",
                    "file": "/upload/test.pdf",
                }
            ]

            temp_db.save_decisions(decisions)

        # Step 2: Verify stored timestamp is in Moscow time
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute("SELECT fetched_at FROM decisions")
            fetched_at_str = cursor.fetchone()[0]

            stored_dt = datetime.fromisoformat(fetched_at_str)

            # Hour should be 14 (Moscow), not 11 (UTC)
            assert (
                stored_dt.hour == 14
            ), f"Stored hour should be 14 (MSK), got {stored_dt.hour}"

        # Step 3: Use in prediction at same hour
        predictor = PublicationPredictor(temp_db, base_interval=1800)

        # Analyze patterns without mocking - should work with real fromisoformat
        patterns = predictor.analyze_patterns()

        # Fetch patterns should show activity at hour 14
        hour_distribution = patterns["fetch"]["hour"]
        assert (
            hour_distribution[14] == 1
        ), "Hour 14 should have activity from saved decision"

        # No activity at UTC-equivalent hours
        assert hour_distribution[11] == 0, "Hour 11 (UTC) should have no activity"

    def test_midnight_bug_fix_integration(self, temp_db):
        """
        Integration test for the critical midnight bug fix:
        Save at 00:00 MSK → stored as 00:00 → prediction sees hour 0
        """
        moscow_tz = ZoneInfo("Europe/Moscow")

        # Save at Moscow midnight
        moscow_midnight = datetime(2026, 2, 9, 0, 0, 0, tzinfo=moscow_tz)

        with patch("datastore.datetime") as mock_datetime:
            mock_datetime.now.return_value = moscow_midnight
            mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

            decisions = [
                {
                    "id": "midnight_integration",
                    "name": "Midnight Decision",
                    "number": "1/2026",
                    "date": "2026-02-09",
                    "file": "/upload/midnight.pdf",
                }
            ]

            temp_db.save_decisions(decisions)

        # Verify stored as hour 0
        with sqlite3.connect(temp_db.db_path) as conn:
            cursor = conn.execute(
                "SELECT fetched_at FROM decisions WHERE mgik_id = ?",
                ("midnight_integration",),
            )
            fetched_at_str = cursor.fetchone()[0]
            stored_dt = datetime.fromisoformat(fetched_at_str)

            assert (
                stored_dt.hour == 0
            ), f"Midnight should store as hour 0, got {stored_dt.hour}"

        # Verify prediction sees hour 0, not 21 or 23
        predictor = PublicationPredictor(temp_db, base_interval=1800)
        patterns = predictor.analyze_patterns()

        hour_dist = patterns["fetch"]["hour"]
        assert hour_dist[0] == 1, "Hour 0 should have count 1"
        assert hour_dist[21] == 0, "Hour 21 (old UTC bug) should be 0"
        assert hour_dist[23] == 0, "Hour 23 (old UTC bug) should be 0"

    def test_multiple_saves_at_different_moscow_hours(self, temp_db):
        """
        Test multiple saves at different Moscow hours maintain consistency
        """
        moscow_tz = ZoneInfo("Europe/Moscow")
        test_hours = [0, 6, 12, 18, 23]

        # Save decisions at various Moscow hours
        for hour in test_hours:
            mock_time = datetime(2026, 2, 9, hour, 0, 0, tzinfo=moscow_tz)

            with patch("datastore.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_time
                mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

                decisions = [
                    {
                        "id": f"hour_{hour}",
                        "name": f"Decision at {hour}:00",
                        "number": f"{hour}/2026",
                        "date": "2026-02-09",
                        "file": f"/upload/hour_{hour}.pdf",
                    }
                ]

                temp_db.save_decisions(decisions)

        # Verify all hours are stored correctly
        with sqlite3.connect(temp_db.db_path) as conn:
            for hour in test_hours:
                cursor = conn.execute(
                    "SELECT fetched_at FROM decisions WHERE mgik_id = ?",
                    (f"hour_{hour}",),
                )
                fetched_at_str = cursor.fetchone()[0]
                stored_dt = datetime.fromisoformat(fetched_at_str)

                assert (
                    stored_dt.hour == hour
                ), f"Hour {hour} should store as {hour}, got {stored_dt.hour}"

        # Verify prediction sees all correct hours
        predictor = PublicationPredictor(temp_db, base_interval=1800)
        patterns = predictor.analyze_patterns()

        hour_dist = patterns["fetch"]["hour"]
        for hour in test_hours:
            assert (
                hour_dist[hour] == 1
            ), f"Hour {hour} should have count 1, got {hour_dist[hour]}"

    def test_cross_module_timezone_consistency(self):
        """
        Test that all modules use the same timezone instance
        """
        # Both modules should import the same mgik_timezone
        assert (
            datastore_tz == prediction_tz
        ), "datastore and prediction should use same timezone"

        # Should be Europe/Moscow (from env)
        assert (
            str(datastore_tz) == "Europe/Moscow"
        ), f"Expected Europe/Moscow, got {datastore_tz}"

    def test_prediction_coefficient_with_moscow_time(self, temp_db):
        """
        Test that prediction coefficient calculation works with Moscow time
        """
        moscow_tz = ZoneInfo("Europe/Moscow")

        # Save multiple decisions at hour 10 Moscow
        for i in range(5):
            mock_time = datetime(2026, 2, 10 + i, 10, 0, 0, tzinfo=moscow_tz)

            with patch("datastore.datetime") as mock_datetime:
                mock_datetime.now.return_value = mock_time
                mock_datetime.fromisoformat.side_effect = datetime.fromisoformat

                decisions = [
                    {
                        "id": f"coef_test_{i}",
                        "name": f"Decision {i}",
                        "number": f"{i}/2026",
                        "date": f"2026-02-{10+i:02d}",
                        "file": f"/upload/test_{i}.pdf",
                    }
                ]

                temp_db.save_decisions(decisions)

        # Check coefficient at hour 10 Moscow
        predictor = PublicationPredictor(temp_db, base_interval=1800)

        check_time = datetime(2026, 2, 15, 10, 30, 0, tzinfo=moscow_tz)

        # Create custom datetime class that mocks now() but keeps isinstance working
        class DateTimeMeta(type):
            """Metaclass that makes isinstance work with real datetime instances"""

            def __instancecheck__(cls, instance):
                return isinstance(instance, datetime)

        class MockDateTime(datetime, metaclass=DateTimeMeta):
            """Mock datetime class that overrides now() for testing"""

            @classmethod
            def now(cls, tz=None):
                return check_time

            @classmethod
            def fromisoformat(cls, date_string):
                return datetime.fromisoformat(date_string)

        with patch("prediction.datetime", MockDateTime):
            coefficient = predictor.get_coefficient()

            # Should be > 1.0 because hour 10 has activity
            assert (
                coefficient > 1.0
            ), f"Expected coefficient > 1.0 at active hour, got {coefficient}"

        # Check coefficient at hour 20 Moscow (no activity)
        check_time_20h = datetime(2026, 2, 15, 20, 30, 0, tzinfo=moscow_tz)

        class MockDateTime20(datetime, metaclass=DateTimeMeta):
            """Mock datetime class for hour 20 testing"""

            @classmethod
            def now(cls, tz=None):
                return check_time_20h

            @classmethod
            def fromisoformat(cls, date_string):
                return datetime.fromisoformat(date_string)

        with patch("prediction.datetime", MockDateTime20):
            coefficient_20h = predictor.get_coefficient()

            # Should be lower at inactive hour
            assert (
                coefficient_20h < coefficient
            ), "Inactive hour should have lower coefficient"

    def test_timezone_offset_in_stored_timestamps(self, temp_db):
        """
        Test that stored ISO timestamps can include timezone offset info
        """
        # Manually insert timestamp with explicit offset
        with sqlite3.connect(temp_db.db_path) as conn:
            conn.execute(
                """
                INSERT INTO decisions (mgik_id, name, number, date, file, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "offset_test",
                    "Offset Test",
                    "1/2026",
                    "2026-02-09",
                    "https://example.com/test.pdf",
                    "2026-02-09T15:30:00+03:00",  # Explicit +03:00
                ),
            )

        # Prediction should parse this correctly
        predictor = PublicationPredictor(temp_db, base_interval=1800)
        patterns = predictor.analyze_patterns()

        # Hour should be 15 (from the explicit timestamp)
        hour_dist = patterns["fetch"]["hour"]
        assert hour_dist[15] == 1, f"Hour 15 should have count 1, got {hour_dist[15]}"
