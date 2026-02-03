"""
Pytest configuration and shared fixtures
"""

import pytest
import os
import tempfile
import shutil


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch, tmp_path):
    """
    Setup test environment with minimal required environment variables.
    Runs automatically for all tests.
    """
    # Set minimal required env vars to prevent import errors
    test_env = {
        "MGIK_NEWS_URL": "https://test.example.com/api/news",
        "MGIK_DB_PATH": str(tmp_path / "test.db"),
        "MGIK_HEADERS": "{}",
        "REQUEST_TIMEOUT": "30",
        "MGIK_EARLIEST_DATE": "2025-01-01",
        "SCHEDULER_DEFAULT_INTERVAL": "1800",
        "SCHEDULER_MAX_INTERVAL": "28800",
        "SCHEDULER_MAX_MEMORY_MB": "500",
        "OUTPUT_PATH": str(tmp_path / "feed.xml"),
        "OUTPUT_MAX_ITEMS": "100",
        "MGIK_BASE_URL": "https://www.mosgorizbirkom.ru",
        "RSS_FEED_TITLE": "Test Feed",
        "RSS_FEED_DESCRIPTION": "Test Description",
        "ATTACHMENTS_DIR": str(tmp_path / "attachments"),
        "ATTACHMENTS_MAX_FAILURES": "3",
        "LOG_LEVEL": "INFO",
        "LOG_FILE": str(tmp_path / "test.log"),
        "LOG_MAX_BYTES": "10485760",
        "LOG_BACKUP_COUNT": "5",
    }

    for key, value in test_env.items():
        monkeypatch.setenv(key, value)


@pytest.fixture
def sample_api_response():
    """Sample valid API response with items and pagination"""
    return {
        "items": [
            {
                "id": "69395",
                "name": "Решение о регистрации",
                "number": "123/2025-П",
                "date": "2025-01-15",
                "file": "/documents/69395/CustomDocument_69395.pdf",
            },
            {
                "id": "69384",
                "name": "Решение об отказе",
                "number": "124/2025-П",
                "date": "2025-01-14",
                "file": "/documents/69384/CustomDocument_69384.pdf",
            },
        ],
        "meta": {
            "next": "https://test.example.com/api/news?page=2",
            "total": 50,
        },
    }


@pytest.fixture
def sample_api_response_last_page():
    """Sample API response for last page (no next link)"""
    return {
        "items": [
            {
                "id": "69300",
                "name": "Старое решение",
                "number": "100/2025-П",
                "date": "2025-01-10",
                "file": "/documents/69300/CustomDocument_69300.pdf",
            }
        ],
        "meta": {
            "next": None,
            "total": 50,
        },
    }


@pytest.fixture
def sample_api_response_empty():
    """Sample API response with no items"""
    return {
        "items": [],
        "meta": {
            "next": None,
            "total": 0,
        },
    }


@pytest.fixture
def sample_decisions():
    """Sample decisions list for database testing"""
    return [
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
            "file": "/upload/file3.pdf",
        },
    ]


@pytest.fixture
def mock_pdf_content():
    """Mock PDF file content"""
    return b"%PDF-1.4\n%\xE2\xE3\xCF\xD3\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>endobj\n%%EOF"
