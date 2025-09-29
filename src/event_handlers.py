#!/usr/bin/env python3
"""
Event handlers for Overmind GUI Web Server
Contains startup and shutdown event handlers
"""


async def startup_handler(sanic_app, _loop):
    """Handle application startup"""
    print("🚀 Starting Overmind GUI...")

    # Procfile loading is now handled in initialize_managers with proper working directory
    print("📋 Procfile loading will be handled by daemon management task")

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
