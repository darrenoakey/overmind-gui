#!/usr/bin/env python3
"""
Port utilities for the Overmind GUI Web Server
Provides functions for finding available ports
"""

import socket
import unittest


def find_free_port(start_port=8000, max_attempts=100):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('', port))
                return port
        except OSError:
            continue

    # If we can't find a port in the range, try system-assigned port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('', 0))
        return sock.getsockname()[1]


class TestPortUtils(unittest.TestCase):
    """Test cases for port utilities"""

    def test_find_free_port(self):
        """Test find_free_port function"""
        port = find_free_port()
        self.assertIsInstance(port, int)
        self.assertGreater(port, 0)
        self.assertLess(port, 65536)

    def test_find_free_port_with_start_port(self):
        """Test find_free_port with custom start port"""
        port = find_free_port(9000)
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, 9000)
        self.assertLess(port, 65536)

    def test_find_free_port_with_max_attempts(self):
        """Test find_free_port with custom max attempts"""
        port = find_free_port(50000, 10)
        self.assertIsInstance(port, int)
        self.assertGreater(port, 0)
        self.assertLess(port, 65536)
