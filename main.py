#!/usr/bin/env python3
"""
Overmind GUI - Web-based interface for Overmind process management

A modern, real-time web interface for managing Overmind processes with:
- Live process monitoring and control
- Real-time output streaming
- Advanced filtering and search
- Modern React-based UI
- Desktop app wrapper via PyWebView
"""

import argparse
import asyncio
import os
import subprocess
import sys
import unittest
import warnings

from sanic import Sanic
from sanic.server.protocols.websocket_protocol import WebSocketProtocol

import webview

# Import our modules
from process_manager import ProcessManager
from overmind_controller import OvermindController
from websocket_handler import websocket_handler, websocket_manager
from static_files import setup_static_routes

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
app = Sanic("OvermindGUI")
app.config.DEBUG = True
app.config.AUTO_RELOAD = True
app.config.UI_PORT = DEFAULT_PORT

# Initialize managers
app.ctx.process_manager = ProcessManager()
app.ctx.overmind_controller = None
app.ctx.tasks = []


# -----------------------------------------------------------------------------
# Background tasks and callbacks
# -----------------------------------------------------------------------------
def handle_output_line(line: str, app_instance):
    """Handle new output line from overmind"""
    # Add to process manager
    app_instance.ctx.process_manager.add_output_line(line)

    # Schedule broadcast to WebSocket clients
    asyncio.create_task(websocket_manager.broadcast("output_line", {"line": line}))


def handle_status_update(status_updates: dict, app_instance):
    """Handle status updates from overmind"""
    # Update process manager
    for process_name, status in status_updates.items():
        app_instance.ctx.process_manager.update_process_status(process_name, status)

    # Get updated stats
    stats = app_instance.ctx.process_manager.get_stats()

    # Schedule broadcast to WebSocket clients
    asyncio.create_task(websocket_manager.broadcast("status_update", {
        "updates": status_updates,
        "stats": stats
    }))


async def periodic_status_update(app_instance):
    """Periodically check and broadcast status updates"""
    await asyncio.sleep(10)  # Wait for initial startup

    while app_instance.ctx.running:
        try:
            if app_instance.ctx.overmind_controller:
                # Force a status check
                status_output = await app_instance.ctx.overmind_controller.get_status()
                if status_output:
                    status_updates = app_instance.ctx.overmind_controller.parse_status_output(
                        status_output
                    )
                    if status_updates:
                        handle_status_update(status_updates, app_instance)
        except (OSError, subprocess.SubprocessError) as e:
            print(f"Error in periodic status update: {e}")

        # Wait 30 seconds before next check
        await asyncio.sleep(30)


async def output_broadcaster(app_instance):
    """Broadcast combined output to new clients"""
    while app_instance.ctx.running:
        await asyncio.sleep(5)  # Check every 5 seconds

        # This task mainly exists to keep the event loop active
        # Actual broadcasting happens in the WebSocket message handlers


# -----------------------------------------------------------------------------
# Lifecycle hooks
# -----------------------------------------------------------------------------
@app.listener("before_server_start")
async def setup_app(app_instance, loop):
    """Set up the application before server starts"""
    app_instance.ctx.running = True

    # Check for Procfile
    if not os.path.exists("Procfile"):
        print("WARNING: No Procfile found in current directory")
        return

    # Load processes from Procfile
    try:
        process_names = app_instance.ctx.process_manager.load_procfile()
        print(f"Loaded {len(process_names)} processes: {', '.join(process_names)}")
    except (FileNotFoundError, OSError) as e:
        print(f"Error loading Procfile: {e}")
        return

    # Initialize overmind controller with callbacks
    app_instance.ctx.overmind_controller = OvermindController(
        output_callback=lambda line: handle_output_line(line, app_instance),
        status_callback=lambda updates: handle_status_update(updates, app_instance)
    )

    # Start overmind
    success = await app_instance.ctx.overmind_controller.start()
    if success:
        print("Overmind started successfully")
    else:
        print("Failed to start Overmind - continuing without it")

    # Start background tasks
    tasks = [
        loop.create_task(periodic_status_update(app_instance)),
        loop.create_task(output_broadcaster(app_instance))
    ]
    app_instance.ctx.tasks.extend(tasks)


@app.listener("before_server_stop")
async def cleanup_app(app_instance, _loop):
    """Clean up resources before server stops"""
    app_instance.ctx.running = False

    # Stop overmind controller
    if app_instance.ctx.overmind_controller:
        await app_instance.ctx.overmind_controller.stop()

    # Cancel background tasks
    for task in app_instance.ctx.tasks:
        task.cancel()

    if app_instance.ctx.tasks:
        await asyncio.gather(*app_instance.ctx.tasks, return_exceptions=True)

    app_instance.ctx.tasks.clear()
    print("Cleanup completed")


# -----------------------------------------------------------------------------
# UI launcher
# -----------------------------------------------------------------------------
def launch_ui(port: int):
    """Launch the desktop UI using webview"""
    webview.create_window(
        "Overmind GUI",
        f"http://localhost:{port}",
        width=1400,
        height=900,
        min_size=(800, 600)
    )
    webview.start()


# -----------------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------------
def main():
    """Main entry point for the application"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Overmind GUI - Web-based process management interface",
        allow_abbrev=False
    )

    parser.add_argument("--ui", action="store_true",
                       help="Launch desktop UI mode (PyWebView)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT,
                       help=f"Port to run on (default: {DEFAULT_PORT})")
    parser.add_argument("--host", type=str, default=HOST,
                       help=f"Host to bind to (default: {HOST})")
    parser.add_argument("--no-browser", action="store_true",
                       help="Don't open browser automatically")

    # Parse known args, everything else could be passed to overmind
    args, unknown_args = parser.parse_known_args()

    if unknown_args:
        print(f"Note: Unknown arguments will be ignored: {' '.join(unknown_args)}")

    # Set configuration
    app.config.UI_PORT = args.port

    # Check for Procfile
    if not os.path.exists("Procfile"):
        print("ERROR: No Procfile found in current directory")
        print("Please run this application from a directory containing a Procfile")
        return 1

    # Check if overmind is available
    try:
        result = subprocess.run(["overmind", "--version"],
                              capture_output=True, check=True)
        print(f"Found overmind: {result.stdout.decode().strip()}")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("WARNING: overmind not found or not working")
        print("Please install overmind: brew install overmind")
        print("Continuing anyway - GUI will work but process management will be limited")

    print(f"Starting Overmind GUI on {args.host}:{args.port}")
    print("Press Ctrl+C to stop")

    if args.ui:
        # Launch desktop UI
        print("Launching desktop application...")
        launch_ui(args.port)
    else:
        # Run web server
        if not args.no_browser:
            print(f"Open your browser to: http://{args.host}:{args.port}")

        try:
            app.run(
                host=args.host,
                port=args.port,
                protocol=WebSocketProtocol,
                debug=True,
                auto_reload=True,
                access_log=False  # Reduce noise
            )
        except KeyboardInterrupt:
            print("\nShutting down...")
        except (OSError, RuntimeError) as e:
            print(f"Error starting server: {e}")
            return 1

    return 0


# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------
class TestOvermindGui(unittest.TestCase):
    """Test cases for the Overmind GUI application"""

    def test_default_configuration(self):
        """Test default configuration values"""
        self.assertEqual(DEFAULT_PORT, 8000)
        self.assertEqual(HOST, "127.0.0.1")

    def test_app_initialization(self):
        """Test that the Sanic app is properly initialized"""
        self.assertEqual(app.name, "OvermindGUI")
        self.assertTrue(app.config.DEBUG)
        self.assertTrue(app.config.AUTO_RELOAD)

    def test_process_manager_initialization(self):
        """Test that process manager is initialized"""
        self.assertIsInstance(app.ctx.process_manager, ProcessManager)

    def test_tasks_list_initialization(self):
        """Test that tasks list is initialized"""
        self.assertIsInstance(app.ctx.tasks, list)

    def test_main_function_exists(self):
        """Test that main function is callable"""
        self.assertTrue(callable(main))

    def test_launch_ui_function_exists(self):
        """Test that launch_ui function is callable"""
        self.assertTrue(callable(launch_ui))


def setup_routes_for_app():
    """Setup routes for the app - only called when running as main"""
    setup_static_routes(app)
    # WebSocket route
    app.websocket("/ws")(websocket_handler)


if __name__ == "__main__":
    # Only setup routes when running as main script
    setup_routes_for_app()
    EXIT_CODE = main()
    sys.exit(EXIT_CODE)
