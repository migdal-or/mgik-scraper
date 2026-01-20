"""
Core Scheduler for MGIK Scraper Daemon

Main event loop that orchestrates fetch, attachments, output generation,
and memory monitoring in strict sequential order.
"""

import psutil
import os
import signal
import time
import logging
from mgik_website_worker import load_decisions_from_web_to_database
from attachments import AttachmentManager
from output import RSSGenerator

logger = logging.getLogger('mgik-scraper')


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
        self.current_interval = config['SCHEDULER_DEFAULT_INTERVAL']
        self.max_interval = config['SCHEDULER_MAX_INTERVAL']
        self.max_memory_mb = config.get('SCHEDULER_MAX_MEMORY_MB', 500)

        # Initialize components
        self.attachment_mgr = AttachmentManager(config)
        self.output_gen = RSSGenerator(config)

        logger.info(
            f"Scheduler initialized: interval={self.current_interval}s, "
            f"max_memory={self.max_memory_mb}MB"
        )

    def run(self):
        """Main event loop - runs until stopped"""
        self.setup_signal_handlers()
        logger.info("Starting main scheduler loop")

        while self.running:
            try:
                # 1. Fetch news (existing function)
                logger.info("Starting fetch pipeline")
                fetch_result = self.fetch_news()

                if fetch_result:  # Fetch succeeded
                    logger.info("Fetch pipeline completed successfully")

                    # 2. Download attachments (runs AFTER fetch)
                    if self.config.get('ATTACHMENTS_ENABLED', True):
                        logger.info("Starting attachment downloads")
                        self.run_attachments()

                    # 3. Prediction module (BACKLOG - skip for now)
                    # When implemented:
                    # coefficient = self.prediction_engine.compute_urgency()
                    # self.current_interval = self.max_interval / coefficient

                    # For now: use fixed interval
                    self.current_interval = self.config['SCHEDULER_DEFAULT_INTERVAL']

                    # 4. Generate output (runs AFTER prediction)
                    logger.info("Generating output feed")
                    self.run_output_generation()

                else:
                    # Network error (server unreachable) - use backoff
                    logger.warning("Fetch failed (server unreachable)")

                    # Still run attachments (don't skip them)
                    if self.config.get('ATTACHMENTS_ENABLED', True):
                        logger.info("Starting attachment downloads (despite fetch failure)")
                        self.run_attachments()

                    # Prediction feedback loop: server error → increase interval (backoff)
                    # When prediction is implemented, this signals to adjust coefficient
                    # For now: use exponential backoff
                    self.current_interval = min(
                        self.current_interval * 1.5,
                        self.max_interval
                    )
                    logger.warning(
                        f"Using backoff interval: {self.current_interval/60:.1f} min"
                    )

                # 5. Memory check before sleep
                if self.check_memory_and_suicide():
                    logger.info("Memory threshold exceeded, exiting for restart")
                    break

                # 6. Sleep until next run
                logger.info(
                    f"Next check in {self.current_interval/60:.1f} minutes "
                    f"({self.current_interval}s)"
                )
                time.sleep(self.current_interval)

            except Exception as e:
                logger.error(f"Daemon error: {e}", exc_info=True)
                time.sleep(60)  # Wait 1 minute on unexpected error

        logger.info("Daemon shutdown complete")

    def fetch_news(self) -> bool:
        """
        Wrapper around existing load_decisions_from_web_to_database

        Returns:
            bool: True on success, False on error
        """
        try:
            load_decisions_from_web_to_database()
            return True
        except Exception as e:
            logger.error(f"Fetch pipeline error: {e}", exc_info=True)
            return False

    def run_attachments(self):
        """Run attachment downloads"""
        self.attachment_mgr.download_and_upload()

    def run_output_generation(self):
        """Run output generation"""
        self.output_gen.generate()

    def check_memory_and_suicide(self) -> bool:
        """
        Check current memory consumption and exit if threshold exceeded

        Returns:
            bool: True if should exit (memory exceeded), False otherwise
        """
        try:
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024  # Convert to MB

            logger.debug(f"Current memory usage: {memory_mb:.2f} MB")

            if memory_mb > self.max_memory_mb:
                logger.warning(
                    f"Memory threshold exceeded: {memory_mb:.2f} MB > "
                    f"{self.max_memory_mb} MB"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"Memory check failed: {e}", exc_info=True)
            return False

    def setup_signal_handlers(self):
        """Setup handlers for graceful shutdown and reload"""

        def handle_sigterm(signum, frame):
            logger.info(f"Received signal {signum}, shutting down gracefully")
            self.running = False

        def handle_sighup(signum, frame):
            logger.info("Received SIGHUP, reloading configuration")
            # Reload .env and reinitialize components
            from dotenv import load_dotenv
            load_dotenv(override=True)

            # Re-read config values that can be hot-reloaded
            self.max_memory_mb = int(os.getenv('SCHEDULER_MAX_MEMORY_MB', '500'))
            logger.info(f"Configuration reloaded: max_memory={self.max_memory_mb}MB")

        signal.signal(signal.SIGTERM, handle_sigterm)
        signal.signal(signal.SIGINT, handle_sigterm)
        signal.signal(signal.SIGHUP, handle_sighup)

        logger.debug("Signal handlers registered (SIGTERM, SIGINT, SIGHUP)")
