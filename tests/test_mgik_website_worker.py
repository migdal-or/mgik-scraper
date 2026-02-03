"""
Tests for mgik_website_worker module
"""

import json
from unittest.mock import Mock
from unittest.mock import patch
from unittest.mock import mock_open
from datetime import datetime
import requests
from mgik_website_worker import (
    fetch_mgik_news,
    fetch_attachment,
    load_decisions_from_web_to_database,
    save_to_database,
)


class TestFetchMgikNews:
    """Tests for fetch_mgik_news function"""

    @patch("mgik_website_worker.requests.get")
    def test_fetch_success(self, mock_get):
        """Test successful API fetch"""
        mock_response = Mock()
        mock_response.json.return_value = {
            "items": [{"id": "123", "name": "Test Decision"}],
            "meta": {"next": None},
        }
        mock_get.return_value = mock_response

        result = fetch_mgik_news("http://test.com/api")

        assert result["status"] == "success"
        assert "items" in result["data"]
        assert len(result["data"]["items"]) == 1

    @patch("mgik_website_worker.requests.get")
    def test_fetch_timeout(self, mock_get):
        """Test timeout handling"""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = fetch_mgik_news("http://test.com/api")

        assert result["status"] == "error"
        assert "timeout" in result["error"].lower()

    @patch("mgik_website_worker.requests.get")
    def test_fetch_connection_error(self, mock_get):
        """Test connection error handling"""
        mock_get.side_effect = requests.exceptions.ConnectionError()

        result = fetch_mgik_news("http://test.com/api")

        assert result["status"] == "error"
        assert "connection failed" in result["error"].lower()

    @patch("mgik_website_worker.requests.get")
    def test_fetch_http_error(self, mock_get):
        """Test HTTP error handling (4xx/5xx)"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.side_effect = requests.exceptions.HTTPError(response=mock_response)

        result = fetch_mgik_news("http://test.com/api")

        assert result["status"] == "error"
        assert "HTTP" in result["error"]
        assert "404" in result["error"]

    @patch("mgik_website_worker.requests.get")
    def test_fetch_invalid_json(self, mock_get):
        """Test invalid JSON response handling"""
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("test", "test", 0)
        mock_get.return_value = mock_response

        result = fetch_mgik_news("http://test.com/api")

        assert result["status"] == "error"
        assert "invalid JSON".lower() in result["error"].lower()


class TestFetchAttachment:
    """Tests for fetch_attachment function"""

    @patch("mgik_website_worker.requests.get")
    @patch("builtins.open", new_callable=mock_open)
    def test_fetch_attachment_success(self, mock_file, mock_get):
        """Test successful PDF download"""
        mock_response = Mock()
        mock_response.iter_content.return_value = [b"PDF content chunk 1", b"chunk 2"]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch_attachment("http://test.com/file.pdf", "/tmp/test.pdf")

        assert result["status"] == "success"
        mock_file.assert_called_once_with("/tmp/test.pdf", "wb")
        mock_get.assert_called_once()

    @patch("mgik_website_worker.requests.get")
    def test_fetch_attachment_timeout(self, mock_get):
        """Test attachment download timeout"""
        mock_get.side_effect = requests.exceptions.Timeout()

        result = fetch_attachment("http://test.com/file.pdf", "/tmp/test.pdf")

        assert result["status"] == "error"
        assert "Timeout" in result["error"]

    @patch("mgik_website_worker.requests.get")
    def test_fetch_attachment_connection_error(self, mock_get):
        """Test attachment download connection error"""
        mock_get.side_effect = requests.exceptions.ConnectionError("Network error")

        result = fetch_attachment("http://test.com/file.pdf", "/tmp/test.pdf")

        assert result["status"] == "error"
        assert "Connection failed" in result["error"]

    @patch("mgik_website_worker.requests.get")
    def test_fetch_attachment_http_error(self, mock_get):
        """Test attachment download HTTP error"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=mock_response
        )
        mock_get.return_value = mock_response

        result = fetch_attachment("http://test.com/file.pdf", "/tmp/test.pdf")

        assert result["status"] == "error"
        assert "HTTP 404" in result["error"]

    @patch("mgik_website_worker.requests.get")
    @patch("builtins.open", side_effect=OSError("Disk full"))
    def test_fetch_attachment_file_error(self, _mock_file, mock_get):
        """Test attachment download file system error"""
        mock_response = Mock()
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch_attachment("http://test.com/file.pdf", "/tmp/test.pdf")

        assert result["status"] == "error"
        assert "File error" in result["error"]

    @patch("mgik_website_worker.requests.get")
    def test_fetch_attachment_file_too_large(self, mock_get):
        """Test that file size limit is enforced"""
        mock_response = Mock()
        mock_response.headers = {"Content-Length": str(100 * 1024 * 1024)}  # 100 MB
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch_attachment(
            "http://test.com/huge.pdf", "/tmp/test.pdf", max_size_mb=50
        )

        assert result["status"] == "error"
        assert "File too large" in result["error"]
        assert "100" in result["error"]
        assert "50" in result["error"]

    @patch("mgik_website_worker.requests.get")
    @patch("builtins.open", new_callable=mock_open)
    def test_fetch_attachment_within_size_limit(self, mock_file, mock_get):
        """Test that files within size limit are downloaded"""
        mock_response = Mock()
        mock_response.headers = {"Content-Length": str(10 * 1024 * 1024)}  # 10 MB
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch_attachment(
            "http://test.com/small.pdf", "/tmp/test.pdf", max_size_mb=50
        )

        assert result["status"] == "success"
        mock_file.assert_called_once_with("/tmp/test.pdf", "wb")

    @patch("mgik_website_worker.requests.get")
    @patch("builtins.open", new_callable=mock_open)
    def test_fetch_attachment_no_content_length(self, mock_file, mock_get):
        """Test that downloads proceed when Content-Length header is missing"""
        mock_response = Mock()
        mock_response.headers = {}  # No Content-Length header
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = fetch_attachment(
            "http://test.com/file.pdf", "/tmp/test.pdf", max_size_mb=50
        )

        assert result["status"] == "success"
        mock_file.assert_called_once_with("/tmp/test.pdf", "wb")

    @patch("mgik_website_worker.requests.get")
    def test_fetch_attachment_custom_timeout(self, mock_get):
        """Test that custom timeout is used"""
        mock_response = Mock()
        mock_response.iter_content.return_value = [b"content"]
        mock_response.raise_for_status = Mock()
        mock_response.headers = {}
        mock_get.return_value = mock_response

        with patch("builtins.open", new_callable=mock_open):
            fetch_attachment(
                "http://test.com/file.pdf", "/tmp/test.pdf", timeout=600
            )

        # Verify timeout parameter was passed to requests.get
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["timeout"] == 600


class TestSaveToDatabase:
    """Tests for save_to_database function"""

    def test_save_new_decisions(self, tmp_path):
        """Test saving new decisions to database"""
        import datastore

        # Setup temporary database - patch the module-level db_path variable
        db_path = tmp_path / "test_save.db"

        with patch.object(datastore, "db_path", str(db_path)):
            items = [
                {
                    "id": "1",
                    "name": "Decision 1",
                    "number": "1/2025",
                    "date": "2025-01-01",
                    "file": "/test1.pdf",
                },
                {
                    "id": "2",
                    "name": "Decision 2",
                    "number": "2/2025",
                    "date": "2025-01-02",
                    "file": "/test2.pdf",
                },
            ]

            result = save_to_database(items)

            # Should save both new items
            assert result == 2

            # Verify they're in the database
            db = datastore.DecisionsDatabase()
            all_decisions = db.get_all()
            assert len(all_decisions) == 2

    def test_save_with_duplicates(self, tmp_path):
        """Test saving decisions with duplicates"""
        import datastore

        # Setup temporary database - patch the module-level db_path variable
        db_path = tmp_path / "test_duplicates.db"

        with patch.object(datastore, "db_path", str(db_path)):
            # First batch: 2 new items
            items_batch1 = [
                {
                    "id": "1",
                    "name": "Decision 1",
                    "number": "1/2025",
                    "date": "2025-01-01",
                    "file": "/test1.pdf",
                },
                {
                    "id": "2",
                    "name": "Decision 2",
                    "number": "2/2025",
                    "date": "2025-01-02",
                    "file": "/test2.pdf",
                },
            ]

            result1 = save_to_database(items_batch1)
            assert result1 == 2  # Both new

            # Second batch: 1 duplicate, 1 new
            items_batch2 = [
                {
                    "id": "1",
                    "name": "Decision 1",
                    "number": "1/2025",
                    "date": "2025-01-01",
                    "file": "/test1.pdf",
                },  # Duplicate
                {
                    "id": "3",
                    "name": "Decision 3",
                    "number": "3/2025",
                    "date": "2025-01-03",
                    "file": "/test3.pdf",
                },  # New
            ]

            result2 = save_to_database(items_batch2)
            assert result2 == 1  # Only 1 new (duplicate ignored)

            # Verify total count
            db = datastore.DecisionsDatabase()
            all_decisions = db.get_all()
            assert len(all_decisions) == 3  # Total: 3 unique decisions


class TestLoadDecisionsFromWebToDatabase:
    """Tests for load_decisions_from_web_to_database function"""

    @patch("mgik_website_worker.fetch_mgik_news")
    @patch("mgik_website_worker.save_to_database")
    def test_pagination_single_page(self, mock_save, mock_fetch):
        """Test pagination with single page"""
        mock_fetch.return_value = {
            "status": "success",
            "data": {
                "items": [
                    {
                        "id": "1",
                        "name": "Decision 1",
                        "number": "1/1",
                        "date": "2025-01-15",
                        "file": "/test.pdf",
                    }
                ],
                "meta": {"next": None},
            },
        }
        mock_save.return_value = 1

        result = load_decisions_from_web_to_database()

        assert result == 1
        mock_fetch.assert_called_once()
        mock_save.assert_called_once()

    @patch("mgik_website_worker.fetch_mgik_news")
    @patch("mgik_website_worker.save_to_database")
    def test_pagination_multiple_pages(self, mock_save, mock_fetch):
        """Test pagination with multiple pages"""
        mock_fetch.side_effect = [
            {
                "status": "success",
                "data": {
                    "items": [
                        {
                            "id": "1",
                            "name": "Decision 1",
                            "number": "1/1",
                            "date": "2025-01-15",
                            "file": "/test1.pdf",
                        }
                    ],
                    "meta": {"next": "http://test.com/page2"},
                },
            },
            {
                "status": "success",
                "data": {
                    "items": [
                        {
                            "id": "2",
                            "name": "Decision 2",
                            "number": "2/2",
                            "date": "2025-01-14",
                            "file": "/test2.pdf",
                        }
                    ],
                    "meta": {"next": None},
                },
            },
        ]
        mock_save.side_effect = [1, 1]

        result = load_decisions_from_web_to_database()

        assert result == 2
        assert mock_fetch.call_count == 2
        assert mock_save.call_count == 2

    @patch("mgik_website_worker.fetch_mgik_news")
    def test_pagination_fetch_error(self, mock_fetch):
        """Test pagination stops on fetch error"""
        mock_fetch.return_value = {
            "status": "error",
            "error": "Connection failed",
        }

        result = load_decisions_from_web_to_database()

        assert result is None
        mock_fetch.assert_called_once()

    @patch("mgik_website_worker.fetch_mgik_news")
    @patch("mgik_website_worker.save_to_database")
    def test_pagination_stops_on_no_items(self, mock_save, mock_fetch):
        """Test pagination stops when no items in response"""
        mock_fetch.return_value = {
            "status": "success",
            "data": {
                "items": [],
                "meta": {"next": "http://test.com/page2"},
            },
        }

        result = load_decisions_from_web_to_database()

        assert result == 0
        mock_fetch.assert_called_once()
        mock_save.assert_not_called()

    @patch("mgik_website_worker.fetch_mgik_news")
    @patch("mgik_website_worker.save_to_database")
    @patch("mgik_website_worker.earliest_date", datetime(2025, 1, 10))
    def test_pagination_stops_on_old_dates(self, mock_save, mock_fetch):
        """Test pagination stops when oldest item is before earliest_date"""
        mock_fetch.return_value = {
            "status": "success",
            "data": {
                "items": [
                    {
                        "id": "1",
                        "name": "Old Decision",
                        "number": "1/1",
                        "date": "2025-01-05",
                        "file": "/old.pdf",
                    }
                ],
                "meta": {"next": "http://test.com/page2"},
            },
        }

        result = load_decisions_from_web_to_database()

        assert result == 0
        mock_fetch.assert_called_once()
        mock_save.assert_not_called()

    @patch("mgik_website_worker.fetch_mgik_news")
    @patch("mgik_website_worker.save_to_database")
    def test_pagination_stops_on_no_new_records(self, mock_save, mock_fetch):
        """Test pagination stops when all records are duplicates"""
        mock_fetch.side_effect = [
            {
                "status": "success",
                "data": {
                    "items": [
                        {
                            "id": "1",
                            "name": "Decision 1",
                            "number": "1/1",
                            "date": "2025-01-15",
                            "file": "/test.pdf",
                        }
                    ],
                    "meta": {"next": "http://test.com/page2"},
                },
            }
        ]
        mock_save.return_value = 0  # All duplicates

        result = load_decisions_from_web_to_database()

        assert result == 0
        mock_fetch.assert_called_once()
        mock_save.assert_called_once()
