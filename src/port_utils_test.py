#!/usr/bin/env python3
"""Tests for port_utils module."""

import unittest
import socket
from port_utils import find_free_port


class TestPortUtilsBasic(unittest.TestCase):
    """Basic test cases for port_utils module to ensure coverage"""

    def test_find_free_port_basic(self):
        """Test find_free_port returns a valid port"""
        port = find_free_port()
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, 8000)
        self.assertLess(port, 65536)

    def test_find_free_port_with_start_port(self):
        """Test find_free_port with custom start port"""
        port = find_free_port(9000)
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, 9000)
        self.assertLess(port, 65536)

    def test_find_free_port_with_max_attempts(self):
        """Test find_free_port with limited attempts"""
        port = find_free_port(50000, 10)
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, 50000)
        self.assertLess(port, 50010)

    def test_port_is_actually_available(self):
        """Test that the returned port is actually available"""
        port = find_free_port()

        # Try to bind to the port to verify it's available
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(('', port))
                # If we can bind, the port is available
                self.assertTrue(True)
            except OSError:
                # Port is not available - this should not happen
                self.fail(f"find_free_port returned port {port} but it's not available")

    def test_port_in_expected_range(self):
        """Test that port is in expected range"""
        port = find_free_port(8000, 50)
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, 8000)
        self.assertLess(port, 8050)

    def test_different_start_ports(self):
        """Test with different start ports"""
        port1 = find_free_port(8100, 10)
        port2 = find_free_port(8200, 10)

        self.assertGreaterEqual(port1, 8100)
        self.assertLess(port1, 8110)
        self.assertGreaterEqual(port2, 8200)
        self.assertLess(port2, 8210)


if __name__ == '__main__':
    unittest.main()
