#!/usr/bin/env python3
"""
Overmind GUI - Polling-based web interface for Overmind process management

A modern, polling-based web interface for managing Overmind processes with:
- Live process monitoring and control via polling  
- Real-time output streaming with 4x/sec updates
- Advanced filtering and search
- Modern CSS-based UI with 5000 line limit
- No WebSockets - pure HTTP polling
"""

import argparse
import asyncio
import os
import subprocess
import sys
import unittest
import warnings
import signal
import threading
import time
import traceback
import inspect
import socket

from sanic import Sanic, response

# Import our modules
from process_manager import ProcessManager
from overmind_controller import OvermindController
from static_files import setup_static_routes
from api_routes import setup_api_routes
from update_queue import update_queue

# -----------------------------------------------------------------------------
# Suppress pkg_resources warning from tracerite/html
# -----------------------------------------------------------------------------
warnings.filterwarnings(
    "ignore",
    message="pkg_resources is deprecated as an API.*",
    module="tracerite.html",
)

# -----------------------------------------------------------------------------
# Port Configuration - CRITICAL SECTION
# -----------------------------------------------------------------------------
# WARNING: DO NOT USE HARDCODED PORTS ANYWHERE EXCEPT DEFAULT_PORT_START
# The actual port will be dynamically allocated and stored in ALLOCATED_PORT_DONT_CHANGE
DEFAULT_PORT_START = 8000  # Only used as starting point for port search
HOST = "127.0.0.1"

# CRITICAL: This will be set to the actual allocated port - DO NOT MODIFY ANYWHERE ELSE
ALLOCATED_PORT_DONT_CHANGE = None

# -----------------------------------------------------------------------------
# Port management
# -----------------------------------------------------------------------------
def find_available_port(start_port=DEFAULT_PORT_START, max_attempts=100):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(('127.0.0.1', port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available ports found in range {start_port}-{start_port + max_attempts}")

# -----------------------------------------------------------------------------
# Version management
# -----------------------------------------------------------------------------
def get_and_increment_version():
    """Read current version, increment it, and return the new version"""
    # Get version file relative to script location, not current directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    version_file = os.path.join(script_dir, "version.txt")
    
    try:
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                current_version = int(f.read().strip())
        else:
            current_version = 0
        
        new_version = current_version + 1
        with open(version_file, 'w') as f:
            f.write(str(new_version))
        
        return new_version
    except (ValueError, IOError) as e:
        print(f"Error managing version: {e}")
        return 1

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = Sanic("OvermindGUI")
app.config.DEBUG = True
app.config.AUTO_RELOAD = False
app.config.WORKERS = 1
# UI_PORT will be stored in app.ctx at runtime - NO CONFIG FILES!

# Get version and store in app context
app.ctx.version = get_and_increment_version()
print(f"Starting Overmind GUI v{app.ctx.version}")

# Initialize managers
app.ctx.process_manager = ProcessManager()
app.ctx.overmind_controller = None
app.ctx.overmind_failed = False
app.ctx.overmind_error = ""
app.ctx.tasks = []
app.ctx.shutdown_initiated = False
app.ctx.shutdown_complete = False
app.ctx.overmind_args = []  # Will be populated by main()

# Global shutdown event for coordination
shutdown_event = asyncio.Event()

# -----------------------------------------------------------------------------
# Shutdown message chain
# -----------------------------------------------------------------------------
async def shutdown_message_chain(app_instance):
    """Handle the proper shutdown message flow"""
    try:
        print("🔗 SHUTDOWN MESSAGE CHAIN STARTED")
        print("=" * 40)

        # Message 1: UI closed → Stop overmind
        print("📨 [MESSAGE 1] UI closed → Stopping overmind...")
        if app_instance.ctx.overmind_controller:
            print("📦 Stopping overmind controller...")
            try:
                await app_instance.ctx.overmind_controller.stop()
                print("✅ [MESSAGE 1] Overmind controller stopped completely")
            except Exception as e:
                print(f"❌ [MESSAGE 1] Error stopping overmind: {e}")
                import traceback
                traceback.print_exc()
            finally:
                app_instance.ctx.overmind_controller = None
        else:
            print("ℹ️  [MESSAGE 1] No overmind controller to stop")

        print("📨 [MESSAGE 1] ✅ COMPLETE - Overmind shutdown finished")

        # Message 2: Overmind stopped → Stop Sanic
        print("\n📨 [MESSAGE 2] Overmind stopped → Stopping Sanic server...")
        try:
            app_instance.stop()
            print("✅ [MESSAGE 2] Sanic server shutdown initiated")
        except Exception as e:
            print(f"❌ [MESSAGE 2] Error stopping Sanic server: {e}")
            import traceback
            traceback.print_exc()

        print("📨 [MESSAGE 2] ✅ COMPLETE - Server shutdown initiated")
        print("\n🔗 SHUTDOWN MESSAGE CHAIN COMPLETED")

    except Exception as e:
        print(f"❌ Error in shutdown message chain: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: try to stop server anyway
        try:
            app_instance.stop()
        except:
            pass


# -----------------------------------------------------------------------------
# Setup routes
# -----------------------------------------------------------------------------
setup_static_routes(app)
setup_api_routes(app)


# Shutdown endpoint to stop the server
@app.route("/shutdown", methods=["POST"])
async def shutdown_server(request):
    """Shutdown the Sanic server"""
    try:
        # Schedule server stop
        request.app.add_task(lambda: request.app.stop())
        return response.json({"success": True, "message": "Server shutdown initiated"})
    except Exception as e:
        return response.json({"error": str(e)}, status=500)

# -----------------------------------------------------------------------------
# Background task callbacks for update queue
# -----------------------------------------------------------------------------
def handle_output_line(line: str, app_instance):
    """Handle new output line from overmind - add to update queue"""
    # Parse process name from overmind output
    process_name = app_instance.ctx.process_manager.add_output_line(line)
    
    if process_name:
        # Add to update queue
        update_queue.add_output_line(line, process_name)
    else:
        # Fallback - add as 'system' output
        update_queue.add_output_line(line, 'system')


def handle_status_update(status_updates: dict, app_instance):
    """Handle status updates from overmind - add to update queue"""
    # Update process manager
    for process_name, status in status_updates.items():
        app_instance.ctx.process_manager.update_process_status(process_name, status)

    # Add to update queue
    update_queue.add_bulk_status_updates(status_updates)


# -----------------------------------------------------------------------------
# Background tasks
# -----------------------------------------------------------------------------
async def overmind_task(app_instance):
    """Run the overmind controller as a background task"""
    try:
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

        # Load processes from Procfile into process manager
        process_names = app_instance.ctx.process_manager.load_procfile("Procfile")
        print(f"DEBUG: Loaded {len(process_names)} processes from Procfile: {process_names}")
        
        # Initialize overmind controller with callbacks and passthrough args
        overmind_args = getattr(app_instance.ctx, 'overmind_args', [])
        app_instance.ctx.overmind_controller = OvermindController(
            output_callback=lambda line: handle_output_line(line, app_instance),
            status_callback=lambda updates: handle_status_update(updates, app_instance),
            overmind_args=overmind_args
        )

        # Start overmind
        success = await app_instance.ctx.overmind_controller.start()
        if success:
            print("Overmind started successfully")
            # Force initial status check
            try:
                status_output = await app_instance.ctx.overmind_controller.get_status()
                if status_output:
                    status_updates = app_instance.ctx.overmind_controller.parse_status_output(status_output)
                    if status_updates:
                        handle_status_update(status_updates, app_instance)
                        print(f"Initial status loaded: {status_updates}")
            except Exception as e:
                print(f"Error getting initial status: {e}")
        else:
            error_msg = "Failed to start Overmind"
            # Check for common issues
            if os.path.exists(".overmind.sock"):
                error_msg += " (socket file exists - another instance may be running)"
            print(error_msg)
            app_instance.ctx.overmind_failed = True
            app_instance.ctx.overmind_error = error_msg
            return

        # Keep running periodic status updates
        await asyncio.sleep(10)  # Wait for initial startup

        while app_instance.ctx.running and not shutdown_event.is_set():
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
            for _ in range(30):
                if shutdown_event.is_set() or not app_instance.ctx.running:
                    break
                await asyncio.sleep(1)

    except asyncio.CancelledError:
        print("🛑 [OVERMIND TASK] Task was cancelled - shutdown in progress")
    except RuntimeError as e:
        print(f"❌ [OVERMIND TASK] Runtime error: {e}")
        traceback.print_exc()
    finally:
        print("🏁 [OVERMIND TASK] Overmind background task completed")


async def ui_launcher_task(app_instance):
    """Launch the UI subprocess"""
    proc = None
    try:
        # ====================================================================
        # CRITICAL: Port must match ALLOCATED_PORT_DONT_CHANGE
        # ====================================================================
        global ALLOCATED_PORT_DONT_CHANGE
        
        port_from_context = app_instance.ctx.UI_PORT
        port_from_global = ALLOCATED_PORT_DONT_CHANGE
        
        print(f"🔌 [UI LAUNCHER] Port from context: {port_from_context}")
        print(f"🔌 [UI LAUNCHER] Port from global: {port_from_global}")
        
        # VERIFICATION: These MUST match or we have a bug
        if port_from_context != port_from_global:
            raise RuntimeError(f"PORT MISMATCH BUG! Context={port_from_context}, Global={port_from_global}")
        
        # Use the global variable as the source of truth
        THE_CORRECT_PORT = ALLOCATED_PORT_DONT_CHANGE
        print(f"🔌 [UI LAUNCHER] Using THE_CORRECT_PORT = {THE_CORRECT_PORT}")

        # Check if we should launch UI
        if os.environ.get('NO_UI_LAUNCH', '').lower() in ('1', 'true', 'yes'):
            print("[UI] UI launch disabled by NO_UI_LAUNCH environment variable")
            return

        # CRITICAL: Pass THE_CORRECT_PORT to prevent any hardcoded 8000 issues
        subprocess_args = [
            sys.executable,
            __file__,
            "--ui",
            "--port",
            str(THE_CORRECT_PORT)  # This MUST be the same as the main server port
        ]
        print(f"🔌 [UI LAUNCHER] Subprocess args: {' '.join(subprocess_args)}")
        
        proc = await asyncio.create_subprocess_exec(
            *subprocess_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=os.getcwd(),
        )

        print(f"[UI] UI subprocess started with PID {proc.pid}")

        while app_instance.ctx.running and proc.returncode is None and not shutdown_event.is_set():
            try:
                line = await asyncio.wait_for(proc.stdout.readline(), timeout=1.0)
                if not line:
                    break
                print(f"[UI] {line.decode().rstrip()}", file=sys.stdout)
            except asyncio.TimeoutError:
                continue

        if proc.returncode is not None:
            print(f"[UI] UI subprocess exited with code {proc.returncode}")
            
            # If the UI subprocess exited normally (code 0), it means user closed the window
            # Start the shutdown message chain
            if proc.returncode == 0 and not app_instance.ctx.shutdown_initiated:
                print("\n" + "="*70)
                print("🔴 UI SUBPROCESS EXITED - STARTING SHUTDOWN MESSAGE CHAIN")
                print("="*70)
                
                # Step 1: Set flags and start overmind shutdown
                print("📨 [MESSAGE 1] UI closed → Starting overmind shutdown...")
                app_instance.ctx.shutdown_initiated = True
                shutdown_event.set()
                
                # Create a background task to handle the shutdown chain
                asyncio.create_task(shutdown_message_chain(app_instance))

    except asyncio.CancelledError:
        print("🛑 [UI LAUNCHER] Task was cancelled - shutdown in progress")
    except (OSError, subprocess.SubprocessError) as e:
        print(f"❌ [UI LAUNCHER] Error in UI launcher task: {e}")
        traceback.print_exc()
    finally:
        if proc is not None and proc.returncode is None:
            print(f"🔄 [UI LAUNCHER] Terminating UI subprocess (PID {proc.pid})")
            proc.kill()
            await proc.wait()
            print(f"✅ [UI LAUNCHER] UI subprocess terminated")
        print("🏁 [UI LAUNCHER] UI launcher task completed")


# -----------------------------------------------------------------------------
# Signal handling for graceful shutdown
# -----------------------------------------------------------------------------
def setup_signal_handlers(app_instance):
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(sig, _frame):
        if not app_instance.ctx.shutdown_initiated:
            print(f"\nReceived signal {sig}, shutting down gracefully...")
            app_instance.ctx.shutdown_initiated = True
            shutdown_event.set()
            app_instance.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


# -----------------------------------------------------------------------------
# Window close handler for webview
# -----------------------------------------------------------------------------
def on_window_closing():
    """Called when webview window is closing - trigger graceful shutdown"""
    print("\n" + "="*70)
    print("🔴 WEBVIEW WINDOW CLOSING - SHUTDOWN SEQUENCE INITIATED")
    print("="*70)
    
    # Set the shutdown flag to trigger cleanup
    if not app.ctx.shutdown_initiated:
        print("🚩 Setting shutdown flags and triggering server stop...")
        app.ctx.shutdown_initiated = True
        shutdown_event.set()
        
        # Stop the Sanic server gracefully
        try:
            print("🛑 Stopping Sanic server...")
            app.stop()
            print("✅ Sanic server stop initiated")
        except Exception as e:
            print(f"❌ Error stopping server: {e}")
    else:
        print("⚠️  Shutdown already in progress - ignoring additional close request")
    
    print("🔄 Window close handler completed - awaiting server cleanup...")
    return True


# -----------------------------------------------------------------------------
# Lifecycle hooks
# -----------------------------------------------------------------------------

@app.before_server_start
async def setup(app_instance, loop):
    """Set up the application before server starts"""
    app_instance.ctx.running = True

    # Setup signal handlers
    setup_signal_handlers(app_instance)

    # Send startup message to indicate server restart
    update_queue.add_server_started(app_instance.ctx.version)

    # Start overmind controller task
    t1 = loop.create_task(overmind_task(app_instance))

    # Start UI launcher task
    t2 = loop.create_task(ui_launcher_task(app_instance))

    app_instance.ctx.tasks.extend([t1, t2])


@app.listener("after_server_start")
async def launch_ui(_app, _loop):
    await asyncio.sleep(0.2)  # tiny grace so routes are live
    subprocess.Popen(["open", "/Applications/Overmind.app"])


@app.before_server_stop
async def cleanup(app_instance, _loop):
    """Clean up remaining resources - overmind should already be stopped by message chain"""
    if app_instance.ctx.shutdown_complete:
        print("⚠️  Cleanup already completed - skipping duplicate cleanup")
        return

    print("\n" + "="*70)
    print("🧹 FINAL SERVER CLEANUP (Message 3)")
    print("="*70)
    
    app_instance.ctx.running = False

    # Overmind should already be stopped by the message chain, but check just in case
    if app_instance.ctx.overmind_controller:
        print("⚠️  [CLEANUP] Overmind controller still present - stopping as fallback...")
        try:
            await app_instance.ctx.overmind_controller.stop()
            print("✅ [CLEANUP] Fallback overmind stop completed")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"❌ [CLEANUP] Fallback overmind stop failed: {e}")
        finally:
            app_instance.ctx.overmind_controller = None
    else:
        print("✅ [CLEANUP] Overmind already stopped by message chain")

    # Cancel background tasks
    print("\n🧹 [CLEANUP] Cancelling background tasks...")
    if app_instance.ctx.tasks:
        for i, task in enumerate(app_instance.ctx.tasks):
            if not task.done():
                print(f"🔄 [TASK {i+1}/{len(app_instance.ctx.tasks)}] Cancelling...")
                task.cancel()
            else:
                print(f"✅ [TASK {i+1}/{len(app_instance.ctx.tasks)}] Already completed")

        # Wait briefly for tasks to complete
        print("⏳ [CLEANUP] Waiting for background tasks...")
        for i, task in enumerate(app_instance.ctx.tasks):
            try:
                await asyncio.wait_for(task, timeout=5.0)
                print(f"✅ [TASK {i+1}] Completed")
            except (asyncio.TimeoutError, asyncio.CancelledError):
                print(f"✅ [TASK {i+1}] Cancelled/Timed out")
            except Exception as e:  # pylint: disable=broad-exception-caught
                print(f"⚠️  [TASK {i+1}] Error: {e}")
    else:
        print("✅ [CLEANUP] No background tasks to cancel")

    app_instance.ctx.tasks.clear()
    app_instance.ctx.shutdown_complete = True
    
    print("\n" + "="*70)
    print("✅ FINAL CLEANUP COMPLETED")
    print("🏁 APPLICATION SHUTDOWN SEQUENCE FINISHED")
    print("="*70)


# -----------------------------------------------------------------------------
# UI-only launcher
# -----------------------------------------------------------------------------
def launch_ui(port: int, is_subprocess: bool = False):
    """Launch the desktop UI - uses system browser by default, pywebview if USE_PYTHON_WEBVIEW is set
    
    CRITICAL: This function MUST receive the correct dynamically allocated port.
    DO NOT hardcode port 8000 anywhere in this function or its callees.
    """
    print(f"[UI] launch_ui called with port={port}, is_subprocess={is_subprocess}")
    
    # Check if pywebview should be used (when USE_PYTHON_WEBVIEW is set)
    use_webview = os.environ.get('USE_PYTHON_WEBVIEW', '').lower() in ('1', 'true', 'yes')
    
    if not use_webview:
        # Default path: open in system browser
        import webbrowser
        # CRITICAL: Use the passed port parameter, NOT hardcoded 8000
        url = f"http://localhost:{port}"
        print(f"[UI] Opening {url} in default system browser (NOT hardcoded 8000!)")
        print("[UI] Set USE_PYTHON_WEBVIEW=1 to use pywebview instead")
        
        try:
            webbrowser.open(url)
            print("[UI] Browser launched successfully")
        except Exception as e:
            print(f"[UI] Error launching browser: {e}")
            print(f"[UI] Please manually open {url} in your browser")
        
        # For subprocess mode, we need to wait/block instead of returning immediately
        # Otherwise the subprocess exits and triggers shutdown
        if is_subprocess:
            print("[UI] Browser mode: keeping subprocess alive, close server with Ctrl+C")
            # Wait for shutdown signal instead of exiting
            while not shutdown_event.is_set():
                time.sleep(1)
            print("[UI] Browser mode: shutdown event received, subprocess exiting")
        return
    
    # pywebview path (when USE_PYTHON_WEBVIEW is enabled)
    try:
        # Check if webview is available
        # pylint: disable=import-outside-toplevel,redefined-outer-name,reimported
        import webview
    except ImportError:
        print("[UI] ERROR: pywebview is not installed!")
        print("[UI] Install it with: pip install pywebview")
        print(f"[UI] Falling back to browser mode - open http://localhost:{port} "
              "in your browser")
        import webbrowser
        webbrowser.open(f"http://localhost:{port}")
        return

    # Check if we're in a headless environment
    if os.environ.get('DISPLAY') is None and sys.platform not in ('win32', 'darwin'):
        print("[UI] No display detected (headless environment)")
        print(f"[UI] Open http://localhost:{port} in your browser to access the GUI")
        return

    def shutdown_monitor():
        """Monitor shutdown event and close webview"""
        if not is_subprocess:
            return
            
        while True:
            if shutdown_event.is_set():
                print("Shutdown event detected, closing webview...")
                try:
                    if webview.windows:
                        webview.windows[0].destroy()
                except (AttributeError, RuntimeError) as e:
                    print(f"Error closing webview: {e}")
                break
            time.sleep(0.5)

    # Only start shutdown monitor for subprocesses
    if is_subprocess:
        monitor_thread = threading.Thread(target=shutdown_monitor, daemon=True)
        monitor_thread.start()

    try:
        window = webview.create_window(
            "Daz Overmind GUI",
            f"http://localhost:{port}",
            width=1400,
            height=900,
            min_size=(800, 600),
            on_top=False
        )

        # Set window closing handler for both subprocess and main process
        if window and hasattr(window, 'events'):
            if is_subprocess:
                # For subprocess: simplified handler that just returns True
                def on_subprocess_window_closing():
                    print("\n" + "="*70)
                    print("🔴 WEBVIEW SUBPROCESS WINDOW CLOSING")
                    print("="*70)
                    print("🔄 Subprocess will exit and trigger main process shutdown")
                    return True
                window.events.closing += on_subprocess_window_closing
            else:
                # For main process: full shutdown handler
                window.events.closing += on_window_closing

        print(f"[UI] Starting webview window for http://localhost:{port}")
        webview.start()
        print("[UI] Webview window closed")
    except (ImportError, RuntimeError, OSError) as e:
        print(f"[UI] Error launching webview: {e}")
        print(f"[UI] Open http://localhost:{port} in your browser to access the GUI")
    finally:
        # Only set shutdown event if we're NOT a subprocess
        if not is_subprocess:
            shutdown_event.set()


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------
def main():
    """Main entry point for the application"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--ui", action="store_true", help="UI-only mode")
    parser.add_argument("--no-ui", action="store_true", help="Run server without UI")
    parser.add_argument("--port", type=int, default=None, help="Port (auto-allocated if not specified)")
    
    # Parse known args and collect unknown args to pass to overmind
    args, unknown_args = parser.parse_known_args()
    
    # Store overmind arguments for passthrough
    app.ctx.overmind_args = unknown_args
    
    # ========================================================================
    # CRITICAL PORT ALLOCATION SECTION - DO NOT BREAK THIS
    # ========================================================================
    global ALLOCATED_PORT_DONT_CHANGE
    
    if args.port is None:
        # Dynamically find an available port
        ALLOCATED_PORT_DONT_CHANGE = find_available_port(DEFAULT_PORT_START)
        print(f"🔌 ALLOCATED PORT: {ALLOCATED_PORT_DONT_CHANGE} (dynamically found)")
    else:
        # Use user-specified port
        ALLOCATED_PORT_DONT_CHANGE = args.port
        print(f"🔌 ALLOCATED PORT: {ALLOCATED_PORT_DONT_CHANGE} (user specified)")
    
    # VERIFICATION: Double-check we have the right port
    print(f"🔌 PORT VERIFICATION: ALLOCATED_PORT_DONT_CHANGE = {ALLOCATED_PORT_DONT_CHANGE}")
    
    if unknown_args:
        print(f"Passing additional arguments to overmind: {' '.join(unknown_args)}")

    # Store in app context (runtime variable, not a config file!)
    app.ctx.UI_PORT = ALLOCATED_PORT_DONT_CHANGE
    print(f"🔌 PORT STORED IN APP CONTEXT: {app.ctx.UI_PORT}")

    if args.ui:
        # Running as UI subprocess - MUST use the allocated port
        print(f"🔌 [UI SUBPROCESS] Using ALLOCATED_PORT_DONT_CHANGE = {ALLOCATED_PORT_DONT_CHANGE}")
        launch_ui(ALLOCATED_PORT_DONT_CHANGE, is_subprocess=True)
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

    print(f"Starting Overmind GUI (polling-based) on {HOST}:{ALLOCATED_PORT_DONT_CHANGE}")

    if args.no_ui:
        print(f"UI launch disabled - access the GUI at http://localhost:{ALLOCATED_PORT_DONT_CHANGE}")
        os.environ['NO_UI_LAUNCH'] = '1'
    else:
        print("UI will launch automatically. Use --no-ui to disable.")

    print("Press Ctrl+C to stop")
    
    # ========================================================================
    # FINAL PORT VERIFICATION BEFORE SERVER START
    # ========================================================================
    SERVER_PORT = ALLOCATED_PORT_DONT_CHANGE
    print(f"🔌 FINAL VERIFICATION: Starting server on port {SERVER_PORT}")
    print(f"🔌 FINAL VERIFICATION: UI will connect to port {SERVER_PORT}")
    
    if SERVER_PORT is None:
        raise RuntimeError("CRITICAL BUG: SERVER_PORT is None!")
    
    print(f"🔌 SERVER STARTING ON PORT {SERVER_PORT} (NOT 8000!)")

    try:
        app.run(
            host=HOST,
            port=SERVER_PORT,  # Use the verified allocated port
            debug=True,
            auto_reload=False,
            workers=1,
            access_log=False,
            reload_dir=".",
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
        self.assertEqual(DEFAULT_PORT_START, 8000)
        self.assertEqual(HOST, "127.0.0.1")
        
    def test_port_allocation(self):
        """Test dynamic port allocation"""
        port = find_available_port(DEFAULT_PORT_START)
        self.assertIsInstance(port, int)
        self.assertGreaterEqual(port, DEFAULT_PORT_START)

    def test_app_initialization(self):
        """Test that the Sanic app is properly initialized"""
        self.assertEqual(app.name, "OvermindGUI")
        self.assertFalse(app.config.DEBUG)
        self.assertFalse(app.config.AUTO_RELOAD)
        self.assertEqual(app.config.WORKERS, 1)

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
        sig = inspect.signature(launch_ui)
        params = list(sig.parameters.keys())
        self.assertIn('port', params)
        self.assertIn('is_subprocess', params)

    def test_shutdown_event_initialization(self):
        """Test that shutdown event is properly initialized"""
        self.assertIsInstance(shutdown_event, asyncio.Event)

    def test_callback_functions_exist(self):
        """Test that callback functions exist and are callable"""
        self.assertTrue(callable(handle_output_line))
        self.assertTrue(callable(handle_status_update))


if __name__ == "__main__":
    main()
