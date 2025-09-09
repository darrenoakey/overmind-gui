"""
API Routes - Message-based polling endpoints with incremental IDs
Provides endpoints for process management and polling updates using message IDs
"""

import asyncio
import json
import re
import time
import unittest
from typing import Dict, Any, Optional

from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse

from update_queue import update_queue
from process_manager import ProcessManager


# Create API blueprint
api_bp = Blueprint("api", url_prefix="/api")


@api_bp.route("/state", methods=["GET"])
async def get_current_state(request: Request) -> HTTPResponse:
    """Get complete current state for initial page load"""
    try:
        state = update_queue.get_current_state()
        
        # Add process manager stats
        if hasattr(request.app.ctx, 'process_manager'):
            stats = request.app.ctx.process_manager.get_stats()
            state['stats'] = stats
            
            # Add process info
            processes = request.app.ctx.process_manager.get_all_processes()
            state['processes'] = {
                name: proc.to_dict() for name, proc in processes.items()
            }
            print(f"DEBUG: Returning {len(state['processes'])} processes with statuses: {[(name, proc['status']) for name, proc in state['processes'].items()]}")
        else:
            state['stats'] = {}
            state['processes'] = {}
        
        # Add overmind status
        overmind_status = "unknown"
        if hasattr(request.app.ctx, 'overmind_controller') and request.app.ctx.overmind_controller:
            if request.app.ctx.overmind_controller.is_running():
                overmind_status = "running"
            else:
                overmind_status = "stopped"
        elif hasattr(request.app.ctx, 'overmind_failed') and request.app.ctx.overmind_failed:
            overmind_status = "failed"
        
        state['overmind_status'] = overmind_status
        state['version'] = getattr(request.app.ctx, 'version', 1)
        
        # Add queue stats
        state['queue_stats'] = update_queue.get_stats()
        
        return response.json(state)
        
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/poll", methods=["GET"])
async def poll_updates(request: Request) -> HTTPResponse:
    """Poll for updates since last message ID"""
    try:
        # Get last message ID from query parameter
        last_id_str = request.args.get('last_message_id', '0')
        
        try:
            last_message_id = int(last_id_str)
        except (ValueError, TypeError):
            return response.json({"error": "Invalid last_message_id - must be integer"}, status=400)
        
        if last_message_id < 0:
            return response.json({"error": "last_message_id must be >= 0"}, status=400)
        
        # Poll for updates - NEW MESSAGE-BASED FORMAT
        response_package, latest_message_id = update_queue.poll_updates(last_message_id)
        
        # Add current stats
        stats = {}
        if hasattr(request.app.ctx, 'process_manager'):
            stats = request.app.ctx.process_manager.get_stats()
        
        # Build final response with new message-based structure
        return response.json({
            "output_lines": response_package['output_lines'],
            "status_updates": response_package['status_updates'],
            "total_lines": response_package['total_lines'],
            "other_updates": response_package['other_updates'],
            "latest_message_id": latest_message_id,  # Changed from timestamp
            "stats": stats,
            "queue_stats": update_queue.get_stats()
        })
        
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/process/<process_name>/start", methods=["POST"])
async def start_process(request: Request, process_name: str) -> HTTPResponse:
    """Start a specific process"""
    try:
        if not hasattr(request.app.ctx, 'overmind_controller') or not request.app.ctx.overmind_controller:
            return response.json({"error": "Overmind controller not available"}, status=503)
        
        success = await request.app.ctx.overmind_controller.start_process(process_name)
        
        if success:
            update_queue.add_status_update(process_name, "starting")
            return response.json({"success": True, "message": f"Started {process_name}"})
        else:
            return response.json({"success": False, "error": f"Failed to start {process_name}"})
            
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/process/<process_name>/stop", methods=["POST"])
async def stop_process(request: Request, process_name: str) -> HTTPResponse:
    """Stop a specific process"""
    try:
        if not hasattr(request.app.ctx, 'overmind_controller') or not request.app.ctx.overmind_controller:
            return response.json({"error": "Overmind controller not available"}, status=503)
        
        success = await request.app.ctx.overmind_controller.stop_process(process_name)
        
        if success:
            update_queue.add_status_update(process_name, "stopping")
            return response.json({"success": True, "message": f"Stopped {process_name}"})
        else:
            return response.json({"success": False, "error": f"Failed to stop {process_name}"})
            
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/process/<process_name>/restart", methods=["POST"])
async def restart_process(request: Request, process_name: str) -> HTTPResponse:
    """Restart a specific process"""
    try:
        if not hasattr(request.app.ctx, 'overmind_controller') or not request.app.ctx.overmind_controller:
            return response.json({"error": "Overmind controller not available"}, status=503)
        
        success = await request.app.ctx.overmind_controller.restart_process(process_name)
        
        if success:
            # Mark process as restarted in process manager
            if hasattr(request.app.ctx, 'process_manager'):
                request.app.ctx.process_manager.restart_process(process_name)
            
            update_queue.add_status_update(process_name, "restarting")
            return response.json({"success": True, "message": f"Restarted {process_name}"})
        else:
            return response.json({"success": False, "error": f"Failed to restart {process_name}"})
            
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/process/<process_name>/toggle", methods=["POST"])
async def toggle_process_selection(request: Request, process_name: str) -> HTTPResponse:
    """Toggle process selection for output display"""
    try:
        if not hasattr(request.app.ctx, 'process_manager'):
            return response.json({"error": "Process manager not available"}, status=503)
        
        new_state = request.app.ctx.process_manager.toggle_process_selection(process_name)
        
        return response.json({
            "success": True,
            "process": process_name,
            "selected": new_state
        })
        
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/processes/select-all", methods=["POST"])
async def select_all_processes(request: Request) -> HTTPResponse:
    """Select all processes for output display"""
    try:
        if not hasattr(request.app.ctx, 'process_manager'):
            return response.json({"error": "Process manager not available"}, status=503)
        
        request.app.ctx.process_manager.select_all_processes()
        
        # Return updated process list
        processes = request.app.ctx.process_manager.get_all_processes()
        process_data = {name: proc.to_dict() for name, proc in processes.items()}
        
        return response.json({
            "success": True, 
            "message": "All processes selected",
            "processes": process_data
        })
        
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/processes/deselect-all", methods=["POST"])
async def deselect_all_processes(request: Request) -> HTTPResponse:
    """Deselect all processes from output display"""
    try:
        if not hasattr(request.app.ctx, 'process_manager'):
            return response.json({"error": "Process manager not available"}, status=503)
        
        request.app.ctx.process_manager.deselect_all_processes()
        
        # Return updated process list
        processes = request.app.ctx.process_manager.get_all_processes()
        process_data = {name: proc.to_dict() for name, proc in processes.items()}
        
        return response.json({
            "success": True, 
            "message": "All processes deselected",
            "processes": process_data
        })
        
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/output/clear", methods=["POST"])
async def clear_output(request: Request) -> HTTPResponse:
    """Clear all output lines"""
    try:
        update_queue.clear_all()
        
        # Also clear process manager output if available
        if hasattr(request.app.ctx, 'process_manager'):
            request.app.ctx.process_manager.clear_all_output()
        
        return response.json({
            "success": True, 
            "message": "Output cleared",
            "latest_message_id": update_queue.message_counter
        })
        
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


@api_bp.route("/status", methods=["GET"])
async def get_status(request: Request) -> HTTPResponse:
    """Get overmind and system status"""
    try:
        status_info = {
            "overmind_running": False,
            "process_count": 0,
            "line_count": 0,
            "uptime": 0,
            "latest_message_id": update_queue.message_counter
        }
        
        if hasattr(request.app.ctx, 'overmind_controller') and request.app.ctx.overmind_controller:
            status_info["overmind_running"] = request.app.ctx.overmind_controller.is_running()
        
        if hasattr(request.app.ctx, 'process_manager'):
            stats = request.app.ctx.process_manager.get_stats()
            status_info["process_count"] = stats.get("total", 0)
        
        # Add queue stats
        queue_stats = update_queue.get_stats()
        status_info["message_count"] = queue_stats["total_messages"]
        status_info["line_count"] = queue_stats["total_lines"]
        
        return response.json(status_info)
        
    except Exception as e:
        return response.json({"error": str(e)}, status=500)


def setup_api_routes(app):
    """Setup API routes on the app"""
    app.blueprint(api_bp)


class TestApiRoutes(unittest.TestCase):
    """Test cases for API routes"""
    
    def test_api_blueprint_creation(self):
        """Test that API blueprint is created correctly"""
        self.assertEqual(api_bp.name, "api")
        self.assertEqual(api_bp.url_prefix, "/api")
    
    def test_setup_api_routes(self):
        """Test setup_api_routes function exists"""
        self.assertTrue(callable(setup_api_routes))


@api_bp.route("/shutdown", methods=["POST"])
async def shutdown_overmind(request: Request) -> HTTPResponse:
    """Initiate overmind quit and system shutdown sequence"""
    try:
        if not hasattr(request.app.ctx, "overmind_controller") or not request.app.ctx.overmind_controller:
            return response.json({"error": "Overmind controller not available"}, status=503)
        
        # Execute overmind quit command and wait for it to complete
        success = await request.app.ctx.overmind_controller.quit()
        
        if success:
            # Overmind has fully shut down, now trigger Sanic shutdown
            # Schedule Sanic shutdown after sending response
            async def delayed_sanic_shutdown():
                # Small delay to ensure response is sent
                await asyncio.sleep(0.5)
                request.app.stop()
            
            request.app.add_task(delayed_sanic_shutdown())
            
            return response.json({
                "success": True, 
                "message": "Overmind quit completed successfully, server shutting down"
            })
        else:
            return response.json({
                "success": False, 
                "error": "Failed to execute overmind quit"
            }, status=500)
            
    except Exception as e:
        return response.json({"error": str(e)}, status=500)

