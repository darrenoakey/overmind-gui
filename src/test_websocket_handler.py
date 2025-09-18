"""
Tests for WebSocket Handler
"""

import unittest
from websocket_handler import (
    WebSocketManager,
    ClientConnection,
    websocket_handler
)


class MockWebSocket:  # pylint: disable=too-few-public-methods
    """Mock WebSocket for testing"""

    def __init__(self):
        self.sent_messages = []
        self.closed = False
        self.state = 1  # Mock OPEN state

    async def send(self, message):
        """Mock send method"""
        self.sent_messages.append(message)

    def close(self):
        """Mock close method"""
        self.closed = True
        self.state = 3  # Mock CLOSED state


class MockApp:  # pylint: disable=too-few-public-methods
    """Mock Sanic app for testing"""

    def __init__(self):
        self.ctx = MockContext()


class MockContext:  # pylint: disable=too-few-public-methods
    """Mock app context for testing"""

    def __init__(self):
        self.process_manager = MockProcessManager()
        self.overmind_controller = MockOvermindController()


class MockProcessManager:  # pylint: disable=too-few-public-methods
    """Mock process manager for testing"""

    def toggle_process_selection(self, process_name):  # pylint: disable=unused-argument
        """Mock toggle process selection"""
        return True

    def clear_all_output(self):
        """Mock clear all output"""

    def to_dict(self):
        """Mock to_dict"""
        return {}

    def get_combined_output(self):
        """Mock get combined output"""
        return "test output"

    def update_process_status(self, process_name, status):  # pylint: disable=unused-argument
        """Mock update process status"""

    def get_stats(self):
        """Mock get stats"""
        return {"total": 0, "running": 0}


class MockOvermindController:  # pylint: disable=too-few-public-methods
    """Mock overmind controller for testing"""

    async def start_process(self, process_name):  # pylint: disable=unused-argument
        """Mock start process"""
        return True

    async def stop_process(self, process_name):  # pylint: disable=unused-argument
        """Mock stop process"""
        return True

    async def restart_process(self, process_name):  # pylint: disable=unused-argument
        """Mock restart process"""
        return True

    async def get_status(self):
        """Mock get status"""
        return "status output"

    def parse_status_output(self, output):  # pylint: disable=unused-argument
        """Mock parse status output"""
        return {}


class TestWebSocketManager(unittest.TestCase):
    """Test WebSocket manager functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.manager = WebSocketManager()
        self.mock_ws = MockWebSocket()
        self.mock_app = MockApp()

    def test_initialization(self):
        """Test WebSocketManager initialization"""
        self.assertIsInstance(self.manager.connections, dict)
        self.assertEqual(len(self.manager.connections), 0)

    def test_client_connection(self):
        """Test ClientConnection creation"""
        conn = ClientConnection(ws=self.mock_ws)
        self.assertIsNotNone(conn.connected_at)
        self.assertIsNotNone(conn.last_activity)
        self.assertTrue(conn.is_alive())

    async def test_add_remove_connection(self):
        """Test adding and removing connections"""
        await self.manager.add_connection(self.mock_ws)
        self.assertEqual(len(self.manager.connections), 1)

        await self.manager.remove_connection(self.mock_ws)
        self.assertEqual(len(self.manager.connections), 0)

    def test_websocket_handler_function_exists(self):
        """Test that websocket_handler function exists"""
        self.assertTrue(callable(websocket_handler))

    async def test_send_to_client(self):
        """Test sending message to specific client"""
        await self.manager.add_connection(self.mock_ws)
        result = await self.manager.send_to_client(
            self.mock_ws, "test", {"data": "test"}
        )
        self.assertTrue(result)

    async def test_broadcast_empty(self):
        """Test broadcasting with no connections"""
        await self.manager.broadcast("test", {"data": "test"})
        # Should not raise an error

    async def test_handle_message(self):
        """Test handling messages"""
        await self.manager.add_connection(self.mock_ws)
        await self.manager.handle_message(
            self.mock_ws, '{"type": "ping", "data": {}}', self.mock_app
        )
        # Should handle without error

    def test_global_websocket_manager_exists(self):
        """Test that global websocket_manager exists"""
        from websocket_handler import websocket_manager  # pylint: disable=import-outside-toplevel
        self.assertIsInstance(websocket_manager, WebSocketManager)
