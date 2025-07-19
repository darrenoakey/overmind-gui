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
import signal

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
app.ctx.overmind_failed = False
app.ctx.overmind_error = ""
app.ctx.tasks = []
app.ctx.shutdown_initiated = False

# -----------------------------------------------------------------------------
# Setup routes
# -----------------------------------------------------------------------------
setup_static_routes(app)
app.websocket("/ws")(websocket_handler)


# -----------------------------------------------------------------------------
# Background task callbacks
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


# -----------------------------------------------------------------------------
# Background tasks
# -----------------------------------------------------------------------------
async def overmind_task(app_instance):
    """Run the overmind controller as a background task"""
    # Check for Procfile
    if not os.path.exists("Procfile"):
        print("WARNING: No Procfile found in current directory")
        app_instance.ctx.overmind_failed = True
        app_instance.ctx.overmind_error = "No Procfile found in current directory"
        return

    # Load processes from Procfile
    try:
        process_names = app_instance.ctx.process_manager.load_procfile()
        print(f"Loaded {len(process_names)} processes: {', '.join(process_names)}")
    except (FileNotFoundError, OSError) as e:
        print(f"Error loading Procfile: {e}")
        app_instance.ctx.overmind_failed = True
        app_instance.ctx.overmind_error = f"Error loading Procfile: {e}"
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
        # Broadcast success to any connected clients
        asyncio.create_task(websocket_manager.broadcast("overmind_status", {
            "status": "running",
            "error": None
        }))
    else:
        error_msg = "Failed to start Overmind"
        # Check for common issues
        if os.path.exists(".overmind.sock"):
            error_msg += " (socket file exists - another instance may be running)"
        print(error_msg)
        app_instance.ctx.overmind_failed = True
        app_instance.ctx.overmind_error = error_msg
        
        # Broadcast failure to any connected clients
        asyncio.create_task(websocket_manager.broadcast("overmind_status", {
            "status": "failed",
            "error": error_msg
        }))
        return

    # Keep running periodic status updates
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


async def ui_launcher_task(app_instance):
    """Launch the UI subprocess"""
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
# Signal handling for graceful shutdown
# -----------------------------------------------------------------------------
def setup_signal_handlers(app_instance):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(sig, _frame):
        if not app_instance.ctx.shutdown_initiated:
            print(f"\nReceived signal {sig}, shutting down gracefully...")
            app_instance.ctx.shutdown_initiated = True
            app_instance.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


# -----------------------------------------------------------------------------
# Lifecycle hooks
# -----------------------------------------------------------------------------
@app.listener("before_server_start")
async def setup(app_instance, loop):
    """Set up the application before server starts"""
    app_instance.ctx.running = True

    # Setup signal handlers
    setup_signal_handlers(app_instance)

    # Start overmind controller task
    t1 = loop.create_task(overmind_task(app_instance))

    # Start UI launcher task
    t2 = loop.create_task(ui_launcher_task(app_instance))

    app_instance.ctx.tasks.extend([t1, t2])


@app.listener("before_server_stop")
async def cleanup(app_instance, _loop):
    """Clean up resources before server stops"""
    if app_instance.ctx.shutdown_initiated:
        return  # Already cleaning up
    
    print("Starting cleanup...")
    app_instance.ctx.shutdown_initiated = True
    # signal tasks to stop
    app_instance.ctx.running = False

    # Stop overmind controller first and WAIT for it
    if app_instance.ctx.overmind_controller:
        print("Stopping overmind controller...")
        await app_instance.ctx.overmind_controller.stop()
        print("Overmind controller stopped")

    # cancel & await tasks
    print("Cancelling background tasks...")
    for t in app_instance.ctx.tasks:
        t.cancel()
    await asyncio.gather(*app_instance.ctx.tasks, return_exceptions=True)
    app_instance.ctx.tasks.clear()
    print("Cleanup completed")


# -----------------------------------------------------------------------------
# UI‑only launcher
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
# Entrypoint
# -----------------------------------------------------------------------------
def main():
    """Main entry point for the application"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="UI‑only mode")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="Port")
    args = parser.parse_args()

    app.config.UI_PORT = args.port

    if args.ui:
        launch_ui(args.port)
        return 0

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

    print(f"Starting Overmind GUI on {HOST}:{args.port}")
    print("Press Ctrl+C to stop")

    try:
        app.run(
            host=HOST,
            port=args.port,
            protocol=WebSocketProtocol,
            debug=True,
            auto_reload=True,
        )
    except KeyboardInterrupt:
        print("\nShutdown complete")
    except (OSError, RuntimeError) as e:
        print(f"Error: {e}")
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


if __name__ == "__main__":
    main()
