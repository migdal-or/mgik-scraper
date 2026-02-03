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

logger = logging.getLogger("mgik-scraper")


class AttachmentManager:
    """
    Manages PDF attachment downloads with failure threshold
    """

    def __init__(self, config: dict):
        """
        Initialize attachment manager

        Args:
            config: Configuration dictionary with DB path, attachments dir, etc.
        """
        self.db = DecisionsDatabase()
        self.attachments_dir = config["ATTACHMENTS_DIR"]
        self.max_consecutive_failures = config["ATTACHMENTS_MAX_FAILURES"]

        logger.info(
            "AttachmentManager initialized: dir=%s, max_failures=%s",
            self.attachments_dir,
            self.max_consecutive_failures,
        )

    def download(self):
        """
        Download missing PDFs

        Returns:
            list[str]: List of successfully downloaded local file paths
        """
        # 1. Identify missing files
        missing_files = self.get_missing_files()

        if not missing_files:
            logger.info("No missing attachments")
            return []

        logger.info("Found %s missing attachments", len(missing_files))

        # 2. Download with failure threshold
        downloaded_files = self.download_with_threshold(missing_files)

        logger.info(
            "Attachment downloads complete: %s downloaded, %s failed/skipped",
            len(downloaded_files),
            len(missing_files) - len(downloaded_files),
        )

        return downloaded_files

    def upload(self, file_paths: list[str]):  # pylint: disable=W0613
        """
        Upload files to SSH mirror (BACKLOG - #todo)

        Args:
            file_paths: List of local file paths to upload
        """
        # TODO: SSH upload: MOVED TO BACKLOG (#todo)
        # Will be discussed and implemented later
        logger.debug("SSH upload not yet implemented (backlog)")

    def get_missing_files(self) -> list[str]:
        """
        Compare database URLs with local files

        Returns:
            list[str]: List of URLs for missing files
        """
        db_files = self.db.get_all_files()

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
                    "Stopping downloads: %s consecutive failures (threshold: %s)",
                    consecutive_failures,
                    self.max_consecutive_failures,
                )
                break

            result = self.download_file(file_url)

            if result["status"] == "success":
                downloaded.append(result["local_path"])
                consecutive_failures = 0  # Reset counter on success
                logger.info("Downloaded: %s", os.path.basename(file_url))
            else:
                consecutive_failures += 1
                logger.error(
                    "Download failed (%s/%s): %s - %s",
                    consecutive_failures,
                    self.max_consecutive_failures,
                    file_url,
                    result["error"],
                )

        logger.info("Downloaded %s/%s files", len(downloaded), len(file_urls))
        return downloaded

    def download_file(self, file_url: str) -> dict:
        """
        Download single file using fetch_attachment from mgik_website_worker

        Args:
            file_url: URL of the PDF file

        Returns:
            dict: {"status": "success"/"error", "local_path": ..., "error": ...}
        """
        filename = os.path.basename(file_url)
        local_path = os.path.join(self.attachments_dir, filename)

        # Use dedicated fetch_attachment function (reuses proxy/headers/timeout)
        result = fetch_attachment(file_url, local_path)

        if result["status"] == "error":
            return {"status": "error", "error": result["error"]}

        return {"status": "success", "local_path": local_path}
