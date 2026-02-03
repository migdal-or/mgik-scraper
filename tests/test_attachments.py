"""
Tests for attachments module
"""

import os
from unittest.mock import Mock
from unittest.mock import patch
import pytest
from attachments import AttachmentManager


class TestAttachmentManager:
    """Tests for AttachmentManager class"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock configuration"""
        return {
            "ATTACHMENTS_DIR": str(tmp_path / "attachments"),
            "ATTACHMENTS_MAX_FAILURES": 3,
            "ATTACHMENTS_MAX_SIZE_MB": 50,
            "ATTACHMENTS_TIMEOUT": 600,
            "MGIK_DB_PATH": str(tmp_path / "test.db"),
        }

    @pytest.fixture
    def attachment_manager(self, mock_config):
        """Create AttachmentManager with mocked database"""
        with patch("attachments.DecisionsDatabase"):
            manager = AttachmentManager(mock_config)
            manager.db = Mock()
            return manager

    def test_init(self, mock_config):
        """Test AttachmentManager initialization"""
        with patch("attachments.DecisionsDatabase"):
            manager = AttachmentManager(mock_config)
            assert manager.attachments_dir == mock_config["ATTACHMENTS_DIR"]
            assert manager.max_consecutive_failures == 3

    def test_get_missing_files_no_local_files(self, attachment_manager, mock_config):
        """Test identifying missing files when no local files exist"""
        attachment_manager.db.get_all_files.return_value = [
            "http://example.com/file1.pdf",
            "http://example.com/file2.pdf",
        ]

        # Ensure directory exists but is empty
        os.makedirs(mock_config["ATTACHMENTS_DIR"], exist_ok=True)

        missing = attachment_manager.get_missing_files()

        assert len(missing) == 2
        assert "http://example.com/file1.pdf" in missing
        assert "http://example.com/file2.pdf" in missing

    def test_get_missing_files_some_exist(self, attachment_manager, mock_config):
        """Test identifying missing files when some files already exist"""
        attachment_manager.db.get_all_files.return_value = [
            "http://example.com/file1.pdf",
            "http://example.com/file2.pdf",
            "http://example.com/file3.pdf",
        ]

        # Create directory and add one existing file
        os.makedirs(mock_config["ATTACHMENTS_DIR"], exist_ok=True)
        with open(
            os.path.join(mock_config["ATTACHMENTS_DIR"], "file1.pdf"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("dummy content")

        missing = attachment_manager.get_missing_files()

        assert len(missing) == 2
        assert "http://example.com/file2.pdf" in missing
        assert "http://example.com/file3.pdf" in missing
        assert "http://example.com/file1.pdf" not in missing

    def test_get_missing_files_all_exist(self, attachment_manager, mock_config):
        """Test when all files already exist locally"""
        attachment_manager.db.get_all_files.return_value = [
            "http://example.com/file1.pdf",
        ]

        # Create directory and add the file
        os.makedirs(mock_config["ATTACHMENTS_DIR"], exist_ok=True)
        with open(
            os.path.join(mock_config["ATTACHMENTS_DIR"], "file1.pdf"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("dummy content")

        missing = attachment_manager.get_missing_files()

        assert len(missing) == 0

    @patch("attachments.fetch_attachment")
    def test_download_file_success(self, mock_fetch, attachment_manager):
        """Test successful single file download"""
        mock_fetch.return_value = {"status": "success"}

        result = attachment_manager.download_file("http://example.com/test.pdf")

        assert result["status"] == "success"
        assert "local_path" in result
        assert result["local_path"].endswith("test.pdf")
        mock_fetch.assert_called_once()

    @patch("attachments.fetch_attachment")
    def test_download_file_failure(self, mock_fetch, attachment_manager):
        """Test failed single file download"""
        mock_fetch.return_value = {"status": "error", "error": "Connection failed"}

        result = attachment_manager.download_file("http://example.com/test.pdf")

        assert result["status"] == "error"
        assert "Connection failed" in result["error"]

    @patch("attachments.fetch_attachment")
    @patch("attachments.random.shuffle")
    def test_download_with_threshold_stops_on_failures(
        self, mock_shuffle, mock_fetch, attachment_manager
    ):
        """Test that downloads stop after consecutive failures threshold"""
        # Don't actually shuffle for predictable testing
        mock_shuffle.side_effect = lambda x: x

        # All downloads fail
        mock_fetch.return_value = {"status": "error", "error": "Connection failed"}

        file_urls = [
            "http://example.com/file1.pdf",
            "http://example.com/file2.pdf",
            "http://example.com/file3.pdf",
            "http://example.com/file4.pdf",
            "http://example.com/file5.pdf",
        ]

        downloaded = attachment_manager.download_with_threshold(file_urls)

        # Should stop after 3 consecutive failures (max_consecutive_failures)
        assert len(downloaded) == 0
        assert mock_fetch.call_count == 3  # Should only try 3 times

    @patch("attachments.fetch_attachment")
    @patch("attachments.random.shuffle")
    def test_download_with_threshold_resets_on_success(
        self, mock_shuffle, mock_fetch, attachment_manager
    ):
        """Test that failure counter resets after successful download"""
        mock_shuffle.side_effect = lambda x: x

        # Fail, fail, succeed, fail, fail, succeed
        mock_fetch.side_effect = [
            {"status": "error", "error": "Failed"},
            {"status": "error", "error": "Failed"},
            {"status": "success"},
            {"status": "error", "error": "Failed"},
            {"status": "error", "error": "Failed"},
            {"status": "success"},
        ]

        file_urls = [f"http://example.com/file{i}.pdf" for i in range(6)]

        downloaded = attachment_manager.download_with_threshold(file_urls)

        # Should complete all downloads because successes reset the counter
        assert len(downloaded) == 2
        assert mock_fetch.call_count == 6

    @patch("attachments.fetch_attachment")
    @patch("attachments.random.shuffle")
    def test_download_with_threshold_all_success(
        self, mock_shuffle, mock_fetch, attachment_manager
    ):
        """Test successful download of all files"""
        mock_shuffle.side_effect = lambda x: x
        mock_fetch.return_value = {"status": "success"}

        file_urls = [f"http://example.com/file{i}.pdf" for i in range(5)]

        downloaded = attachment_manager.download_with_threshold(file_urls)

        assert len(downloaded) == 5
        assert mock_fetch.call_count == 5

    def test_download_no_missing_files(self, attachment_manager):
        """Test download when no files are missing"""
        attachment_manager.db.get_all_files.return_value = []

        result = attachment_manager.download()

        assert result == []

    @patch("attachments.fetch_attachment")
    def test_download_integration(self, mock_fetch, attachment_manager, mock_config):
        """Test full download workflow"""
        # Setup: some files in DB, one exists locally
        attachment_manager.db.get_all_files.return_value = [
            "http://example.com/file1.pdf",
            "http://example.com/file2.pdf",
        ]

        os.makedirs(mock_config["ATTACHMENTS_DIR"], exist_ok=True)
        with open(
            os.path.join(mock_config["ATTACHMENTS_DIR"], "file1.pdf"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write("existing")

        mock_fetch.return_value = {"status": "success"}

        downloaded = attachment_manager.download()

        # Should only download the missing file
        assert len(downloaded) == 1
        mock_fetch.assert_called_once()

    def test_upload_not_implemented(self, attachment_manager):
        """Test that upload method exists but is not yet implemented"""
        # Should not raise an error, just log
        attachment_manager.upload(["/path/to/file.pdf"])

    @patch("attachments.random.shuffle")
    def test_download_shuffles_files(
        self, mock_shuffle, attachment_manager, mock_config
    ):
        """Test that file list is shuffled before downloading"""
        attachment_manager.db.get_all_files.return_value = [
            "http://example.com/file1.pdf",
            "http://example.com/file2.pdf",
        ]

        os.makedirs(mock_config["ATTACHMENTS_DIR"], exist_ok=True)

        with patch("attachments.fetch_attachment") as mock_fetch:
            mock_fetch.return_value = {"status": "success"}
            attachment_manager.download()

        # Verify shuffle was called
        mock_shuffle.assert_called()

    def test_creates_attachments_directory(self, attachment_manager, mock_config):
        """Test that attachments directory is created if it doesn't exist"""
        # Directory should not exist initially
        assert not os.path.exists(mock_config["ATTACHMENTS_DIR"])

        attachment_manager.db.get_all_files.return_value = []
        attachment_manager.get_missing_files()

        # Directory should now exist
        assert os.path.exists(mock_config["ATTACHMENTS_DIR"])
