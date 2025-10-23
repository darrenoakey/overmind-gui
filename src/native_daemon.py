#!/usr/bin/env python3
"""
Native Daemon - Direct process management without overmind/tmux
Independent daemon process for managing Procfile processes directly

Key Features:
- Direct subprocess management (no overmind/tmux dependency)
- Colored output matching overmind's format
- Persistent SQLite storage for output and state
- Process lifecycle management (start/stop/restart)
- CLI commands for process control
"""

import asyncio
import logging
import os
import signal
import sqlite3
import sys
import threading
import time
import uuid
from typing import Optional

from procfile_parser import ProcfileParser
from output_formatter import OutputFormatter
from native_process_manager import NativeProcessManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("native-daemon.log")],
)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages SQLite database for persistent storage"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.connection_pool = {}
        self._lock = threading.Lock()

        # Ensure database directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # Initialize database
        self._initialize_database()

        logger.info(f"Database initialized at {db_path}")

    def _initialize_database(self):
        """Create database schema if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS output_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process TEXT NOT NULL,
                    html TEXT NOT NULL
                )
            """)

            # Create indexes for performance
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_output_lines_id ON output_lines(id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_output_lines_process_id ON output_lines(process, id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_output_lines_id_process ON output_lines(id, process)")

            # Commands table for GUI -> Daemon communication
            conn.execute("""
                CREATE TABLE IF NOT EXISTS daemon_commands (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    command TEXT NOT NULL,
                    process_name TEXT,
                    timestamp REAL NOT NULL,
                    status TEXT DEFAULT 'pending'
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daemon_commands_status ON daemon_commands(status)")

            # Status updates table for Daemon -> GUI communication
            conn.execute("""
                CREATE TABLE IF NOT EXISTS process_status (
                    process_name TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    pid INTEGER,
                    updated_at REAL NOT NULL
                )
            """)

            conn.commit()

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection for the current thread"""
        thread_id = threading.get_ident()

        with self._lock:
            if thread_id not in self.connection_pool:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Enable dict-like access
                self.connection_pool[thread_id] = conn

            return self.connection_pool[thread_id]

    def close_connections(self):
        """Close all database connections"""
        with self._lock:
            for conn in self.connection_pool.values():
                try:
                    conn.close()
                except Exception:
                    pass
            self.connection_pool.clear()

    def add_command(self, command: str, process_name: str = None) -> int:
        """Add a command for the daemon to execute"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO daemon_commands (command, process_name, timestamp) VALUES (?, ?, ?)",
            (command, process_name, time.time())
        )
        conn.commit()

        return cursor.lastrowid

    def get_pending_commands(self) -> list:
        """Get all pending commands"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, command, process_name FROM daemon_commands WHERE status = 'pending' ORDER BY id"
        )

        commands = []
        for row in cursor.fetchall():
            commands.append({
                'id': row[0],
                'command': row[1],
                'process_name': row[2]
            })

        return commands

    def mark_command_completed(self, command_id: int):
        """Mark a command as completed"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE daemon_commands SET status = 'completed' WHERE id = ?",
            (command_id,)
        )
        conn.commit()

    def update_process_status(self, process_name: str, status: str, pid: int = None):
        """Update process status for GUI to read"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT OR REPLACE INTO process_status (process_name, status, pid, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (process_name, status, pid, time.time())
        )
        conn.commit()

    def store_output_line(self, process: str, html: str) -> int:
        """Store an output line in the database"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO output_lines (process, html)
            VALUES (?, ?)
        """,
            (process, html),
        )

        conn.commit()
        return cursor.lastrowid


class NativeDaemonInstance:
    """Represents a single native daemon instance"""

    def __init__(self, working_directory: str = None):
        self.instance_id = str(uuid.uuid4())
        self.working_directory = working_directory or os.getcwd()
        self.pid = os.getpid()
        self.started_at = time.time()
        self.status = "initializing"

        # Database setup - lives next to Procfile, clear on startup
        db_path = os.path.join(self.working_directory, "overmind.db")

        # Remove existing database for fresh start
        if os.path.exists(db_path):
            os.remove(db_path)
            logger.info(f"Cleared existing database: {db_path}")

        self.db = DatabaseManager(db_path)

        # State
        self.is_running = False
        self.shutdown_event = None  # Will be created in async context

        # Process management
        self.process_manager: Optional[NativeProcessManager] = None
        self.procfile_parser: Optional[ProcfileParser] = None
        self.formatter: Optional[OutputFormatter] = None

        # Write process ID file for backend discovery
        self.pid_file = os.path.join(self.working_directory, "overmind-daemon.pid")
        self._write_pid_file()

        logger.info(f"Native daemon instance created: {self.instance_id}")
        logger.info(f"Working directory: {self.working_directory}")
        logger.info(f"PID file: {self.pid_file}")
        logger.info(f"Database: {db_path}")

    def _write_pid_file(self):
        """Write process ID file for backend discovery"""
        with open(self.pid_file, "w") as f:
            f.write(str(self.pid))
        logger.info(f"Wrote daemon PID {self.pid} to {self.pid_file}")

    def _cleanup_pid_file(self):
        """Remove process ID file"""
        try:
            if os.path.exists(self.pid_file):
                os.remove(self.pid_file)
                logger.info(f"Removed PID file: {self.pid_file}")
        except Exception as e:
            logger.warning(f"Failed to remove PID file: {e}")

    async def start(self):
        """Start the native daemon instance"""
        self.is_running = True
        self.status = "running"

        # Create shutdown event in async context
        self.shutdown_event = asyncio.Event()

        logger.info(f"Starting native daemon instance {self.instance_id}")

        try:
            # Parse Procfile
            procfile_path = os.path.join(self.working_directory, "Procfile")
            if not os.path.exists(procfile_path):
                logger.error(f"Procfile not found: {procfile_path}")
                self._cleanup_pid_file()
                return False

            self.procfile_parser = ProcfileParser(procfile_path)
            if not self.procfile_parser.parse():
                logger.error("Failed to parse Procfile")
                for line_num, error in self.procfile_parser.get_errors():
                    logger.error(f"  Line {line_num}: {error}")
                self._cleanup_pid_file()
                return False

            logger.info(f"Parsed {len(self.procfile_parser.get_entries())} processes from Procfile")

            # Create output formatter
            process_names = self.procfile_parser.get_process_names()
            self.formatter = OutputFormatter(process_names)

            # Show process list with colors
            logger.info(self.formatter.get_formatted_header())

            # Create process manager
            self.process_manager = NativeProcessManager(
                entries=self.procfile_parser.get_entries(),
                formatter=self.formatter,
                database_manager=self.db,
                working_directory=self.working_directory,
            )

            # Start all processes
            if not self.process_manager.start_all():
                logger.error("Failed to start all processes")
                self._cleanup_pid_file()
                return False

            logger.info("All processes started successfully - daemon ready")

            # Write initial status to database for GUI
            for process_name in process_names:
                process = self.process_manager.processes.get(process_name)
                if process:
                    self.db.update_process_status(process_name, process.status, process.pid)

            # Run command processing loop and wait for shutdown
            await self._run_command_loop()

        except Exception as e:
            logger.error(f"Error starting daemon instance: {e}", exc_info=True)
            self.status = "error"
            self._cleanup_pid_file()
            raise

    async def _run_command_loop(self):
        """Process commands from database and wait for shutdown"""
        import asyncio

        while not self.shutdown_event.is_set():
            try:
                # Check for pending commands
                commands = self.db.get_pending_commands()

                for cmd_info in commands:
                    cmd_id = cmd_info['id']
                    command = cmd_info['command']
                    process_name = cmd_info['process_name']

                    logger.info(f"Processing command: {command} for process {process_name}")

                    # Execute command
                    if command == 'restart' and process_name:
                        self.restart_process(process_name)
                    elif command == 'stop' and process_name:
                        self.stop_process(process_name)
                    elif command == 'start' and process_name:
                        # Start is handled by initial startup, but we can restart
                        self.restart_process(process_name)

                    # Mark as completed
                    self.db.mark_command_completed(cmd_id)

            except Exception as e:
                logger.error(f"Error processing commands: {e}")

            # Wait before next poll (check for commands every 0.5 seconds)
            try:
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=0.5)
                break  # Shutdown signal received
            except asyncio.TimeoutError:
                pass  # Continue polling

    async def stop(self):
        """Stop the daemon instance gracefully"""
        logger.info(f"Stopping native daemon instance {self.instance_id}")

        self.is_running = False
        self.status = "stopping"

        # Stop process manager
        if self.process_manager:
            try:
                self.process_manager.stop_all()
                logger.info("Process manager stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping process manager: {e}", exc_info=True)

        # Close database connections
        self.db.close_connections()

        # Clean up PID file
        self._cleanup_pid_file()

        # Signal shutdown (if event was created)
        if self.shutdown_event:
            self.shutdown_event.set()

        self.status = "stopped"
        logger.info(f"Native daemon instance {self.instance_id} stopped")

    def restart_process(self, process_name: str) -> bool:
        """Restart a specific process"""
        if not self.process_manager:
            logger.error("Process manager not initialized")
            return False

        return self.process_manager.restart_process(process_name)

    def stop_process(self, process_name: str) -> bool:
        """Stop a specific process"""
        if not self.process_manager:
            logger.error("Process manager not initialized")
            return False

        return self.process_manager.stop_process(process_name)

    def get_process_status(self) -> dict:
        """Get status of all processes"""
        if not self.process_manager:
            return {}

        return self.process_manager.get_all_status()


class NativeDaemon:
    """Main native daemon class"""

    def __init__(self):
        self.instance: Optional[NativeDaemonInstance] = None
        self.shutdown_requested = False

    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.shutdown_requested = True
            if self.instance:
                asyncio.create_task(self.instance.stop())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def run(self, working_directory: str = None):
        """Run the native daemon"""
        logger.info("Starting Native Daemon (no overmind/tmux)")

        # Setup signal handlers
        self.setup_signal_handlers()

        try:
            # Create and start daemon instance
            self.instance = NativeDaemonInstance(working_directory)
            await self.instance.start()

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Daemon error: {e}", exc_info=True)
        finally:
            if self.instance:
                await self.instance.stop()

        logger.info("Native Daemon stopped")


def main():
    """Main entry point for the native daemon"""
    import argparse

    parser = argparse.ArgumentParser(description="Native Daemon - Direct process manager without overmind/tmux")
    parser.add_argument("--working-dir", "-d", type=str, help="Working directory (default: current directory)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Log level")

    args = parser.parse_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Create daemon
    daemon = NativeDaemon()

    # Run daemon
    try:
        asyncio.run(daemon.run(args.working_dir))
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Daemon failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
