#!/usr/bin/env python3
"""
Event handlers for Overmind GUI Web Server
Contains startup and shutdown event handlers
"""

import unittest


async def startup_handler(sanic_app, _loop):
    """Handle application startup"""
    print("🚀 Starting Overmind GUI...")

    # Try to load Procfile if it exists
    if hasattr(sanic_app.ctx, 'process_manager'):
        try:
            process_names = sanic_app.ctx.process_manager.load_procfile()
            if process_names:
                process_list = ', '.join(process_names)
                print(f"📋 Loaded {len(process_names)} processes: {process_list}")
            else:
                print("📋 No processes found in Procfile")
        except FileNotFoundError:
            print("📋 No Procfile found - will start without predefined processes")
        except Exception as e:  # pylint: disable=broad-exception-caught
            print(f"⚠️ Error loading Procfile: {e}")

    # Start overmind controller
    if hasattr(sanic_app.ctx, 'overmind_controller'):
        success = await sanic_app.ctx.overmind_controller.start()
        if success:
            print("✅ Overmind controller started successfully")
        else:
            print("❌ Failed to start overmind controller")


async def shutdown_handler(sanic_app, _loop):
    """Handle application shutdown"""
    print("🛑 Shutting down Overmind GUI...")

    # Stop overmind controller
    if hasattr(sanic_app.ctx, 'overmind_controller'):
        await sanic_app.ctx.overmind_controller.stop()
        print("✅ Overmind controller stopped")


class TestEventHandlers(unittest.TestCase):
    """Test cases for event handlers"""

    def test_startup_handler_exists(self):
        """Test that startup_handler function exists and is callable"""
        self.assertTrue(callable(startup_handler))

    def test_shutdown_handler_exists(self):
        """Test that shutdown_handler function exists and is callable"""
        self.assertTrue(callable(shutdown_handler))
