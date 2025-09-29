#!/usr/bin/env python3
"""
Daemon Manager - Simple PID - based daemon lifecycle management
Replaces the complex discovery system with simple PID file checking
"""

import os
import signal
import subprocess
import time
import logging
import unittest
import tempfile
import shutil
from typing import Optional

logger = logging.getLogger(__name__)


class DaemonManager:
    """Simple daemon lifecycle manager using PID files"""

    def __init__(self, working_directory: str):
        self.working_directory = working_directory
        self.pid_file = os.path.join(working_directory, 'overmind - daemon.pid')

    def is_daemon_running(self) -> bool:
        """Check if daemon is running by checking PID file and process"""
        if not os.path.exists(self.pid_file):
            logger.debug("No PID file found")
            return False

        try:
            with open(self.pid_file, 'r') as f:
                pid_str = f.read().strip()

            if not pid_str.isdigit():
                logger.warning(f"Invalid PID in file: {pid_str}")
                self._cleanup_stale_pid_file()
                return False

            pid = int(pid_str)

            # Check if process exists and is still running
            try:
                # On Unix, signal 0 checks if process exists without sending a signal
                os.kill(pid, 0)
                logger.debug(f"Daemon running with PID {pid}")
                return True
            except OSError:
                # Process doesn't exist
                logger.info(f"Stale PID file found (process {pid} no longer exists)")
                self._cleanup_stale_pid_file()
                return False

        except Exception as e:
            logger.warning(f"Error checking daemon PID: {e}")
            self._cleanup_stale_pid_file()
            return False

    def get_daemon_pid(self) -> Optional[int]:
        """Get the daemon PID if running"""
        if not self.is_daemon_running():
            return None

        try:
            with open(self.pid_file, 'r') as f:
                return int(f.read().strip())
        except Exception as e:
            logger.error(f"Error reading daemon PID: {e}")
            return None

    def start_daemon(self, overmind_args: list = None) -> bool:
        """Start the daemon if not already running"""
        if self.is_daemon_running():
            logger.info("Daemon already running")
            return True

        logger.info("Starting daemon...")

        try:
            # Get path to daemon script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            daemon_script = os.path.join(script_dir, 'overmind_daemon.py')

            if not os.path.exists(daemon_script):
                logger.error(f"Daemon script not found: {daemon_script}")
                return False

            # Build command
            cmd = ['python', daemon_script, '--working - dir', self.working_directory]
            if overmind_args:
                cmd.extend(overmind_args)

            # Start daemon in background
            logger.info(f"Starting daemon with: {' '.join(cmd)}")
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent
            )

            # Wait a moment to see if daemon starts
            time.sleep(2)

            # Check if daemon is now running
            if self.is_daemon_running():
                logger.info(f"Daemon started successfully with PID {self.get_daemon_pid()}")
                return True
            else:
                logger.error("Daemon failed to start (no PID file created)")
                return False

        except Exception as e:
            logger.error(f"Error starting daemon: {e}")
            return False

    def stop_daemon(self) -> bool:
        """Stop the daemon gracefully"""
        pid = self.get_daemon_pid()
        if not pid:
            logger.info("No daemon running")
            return True

        try:
            logger.info(f"Stopping daemon with PID {pid}")

            # First try overmind quit to gracefully shut down overmind
            try:
                subprocess.run(['overmind', 'quit'],
                             cwd=self.working_directory,
                             timeout=10,
                             capture_output=True)
                logger.info("Sent overmind quit command")

                # Wait for daemon to shut down naturally
                for i in range(30):  # Wait up to 30 seconds
                    if not self.is_daemon_running():
                        logger.info("Daemon stopped gracefully")
                        return True
                    time.sleep(1)

            except subprocess.TimeoutExpired:
                logger.warning("Overmind quit command timed out")
            except FileNotFoundError:
                logger.warning("Overmind command not found, sending signal directly")

            # If still running, send TERM signal to daemon
            if self.is_daemon_running():
                logger.info("Sending SIGTERM to daemon")
                os.kill(pid, signal.SIGTERM)

                # Wait for graceful shutdown
                for i in range(10):
                    if not self.is_daemon_running():
                        logger.info("Daemon stopped after SIGTERM")
                        return True
                    time.sleep(1)

            # If still running, force kill
            if self.is_daemon_running():
                logger.warning("Force killing daemon with SIGKILL")
                os.kill(pid, signal.SIGKILL)
                time.sleep(2)

                if not self.is_daemon_running():
                    logger.info("Daemon force killed")
                    return True
                else:
                    logger.error("Failed to kill daemon")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error stopping daemon: {e}")
            return False

    def ensure_daemon_running(self, overmind_args: list = None) -> bool:
        """Ensure daemon is running, start if necessary"""
        if self.is_daemon_running():
            return True
        return self.start_daemon(overmind_args)

    def _cleanup_stale_pid_file(self):
        """Remove stale PID file"""
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
                logger.debug("Removed stale PID file")
        except Exception as e:
            logger.warning(f"Failed to remove stale PID file: {e}")


# Tests


class TestDaemonManager(unittest.TestCase):
    """Test daemon manager functionality"""

    def setUp(self):
        """Set up test directory"""
        self.test_dir = tempfile.mkdtemp()
        self.manager = DaemonManager(self.test_dir)

    def tearDown(self):
        """Clean up test directory"""
        shutil.rmtree(self.test_dir)

    def test_no_daemon_initially(self):
        """Test that no daemon is detected initially"""
        self.assertFalse(self.manager.is_daemon_running())
        self.assertIsNone(self.manager.get_daemon_pid())

    def test_stale_pid_file_cleanup(self):
        """Test cleanup of stale PID files"""
        # Create a PID file with non - existent PID
        nonexistent_pid = 999999  # Very unlikely to exist
        with open(self.manager.pid_file, 'w') as f:
            f.write(str(nonexistent_pid))

        # Should detect it's stale and clean up
        self.assertFalse(self.manager.is_daemon_running())
        self.assertFalse(os.path.exists(self.manager.pid_file))

    def test_valid_pid_file(self):
        """Test detection of valid running process"""
        # Use current process PID as a test
        current_pid = os.getpid()
        with open(self.manager.pid_file, 'w') as f:
            f.write(str(current_pid))

        # Should detect as running
        self.assertTrue(self.manager.is_daemon_running())
        self.assertEqual(self.manager.get_daemon_pid(), current_pid)

    def test_invalid_pid_file_content(self):
        """Test handling of invalid PID file content"""
        # Create PID file with invalid content
        with open(self.manager.pid_file, 'w') as f:
            f.write("not_a_number")

        self.assertFalse(self.manager.is_daemon_running())
        self.assertFalse(os.path.exists(self.manager.pid_file))


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
