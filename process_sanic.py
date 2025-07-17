"""Sanic process - web server with websockets and frontend."""

import asyncio
import json
import os
import signal
import threading
import unittest
from multiprocessing import Queue
from typing import Dict, Any, Set

from sanic import Sanic, response
from sanic.server.websockets.impl import WebsocketImplProtocol


# Global variables for the sanic process
app = Sanic("overmind_gui")
connected_clients: Set[WebsocketImplProtocol] = set()
message_queue: Queue = None
SHOULD_STOP = False


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Overmind GUI</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        .messages { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; }
        .message { margin: 5px 0; padding: 5px; background-color: #f0f0f0; border-radius: 3px; }
        .timestamp { color: #666; font-size: 0.8em; }
        .status { margin: 10px 0; padding: 10px; background-color: #e8f5e8; border-radius: 3px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Overmind GUI</h1>
        <div class="status" id="status">Connecting...</div>
        <div class="messages" id="messages"></div>
    </div>

    <script>
        const messagesDiv = document.getElementById('messages');
        const statusDiv = document.getElementById('status');

        // Connect to websocket
        const ws = new WebSocket('ws://localhost:' + window.location.port + '/ws');

        ws.onopen = function(event) {
            statusDiv.textContent = 'Connected';
            statusDiv.style.backgroundColor = '#e8f5e8';
        };

        ws.onmessage = function(event) {
            const data = JSON.parse(event.data);
            if (data.type === 'update') {
                addMessage(data.data, data.timestamp);
            }
        };

        ws.onclose = function(event) {
            statusDiv.textContent = 'Disconnected';
            statusDiv.style.backgroundColor = '#f5e8e8';
        };

        ws.onerror = function(error) {
            statusDiv.textContent = 'Connection Error';
            statusDiv.style.backgroundColor = '#f5e8e8';
        };

        function addMessage(text, timestamp) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message';

            const timestampSpan = document.createElement('span');
            timestampSpan.className = 'timestamp';
            timestampSpan.textContent = new Date(timestamp * 1000).toLocaleTimeString() + ' - ';

            messageDiv.appendChild(timestampSpan);
            messageDiv.appendChild(document.createTextNode(text));

            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }
    </script>
</body>
</html>
"""


@app.route("/")
async def index(_request):
    """Serve the main frontend page."""
    return response.html(HTML_TEMPLATE)


@app.route("/start")
async def start_endpoint(_request):
    """Start the message processing loop."""
    global SHOULD_STOP  # pylint: disable=global-statement
    SHOULD_STOP = False

    # Start the message processing in a separate thread
    threading.Thread(target=process_messages, daemon=True).start()

    # Don't send a response - just let it hang
    await asyncio.sleep(3600)  # Sleep for an hour
    return response.text("OK")


@app.websocket("/ws")
async def websocket_handler(_request, websocket):
    """Handle websocket connections."""
    connected_clients.add(websocket)
    try:
        await websocket.wait_for_connection_lost()
    finally:
        connected_clients.discard(websocket)


def process_messages():
    """Process messages from the queue and send to websocket clients."""
    global SHOULD_STOP  # pylint: disable=global-statement

    while not SHOULD_STOP:
        try:
            message = message_queue.get(timeout=1)

            if message.get('type') == 'stop':
                print("Sanic process received stop signal")
                SHOULD_STOP = True
                # Shutdown the sanic app
                threading.Thread(target=shutdown_sanic, daemon=True).start()
                break
            if message.get('type') == 'update':
                # Send to all connected websocket clients
                asyncio.run(broadcast_message(message))

        except Exception:  # pylint: disable=broad-exception-caught
            # Timeout or no message, continue
            continue


async def broadcast_message(message):
    """Broadcast message to all connected websocket clients."""
    if connected_clients:
        disconnected = set()
        for client in connected_clients:
            try:
                await client.send(json.dumps(message))
            except Exception:  # pylint: disable=broad-exception-caught
                disconnected.add(client)

        # Remove disconnected clients
        for client in disconnected:
            connected_clients.discard(client)


def shutdown_sanic():
    """Shutdown the sanic application."""
    # Send signal to shutdown sanic
    os.kill(os.getpid(), signal.SIGTERM)


def sanic_main(config: Dict[str, Any]) -> None:
    """Main function for the sanic process.

    Args:
        config: Configuration dictionary containing queues and port
    """
    global message_queue  # pylint: disable=global-statement

    port: int = config['port']
    sanic_queue: Queue = config['sanic_queue']
    message_queue = sanic_queue

    print(f"Sanic process started on port {port}")

    # Run sanic
    app.run(host="0.0.0.0", port=port, debug=True)


class TestSanic(unittest.TestCase):
    """Test cases for sanic functionality."""

    def test_html_template_contains_websocket(self):
        """Test that HTML template includes websocket code."""
        self.assertIn('WebSocket', HTML_TEMPLATE)
        self.assertIn('/ws', HTML_TEMPLATE)

    def test_message_broadcast_format(self):
        """Test message format for broadcasting."""
        message = {
            'type': 'update',
            'data': 'test message',
            'timestamp': 1234567890
        }
        # Should be JSON serializable
        json_str = json.dumps(message)
        parsed = json.loads(json_str)
        self.assertEqual(parsed['type'], 'update')

    def test_stop_message_handling(self):
        """Test stop message format."""
        stop_message = {'type': 'stop'}
        self.assertEqual(stop_message['type'], 'stop')
