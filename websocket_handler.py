"""
WebSocket Handler - Real-time communication with frontend
Manages WebSocket connections and message routing
"""

import json
import asyncio
import unittest
from typing import Set, Dict, Any
from sanic import Websocket
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError


class WebSocketManager:
    """Manages WebSocket connections and message broadcasting"""

    def __init__(self):
        self.clients: Set[Websocket] = set()

    def add_client(self, ws: Websocket):
        """Add a new WebSocket client"""
        self.clients.add(ws)
        print(f"Client connected. Total clients: {len(self.clients)}")

    def remove_client(self, ws: Websocket):
        """Remove a WebSocket client"""
        self.clients.discard(ws)
        print(f"Client disconnected. Total clients: {len(self.clients)}")

    async def broadcast(self, message_type: str, data: Any):
        """Broadcast a message to all connected clients"""
        if not self.clients:
            return

        message = {
            "type": message_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        }

        message_json = json.dumps(message)

        # Send to all clients, removing any that have disconnected
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(message_json)
            except (ConnectionClosedOK, ConnectionClosedError) as e:
                print(f"Client disconnected during broadcast: {e}")
                disconnected.add(client)

        # Clean up disconnected clients
        for client in disconnected:
            self.clients.discard(client)

    async def send_to_client(self, ws: Websocket, message_type: str, data: Any):
        """Send a message to a specific client"""
        message = {
            "type": message_type,
            "data": data,
            "timestamp": asyncio.get_event_loop().time()
        }

        try:
            await ws.send(json.dumps(message))
        except (ConnectionClosedOK, ConnectionClosedError) as e:
            print(f"Failed to send to client: {e}")
            self.clients.discard(ws)

    async def handle_client_message(self, ws: Websocket, message: str, app) -> None:
        """Handle incoming message from client"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            payload = data.get("data", {})

            if message_type == "toggle_process":
                await self._handle_toggle_process(payload, app)
            elif message_type == "process_action":
                await self._handle_process_action(ws, payload, app)
            elif message_type == "clear_output":
                await self._handle_clear_output(app)
            elif message_type == "get_initial_state":
                await self.handle_get_initial_state(ws, app)
            else:
                print(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            print(f"Invalid JSON received: {message}")
        except (ConnectionClosedOK, ConnectionClosedError) as e:
            print(f"Connection error while handling message: {e}")

    async def _handle_toggle_process(self, payload: Dict[str, Any], app):
        """Handle process selection toggle"""
        process_name = payload.get("process_name")
        if not process_name:
            return

        process_manager = app.ctx.process_manager
        new_state = process_manager.toggle_process_selection(process_name)

        # Broadcast the updated process state
        await self.broadcast("process_updated", {
            "name": process_name,
            "selected": new_state
        })

        # Send updated output
        await self._send_filtered_output(app)

    async def _handle_process_action(self, ws: Websocket, payload: Dict[str, Any], app):
        """Handle process control actions (start/stop/restart)"""
        process_name = payload.get("process_name")
        action = payload.get("action")

        if not process_name or not action:
            return

        overmind_controller = app.ctx.overmind_controller
        process_manager = app.ctx.process_manager
        success = False

        if action == "start":
            success = await overmind_controller.start_process(process_name)
        elif action == "stop":
            success = await overmind_controller.stop_process(process_name)
        elif action == "restart":
            success = await overmind_controller.restart_process(process_name)
            # Clear broken status when restarting
            if success:
                process_manager.restart_process(process_name)
                print(f"Cleared broken status for {process_name} after restart")

        # Send action result
        await self.send_to_client(ws, "action_result", {
            "process_name": process_name,
            "action": action,
            "success": success
        })

        # Force status update
        if success:
            await self._force_status_update(app)

    async def _handle_clear_output(self, app):
        """Handle clear output request"""
        process_manager = app.ctx.process_manager
        process_manager.clear_all_output()

        await self.broadcast("output_cleared", {})

    async def handle_get_initial_state(self, ws: Websocket, app):
        """Send initial application state to newly connected client"""
        process_manager = app.ctx.process_manager

        # Send process list and states
        await self.send_to_client(ws, "initial_state", {
            "processes": process_manager.to_dict(),
            "output": process_manager.get_combined_output(selected_only=True)
        })

    async def _send_filtered_output(self, app):
        """Send filtered output to all clients"""
        process_manager = app.ctx.process_manager
        output_lines = process_manager.get_combined_output(selected_only=True)

        await self.broadcast("output_updated", {
            "lines": output_lines
        })

    async def _force_status_update(self, app):
        """Force an immediate status update"""
        try:
            overmind_controller = app.ctx.overmind_controller
            status_output = await overmind_controller.get_status()
            if status_output:
                # Call the public method instead of protected one
                status_updates = overmind_controller.parse_status_output(status_output)
                if status_updates:
                    await self._handle_status_update(status_updates, app)
        except (ConnectionClosedOK, ConnectionClosedError) as e:
            print(f"Connection error in status update: {e}")

    async def _handle_status_update(self, status_updates: Dict[str, str], app):
        """Handle status updates from overmind"""
        process_manager = app.ctx.process_manager

        for process_name, status in status_updates.items():
            process_manager.update_process_status(process_name, status)

        # Broadcast updated process states
        await self.broadcast("status_update", {
            "updates": status_updates,
            "stats": process_manager.get_stats()
        })


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


async def websocket_handler(request, ws: Websocket):
    """Handle WebSocket connections"""
    websocket_manager.add_client(ws)

    try:
        # Send initial state when client connects
        await websocket_manager.handle_get_initial_state(ws, request.app)

        # Listen for messages
        async for message in ws:
            await websocket_manager.handle_client_message(ws, message, request.app)

    except (ConnectionClosedOK, ConnectionClosedError, asyncio.CancelledError):
        pass
    except (ConnectionResetError, OSError) as e:
        print(f"WebSocket connection error: {e}")
    finally:
        websocket_manager.remove_client(ws)


class MockWebSocket:  # pylint: disable=too-few-public-methods
    """Mock WebSocket for testing"""

    def __init__(self):
        self.sent_messages = []
        self.closed = False

    async def send(self, message):
        """Mock send method"""
        if self.closed:
            raise ConnectionClosedOK(None, None)
        self.sent_messages.append(message)

    def close(self):
        """Mock close method"""
        self.closed = True


class MockApp:  # pylint: disable=too-few-public-methods
    """Mock app for testing"""

    def __init__(self):
        self.ctx = MockContext()


class MockContext:  # pylint: disable=too-few-public-methods
    """Mock context for testing"""

    def __init__(self):
        self.process_manager = MockProcessManager()
        self.overmind_controller = MockOvermindController()


class MockProcessManager:  # pylint: disable=too-few-public-methods
    """Mock process manager for testing"""

    def toggle_process_selection(self, name):  # pylint: disable=unused-argument
        """Mock toggle process selection"""
        return True

    def clear_all_output(self):
        """Mock clear all output"""
        return None

    def restart_process(self, name):  # pylint: disable=unused-argument
        """Mock restart process"""
        return None

    def to_dict(self):
        """Mock to_dict"""
        return {"processes": {}, "stats": {}}

    def get_combined_output(self, selected_only=True):  # pylint: disable=unused-argument
        """Mock get combined output"""
        return []

    def update_process_status(self, name, status):  # pylint: disable=unused-argument
        """Mock update process status"""
        return None

    def get_stats(self):
        """Mock get stats"""
        return {"total": 0, "running": 0, "selected": 0}


class MockOvermindController:  # pylint: disable=too-few-public-methods
    """Mock overmind controller for testing"""

    async def start_process(self, name):  # pylint: disable=unused-argument
        """Mock start process"""
        return True

    async def stop_process(self, name):  # pylint: disable=unused-argument
        """Mock stop process"""
        return True

    async def restart_process(self, name):  # pylint: disable=unused-argument
        """Mock restart process"""
        return True

    async def get_status(self):
        """Mock get status"""
        return "PROCESS PID STATUS\nweb 123 running"

    def parse_status_output(self, output):  # pylint: disable=unused-argument
        """Mock parse status output"""
        return {"web": "running"}


class TestWebSocketManager(unittest.TestCase):
    """Test cases for WebSocketManager"""

    def setUp(self):
        """Set up test environment"""
        self.manager = WebSocketManager()
        self.mock_ws = MockWebSocket()
        self.mock_app = MockApp()

    def test_initialization(self):
        """Test WebSocketManager initialization"""
        manager = WebSocketManager()
        self.assertEqual(len(manager.clients), 0)

    def test_add_remove_client(self):
        """Test adding and removing clients"""
        ws = MockWebSocket()

        self.manager.add_client(ws)
        self.assertEqual(len(self.manager.clients), 1)
        self.assertIn(ws, self.manager.clients)

        self.manager.remove_client(ws)
        self.assertEqual(len(self.manager.clients), 0)
        self.assertNotIn(ws, self.manager.clients)

    def test_websocket_handler_function_exists(self):
        """Test that websocket_handler function is callable"""
        self.assertTrue(callable(websocket_handler))

    async def test_send_to_client(self):
        """Test sending message to specific client"""
        await self.manager.send_to_client(self.mock_ws, "test_type", {"key": "value"})

        self.assertEqual(len(self.mock_ws.sent_messages), 1)
        message = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(message["type"], "test_type")
        self.assertEqual(message["data"]["key"], "value")

    async def test_broadcast_empty_clients(self):
        """Test broadcasting with no clients"""
        # Should not raise any exceptions
        await self.manager.broadcast("test_type", {"data": "test"})

    async def test_broadcast_with_clients(self):
        """Test broadcasting to clients"""
        self.manager.add_client(self.mock_ws)
        await self.manager.broadcast("test_type", {"data": "test"})

        self.assertEqual(len(self.mock_ws.sent_messages), 1)
        message = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(message["type"], "test_type")

    async def test_handle_get_initial_state(self):
        """Test handling get initial state request"""
        await self.manager.handle_get_initial_state(self.mock_ws, self.mock_app)

        self.assertEqual(len(self.mock_ws.sent_messages), 1)
        message = json.loads(self.mock_ws.sent_messages[0])
        self.assertEqual(message["type"], "initial_state")

    async def test_handle_client_message_invalid_json(self):
        """Test handling invalid JSON message"""
        # Should not raise exceptions
        await self.manager.handle_client_message(self.mock_ws, "invalid json", self.mock_app)

    async def test_handle_client_message_toggle_process(self):
        """Test handling toggle process message"""
        message = json.dumps({
            "type": "toggle_process",
            "data": {"process_name": "web"}
        })

        await self.manager.handle_client_message(self.mock_ws, message, self.mock_app)
        # Should not raise exceptions - actual functionality depends on mock implementations

    async def test_handle_client_message_unknown_type(self):
        """Test handling unknown message type"""
        message = json.dumps({
            "type": "unknown_type",
            "data": {}
        })

        # Should not raise exceptions
        await self.manager.handle_client_message(self.mock_ws, message, self.mock_app)

    def test_global_websocket_manager_exists(self):
        """Test that global websocket_manager instance exists"""
        self.assertIsInstance(websocket_manager, WebSocketManager)
