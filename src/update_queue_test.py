#!/usr/bin/env python3
"""Tests for update_queue module."""

import unittest
from update_queue import UpdateQueue


class TestUpdateQueue(unittest.TestCase):
    """Test cases for update_queue module."""

    def setUp(self):
        """Set up fresh UpdateQueue for each test"""
        self.queue = UpdateQueue()

    def test_initialization(self):
        """Test UpdateQueue initialization"""
        self.assertEqual(self.queue.message_counter, 0)
        self.assertEqual(len(self.queue.output_lines), 0)
        self.assertEqual(len(self.queue.status_updates), 0)

    def test_get_current_state(self):
        """Test getting current state"""
        state = self.queue.get_current_state()
        self.assertIn('output_lines', state)
        self.assertIn('status_updates', state)
        self.assertIn('latest_message_id', state)
        self.assertIn('processes', state)
        self.assertIn('stats', state)
        self.assertEqual(state['latest_message_id'], 0)

    def test_add_output_line(self):
        """Test adding output lines"""
        self.queue.add_output_line("Test output", "test_process")

        self.assertEqual(self.queue.message_counter, 1)
        self.assertEqual(len(self.queue.output_lines), 1)

        line = self.queue.output_lines[0]
        self.assertEqual(line['id'], 1)
        self.assertEqual(line['html'], "Test output")
        self.assertEqual(line['process'], "test_process")
        self.assertIsInstance(line['timestamp'], float)

    def test_add_status_update(self):
        """Test adding status updates"""
        self.queue.add_status_update("test_process", "running")

        self.assertEqual(self.queue.message_counter, 1)
        self.assertEqual(len(self.queue.status_updates), 1)

        update = self.queue.status_updates[0]
        self.assertEqual(update['id'], 1)
        self.assertEqual(update['process'], "test_process")
        self.assertEqual(update['status'], "running")
        self.assertIsInstance(update['timestamp'], float)

    def test_add_bulk_status_updates(self):
        """Test adding multiple status updates at once"""
        updates = {
            'web': 'running',
            'worker': 'stopped',
            'helper': 'dead'
        }

        self.queue.add_bulk_status_updates(updates)

        self.assertEqual(self.queue.message_counter, 3)
        self.assertEqual(len(self.queue.status_updates), 3)

        # Check all processes were updated
        processes = {update['process'] for update in self.queue.status_updates}
        self.assertEqual(processes, {'web', 'worker', 'helper'})

    def test_get_updates_since(self):
        """Test getting updates since specific message ID"""
        self.queue.add_output_line("Line 1", "p1")
        self.queue.add_status_update("p1", "running")

        updates = self.queue.get_updates_since(0)
        self.assertIn('output_lines', updates)
        self.assertIn('status_updates', updates)
        self.assertIn('latest_message_id', updates)
        self.assertEqual(updates['latest_message_id'], 2)

    def test_clear_all(self):
        """Test clearing all queued data"""
        self.queue.add_output_line("Test", "test")
        self.queue.add_status_update("test", "running")

        initial_counter = self.queue.message_counter
        self.queue.clear_all()

        self.assertEqual(len(self.queue.output_lines), 0)
        self.assertEqual(len(self.queue.status_updates), 0)
        self.assertEqual(self.queue.message_counter, initial_counter + 1)

    def test_get_stats(self):
        """Test getting queue statistics"""
        self.queue.add_output_line("Test", "test")
        self.queue.add_status_update("test", "running")

        stats = self.queue.get_stats()
        self.assertEqual(stats['total_messages'], 2)
        self.assertEqual(stats['total_lines'], 1)
        self.assertEqual(stats['total_status_updates'], 1)

    def test_output_line_limit(self):
        """Test that output lines are limited to prevent memory growth"""
        # Add exactly 1001 lines to trigger trimming once
        for i in range(1001):
            self.queue.add_output_line(f"Line {i}", "test")

        # After adding 1001 items, it should trim to 500 at the 1001st addition
        self.assertEqual(len(self.queue.output_lines), 500)
        # Check that we have the most recent lines (501-1000)
        self.assertEqual(self.queue.output_lines[0]['html'], "Line 501")
        self.assertEqual(self.queue.output_lines[-1]['html'], "Line 1000")

    def test_status_update_limit(self):
        """Test that status updates are limited to prevent memory growth"""
        # Add exactly 201 updates to trigger trimming once
        for i in range(201):
            self.queue.add_status_update("test", f"status_{i}")

        # After adding 201 items, it should trim to 100 at the 201st addition
        self.assertEqual(len(self.queue.status_updates), 100)
        # Check that we have the most recent updates (101-200)
        self.assertEqual(self.queue.status_updates[0]['status'], "status_101")
        self.assertEqual(self.queue.status_updates[-1]['status'], "status_200")

    def test_thread_safety_basic(self):
        """Test basic thread safety with lock usage"""
        import threading

        def add_lines():
            for i in range(50):
                self.queue.add_output_line(f"Thread line {i}", "thread_test")

        def add_status():
            for i in range(50):
                self.queue.add_status_update("thread_test", f"status_{i}")

        thread1 = threading.Thread(target=add_lines)
        thread2 = threading.Thread(target=add_status)

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Should have all items added
        self.assertEqual(len(self.queue.output_lines), 50)
        self.assertEqual(len(self.queue.status_updates), 50)
        self.assertEqual(self.queue.message_counter, 100)


if __name__ == '__main__':
    unittest.main()
