#!/usr/bin/env python3
"""
Backend Database Client - Direct SQLite access for backend polling
Replaces HTTP API calls with direct database queries
"""

import sqlite3
import os
import time
import unittest
import tempfile
import shutil
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class DatabaseClient:
    """Direct SQLite database client for backend polling"""

    def __init__(self, working_directory: str):
        self.working_directory = working_directory
        self.db_path = os.path.join(working_directory, "overmind.db")

    def is_database_available(self) -> bool:
        """Check if database exists and is accessible"""
        return os.path.exists(self.db_path)

    def get_output_lines(self, since_id: int = 0, limit: int = 5000, process_filter: List[str] = None) -> List[Dict]:
        """
        Get output lines since specified ID with smart limiting

        For initial load (since_id=0):
        - Limit to last 5000 lines PER PROCESS to avoid overwhelming frontend
        - If a process has 1M lines, only return the most recent 5000

        For incremental polling (since_id>0):
        - Return all new lines since that ID (no per - process limit)
        """
        if not self.is_database_available():
            return []

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if since_id == 0:
                    # Initial load - limit per process
                    return self._get_initial_lines_limited(cursor, process_filter, limit)
                else:
                    # Incremental polling - get all new lines
                    return self._get_incremental_lines(cursor, since_id, process_filter)

        except Exception as e:
            logger.error(f"Error querying database: {e}")
            return []

    def _get_initial_lines_limited(
        self, cursor: sqlite3.Cursor, process_filter: List[str] = None, limit_per_process: int = 5000
    ) -> List[Dict]:
        """
        Get initial lines with per - process limiting
        If web has 1M lines and api has 4 lines, return latest 5000 web + 4 api = 5004 total
        """
        lines = []

        # Get unique processes
        if process_filter:
            placeholders = ",".join("?" * len(process_filter))
            cursor.execute(
                f"""
                SELECT DISTINCT process FROM output_lines
                WHERE process IN ({placeholders})
            """,
                process_filter,
            )
        else:
            cursor.execute("SELECT DISTINCT process FROM output_lines")

        processes = [row["process"] for row in cursor.fetchall()]

        # For each process, get the most recent limit_per_process lines
        for process in processes:
            cursor.execute(
                """
                SELECT id, process, html
                FROM output_lines
                WHERE process = ?
                ORDER BY id DESC
                LIMIT ?
            """,
                (process, limit_per_process),
            )

            # Reverse to get chronological order (oldest first)
            process_lines = [dict(row) for row in reversed(cursor.fetchall())]
            lines.extend(process_lines)

        # Sort all lines by ID to maintain chronological order
        lines.sort(key=lambda x: x["id"])

        logger.info(
            f"Initial load: {len(lines)} lines across {len(processes)} processes (max {limit_per_process} per process)"
        )
        return lines

    def _get_incremental_lines(
        self, cursor: sqlite3.Cursor, since_id: int, process_filter: List[str] = None
    ) -> List[Dict]:
        """Get all lines since specified ID (no per - process limit for incremental)"""
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

        query += " ORDER BY id ASC"

        cursor.execute(query, params)
        lines = [dict(row) for row in cursor.fetchall()]

        if lines:
            logger.debug(f"Incremental poll: {len(lines)} new lines since ID {since_id}")

        return lines

    def get_max_id(self) -> int:
        """Get the highest ID in the database"""
        if not self.is_database_available():
            return 0

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(id) FROM output_lines")
                result = cursor.fetchone()
                return result[0] if result[0] is not None else 0
        except Exception as e:
            logger.error(f"Error getting max ID: {e}")
            return 0

    def get_process_stats(self) -> Dict[str, Dict]:
        """Get line counts per process"""
        if not self.is_database_available():
            return {}

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT process, COUNT(*) as line_count, MIN(id) as first_id, MAX(id) as last_id
                    FROM output_lines
                    GROUP BY process
                    ORDER BY process
                """)

                stats = {}
                for row in cursor.fetchall():
                    stats[row["process"]] = {
                        "line_count": row["line_count"],
                        "first_id": row["first_id"],
                        "last_id": row["last_id"],
                    }

                return stats

        except Exception as e:
            logger.error(f"Error getting process stats: {e}")
            return {}


# Comprehensive tests


class TestDatabaseClient(unittest.TestCase):
    """Test the database client with various scenarios"""

    def setUp(self):
        """Set up test database"""
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "overmind.db")
        self.client = DatabaseClient(self.test_dir)

        # Create test database with schema
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE output_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process TEXT NOT NULL,
                    html TEXT NOT NULL
                )
            """)
            conn.commit()

    def tearDown(self):
        """Clean up test database"""
        shutil.rmtree(self.test_dir)

    def _insert_test_lines(self, lines: List[Tuple[str, str]]):
        """Insert test lines (process, html)"""
        with sqlite3.connect(self.db_path) as conn:
            for process, html in lines:
                conn.execute("INSERT INTO output_lines (process, html) VALUES (?, ?)", (process, html))
            conn.commit()

    def test_initial_load_with_limits(self):
        """Test initial load respects per - process limits"""
        # Insert many lines for 'web' and few for 'api'
        lines = []

        # 10 lines for web process
        for i in range(10):
            lines.append(("web", f"<span>Web line {i}</span>"))

        # 3 lines for api process
        for i in range(3):
            lines.append(("api", f"<span>API line {i}</span>"))

        self._insert_test_lines(lines)

        # Initial load with limit of 5 per process
        result = self.client.get_output_lines(since_id=0, limit=5)

        # Should get 5 web lines + 3 api lines = 8 total
        self.assertEqual(len(result), 8)

        # Check we got the LATEST 5 web lines (5 - 9, not 0 - 4)
        web_lines = [r for r in result if r["process"] == "web"]
        self.assertEqual(len(web_lines), 5)
        self.assertIn("Web line 5", web_lines[0]["html"])  # Oldest of the 5 we kept
        self.assertIn("Web line 9", web_lines[-1]["html"])  # Most recent

        # Check we got all 3 api lines
        api_lines = [r for r in result if r["process"] == "api"]
        self.assertEqual(len(api_lines), 3)

    def test_incremental_polling(self):
        """Test incremental polling returns only new lines"""
        # Insert initial lines
        initial_lines = [
            ("web", "<span>Web line 1</span>"),
            ("api", "<span>API line 1</span>"),
        ]
        self._insert_test_lines(initial_lines)

        # Get initial load
        initial_result = self.client.get_output_lines(since_id=0)
        self.assertEqual(len(initial_result), 2)
        max_id = max(r["id"] for r in initial_result)

        # Add more lines
        new_lines = [
            ("web", "<span>Web line 2</span>"),
            ("api", "<span>API line 2</span>"),
        ]
        self._insert_test_lines(new_lines)

        # Incremental poll
        incremental_result = self.client.get_output_lines(since_id=max_id)
        self.assertEqual(len(incremental_result), 2)

        # Verify content
        web_new = [r for r in incremental_result if r["process"] == "web"][0]
        self.assertIn("Web line 2", web_new["html"])

    def test_large_dataset_performance(self):
        """Test with large dataset to ensure efficiency"""
        # Insert 1000 lines for web, 5 for api
        lines = []
        for i in range(1000):
            lines.append(("web", f"<span>Web line {i}</span>"))
        for i in range(5):
            lines.append(("api", f"<span>API line {i}</span>"))

        self._insert_test_lines(lines)

        # Initial load should limit web to 5000 (but we only have 1000)
        start_time = time.time()
        result = self.client.get_output_lines(since_id=0, limit=5000)
        end_time = time.time()

        # Should be fast (under 1 second)
        self.assertLess(end_time - start_time, 1.0)

        # Should get all 1005 lines (1000 web + 5 api)
        self.assertEqual(len(result), 1005)

        # Verify ordering (should be chronological)
        self.assertTrue(all(result[i]["id"] < result[i + 1]["id"] for i in range(len(result) - 1)))

    def test_process_stats(self):
        """Test process statistics"""
        lines = [
            ("web", "<span>Web 1</span>"),
            ("web", "<span>Web 2</span>"),
            ("api", "<span>API 1</span>"),
        ]
        self._insert_test_lines(lines)

        stats = self.client.get_process_stats()

        self.assertEqual(stats["web"]["line_count"], 2)
        self.assertEqual(stats["api"]["line_count"], 1)
        self.assertTrue(stats["web"]["first_id"] > 0)
        self.assertTrue(stats["web"]["last_id"] > stats["web"]["first_id"])

    def test_database_not_available(self):
        """Test behavior when database doesn't exist"""
        client = DatabaseClient("/nonexistent/directory")

        self.assertFalse(client.is_database_available())
        self.assertEqual(client.get_output_lines(), [])
        self.assertEqual(client.get_max_id(), 0)
        self.assertEqual(client.get_process_stats(), {})


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
