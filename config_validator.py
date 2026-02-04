"""
Configuration Validator for MGIK Scraper

Validates all configuration values on startup to fail fast with clear error messages.
Checks types, ranges, file paths, and logical constraints.
"""

import os
from pathlib import Path


class ConfigValidationError(Exception):
    """Raised when configuration validation fails"""


class ConfigValidator:
    """Validates configuration dictionary"""

    def __init__(self, config: dict):
        """
        Initialize validator with config

        Args:
            config: Configuration dictionary to validate
        """
        self.config = config
        self.errors = []

    def validate_all(self):
        """
        Validate all configuration values

        Raises:
            ConfigValidationError: If any validation fails
        """
        # Required string values (non-empty)
        self._validate_required_string("MGIK_NEWS_URL", "API endpoint URL")
        self._validate_required_string("MGIK_DB_PATH", "database file path")
        self._validate_required_string("OUTPUT_PATH", "RSS output file path")
        self._validate_required_string("MGIK_BASE_URL", "base URL for links")
        self._validate_required_string("RSS_FEED_TITLE", "RSS feed title")
        self._validate_required_string("RSS_FEED_DESCRIPTION", "RSS feed description")
        self._validate_required_string("ATTACHMENTS_DIR", "attachments directory path")
        self._validate_required_string("LOG_FILE", "log file path")
        self._validate_required_string("LOG_LEVEL", "logging level")

        # Positive integers
        self._validate_positive_int(
            "SCHEDULER_DEFAULT_INTERVAL", "default check interval"
        )
        self._validate_positive_int("SCHEDULER_MAX_INTERVAL", "maximum check interval")
        self._validate_positive_int(
            "SCHEDULER_MAX_MEMORY_MB", "memory suicide threshold"
        )

        # Positive floats
        self._validate_positive_float(
            "SCHEDULER_BACKOFF_MULTIPLIER", "backoff multiplier", min_value=1.0
        )
        self._validate_positive_int("OUTPUT_MAX_ITEMS", "max RSS items")
        self._validate_positive_int(
            "ATTACHMENTS_MAX_FAILURES", "max consecutive attachment failures"
        )
        self._validate_positive_int(
            "ATTACHMENTS_MAX_SIZE_MB", "max attachment file size"
        )
        self._validate_positive_int("ATTACHMENTS_TIMEOUT", "attachment download timeout")
        self._validate_positive_int("LOG_MAX_BYTES", "max log file size")
        self._validate_positive_int("LOG_BACKUP_COUNT", "number of log backups")

        # Logical constraints
        self._validate_interval_relationship()
        self._validate_reasonable_memory_limit()
        self._validate_reasonable_rss_items()
        self._validate_reasonable_attachment_size()
        self._validate_reasonable_attachment_timeout()

        # Path validations
        self._validate_writable_directory_path("ATTACHMENTS_DIR", create=True)
        self._validate_writable_file_path("OUTPUT_PATH")
        self._validate_writable_file_path("LOG_FILE")
        self._validate_writable_file_path("MGIK_DB_PATH")

        # Log level validation
        self._validate_log_level()

        # URL validations
        self._validate_url("MGIK_NEWS_URL")
        self._validate_url("MGIK_BASE_URL")

        # If any errors, raise with all error messages
        if self.errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(
                f"  - {error}" for error in self.errors
            )
            raise ConfigValidationError(error_msg)

    def _validate_required_string(self, key: str, description: str):
        """Validate that a required string value exists and is non-empty"""
        value = self.config.get(key)
        if not value or not isinstance(value, str) or not value.strip():
            self.errors.append(
                f"{key} ({description}) is required and must be non-empty"
            )

    def _validate_positive_int(self, key: str, description: str):
        """Validate that a value is a positive integer"""
        value = self.config.get(key)
        if value is None:
            self.errors.append(f"{key} ({description}) is required")
            return

        if not isinstance(value, int):
            self.errors.append(
                f"{key} ({description}) must be an integer, got {type(value).__name__}"
            )
            return

        if value <= 0:
            self.errors.append(f"{key} ({description}) must be positive, got {value}")

    def _validate_positive_float(
        self, key: str, description: str, min_value: float = 0.0
    ):
        """Validate that a value is a positive float >= min_value"""
        value = self.config.get(key)
        if value is None:
            self.errors.append(f"{key} ({description}) is required")
            return

        if not isinstance(value, (int, float)):
            self.errors.append(
                f"{key} ({description}) must be a number, got {type(value).__name__}"
            )
            return

        if value < min_value:
            self.errors.append(
                f"{key} ({description}) must be >= {min_value}, got {value}"
            )

    def _validate_interval_relationship(self):
        """Validate that max interval >= default interval"""
        default = self.config.get("SCHEDULER_DEFAULT_INTERVAL")
        maximum = self.config.get("SCHEDULER_MAX_INTERVAL")

        if (
            default
            and maximum
            and isinstance(default, int)
            and isinstance(maximum, int)
        ):
            if maximum < default:
                self.errors.append(
                    f"SCHEDULER_MAX_INTERVAL ({maximum}s) must be >= "
                    f"SCHEDULER_DEFAULT_INTERVAL ({default}s)"
                )

    def _validate_reasonable_memory_limit(self):
        """Validate that memory limit is reasonable (between 100MB and 10GB)"""
        memory_mb = self.config.get("SCHEDULER_MAX_MEMORY_MB")
        if isinstance(memory_mb, int):
            if memory_mb < 100:
                self.errors.append(
                    f"SCHEDULER_MAX_MEMORY_MB ({memory_mb}) is too low, "
                    "minimum recommended is 100 MB"
                )
            elif memory_mb > 10240:  # 10 GB
                self.errors.append(
                    f"SCHEDULER_MAX_MEMORY_MB ({memory_mb}) is too high, "
                    "maximum recommended is 10240 MB (10 GB)"
                )

    def _validate_reasonable_rss_items(self):
        """Validate that RSS item count is reasonable (between 1 and 1000)"""
        max_items = self.config.get("OUTPUT_MAX_ITEMS")
        if isinstance(max_items, int):
            if max_items < 1:
                self.errors.append(f"OUTPUT_MAX_ITEMS ({max_items}) must be at least 1")
            elif max_items > 1000:
                self.errors.append(
                    f"OUTPUT_MAX_ITEMS ({max_items}) is too high, "
                    "maximum recommended is 1000"
                )

    def _validate_reasonable_attachment_size(self):
        """Validate that attachment size limit is reasonable (between 1MB and 500MB)"""
        max_size_mb = self.config.get("ATTACHMENTS_MAX_SIZE_MB")
        if isinstance(max_size_mb, int):
            if max_size_mb < 1:
                self.errors.append(
                    f"ATTACHMENTS_MAX_SIZE_MB ({max_size_mb}) is too low, "
                    "minimum recommended is 1 MB"
                )
            elif max_size_mb > 500:
                self.errors.append(
                    f"ATTACHMENTS_MAX_SIZE_MB ({max_size_mb}) is too high, "
                    "maximum recommended is 500 MB"
                )

    def _validate_reasonable_attachment_timeout(self):
        """Validate that attachment timeout is reasonable (between 10s and 3600s)"""
        timeout = self.config.get("ATTACHMENTS_TIMEOUT")
        if isinstance(timeout, int):
            if timeout < 10:
                self.errors.append(
                    f"ATTACHMENTS_TIMEOUT ({timeout}s) is too low, "
                    "minimum recommended is 10 seconds"
                )
            elif timeout > 3600:
                self.errors.append(
                    f"ATTACHMENTS_TIMEOUT ({timeout}s) is too high, "
                    "maximum recommended is 3600 seconds (1 hour)"
                )

    def _validate_writable_directory_path(self, key: str, create: bool = False):
        """Validate that a directory path is writable"""
        path_str = self.config.get(key)
        if not path_str or not isinstance(path_str, str):
            return  # Already caught by required_string validation

        path = Path(path_str)

        # Check if path exists first
        if path.exists():
            # If it exists but is not a directory, fail immediately
            if not path.is_dir():
                self.errors.append(
                    f"{key} ({path_str}): Path exists but is not a directory"
                )
                return
        else:
            # Path doesn't exist - try to create it if requested
            if create:
                try:
                    path.mkdir(parents=True, exist_ok=True)
                except (OSError, PermissionError) as e:
                    self.errors.append(f"{key} ({path_str}): Cannot create directory - {e}")
                    return
            else:
                # Check if parent directory exists
                parent = path.parent
                if not parent.exists():
                    self.errors.append(
                        f"{key} ({path_str}): Parent directory does not exist"
                    )
                    return

        # At this point, path should be an existing directory
        # Check write permissions by trying to create a temp file
        test_file = path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except (OSError, PermissionError):
            self.errors.append(f"{key} ({path_str}): Directory is not writable")

    def _validate_writable_file_path(self, key: str):
        """Validate that a file path is writable"""
        path_str = self.config.get(key)
        if not path_str or not isinstance(path_str, str):
            return  # Already caught by required_string validation

        path = Path(path_str)

        # Check if parent directory exists
        parent = path.parent
        if not parent.exists():
            self.errors.append(
                f"{key} ({path_str}): Parent directory '{parent}' does not exist"
            )
            return

        if not parent.is_dir():
            self.errors.append(
                f"{key} ({path_str}): Parent path '{parent}' is not a directory"
            )
            return

        # If file exists, check if it's writable
        if path.exists():
            if not path.is_file():
                self.errors.append(f"{key} ({path_str}): Path exists but is not a file")
                return
            if not os.access(path, os.W_OK):
                self.errors.append(f"{key} ({path_str}): File is not writable")
        else:
            # Check if parent directory is writable (to create new file)
            if not os.access(parent, os.W_OK):
                self.errors.append(
                    f"{key} ({path_str}): Parent directory is not writable"
                )

    def _validate_log_level(self):
        """Validate that log level is valid"""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        log_level = self.config.get("LOG_LEVEL")

        if isinstance(log_level, str) and log_level.upper() not in valid_levels:
            self.errors.append(
                f"LOG_LEVEL must be one of {valid_levels}, got '{log_level}'"
            )

    def _validate_url(self, key: str):
        """Validate that a URL is well-formed"""
        url = self.config.get(key)
        if not url or not isinstance(url, str):
            return  # Already caught by required_string validation

        if not url.startswith(("http://", "https://")):
            self.errors.append(f"{key} ({url}): Must start with http:// or https://")


def validate_config(config: dict):
    """
    Validate configuration and raise exception on failure

    Args:
        config: Configuration dictionary

    Raises:
        ConfigValidationError: If validation fails
    """
    validator = ConfigValidator(config)
    validator.validate_all()
