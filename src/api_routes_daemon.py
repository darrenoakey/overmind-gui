"""
API Routes (Database Mode) - Direct database polling endpoints
Provides endpoints for process management and polling updates using direct database access
"""

import asyncio
import os
import time
import unittest


from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse

from update_queue import update_queue

# Create API blueprint
api_bp = Blueprint("api", url_prefix="/api")


@api_bp.route("/state", methods=["GET"])
async def get_current_state(request: Request) -> HTTPResponse:
    """Get complete current state for initial page load"""
    try:
        state = update_queue.get_current_state()

        # Get processes from process manager (local state)
        if hasattr(request.app.ctx, "process_manager"):
            processes = request.app.ctx.process_manager.get_all_processes()
            state["processes"] = {name: proc.to_dict() for name, proc in processes.items()}

            # Calculate stats from processes
            stats = request.app.ctx.process_manager.get_stats()
            state["stats"] = stats
        else:
            state["stats"] = {}
            state["processes"] = {}

        # Add daemon status instead of overmind status
        daemon_status = "unknown"
        if hasattr(request.app.ctx, "daemon_manager") and request.app.ctx.daemon_manager:
            if request.app.ctx.daemon_manager.is_daemon_running():
                daemon_status = "running"
            else:
                daemon_status = "stopped"

        state["overmind_status"] = daemon_status  # Keep same key for UI compatibility
        state["daemon_status"] = daemon_status  # Also provide daemon-specific key
        state["version"] = getattr(request.app.ctx, "version", 1)

        # Add database stats if available
        if hasattr(request.app.ctx, "database_client") and request.app.ctx.database_client:
            try:
                process_stats = request.app.ctx.database_client.get_process_stats()
                state["queue_stats"] = {
                    "total_processes": len(process_stats),
                    "total_lines": sum(stats["line_count"] for stats in process_stats.values()),
                    "processes": process_stats,
                }
            except Exception as e:
                print(f"Error getting database stats: {e}")
                state["queue_stats"] = {}

        return response.json(state)

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/processes", methods=["GET"])
async def get_processes(request: Request) -> HTTPResponse:
    """Get processes from process manager"""
    try:
        if hasattr(request.app.ctx, "process_manager"):
            processes = request.app.ctx.process_manager.get_all_processes()
            process_data = {name: proc.to_dict() for name, proc in processes.items()}
            return response.json({"processes": process_data}, status=200)
        else:
            return response.json({"error": "Process manager not available", "processes": {}}, status=503)
    except Exception as e:
        error_msg = f"Error getting processes: {e}"
        print(f"❌ [API] {error_msg}")
        return response.json({"error": error_msg, "processes": {}}, status=500)


@api_bp.route("/poll", methods=["GET"])
async def poll_updates(request: Request) -> HTTPResponse:
    """Poll for updates since last message ID - proxy to daemon"""
    try:
        # Get last message ID from query parameter
        last_id_str = request.args.get("last_message_id", "0")

        try:
            last_message_id = int(last_id_str)
        except (ValueError, TypeError):
            return response.json({"error": "Invalid last_message_id - must be integer"}, status=400)

        if last_message_id < 0:
            return response.json({"error": "last_message_id must be >= 0"}, status=400)

        # Use direct database polling (new architecture)
        try:
            # Get database client
            if not hasattr(request.app.ctx, "database_client") or not request.app.ctx.database_client:
                return response.json({"error": "Database client not available"}, status=503)

            db_client = request.app.ctx.database_client

            # Get new output lines since last message ID
            new_lines = db_client.get_output_lines(since_id=last_message_id, limit=100)

            # Get process stats and status updates
            stats = {}
            status_updates = {}
            if hasattr(request.app.ctx, "process_manager"):
                stats = request.app.ctx.process_manager.get_stats()

                # For native mode, get status from database (daemon writes it there)
                # For overmind mode, use local process manager (updated via poll_overmind_status)
                daemon_mode = getattr(request.app.ctx, "daemon_mode", "overmind")
                if daemon_mode == "native":
                    # Get status from database
                    db_status = db_client.get_process_status_updates()
                    if db_status:
                        status_updates = db_status
                        # Also update local process manager for consistency
                        for name, status in db_status.items():
                            request.app.ctx.process_manager.update_process_status(name, status)
                    else:
                        # Fallback to local process manager
                        processes = request.app.ctx.process_manager.get_all_processes()
                        status_updates = {name: proc.status for name, proc in processes.items()}
                else:
                    # Overmind mode - use local process manager
                    processes = request.app.ctx.process_manager.get_all_processes()
                    status_updates = {name: proc.status for name, proc in processes.items()}

            # Format response to match frontend expectations
            response_data = {
                "output_lines": new_lines,
                "stats": stats,
                "status_updates": status_updates,
                "last_id": max([line["id"] for line in new_lines]) if new_lines else last_message_id,
            }

            return response.json(response_data)

        except Exception as e:
            return response.json({"error": f"Failed to poll database: {e}"}, status=500)

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


async def _execute_daemon_command(request: Request, command: str, process_name: str) -> tuple:
    """
    Execute a daemon command (start/stop/restart) using the appropriate CLI
    Returns: (success: bool, message: str)
    """
    import asyncio
    import os
    import sys

    working_dir = getattr(request.app.ctx, "working_directory", os.getcwd())
    daemon_cli = getattr(request.app.ctx, "daemon_cli", "overmind")
    daemon_mode = getattr(request.app.ctx, "daemon_mode", "overmind")

    # Build CLI command
    if daemon_mode == "native":
        # native_ctl.py requires python interpreter
        cli_cmd = [sys.executable, daemon_cli, "--working-dir", working_dir, command, process_name]
    else:
        # overmind is a standalone binary
        cli_cmd = [daemon_cli, command, process_name]

    # Execute
    process = await asyncio.create_subprocess_exec(
        *cli_cmd,
        cwd=working_dir,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.wait()

    success = process.returncode == 0
    stderr = (await process.stderr.read()).decode() if process.stderr else ""

    return success, stderr


@api_bp.route("/process/<process_name>/start", methods=["POST"])
async def start_process(request: Request, process_name: str) -> HTTPResponse:
    """Start a specific process"""
    try:
        success, stderr = await _execute_daemon_command(request, "start", process_name)

        if success:
            if hasattr(request.app.ctx, "process_manager"):
                request.app.ctx.process_manager.update_process_status(process_name, "running")
            return response.json({"success": True, "message": f"Started {process_name}"})
        else:
            return response.json({"success": False, "error": f"Failed to start {process_name}: {stderr}"})

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/process/<process_name>/stop", methods=["POST"])
async def stop_process(request: Request, process_name: str) -> HTTPResponse:
    """Stop a specific process"""
    try:
        success, stderr = await _execute_daemon_command(request, "stop", process_name)

        if success:
            if hasattr(request.app.ctx, "process_manager"):
                request.app.ctx.process_manager.update_process_status(process_name, "stopped")
            return response.json({"success": True, "message": f"Stopped {process_name}"})
        else:
            return response.json({"success": False, "error": f"Failed to stop {process_name}: {stderr}"})

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/process/<process_name>/restart", methods=["POST"])
async def restart_process(request: Request, process_name: str) -> HTTPResponse:
    """Restart a specific process"""
    try:
        success, stderr = await _execute_daemon_command(request, "restart", process_name)

        if success:
            if hasattr(request.app.ctx, "process_manager"):
                request.app.ctx.process_manager.restart_process(process_name)
            return response.json({"success": True, "message": f"Restarted {process_name}"})
        else:
            return response.json({"success": False, "error": f"Failed to restart {process_name}: {stderr}"})

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/process/<process_name>/toggle", methods=["POST"])
async def toggle_process_selection(request: Request, process_name: str) -> HTTPResponse:
    """Toggle process selection for output display"""
    try:
        if not hasattr(request.app.ctx, "process_manager"):
            return response.json({"error": "Process manager not available"}, status=503)

        new_state = request.app.ctx.process_manager.toggle_process_selection(process_name)

        return response.json({"success": True, "process": process_name, "selected": new_state})

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/processes/select-all", methods=["POST"])
async def select_all_processes(request: Request) -> HTTPResponse:
    """Select all processes for output display"""
    try:
        if not hasattr(request.app.ctx, "process_manager"):
            return response.json({"error": "Process manager not available"}, status=503)

        request.app.ctx.process_manager.select_all_processes()

        # Return updated process list
        processes = request.app.ctx.process_manager.get_all_processes()
        process_data = {name: proc.to_dict() for name, proc in processes.items()}

        return response.json({"success": True, "message": "All processes selected", "processes": process_data})

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/processes/deselect-all", methods=["POST"])
async def deselect_all_processes(request: Request) -> HTTPResponse:
    """Deselect all processes from output display"""
    try:
        if not hasattr(request.app.ctx, "process_manager"):
            return response.json({"error": "Process manager not available"}, status=503)

        request.app.ctx.process_manager.deselect_all_processes()

        # Return updated process list
        processes = request.app.ctx.process_manager.get_all_processes()
        process_data = {name: proc.to_dict() for name, proc in processes.items()}

        return response.json({"success": True, "message": "All processes deselected", "processes": process_data})

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/output/clear", methods=["POST"])
async def clear_output(request: Request) -> HTTPResponse:
    """Clear all output lines"""
    try:
        update_queue.clear_all()

        # Also clear process manager output if available
        if hasattr(request.app.ctx, "process_manager"):
            request.app.ctx.process_manager.clear_all_output()

        return response.json(
            {"success": True, "message": "Output cleared", "latest_message_id": update_queue.message_counter}
        )

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/status", methods=["GET"])
async def get_status(request: Request) -> HTTPResponse:
    """Get daemon and system status"""
    try:
        status_info = {
            "overmind_running": False,
            "daemon_running": False,
            "process_count": 0,
            "line_count": 0,
            "uptime": 0,
            "latest_message_id": update_queue.message_counter,
        }

        if hasattr(request.app.ctx, "daemon_client") and request.app.ctx.daemon_client:
            daemon_running = request.app.ctx.daemon_client.is_running()
            status_info["daemon_running"] = daemon_running
            status_info["overmind_running"] = daemon_running  # For UI compatibility

        if hasattr(request.app.ctx, "process_manager"):
            stats = request.app.ctx.process_manager.get_stats()
            status_info["process_count"] = stats.get("total", 0)

        # Add queue stats
        queue_stats = update_queue.get_stats()
        status_info["message_count"] = queue_stats["total_messages"]
        status_info["line_count"] = queue_stats["total_lines"]

        return response.json(status_info)

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/daemon/info", methods=["GET"])
async def get_daemon_info(request: Request) -> HTTPResponse:
    """Get daemon connection info"""
    try:
        daemon_info = {
            "connected": False,
            "daemon_id": None,
            "host": None,
            "port": None,
            "connection_status": "disconnected",
        }

        if hasattr(request.app.ctx, "daemon_client") and request.app.ctx.daemon_client:
            daemon_info.update(
                {
                    "connected": request.app.ctx.daemon_client.is_running(),
                    "host": request.app.ctx.daemon_client.daemon_host,
                    "port": request.app.ctx.daemon_client.daemon_port,
                    "connection_status": "connected" if request.app.ctx.daemon_client.is_running() else "disconnected",
                }
            )

        if hasattr(request.app.ctx, "daemon_discovery") and request.app.ctx.daemon_discovery:
            connection_status = request.app.ctx.daemon_discovery.get_connection_status()
            daemon_info["all_connections"] = connection_status

        return response.json(daemon_info)

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/daemon/discover", methods=["POST"])
async def discover_daemons(request: Request) -> HTTPResponse:
    """Trigger daemon discovery and return found daemons"""
    try:
        if not hasattr(request.app.ctx, "daemon_discovery") or not request.app.ctx.daemon_discovery:
            return response.json({"error": "Daemon discovery not available"}, status=503)

        # Get port range from request body if provided
        request_data = request.json or {}
        port_range = request_data.get("port_range", (9000, 9100))

        discovered = await request.app.ctx.daemon_discovery.discover_daemons(port_range)

        return response.json({"success": True, "discovered_count": len(discovered), "daemons": discovered})

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/daemon/reconnect", methods=["POST"])
async def reconnect_daemon(request: Request) -> HTTPResponse:
    """Reconnect to best available daemon"""
    try:
        if not hasattr(request.app.ctx, "daemon_discovery") or not request.app.ctx.daemon_discovery:
            return response.json({"error": "Daemon discovery not available"}, status=503)

        # Stop current client if any
        if hasattr(request.app.ctx, "daemon_client") and request.app.ctx.daemon_client:
            await request.app.ctx.daemon_client.stop()

        # Find and connect to best daemon
        best_daemon = await request.app.ctx.daemon_discovery.get_best_daemon()
        if best_daemon is None:
            return response.json({"success": False, "error": "No daemon instances available"})

        # Create new client
        new_client = await request.app.ctx.daemon_discovery.create_client(
            daemon_info=best_daemon,
            output_callback=lambda line: handle_output_line(line, request.app),
            status_callback=lambda updates: handle_status_update(updates, request.app),
        )

        if new_client is None:
            return response.json({"success": False, "error": f"Failed to connect to daemon {best_daemon['daemon_id']}"})

        request.app.ctx.daemon_client = new_client

        return response.json(
            {
                "success": True,
                "daemon_id": best_daemon["daemon_id"],
                "host": best_daemon["host"],
                "port": best_daemon["port"],
            }
        )

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/shutdown", methods=["POST"])
async def shutdown_daemon(request: Request) -> HTTPResponse:
    """Initiate proper shutdown sequence using daemon manager"""
    try:
        # Check if we have daemon manager
        if not hasattr(request.app.ctx, "daemon_manager") or not request.app.ctx.daemon_manager:
            return response.json({"error": "Daemon manager not available"}, status=503)

        print("=" * 70)
        print("🔄 SHUTDOWN: Initiating graceful shutdown sequence")
        print("=" * 70)

        # Get daemon mode for logging
        daemon_mode = getattr(request.app.ctx, "daemon_mode", "unknown")
        print(f"🔍 SHUTDOWN: Daemon mode is: {daemon_mode}")

        # CRITICAL: Set shutdown flag FIRST to prevent daemon auto-restart
        request.app.ctx.shutdown_initiated = True
        print("✅ SHUTDOWN: Set shutdown_initiated flag to prevent daemon auto-restart")

        # Use daemon manager to stop the daemon (works for both overmind and native)
        daemon_manager = request.app.ctx.daemon_manager

        print(f"🛑 SHUTDOWN: Stopping {daemon_mode} daemon via daemon manager...")
        success = daemon_manager.stop_daemon()

        if success:
            print("✅ Daemon stopped successfully")

            # The cascade will continue:
            # - GUI daemon_monitor_task will detect daemon exit and shutdown GUI
            print("✅ Shutdown sequence completed - cascade in progress...")

            return response.json({"success": True, "message": "Shutdown sequence initiated: daemon → GUI"})
        else:
            print("⚠️ Daemon stop returned False, may have already been stopped")
            return response.json({"success": True, "message": "Daemon stop attempted, may have already been stopped"})

    except Exception as e:
        print(f"❌ Error during shutdown: {e}")
        import traceback
        traceback.print_exc()
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/restart", methods=["POST"])
async def restart_server(request: Request) -> HTTPResponse:
    """Restart the GUI server process to pick up code changes"""
    try:
        # Schedule server restart after sending response
        async def delayed_restart():
            # Small delay to ensure response is sent
            await asyncio.sleep(0.5)
            print("🔄 Restarting GUI server process to pick up code changes...")

            # Import here to avoid circular imports
            import os
            import sys
            import subprocess

            # Get the current command line arguments
            args = sys.argv.copy()

            # Stop the current app first
            request.app.stop()

            # Give it a moment to shut down
            await asyncio.sleep(2)

            # Start new process before exiting (more reliable than execv)
            print(f"🚀 Starting new process: {' '.join([sys.executable] + args)}")
            subprocess.Popen([sys.executable] + args, cwd=os.getcwd())

            # Exit current process
            print("✅ New process started, exiting current process")
            os._exit(0)

        request.app.add_task(delayed_restart())

        return response.json({"success": True, "message": "Server restart initiated"})
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/failure-declarations/<process_name>", methods=["GET"])
async def get_failure_declarations(request: Request, process_name: str) -> HTTPResponse:
    """Get failure declarations for a specific process"""
    try:
        if not hasattr(request.app.ctx, "process_manager"):
            return response.json({"error": "Process manager not available"}, status=503)

        declarations = request.app.ctx.process_manager.get_failure_declarations(process_name)
        return response.json({"process": process_name, "declarations": declarations})

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/failure-declarations/<process_name>/add", methods=["POST"])
async def add_failure_declaration(request: Request, process_name: str) -> HTTPResponse:
    """Add a failure declaration for a process"""
    try:
        if not hasattr(request.app.ctx, "process_manager"):
            return response.json({"error": "Process manager not available"}, status=503)

        # Get the failure string from the request body
        body = request.json
        if not body or "failure_string" not in body:
            return response.json({"error": "Missing failure_string in request body"}, status=400)

        failure_string = body["failure_string"].strip()
        if not failure_string:
            return response.json({"error": "failure_string cannot be empty"}, status=400)

        success = request.app.ctx.process_manager.add_failure_declaration(process_name, failure_string)

        if success:
            # Return updated declarations
            declarations = request.app.ctx.process_manager.get_failure_declarations(process_name)
            return response.json(
                {"success": True, "message": f"Added failure declaration for {process_name}", "declarations": declarations}
            )
        else:
            return response.json({"success": False, "error": "Failed to save failure declaration"}, status=500)

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/failure-declarations/<process_name>/remove", methods=["POST"])
async def remove_failure_declaration(request: Request, process_name: str) -> HTTPResponse:
    """Remove a failure declaration for a process"""
    try:
        if not hasattr(request.app.ctx, "process_manager"):
            return response.json({"error": "Process manager not available"}, status=503)

        # Get the failure string from the request body
        body = request.json
        if not body or "failure_string" not in body:
            return response.json({"error": "Missing failure_string in request body"}, status=400)

        failure_string = body["failure_string"]
        success = request.app.ctx.process_manager.remove_failure_declaration(process_name, failure_string)

        if success:
            # Return updated declarations
            declarations = request.app.ctx.process_manager.get_failure_declarations(process_name)
            return response.json(
                {
                    "success": True,
                    "message": f"Removed failure declaration for {process_name}",
                    "declarations": declarations,
                }
            )
        else:
            return response.json({"success": False, "error": "Failed to save failure declaration"}, status=500)

    except Exception as e:
        return response.json({"error": str(e)}, status=500)


def setup_api_routes(app):
    """Setup API routes on the app"""
    app.blueprint(api_bp)


# Import callback functions from main_daemon for daemon reconnection


async def kill_process_on_failure(app_instance, process_name: str, failure_pattern: str):
    """Kill a process that has matched a failure pattern"""
    try:
        import asyncio
        import os
        from datetime import datetime

        working_dir = getattr(app_instance.ctx, "working_directory", os.getcwd())

        print(f"🔴 FAILURE DETECTED: Process '{process_name}' matched failure pattern: '{failure_pattern}'")
        print(f"🔪 Killing process '{process_name}'...")

        # Use direct overmind command to stop process
        process = await asyncio.create_subprocess_exec(
            "overmind",
            "stop",
            process_name,
            cwd=working_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.wait()

        if process.returncode == 0:
            print(f"✅ Process '{process_name}' killed successfully")

            # Update process status in process manager
            if hasattr(app_instance.ctx, "process_manager"):
                app_instance.ctx.process_manager.update_process_status(process_name, "stopped")

            # Add failure message to output queue
            timestamp = datetime.now().strftime("%H:%M:%S")
            failure_message = (
                f"{process_name} | ❌ PROCESS KILLED: Detected failure pattern '{failure_pattern}' at {timestamp}"
            )
            update_queue.add_output_line(failure_message, process_name)

        else:
            print(f"⚠️ Failed to kill process '{process_name}' (exit code: {process.returncode})")

    except Exception as e:
        print(f"❌ Error killing process '{process_name}': {e}")
        import traceback

        traceback.print_exc()


def handle_output_line(line: str, app_instance):
    """Handle new output line from daemon client - add to update queue"""
    # Parse process name from daemon client output and check for failure patterns
    process_name, failure_pattern = app_instance.ctx.process_manager.add_output_line(line)

    if process_name:
        # Add to update queue
        update_queue.add_output_line(line, process_name)

        # Check if a failure pattern was detected
        if failure_pattern:
            # Kill the process asynchronously
            import asyncio

            try:
                # Get the event loop
                loop = asyncio.get_event_loop()
                # Schedule the kill task
                loop.create_task(kill_process_on_failure(app_instance, process_name, failure_pattern))
            except RuntimeError:
                print(f"⚠️ Could not schedule process kill for '{process_name}' - no event loop")
    else:
        # Fallback - add as 'system' output
        update_queue.add_output_line(line, "system")


def handle_status_update(status_updates: dict, app_instance):
    """Handle status updates from daemon client - add to update queue"""
    # Update process manager
    for process_name, status in status_updates.items():
        app_instance.ctx.process_manager.update_process_status(process_name, status)

    # Add to update queue
    update_queue.add_bulk_status_updates(status_updates)


class TestApiRoutesDaemon(unittest.TestCase):
    """Test cases for daemon API routes"""

    def test_api_blueprint_creation(self):
        """Test that API blueprint is created correctly"""
        self.assertEqual(api_bp.name, "api")
        self.assertEqual(api_bp.url_prefix, "/api")

    def test_setup_api_routes(self):
        """Test setup_api_routes function exists"""
        self.assertTrue(callable(setup_api_routes))

    def test_callback_functions_exist(self):
        """Test that callback functions exist and are callable"""
        self.assertTrue(callable(handle_output_line))
        self.assertTrue(callable(handle_status_update))
