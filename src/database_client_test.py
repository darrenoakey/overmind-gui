#!/usr/bin/env python3
"""Tests for database_client module."""

import unittest
import tempfile
import shutil
import sqlite3
from database_client import DatabaseClient


class TestDatabaseClientBasic(unittest.TestCase):
    """Basic test cases for database_client module to ensure coverage"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()
        self.client = DatabaseClient(self.test_dir)

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)

    def test_database_availability(self):
        """Test checking database availability"""
        # Initially no database
        self.assertFalse(self.client.is_database_available())

        # Create database
        with sqlite3.connect(self.client.db_path) as conn:
            conn.execute("""
                CREATE TABLE output_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process TEXT NOT NULL,
                    html TEXT NOT NULL
                )
            """)
            conn.commit()

        # Now database should be available
        self.assertTrue(self.client.is_database_available())

    def test_get_max_id_empty_database(self):
        """Test getting max ID from empty database"""
        # Create empty database
        with sqlite3.connect(self.client.db_path) as conn:
            conn.execute("""
                CREATE TABLE output_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process TEXT NOT NULL,
                    html TEXT NOT NULL
                )
            """)
            conn.commit()

        max_id = self.client.get_max_id()
        self.assertEqual(max_id, 0)

    def test_get_output_lines_no_database(self):
        """Test getting output lines when database doesn't exist"""
        lines = self.client.get_output_lines()
        self.assertEqual(lines, [])

    def test_basic_functionality_with_data(self):
        """Test basic functionality with some data"""
        # Create database with data
        with sqlite3.connect(self.client.db_path) as conn:
            conn.execute("""
                CREATE TABLE output_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process TEXT NOT NULL,
                    html TEXT NOT NULL
                )
            """)
            conn.execute("INSERT INTO output_lines (process, html) VALUES (?, ?)", ("test", "<span>Test line</span>"))
            conn.commit()

        # Test get_max_id
        max_id = self.client.get_max_id()
        self.assertEqual(max_id, 1)

        # Test get_output_lines
        lines = self.client.get_output_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["process"], "test")
        self.assertEqual(lines[0]["html"], "<span>Test line</span>")

        # Test get_process_stats
        stats = self.client.get_process_stats()
        self.assertIn("test", stats)
        self.assertEqual(stats["test"]["line_count"], 1)

    def test_process_filtering(self):
        """Test filtering by process"""
        # Create database with multiple processes
        with sqlite3.connect(self.client.db_path) as conn:
            conn.execute("""
                CREATE TABLE output_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process TEXT NOT NULL,
                    html TEXT NOT NULL
                )
            """)
            conn.execute("INSERT INTO output_lines (process, html) VALUES (?, ?)", ("web", "<span>Web line</span>"))
            conn.execute("INSERT INTO output_lines (process, html) VALUES (?, ?)", ("api", "<span>API line</span>"))
            conn.commit()

        # Test filtering
        web_lines = self.client.get_output_lines(process_filter=["web"])
        self.assertEqual(len(web_lines), 1)
        self.assertEqual(web_lines[0]["process"], "web")

        api_lines = self.client.get_output_lines(process_filter=["api"])
        self.assertEqual(len(api_lines), 1)
        self.assertEqual(api_lines[0]["process"], "api")

    def test_incremental_polling(self):
        """Test incremental polling functionality"""
        # Create database with initial data
        with sqlite3.connect(self.client.db_path) as conn:
            conn.execute("""
                CREATE TABLE output_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process TEXT NOT NULL,
                    html TEXT NOT NULL
                )
            """)
            conn.execute("INSERT INTO output_lines (process, html) VALUES (?, ?)", ("web", "<span>Initial line</span>"))
            conn.commit()

        # Get initial lines
        initial_lines = self.client.get_output_lines(since_id=0)
        self.assertEqual(len(initial_lines), 1)
        max_id = initial_lines[0]["id"]

        # Add more lines
        with sqlite3.connect(self.client.db_path) as conn:
            conn.execute("INSERT INTO output_lines (process, html) VALUES (?, ?)", ("web", "<span>New line</span>"))
            conn.commit()

        # Test incremental polling
        new_lines = self.client.get_output_lines(since_id=max_id)
        self.assertEqual(len(new_lines), 1)
        self.assertEqual(new_lines[0]["html"], "<span>New line</span>")

    def test_per_process_limiting(self):
        """Test per-process limiting functionality"""
        # Create database with many lines for one process
        with sqlite3.connect(self.client.db_path) as conn:
            conn.execute("""
                CREATE TABLE output_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process TEXT NOT NULL,
                    html TEXT NOT NULL
                )
            """)
            # Insert 10 lines
            for i in range(10):
                conn.execute(
                    "INSERT INTO output_lines (process, html) VALUES (?, ?)", ("web", f"<span>Line {i}</span>")
                )
            conn.commit()

        # Test limiting to 5 lines
        lines = self.client.get_output_lines(since_id=0, limit=5)

        # Should get only 5 most recent lines
        self.assertEqual(len(lines), 5)
        # Check we got the most recent lines (5-9, not 0-4)
        self.assertIn("Line 5", lines[0]["html"])
        self.assertIn("Line 9", lines[-1]["html"])

    def test_exception_handling(self):
        """Test exception handling when database operations fail"""
        # Test with invalid database path
        client = DatabaseClient("/invalid/path")

        # All operations should return empty/default results
        self.assertFalse(client.is_database_available())
        self.assertEqual(client.get_output_lines(), [])
        self.assertEqual(client.get_max_id(), 0)
        self.assertEqual(client.get_process_stats(), {})

    def test_empty_database_stats(self):
        """Test getting stats from empty database"""
        # Create empty database
        with sqlite3.connect(self.client.db_path) as conn:
            conn.execute("""
                CREATE TABLE output_lines (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    process TEXT NOT NULL,
                    html TEXT NOT NULL
                )
            """)
            conn.commit()

        stats = self.client.get_process_stats()
        self.assertEqual(stats, {})


if __name__ == "__main__":
    unittest.main()
