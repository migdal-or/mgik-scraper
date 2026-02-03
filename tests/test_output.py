"""
Tests for output module (RSS generator)
"""

import os
from unittest.mock import Mock
from unittest.mock import patch
from datetime import datetime
import xml.etree.ElementTree as ET
import pytest
from output import RSSGenerator


class TestRSSGenerator:
    """Tests for RSSGenerator class"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock configuration"""
        return {
            "OUTPUT_PATH": str(tmp_path / "feed.xml"),
            "OUTPUT_MAX_ITEMS": 10,
            "MGIK_BASE_URL": "https://www.example.com",
            "RSS_FEED_TITLE": "Test Feed",
            "RSS_FEED_DESCRIPTION": "Test Description",
            "MGIK_DB_PATH": str(tmp_path / "test.db"),
        }

    @pytest.fixture
    def rss_generator(self, mock_config):
        """Create RSSGenerator with mocked database"""
        with patch("output.DecisionsDatabase"):
            generator = RSSGenerator(mock_config)
            generator.db = Mock()
            return generator

    def test_init(self, mock_config):
        """Test RSSGenerator initialization"""
        with patch("output.DecisionsDatabase"):
            generator = RSSGenerator(mock_config)
            assert generator.output_path == mock_config["OUTPUT_PATH"]
            assert generator.max_items == 10
            assert generator.base_url == "https://www.example.com"
            assert generator.feed_title == "Test Feed"
            assert generator.feed_description == "Test Description"

    def test_escape_xml(self, rss_generator):
        """Test XML special character escaping"""
        assert rss_generator.escape_xml("&") == "&amp;"
        assert rss_generator.escape_xml("<") == "&lt;"
        assert rss_generator.escape_xml(">") == "&gt;"
        assert rss_generator.escape_xml('"') == "&quot;"
        assert rss_generator.escape_xml("'") == "&apos;"
        assert rss_generator.escape_xml("Test & <stuff>") == "Test &amp; &lt;stuff&gt;"

    def test_escape_xml_empty_string(self, rss_generator):
        """Test escaping empty or None values"""
        assert rss_generator.escape_xml("") == ""
        assert rss_generator.escape_xml(None) == ""

    def test_format_rfc822(self, rss_generator):
        """Test RFC 822 date formatting"""
        dt = datetime(2025, 1, 15, 12, 30, 45)
        result = rss_generator.format_rfc822(dt)

        # Should be in RFC 822 format
        assert "2025" in result
        assert "GMT" in result or "UT" in result

    def test_format_rfc822_from_date_valid(self, rss_generator):
        """Test RFC 822 formatting from date string"""
        result = rss_generator.format_rfc822_from_date("2025-01-15")

        assert "2025" in result
        assert "GMT" in result or "UT" in result

    def test_format_rfc822_from_date_invalid(self, rss_generator):
        """Test RFC 822 formatting with invalid date falls back to current date"""
        result = rss_generator.format_rfc822_from_date("invalid-date")

        # Should not raise error, should return some valid date
        assert result is not None
        assert len(result) > 0

    def test_build_item(self, rss_generator):
        """Test building single RSS item"""
        decision = {
            "mgik_id": "123",
            "name": "Test Decision",
            "number": "1/2025",
            "date": "2025-01-15",
            "file": "https://example.com/test.pdf",
        }

        item_xml = rss_generator.build_item(decision)

        assert "<item>" in item_xml
        assert "</item>" in item_xml
        assert "<title>Test Decision</title>" in item_xml
        assert '<guid isPermaLink="false">123</guid>' in item_xml
        assert "1/2025" in item_xml
        assert "2025-01-15" in item_xml
        assert "https://example.com/test.pdf" in item_xml

    def test_build_item_with_special_characters(self, rss_generator):
        """Test building item with special characters in name"""
        decision = {
            "mgik_id": "123",
            "name": "Test & <Decision>",
            "number": "1/2025",
            "date": "2025-01-15",
            "file": "https://example.com/test.pdf",
        }

        item_xml = rss_generator.build_item(decision)

        # Special characters should be escaped
        assert "&amp;" in item_xml
        assert "&lt;" in item_xml
        assert "&gt;" in item_xml

    def test_build_item_without_file(self, rss_generator):
        """Test building item when file field is missing"""
        decision = {
            "mgik_id": "123",
            "name": "Test Decision",
            "number": "1/2025",
            "date": "2025-01-15",
            "file": None,
        }

        item_xml = rss_generator.build_item(decision)

        # Should not crash, should handle missing file gracefully
        assert "<item>" in item_xml
        assert "</item>" in item_xml

    def test_build_rss_xml(self, rss_generator):
        """Test building complete RSS XML"""
        decisions = [
            {
                "mgik_id": "1",
                "name": "Decision 1",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "https://example.com/file1.pdf",
            },
            {
                "mgik_id": "2",
                "name": "Decision 2",
                "number": "2/2025",
                "date": "2025-01-16",
                "file": "https://example.com/file2.pdf",
            },
        ]

        xml = rss_generator.build_rss_xml(decisions)

        # Check XML structure
        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml
        assert '<rss version="2.0">' in xml
        assert "<channel>" in xml
        assert "</channel>" in xml
        assert "</rss>" in xml

        # Check feed metadata
        assert "<title>Test Feed</title>" in xml
        assert "<description>Test Description</description>" in xml
        assert "<link>https://www.example.com</link>" in xml
        assert "<language>ru</language>" in xml

        # Check items
        assert "Decision 1" in xml
        assert "Decision 2" in xml

    def test_build_rss_xml_empty(self, rss_generator):
        """Test building RSS with no items"""
        xml = rss_generator.build_rss_xml([])

        # Should still be valid RSS structure
        assert '<?xml version="1.0" encoding="UTF-8"?>' in xml
        assert '<rss version="2.0">' in xml
        assert "<channel>" in xml
        assert "</channel>" in xml

    def test_build_rss_xml_is_valid_xml(self, rss_generator):
        """Test that generated RSS is valid XML"""
        decisions = [
            {
                "mgik_id": "1",
                "name": "Test Decision",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "https://example.com/test.pdf",
            }
        ]

        xml = rss_generator.build_rss_xml(decisions)

        # Should be parseable as XML
        try:
            ET.fromstring(xml)
            assert True
        except ET.ParseError as e:
            pytest.fail(f"Generated RSS is not valid XML: {e}")

    def test_generate_creates_file(self, rss_generator, mock_config):
        """Test that generate() creates RSS file"""
        rss_generator.db.get_all.return_value = [
            {
                "mgik_id": "1",
                "name": "Test Decision",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "https://example.com/test.pdf",
            }
        ]

        rss_generator.generate()

        # File should exist
        assert os.path.exists(mock_config["OUTPUT_PATH"])

        # File should contain valid RSS
        with open(mock_config["OUTPUT_PATH"], "r", encoding="utf-8") as f:
            content = f.read()
            assert "<?xml" in content
            assert "<rss" in content
            assert "Test Decision" in content

    def test_generate_limits_items(self, rss_generator, mock_config):
        """Test that generate() respects max_items limit"""
        # Create 20 decisions
        decisions = [
            {
                "mgik_id": str(i),
                "name": f"Decision {i}",
                "number": f"{i}/2025",
                "date": "2025-01-15",
                "file": f"https://example.com/file{i}.pdf",
            }
            for i in range(20)
        ]

        rss_generator.db.get_all.return_value = decisions
        rss_generator.max_items = 5

        rss_generator.generate()

        # Read generated file and count items
        with open(mock_config["OUTPUT_PATH"], "r", encoding="utf-8") as f:
            content = f.read()
            item_count = content.count("<item>")
            assert item_count == 5

    def test_generate_sorts_by_date_descending(self, rss_generator, mock_config):
        """Test that items are sorted by date, newest first"""
        decisions = [
            {
                "mgik_id": "1",
                "name": "Old Decision",
                "number": "1/2025",
                "date": "2025-01-10",
                "file": "https://example.com/old.pdf",
            },
            {
                "mgik_id": "2",
                "name": "New Decision",
                "number": "2/2025",
                "date": "2025-01-20",
                "file": "https://example.com/new.pdf",
            },
            {
                "mgik_id": "3",
                "name": "Middle Decision",
                "number": "3/2025",
                "date": "2025-01-15",
                "file": "https://example.com/middle.pdf",
            },
        ]

        rss_generator.db.get_all.return_value = decisions
        rss_generator.generate()

        with open(mock_config["OUTPUT_PATH"], "r", encoding="utf-8") as f:
            content = f.read()

        # Find positions of decision names in the content
        new_pos = content.find("New Decision")
        middle_pos = content.find("Middle Decision")
        old_pos = content.find("Old Decision")

        # Newest should appear first (smallest position)
        assert new_pos < middle_pos < old_pos

    def test_generate_atomic_write(self, rss_generator, mock_config):
        """Test that generate() uses atomic write (temp file + rename)"""
        rss_generator.db.get_all.return_value = [
            {
                "mgik_id": "1",
                "name": "Test",
                "number": "1/2025",
                "date": "2025-01-15",
                "file": "https://example.com/test.pdf",
            }
        ]

        # Temp file should not exist before
        temp_path = f"{mock_config['OUTPUT_PATH']}.tmp"
        assert not os.path.exists(temp_path)

        rss_generator.generate()

        # Final file should exist
        assert os.path.exists(mock_config["OUTPUT_PATH"])

        # Temp file should not exist after (should be cleaned up via rename)
        assert not os.path.exists(temp_path)
