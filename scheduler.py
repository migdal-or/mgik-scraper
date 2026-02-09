"""
Core Scheduler for MGIK Scraper Daemon

Main event loop that orchestrates fetch, attachments, output generation,
and memory monitoring in strict sequential order.
"""

import os
import time
import logging
import psutil
from mgik_website_worker import load_decisions_from_web_to_database
from attachments import AttachmentManager
from output import OutputManager
from prediction import PublicationPredictor
from datastore import DecisionsDatabase

logger = logging.getLogger("mgik-scraper")


class DaemonScheduler:
    """Main daemon scheduler with adaptive intervals and memory monitoring"""

    def __init__(self, config: dict):
        """
        Initialize scheduler with configuration

        Args:
            config: Configuration dictionary from daemon.py
        """
        self.config = config
        self.running = True
        self.current_interval = config["SCHEDULER_DEFAULT_INTERVAL"]
        self.max_interval = config["SCHEDULER_MAX_INTERVAL"]
        self.max_memory_mb = config.get("SCHEDULER_MAX_MEMORY_MB")

        # Backoff multiplier (configurable)
        self.backoff_multiplier = config.get("SCHEDULER_BACKOFF_MULTIPLIER", 1.5)

        # Initialize components
        self.attachment_mgr = AttachmentManager(config)
        self.output_mgr = OutputManager(config)

        # Initialize prediction module
        db = DecisionsDatabase()
        base_interval = config["SCHEDULER_DEFAULT_INTERVAL"]
        self.predictor = PublicationPredictor(db, base_interval)

        logger.info(
            "Scheduler initialized: interval=%ss, max_interval=%ss, backoff=%.1fx, max_memory=%sMB",
            self.current_interval,
            self.max_interval,
            self.backoff_multiplier,
            self.max_memory_mb,
        )

    def run(self):
        """Main event loop - runs until stopped"""
        logger.info("Starting main scheduler loop")

        while self.running:
            try:
                # 1. Fetch news
                logger.info("Starting fetch pipeline")
                fetch_result = self.fetch_news()

                if fetch_result is not None:  # Fetch succeeded (could be 0 new records)
                    logger.info(
                        "Fetch pipeline completed: %s new records", fetch_result
                    )
                else:
                    # Network error (server unreachable) - use backoff
                    logger.warning("Fetch failed (server unreachable)")

                # 2. Download attachments (runs AFTER fetch no matter if succeeded or not)
                logger.info("Starting attachment downloads")
                downloaded_count = self.run_attachments()

                # 3. Generate output (RSS, HTML, etc.) if we have new content
                # Output generated when either new records OR new attachments
                # Skipped only when both counts are 0
                if (
                    fetch_result is not None and fetch_result > 0
                ) or downloaded_count > 0:
                    logger.info(
                        "Generating output (%s new records, %s new attachments)",
                        fetch_result,
                        downloaded_count,
                    )
                    self.run_output_generation()
                else:
                    logger.info("No new content, skipping output generation")

                # 4. Update check interval based on result
                # SUCCESS = either fetch succeeded with new records OR attachments downloaded
                if (
                    fetch_result is not None and fetch_result > 0
                ) or downloaded_count > 0:
                    # Apply prediction to current interval
                    prediction_coeff = self.predictor.get_coefficient()
                    self.current_interval = int(
                        self.current_interval / prediction_coeff
                    )
                    logger.info(
                        "Success (fetch=%s, attachments=%s), prediction coeff=%.1f → %.1f min",
                        fetch_result if fetch_result is not None else 0,
                        downloaded_count,
                        prediction_coeff,
                        self.current_interval / 60,
                    )
                elif fetch_result is None and downloaded_count == 0:
                    # COMPLETE FAILURE: Apply backoff multiplier
                    self.current_interval = min(
                        int(self.current_interval * self.backoff_multiplier),
                        self.max_interval,
                    )
                    logger.warning(
                        "Complete failure (fetch and attachments), backoff %.1fx → %.1f min (max %.1f min)",
                        self.backoff_multiplier,
                        self.current_interval / 60,
                        self.max_interval / 60,
                    )
                else:
                    # Fetch succeeded but no new records, keep current interval
                    logger.info(
                        "Fetch succeeded with 0 new records, keeping interval %.1f min",
                        self.current_interval / 60,
                    )

                # 5. Memory check before sleep
                if self.check_memory_and_suicide():
                    logger.info("Memory threshold exceeded, exiting for restart")
                    break

                # 6. Sleep until next run
                logger.info(
                    "Next check in %.1f minutes (%ss)",
                    self.current_interval / 60,
                    self.current_interval,
                )
                time.sleep(self.current_interval)

            except (OSError, RuntimeError) as e:
                logger.error("Daemon error in main loop: %s", e, exc_info=True)
                # Continue running - no sleep, no exit

        logger.info("Daemon shutdown complete")

    def fetch_news(self) -> int | None:
        """
        Wrapper around existing load_decisions_from_web_to_database

        Returns:
            int: Number of new records inserted (0 if no new data)
            None: Error occurred during fetch
        """
        try:
            new_records = load_decisions_from_web_to_database()
            return new_records
        except (OSError, ValueError, RuntimeError) as e:
            logger.error("Fetch pipeline error: %s", e, exc_info=True)
            return None

    def run_attachments(self) -> int:
        """
        Run attachment downloads and uploads

        Returns:
            int: Number of files successfully downloaded
        """
        downloaded_files = self.attachment_mgr.download()
        self.attachment_mgr.upload(downloaded_files)
        return len(downloaded_files)

    def run_output_generation(self):
        """Run all output generators (RSS, HTML, Telegram, etc.)"""
        self.output_mgr.generate()

    def check_memory_and_suicide(self) -> bool:
        """
        Check current memory consumption and exit if threshold exceeded

        Returns:
            bool: True if should exit (memory exceeded), False otherwise
        """
        process = psutil.Process(os.getpid())
        memory_mb = process.memory_info().rss / 1024 / 1024  # Convert to MB

        logger.debug("Current memory usage: %.2f MB", memory_mb)

        if memory_mb > self.max_memory_mb:
            logger.warning(
                "Memory threshold exceeded: %.2f MB > %s MB",
                memory_mb,
                self.max_memory_mb,
            )
            return True

        return False
