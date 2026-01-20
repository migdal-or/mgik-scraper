#!/usr/bin/env python3
"""
MGIK Scraper Daemon - Main entry point for background execution
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from scheduler import DaemonScheduler


def setup_logging(config):
    """Setup logging with file rotation"""
    logger = logging.getLogger('mgik-scraper')
    logger.setLevel(config.get('LOG_LEVEL', 'INFO'))

    # File handler with rotation
    file_handler = RotatingFileHandler(
        config['LOG_FILE'],
        maxBytes=config.get('LOG_MAX_BYTES', 10485760),
        backupCount=config.get('LOG_BACKUP_COUNT', 5)
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        '%(levelname)s: %(message)s'
    ))
    logger.addHandler(console_handler)

    return logger


def load_config():
    """Load configuration from .env"""
    load_dotenv()

    config = {
        # Existing config
        'MGIK_NEWS_URL': os.getenv('MGIK_NEWS_URL'),
        'MGIK_DB_PATH': os.getenv('MGIK_DB_PATH'),

        # Scheduler config
        'SCHEDULER_DEFAULT_INTERVAL': int(os.getenv('SCHEDULER_DEFAULT_INTERVAL', '28800')),
        'SCHEDULER_MAX_INTERVAL': int(os.getenv('SCHEDULER_MAX_INTERVAL', '28800')),
        'SCHEDULER_MAX_MEMORY_MB': int(os.getenv('SCHEDULER_MAX_MEMORY_MB', '500')),

        # Output config (RSS for now)
        'OUTPUT_PATH': os.getenv('OUTPUT_PATH', './mgik-feed.xml'),
        'OUTPUT_MAX_ITEMS': int(os.getenv('OUTPUT_MAX_ITEMS', '100')),
        'MGIK_BASE_URL': os.getenv('MGIK_BASE_URL', 'https://www.mosgorizbirkom.ru'),

        # Attachments config
        'ATTACHMENTS_ENABLED': os.getenv('ATTACHMENTS_ENABLED', 'true').lower() == 'true',
        'ATTACHMENTS_DIR': os.getenv('ATTACHMENTS_DIR', './attachments'),
        'ATTACHMENTS_MAX_FAILURES': int(os.getenv('ATTACHMENTS_MAX_FAILURES', '3')),

        # Logging config
        'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO'),
        'LOG_FILE': os.getenv('LOG_FILE', './mgik-scraper.log'),
        'LOG_MAX_BYTES': int(os.getenv('LOG_MAX_BYTES', '10485760')),
        'LOG_BACKUP_COUNT': int(os.getenv('LOG_BACKUP_COUNT', '5')),
    }

    # Validate required config
    if not config['MGIK_NEWS_URL']:
        raise ValueError("MGIK_NEWS_URL must be set in .env")
    if not config['MGIK_DB_PATH']:
        raise ValueError("MGIK_DB_PATH must be set in .env")

    return config


def main():
    """Main daemon entry point"""
    try:
        # Load configuration
        config = load_config()

        # Setup logging
        logger = setup_logging(config)
        logger.info("MGIK Scraper Daemon starting")

        # Create and run scheduler
        scheduler = DaemonScheduler(config)
        scheduler.run()

    except KeyboardInterrupt:
        logger = logging.getLogger('mgik-scraper')
        logger.info("Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger = logging.getLogger('mgik-scraper')
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
