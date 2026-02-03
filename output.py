"""
Output Generator for MGIK Scraper

Manages multiple output formats: RSS feed, HTML pages, Telegram notifications, etc.
Each output format is implemented as a separate generator class.
"""

import os
import logging
from datetime import datetime
from email.utils import formatdate
import feedparser
from datastore import DecisionsDatabase

logger = logging.getLogger("mgik-scraper")


class OutputManager:
    """
    Orchestrates multiple output formats

    This is the main interface used by the scheduler. It manages
    different output generators (RSS, HTML, Telegram, etc.) and
    ensures they all succeed or fail together.
    """

    def __init__(self, config: dict):
        """
        Initialize output manager with all enabled generators

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.generators = []

        # Initialize RSS generator (always enabled for now)
        if config.get("OUTPUT_PATH"):
            self.generators.append(RSSGenerator(config))
            logger.info("Initialized RSS generator")

        # Future: Initialize other generators based on config
        # if config.get("HTML_OUTPUT_PATH"):
        #     self.generators.append(HTMLGenerator(config))
        # if config.get("TELEGRAM_BOT_TOKEN"):
        #     self.generators.append(TelegramNotifier(config))

        logger.info(
            "OutputManager initialized with %d generators", len(self.generators)
        )

    def generate(self):
        """
        Generate all enabled output formats

        Executes each generator in sequence. If any generator fails, the exception
        is logged and re-raised to stop execution (fail-fast behavior).

        Rationale for fail-fast:
        - Output generation failures typically indicate bugs, not transient errors
        - Examples: RSS validation failure, filesystem permission errors, etc.
        - Better to stop the daemon visibly than continue with partial/broken output
        - Allows external monitoring to detect and alert on output issues
        - Primary data collection (scraping to database) completes before this step

        Raises:
            Exception: If any generator fails, the original exception propagates
        """
        for generator in self.generators:
            generator_name = generator.__class__.__name__
            logger.info("Running %s", generator_name)
            try:
                generator.generate()
                logger.info("%s completed successfully", generator_name)
            except Exception as e:
                logger.error("%s failed: %s", generator_name, e, exc_info=True)
                # Re-raise to stop execution - output generation failures should be visible
                raise


class RSSGenerator:
    """Generates RSS 2.0 XML feed from decisions database"""

    def __init__(self, config: dict):
        """
        Initialize RSS generator

        Args:
            config: Configuration dictionary with DB path, output path, etc.
        """
        self.db = DecisionsDatabase()
        self.output_path = config["OUTPUT_PATH"]
        self.base_url = config["MGIK_BASE_URL"]
        self.max_items = config["OUTPUT_MAX_ITEMS"]
        self.feed_title = config["RSS_FEED_TITLE"]
        self.feed_description = config["RSS_FEED_DESCRIPTION"]

        logger.info(
            "RSSGenerator initialized: output=%s, max_items=%s",
            self.output_path,
            self.max_items,
        )

    def generate(self):
        """Generate RSS 2.0 XML and write to file"""
        decisions = self.db.get_all()

        # Sort by date descending (newest first)
        decisions.sort(key=lambda d: d.get("date", ""), reverse=True)

        # Take most recent N items
        recent = decisions[: self.max_items]

        rss_xml = self.build_rss_xml(recent)

        # Validate RSS before writing
        # Uses feedparser to perform semantic RSS validation, not just XML syntax checking.
        # The 'bozo' flag indicates a malformed feed (missing required elements,
        # invalid structure, etc.). This catches bugs in RSS generation logic before
        # writing corrupted feeds to disk.
        #
        # Rationale for fail-fast behavior:
        # - RSS validation failures indicate a bug in our code, not transient errors
        # - Writing invalid RSS would break feed readers and go unnoticed
        # - Better to fail visibly (stop daemon) than silently serve broken feeds
        # - The atomic write pattern ensures old valid RSS remains available
        parsed = feedparser.parse(rss_xml)
        if parsed.bozo:
            error_msg = (
                str(parsed.bozo_exception)
                if hasattr(parsed, "bozo_exception")
                else "unknown parsing error"
            )
            logger.error("Generated RSS is malformed: %s", error_msg)
            raise ValueError(f"RSS validation failed: {error_msg}")

        # Write atomically (write to temp file, then rename)
        # This prevents RSS readers from seeing partial/corrupted files:
        # - Write complete content to temporary file first
        # - os.replace() atomically swaps the files (all-or-nothing operation)
        # - Readers see either old complete file or new complete file, never partial
        # - If write fails, original file remains unchanged
        temp_path = f"{self.output_path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as f:
            f.write(rss_xml)
        os.replace(temp_path, self.output_path)

        logger.info(
            "RSS feed generated: %s items written to %s", len(recent), self.output_path
        )

    def build_rss_xml(self, decisions: list) -> str:
        """
        Build RSS 2.0 XML string

        Args:
            decisions: List of decision dictionaries

        Returns:
            str: Complete RSS 2.0 XML document
        """
        items = []
        for decision in decisions:
            item_xml = self.build_item(decision)
            items.append(item_xml)

        escaped_title = self.escape_xml(self.feed_title)
        escaped_url = self.escape_xml(self.base_url)
        escaped_description = self.escape_xml(self.feed_description)
        build_date = self.format_rfc822(datetime.now())
        items_xml = "".join(items)

        channel_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{escaped_title}</title>
    <link>{escaped_url}</link>
    <description>{escaped_description}</description>
    <language>ru</language>
    <lastBuildDate>{build_date}</lastBuildDate>
{items_xml}
  </channel>
</rss>"""
        return channel_xml

    def build_item(self, decision: dict) -> str:
        """
        Build single RSS item

        Args:
            decision: Decision dictionary from database

        Returns:
            str: RSS item XML
        """
        title = self.escape_xml(decision["name"])
        guid = decision["internal_id"]  # Use internal_id for unique GUID
        pub_date = self.format_rfc822_from_date(decision["date"])

        # Build description with decision metadata
        escaped_number = self.escape_xml(decision["number"])
        escaped_date = self.escape_xml(decision["date"])
        desc_html = f"""<p><strong>Number:</strong>
{escaped_number}</p>
<p><strong>Date:</strong> {escaped_date}</p>"""

        # Add file link if available
        if decision_file := decision.get("file"):
            escaped_file = self.escape_xml(decision_file)
            desc_html += f"""
<p><strong>Original:</strong>
<a href="{escaped_file}">{escaped_file}</a>
</p>"""

        # TODO: Add mirror URL when SSH upload is implemented (#todo)

        link_url = self.escape_xml(decision.get("file") or "")
        return f"""
    <item>
      <title>{title}</title>
      <link>{link_url}</link>
      <guid isPermaLink="false">{guid}</guid>
      <pubDate>{pub_date}</pubDate>
      <description><![CDATA[
{desc_html}
      ]]></description>
    </item>"""

    def escape_xml(self, text: str) -> str:
        """
        Escape XML special characters

        Args:
            text: Text to escape

        Returns:
            str: Escaped text safe for XML
        """
        if not text:
            return ""
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def format_rfc822(self, dt: datetime) -> str:
        """
        Convert datetime to RFC 822 format for RSS

        Args:
            dt: datetime object

        Returns:
            str: RFC 822 formatted date string
        """
        return formatdate(timeval=dt.timestamp(), localtime=False, usegmt=True)

    def format_rfc822_from_date(self, date_str: str) -> str:
        """
        Convert YYYY-MM-DD date string to RFC 822

        Args:
            date_str: Date string in YYYY-MM-DD format

        Returns:
            str: RFC 822 formatted date string
        """
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return self.format_rfc822(dt)
        except (ValueError, TypeError):
            return self.format_rfc822(datetime.now())
