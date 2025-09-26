#!/usr/bin/env python3
"""
Quick test for daemon + GUI integration
Start daemon first, then GUI, and test basic connectivity
"""

import asyncio
import json
import tempfile
import time
import urllib.request

from daemon_integration_test import MockProcessEnvironment
from overmind_daemon import OvermindDaemon


async def test_daemon_gui():
    """Quick test of daemon + GUI"""
    test_dir = tempfile.mkdtemp(prefix='quick-test-')

    # Create test environment
    mock_env = MockProcessEnvironment(test_dir)
    mock_env.create_test_processes()
    mock_env.create_procfile()

    # Start daemon
    daemon = OvermindDaemon()
    daemon_task = asyncio.create_task(
        daemon.run(working_directory=test_dir, api_port=9988)
    )

    try:
        # Wait for daemon to start
        await asyncio.sleep(8)

        # Test daemon health
        health_url = "http://127.0.0.1:9988/health"
        with urllib.request.urlopen(health_url) as response:
            health_data = json.loads(response.read().decode())
            print(f"Daemon health: {health_data}")

        # Now test daemon discovery from GUI perspective
        from daemon_discovery import DaemonDiscoveryManager
        discovery = DaemonDiscoveryManager()

        discovered = await discovery.discover_daemons((9985, 9990))
        print(f"Discovered daemons: {discovered}")

        if discovered:
            # Test creating client
            client = await discovery.create_client(
                daemon_info=discovered[0],
                output_callback=lambda line: print(f"Output: {line}"),
                status_callback=lambda status: print(f"Status: {status}")
            )

            if client:
                print(f"Client connected: {client.is_running()}")
                await asyncio.sleep(3)
                await client.stop()
            else:
                print("Failed to create client")
        else:
            print("No daemons discovered")

    except Exception as e:
        print(f"Test error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Stop daemon
        daemon.shutdown_requested = True
        if daemon.instance:
            await daemon.instance.stop()
        daemon_task.cancel()
        try:
            await daemon_task
        except asyncio.CancelledError:
            pass

        # Clean up
        import shutil
        shutil.rmtree(test_dir)


if __name__ == "__main__":
    asyncio.run(test_daemon_gui())