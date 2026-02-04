#!/usr/bin/env python3
# type: ignore

"""
MGIK Scraper Daemon - Main entry point for background execution
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from scheduler import DaemonScheduler
from config_validator import validate_config, ConfigValidationError


def setup_logging(config):
    """Setup logging with file rotation"""
    logger = logging.getLogger("mgik-scraper")
    logger.setLevel(config.get("LOG_LEVEL", "INFO"))

    # File handler with rotation
    file_handler = RotatingFileHandler(
        config["LOG_FILE"],
        maxBytes=config.get("LOG_MAX_BYTES"),
        backupCount=config.get("LOG_BACKUP_COUNT"),
    )
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(console_handler)

    return logger


def load_config():
    """Load configuration from .env"""
    load_dotenv()

    config = {
        # Existing config
        "MGIK_NEWS_URL": os.getenv("MGIK_NEWS_URL"),
        "MGIK_DB_PATH": os.getenv("MGIK_DB_PATH"),
        # Scheduler config
        "SCHEDULER_DEFAULT_INTERVAL": int(os.getenv("SCHEDULER_DEFAULT_INTERVAL")),
        "SCHEDULER_MAX_INTERVAL": int(os.getenv("SCHEDULER_MAX_INTERVAL")),
        "SCHEDULER_BACKOFF_MULTIPLIER": float(os.getenv("SCHEDULER_BACKOFF_MULTIPLIER")),
        "SCHEDULER_MAX_MEMORY_MB": int(os.getenv("SCHEDULER_MAX_MEMORY_MB")),
        # Output config (RSS for now)
        "OUTPUT_PATH": os.getenv("OUTPUT_PATH"),
        "OUTPUT_MAX_ITEMS": int(os.getenv("OUTPUT_MAX_ITEMS")),
        "MGIK_BASE_URL": os.getenv("MGIK_BASE_URL"),
        "RSS_FEED_TITLE": os.getenv("RSS_FEED_TITLE"),
        "RSS_FEED_DESCRIPTION": os.getenv("RSS_FEED_DESCRIPTION"),
        "ATTACHMENTS_DIR": os.getenv("ATTACHMENTS_DIR"),
        "ATTACHMENTS_MAX_FAILURES": int(os.getenv("ATTACHMENTS_MAX_FAILURES")),
        "ATTACHMENTS_MAX_SIZE_MB": int(os.getenv("ATTACHMENTS_MAX_SIZE_MB")),
        "ATTACHMENTS_TIMEOUT": int(os.getenv("ATTACHMENTS_TIMEOUT")),
        # Logging config
        "LOG_LEVEL": os.getenv("LOG_LEVEL"),
        "LOG_FILE": os.getenv("LOG_FILE"),
        "LOG_MAX_BYTES": int(os.getenv("LOG_MAX_BYTES")),
        "LOG_BACKUP_COUNT": int(os.getenv("LOG_BACKUP_COUNT")),
    }

    return config


def main():
    """Main daemon entry point"""
    try:
        # Load configuration
        config = load_config()

        # Validate configuration (fail fast with clear errors)
        try:
            validate_config(config)
        except ConfigValidationError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)

        # Setup logging
        logger = setup_logging(config)
        logger.info("MGIK Scraper Daemon starting")
        logger.info("Configuration validated successfully")

        # Create and run scheduler
        scheduler = DaemonScheduler(config)
        scheduler.run()

    except KeyboardInterrupt:
        logger = logging.getLogger("mgik-scraper")
        logger.info("Interrupted by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
