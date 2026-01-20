"""
Attachment Manager for MGIK Scraper

Downloads missing PDF attachments using existing fetch logic,
with failure threshold to stop after N consecutive failures.
"""

import os
import random
import logging
from mgik_website_worker import fetch_attachment
from datastore import DecisionsDatabase

logger = logging.getLogger('mgik-scraper')


class AttachmentManager:
    """Manages PDF attachment downloads with failure threshold"""

    def __init__(self, config: dict):
        """
        Initialize attachment manager

        Args:
            config: Configuration dictionary with DB path, attachments dir, etc.
        """
        self.db = DecisionsDatabase(config['MGIK_DB_PATH'])
        self.attachments_dir = config['ATTACHMENTS_DIR']
        self.max_consecutive_failures = config['ATTACHMENTS_MAX_FAILURES']

        logger.info(
            f"AttachmentManager initialized: dir={self.attachments_dir}, "
            f"max_failures={self.max_consecutive_failures}"
        )

    def download_and_upload(self):
        """
        Main workflow: download missing PDFs
        (SSH upload moved to backlog - #todo)
        """
        # 1. Identify missing files
        missing_files = self.get_missing_files()

        if not missing_files:
            logger.info("No missing attachments")
            return

        logger.info(f"Found {len(missing_files)} missing attachments")

        # 2. Download with failure threshold
        downloaded_files = self.download_with_threshold(missing_files)

        logger.info(
            f"Attachment downloads complete: {len(downloaded_files)} downloaded, "
            f"{len(missing_files) - len(downloaded_files)} failed/skipped"
        )

        # 3. SSH upload: MOVED TO BACKLOG (#todo)
        # Will be discussed and implemented later

    def get_missing_files(self) -> list[str]:
        """
        Compare database URLs with local files

        Returns:
            list[str]: List of URLs for missing files
        """
        db_files = self.db.get_all_files()  # Already implemented in datastore.py

        # Ensure attachments directory exists
        os.makedirs(self.attachments_dir, exist_ok=True)

        local_files = set(os.listdir(self.attachments_dir))

        missing = []
        for file_url in db_files:
            filename = os.path.basename(file_url)
            if filename not in local_files:
                missing.append(file_url)

        return missing

    def download_with_threshold(self, file_urls: list[str]) -> list[str]:
        """
        Download files, stopping after N consecutive failures

        Args:
            file_urls: List of URLs to download

        Returns:
            list[str]: List of successfully downloaded local file paths
        """
        consecutive_failures = 0
        downloaded = []

        # Shuffle for randomization (existing pattern from mgik_website_worker)
        random.shuffle(file_urls)

        for file_url in file_urls:
            if consecutive_failures >= self.max_consecutive_failures:
                logger.warning(
                    f"Stopping downloads: {consecutive_failures} consecutive failures "
                    f"(threshold: {self.max_consecutive_failures})"
                )
                break

            result = self.download_file(file_url)

            if result['status'] == 'success':
                downloaded.append(result['local_path'])
                consecutive_failures = 0  # Reset counter on success
                logger.info(f"Downloaded: {os.path.basename(file_url)}")
            else:
                consecutive_failures += 1
                logger.error(
                    f"Download failed ({consecutive_failures}/{self.max_consecutive_failures}): "
                    f"{file_url} - {result['error']}"
                )

        logger.info(f"Downloaded {len(downloaded)}/{len(file_urls)} files")
        return downloaded

    def download_file(self, file_url: str) -> dict:
        """
        Download single file using fetch_attachment from mgik_website_worker

        Args:
            file_url: URL of the PDF file

        Returns:
            dict: {"status": "success"/"error", "local_path": ..., "error": ...}
        """
        try:
            filename = os.path.basename(file_url)
            local_path = os.path.join(self.attachments_dir, filename)

            # Use dedicated fetch_attachment function (reuses proxy/headers/timeout)
            result = fetch_attachment(file_url, local_path)

            if result['status'] == 'error':
                return {"status": "error", "error": result['error']}

            return {"status": "success", "local_path": local_path}

        except Exception as e:
            return {"status": "error", "error": str(e)}
