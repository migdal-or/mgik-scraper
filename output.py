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

logger = logging.getLogger('mgik-scraper')


class RSSGenerator:
    """Generates RSS 2.0 XML feed from decisions database"""

    def __init__(self, config: dict):
        """
        Initialize RSS generator

        Args:
            config: Configuration dictionary with DB path, output path, etc.
        """
        self.db = DecisionsDatabase(config['MGIK_DB_PATH'])
        self.output_path = config['OUTPUT_PATH']
        self.base_url = config['MGIK_BASE_URL']
        self.max_items = config.get('OUTPUT_MAX_ITEMS', 100)

        logger.info(
            f"RSSGenerator initialized: output={self.output_path}, "
            f"max_items={self.max_items}"
        )

    def generate(self):
        """Generate RSS 2.0 XML and write to file"""
        try:
            decisions = self.db.get_all()

            # Sort by date descending (newest first)
            decisions.sort(key=lambda d: d.get('date', ''), reverse=True)

            # Take most recent N items
            recent = decisions[:self.max_items]

            rss_xml = self.build_rss_xml(recent)

            # Write atomically (write to temp file, then rename)
            temp_path = f"{self.output_path}.tmp"
            with open(temp_path, 'w', encoding='utf-8') as f:
                f.write(rss_xml)
            os.replace(temp_path, self.output_path)

            logger.info(
                f"RSS feed generated: {len(recent)} items written to {self.output_path}"
            )

        except Exception as e:
            logger.error(f"RSS generation failed: {e}", exc_info=True)

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
    <title>MGIK Decisions Feed</title>
    <link>{self.escape_xml(self.base_url)}</link>
    <description>Moscow City Election Commission decisions</description>
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
        title = self.escape_xml(decision.get('name', 'Untitled'))
        guid = f"mgik-{decision.get('mgik_id', 'unknown')}"
        pub_date = self.format_rfc822_from_date(decision.get('date', ''))

        # Build description with decision metadata
        desc_html = f"""<p><strong>Number:</strong> {self.escape_xml(decision.get('number', 'N/A'))}</p>
<p><strong>Date:</strong> {self.escape_xml(decision.get('date', 'N/A'))}</p>"""

        # Add file link if available
        if decision.get('file'):
            desc_html += f"""
<p><strong>Original:</strong> <a href="{self.escape_xml(decision.get('file', ''))}">{self.escape_xml(decision.get('file', ''))}</a></p>"""

        # TODO: Add mirror URL when SSH upload is implemented (#todo)
        # if self.mirror_url and decision.get('file'):
        #     filename = os.path.basename(decision['file'])
        #     mirror_full_url = f"{self.mirror_url}{filename}"
        #     desc_html += f"""
        # <p><strong>Mirror:</strong> <a href="{self.escape_xml(mirror_full_url)}">{self.escape_xml(mirror_full_url)}</a></p>"""

        return f"""
    <item>
      <title>{title}</title>
      <link>{self.escape_xml(decision.get('file', self.base_url))}</link>
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
            return ''
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))

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
            dt = datetime.strptime(date_str, '%Y-%m-%d')
            return self.format_rfc822(dt)
        except (ValueError, TypeError):
            return self.format_rfc822(datetime.now())
