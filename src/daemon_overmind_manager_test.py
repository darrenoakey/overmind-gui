#!/usr/bin/env python3
"""Integration tests for daemon_overmind_manager module."""

import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from daemon_overmind_manager import DaemonOvermindManager


class TestDaemonOvermindManagerUnit(unittest.TestCase):
    """Unit tests for DaemonOvermindManager class methods"""

    def setUp(self):
        """Set up test environment"""
        self.test_dir = tempfile.mkdtemp()

        # Create a simple database manager
        class TestDBManager:
            def __init__(self, db_path):
                self.db_path = db_path

            def initialize_database(self):
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS output_lines (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            process TEXT NOT NULL,
                            html TEXT NOT NULL
                        )
                    """)
                    conn.commit()

        self.db_manager = TestDBManager(os.path.join(self.test_dir, "test.db"))
        self.db_manager.initialize_database()
        self.manager = DaemonOvermindManager("test-instance", self.db_manager, self.test_dir)

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test daemon manager initialization"""
        self.assertEqual(self.manager.daemon_instance_id, "test-instance")
        self.assertEqual(self.manager.working_directory, self.test_dir)
        self.assertFalse(self.manager.is_running)
        self.assertFalse(self.manager.is_stopping)
        self.assertIsNone(self.manager.overmind_process)

    def test_parse_line_for_storage(self):
        """Test ANSI-to-HTML conversion in line parsing"""
        # Test normal line
        process, html = self.manager._parse_line_for_storage("test | normal output")
        self.assertEqual(process, "test")
        self.assertIn("normal output", html)

        # Test ANSI escape sequences are converted
        ansi_line = "test | \x1b[32mgreen text\x1b[0m"
        process, html = self.manager._parse_line_for_storage(ansi_line)
        self.assertEqual(process, "test")
        # Should not contain raw ANSI sequences
        self.assertNotIn("\x1b[32m", html)
        self.assertNotIn("\x1b[0m", html)

    def test_extract_process_name(self):
        """Test process name extraction"""
        # Test normal process line
        process = self.manager._extract_process_name("web | starting server")
        self.assertEqual(process, "web")

        # Test line without separator
        process = self.manager._extract_process_name("just a line")
        self.assertEqual(process, "system")

        # Test with ANSI codes in process name
        process = self.manager._extract_process_name("\x1b[32mweb\x1b[0m | output")
        self.assertEqual(process, "web")

    def test_output_file_path(self):
        """Test output file path configuration"""
        expected_path = os.path.join(self.test_dir, "overmind_output.log")
        self.assertEqual(self.manager.output_file, expected_path)


class TestDaemonOvermindManager(unittest.TestCase):
    """Integration test cases for daemon_overmind_manager module."""

    def test_bulk_output_processing_integration(self):
        """Test that daemon_overmind_manager can handle 20,000 lines of bulk output"""
        # Create temporary directory with short GUID name (avoid tmux socket path length limits)
        base_temp_dir = tempfile.gettempdir()
        test_guid = str(uuid.uuid4())[:8]  # Use only first 8 characters of UUID
        test_dir = os.path.join(base_temp_dir, f"overmind_test_{test_guid}")

        try:
            os.makedirs(test_dir, exist_ok=True)

            # Copy bulk_output.sh to test directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            bulk_output_src = os.path.join(current_dir, "bulk_output.sh")
            bulk_output_dst = os.path.join(test_dir, "bulk_output.sh")
            shutil.copy2(bulk_output_src, bulk_output_dst)

            # Create Procfile
            procfile_content = "bulk_test: ./bulk_output.sh\n"
            procfile_path = os.path.join(test_dir, "Procfile")
            with open(procfile_path, "w") as f:
                f.write(procfile_content)

            # Start the overmind daemon in the test directory
            daemon_script = os.path.join(current_dir, "overmind_daemon.py")

            daemon_process = subprocess.Popen(
                [sys.executable, daemon_script, "--working-dir", test_dir, "--log-level", "INFO"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for daemon to start and process
            time.sleep(2)

            # Check if daemon started successfully
            if daemon_process.poll() is not None:
                stdout, stderr = daemon_process.communicate()
                self.fail(f"Daemon failed to start!\nSTDOUT: {stdout}\nSTDERR: {stderr}")

            # Wait for processing to complete (bulk_output.sh should finish)
            timeout = 30
            start_time = time.time()

            while time.time() - start_time < timeout:
                if daemon_process.poll() is not None:
                    break
                time.sleep(0.5)

            # Terminate daemon and wait for clean shutdown
            daemon_process.terminate()
            try:
                stdout, stderr = daemon_process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                daemon_process.kill()
                stdout, stderr = daemon_process.communicate()

            # Print daemon output for debugging if test fails
            print(f"Daemon STDOUT: {stdout}")
            print(f"Daemon STDERR: {stderr}")

            # Check the database
            db_path = os.path.join(test_dir, "overmind.db")
            self.assertTrue(os.path.exists(db_path), f"Database not found at {db_path}")

            # Connect to database and verify content
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            try:
                # Get all lines from bulk_test process to verify content
                cursor.execute("""
                    SELECT id, process, html
                    FROM output_lines
                    WHERE process = 'bulk_test'
                    ORDER BY id
                """)

                lines = cursor.fetchall()
                line_count = len(lines)

                # Should have exactly 20,000 data lines
                self.assertGreaterEqual(line_count, 20000, f"Expected >=20000 lines, got {line_count}")

                # Verify line sequence by extracting line numbers
                seen_numbers = []
                for line_id, process, html in lines:
                    # Extract line number from content like "BATCH1 Line #00001:" or "Line #00001:"
                    match = re.search(r"Line #(\d+):", html)
                    if match:
                        line_num = int(match.group(1))
                        seen_numbers.append(line_num)

                # Should have extracted numbered lines
                if seen_numbers:
                    expected_range = set(range(1, 20001))  # 1 to 20000
                    actual_set = set(seen_numbers)
                    missing_lines = expected_range - actual_set

                    if missing_lines:
                        self.fail(
                            f"Missing {len(missing_lines)} numbered lines. "
                            f"First 10 missing: {sorted(list(missing_lines))[:10]}"
                        )

            finally:
                conn.close()

        finally:
            # Clean up test directory
            if os.path.exists(test_dir):
                try:
                    shutil.rmtree(test_dir)
                except Exception:
                    pass  # Best effort cleanup

    def test_colorized_output_to_database_integration(self):
        """Test that colorized output is properly converted to HTML and stored in database"""
        # Create temporary directory with short GUID name (avoid tmux socket path length limits)
        base_temp_dir = tempfile.gettempdir()
        test_guid = str(uuid.uuid4())[:8]  # Use only first 8 characters of UUID
        test_dir = os.path.join(base_temp_dir, f"overmind_color_test_{test_guid}")

        try:
            os.makedirs(test_dir, exist_ok=True)

            # Create Procfile with two different colored echo commands
            procfile_content = """hello_red: echo -e "\\033[31mhello\\033[0m"
world_green: echo -e "\\033[32mworld\\033[0m"
"""
            procfile_path = os.path.join(test_dir, "Procfile")
            with open(procfile_path, "w") as f:
                f.write(procfile_content)

            # Start the overmind daemon in the test directory
            current_dir = os.path.dirname(os.path.abspath(__file__))
            daemon_script = os.path.join(current_dir, "overmind_daemon.py")

            daemon_process = subprocess.Popen(
                [sys.executable, daemon_script, "--working-dir", test_dir, "--log-level", "INFO"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Wait for daemon to start and process
            time.sleep(3)

            # Check if daemon started successfully
            if daemon_process.poll() is not None:
                stdout, stderr = daemon_process.communicate()
                self.fail(f"Daemon failed to start!\nSTDOUT: {stdout}\nSTDERR: {stderr}")

            # Wait for processing to complete (echo commands should finish quickly)
            timeout = 15
            start_time = time.time()

            while time.time() - start_time < timeout:
                if daemon_process.poll() is not None:
                    break
                time.sleep(0.5)

            # Terminate daemon and wait for clean shutdown
            daemon_process.terminate()
            try:
                stdout, stderr = daemon_process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                daemon_process.kill()
                stdout, stderr = daemon_process.communicate()

            # Print daemon output for debugging if test fails
            print(f"Color test daemon STDOUT: {stdout}")
            print(f"Color test daemon STDERR: {stderr}")

            # Check the database
            db_path = os.path.join(test_dir, "overmind.db")
            self.assertTrue(os.path.exists(db_path), f"Database not found at {db_path}")

            # Connect to database and verify colorized content
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            try:
                # Get all lines from both processes
                cursor.execute("""
                    SELECT id, process, html
                    FROM output_lines
                    WHERE process IN ('hello_red', 'world_green')
                    ORDER BY id
                """)

                lines = cursor.fetchall()
                line_count = len(lines)

                # Should have at least 2 lines (one from each process)
                self.assertGreaterEqual(line_count, 2, f"Expected >=2 lines, got {line_count}")

                # Verify we have both processes
                processes_found = {line[1] for line in lines}
                self.assertIn("hello_red", processes_found, "hello_red process output not found")
                self.assertIn("world_green", processes_found, "world_green process output not found")

                # Verify HTML contains proper color formatting
                red_html_found = False
                green_html_found = False

                for line_id, process, html in lines:
                    print(f"Process: {process}, HTML: {html}")

                    if process == "hello_red":
                        # Should contain red color
                        has_red_standard = "color: #800000" in html or "color: #ff0000" in html
                        has_red_generic = "color:" in html and (
                            "red" in html.lower() or "800000" in html or "ff0000" in html
                        )
                        if has_red_standard or has_red_generic:
                            red_html_found = True
                        self.assertIn("hello", html, f"'hello' text not found in red process HTML: {html}")

                    elif process == "world_green":
                        # Should contain green color
                        has_green_standard = "color: #008000" in html or "color: #00ff00" in html
                        has_green_generic = "color:" in html and (
                            "green" in html.lower() or "008000" in html or "00ff00" in html
                        )
                        if has_green_standard or has_green_generic:
                            green_html_found = True
                        self.assertIn("world", html, f"'world' text not found in green process HTML: {html}")

                    # Verify no raw ANSI escape sequences made it into the database
                    self.assertNotIn("\x1b[", html, f"Raw ANSI escape sequences found in HTML: {html}")
                    self.assertNotIn("\\033[", html, f"Raw ANSI escape sequences found in HTML: {html}")

                # Verify both colors were found
                self.assertTrue(red_html_found, "Red color formatting not found in hello_red process HTML")
                self.assertTrue(green_html_found, "Green color formatting not found in world_green process HTML")

            finally:
                conn.close()

        finally:
            # Clean up test directory
            if os.path.exists(test_dir):
                try:
                    shutil.rmtree(test_dir)
                except Exception:
                    pass  # Best effort cleanup


if __name__ == "__main__":
    unittest.main()
