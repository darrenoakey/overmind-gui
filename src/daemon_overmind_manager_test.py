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
            with open(procfile_path, 'w') as f:
                f.write(procfile_content)

            # Start the overmind daemon in the test directory
            daemon_script = os.path.join(current_dir, "overmind_daemon.py")

            daemon_process = subprocess.Popen([
                sys.executable, daemon_script,
                "--working-dir", test_dir,
                "--log-level", "INFO"
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

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
                self.assertGreaterEqual(line_count, 20000,
                                      f"Expected >=20000 lines, got {line_count}")

                # Verify line sequence by extracting line numbers
                seen_numbers = []
                for line_id, process, html in lines:
                    # Extract line number from content like "BATCH1 Line #00001:" or "Line #00001:"
                    match = re.search(r'Line #(\d+):', html)
                    if match:
                        line_num = int(match.group(1))
                        seen_numbers.append(line_num)

                # Should have extracted numbered lines
                if seen_numbers:
                    expected_range = set(range(1, 20001))  # 1 to 20000
                    actual_set = set(seen_numbers)
                    missing_lines = expected_range - actual_set

                    if missing_lines:
                        self.fail(f"Missing {len(missing_lines)} numbered lines. "
                                f"First 10 missing: {sorted(list(missing_lines))[:10]}")

            finally:
                conn.close()

        finally:
            # Clean up test directory
            if os.path.exists(test_dir):
                try:
                    shutil.rmtree(test_dir)
                except Exception:
                    pass  # Best effort cleanup


if __name__ == '__main__':
    unittest.main()
