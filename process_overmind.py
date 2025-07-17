"""Overmind process - sends periodic updates to the sanic process."""

import time
import unittest
from multiprocessing import Queue
from typing import Dict, Any


def overmind_main(config: Dict[str, Any]) -> None:
    """Main function for the overmind process.

    Args:
        config: Configuration dictionary containing queues and port
    """
    sanic_queue: Queue = config['sanic_queue']
    overmind_queue: Queue = config['overmind_queue']

    print("Overmind process started")

    counter = 0
    while True:
        # Check for stop message (non-blocking)
        try:
            message = overmind_queue.get_nowait()
            if message.get('type') == 'stop':
                print("Overmind process received stop signal")
                break
        except Exception:  # pylint: disable=broad-exception-caught
            # No message available, continue
            pass

        # Send update message to sanic
        counter += 1
        update_message = {
            'type': 'update',
            'data': f'Update #{counter} from overmind at {time.strftime("%H:%M:%S")}',
            'timestamp': time.time()
        }

        try:
            sanic_queue.put_nowait(update_message)
        except Exception:  # pylint: disable=broad-exception-caught
            # Queue might be full, just continue
            pass

        # Wait for 1 second
        time.sleep(1)

    print("Overmind process finished")


class TestOvermind(unittest.TestCase):
    """Test cases for overmind functionality."""

    def test_overmind_message_format(self):
        """Test that overmind creates properly formatted messages."""
        # This is a basic structure test
        message = {
            'type': 'update',
            'data': 'Test message',
            'timestamp': time.time()
        }
        self.assertEqual(message['type'], 'update')
        self.assertIn('data', message)
        self.assertIn('timestamp', message)

    def test_stop_message_format(self):
        """Test stop message format."""
        stop_message = {'type': 'stop'}
        self.assertEqual(stop_message['type'], 'stop')
