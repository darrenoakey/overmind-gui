#!/usr/bin/env python3
"""
Native Daemon Manager - PID-based daemon lifecycle management for native daemon
Similar to daemon_manager.py but for native_daemon.py
"""

import os
import signal
import subprocess
import time
import logging
from typing import Optional

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger(__name__)


class NativeDaemonManager:
    """Daemon lifecycle manager for native daemon"""

    def __init__(self, working_directory: str):
        self.working_directory = working_directory
        self.pid_file = os.path.join(working_directory, "overmind-daemon.pid")

    def is_daemon_running(self) -> bool:
        """Check if native daemon is running"""
        if not os.path.exists(self.pid_file):
            logger.debug("No PID file found for native daemon")
            return False

        try:
            with open(self.pid_file, "r") as f:
                pid_str = f.read().strip()

            if not pid_str.isdigit():
                logger.warning(f"Invalid PID in file: {pid_str}")
                self._cleanup_stale_pid_file()
                return False

            pid = int(pid_str)

            # Check if process exists AND is not a zombie
            try:
                os.kill(pid, 0)  # Check if PID exists

                # If psutil is available, do more thorough checks
                if psutil:
                    try:
                        proc = psutil.Process(pid)

                        # Check if zombie
                        if proc.status() == psutil.STATUS_ZOMBIE:
                            logger.warning(f"Native daemon PID {pid} is a zombie process - cleaning up")
                            self._cleanup_stale_pid_file()
                            return False

                        # Verify it's actually our daemon
                        try:
                            cmdline = proc.cmdline()
                            if cmdline and 'native_daemon.py' in ' '.join(cmdline):
                                logger.debug(f"Native daemon running with PID {pid}")
                                return True
                            else:
                                logger.warning(f"PID {pid} exists but is not native_daemon.py: {cmdline}")
                                self._cleanup_stale_pid_file()
                                return False
                        except (psutil.AccessDenied, psutil.ZombieProcess):
                            # Can't access cmdline due to permissions or process is zombie
                            # Since we already checked for zombie above, this is likely AccessDenied
                            # Trust that the PID exists and isn't a zombie
                            logger.debug(f"Native daemon PID {pid} exists but can't verify cmdline (permission denied)")
                            return True

                    except psutil.NoSuchProcess:
                        logger.info(f"Process {pid} no longer exists")
                        self._cleanup_stale_pid_file()
                        return False
                else:
                    # Without psutil, just trust os.kill check (less reliable)
                    logger.debug(f"Native daemon appears to be running with PID {pid} (psutil not available for verification)")
                    return True

            except OSError:
                logger.info(f"Stale PID file found (process {pid} no longer exists)")
                self._cleanup_stale_pid_file()
                return False

        except Exception as e:
            logger.error(f"Unexpected error checking daemon PID: {type(e).__name__}: {e}", exc_info=True)
            # Don't cleanup PID file for unexpected errors - let the daemon continue
            # Only cleanup if we're sure the process is gone
            return False

    def get_daemon_pid(self) -> Optional[int]:
        """Get the daemon PID if running"""
        if not self.is_daemon_running():
            return None

        try:
            with open(self.pid_file, "r") as f:
                return int(f.read().strip())
        except Exception as e:
            logger.error(f"Error reading daemon PID: {e}")
            return None

    def start_daemon(self) -> bool:
        """Start the native daemon if not already running"""
        if self.is_daemon_running():
            logger.info("Native daemon already running")
            return True

        logger.info("Starting native daemon...")

        try:
            # Get path to daemon script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            daemon_script = os.path.join(script_dir, "native_daemon.py")

            if not os.path.exists(daemon_script):
                logger.error(f"Native daemon script not found: {daemon_script}")
                return False

            # Build command
            cmd = ["python", daemon_script, "--working-dir", self.working_directory]

            # Start daemon in background
            logger.info(f"Starting native daemon with: {' '.join(cmd)}")
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,  # Detach from parent
            )

            # Wait for daemon to start
            time.sleep(2)

            # Check if daemon is now running
            if self.is_daemon_running():
                logger.info(f"Native daemon started successfully with PID {self.get_daemon_pid()}")
                return True
            else:
                logger.error("Native daemon failed to start (no PID file created)")
                return False

        except Exception as e:
            logger.error(f"Error starting native daemon: {e}")
            return False

    def stop_daemon(self) -> bool:
        """Stop the native daemon gracefully"""
        pid = self.get_daemon_pid()
        if not pid:
            logger.info("No native daemon running")
            return True

        try:
            logger.info(f"Stopping native daemon with PID {pid}")

            # Send SIGTERM signal for graceful shutdown
            os.kill(pid, signal.SIGTERM)
            logger.info("Sent SIGTERM to native daemon")

            # Wait for daemon to shut down gracefully
            for i in range(30):  # Wait up to 30 seconds
                if not self.is_daemon_running():
                    logger.info("Native daemon stopped gracefully")
                    return True
                time.sleep(1)

            # If still running, send SIGKILL
            if self.is_daemon_running():
                logger.warning("Force killing native daemon with SIGKILL")
                os.kill(pid, signal.SIGKILL)
                time.sleep(2)

                if not self.is_daemon_running():
                    logger.info("Native daemon force killed")
                    return True
                else:
                    logger.error("Failed to kill native daemon")
                    return False

            return True

        except Exception as e:
            logger.error(f"Error stopping native daemon: {e}")
            return False

    def ensure_daemon_running(self) -> bool:
        """Ensure daemon is running, start if necessary"""
        if self.is_daemon_running():
            return True
        return self.start_daemon()

    def _cleanup_stale_pid_file(self):
        """Remove stale PID file"""
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
                logger.debug("Removed stale PID file")
        except Exception as e:
            logger.warning(f"Failed to remove stale PID file: {e}")
