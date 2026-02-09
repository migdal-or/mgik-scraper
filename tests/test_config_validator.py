"""
Tests for config_validator module
"""

import json
from pathlib import Path
import pytest
from config_validator import ConfigValidator
from config_validator import ConfigValidationError
from config_validator import validate_config


class TestConfigValidator:
    """Tests for ConfigValidator class"""

    @pytest.fixture
    def valid_config(self, tmp_path):
        """Create a valid configuration using test_env_config.json"""
        fixtures_dir = Path(__file__).parent / "fixtures"
        with open(fixtures_dir / "test_env_config.json", encoding="utf-8") as f:
            config = json.load(f)

        # Add tmp_path dependent values
        config["MGIK_DB_PATH"] = str(tmp_path / "test.db")
        config["OUTPUT_PATH"] = str(tmp_path / "feed.xml")
        config["ATTACHMENTS_DIR"] = str(tmp_path / "attachments")
        config["LOG_FILE"] = str(tmp_path / "test.log")

        # Convert string values to appropriate types
        config["SCHEDULER_DEFAULT_INTERVAL"] = int(config["SCHEDULER_DEFAULT_INTERVAL"])
        config["SCHEDULER_MAX_INTERVAL"] = int(config["SCHEDULER_MAX_INTERVAL"])
        config["SCHEDULER_BACKOFF_MULTIPLIER"] = float(
            config["SCHEDULER_BACKOFF_MULTIPLIER"]
        )
        config["SCHEDULER_MAX_MEMORY_MB"] = int(config["SCHEDULER_MAX_MEMORY_MB"])
        config["OUTPUT_MAX_ITEMS"] = int(config["OUTPUT_MAX_ITEMS"])
        config["ATTACHMENTS_MAX_FAILURES"] = int(config["ATTACHMENTS_MAX_FAILURES"])
        config["ATTACHMENTS_MAX_SIZE_MB"] = int(config["ATTACHMENTS_MAX_SIZE_MB"])
        config["ATTACHMENTS_TIMEOUT"] = int(config["ATTACHMENTS_TIMEOUT"])
        config["LOG_MAX_BYTES"] = int(config["LOG_MAX_BYTES"])
        config["LOG_BACKUP_COUNT"] = int(config["LOG_BACKUP_COUNT"])

        return config

    def test_valid_config_passes(self, valid_config):
        """Test that a valid configuration passes validation"""
        validator = ConfigValidator(valid_config)
        validator.validate_all()  # Should not raise

    def test_validate_config_function(self, valid_config):
        """Test the validate_config convenience function"""
        validate_config(valid_config)  # Should not raise

    def test_missing_required_string(self, valid_config):
        """Test that missing required string is caught"""
        del valid_config["MGIK_NEWS_URL"]
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "MGIK_NEWS_URL" in str(exc_info.value)
        assert "required" in str(exc_info.value).lower()

    def test_empty_required_string(self, valid_config):
        """Test that empty required string is caught"""
        valid_config["RSS_FEED_TITLE"] = ""
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "RSS_FEED_TITLE" in str(exc_info.value)

    def test_whitespace_only_string(self, valid_config):
        """Test that whitespace-only string is caught"""
        valid_config["RSS_FEED_DESCRIPTION"] = "   "
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "RSS_FEED_DESCRIPTION" in str(exc_info.value)

    def test_missing_positive_int(self, valid_config):
        """Test that missing positive integer is caught"""
        del valid_config["SCHEDULER_DEFAULT_INTERVAL"]
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "SCHEDULER_DEFAULT_INTERVAL" in str(exc_info.value)

    def test_non_integer_value(self, valid_config):
        """Test that non-integer value is caught"""
        valid_config["OUTPUT_MAX_ITEMS"] = "100"  # String instead of int
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "OUTPUT_MAX_ITEMS" in str(exc_info.value)
        assert "integer" in str(exc_info.value).lower()

    def test_negative_integer(self, valid_config):
        """Test that negative integer is caught"""
        valid_config["SCHEDULER_DEFAULT_INTERVAL"] = -100
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "SCHEDULER_DEFAULT_INTERVAL" in str(exc_info.value)
        assert "positive" in str(exc_info.value).lower()

    def test_zero_integer(self, valid_config):
        """Test that zero is caught for positive integers"""
        valid_config["OUTPUT_MAX_ITEMS"] = 0
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "OUTPUT_MAX_ITEMS" in str(exc_info.value)
        assert "positive" in str(exc_info.value).lower()

    def test_max_interval_less_than_default(self, valid_config):
        """Test that max interval < default interval is caught"""
        valid_config["SCHEDULER_DEFAULT_INTERVAL"] = 28800
        valid_config["SCHEDULER_MAX_INTERVAL"] = 3600
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "SCHEDULER_MAX_INTERVAL" in str(exc_info.value)
        assert "SCHEDULER_DEFAULT_INTERVAL" in str(exc_info.value)

    def test_memory_limit_too_low(self, valid_config):
        """Test that memory limit below 100MB is warned"""
        valid_config["SCHEDULER_MAX_MEMORY_MB"] = 50
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "SCHEDULER_MAX_MEMORY_MB" in str(exc_info.value)
        assert "too low" in str(exc_info.value).lower()

    def test_memory_limit_too_high(self, valid_config):
        """Test that memory limit above 10GB is warned"""
        valid_config["SCHEDULER_MAX_MEMORY_MB"] = 20480  # 20 GB
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "SCHEDULER_MAX_MEMORY_MB" in str(exc_info.value)
        assert "too high" in str(exc_info.value).lower()

    def test_rss_items_zero(self, valid_config):
        """Test that OUTPUT_MAX_ITEMS of 0 is caught"""
        valid_config["OUTPUT_MAX_ITEMS"] = 0
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "OUTPUT_MAX_ITEMS" in str(exc_info.value)

    def test_rss_items_too_high(self, valid_config):
        """Test that OUTPUT_MAX_ITEMS above 1000 is warned"""
        valid_config["OUTPUT_MAX_ITEMS"] = 5000
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "OUTPUT_MAX_ITEMS" in str(exc_info.value)
        assert "too high" in str(exc_info.value).lower()

    def test_invalid_log_level(self, valid_config):
        """Test that invalid log level is caught"""
        valid_config["LOG_LEVEL"] = "VERBOSE"
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "LOG_LEVEL" in str(exc_info.value)
        assert "VERBOSE" in str(exc_info.value)

    def test_valid_log_levels(self, valid_config):
        """Test that all valid log levels pass"""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            valid_config["LOG_LEVEL"] = level
            validator = ConfigValidator(valid_config)
            validator.validate_all()  # Should not raise

    def test_url_without_protocol(self, valid_config):
        """Test that URL without http(s):// is caught"""
        valid_config["MGIK_NEWS_URL"] = "example.com/api"
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "MGIK_NEWS_URL" in str(exc_info.value)
        assert "http" in str(exc_info.value).lower()

    def test_http_and_https_urls_valid(self, valid_config):
        """Test that both HTTP and HTTPS URLs are valid"""
        valid_config["MGIK_NEWS_URL"] = "http://example.com/api"
        valid_config["MGIK_BASE_URL"] = "https://example.com"
        validator = ConfigValidator(valid_config)
        validator.validate_all()  # Should not raise

    def test_nonexistent_parent_directory(self, valid_config, tmp_path):
        """Test that file with nonexistent parent directory is caught"""
        valid_config["OUTPUT_PATH"] = str(
            tmp_path / "nonexistent" / "subdir" / "feed.xml"
        )
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "OUTPUT_PATH" in str(exc_info.value)
        assert "does not exist" in str(exc_info.value).lower()

    def test_attachments_dir_created(self, valid_config, tmp_path):
        """Test that ATTACHMENTS_DIR is created if it doesn't exist"""
        attachments_dir = tmp_path / "new_attachments"
        valid_config["ATTACHMENTS_DIR"] = str(attachments_dir)

        assert not attachments_dir.exists()

        validator = ConfigValidator(valid_config)
        validator.validate_all()

        # Directory should be created
        assert attachments_dir.exists()
        assert attachments_dir.is_dir()

    def test_file_path_is_directory(self, valid_config, tmp_path):
        """Test that file path pointing to directory is caught"""
        dir_path = tmp_path / "somedir"
        dir_path.mkdir()
        valid_config["OUTPUT_PATH"] = str(dir_path)
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "OUTPUT_PATH" in str(exc_info.value)
        assert "not a file" in str(exc_info.value).lower()

    def test_directory_path_is_file(self, valid_config, tmp_path):
        """Test that directory path pointing to file is caught"""
        file_path = tmp_path / "somefile"
        file_path.touch()
        valid_config["ATTACHMENTS_DIR"] = str(file_path)
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "ATTACHMENTS_DIR" in str(exc_info.value)
        assert "not a directory" in str(exc_info.value).lower()

    def test_multiple_errors_reported(self, valid_config):
        """Test that multiple validation errors are all reported"""
        # Create multiple errors
        del valid_config["MGIK_NEWS_URL"]
        valid_config["OUTPUT_MAX_ITEMS"] = -5
        valid_config["LOG_LEVEL"] = "INVALID"

        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        error_msg = str(exc_info.value)
        # All three errors should be present
        assert "MGIK_NEWS_URL" in error_msg
        assert "OUTPUT_MAX_ITEMS" in error_msg
        assert "LOG_LEVEL" in error_msg

    def test_writable_file_permissions(self, valid_config, tmp_path):
        """Test that existing writable file passes validation"""
        existing_file = tmp_path / "existing.xml"
        existing_file.touch()
        valid_config["OUTPUT_PATH"] = str(existing_file)

        validator = ConfigValidator(valid_config)
        validator.validate_all()  # Should not raise

    def test_edge_case_memory_limits(self, valid_config):
        """Test memory limit edge cases"""
        # Exactly 100 MB should pass
        valid_config["SCHEDULER_MAX_MEMORY_MB"] = 100
        validator = ConfigValidator(valid_config)
        validator.validate_all()

        # Exactly 10 GB (10240 MB) should pass
        valid_config["SCHEDULER_MAX_MEMORY_MB"] = 10240
        validator = ConfigValidator(valid_config)
        validator.validate_all()

    def test_edge_case_rss_items(self, valid_config):
        """Test RSS items edge cases"""
        # Exactly 1 should pass
        valid_config["OUTPUT_MAX_ITEMS"] = 1
        validator = ConfigValidator(valid_config)
        validator.validate_all()

        # Exactly 1000 should pass
        valid_config["OUTPUT_MAX_ITEMS"] = 1000
        validator = ConfigValidator(valid_config)
        validator.validate_all()

    def test_attachment_size_too_low(self, valid_config):
        """Test that attachment size below 1MB is caught"""
        valid_config["ATTACHMENTS_MAX_SIZE_MB"] = 0
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "ATTACHMENTS_MAX_SIZE_MB" in str(exc_info.value)
        assert "too low" in str(exc_info.value).lower()

    def test_attachment_size_too_high(self, valid_config):
        """Test that attachment size above 500MB is caught"""
        valid_config["ATTACHMENTS_MAX_SIZE_MB"] = 1000
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "ATTACHMENTS_MAX_SIZE_MB" in str(exc_info.value)
        assert "too high" in str(exc_info.value).lower()

    def test_attachment_size_edge_cases(self, valid_config):
        """Test attachment size edge cases"""
        # Exactly 1 MB should pass
        valid_config["ATTACHMENTS_MAX_SIZE_MB"] = 1
        validator = ConfigValidator(valid_config)
        validator.validate_all()

        # Exactly 500 MB should pass
        valid_config["ATTACHMENTS_MAX_SIZE_MB"] = 500
        validator = ConfigValidator(valid_config)
        validator.validate_all()

    def test_attachment_timeout_too_low(self, valid_config):
        """Test that attachment timeout below 10s is caught"""
        valid_config["ATTACHMENTS_TIMEOUT"] = 5
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "ATTACHMENTS_TIMEOUT" in str(exc_info.value)
        assert "too low" in str(exc_info.value).lower()

    def test_attachment_timeout_too_high(self, valid_config):
        """Test that attachment timeout above 3600s is caught"""
        valid_config["ATTACHMENTS_TIMEOUT"] = 7200
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "ATTACHMENTS_TIMEOUT" in str(exc_info.value)
        assert "too high" in str(exc_info.value).lower()

    def test_attachment_timeout_edge_cases(self, valid_config):
        """Test attachment timeout edge cases"""
        # Exactly 10s should pass
        valid_config["ATTACHMENTS_TIMEOUT"] = 10
        validator = ConfigValidator(valid_config)
        validator.validate_all()

        # Exactly 3600s (1 hour) should pass
        valid_config["ATTACHMENTS_TIMEOUT"] = 3600
        validator = ConfigValidator(valid_config)
        validator.validate_all()

    def test_timezone_must_be_set(self, valid_config):
        """Test that MGIK_TIMEZONE must be set"""
        del valid_config["MGIK_TIMEZONE"]
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "MGIK_TIMEZONE" in str(exc_info.value)

    def test_valid_timezone_names(self, valid_config):
        """Test that valid IANA timezone names pass validation"""
        valid_timezones = ["Europe/Moscow", "UTC", "America/New_York", "Asia/Tokyo"]

        for tz_name in valid_timezones:
            valid_config["MGIK_TIMEZONE"] = tz_name
            validator = ConfigValidator(valid_config)
            validator.validate_all()  # Should not raise

    def test_invalid_timezone_name(self, valid_config):
        """Test that invalid timezone names are caught"""
        valid_config["MGIK_TIMEZONE"] = "Invalid/Timezone"
        validator = ConfigValidator(valid_config)

        with pytest.raises(ConfigValidationError) as exc_info:
            validator.validate_all()

        assert "MGIK_TIMEZONE" in str(exc_info.value)
        assert "Invalid/Timezone" in str(exc_info.value)
