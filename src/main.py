#!/usr/bin/env python3
"""
Overmind GUI - Daemon - based web interface for Overmind process management

A modern, daemon - based web interface for managing Overmind processes with:
- Connection to independent overmind daemon
- Live process monitoring and control via polling
- Real - time output streaming with 4x/sec updates
- Advanced filtering and search
- Modern CSS - based UI with 5000 line limit
- Automatic daemon discovery and connection management
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
from daemon_manager import DaemonManager
from native_daemon_manager import NativeDaemonManager
from database_client import DatabaseClient
from static_files import setup_static_routes
from api_routes_daemon import setup_api_routes, handle_output_line, handle_status_update

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

# Global working directory - set in main() and accessed by background tasks
WORKING_DIRECTORY = None

# -----------------------------------------------------------------------------
# Port management
# -----------------------------------------------------------------------------


def find_available_port(start_port=DEFAULT_PORT_START, max_attempts=100):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", port))
                return port
        except OSError:
            continue
    raise RuntimeError(f"No available ports found in range {start_port}-{start_port + max_attempts}")


# -----------------------------------------------------------------------------
# Version management
# -----------------------------------------------------------------------------


def get_and_increment_version():
    """Read current version, increment it, and return the new version"""
    # Get version file in the parent directory (root)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)
    version_file = os.path.join(root_dir, "version.txt")

    try:
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                current_version = int(f.read().strip())
        else:
            current_version = 0

        new_version = current_version + 1
        with open(version_file, "w") as f:
            f.write(str(new_version))

        return new_version
    except (ValueError, IOError) as e:
        print(f"Error managing version: {e}")
        return 1


# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------


app = Sanic("OvermindGUIDaemon")
app.config.DEBUG = False  # Disable debug spam
app.config.AUTO_RELOAD = False
app.config.WORKERS = 1
# UI_PORT will be stored in app.ctx at runtime - NO CONFIG FILES!

# Get version and store in app context
app.ctx.version = get_and_increment_version()
print(f"Starting Overmind GUI (Daemon Mode) v{app.ctx.version}")

# Initialize managers - simplified database - based architecture
# Note: ProcessManager will be re-initialized with working_directory in initialize_managers()
app.ctx.process_manager = ProcessManager()
app.ctx.daemon_manager = None  # Will be set when we know working directory
app.ctx.database_client = None  # Will be set when we know working directory
app.ctx.daemon_failed = False
app.ctx.daemon_error = ""
app.ctx.tasks = []
app.ctx.shutdown_initiated = False
app.ctx.shutdown_complete = False
app.ctx.last_poll_id = 0  # Track last database ID for incremental polling

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

        # Message 1: UI closed → Stop daemon
        print("📨 [MESSAGE 1] UI closed → Stopping daemon...")
        if app_instance.ctx.daemon_manager:
            print("📦 Stopping daemon via daemon manager...")
            try:
                success = app_instance.ctx.daemon_manager.stop_daemon()
                if success:
                    print("✅ [MESSAGE 1] Daemon stopped completely")
                else:
                    print("⚠️ [MESSAGE 1] Daemon stop reported failure")
            except Exception as e:
                print(f"❌ [MESSAGE 1] Error stopping daemon: {e}")
                import traceback

                traceback.print_exc()
        else:
            print("ℹ️  [MESSAGE 1] No daemon manager available")

        print("📨 [MESSAGE 1] ✅ COMPLETE - Daemon shutdown finished")

        # Message 2: Daemon stopped → Stop Sanic
        print("\n📨 [MESSAGE 2] Daemon stopped → Stopping Sanic server...")
        try:
            # Instead of calling app_instance.stop() directly, we need to signal the server
            # to stop from outside the current async context to avoid deadlock
            import os
            import signal

            # Get the current process ID and send SIGINT to trigger graceful shutdown
            current_pid = os.getpid()
            print(f"📤 [MESSAGE 2] Sending SIGINT to main process PID {current_pid}")
            os.kill(current_pid, signal.SIGINT)
            print("✅ [MESSAGE 2] Sanic server shutdown signal sent")
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

        # Emergency: try to stop server anyway
        try:
            app_instance.stop()
        except Exception:
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
        # Set shutdown flags first
        request.app.ctx.shutdown_initiated = True
        shutdown_event.set()

        # Schedule graceful shutdown with delay to allow cleanup
        async def graceful_shutdown():
            print("🛑 Graceful shutdown initiated...")

            # Stop daemon client first if it's running
            if request.app.ctx.daemon_client:
                print("🛑 Stopping daemon client...")
                try:
                    await request.app.ctx.daemon_client.stop()
                    print("✅ Daemon client stopped")
                except Exception as e:
                    print(f"❌ Error stopping daemon client: {e}")
                finally:
                    request.app.ctx.daemon_client = None

            # Stop discovery manager
            if request.app.ctx.daemon_discovery:
                print("🛑 Stopping daemon discovery...")
                try:
                    await request.app.ctx.daemon_discovery.cleanup_connections()
                    print("✅ Daemon discovery stopped")
                except Exception as e:
                    print(f"❌ Error stopping daemon discovery: {e}")

            # Cancel background tasks cleanly
            if request.app.ctx.tasks:
                print("🛑 Cancelling background tasks...")

                # First cancel all tasks
                for task in request.app.ctx.tasks:
                    if not task.done():
                        task.cancel()

                # Then wait for all cancellations to complete
                if request.app.ctx.tasks:
                    try:
                        await asyncio.gather(*request.app.ctx.tasks, return_exceptions=True)
                    except Exception:
                        pass  # Cancellations can raise exceptions, that's expected

                request.app.ctx.tasks.clear()
                print("✅ Background tasks cleaned up")

            # Mark cleanup as complete
            request.app.ctx.shutdown_complete = True

            # Now stop the server
            print("🛑 Stopping Sanic server...")
            request.app.stop()

        request.app.add_task(graceful_shutdown())
        return response.json({"success": True, "message": "Server shutdown initiated"})
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


# -----------------------------------------------------------------------------
# Database polling helpers
# -----------------------------------------------------------------------------


def initialize_managers(app_instance, working_directory: str, use_overmind: bool = False):
    """Initialize daemon and database managers once we know working directory"""
    # Choose daemon manager based on mode
    if use_overmind:
        print("=" * 70)
        print("📦 DAEMON MODE: OVERMIND (legacy mode with tmux)")
        print("=" * 70)
        app_instance.ctx.daemon_manager = DaemonManager(working_directory)
        app_instance.ctx.daemon_mode = "overmind"
        app_instance.ctx.daemon_cli = "overmind"  # CLI command for process control
    else:
        print("=" * 70)
        print("🚀 DAEMON MODE: NATIVE (direct process management, no tmux)")
        print("=" * 70)
        app_instance.ctx.daemon_manager = NativeDaemonManager(working_directory)
        app_instance.ctx.daemon_mode = "native"
        # Store path to native_ctl for CLI commands
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_instance.ctx.daemon_cli = os.path.join(script_dir, "native_ctl.py")

    app_instance.ctx.database_client = DatabaseClient(working_directory)

    # Re-initialize process manager with working directory
    app_instance.ctx.process_manager = ProcessManager(working_directory)

    # Load processes from Procfile - this should never return 0 processes!
    procfile_path = os.path.join(working_directory, "Procfile")
    process_names = app_instance.ctx.process_manager.load_procfile(procfile_path)

    print(f"📋 Loaded {len(process_names)} processes from Procfile: {process_names}")

    # For native daemon, set all processes to "running" initially
    # (native daemon starts all processes on launch)
    if not use_overmind:
        for process_name in process_names:
            app_instance.ctx.process_manager.update_process_status(process_name, "running")

    print(f"✅ Initialized managers for directory: {working_directory}")


# -----------------------------------------------------------------------------
# Background tasks
# -----------------------------------------------------------------------------


async def poll_overmind_status(app_instance):
    """Poll overmind status and update process manager (only for overmind mode)"""
    try:
        # Skip status polling if using native daemon (status comes through /api/poll)
        daemon_mode = getattr(app_instance.ctx, "daemon_mode", "overmind")
        if daemon_mode == "native":
            return  # Native daemon status is handled via API polling, not overmind ps

        import subprocess

        working_dir = getattr(app_instance.ctx, "working_directory", os.getcwd())

        # Run overmind status
        result = subprocess.run(["overmind", "status"], cwd=working_dir, capture_output=True, text=True, timeout=5)

        if result.returncode == 0:
            # Parse overmind status output
            lines = result.stdout.strip().split("\n")
            status_updates = {}

            # Skip header line if present
            data_lines = [line for line in lines if line.strip() and not line.startswith("PROCESS")]

            for line in data_lines:
                # Split by whitespace - format: PROCESS    PID    STATUS
                parts = line.split()
                if len(parts) >= 3:
                    process_name = parts[0].strip()
                    # pid = parts[1].strip()  # Not needed for status updates
                    status = parts[2].strip()

                    # Update process manager
                    if process_name in app_instance.ctx.process_manager.processes:
                        app_instance.ctx.process_manager.update_process_status(process_name, status)
                        status_updates[process_name] = status

    except subprocess.TimeoutExpired:
        pass  # Silent timeout
    except FileNotFoundError:
        pass  # Overmind not available
    except Exception:
        pass  # Silent error handling


async def status_polling_task(app_instance):
    """Background task to poll overmind status every second"""
    try:
        # Do initial status poll immediately
        await poll_overmind_status(app_instance)

        while app_instance.ctx.running:
            try:
                # Poll every second
                await asyncio.sleep(1.0)
                await poll_overmind_status(app_instance)
            except Exception as e:
                print(f"⚠️ Error in status polling cycle: {e}")
                await asyncio.sleep(5.0)  # Wait longer on error

    except asyncio.CancelledError:
        print("🛑 Status polling task cancelled")
    except Exception as e:
        print(f"❌ Status polling task failed: {e}")
    finally:
        print("🏁 Status polling task completed")


async def daemon_management_task(app_instance, working_directory: str):
    """Manage daemon lifecycle and database polling"""
    try:
        print("🔄 Starting daemon management task")

        # Use the passed working directory
        working_dir = working_directory
        print(f"📁 Working directory: {working_dir}")

        # Store working directory in context for other functions
        app_instance.ctx.working_directory = working_dir

        # Get daemon mode from app context (set in main())
        use_overmind = getattr(app_instance.ctx, "use_overmind", False)

        # Initialize managers
        initialize_managers(app_instance, working_dir, use_overmind)

        # Ensure daemon is running
        print("🔄 Ensuring daemon is running...")
        if app_instance.ctx.daemon_manager.is_daemon_running():
            daemon_pid = app_instance.ctx.daemon_manager.get_daemon_pid()
            if daemon_pid:
                print(f"✅ Found daemon as process {daemon_pid}")
                app_instance.ctx.daemon_pid = daemon_pid  # Store for monitoring
            else:
                print("✅ Found daemon running")
        else:
            daemon_started = app_instance.ctx.daemon_manager.start_daemon()
            if not daemon_started:
                print("❌ Failed to start daemon")
                app_instance.ctx.daemon_failed = True
                app_instance.ctx.daemon_error = "Failed to start daemon"
                return

            daemon_pid = app_instance.ctx.daemon_manager.get_daemon_pid()
            if daemon_pid:
                print(f"✅ Started daemon as process {daemon_pid}")
                app_instance.ctx.daemon_pid = daemon_pid  # Store for monitoring
            else:
                print("✅ Daemon started")

        # Initialize polling with first load (limited per process)
        print("🔄 Loading initial data...")
        initial_lines = app_instance.ctx.database_client.get_output_lines(since_id=0, limit=5000)
        if initial_lines:
            app_instance.ctx.last_poll_id = max(line["id"] for line in initial_lines)
            print(f"📊 Initial load: {len(initial_lines)} lines, latest ID: {app_instance.ctx.last_poll_id}")

            # Process for local tracking (but DON'T check for failures in historical lines)
            # Historical lines are before current process state, so we skip failure detection
            for line in initial_lines:
                app_instance.ctx.process_manager.add_output_line(line["html"])

        # Start database polling loop and status monitoring
        print("🔄 Starting database polling loop...")

        while not app_instance.ctx.shutdown_initiated and app_instance.ctx.running:
            try:
                # Check if daemon is still running - but DON'T restart it
                # The daemon should only be started once at startup
                if not app_instance.ctx.daemon_manager.is_daemon_running():
                    print("⚠️ Daemon has exited unexpectedly - initiating shutdown")
                    app_instance.ctx.daemon_failed = True

                    # Daemon died, so we should shut down the entire backend
                    shutdown_event.set()
                    app_instance.ctx.shutdown_initiated = True
                    app_instance.stop()
                    break

                # Poll database for new lines (incremental)
                new_lines = app_instance.ctx.database_client.get_output_lines(
                    since_id=app_instance.ctx.last_poll_id,
                    limit=1000,  # Reasonable batch size for incremental updates
                )

                if new_lines:
                    # Update last poll ID
                    app_instance.ctx.last_poll_id = max(line["id"] for line in new_lines)

                    # Process lines for local tracking and failure detection
                    for line in new_lines:
                        process_name, failure_pattern = app_instance.ctx.process_manager.add_output_line(line["html"])

                        # Check if a failure pattern was detected
                        if failure_pattern and process_name:
                            # Import kill function from api_routes_daemon
                            from api_routes_daemon import kill_process_on_failure

                            # Schedule process kill
                            loop.create_task(kill_process_on_failure(app_instance, process_name, failure_pattern))

                # Poll every 250ms for good responsiveness
                await asyncio.sleep(0.25)

            except Exception as e:
                print(f"⚠️ Error in polling loop: {e}")
                await asyncio.sleep(1)  # Wait a bit before retrying

        print("🔄 Daemon management task ending due to shutdown")

    except asyncio.CancelledError:
        print("🛑 [DAEMON MANAGEMENT] Task was cancelled - shutdown in progress")
    except Exception as e:
        print(f"❌ [DAEMON MANAGEMENT] Error: {e}")
        import traceback

        traceback.print_exc()
        app_instance.ctx.daemon_failed = True
        app_instance.ctx.daemon_error = str(e)
    finally:
        print("🏁 [DAEMON MANAGEMENT] Daemon management task completed")


async def daemon_monitor_task(app_instance):
    """Monitor daemon process and trigger GUI shutdown when daemon exits"""
    try:
        print("👁️ [DAEMON MONITOR] Started monitoring daemon process")

        # Wait for daemon PID to be set
        while not hasattr(app_instance.ctx, "daemon_pid") or app_instance.ctx.daemon_pid is None:
            await asyncio.sleep(1)
            if shutdown_event.is_set() or app_instance.ctx.shutdown_initiated:
                return

        daemon_pid = app_instance.ctx.daemon_pid
        print(f"👁️ [DAEMON MONITOR] Monitoring daemon PID: {daemon_pid}")

        # Monitor daemon process
        import psutil

        while not shutdown_event.is_set() and app_instance.ctx.running:
            try:
                # Check if daemon process exists AND is not a zombie
                daemon_alive = False
                try:
                    proc = psutil.Process(daemon_pid)
                    # Check if it's a zombie
                    if proc.status() == psutil.STATUS_ZOMBIE:
                        print(f"⚠️ [DAEMON MONITOR] Daemon PID {daemon_pid} is a zombie process!")
                    else:
                        daemon_alive = True
                except psutil.NoSuchProcess:
                    print(f"⚠️ [DAEMON MONITOR] Daemon process {daemon_pid} no longer exists!")

                if not daemon_alive:
                    print("🛑 [DAEMON MONITOR] Initiating GUI shutdown...")

                    # Set shutdown flag
                    shutdown_event.set()
                    app_instance.ctx.shutdown_initiated = True

                    # Trigger graceful shutdown
                    print("🛑 [DAEMON MONITOR] Stopping server...")
                    app_instance.stop()
                    break

                # Check every second
                await asyncio.sleep(1)

            except Exception as e:
                print(f"⚠️ [DAEMON MONITOR] Error checking daemon: {e}")
                await asyncio.sleep(1)

        print("🏁 [DAEMON MONITOR] Monitoring task completed")

    except asyncio.CancelledError:
        print("🛑 [DAEMON MONITOR] Task was cancelled")
    except Exception as e:
        print(f"❌ [DAEMON MONITOR] Error: {e}")
        import traceback

        traceback.print_exc()


async def ui_launcher_task(app_instance):
    """Launch the UI subprocess"""
    proc = None
    try:
        # ====================================================================
        # CRITICAL: Port must match ALLOCATED_PORT_DONT_CHANGE
        # ====================================================================
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
        if os.environ.get("NO_UI_LAUNCH", "").lower() in ("1", "true", "yes"):
            print("[UI] UI launch disabled by NO_UI_LAUNCH environment variable")
            return

        # CRITICAL: Pass THE_CORRECT_PORT to prevent any hardcoded 8000 issues
        subprocess_args = [
            sys.executable,
            __file__,
            "--ui",
            "--port",
            str(THE_CORRECT_PORT),  # This MUST be the same as the main server port
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
                print("\n" + "=" * 70)
                print("🔴 UI SUBPROCESS EXITED - STARTING SHUTDOWN MESSAGE CHAIN")
                print("=" * 70)

                # Step 1: Set flags and start daemon client shutdown
                print("📨 [MESSAGE 1] UI closed → Starting daemon client shutdown...")
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
            print("✅ [UI LAUNCHER] UI subprocess terminated")
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
    print("\n" + "=" * 70)
    print("🔴 WEBVIEW WINDOW CLOSING - SHUTDOWN SEQUENCE INITIATED")
    print("=" * 70)

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

    # Backend startup - daemon handles startup messages

    # Start daemon management task (replaces daemon client)
    # Get working directory from environment variable (set by main())
    working_dir = os.environ.get("OVERMIND_GUI_WORKING_DIR", os.getcwd())
    t1 = loop.create_task(daemon_management_task(app_instance, working_dir))

    # Start UI launcher task
    t2 = loop.create_task(ui_launcher_task(app_instance))

    # Start backend status polling task (this polls overmind status, not the daemon)
    t3 = loop.create_task(status_polling_task(app_instance))

    # Start daemon monitor task to watch for daemon exit
    t4 = loop.create_task(daemon_monitor_task(app_instance))

    app_instance.ctx.tasks.extend([t1, t2, t3, t4])


@app.listener("after_server_start")
async def auto_launch_macos_app(_app, _loop):
    await asyncio.sleep(0.2)  # tiny grace so routes are live
    # Try ~/Applications first, then /Applications as secondary location
    home_app_path = os.path.expanduser("~/Applications/Overmind.app")
    system_app_path = "/Applications/Overmind.app"

    if os.path.exists(home_app_path):
        subprocess.Popen(["open", home_app_path])
    elif os.path.exists(system_app_path):
        subprocess.Popen(["open", system_app_path])
    else:
        print(f"⚠️ Overmind.app not found in {home_app_path} or {system_app_path}")


@app.before_server_stop
async def cleanup(app_instance, _loop):
    """Final cleanup - should be minimal since main cleanup happens in shutdown endpoint"""
    if app_instance.ctx.shutdown_complete:
        print("✅ Clean shutdown - all resources already cleaned up")
        return

    print("\n⚠️  [EMERGENCY CLEANUP] Cleanup not completed by shutdown endpoint")
    print("🧹 Performing minimal emergency cleanup...")

    # Only do essential cleanup that must complete
    app_instance.ctx.running = False
    app_instance.ctx.shutdown_complete = True

    print("✅ Emergency cleanup completed")


# -----------------------------------------------------------------------------
# UI - only launcher
# -----------------------------------------------------------------------------


def launch_ui(port: int, is_subprocess: bool = False):
    """Launch the desktop UI - uses system browser by default, pywebview if USE_PYTHON_WEBVIEW is set

    CRITICAL: This function MUST receive the correct dynamically allocated port.
    DO NOT hardcode port 8000 anywhere in this function or its callees.
    """
    print(f"[UI] launch_ui called with port={port}, is_subprocess={is_subprocess}")

    # Check if pywebview should be used (when USE_PYTHON_WEBVIEW is set)
    use_webview = os.environ.get("USE_PYTHON_WEBVIEW", "").lower() in ("1", "true", "yes")

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
        # pylint: disable=import - outside - toplevel,redefined - outer - name,reimported
        import webview
    except ImportError:
        print("[UI] ERROR: pywebview is not installed!")
        print("[UI] Install it with: pip install pywebview")
        print(f"[UI] Falling back to browser mode - open http://localhost:{port} in your browser")
        import webbrowser

        webbrowser.open(f"http://localhost:{port}")
        return

    # Check if we're in a headless environment
    if os.environ.get("DISPLAY") is None and sys.platform not in ("win32", "darwin"):
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
            "Daz Overmind GUI (Daemon Mode)",
            f"http://localhost:{port}",
            width=1400,
            height=900,
            min_size=(800, 600),
            on_top=False,
        )

        # Set window closing handler for both subprocess and main process
        if window and hasattr(window, "events"):
            if is_subprocess:
                # For subprocess: simplified handler that just returns True
                def on_subprocess_window_closing():
                    print("\n" + "=" * 70)
                    print("🔴 WEBVIEW SUBPROCESS WINDOW CLOSING")
                    print("=" * 70)
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
    parser.add_argument("--ui", action="store_true", help="UI - only mode")
    parser.add_argument("--no-ui", action="store_true", help="Run server without UI")
    parser.add_argument("--port", type=int, default=None, help="Port (auto - allocated if not specified)")
    parser.add_argument(
        "--working-dir", type=str, default=None, help="Working directory (defaults to current directory)"
    )
    parser.add_argument(
        "--overmind",
        action="store_true",
        help="Use overmind daemon (legacy mode with tmux). Default is native daemon (direct process management)."
    )

    # Parse known args - we don't pass args to daemon since daemon is independent
    args, unknown_args = parser.parse_known_args()

    if unknown_args:
        print(f"Warning: Unknown arguments ignored in daemon mode: {' '.join(unknown_args)}")
        print("Arguments are passed directly to the daemon, not the GUI")

    # ========================================================================
    # CRITICAL PORT ALLOCATION SECTION - DO NOT BREAK THIS
    # ========================================================================
    global ALLOCATED_PORT_DONT_CHANGE

    if args.port is None:
        # Dynamically find an available port
        ALLOCATED_PORT_DONT_CHANGE = find_available_port(DEFAULT_PORT_START)
        print(f"🔌 ALLOCATED PORT: {ALLOCATED_PORT_DONT_CHANGE} (dynamically found)")
    else:
        # Use user - specified port
        ALLOCATED_PORT_DONT_CHANGE = args.port
        print(f"🔌 ALLOCATED PORT: {ALLOCATED_PORT_DONT_CHANGE} (user specified)")

    # VERIFICATION: Double - check we have the right port
    print(f"🔌 PORT VERIFICATION: ALLOCATED_PORT_DONT_CHANGE = {ALLOCATED_PORT_DONT_CHANGE}")

    # Store in app context (runtime variable, not a config file!)
    app.ctx.UI_PORT = ALLOCATED_PORT_DONT_CHANGE
    print(f"🔌 PORT STORED IN APP CONTEXT: {app.ctx.UI_PORT}")

    # Store working directory in environment variable so worker process can access it
    working_dir = args.working_dir if args.working_dir else os.getcwd()
    working_dir = os.path.abspath(working_dir)

    # Set environment variable for worker process
    os.environ["OVERMIND_GUI_WORKING_DIR"] = working_dir
    app.ctx.working_directory = working_dir

    # Store daemon mode flag
    app.ctx.use_overmind = args.overmind

    print(f"📁 WORKING DIRECTORY STORED: {working_dir}")
    if args.overmind:
        print("📦 DAEMON MODE: overmind (legacy)")
    else:
        print("🚀 DAEMON MODE: native (default)")

    if args.ui:
        # Running as UI subprocess - MUST use the allocated port
        print(f"🔌 [UI SUBPROCESS] Using ALLOCATED_PORT_DONT_CHANGE = {ALLOCATED_PORT_DONT_CHANGE}")
        launch_ui(ALLOCATED_PORT_DONT_CHANGE, is_subprocess=True)
        return 0

    print(f"Starting Overmind GUI (daemon - based) on {HOST}:{ALLOCATED_PORT_DONT_CHANGE}")
    print("This GUI connects to an independent overmind daemon.")
    print("Make sure you have started an overmind daemon first with:")
    print("  python overmind_daemon.py")

    if args.no_ui:
        print(f"UI launch disabled - access the GUI at http://localhost:{ALLOCATED_PORT_DONT_CHANGE}")
        os.environ["NO_UI_LAUNCH"] = "1"
    else:
        print("UI will launch automatically. Use --no - ui to disable.")

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
            debug=False,  # No debug spam
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


class TestOvermindGuiDaemon(unittest.TestCase):
    """Test cases for the Overmind GUI Daemon application"""

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
        self.assertEqual(app.name, "OvermindGUIDaemon")
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
        self.assertIn("port", params)
        self.assertIn("is_subprocess", params)

    def test_shutdown_event_initialization(self):
        """Test that shutdown event is properly initialized"""
        self.assertIsInstance(shutdown_event, asyncio.Event)

    def test_callback_functions_exist(self):
        """Test that callback functions exist and are callable"""
        self.assertTrue(callable(handle_output_line))
        self.assertTrue(callable(handle_status_update))


if __name__ == "__main__":
    main()
