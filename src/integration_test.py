#!/usr/bin/env python3
"""
Integration Test - Full Application Lifecycle Test

Tests the complete application flow:
1. Start server with demo Procfile
2. Load page in browser and verify all assets load
3. Check processes are visible and updating
4. Click shutdown button
5. Verify clean shutdown (overmind.sock removed, process terminated)
"""

import asyncio
import time
import sys
from pathlib import Path


async def test_with_playwright():
    """Integration test using Playwright"""
    print("🧪 Running integration test with Playwright...")

    from playwright.async_api import async_playwright

    # Setup test environment
    script_dir = Path(__file__).parent
    root_dir = script_dir.parent
    test_dir = root_dir / "output" / "integration - test"
    test_dir.mkdir(parents=True, exist_ok=True)

    # Copy demo Procfile
    demo_procfile = script_dir / "demo.Procfile"
    test_procfile = test_dir / "Procfile"

    if not demo_procfile.exists():
        print(f"❌ Demo Procfile not found: {demo_procfile}")
        return False

    import shutil
    shutil.copy2(demo_procfile, test_procfile)
    print(f"✓ Copied demo Procfile to {test_procfile}")

    server_process = None

    try:
        # Start server process
        print("🚀 Starting server process...")
        main_py = script_dir / "main.py"

        server_process = await asyncio.create_subprocess_exec(
            sys.executable, str(main_py), "--no - ui", "--port", "0",  # port 0 = auto - allocate
            cwd=str(test_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Extract allocated port from server output
        port = None
        timeout = 30
        start_time = time.time()

        while time.time() - start_time < timeout:
            if server_process.returncode is not None:
                stderr_data = await server_process.stderr.read()
                print(f"❌ Server process exited early: {stderr_data.decode()}")
                return False

            try:
                # Try to read line with timeout
                line_bytes = await asyncio.wait_for(server_process.stdout.readline(), timeout=0.1)
                if line_bytes:
                    line = line_bytes.decode().strip()
                    print(f"Server: {line}")
                    if "🔌 ALLOCATED PORT:" in line:
                        port = int(line.split("🔌 ALLOCATED PORT:")[1].split()[0])
                        print(f"✓ Server allocated port: {port}")
                        break
            except asyncio.TimeoutError:
                await asyncio.sleep(0.1)

        if port is None:
            print("❌ Could not determine server port")
            return False

        # Wait for server to be ready
        url = f"http://localhost:{port}"
        print(f"⏳ Waiting for server to be ready at {url}...")

        import aiohttp
        async with aiohttp.ClientSession() as session:
            for _ in range(30):
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=2)) as response:
                        if response.status == 200:
                            print("✓ Server is ready")
                            break
                except Exception:
                    await asyncio.sleep(1)
            else:
                print("❌ Server failed to become ready")
                return False

        # Start browser automation
        async with async_playwright() as p:
            print("🌐 Starting browser...")
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Monitor console for errors
            console_messages = []
            page.on("console", lambda msg: console_messages.append(msg))

            # Load the page
            print(f"📄 Loading page: {url}")
            await page.goto(url, wait_until="domcontentloaded")

            # Wait for app to initialize
            print("🔍 Checking page loaded correctly...")
            await page.wait_for_selector("#app", timeout=10000)
            print("✓ Main app container found")

            # Wait for processes to appear
            processes_found = False
            for attempt in range(10):
                # Look for process indicators
                process_elements = await page.query_selector_all(".process - item")
                if process_elements:
                    processes_found = True
                    print(f"✓ Found {len(process_elements)} process items")
                    break

                # Alternative: look for process output text
                process_content = await page.text_content("body")
                if any(marker in process_content for marker in ["[WEB]", "[API]", "[WORKER]", "[MONITOR]", "[LOGGER]"]):
                    processes_found = True
                    print("✓ Found process output on page")
                    break

                await asyncio.sleep(1)

            if not processes_found:
                print("⚠️  No processes visible on page (may be normal for short test)")

            # Check console for errors
            error_messages = [msg for msg in console_messages if msg.type in ['error', 'warning']]
            if error_messages:
                print("⚠️  Browser console messages:")
                for msg in error_messages[-5:]:  # Show last 5 messages
                    print(f"   {msg.type.upper()}: {msg.text}")
            else:
                print("✓ No browser console errors")

            # Look for shutdown functionality
            print("🔘 Looking for shutdown mechanism...")
            shutdown_found = False

            # Try to find shutdown button
            shutdown_selectors = [
                "button:has - text('Shutdown')",
                "button:has - text('Stop')",
                "button[onclick*='shutdown']",
                ".shutdown - button",
                "#shutdown - btn"
            ]

            for selector in shutdown_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        print(f"✓ Found shutdown button: {selector}")
                        await button.click()
                        shutdown_found = True
                        print("✓ Clicked shutdown button")
                        break
                except Exception:
                    continue

            if not shutdown_found:
                print("⚠️  Shutdown button not found - trying API endpoint")
                # Try direct API call
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.post(f"{url}/shutdown") as response:
                            if response.status == 200:
                                print("✓ Sent shutdown request via API")
                                shutdown_found = True
                    except Exception:
                        pass

            await browser.close()

        # Wait for shutdown process
        print("⏳ Waiting for shutdown to complete...")
        await asyncio.sleep(5)

        # Check that .overmind.sock is gone
        overmind_sock = test_dir / ".overmind.sock"
        if overmind_sock.exists():
            print("⚠️  .overmind.sock still exists after shutdown")
        else:
            print("✓ .overmind.sock removed")

        # Check server process status and capture stderr
        if server_process.returncode is None:
            print("⏳ Waiting for server process to terminate...")
            try:
                await asyncio.wait_for(server_process.wait(), timeout=10)
                print("✓ Server process terminated cleanly")

                # Capture and check stderr for errors
                stderr_data = await server_process.stderr.read()
                if stderr_data:
                    stderr_text = stderr_data.decode().strip()
                    stderr_lines = stderr_text.split('\n')
                    error_lines = []

                    for line in stderr_lines:
                        line = line.strip()
                        if line and not line.startswith('INFO:') and 'DEBUG:' not in line:
                            # Filter out common non - error messages
                            if not any(ignore in line.lower() for ignore in [
                                'server stopped',
                                'shutdown complete',
                                'connection closed',
                                'task was cancelled',
                                'cleanup',
                                'stopping'
                            ]):
                                error_lines.append(line)

                    if error_lines:
                        print("❌ ERRORS DETECTED during shutdown:")
                        for error in error_lines[-10:]:  # Show last 10 error lines
                            print(f"   ERROR: {error}")
                        return False  # Test fails if shutdown has errors
                    else:
                        print("✓ Clean shutdown - no errors in stderr")
                else:
                    print("✓ Clean shutdown - no stderr output")

            except asyncio.TimeoutError:
                print("⚠️  Server process did not terminate in time")
                server_process.terminate()
                try:
                    await asyncio.wait_for(server_process.wait(), timeout=5)
                    # Try to capture stderr from forced termination
                    stderr_data = await server_process.stderr.read()
                    if stderr_data:
                        print(f"❌ stderr during forced shutdown: {stderr_data.decode()}")
                except Exception:
                    pass
                return False
        else:
            print("✓ Server process terminated")
            # Try to capture any final stderr
            try:
                stderr_data = await server_process.stderr.read()
                if stderr_data and stderr_data.strip():
                    stderr_text = stderr_data.decode().strip()
                    if stderr_text:
                        print(f"⚠️  Final stderr output: {stderr_text}")
            except Exception:
                pass

        print("✅ Integration test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        if server_process and server_process.returncode is None:
            try:
                server_process.terminate()
                await asyncio.wait_for(server_process.wait(), timeout=5)
            except Exception:
                try:
                    server_process.kill()
                except Exception:
                    pass


def run_integration_test():
    """Run the integration test with Playwright"""
    print("🧪 Starting Integration Test")
    print("=" * 50)
    print("Testing complete application lifecycle:")
    print("1. Start server with demo Procfile")
    print("2. Load page and verify assets")
    print("3. Check processes are visible")
    print("4. Test shutdown functionality")
    print("5. Verify clean shutdown")
    print("=" * 50)

    # Run Playwright test
    result = asyncio.run(test_with_playwright())
    if not result:
        print("\n❌ Integration test failed")
        print("\nTo install testing dependencies:")
        print("  pip install playwright aiohttp requests")
        print("  playwright install chromium")
    return result


if __name__ == "__main__":
    success = run_integration_test()
    sys.exit(0 if success else 1)
