"""
Daemon Overmind Manager - Independent overmind process management
Extracted and enhanced from OvermindController to run in daemon process

Key Features:
- Owns and manages overmind subprocess independently
- Captures and stores all output persistently
- Handles process lifecycle without GUI dependency
- Provides API for process control operations
"""

import asyncio
import os
import signal
import subprocess
import time
import logging
from typing import Optional, Callable, Dict, Any, List


from daemon_config import daemon_config

logger = logging.getLogger(__name__)


class DaemonOvermindManager:
    """Manages overmind process lifecycle independently of GUI"""

    def __init__(self, daemon_instance_id: str, database_manager,
                 working_directory: str = None, overmind_args: List[str] = None,
                 on_overmind_death: Callable = None):
        """
        Initialize overmind manager for daemon

        Args:
            daemon_instance_id: Unique ID of daemon instance
            database_manager: Database manager for persistent storage
            working_directory: Working directory for overmind
            overmind_args: Additional arguments for overmind start
            on_overmind_death: Callback when overmind dies unexpectedly
        """
        self.daemon_instance_id = daemon_instance_id
        self.db = database_manager
        self.working_directory = working_directory or os.getcwd()
        self.overmind_args = overmind_args or []
        self.on_overmind_death = on_overmind_death

        # Process state
        self.overmind_process: Optional[asyncio.subprocess.Process] = None
        self.is_running = False
        self.is_stopping = False

        # Output processing
        self.message_id_counter = 0
        self.line_buffer = []
        self.last_output_time = time.time()

        # Producer - consumer queue for fast output handling
        self.output_queue: asyncio.Queue = asyncio.Queue(maxsize=10000)
        self.poison_pill = object()  # Sentinel value to stop consumers

        # Monitoring tasks
        self._output_task: Optional[asyncio.Task] = None
        self._status_monitor_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_task: Optional[asyncio.Task] = None
        self._db_writer_tasks: List[asyncio.Task] = []  # Database writer consumer tasks

        # Callbacks for real - time updates (for future API clients)
        self.output_callbacks: List[Callable] = []
        self.status_callbacks: List[Callable] = []

        # Process information
        self.processes: Dict[str, Dict] = {}

        logger.info(f"Daemon Overmind Manager initialized for instance {daemon_instance_id}")
        logger.info(f"Working directory: {self.working_directory}")

    def add_output_callback(self, callback: Callable):
        """Add callback for real - time output updates"""
        self.output_callbacks.append(callback)

    def add_status_callback(self, callback: Callable):
        """Add callback for real - time status updates"""
        self.status_callbacks.append(callback)

    def get_colored_env(self) -> Dict[str, str]:
        """Get environment variables that enable color output without forcing specific colors"""
        env = os.environ.copy()

        # Only set minimal color support - let overmind choose its own colors
        if 'TERM' not in env or not env['TERM']:
            env['TERM'] = 'xterm - 256color'
        if 'COLORTERM' not in env:
            env['COLORTERM'] = 'truecolor'

        # Remove NO_COLOR if it exists to ensure colors are not disabled
        env.pop('NO_COLOR', None)

        return env

    async def start_overmind(self) -> bool:
        """
        Start overmind process and monitoring tasks
        Returns True if successful, False otherwise
        """

        if self.is_running:
            logger.warning("Overmind already running")
            return True

        logger.info("Starting overmind process...")

        try:
            # Check if overmind is available
            result = await asyncio.create_subprocess_exec(
                "overmind", "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await result.wait()
            if result.returncode != 0:
                logger.error("Overmind binary not found or not working")
                return False
        except FileNotFoundError:
            logger.error("Overmind binary not found")
            return False

        # Check for existing socket file - but ONLY remove if we're in a test directory or explicitly asked
        socket_file = os.path.join(self.working_directory, ".overmind.sock")
        if os.path.exists(socket_file):
            # Only remove socket file if we're in a temporary test directory
            # This prevents accidentally killing other overmind instances
            is_test_dir = 'overmind - daemon - test-' in self.working_directory or '/tmp' in self.working_directory

            if is_test_dir:
                logger.warning(f"Socket file {socket_file} already exists in test directory")
                try:
                    os.unlink(socket_file)
                    logger.info("Removed stale test socket file")
                except OSError as e:
                    logger.error(f"Could not remove socket file: {e}")
                    return False
            else:
                logger.error(f"Socket file {socket_file} already exists")
                logger.error("Another overmind instance is already running in this directory")
                logger.error("Cannot start daemon - would conflict with existing overmind")
                return False

        try:
            # Build overmind start command
            cmd = ["overmind", "start", "--any - can - die", "--no - port"] + self.overmind_args

            if self.overmind_args:
                logger.info(f"Using additional overmind arguments: {' '.join(self.overmind_args)}")

            logger.info(f"Starting overmind with command: {' '.join(cmd)}")

            # Get environment with color forcing
            env = self.get_colored_env()

            # Start overmind process
            self.overmind_process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.working_directory,
                env=env
            )

            self.is_running = True
            logger.info(f"Overmind process started with PID: {self.overmind_process.pid}")

            # Give overmind a moment to start
            await asyncio.sleep(2)

            # Check if process is still running
            if self.overmind_process.returncode is not None:
                logger.error(f"Overmind process exited immediately with code: {self.overmind_process.returncode}")
                self.is_running = False
                return False

            # Load processes from Procfile
            await self._load_procfile_processes()

            # Start monitoring tasks
            self._output_task = asyncio.create_task(self._read_output_continuously())
            self._status_monitor_task = asyncio.create_task(self._monitor_status_continuously())
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup_loop())

            # Start database writer consumer tasks (3 concurrent writers for fast processing)
            for i in range(3):
                writer_task = asyncio.create_task(self._database_writer_consumer(f"writer-{i}"))
                self._db_writer_tasks.append(writer_task)

            # Log startup event
            self._log_daemon_event("overmind_started", {
                "pid": self.overmind_process.pid,
                "command": " ".join(cmd),
                "working_directory": self.working_directory
            })

            logger.info("Overmind started successfully and monitoring tasks initiated")
            return True

        except (OSError, subprocess.SubprocessError) as e:
            logger.error(f"Failed to start overmind: {e}")
            self.is_running = False
            return False

    async def stop_overmind(self):
        """Stop overmind and all monitoring tasks"""
        if not self.is_running or self.is_stopping:
            logger.info("Overmind already stopped or stopping")
            return

        self.is_stopping = True
        logger.info("Stopping overmind and monitoring tasks...")

        # Send poison pill to stop database writers
        await self.output_queue.put(self.poison_pill)

        # Cancel monitoring tasks
        all_tasks = [self._output_task, self._status_monitor_task,
                      self._heartbeat_task, self._cleanup_task] + self._db_writer_tasks
        for task in all_tasks:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Stop overmind process
        if self.overmind_process and self.overmind_process.returncode is None:
            await self._graceful_shutdown_overmind()

        # Clean up resources
        await self._cleanup_resources()

        self.is_running = False
        self.is_stopping = False

        # Log shutdown event
        self._log_daemon_event("overmind_stopped", {
            "graceful": True,
            "working_directory": self.working_directory
        })

        logger.info("Overmind stopped successfully")

    async def _load_procfile_processes(self):
        """Load process definitions from Procfile"""
        procfile_path = os.path.join(self.working_directory, "Procfile")

        if not os.path.exists(procfile_path):
            logger.warning(f"No Procfile found at {procfile_path}")
            return

        try:
            with open(procfile_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if ':' in line:
                            process_name = line.split(':', 1)[0].strip()
                            self.processes[process_name] = {
                                'name': process_name,
                                'status': 'unknown',
                                'selected': True,  # Default to selected
                                'last_updated': time.time()
                            }

                            # Database only stores output lines, not process status

            logger.info(f"Loaded {len(self.processes)} processes from Procfile: {list(self.processes.keys())}")

        except (OSError, IOError) as e:
            logger.error(f"Error reading Procfile: {e}")

    async def _read_output_continuously(self):
        """Continuously read and store overmind output with optimization for dead processes and line limits"""
        if not self.overmind_process or not self.overmind_process.stdout:
            return

        logger.info("Starting continuous output monitoring")

        # Track lines per process to implement UI limit optimization
        process_line_counts = {}

        # Buffer for incomplete lines when reading chunks
        incomplete_line = b''

        try:
            while self.is_running:
                # Read in larger chunks (64KB) instead of line by line
                # This prevents buffer overflow when processes output lots of data at once
                try:
                    chunk = await self.overmind_process.stdout.read(65536)
                except asyncio.CancelledError:
                    break

                if not chunk:
                    # No more data - check if process is still running
                    if self.overmind_process.returncode is not None:
                        logger.warning(f"🛑 Overmind process ended with code {self.overmind_process.returncode}")
                        # Try one more read to drain any remaining data
                        try:
                            final_chunk = await asyncio.wait_for(
                                self.overmind_process.stdout.read(65536),
                                timeout=0.5
                            )
                            if final_chunk:
                                chunk = final_chunk
                            else:
                                break
                        except asyncio.TimeoutError:
                            break
                    else:
                        # Process still running but no data yet
                        await asyncio.sleep(0.01)
                        continue

                # Combine with any incomplete line from previous chunk
                data = incomplete_line + chunk

                # Split into lines
                lines = data.split(b'\n')

                # Last element might be incomplete if chunk ended mid - line
                # Save it for next iteration
                incomplete_line = lines[-1]

                # Process all complete lines
                for line_bytes in lines[:-1]:
                    # Decode with error handling
                    try:
                        line_str = line_bytes.decode('utf - 8', errors='replace')
                    except UnicodeDecodeError:
                        line_str = line_bytes.decode('latin - 1', errors='replace')

                    if line_str:
                        # Extract process name for optimization
                        process_name = self._extract_process_name(line_str)

                        # Track line count for this process
                        if process_name not in process_line_counts:
                            process_line_counts[process_name] = 0
                        process_line_counts[process_name] += 1

                        # Process every line - the database and UI handle their own limits
                        # We need to capture everything for accurate logging and debugging
                        await self._process_output_line(line_str)

            # Process any remaining incomplete line
            if incomplete_line:
                try:
                    line_str = incomplete_line.decode('utf - 8', errors='replace')
                    if line_str:
                        process_name = self._extract_process_name(line_str)
                        await self._process_output_line(line_str)
                except (UnicodeDecodeError, AttributeError):
                    pass  # Ignore decode errors on final incomplete line

            # Check if overmind died unexpectedly
            if self.overmind_process.returncode is not None:
                logger.error(f"🚨 Overmind process died with exit code: {self.overmind_process.returncode}")
                self.is_running = False

                # Trigger daemon shutdown if callback is provided
                if self.on_overmind_death:
                    logger.info("🔄 Triggering daemon shutdown due to overmind death")
                    try:
                        if asyncio.iscoroutinefunction(self.on_overmind_death):
                            asyncio.create_task(self.on_overmind_death())
                        else:
                            self.on_overmind_death()
                    except Exception as e:
                        logger.error(f"Error calling overmind death callback: {e}", exc_info=True)

        except Exception as e:
            if self.is_running:
                logger.error(f"Error reading overmind output: {e}", exc_info=True)
        finally:
            logger.info("Output monitoring stopped")

            # Log final statistics
            total_lines = sum(process_line_counts.values())
            logger.info(f"📊 Output monitoring final stats: {total_lines} total lines "
                        f"across {len(process_line_counts)} processes")
            for proc, count in process_line_counts.items():
                if count > 1000:  # Only log processes with significant output
                    logger.info(f"  📈 {proc}: {count} lines")

    def _extract_process_name(self, line: str) -> str:
        """Extract process name from overmind output line for optimization tracking"""
        # Try to extract process name from overmind's format: "[process] message"
        if ' | ' in line:
            parts = line.split(' | ', 1)
            if len(parts) >= 2:
                process_part = parts[0].strip()
                # Remove ANSI color codes to get actual process name
                import re
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                clean_process = ansi_escape.sub('', process_part)
                if clean_process in self.processes:
                    return clean_process
        return "system"  # Default for unparseable lines

    async def _database_writer_consumer(self, name: str):
        """Consumer task that writes queued lines to the database in large batches"""
        logger.info(f"Database writer {name} started")
        batch = []
        batch_size = 1000  # Write in large batches for maximum efficiency
        batch_timeout = 0.1  # Flush after 100ms of no new data

        try:
            while True:
                try:
                    # Get item from queue with timeout for batch flushing
                    item = await asyncio.wait_for(self.output_queue.get(), timeout=batch_timeout)

                    # Check for poison pill (shutdown signal)
                    if item is self.poison_pill:
                        # Put it back for other consumers
                        await self.output_queue.put(self.poison_pill)
                        break

                    batch.append(item)

                    # Write batch if it's full
                    if len(batch) >= batch_size:
                        await self._write_batch_to_database(batch)
                        batch = []

                except asyncio.TimeoutError:
                    # Timeout - flush any pending batch
                    if batch:
                        await self._write_batch_to_database(batch)
                        batch = []

        except Exception as e:
            logger.error(f"Database writer {name} error: {e}", exc_info=True)
        finally:
            # Flush any remaining items
            if batch:
                await self._write_batch_to_database(batch)
            logger.info(f"Database writer {name} stopped")

    async def _write_batch_to_database(self, batch: List[Dict]):
        """Write a batch of lines to the database in a single transaction"""
        if not batch:
            return

        try:
            # Get database connection from the manager
            conn = self.db.get_connection()
            cursor = conn.cursor()

            # Begin transaction for batch insert (much faster)
            cursor.execute("BEGIN TRANSACTION")

            # Prepare batch data for insertion (no timestamp in database schema)
            batch_data = [
                (item['process_name'], item['html_content'])
                for item in batch
            ]

            # Bulk insert all lines at once
            cursor.executemany(
                "INSERT INTO output_lines (process, html) VALUES (?, ?)",
                batch_data
            )

            # Commit transaction
            conn.commit()

            logger.debug(f"Wrote batch of {len(batch)} lines to database")

            # Trigger real - time callbacks (after successful database write)
            for item in batch:
                for callback in self.output_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(item['process_name'], item['html_content'])
                        else:
                            callback(item['process_name'], item['html_content'])
                    except Exception as e:
                        logger.error(f"Error in output callback: {e}")

        except Exception as e:
            logger.error(f"Error writing batch to database: {e}", exc_info=True)
            # Try to rollback on error
            try:
                if 'conn' in locals():
                    conn.rollback()
            except Exception:
                pass

    async def _process_output_line(self, line: str):
        """Process and queue a single output line for database writing"""
        timestamp = time.time()
        self.message_id_counter += 1

        # Extract process name from overmind's ANSI - colored output
        process_name = "system"
        html_content = line

        # Parse overmind's output format: "processname | content"
        # Examples:
        # backend | ⠧  OnboardingAndIdentityEvents
        # [1;38;5;2mweb[0m | Web server starting on port 3000
        # [1;38;5;3mworker[0m | Processing job 1 at 14:21:47

        if " | " in line:
            parts = line.split(" | ", 1)
            if len(parts) == 2:
                process_part = parts[0].strip()

                # Remove ANSI color codes from process name to get actual process name
                import re
                # ANSI escape sequence pattern - more comprehensive
                ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
                potential_process = ansi_escape.sub('', process_part).strip()

                # Handle edge case: if processes not loaded yet, try to match against known names
                known_processes = ['temporal', 'backend', 'web', 'worker', 'helper', 'storybook',
                                 'rse', 'rse2', 'ops - console - api', 'ops - console - web', 'awskeep', 'status']

                # First check against loaded processes (preferred)
                if potential_process in self.processes:
                    process_name = potential_process
                    logger.debug(f"✅ Matched process against loaded: {process_name}")
                # Alternative: check against known process names
                elif potential_process in known_processes:
                    process_name = potential_process
                    logger.debug(f"✅ Matched process against known list: "
                                f"{process_name}")
                else:
                    logger.debug(f"❌ Process '{potential_process}' not found. Loaded: {list(self.processes.keys())}, Known: {known_processes}")

        # Convert ANSI codes to HTML and store only HTML version
        html_content = self._convert_ansi_to_html(line)

        # Queue the line for database writing (decoupled from reading)
        try:
            # Create item to queue
            item = {
                'process_name': process_name,
                'html_content': html_content,
                'timestamp': timestamp,
                'message_id': self.message_id_counter
            }

            # Try to put item in queue without blocking
            try:
                self.output_queue.put_nowait(item)
            except asyncio.QueueFull:
                # Queue is full - log warning but keep reading to prevent pipe buffer overflow
                logger.warning(f"Output queue full! Dropping line from {process_name}")
                # In production, you might want to increase queue size or add overflow handling

        except Exception as e:
            # Queue errors shouldn't stop reading
            logger.error(f"Failed to queue output line: {e}")

        self.last_output_time = timestamp

    def _convert_ansi_to_html(self, text: str) -> str:
        """Convert ANSI color codes to HTML spans using proper converter"""
        from ansi_to_html import AnsiToHtml
        converter = AnsiToHtml()
        return converter.convert(text)

    async def _monitor_status_continuously(self):
        """Continuously monitor process status"""
        logger.info("Starting continuous status monitoring")

        # Wait a bit for overmind to stabilize
        await asyncio.sleep(5)

        while self.is_running:
            try:
                await self._check_process_status()
                await asyncio.sleep(20)  # Check every 20 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in status monitoring: {e}")
                await asyncio.sleep(10)

        logger.info("Status monitoring stopped")

    async def _periodic_cleanup_loop(self):
        """Periodically clean up excess output lines to stay within UI limits"""
        logger.info("Starting periodic database cleanup for UI limits")

        while self.is_running:
            try:
                # Run cleanup every 5 minutes
                await asyncio.sleep(300)

                if not self.is_running:
                    break

                # Clean up excess lines for each process
                MAX_LINES_PER_PROCESS = 10000
                cleaned_processes = 0

                for process_name in self.processes.keys():
                    try:
                        # Count lines for this process
                        line_count = self.db.count_output_lines_for_process(process_name)

                        if line_count > MAX_LINES_PER_PROCESS:
                            excess_lines = line_count - MAX_LINES_PER_PROCESS
                            # Remove oldest lines, keep newest MAX_LINES_PER_PROCESS
                            self.db.cleanup_old_output_lines(process_name,
                                                            MAX_LINES_PER_PROCESS)
                            logger.info(f"🧹 Cleaned up {excess_lines} old lines for process '{process_name}' (kept {MAX_LINES_PER_PROCESS})")
                            cleaned_processes += 1

                    except Exception as e:
                        logger.error(f"Error cleaning up process {process_name}: {e}")

                if cleaned_processes > 0:
                    logger.info(f"✅ Cleanup cycle complete: cleaned {cleaned_processes} processes")

            except asyncio.CancelledError:
                logger.info("Cleanup task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic cleanup: {e}")
                await asyncio.sleep(60)  # Wait a bit before retrying

        logger.info("Periodic cleanup stopped")

    async def _check_process_status(self):
        """Check status of all processes"""
        try:
            status_output = await self.get_status()
            if status_output:
                status_updates = self.parse_status_output(status_output)
                if status_updates:
                    await self._update_process_statuses(status_updates)
        except Exception as e:
            logger.error(f"Error checking process status: {e}")

    async def _update_process_statuses(self, status_updates: Dict[str, str]):
        """Update process statuses in database and notify callbacks"""
        timestamp = time.time()

        for process_name, status in status_updates.items():
            if process_name in self.processes:
                old_status = self.processes[process_name].get('status', 'unknown')

                if old_status != status:
                    logger.info(f"Process {process_name} status changed: {old_status} -> {status}")

                    # Update local state
                    self.processes[process_name]['status'] = status
                    self.processes[process_name]['last_updated'] = timestamp

                    # Database only stores output lines, not process status

                    # Notify callbacks
                    for callback in self.status_callbacks:
                        try:
                            callback({process_name: status})
                        except Exception as e:
                            logger.error(f"Error in status callback: {e}")

    async def _heartbeat_loop(self):
        """Maintain daemon heartbeat"""
        while self.is_running:
            try:
                # Update heartbeat in config system
                daemon_config.update_instance_heartbeat(self.daemon_instance_id)
                await asyncio.sleep(daemon_config.get('daemon.heartbeat_interval', 10))
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in heartbeat: {e}")
                await asyncio.sleep(5)

    # Process control methods (similar to OvermindController)
    async def start_process(self, process_name: str) -> bool:
        """Start a specific process"""
        try:
            env = self.get_colored_env()
            process = await asyncio.create_subprocess_exec(
                "overmind", "start", process_name,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            await process.wait()

            success = process.returncode == 0
            if success:
                logger.info(f"Started process {process_name}")
                self._log_daemon_event("process_started", {"process": process_name})
            else:
                logger.error(f"Failed to start process {process_name}")

            return success

        except Exception as e:
            logger.error(f"Error starting {process_name}: {e}")
            return False

    async def stop_process(self, process_name: str) -> bool:
        """Stop a specific process"""
        try:
            env = self.get_colored_env()
            process = await asyncio.create_subprocess_exec(
                "overmind", "stop", process_name,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            await process.wait()

            success = process.returncode == 0
            if success:
                logger.info(f"Stopped process {process_name}")
                self._log_daemon_event("process_stopped", {"process": process_name})
            else:
                logger.error(f"Failed to stop process {process_name}")

            return success

        except Exception as e:
            logger.error(f"Error stopping {process_name}: {e}")
            return False

    async def restart_process(self, process_name: str) -> bool:
        """Restart a specific process"""
        try:
            env = self.get_colored_env()
            process = await asyncio.create_subprocess_exec(
                "overmind", "restart", process_name,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            await process.wait()

            success = process.returncode == 0
            if success:
                logger.info(f"Restarted process {process_name}")
                self._log_daemon_event("process_restarted", {"process": process_name})
            else:
                logger.error(f"Failed to restart process {process_name}")

            return success

        except Exception as e:
            logger.error(f"Error restarting {process_name}: {e}")
            return False

    async def get_status(self) -> Optional[str]:
        """Get current status of all processes"""
        try:
            env = self.get_colored_env()
            process = await asyncio.create_subprocess_exec(
                "overmind", "status",
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)

            if process.returncode == 0:
                return stdout.decode()
            return None

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            return None

    def parse_status_output(self, status_text: str) -> Dict[str, str]:
        """Parse overmind status output into dict"""
        status_updates = {}
        lines = status_text.strip().splitlines()

        for line in lines:
            line = line.strip()
            # Skip header and empty lines
            if not line or "PROCESS" in line or "PID" in line:
                continue

            # Parse: PROCESS PID STATUS
            parts = line.split()
            if len(parts) >= 3:
                process_name = parts[0]
                status = parts[2]  # Skip PID
                status_updates[process_name] = status

        return status_updates

    def _log_daemon_event(self, event_type: str, data: Dict[str, Any]):
        """Log an event - simplified database only stores output lines"""
        # Skip database logging since we simplified the schema
        logger.info(f"Daemon event: {event_type} - {data}")

    async def _graceful_shutdown_overmind(self):
        """Gracefully shutdown overmind process using 'overmind quit'"""
        if not self.overmind_process:
            return

        overmind_pid = self.overmind_process.pid
        logger.info(f"Gracefully shutting down overmind PID {overmind_pid}")

        try:
            # First try 'overmind quit' - the proper way to shutdown overmind
            logger.info("Attempting to shutdown overmind with 'overmind quit'...")
            quit_cmd = ["overmind", "quit"]

            quit_process = await asyncio.create_subprocess_exec(
                *quit_cmd,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await quit_process.communicate()

            if quit_process.returncode == 0:
                logger.info(f"✅ 'overmind quit' successful: {stdout.decode().strip()}")

                # Wait for the overmind process to exit
                try:
                    await asyncio.wait_for(self.overmind_process.wait(), timeout=10)
                    logger.info("Overmind process exited cleanly after quit command")
                    return
                except asyncio.TimeoutError:
                    logger.warning("Overmind process didn't exit after quit command")
            else:
                logger.warning(f"'overmind quit' failed: {stderr.decode().strip()}")

            # Use signals if quit command didn't work
            logger.info("Falling back to signal - based shutdown")

            # Try SIGINT first
            self.overmind_process.send_signal(signal.SIGINT)

            try:
                await asyncio.wait_for(self.overmind_process.wait(), timeout=10)
                logger.info("Overmind shut down gracefully with SIGINT")
                return
            except asyncio.TimeoutError:
                logger.warning("Overmind didn't respond to SIGINT, trying SIGTERM")

            # Try SIGTERM
            self.overmind_process.send_signal(signal.SIGTERM)

            try:
                await asyncio.wait_for(self.overmind_process.wait(), timeout=15)
                logger.info("Overmind terminated with SIGTERM")
                return
            except asyncio.TimeoutError:
                logger.warning("Overmind didn't respond to SIGTERM, using SIGKILL")

            # Force kill
            self.overmind_process.kill()
            await self.overmind_process.wait()
            logger.warning("Overmind force - killed")

        except Exception as e:
            logger.error(f"Error during overmind shutdown: {e}")
        finally:
            self.overmind_process = None

    async def _cleanup_resources(self):
        """Clean up resources and socket files - SAFELY"""
        # Only clean up socket file if we're in a test directory
        # This prevents accidentally affecting other overmind instances
        socket_file = os.path.join(self.working_directory, ".overmind.sock")
        if os.path.exists(socket_file):
            is_test_dir = 'overmind - daemon - test-' in self.working_directory or '/tmp' in self.working_directory

            if is_test_dir:
                try:
                    os.unlink(socket_file)
                    logger.info("Cleaned up test overmind socket file")
                except OSError as e:
                    logger.warning(f"Could not clean up socket file: {e}")
            else:
                logger.info("Not cleaning up socket file - not in test environment")

        # NEVER cleanup child processes - this is way too dangerous!
        # Other overmind instances might be running for other projects
        # Only our own subprocess should be cleaned up (handled in _graceful_shutdown_overmind)
        logger.info("Resource cleanup completed")

    def get_process_info(self) -> Dict[str, Dict]:
        """Get information about all managed processes"""
        import copy
        return copy.deepcopy(self.processes)

    def is_overmind_running(self) -> bool:
        """Check if overmind process is running"""
        return (self.is_running and
                self.overmind_process is not None and
                self.overmind_process.returncode is None)
