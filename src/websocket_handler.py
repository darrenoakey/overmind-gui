"""
WebSocket Handler - Permanent connection management
Connections should NEVER close - they persist throughout the app lifecycle
"""

import json
import asyncio
import time
import traceback  # Import at top level
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from sanic import Websocket
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError


@dataclass
class ClientConnection:
    """Represents a permanent client connection"""
    ws: Websocket
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    last_ping: float = field(default_factory=time.time)
    id: str = field(default_factory=lambda: f"conn_{time.time()}")

    def is_alive(self) -> bool:
        """Check if connection is still alive"""
        try:
            # Check WebSocket state attribute if available
            # State 1 = OPEN, State 2 = CLOSING, State 3 = CLOSED
            state = getattr(self.ws, 'state', None)
            if state is not None:
                return state == 1
            # If no state attribute, assume alive
            return True
        except (AttributeError, RuntimeError):
            return False

    async def send(self, message: str) -> bool:
        """Send message to client with robust error handling"""
        try:
            if self.is_alive():
                await self.ws.send(message)
                self.last_activity = time.time()
                return True
            print(f"Connection {self.id} is not alive, cannot send message")
            return False
        except (ConnectionClosedOK, ConnectionClosedError) as e:
            print(f"Connection {self.id} closed: {e}")
            return False
        except Exception as e:  # pylint: disable=broad - except
            print(f"Error sending to client {self.id}: {e}")
            return False


class WebSocketManager:
    """
    Singleton WebSocket manager for persistent connections.
    This manager lives for the entire application lifecycle.
    """

    _instance: Optional['WebSocketManager'] = None
    _initialized: bool = False

    def __new__(cls):
        """Ensure singleton pattern - only one manager exists"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize only once"""
        if not self._initialized:
            self.connections: Dict[Websocket, ClientConnection] = {}
            self._lock = asyncio.Lock()
            self.monitor_task: Optional[asyncio.Task] = None
            WebSocketManager._initialized = True
            print("WebSocketManager singleton initialized")

    async def add_connection(self, ws: Websocket) -> ClientConnection:
        """Add a new permanent connection"""
        async with self._lock:
            conn = ClientConnection(ws=ws)
            self.connections[ws] = conn
            print(f"Connection {conn.id} established. Total connections: {len(self.connections)}")
            return conn

    async def remove_connection(self, ws: Websocket):
        """Remove a connection - this indicates a problem that needs fixing"""
        async with self._lock:
            if ws in self.connections:
                conn = self.connections[ws]
                del self.connections[ws]
                print(f"CONNECTION {conn.id} LOST - THIS IS A BUG! "
                      f"Total connections: {len(self.connections)}")
                print("WebSocket disconnections should not happen in single - worker mode")

    async def send_to_client(self, ws: Websocket, message_type: str, data: Any) -> bool:
        """Send message to specific client"""
        async with self._lock:
            if ws in self.connections:
                conn = self.connections[ws]
                try:
                    message = json.dumps({"type": message_type, "data": data})
                    return await conn.send(message)
                except (TypeError, ValueError) as e:
                    print(f"Error serializing message of type {message_type}: {e}")
                    return False
                except Exception as e:  # pylint: disable=broad - except
                    print(f"Error sending message of type {message_type} to {conn.id}: {e}")
                    return False
        print("Connection not found for WebSocket")
        return False

    async def broadcast(self, message_type: str, data: Any):
        """Broadcast message to all connected clients"""
        if not self.connections:
            return

        try:
            message = json.dumps({"type": message_type, "data": data})
        except (TypeError, ValueError) as e:
            print(f"Error serializing broadcast message of type {message_type}: {e}")
            return

        # Get all connections atomically
        async with self._lock:
            connections = list(self.connections.values())

        if not connections:
            return

        # Send to all connections in parallel
        tasks = []
        for conn in connections:
            if conn.is_alive():
                tasks.append(conn.send(message))
            else:
                print(f"Skipping dead connection {conn.id} during broadcast")

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # Log any failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"Broadcast failed for connection {connections[i].id}: {result}")

    async def handle_message(self, ws: Websocket, message: str, app) -> None:
        """Handle incoming message from client"""
        try:
            # Update activity timestamp
            async with self._lock:
                if ws in self.connections:
                    self.connections[ws].last_activity = time.time()
                else:
                    print("WARNING: Message from unknown connection")
                    return

            # Parse the message
            try:
                data = json.loads(message)
            except json.JSONDecodeError as e:
                print(f"[WS] Invalid JSON received: {message[:100]}, error: {e}")
                return

            message_type = data.get("type")
            payload = data.get("data", {})

            print(f"[WS] Processing message type: {message_type}")

            # Handle heartbeat/keepalive
            if message_type == "ping":
                await self.send_to_client(ws, "pong", {"timestamp": time.time()})
                async with self._lock:
                    if ws in self.connections:
                        self.connections[ws].last_ping = time.time()
                return
            if message_type == "pong":
                # Client responded to our ping - connection is healthy
                return

            # Handle business messages
            if message_type == "get_initial_state":
                print("[WS] Client requested initial state")
                # Small delay to ensure connection stability
                await asyncio.sleep(0.1)
                await self.send_initial_state(ws, app)
            elif message_type == "toggle_process":
                await self._handle_toggle_process(payload, app)
            elif message_type == "process_action":
                await self._handle_process_action(ws, payload, app)
            elif message_type == "clear_output":
                await self._handle_clear_output(app)
            else:
                print(f"[WS] Unknown message type: {message_type}")

        except Exception as e:  # pylint: disable=broad - except
            print(f"[WS] Error handling message: {e}")
            traceback.print_exc()
            # Never close connection on error - just log and continue

    async def send_initial_state(self, ws: Websocket, app):
        """Send initial state to client"""
        print("[WS] Preparing to send initial state")
        if hasattr(app.ctx, 'process_manager'):
            process_manager = app.ctx.process_manager
            try:
                state_data = {
                    "processes": process_manager.to_dict(),
                    "output": process_manager.get_combined_output(),
                    "stats": process_manager.get_stats()
                }
                print(f"[WS] Sending initial state with {len(state_data['processes'])} processes")
                success = await self.send_to_client(ws, "initial_state", state_data)
                if success:
                    print("[WS] Initial state sent successfully")
                else:
                    print("[WS] Failed to send initial state")
            except Exception as e:  # pylint: disable=broad - except
                print(f"[WS] Error sending initial state: {e}")
                traceback.print_exc()
        else:
            print("[WS] No process_manager available, not sending initial state")

    async def _handle_toggle_process(self, payload: Dict[str, Any], app):
        """Handle toggle process selection"""
        process_name = payload.get("process_name")
        if process_name and hasattr(app.ctx, 'process_manager'):
            selected = app.ctx.process_manager.toggle_process_selection(process_name)
            await self.broadcast("process_toggled", {
                "process_name": process_name,
                "selected": selected
            })

    async def _handle_process_action(self, ws: Websocket, payload: Dict[str, Any], app):
        """Handle process control actions"""
        action = payload.get("action")
        process_name = payload.get("process_name")

        if not action or not process_name:
            return

        if not hasattr(app.ctx, 'overmind_controller'):
            await self.send_to_client(ws, "error", {
                "message": "Overmind controller not available"
            })
            return

        controller = app.ctx.overmind_controller
        success = False

        try:
            if action == "start":
                success = await controller.start_process(process_name)
            elif action == "stop":
                success = await controller.stop_process(process_name)
            elif action == "restart":
                success = await controller.restart_process(process_name)

            await self.send_to_client(ws, "action_result", {
                "action": action,
                "process_name": process_name,
                "success": success
            })

            # Force status update after action
            if hasattr(app.ctx, 'overmind_controller'):
                try:
                    status_output = await controller.get_status()
                    if status_output:
                        status_updates = controller.parse_status_output(status_output)
                        await self._handle_status_update(status_updates, app)
                except Exception as e:  # pylint: disable=broad - except
                    print(f"Error getting status after action: {e}")

        except Exception as e:  # pylint: disable=broad - except
            print(f"Error performing action {action} on {process_name}: {e}")
            await self.send_to_client(ws, "error", {
                "message": f"Action failed: {str(e)}"
            })

    async def _handle_clear_output(self, app):
        """Handle clear output request"""
        if hasattr(app.ctx, 'process_manager'):
            app.ctx.process_manager.clear_all_output()
            await self.broadcast("output_cleared", {})

    async def _handle_status_update(self, status_updates: dict, app):
        """Handle status updates"""
        if hasattr(app.ctx, 'process_manager'):
            process_manager = app.ctx.process_manager
            for process_name, status in status_updates.items():
                process_manager.update_process_status(process_name, status)

            await self.broadcast("status_update", {
                "updates": status_updates,
                "stats": process_manager.get_stats()
            })

    async def monitor_connections(self):
        """Monitor connections and send periodic heartbeats"""
        print("Starting WebSocket connection monitor")
        while True:
            try:
                await asyncio.sleep(25)  # Send heartbeat every 25 seconds

                # Send heartbeat to all connections
                await self.broadcast("ping", {"timestamp": time.time()})

                # Check connection health
                async with self._lock:
                    now = time.time()
                    for conn in list(self.connections.values()):
                        if not conn.is_alive():
                            print(f"Dead connection detected: {conn.id} - THIS IS A BUG!")
                        elif now - conn.last_activity > 120:
                            print(f"Connection {conn.id} inactive for 2 minutes - may be stale")
                        elif now - conn.last_ping > 60:
                            print(f"Connection {conn.id} hasn't responded to ping in 60 seconds")

                    if self.connections:
                        print(f"Monitor: {len(self.connections)} active connections")

            except Exception as e:  # pylint: disable=broad - except
                print(f"Monitor error: {e}")
                # Continue monitoring even if there's an error


# Global singleton WebSocket manager instance
# This ensures all workers share the same manager
websocket_manager = WebSocketManager()


async def websocket_handler(request, ws: Websocket):
    """
    Handle WebSocket connections - connections persist for app lifecycle.
    In single - worker mode, connections should NEVER close unexpectedly.
    """
    print(f"[WS] New WebSocket connection from {request.ip}")

    # Add connection to manager
    conn = await websocket_manager.add_connection(ws)

    try:
        # Send initial connection success message
        await websocket_manager.send_to_client(ws, "connected", {
            "message": "WebSocket connected successfully",
            "connection_id": conn.id
        })

        # Handle messages forever - this loop should never exit normally
        print(f"[WS] Starting message handler for connection {conn.id} from {request.ip}")
        async for message in ws:
            if message:
                print(f"[WS] Received message from {conn.id}: {message[:100]}...")
                await websocket_manager.handle_message(ws, message, request.app)
            else:
                # Empty message might indicate connection issue
                print(f"[WS] Received empty message from {conn.id} - possible connection issue")

    except (ConnectionClosedOK, ConnectionClosedError) as e:
        # This should NEVER happen in single - worker mode
        print(f"CONNECTION {conn.id} CLOSED - THIS IS A BUG!")
        print(f"Error details: {e}")
        print("Check that the app is running with workers=1")
    except asyncio.CancelledError:
        print(f"WebSocket handler for {conn.id} cancelled - server shutting down")
    except Exception as e:  # pylint: disable=broad - except
        print(f"WebSocket error for {conn.id}: {e}")
        print("CONNECTION SHOULD NOT CLOSE - This indicates a bug!")
        traceback.print_exc()
    finally:
        # Remove connection - this should only happen on server shutdown
        await websocket_manager.remove_connection(ws)
        print(f"Connection {conn.id} removed from manager")


async def start_websocket_monitor(_app):
    """Start the WebSocket connection monitor as a background task"""
    if websocket_manager.monitor_task is None:
        websocket_manager.monitor_task = asyncio.create_task(
            websocket_manager.monitor_connections()
        )
        print("WebSocket monitor task started")
    else:
        print("WebSocket monitor already running")
