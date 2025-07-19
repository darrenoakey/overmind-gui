#!/usr/bin/env python3
"""
Overmind GUI - A Sanic-based web application with WebSocket support.

This module provides a web interface for the Overmind system with real-time
messaging capabilities via WebSockets and optional desktop UI via webview.
"""

import argparse
import asyncio
import os
import sys
import unittest
import warnings

from sanic import Sanic, Websocket
from sanic.response import html
from sanic.server.protocols.websocket_protocol import WebSocketProtocol

import webview
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# -----------------------------------------------------------------------------
# Suppress pkg_resources warning from tracerite/html
# -----------------------------------------------------------------------------
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    module="tracerite.html",
)

# -----------------------------------------------------------------------------
# Defaults
# -----------------------------------------------------------------------------
DEFAULT_PORT = 8000
HOST = "127.0.0.1"

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = Sanic("ShellApp")
app.config.DEBUG = True
app.config.AUTO_RELOAD = True
app.config.UI_PORT = DEFAULT_PORT

clients = set()
app.ctx.tasks = []


# -----------------------------------------------------------------------------
# HTTP & WebSocket handlers
# -----------------------------------------------------------------------------
@app.route("/")
async def index(_request):
    """Serve the main HTML page."""
    return html(
        f"""<!DOCTYPE html>
<html>
  <head><title>overmind gui</title></head>
  <body>
    <h1>Messages (port {app.config.UI_PORT})</h1>
    <ul id="messages"></ul>
    <script>
      const ws = new WebSocket(`ws://${{window.location.host}}/ws`);
      ws.onmessage = e => {{
        const li = document.createElement("li");
        li.textContent = e.data;
        document.getElementById("messages").appendChild(li);
      }};
      window.onbeforeunload = () => ws.close();
    </script>
  </body>
</html>"""
    )


@app.websocket("/ws")
async def websocket_handler(_request, ws: Websocket):
    """Handle WebSocket connections."""
    clients.add(ws)
    try:
        async for _ in ws:
            pass
    except (ConnectionClosedOK, ConnectionClosedError, asyncio.CancelledError):
        ...
    finally:
        clients.discard(ws)


# -----------------------------------------------------------------------------
# Lifecycle hooks
# -----------------------------------------------------------------------------
@app.listener("before_server_start")
async def setup(app_instance, loop):
    """Set up background tasks before server starts."""
    app_instance.ctx.running = True
    # start ticker + watcher
    t1 = loop.create_task(tick_worker(app_instance))
    t2 = loop.create_task(process_watcher(app_instance))
    app_instance.ctx.tasks.extend([t1, t2])


@app.listener("before_server_stop")
async def cleanup(app_instance, _loop):
    """Clean up resources before server stops."""
    # signal tasks to stop
    app_instance.ctx.running = False
    # cancel & await them
    for t in app_instance.ctx.tasks:
        t.cancel()
    await asyncio.gather(*app_instance.ctx.tasks, return_exceptions=True)
    app_instance.ctx.tasks.clear()
    # remove any leftover clients
    clients.clear()


# -----------------------------------------------------------------------------
# Background tasks
# -----------------------------------------------------------------------------
async def tick_worker(app_instance):
    """Send periodic tick messages to connected clients."""
    count = 0
    while app_instance.ctx.running:
        for ws in list(clients):
            try:
                await ws.send(f"tick {count}")
            except (ConnectionClosedOK, ConnectionClosedError):
                pass
        count += 1
        await asyncio.sleep(1)


async def process_watcher(app_instance):
    """Watch for UI process output."""
    port = app_instance.config.UI_PORT
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        __file__,
        "--ui",
        "--port",
        str(port),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=os.getcwd(),
    )
    try:
        while app_instance.ctx.running and proc.returncode is None:
            line = await proc.stdout.readline()
            if not line:
                break
            print(f"[UI] {line.decode().rstrip()}", file=sys.stdout)
    finally:
        if proc.returncode is None:
            proc.kill()
        await proc.wait()
    if app_instance.ctx.running:
        app_instance.stop()


# -----------------------------------------------------------------------------
# UI‑only launcher
# -----------------------------------------------------------------------------
def launch_ui(port: int):
    """Launch the desktop UI using webview."""
    webview.create_window("overmind gui", f"http://localhost:{port}")
    webview.start()


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="UI‑only mode")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port")
    args = parser.parse_args()

    app.config.UI_PORT = args.port

    if args.ui:
        launch_ui(args.port)
    else:
        app.run(
            host=HOST,
            port=args.port,
            protocol=WebSocketProtocol,
            debug=True,
            auto_reload=True,
        )


class TestOvermindGui(unittest.TestCase):
    """Test cases for the Overmind GUI application."""

    def test_default_port(self):
        """Test that the default port is set correctly."""
        self.assertEqual(DEFAULT_PORT, 8000)

    def test_host_configuration(self):
        """Test that the host is configured correctly."""
        self.assertEqual(HOST, "127.0.0.1")

    def test_app_configuration(self):
        """Test that the Sanic app is configured correctly."""
        self.assertTrue(app.config.DEBUG)
        self.assertTrue(app.config.AUTO_RELOAD)
        self.assertEqual(app.config.UI_PORT, DEFAULT_PORT)

    def test_clients_set_initialization(self):
        """Test that the clients set is initialized."""
        self.assertIsInstance(clients, set)

    def test_app_tasks_initialization(self):
        """Test that the app tasks list is initialized."""
        self.assertIsInstance(app.ctx.tasks, list)

    async def test_index_response(self):
        """Test that the index route returns HTML with correct title."""
        from unittest.mock import MagicMock
        request = MagicMock()
        response = await index(request)
        self.assertIn("overmind gui", response.body.decode())
        self.assertIn("<title>overmind gui</title>", response.body.decode())


if __name__ == "__main__":
    main()
