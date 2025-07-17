"""Configuration structure for overmindgui multi-process application."""

import socket
import unittest
from dataclasses import dataclass
from multiprocessing import Queue
from typing import Dict, Any


@dataclass
class AppConfig:
    """Configuration passed to all processes."""
    port: int
    sanic_queue: Queue
    overmind_queue: Queue
    frontend_queue: Queue

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary for easier passing."""
        return {
            'port': self.port,
            'sanic_queue': self.sanic_queue,
            'overmind_queue': self.overmind_queue,
            'frontend_queue': self.frontend_queue
        }


def find_free_port() -> int:
    """Find a free port for the application."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


class TestConfig(unittest.TestCase):
    """Test cases for configuration functionality."""

    def test_find_free_port(self):
        """Test that find_free_port returns a valid port number."""
        port = find_free_port()
        self.assertIsInstance(port, int)
        self.assertGreater(port, 0)
        self.assertLess(port, 65536)

    def test_app_config_creation(self):
        """Test AppConfig object creation."""
        config = AppConfig(
            port=8000,
            sanic_queue=Queue(),
            overmind_queue=Queue(),
            frontend_queue=Queue()
        )
        self.assertEqual(config.port, 8000)
        # Check that it has queue-like methods instead of type checking
        self.assertTrue(hasattr(config.sanic_queue, 'put'))
        self.assertTrue(hasattr(config.sanic_queue, 'get'))

    def test_config_to_dict(self):
        """Test config to dictionary conversion."""
        config = AppConfig(
            port=8000,
            sanic_queue=Queue(),
            overmind_queue=Queue(),
            frontend_queue=Queue()
        )
        config_dict = config.to_dict()
        self.assertEqual(config_dict['port'], 8000)
        self.assertIn('sanic_queue', config_dict)
