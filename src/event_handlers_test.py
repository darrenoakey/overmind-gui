#!/usr/bin/env python3
"""Tests for event_handlers module."""

import unittest
import sys
import os


class TestEventHandlers(unittest.TestCase):
    """Test cases for event_handlers module."""

    def test_event_handlers_functions(self):
        """Test that event handler functions exist and are callable"""
        # Add the directory containing the module to Python path
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        import event_handlers

        self.assertTrue(callable(event_handlers.startup_handler))
        self.assertTrue(callable(event_handlers.shutdown_handler))


if __name__ == '__main__':
    unittest.main()
