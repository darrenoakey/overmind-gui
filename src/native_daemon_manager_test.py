#!/usr/bin/env python3
"""
Tests for native_daemon_manager module
Validates PID checking logic and error handling
"""

import os
import tempfile
import unittest
from unittest.mock import Mock, patch, MagicMock
import psutil

from native_daemon_manager import NativeDaemonManager


class TestNativeDaemonManager(unittest.TestCase):
    """Test native daemon manager functionality"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.manager = NativeDaemonManager(self.temp_dir)

    def tearDown(self):
        """Clean up test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_no_pid_file_returns_false(self):
        """Daemon not running when PID file doesn't exist"""
        self.assertFalse(self.manager.is_daemon_running())

    def test_invalid_pid_in_file(self):
        """Invalid PID in file is treated as not running"""
        # Write invalid PID
        with open(self.manager.pid_file, "w") as f:
            f.write("not-a-number")

        self.assertFalse(self.manager.is_daemon_running())
        # PID file should be cleaned up
        self.assertFalse(os.path.exists(self.manager.pid_file))

    def test_nonexistent_pid(self):
        """Non-existent PID is treated as not running"""
        # Write a PID that definitely doesn't exist
        fake_pid = 999999
        with open(self.manager.pid_file, "w") as f:
            f.write(str(fake_pid))

        self.assertFalse(self.manager.is_daemon_running())
        # PID file should be cleaned up
        self.assertFalse(os.path.exists(self.manager.pid_file))

    @patch('native_daemon_manager.psutil')
    def test_zombie_process(self, mock_psutil_module):
        """Zombie process is treated as not running"""
        # Write current process PID (we know it exists)
        current_pid = os.getpid()
        with open(self.manager.pid_file, "w") as f:
            f.write(str(current_pid))

        # Mock psutil.Process to return a zombie
        mock_proc = Mock()
        mock_proc.status.return_value = psutil.STATUS_ZOMBIE
        mock_psutil_module.Process.return_value = mock_proc
        mock_psutil_module.STATUS_ZOMBIE = psutil.STATUS_ZOMBIE

        self.assertFalse(self.manager.is_daemon_running())
        # PID file should be cleaned up
        self.assertFalse(os.path.exists(self.manager.pid_file))

    @patch('native_daemon_manager.psutil')
    def test_access_denied_still_considered_running(self, mock_psutil_module):
        """Process with AccessDenied on cmdline is still considered running"""
        # Write current process PID (we know it exists)
        current_pid = os.getpid()
        with open(self.manager.pid_file, "w") as f:
            f.write(str(current_pid))

        # Mock psutil.Process to raise AccessDenied on cmdline
        mock_proc = Mock()
        mock_proc.status.return_value = psutil.STATUS_RUNNING
        mock_proc.cmdline.side_effect = psutil.AccessDenied(current_pid)
        mock_psutil_module.Process.return_value = mock_proc
        mock_psutil_module.STATUS_ZOMBIE = psutil.STATUS_ZOMBIE
        mock_psutil_module.STATUS_RUNNING = psutil.STATUS_RUNNING
        mock_psutil_module.AccessDenied = psutil.AccessDenied
        mock_psutil_module.ZombieProcess = psutil.ZombieProcess

        # Should still be considered running despite AccessDenied
        self.assertTrue(self.manager.is_daemon_running())
        # PID file should NOT be cleaned up
        self.assertTrue(os.path.exists(self.manager.pid_file))

    @patch('native_daemon_manager.psutil')
    def test_wrong_process_name(self, mock_psutil_module):
        """Process with wrong name is not considered the daemon"""
        # Write current process PID
        current_pid = os.getpid()
        with open(self.manager.pid_file, "w") as f:
            f.write(str(current_pid))

        # Mock psutil.Process to return wrong process name
        mock_proc = Mock()
        mock_proc.status.return_value = psutil.STATUS_RUNNING
        mock_proc.cmdline.return_value = ['/usr/bin/python3', 'some_other_script.py']
        mock_psutil_module.Process.return_value = mock_proc
        mock_psutil_module.STATUS_ZOMBIE = psutil.STATUS_ZOMBIE
        mock_psutil_module.STATUS_RUNNING = psutil.STATUS_RUNNING

        self.assertFalse(self.manager.is_daemon_running())
        # PID file should be cleaned up
        self.assertFalse(os.path.exists(self.manager.pid_file))

    @patch('native_daemon_manager.psutil')
    def test_correct_process_name(self, mock_psutil_module):
        """Process with correct name is considered running"""
        # Write current process PID
        current_pid = os.getpid()
        with open(self.manager.pid_file, "w") as f:
            f.write(str(current_pid))

        # Mock psutil.Process to return correct process name
        mock_proc = Mock()
        mock_proc.status.return_value = psutil.STATUS_RUNNING
        mock_proc.cmdline.return_value = ['/usr/bin/python3', 'native_daemon.py', '--working-dir', '/tmp']
        mock_psutil_module.Process.return_value = mock_proc
        mock_psutil_module.STATUS_ZOMBIE = psutil.STATUS_ZOMBIE
        mock_psutil_module.STATUS_RUNNING = psutil.STATUS_RUNNING

        self.assertTrue(self.manager.is_daemon_running())
        # PID file should NOT be cleaned up
        self.assertTrue(os.path.exists(self.manager.pid_file))

    @patch('native_daemon_manager.psutil')
    def test_no_such_process(self, mock_psutil_module):
        """NoSuchProcess exception is handled correctly"""
        # Write a PID
        with open(self.manager.pid_file, "w") as f:
            f.write("12345")

        # Mock psutil.Process to raise NoSuchProcess
        mock_psutil_module.Process.side_effect = psutil.NoSuchProcess(12345)
        mock_psutil_module.NoSuchProcess = psutil.NoSuchProcess

        self.assertFalse(self.manager.is_daemon_running())
        # PID file should be cleaned up
        self.assertFalse(os.path.exists(self.manager.pid_file))


if __name__ == "__main__":
    unittest.main()
