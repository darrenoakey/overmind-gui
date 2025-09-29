#!/usr/bin/env python3
"""Tests for event_handlers module."""

import asyncio
import unittest
import sys
import os


class TestController:
    """Real controller for testing event handlers"""

    def __init__(self):
        self.start_called = False
        self.stop_called = False

    async def start(self):
        """Real async start method"""
        self.start_called = True
        return True

    async def stop(self):
        """Real async stop method"""
        self.stop_called = True


class TestApp:
    """Real app object for testing event handlers"""

    def __init__(self):
        self.ctx = self

    def set_controller(self, controller):
        """Add controller to app context"""
        self.overmind_controller = controller


class TestEventHandlers(unittest.TestCase):
    """Test cases for event_handlers module."""

    def setUp(self):
        """Set up test fixtures"""
        # Add the directory containing the module to Python path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import event_handlers
        self.event_handlers = event_handlers

    def test_startup_handler_without_controller(self):
        """Test startup handler when no overmind controller is present"""
        # Create real app without overmind_controller
        app = TestApp()

        # Run the async function
        async def run_test():
            await self.event_handlers.startup_handler(app, None)

        # Should complete without error
        asyncio.run(run_test())

    def test_startup_handler_with_controller(self):
        """Test startup handler when overmind controller is present"""
        # Create real app with controller
        app = TestApp()
        controller = TestController()
        app.set_controller(controller)

        # Run the async function
        async def run_test():
            await self.event_handlers.startup_handler(app, None)

        asyncio.run(run_test())

        # Verify controller.start was called
        self.assertTrue(controller.start_called)

    def test_shutdown_handler_without_controller(self):
        """Test shutdown handler when no overmind controller is present"""
        # Create real app without overmind_controller
        app = TestApp()

        # Run the async function
        async def run_test():
            await self.event_handlers.shutdown_handler(app, None)

        # Should complete without error
        asyncio.run(run_test())

    def test_shutdown_handler_with_controller(self):
        """Test shutdown handler when overmind controller is present"""
        # Create real app with controller
        app = TestApp()
        controller = TestController()
        app.set_controller(controller)

        # Run the async function
        async def run_test():
            await self.event_handlers.shutdown_handler(app, None)

        asyncio.run(run_test())

        # Verify controller.stop was called
        self.assertTrue(controller.stop_called)


if __name__ == '__main__':
    unittest.main()
