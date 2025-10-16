"""
Native Process Manager - Direct process management without overmind/tmux
Handles subprocess spawning, output capture, and process lifecycle
"""

import asyncio
import logging
import os
import signal
import subprocess
import threading
import time
from typing import Dict, Optional, Callable, Any

from ansi_to_html import AnsiToHtml
from output_formatter import OutputFormatter
from procfile_parser import ProcfileEntry

logger = logging.getLogger(__name__)


class ManagedProcess:
    """Represents a single managed process"""

    def __init__(
        self,
        entry: ProcfileEntry,
        formatter: OutputFormatter,
        output_callback: Callable[[str, str], None],
        death_callback: Optional[Callable[[str], None]] = None,
        working_directory: str = None,
    ):
        self.entry = entry
        self.name = entry.name
        self.command = entry.command
        self.formatter = formatter
        self.output_callback = output_callback
        self.death_callback = death_callback
        self.working_directory = working_directory or os.getcwd()

        # Process state
        self.process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.status = "stopped"  # stopped, starting, running, dead
        self.exit_code: Optional[int] = None
        self.started_at: Optional[float] = None
        self.stopped_at: Optional[float] = None

        # Output monitoring threads
        self.stdout_thread: Optional[threading.Thread] = None
        self.stderr_thread: Optional[threading.Thread] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.should_stop = threading.Event()

        # ANSI converter
        self.ansi_converter = AnsiToHtml()

    def start(self) -> bool:
        """Start the process"""
        if self.is_running():
            logger.warning(f"Process {self.name} is already running")
            return False

        try:
            logger.info(f"Starting process: {self.name}")
            self.status = "starting"
            self.should_stop.clear()

            # Start process with pipes for stdout/stderr
            self.process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.working_directory,
                env=self._get_env(),
                preexec_fn=os.setsid,  # Create new process group for clean shutdown
            )

            self.pid = self.process.pid
            self.started_at = time.time()
            self.stopped_at = None
            self.exit_code = None
            self.status = "running"

            # Start output capture threads
            self.stdout_thread = threading.Thread(target=self._capture_stdout, daemon=True, name=f"{self.name}-stdout")
            self.stderr_thread = threading.Thread(target=self._capture_stderr, daemon=True, name=f"{self.name}-stderr")
            self.monitor_thread = threading.Thread(
                target=self._monitor_process, daemon=True, name=f"{self.name}-monitor"
            )

            self.stdout_thread.start()
            self.stderr_thread.start()
            self.monitor_thread.start()

            logger.info(f"Process {self.name} started with PID {self.pid}")
            return True

        except Exception as e:
            logger.error(f"Failed to start process {self.name}: {e}")
            self.status = "dead"
            return False

    def stop(self, timeout: float = 5.0) -> bool:
        """Stop the process gracefully"""
        if not self.is_running():
            logger.info(f"Process {self.name} is not running")
            return True

        try:
            logger.info(f"Stopping process: {self.name} (PID {self.pid})")
            self.should_stop.set()

            if self.process:
                # Try graceful shutdown first (SIGTERM to process group)
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                    logger.info(f"Sent SIGTERM to process group {self.name}")
                except ProcessLookupError:
                    logger.warning(f"Process {self.name} already terminated")
                    return True

                # Wait for process to exit
                try:
                    self.process.wait(timeout=timeout)
                    logger.info(f"Process {self.name} terminated gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if still running
                    logger.warning(f"Process {self.name} did not stop gracefully, force killing")
                    try:
                        os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                        self.process.wait(timeout=2.0)
                    except Exception as e:
                        logger.error(f"Error force killing process {self.name}: {e}")

                self.exit_code = self.process.returncode
                self.stopped_at = time.time()

            # Wait for threads to finish
            self._wait_for_threads(timeout=2.0)

            self.status = "stopped"
            self.process = None
            self.pid = None

            logger.info(f"Process {self.name} stopped")
            return True

        except Exception as e:
            logger.error(f"Error stopping process {self.name}: {e}")
            return False

    def restart(self) -> bool:
        """Restart the process"""
        logger.info(f"Restarting process: {self.name}")
        self.stop()
        time.sleep(0.5)  # Brief pause between stop and start
        return self.start()

    def is_running(self) -> bool:
        """Check if process is currently running"""
        return self.status == "running" and self.process is not None

    def is_alive(self) -> bool:
        """Check if process is alive"""
        if self.process:
            return self.process.poll() is None
        return False

    def get_status(self) -> Dict[str, Any]:
        """Get process status information"""
        return {
            "name": self.name,
            "status": self.status,
            "pid": self.pid,
            "exit_code": self.exit_code,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "uptime": time.time() - self.started_at if self.started_at and self.is_running() else 0,
        }

    def _get_env(self) -> Dict[str, str]:
        """Get environment variables for process"""
        env = os.environ.copy()

        # Force color output
        env["FORCE_COLOR"] = "1"
        env["CLICOLOR_FORCE"] = "1"
        env["TERM"] = "xterm-256color"

        return env

    def _capture_stdout(self):
        """Thread function to capture stdout"""
        try:
            if not self.process or not self.process.stdout:
                return

            for line in iter(self.process.stdout.readline, b""):
                if self.should_stop.is_set():
                    break

                try:
                    # Decode line
                    text = line.decode("utf-8", errors="replace").rstrip("\n\r")
                    if text:  # Skip empty lines
                        # Format output with process name and color
                        formatted_line = self.formatter.format_output_line(self.name, text)
                        # Convert ANSI to HTML
                        html_content = self.ansi_converter.convert(formatted_line)
                        # Send to callback
                        self.output_callback(self.name, html_content)

                except Exception as e:
                    logger.error(f"Error processing stdout from {self.name}: {e}")

        except Exception as e:
            logger.error(f"Error capturing stdout from {self.name}: {e}")
        finally:
            if self.process and self.process.stdout:
                self.process.stdout.close()

    def _capture_stderr(self):
        """Thread function to capture stderr"""
        try:
            if not self.process or not self.process.stderr:
                return

            for line in iter(self.process.stderr.readline, b""):
                if self.should_stop.is_set():
                    break

                try:
                    # Decode line
                    text = line.decode("utf-8", errors="replace").rstrip("\n\r")
                    if text:  # Skip empty lines
                        # Format output with process name and color (stderr gets same treatment)
                        formatted_line = self.formatter.format_output_line(self.name, text)
                        # Convert ANSI to HTML
                        html_content = self.ansi_converter.convert(formatted_line)
                        # Send to callback
                        self.output_callback(self.name, html_content)

                except Exception as e:
                    logger.error(f"Error processing stderr from {self.name}: {e}")

        except Exception as e:
            logger.error(f"Error capturing stderr from {self.name}: {e}")
        finally:
            if self.process and self.process.stderr:
                self.process.stderr.close()

    def _monitor_process(self):
        """Thread function to monitor process health"""
        try:
            if not self.process:
                return

            # Wait for process to exit
            self.exit_code = self.process.wait()
            self.stopped_at = time.time()

            if not self.should_stop.is_set():
                # Process died unexpectedly
                logger.warning(f"Process {self.name} died unexpectedly with exit code {self.exit_code}")
                self.status = "dead"

                # Call death callback
                if self.death_callback:
                    try:
                        self.death_callback(self.name)
                    except Exception as e:
                        logger.error(f"Error calling death callback for {self.name}: {e}")
            else:
                # Process was intentionally stopped
                self.status = "stopped"

        except Exception as e:
            logger.error(f"Error monitoring process {self.name}: {e}")

    def _wait_for_threads(self, timeout: float):
        """Wait for output capture threads to finish"""
        threads = [self.stdout_thread, self.stderr_thread, self.monitor_thread]

        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=timeout)


class NativeProcessManager:
    """Manages multiple processes with direct subprocess control"""

    def __init__(
        self,
        entries: list,
        formatter: OutputFormatter,
        database_manager,
        working_directory: str = None,
    ):
        self.entries = entries
        self.formatter = formatter
        self.db = database_manager
        self.working_directory = working_directory or os.getcwd()

        self.processes: Dict[str, ManagedProcess] = {}
        self.is_running = False

        logger.info(f"Native Process Manager initialized with {len(entries)} processes")

    def start_all(self) -> bool:
        """Start all processes"""
        logger.info("Starting all processes...")
        self.is_running = True

        success = True
        for entry in self.entries:
            process = ManagedProcess(
                entry=entry,
                formatter=self.formatter,
                output_callback=self._handle_output,
                death_callback=self._handle_process_death,
                working_directory=self.working_directory,
            )

            if process.start():
                self.processes[entry.name] = process
            else:
                logger.error(f"Failed to start process: {entry.name}")
                success = False

        logger.info(f"Started {len(self.processes)}/{len(self.entries)} processes")
        return success

    def stop_all(self, timeout: float = 5.0) -> bool:
        """Stop all processes gracefully"""
        logger.info("Stopping all processes...")
        self.is_running = False

        success = True
        for process in self.processes.values():
            if not process.stop(timeout=timeout):
                success = False

        self.processes.clear()
        logger.info("All processes stopped")
        return success

    def restart_process(self, process_name: str) -> bool:
        """Restart a specific process"""
        process = self.processes.get(process_name)
        if not process:
            logger.error(f"Process not found: {process_name}")
            return False

        return process.restart()

    def stop_process(self, process_name: str) -> bool:
        """Stop a specific process"""
        process = self.processes.get(process_name)
        if not process:
            logger.error(f"Process not found: {process_name}")
            return False

        return process.stop()

    def get_process_status(self, process_name: str) -> Optional[Dict[str, Any]]:
        """Get status for a specific process"""
        process = self.processes.get(process_name)
        if not process:
            return None

        return process.get_status()

    def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status for all processes"""
        return {name: process.get_status() for name, process in self.processes.items()}

    def _handle_output(self, process_name: str, html_content: str):
        """
        Handle output from a process
        Stores to database for GUI consumption
        """
        try:
            self.db.store_output_line(process_name, html_content)
        except Exception as e:
            logger.error(f"Error storing output for {process_name}: {e}")

    def _handle_process_death(self, process_name: str):
        """
        Handle unexpected process death
        Called when a process dies unexpectedly
        """
        logger.warning(f"Process {process_name} died unexpectedly")

        # Store notification in output
        death_message = f"\n🔴 Process {process_name} died at {time.strftime('%H:%M:%S')}\n"
        formatted = self.formatter.format_output_line(process_name, death_message)
        html_content = AnsiToHtml().convert(formatted)

        try:
            self.db.store_output_line(process_name, html_content)
        except Exception as e:
            logger.error(f"Error storing death notification: {e}")
