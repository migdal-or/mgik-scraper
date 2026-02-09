"""
Pytest configuration - environment setup only
Environment config loaded from tests/fixtures/test_env_config.json
"""

import json
from pathlib import Path
import pytest


@pytest.fixture(autouse=True)
def setup_test_env(monkeypatch, tmp_path):
    """
    Setup test environment with minimal required environment variables.
    Runs automatically for all tests.
    Loads config from fixtures/test_env_config.json and adds tmp_path values.
    """
    # Load base env config from fixture
    fixtures_dir = Path(__file__).parent / "fixtures"
    with open(fixtures_dir / "test_env_config.json", encoding="utf-8") as f:
        test_env = json.load(f)

    # Add tmp_path dependent values
    test_env["MGIK_DB_PATH"] = str(tmp_path / "test.db")
    test_env["OUTPUT_PATH"] = str(tmp_path / "feed.xml")
    test_env["ATTACHMENTS_DIR"] = str(tmp_path / "attachments")
    test_env["LOG_FILE"] = str(tmp_path / "test.log")

    for key, value in test_env.items():
        monkeypatch.setenv(key, str(value))
