"""
Output Generator for MGIK Scraper

Generates RSS 2.0 XML feed from database decisions.
TODO: Decide final format (RSS vs static HTML vs Telegram bot)
"""

import os
import logging
from datetime import datetime
from email.utils import formatdate
from datastore import DecisionsDatabase

logger = logging.getLogger("mgik-scraper")


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
        items_xml = ''.join(items)

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
        escaped_number = self.escape_xml(decision['number'])
        escaped_date = self.escape_xml(decision['date'])
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
