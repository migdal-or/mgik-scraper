"""
Tests for scheduler module
"""

from unittest.mock import Mock
from unittest.mock import patch
import pytest
from scheduler import DaemonScheduler


class TestDaemonScheduler:
    """Tests for DaemonScheduler class"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create mock configuration"""
        return {
            "SCHEDULER_DEFAULT_INTERVAL": 1800,
            "SCHEDULER_MAX_INTERVAL": 28800,
            "SCHEDULER_MAX_MEMORY_MB": 500,
            "MGIK_DB_PATH": str(tmp_path / "test.db"),
            "ATTACHMENTS_DIR": str(tmp_path / "attachments"),
            "ATTACHMENTS_MAX_FAILURES": 3,
            "OUTPUT_PATH": str(tmp_path / "feed.xml"),
            "OUTPUT_MAX_ITEMS": 10,
            "MGIK_BASE_URL": "https://example.com",
            "RSS_FEED_TITLE": "Test Feed",
            "RSS_FEED_DESCRIPTION": "Test Description",
        }

    @pytest.fixture
    def scheduler(self, mock_config):
        """Create DaemonScheduler with mocked components"""
        with patch("scheduler.AttachmentManager"), patch("scheduler.RSSGenerator"):
            sched = DaemonScheduler(mock_config)
            sched.attachment_mgr = Mock()
            sched.output_gen = Mock()
            return sched

    def test_init(self, mock_config):
        """Test DaemonScheduler initialization"""
        with patch("scheduler.AttachmentManager"), patch("scheduler.RSSGenerator"):
            scheduler = DaemonScheduler(mock_config)
            assert scheduler.current_interval == 1800
            assert scheduler.max_interval == 28800
            assert scheduler.max_memory_mb == 500
            assert scheduler.running is True

    @patch("scheduler.load_decisions_from_web_to_database")
    def test_fetch_news_success(self, mock_load, scheduler):
        """Test successful news fetch"""
        mock_load.return_value = 5

        result = scheduler.fetch_news()

        assert result == 5
        mock_load.assert_called_once()

    @patch("scheduler.load_decisions_from_web_to_database")
    def test_fetch_news_error(self, mock_load, scheduler):
        """Test news fetch with error"""
        mock_load.side_effect = RuntimeError("Connection failed")

        result = scheduler.fetch_news()

        assert result is None

    def test_run_attachments(self, scheduler):
        """Test running attachment downloads"""
        scheduler.attachment_mgr.download.return_value = [
            "/path/file1.pdf",
            "/path/file2.pdf",
        ]

        count = scheduler.run_attachments()

        assert count == 2
        scheduler.attachment_mgr.download.assert_called_once()
        scheduler.attachment_mgr.upload.assert_called_once()

    def test_run_output_generation(self, scheduler):
        """Test running output generation"""
        scheduler.run_output_generation()

        scheduler.output_gen.generate.assert_called_once()

    @patch("scheduler.psutil.Process")
    def test_check_memory_below_threshold(self, mock_process, scheduler):
        """Test memory check when below threshold"""
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 100 * 1024 * 1024  # 100 MB
        mock_process.return_value = mock_proc

        should_exit = scheduler.check_memory_and_suicide()

        assert should_exit is False

    @patch("scheduler.psutil.Process")
    def test_check_memory_above_threshold(self, mock_process, scheduler):
        """Test memory check when above threshold"""
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 600 * 1024 * 1024  # 600 MB
        mock_process.return_value = mock_proc

        should_exit = scheduler.check_memory_and_suicide()

        assert should_exit is True

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_run_single_cycle_success(
        self, mock_load, mock_sleep, scheduler, mock_config
    ):
        """Test single successful cycle"""
        mock_load.return_value = 5
        scheduler.attachment_mgr.download.return_value = []

        # Run one cycle then stop (set running=False inside sleep)
        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_sleep.side_effect = stop_after_sleep

        scheduler.run()

        # Verify workflow
        mock_load.assert_called_once()
        scheduler.attachment_mgr.download.assert_called_once()
        scheduler.output_gen.generate.assert_called_once()

        # Verify interval was reset to default (not increased)
        assert scheduler.current_interval == mock_config["SCHEDULER_DEFAULT_INTERVAL"]

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_run_fetch_failed_no_attachments_uses_backoff(
        self, mock_load, mock_sleep, scheduler
    ):
        """Test backoff when fetch fails and no attachments downloaded"""
        mock_load.side_effect = RuntimeError("Connection failed")
        scheduler.attachment_mgr.download.return_value = []

        # Run one cycle then stop
        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_sleep.side_effect = stop_after_sleep

        scheduler.run()

        # Verify backoff applied (1800 * 1.5 = 2700)
        assert scheduler.current_interval == 2700
        # RSS should not be generated when no new content
        scheduler.output_gen.generate.assert_not_called()

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_run_fetch_failed_but_attachments_downloaded(
        self, mock_load, mock_sleep, scheduler, mock_config
    ):
        """Test no backoff when fetch fails but attachments succeed"""
        mock_load.side_effect = RuntimeError("Connection failed")
        scheduler.attachment_mgr.download.return_value = ["/path/file1.pdf"]

        # Run one cycle then stop
        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_sleep.side_effect = stop_after_sleep

        scheduler.run()

        # Should use normal interval (partial success)
        assert scheduler.current_interval == mock_config["SCHEDULER_DEFAULT_INTERVAL"]
        # RSS should be generated (new attachments)
        scheduler.output_gen.generate.assert_called_once()

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_run_generates_rss_on_new_records(self, mock_load, mock_sleep, scheduler):
        """Test RSS generation when new records found"""
        mock_load.return_value = 5
        scheduler.attachment_mgr.download.return_value = []

        # Run one cycle then stop
        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_sleep.side_effect = stop_after_sleep

        scheduler.run()

        scheduler.output_gen.generate.assert_called_once()

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_run_generates_rss_on_new_attachments(
        self, mock_load, mock_sleep, scheduler
    ):
        """Test RSS generation when new attachments downloaded"""
        mock_load.return_value = 0  # No new records
        scheduler.attachment_mgr.download.return_value = ["/path/file1.pdf"]

        # Run one cycle then stop
        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_sleep.side_effect = stop_after_sleep

        scheduler.run()

        scheduler.output_gen.generate.assert_called_once()

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_run_skips_rss_when_no_new_content(self, mock_load, mock_sleep, scheduler):
        """Test RSS generation skipped when no new content"""
        mock_load.return_value = 0  # No new records
        scheduler.attachment_mgr.download.return_value = []  # No new attachments

        # Run one cycle then stop
        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_sleep.side_effect = stop_after_sleep

        scheduler.run()

        scheduler.output_gen.generate.assert_not_called()

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    @patch("scheduler.psutil.Process")
    def test_run_exits_on_memory_threshold(
        self, mock_process, mock_load, _mock_sleep, scheduler
    ):
        """Test daemon exits when memory threshold exceeded"""
        mock_load.return_value = 0
        scheduler.attachment_mgr.download.return_value = []

        # Memory above threshold
        mock_proc = Mock()
        mock_proc.memory_info.return_value.rss = 600 * 1024 * 1024  # 600 MB
        mock_process.return_value = mock_proc

        scheduler.run()

        # Should exit after first cycle due to memory
        mock_load.assert_called_once()

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_run_exponential_backoff_caps_at_max(
        self, mock_load, mock_sleep, scheduler, mock_config
    ):
        """Test that backoff doesn't exceed max interval"""
        mock_load.side_effect = RuntimeError("Connection failed")
        scheduler.attachment_mgr.download.return_value = []

        # Set default interval close to max so that 1.5x would exceed max_interval
        # max_interval is 28800, so set default to 20000 -> 20000 * 1.5 = 30000
        # (should cap to 28800)
        scheduler.config["SCHEDULER_DEFAULT_INTERVAL"] = 20000

        # Run one cycle then stop
        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_sleep.side_effect = stop_after_sleep

        scheduler.run()

        # Should be capped at max_interval
        assert scheduler.current_interval == mock_config["SCHEDULER_MAX_INTERVAL"]

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_run_sleeps_between_cycles(self, mock_load, mock_sleep, scheduler):
        """Test that scheduler sleeps between cycles"""
        mock_load.return_value = 0
        scheduler.attachment_mgr.download.return_value = []

        # Run one cycle then stop
        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_sleep.side_effect = stop_after_sleep

        scheduler.run()

        # Should sleep for the interval duration
        mock_sleep.assert_called_once()
        assert mock_sleep.call_args[0][0] == scheduler.current_interval

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_run_handles_os_error(self, mock_load, mock_sleep, scheduler):
        """Test that scheduler handles OS errors gracefully"""
        mock_load.side_effect = OSError("Disk error")
        scheduler.attachment_mgr.download.return_value = []

        # Run one cycle then stop
        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_sleep.side_effect = stop_after_sleep

        # Should not crash
        scheduler.run()

        mock_load.assert_called_once()

    @patch("scheduler.time.sleep")
    @patch("scheduler.load_decisions_from_web_to_database")
    def test_workflow_order(self, mock_load, mock_sleep, scheduler):
        """Test that workflow executes in correct order"""
        call_order = []

        def track_load():
            call_order.append("fetch")
            return 1

        def track_download():
            call_order.append("download")
            return []

        def track_generate():
            call_order.append("generate")

        def stop_after_sleep(_interval):
            scheduler.running = False

        mock_load.side_effect = track_load
        scheduler.attachment_mgr.download.side_effect = track_download
        scheduler.output_gen.generate.side_effect = track_generate
        mock_sleep.side_effect = stop_after_sleep

        scheduler.run()

        # Verify correct order: fetch -> download -> generate
        assert call_order == ["fetch", "download", "generate"]
