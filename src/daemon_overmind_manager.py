"""
Daemon Overmind Manager - Simplified file-based output capture
"""

import asyncio
import os
import subprocess
from typing import List
from ansi_to_html import AnsiToHtml

# Configure logging
import logging

logger = logging.getLogger(__name__)


class DaemonOvermindManager:
    """Simplified overmind manager with direct file tailing and synchronous processing"""

    def __init__(
        self,
        daemon_instance_id: str,
        database_manager,
        working_directory: str = None,
        overmind_args: List[str] = None,
        on_overmind_death=None,
    ):
        self.daemon_instance_id = daemon_instance_id
        self.db = database_manager
        self.working_directory = working_directory or os.getcwd()
        self.overmind_args = overmind_args or []
        self.on_overmind_death = on_overmind_death

        # Process management
        self.overmind_process = None
        self.is_running = False
        self.is_stopping = False

        # File-based output capture
        self.output_file = os.path.join(self.working_directory, "overmind_output.log")

        # Simple monitoring
        self._output_task = None

        # Process tracking (from procfile)
        self.processes = {}

        # ANSI to HTML converter
        self.ansi_converter = AnsiToHtml()

        logger.info(f"Daemon Overmind Manager initialized for instance {daemon_instance_id}")
        logger.info(f"Working directory: {self.working_directory}")

    async def start_overmind(self) -> bool:
        """Start overmind process with file output redirection"""
        logger.info("Starting overmind process...")

        # Check for existing overmind socket
        if os.path.exists(os.path.join(self.working_directory, ".overmind.sock")):
            logger.error("Another overmind instance is already running in this directory")
            return False

        try:
            # Remove existing output file for clean start
            if os.path.exists(self.output_file):
                os.remove(self.output_file)

            # Build command with output redirection
            cmd = ["overmind", "start", "--any-can-die", "--no-port"] + self.overmind_args
            logger.info(f"Starting overmind with command: {' '.join(cmd)}")
            logger.info(f"Output will be captured to: {self.output_file}")

            # Get environment with color forcing
            env = self.get_colored_env()

            # Start overmind process with output redirected to file
            cmd_str = " ".join(cmd) + f' > "{self.output_file}" 2>&1'
            self.overmind_process = await asyncio.create_subprocess_shell(cmd_str, cwd=self.working_directory, env=env)

            self.is_running = True
            logger.info(f"Overmind process started with PID: {self.overmind_process.pid}")

            # Give overmind a moment to start
            await asyncio.sleep(2)

            # Check if process is still running
            if self.overmind_process.returncode is not None:
                if self.overmind_process.returncode == 0:
                    logger.info(
                        f"Overmind process completed successfully with code: {self.overmind_process.returncode}"
                    )
                else:
                    # Read error from output file
                    try:
                        if os.path.exists(self.output_file):
                            with open(self.output_file, "r") as f:
                                error_text = f.read()
                            logger.error(f"Overmind process failed with code: {self.overmind_process.returncode}")
                            logger.error(f"Overmind output: {error_text[-1000:]}")  # Last 1000 chars
                        else:
                            logger.error(
                                f"Overmind process failed with code: {self.overmind_process.returncode} "
                                f"(no output file)"
                            )
                    except Exception as e:
                        logger.error(
                            f"Overmind process failed with code: {self.overmind_process.returncode} "
                            f"(could not read output: {e})"
                        )

                    self.is_running = False
                    return False

            # Load processes from Procfile
            await self._load_procfile_processes()

            # Start simple file monitoring
            self._output_task = asyncio.create_task(self._tail_output_file())

            logger.info("Overmind started successfully and monitoring tasks initiated")
            return True

        except Exception as e:
            logger.error(f"Failed to start overmind process: {e}", exc_info=True)
            return False

    async def _load_procfile_processes(self):
        """Load process definitions from Procfile"""
        procfile_path = os.path.join(self.working_directory, "Procfile")

        if not os.path.exists(procfile_path):
            logger.warning(f"No Procfile found at {procfile_path}")
            return

        try:
            with open(procfile_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and ":" in line and not line.startswith("#"):
                        try:
                            name, command = line.split(":", 1)
                            name = name.strip()
                            command = command.strip()
                            self.processes[name] = {"command": command, "status": "unknown"}
                        except ValueError:
                            logger.warning(f"Invalid Procfile line {line_num}: {line}")

            logger.info(f"Loaded {len(self.processes)} processes from Procfile: {list(self.processes.keys())}")

        except Exception as e:
            logger.error(f"Error loading Procfile: {e}", exc_info=True)

    async def _tail_output_file(self):
        """Tail the overmind output file and process all lines synchronously"""
        logger.info("Starting file-based output monitoring")

        # Track lines per process
        process_line_counts = {}
        total_lines = 0
        partial_line = ""  # Store incomplete line from previous read

        # Batch processing for database efficiency
        pending_lines = []

        # Keep file handle open for the entire monitoring session
        file_handle = None

        try:
            while self.is_running:
                try:
                    # Wait for output file to exist and open it once
                    if file_handle is None:
                        if not os.path.exists(self.output_file):
                            await asyncio.sleep(0.1)
                            continue
                        file_handle = open(self.output_file, "r", encoding="utf-8", errors="replace")

                    # Read new content from file (file handle stays open)
                    new_content = file_handle.read()

                    if new_content:
                        # Combine with any partial line from last read
                        full_content = partial_line + new_content

                        # Split into lines
                        lines = full_content.split("\n")

                        # Save the last part (might be incomplete line)
                        partial_line = lines[-1]

                        # Process all complete lines (all except the last)
                        for line in lines[:-1]:
                            if line.strip():  # Skip empty lines
                                # Update monitoring stats
                                process_name = self._extract_process_name(line)
                                process_line_counts[process_name] = process_line_counts.get(process_name, 0) + 1
                                total_lines += 1

                                # Add line to pending batch
                                pending_lines.append(line)

                        # Write immediately when caught up (no more data available)
                        if pending_lines:
                            try:
                                self._write_batch_to_database(pending_lines)
                                pending_lines = []
                            except Exception as e:
                                logger.error(f"Error writing batch to database: {e}")
                                pending_lines = []  # Clear to prevent memory buildup

                    # Check if overmind process has finished
                    if self.overmind_process.returncode is not None:
                        logger.info(f"🛑 Overmind process ended with code {self.overmind_process.returncode}")

                        # Process any final partial line if overmind is done
                        if partial_line.strip():
                            process_name = self._extract_process_name(partial_line)
                            process_line_counts[process_name] = process_line_counts.get(process_name, 0) + 1
                            total_lines += 1
                            pending_lines.append(partial_line)

                        # Write any remaining lines in batch
                        if pending_lines:
                            try:
                                self._write_batch_to_database(pending_lines)
                                logger.info(f"Wrote final batch of {len(pending_lines)} lines")
                                pending_lines = []
                            except Exception as e:
                                logger.error(f"Error writing final batch to database: {e}")

                        # Trigger death callback and exit
                        if self.on_overmind_death:
                            logger.info("🔄 Triggering daemon shutdown due to overmind death")
                            try:
                                if asyncio.iscoroutinefunction(self.on_overmind_death):
                                    asyncio.create_task(self.on_overmind_death())
                                else:
                                    self.on_overmind_death()
                            except Exception as e:
                                logger.error(f"Error calling overmind death callback: {e}", exc_info=True)
                        break

                    # Small delay to avoid busy looping
                    await asyncio.sleep(0.01)

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error reading output file: {e}")
                    await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info("Output monitoring cancelled")
        except Exception as e:
            logger.error(f"Error in output monitoring: {e}", exc_info=True)
        finally:
            # Close file handle if open
            if file_handle is not None:
                try:
                    file_handle.close()
                except Exception:
                    pass

            logger.info("Output monitoring stopped")

            # Log final statistics
            logger.info(
                f"📊 Output monitoring final stats: {total_lines} total lines "
                f"across {len(process_line_counts)} processes"
            )
            for proc, count in process_line_counts.items():
                if count > 1000:  # Only log processes with significant output
                    logger.info(f"  📈 {proc}: {count} lines")

    def _write_batch_to_database(self, lines: List[str]):
        """Write a batch of lines to the database in a single transaction (synchronous)"""
        if not lines:
            return

        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Begin transaction for batch insert
            cursor.execute("BEGIN TRANSACTION")

            # Parse all lines and prepare batch data
            batch_data = []
            for line in lines:
                process_name, html_content = self._parse_line_for_storage(line)
                batch_data.append((process_name, html_content))

            # Bulk insert all lines at once
            cursor.executemany("INSERT INTO output_lines (process, html) VALUES (?, ?)", batch_data)

            # Commit transaction
            conn.commit()
            logger.debug(f"Wrote batch of {len(lines)} lines to database")

        except Exception as e:
            logger.error(f"Error writing batch to database: {e}")
            try:
                if "conn" in locals():
                    conn.rollback()
            except Exception:
                pass

    def _parse_line_for_storage(self, line: str) -> tuple:
        """Parse a line and return (process_name, html_content) for database storage"""
        process_name = "system"

        # Convert ANSI escape sequences to HTML before storage
        html_content = self.ansi_converter.convert(line)

        # Parse overmind's output format: "processname | content"
        if " | " in line:
            parts = line.split(" | ", 1)
            if len(parts) == 2:
                process_part = parts[0].strip()

                # Remove ANSI color codes from process name
                import re

                ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
                potential_process = ansi_escape.sub("", process_part).strip()

                # Known processes
                known_processes = ["temporal", "backend", "web", "worker", "helper", "storybook", "bulk_test"]

                if potential_process in known_processes or potential_process in self.processes:
                    process_name = potential_process
                else:
                    process_name = potential_process if potential_process else "system"

        return process_name, html_content

    def _extract_process_name(self, line: str) -> str:
        """Extract process name from overmind output line for stats tracking"""
        if " | " in line:
            parts = line.split(" | ", 1)
            if len(parts) >= 2:
                process_part = parts[0].strip()
                # Remove ANSI color codes
                import re

                ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
                clean_process = ansi_escape.sub("", process_part)
                return clean_process if clean_process else "system"
        return "system"

    def get_colored_env(self):
        """Get environment with forced color output"""
        env = os.environ.copy()

        # Force color output for various tools
        env["FORCE_COLOR"] = "1"
        env["CLICOLOR_FORCE"] = "1"
        env["TERM"] = "xterm-256color"

        return env

    async def stop_overmind(self):
        """Stop the overmind process gracefully"""
        if not self.is_running or self.is_stopping:
            logger.info("Overmind already stopped or stopping")
            return

        self.is_stopping = True
        logger.info("Stopping overmind and monitoring tasks...")

        # Stop overmind process first - this will cause monitoring task to complete naturally
        if self.overmind_process and self.overmind_process.returncode is None:
            try:
                # Try graceful shutdown first
                quit_result = subprocess.run(
                    ["overmind", "quit"], cwd=self.working_directory, capture_output=True, text=True, timeout=5
                )
                if quit_result.returncode == 0:
                    logger.info("✅ 'overmind quit' successful")
                else:
                    logger.warning(f"'overmind quit' failed: {quit_result.stderr}")

                # Wait for process to exit
                await asyncio.sleep(2)

                # Force kill if still running
                if self.overmind_process.returncode is None:
                    logger.warning("Force terminating overmind process")
                    self.overmind_process.terminate()
                    await asyncio.sleep(1)
                    if self.overmind_process.returncode is None:
                        self.overmind_process.kill()

            except Exception as e:
                logger.error(f"Error shutting down overmind: {e}")

        # Wait for monitoring task to complete naturally (it should detect overmind death)
        if self._output_task and not self._output_task.done():
            try:
                await asyncio.wait_for(self._output_task, timeout=5.0)
                logger.info("Monitoring task completed naturally")
            except asyncio.TimeoutError:
                logger.warning("Monitoring task didn't complete in time, cancelling")
                self._output_task.cancel()
                try:
                    await self._output_task
                except asyncio.CancelledError:
                    pass

        # Clean up resources
        self.db.close_connections()

        self.is_running = False
        self.is_stopping = False

        logger.info("Overmind stopped successfully")
