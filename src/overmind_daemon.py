#!/usr/bin/env python3
"""
Overmind Daemon - Independent daemon process for managing overmind instances
Provides persistent storage and API access for GUI clients to connect

Key Features:
- Runs overmind independently of GUI
- Persistent SQLite storage for output and state
- HTTP API for GUI client connections
- Multi - client support with real - time updates
- Instance discovery and management
"""

import asyncio
import logging
import os
import signal
import sqlite3
import sys
import time
import threading
import uuid
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("overmind - daemon.log")],
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

            # Simplified schema - just output lines

            # Create indexes for performance - order matters for query optimization
            conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_output_lines_id ON output_lines(id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_output_lines_process_id ON output_lines(process, id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_output_lines_id_process ON output_lines(id, process)")

            conn.commit()

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection for the current thread"""
        thread_id = threading.get_ident()

        with self._lock:
            if thread_id not in self.connection_pool:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row  # Enable dict - like access
                self.connection_pool[thread_id] = conn

            return self.connection_pool[thread_id]

    def close_connections(self):
        """Close all database connections"""
        with self._lock:
            for conn in self.connection_pool.values():
                try:
                    conn.close()
                except Exception:
                    # Ignore SQLite threading issues during shutdown
                    pass
            self.connection_pool.clear()

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

    def get_output_lines(self, since_id: int = 0, limit: int = 1000, process_filter: List[str] = None) -> List[Dict]:
        """Retrieve output lines since specified ID"""
        conn = self.get_connection()

        query = """
            SELECT id, process, html
            FROM output_lines
            WHERE id > ?
        """
        params = [since_id]

        if process_filter:
            placeholders = ",".join("?" * len(process_filter))
            query += f" AND process IN ({placeholders})"
            params.extend(process_filter)

        query += " ORDER BY id ASC LIMIT ?"
        params.append(limit)

        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            cursor.close()

    def cleanup_old_data(self, max_lines: int = 100000, days_to_keep: int = 30):
        """Clean up old data to prevent database growth"""
        conn = self.get_connection()
        cutoff_timestamp = time.time() - (days_to_keep * 24 * 60 * 60)

        # Keep only the most recent max_lines
        conn.execute(
            """
            DELETE FROM output_lines
            WHERE id NOT IN (
                SELECT id FROM output_lines
                ORDER BY id DESC LIMIT ?
            )
        """,
            (max_lines,),
        )

        # Remove old events
        conn.execute("DELETE FROM daemon_events WHERE timestamp < ?", (cutoff_timestamp,))

        conn.commit()
        logger.info(f"Database cleanup completed - keeping {max_lines} lines and {days_to_keep} days of events")

    def count_output_lines_for_process(self, process_name: str) -> int:
        """Count output lines for a specific process"""
        conn = self.get_connection()
        cursor = conn.execute("SELECT COUNT(*) FROM output_lines WHERE process_name = ?", (process_name,))
        return cursor.fetchone()[0]

    def cleanup_old_output_lines(self, process_name: str, keep_lines: int):
        """Remove old output lines for a process, keeping only the most recent keep_lines"""
        conn = self.get_connection()

        # Delete old lines, keeping only the most recent keep_lines
        conn.execute(
            """
            DELETE FROM output_lines
            WHERE process_name = ?
            AND id NOT IN (
                SELECT id FROM output_lines
                WHERE process_name = ?
                ORDER BY id DESC
                LIMIT ?
            )
        """,
            (process_name, process_name, keep_lines),
        )

        conn.commit()
        deleted_count = conn.total_changes
        logger.debug(f"Cleaned up {deleted_count} old lines for process {process_name}")


class DaemonInstance:
    """Represents a single overmind daemon instance"""

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
        self.shutdown_event = asyncio.Event()

        # Overmind management
        self.overmind_manager = None

        # Write process ID file for backend discovery
        self.pid_file = os.path.join(self.working_directory, "overmind - daemon.pid")
        self._write_pid_file()

        logger.info(f"Daemon instance created: {self.instance_id}")
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

    def _trigger_shutdown(self):
        """Trigger daemon shutdown when overmind dies"""
        logger.info("🔄 Overmind died - initiating daemon shutdown")
        self.shutdown_event.set()

    async def start(self, overmind_args: List[str] = None):
        """Start the daemon instance - just overmind + database writing"""
        self.is_running = True
        self.status = "running"

        logger.info(f"Starting simplified daemon instance {self.instance_id}")

        try:
            # Import here to avoid circular imports
            from daemon_overmind_manager import DaemonOvermindManager

            # Create overmind manager
            self.overmind_manager = DaemonOvermindManager(
                daemon_instance_id=self.instance_id,
                database_manager=self.db,
                working_directory=self.working_directory,
                overmind_args=overmind_args or [],
                on_overmind_death=self._trigger_shutdown,
            )

            # Start overmind
            overmind_started = await self.overmind_manager.start_overmind()
            if not overmind_started:
                logger.error("Failed to start overmind - exiting daemon")
                self._cleanup_pid_file()
                return False
            else:
                logger.info("Overmind started successfully - daemon ready")

            # Wait for shutdown (triggered by overmind death)
            await self.shutdown_event.wait()

        except Exception as e:
            logger.error(f"Error starting daemon instance: {e}", exc_info=True)
            self.status = "error"
            self._cleanup_pid_file()
            raise

    async def stop(self):
        """Stop the daemon instance gracefully"""
        logger.info(f"Stopping daemon instance {self.instance_id}")

        self.is_running = False
        self.status = "stopping"

        # Stop overmind manager
        if self.overmind_manager:
            try:
                await self.overmind_manager.stop_overmind()
                logger.info("Overmind manager stopped successfully")
            except Exception as e:
                logger.error(f"Error stopping overmind manager: {e}", exc_info=True)

        # Close database connections
        self.db.close_connections()

        # Clean up PID file
        self._cleanup_pid_file()

        # Signal shutdown
        self.shutdown_event.set()

        self.status = "stopped"
        logger.info(f"Daemon instance {self.instance_id} stopped")


class OvermindDaemon:
    """Main daemon class that manages overmind instances"""

    def __init__(self):
        self.instance: Optional[DaemonInstance] = None
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

    async def run(self, working_directory: str = None, overmind_args: List[str] = None):
        """Run the simplified daemon"""
        logger.info("Starting Simplified Overmind Daemon")

        # Setup signal handlers
        self.setup_signal_handlers()

        try:
            # Create and start daemon instance
            self.instance = DaemonInstance(working_directory)
            await self.instance.start(overmind_args)

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Daemon error: {e}", exc_info=True)
        finally:
            if self.instance:
                await self.instance.stop()

        logger.info("Simplified Overmind Daemon stopped")


def main():
    """Main entry point for the daemon"""
    import argparse

    parser = argparse.ArgumentParser(description="Overmind Daemon - Independent overmind process manager")
    parser.add_argument("--working-dir", "-d", type=str, help="Working directory (default: current directory)")
    parser.add_argument("--api-port", "-p", type=int, help="API port (default: auto-detect)")
    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR"], default="INFO", help="Log level")
    parser.add_argument("--overmind-args", type=str, help="Additional arguments to pass to overmind (space-separated)")

    args, unknown_args = parser.parse_known_args()

    # Set log level
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    # Collect overmind arguments
    overmind_args = []
    if args.overmind_args:
        overmind_args.extend(args.overmind_args.split())
    if unknown_args:
        overmind_args.extend(unknown_args)

    # Create daemon
    daemon = OvermindDaemon()

    # Run daemon
    try:
        asyncio.run(daemon.run(args.working_dir, overmind_args))
    except KeyboardInterrupt:
        logger.info("Daemon interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Daemon failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
