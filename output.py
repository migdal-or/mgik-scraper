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

        channel_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{self.escape_xml(self.feed_title)}</title>
    <link>{self.escape_xml(self.base_url)}</link>
    <description>{self.escape_xml(self.feed_description)}</description>
    <language>ru</language>
    <lastBuildDate>{self.format_rfc822(datetime.now())}</lastBuildDate>
{''.join(items)}
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
        guid = decision["mgik_id"]
        pub_date = self.format_rfc822_from_date(decision["date"])

        # Build description with decision metadata
        desc_html = f"""<p><strong>Number:</strong>
{self.escape_xml(decision['number'])}</p>
<p><strong>Date:</strong> {self.escape_xml(decision['date'])}</p>"""

        # Add file link if available
        if decision_file := decision.get("file"):
            desc_html += f"""
<p><strong>Original:</strong>
<a href="{self.escape_xml(decision_file)}">{self.escape_xml(decision_file)}</a>
</p>"""

        # TODO: Add mirror URL when SSH upload is implemented (#todo)

        return f"""
    <item>
      <title>{title}</title>
      <link>{self.escape_xml(decision.get("file") or "")}</link>
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
