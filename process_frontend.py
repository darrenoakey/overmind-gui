"""Frontend process - manages pywebview window and waits for sanic to be ready."""

import threading
import time
import unittest
from multiprocessing import Queue
from typing import Dict, Any

import requests
import webview


def wait_for_sanic(port: int, timeout: int = 30) -> bool:
    """Wait for sanic server to be ready.

    Args:
        port: Port where sanic is running
        timeout: Maximum time to wait in seconds

    Returns:
        True if sanic is ready, False if timeout
    """
    start_time = time.time()
    url = f"http://localhost:{port}"

    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(0.5)

    return False


def check_queue_for_stop(frontend_queue: Queue, window) -> None:
    """Check queue for stop messages in a separate thread.

    Args:
        frontend_queue: Queue to check for messages
        window: Webview window to close if stop received
    """
    while True:
        try:
            message = frontend_queue.get(timeout=1)
            if message.get('type') == 'stop':
                print("Frontend process received stop signal")
                try:
                    window.destroy()
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
                break
        except Exception:  # pylint: disable=broad-exception-caught
            # Timeout or no message, continue
            continue


def frontend_main(config: Dict[str, Any]) -> None:
    """Main function for the frontend process.

    Args:
        config: Configuration dictionary containing queues and port
    """
    port: int = config['port']
    sanic_queue: Queue = config['sanic_queue']
    overmind_queue: Queue = config['overmind_queue']
    frontend_queue: Queue = config['frontend_queue']

    print("Frontend process started")

    # Wait for sanic to be ready
    print(f"Waiting for sanic server on port {port}...")
    if not wait_for_sanic(port):
        print("Timeout waiting for sanic server")
        return

    print("Sanic server is ready")

    # Call the start endpoint (don't wait for response)
    try:
        threading.Thread(
            target=lambda: requests.get(f"http://localhost:{port}/start", timeout=1),
            daemon=True
        ).start()
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    # Create webview window
    url = f"http://localhost:{port}"
    window = webview.create_window('Overmind GUI', url, width=800, height=600)

    # Start thread to check for stop messages
    stop_checker = threading.Thread(
        target=check_queue_for_stop,
        args=(frontend_queue, window),
        daemon=True
    )
    stop_checker.start()

    # Start webview (this blocks until window is closed)
    try:
        webview.start(debug=False)
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    # If we get here, window was closed - send stop to all other processes
    print("Frontend window closed, sending stop signals")
    try:
        sanic_queue.put_nowait({'type': 'stop'})
    except Exception:  # pylint: disable=broad-exception-caught
        pass
    try:
        overmind_queue.put_nowait({'type': 'stop'})
    except Exception:  # pylint: disable=broad-exception-caught
        pass

    print("Frontend process finished")


class TestFrontend(unittest.TestCase):
    """Test cases for frontend functionality."""

    def test_wait_for_sanic_timeout(self):
        """Test that wait_for_sanic times out properly."""
        # Use a port that's definitely not in use
        result = wait_for_sanic(65432, timeout=1)
        self.assertFalse(result)

    def test_stop_message_format(self):
        """Test stop message format."""
        stop_message = {'type': 'stop'}
        self.assertEqual(stop_message['type'], 'stop')
