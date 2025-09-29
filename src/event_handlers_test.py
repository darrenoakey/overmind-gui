#!/usr/bin/env python3
"""Tests for event_handlers module."""

import asyncio
import unittest
import sys
import os
from unittest.mock import MagicMock, AsyncMock


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
        # Create mock sanic app without overmind_controller
        mock_app = MagicMock()
        mock_app.ctx = MagicMock()
        del mock_app.ctx.overmind_controller  # Ensure attribute doesn't exist
        mock_loop = MagicMock()

        # Run the async function
        async def run_test():
            await self.event_handlers.startup_handler(mock_app, mock_loop)

        # Should complete without error
        asyncio.run(run_test())

    def test_startup_handler_with_controller(self):
        """Test startup handler when overmind controller is present"""
        # Create mock sanic app with overmind_controller
        mock_app = MagicMock()
        mock_app.ctx = MagicMock()
        mock_controller = AsyncMock()
        mock_controller.start = AsyncMock(return_value=True)
        mock_app.ctx.overmind_controller = mock_controller
        mock_loop = MagicMock()

        # Run the async function
        async def run_test():
            await self.event_handlers.startup_handler(mock_app, mock_loop)

        asyncio.run(run_test())

        # Verify controller.start was called
        mock_controller.start.assert_called_once()

    def test_shutdown_handler_without_controller(self):
        """Test shutdown handler when no overmind controller is present"""
        # Create mock sanic app without overmind_controller
        mock_app = MagicMock()
        mock_app.ctx = MagicMock()
        del mock_app.ctx.overmind_controller  # Ensure attribute doesn't exist
        mock_loop = MagicMock()

        # Run the async function
        async def run_test():
            await self.event_handlers.shutdown_handler(mock_app, mock_loop)

        # Should complete without error
        asyncio.run(run_test())

    def test_shutdown_handler_with_controller(self):
        """Test shutdown handler when overmind controller is present"""
        # Create mock sanic app with overmind_controller
        mock_app = MagicMock()
        mock_app.ctx = MagicMock()
        mock_controller = AsyncMock()
        mock_controller.stop = AsyncMock()
        mock_app.ctx.overmind_controller = mock_controller
        mock_loop = MagicMock()

        # Run the async function
        async def run_test():
            await self.event_handlers.shutdown_handler(mock_app, mock_loop)

        asyncio.run(run_test())

        # Verify controller.stop was called
        mock_controller.stop.assert_called_once()


if __name__ == '__main__':
    unittest.main()
