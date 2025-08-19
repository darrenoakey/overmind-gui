"""
Overmind Controller - Async management of overmind process lifecycle
Handles starting/stopping overmind, reading output, and process control
"""

import os
import asyncio
import subprocess
import unittest
import signal
from typing import Optional, Callable, Dict, Any

# Try to import psutil for enhanced process management
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not available - child process cleanup will be limited")


class OvermindController:  # pylint: disable=too-many-instance-attributes
    """Controls overmind process and handles communication"""

    def __init__(self, output_callback: Callable[[str], None] = None,
                 status_callback: Callable[[Dict[str, str]], None] = None,
                 overmind_args: list = None):
        """
        Initialize controller

        Args:
            output_callback: Function to call with each output line
            status_callback: Function to call with status updates
            overmind_args: Additional arguments to pass to overmind start
        """
        self.output_callback = output_callback
        self.status_callback = status_callback
        self.overmind_args = overmind_args or []

        self.process: Optional[Any] = None  # asyncio.subprocess.Process
        self.running = False
        self.working_directory = os.getcwd()

        # Tasks for monitoring
        self._output_task: Optional[asyncio.Task] = None
        self._status_task: Optional[asyncio.Task] = None

    def get_colored_env(self) -> Dict[str, str]:
        """Get environment variables that force color output"""
        env = os.environ.copy()
        # Force color output for overmind and child processes
        env.update({
            'FORCE_COLOR': '1',
            'CLICOLOR_FORCE': '1',
            'TERM': 'xterm-256color',
            'COLORTERM': 'truecolor',
        })
        # Remove NO_COLOR if it exists
        env.pop('NO_COLOR', None)
        return env

    async def start(self) -> bool:
        """
        Start overmind process and monitoring tasks
        Returns True if successful, False otherwise
        """
        try:
            # Check if overmind is available
            result = await asyncio.create_subprocess_exec(
                "overmind", "--version",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await result.wait()
            if result.returncode != 0:
                return False
        except FileNotFoundError:
            print("Overmind binary not found")
            return False

        # Check for existing socket file
        socket_file = os.path.join(self.working_directory, ".overmind.sock")
        if os.path.exists(socket_file):
            print(f"Warning: Socket file {socket_file} already exists")
            # Try to remove it
            try:
                os.unlink(socket_file)
                print("Removed stale socket file")
            except OSError as e:
                print(f"Could not remove socket file: {e}")
                return False

        try:
            # Build overmind start command with additional arguments
            # Add --no-port to prevent port conflicts and force color output
            cmd = ["overmind", "start", "--any-can-die", "--no-port"] + self.overmind_args

            # Get environment with color forcing
            env = self.get_colored_env()
            print("Starting overmind with color support")

            # Start overmind process with color-forcing environment
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.working_directory,
                env=env
            )

            self.running = True
            print(f"Overmind process started with PID: {self.process.pid}")

            # Give overmind a moment to start
            await asyncio.sleep(2)

            # Check if process is still running
            if self.process.returncode is not None:
                print(f"Overmind process exited immediately with code: {self.process.returncode}")
                return False

            # Start monitoring tasks
            self._output_task = asyncio.create_task(self._read_output())
            self._status_task = asyncio.create_task(self._monitor_status())

            return True

        except (OSError, subprocess.SubprocessError) as e:
            print(f"Failed to start overmind: {e}")
            return False

    async def stop(self):
        """Stop overmind and all monitoring tasks with enhanced cleanup"""
        if not self.running:
            return

        self.running = False
        print("Stopping overmind controller...")

        # Cancel monitoring tasks first
        if self._output_task:
            self._output_task.cancel()
            try:
                await self._output_task
            except asyncio.CancelledError:
                pass

        if self._status_task:
            self._status_task.cancel()
            try:
                await self._status_task
            except asyncio.CancelledError:
                pass

        # Now stop overmind itself with enhanced shutdown
        if self.process and self.process.returncode is None:
            await self._graceful_shutdown_overmind()

        # Final cleanup
        await self._cleanup_resources()

    def stop_sync(self):
        """Synchronous version of stop for emergency cleanup"""
        if not self.running:
            return

        print("🚨 EMERGENCY SYNC CLEANUP - Event loop may be shutting down")
        self.running = False

        # Try to stop overmind process synchronously
        if self.process and self.process.returncode is None:
            overmind_pid = self.process.pid
            print(f"🚨 Emergency shutdown of overmind PID {overmind_pid}")

            try:
                # Send signals directly without async
                import time
                
                print("📤 Emergency SIGQUIT...")
                self.process.send_signal(signal.SIGQUIT)
                
                # Wait briefly
                for i in range(5):
                    if self.process.returncode is not None:
                        print("✅ Emergency SIGQUIT successful")
                        break
                    time.sleep(1)
                else:
                    print("📤 Emergency SIGTERM...")
                    self.process.send_signal(signal.SIGTERM)
                    
                    # Wait briefly
                    for i in range(5):
                        if self.process.returncode is not None:
                            print("✅ Emergency SIGTERM successful") 
                            break
                        time.sleep(1)
                    else:
                        print("📤 Emergency SIGKILL...")
                        self.process.kill()
                        time.sleep(1)
                        print("✅ Emergency SIGKILL sent")

            except Exception as e:
                print(f"❌ Emergency cleanup error: {e}")

        # Emergency resource cleanup
        self._cleanup_resources_sync()

    def _cleanup_resources_sync(self):
        """Synchronous resource cleanup"""
        print("🧽 Emergency sync resource cleanup")
        socket_file = os.path.join(self.working_directory, ".overmind.sock")
        
        if os.path.exists(socket_file):
            try:
                os.unlink(socket_file)
                print("✅ Emergency socket cleanup successful")
            except OSError as e:
                print(f"❌ Emergency socket cleanup failed: {e}")
        else:
            print("✅ No socket file to clean up")

        # Emergency child process cleanup if psutil available
        if HAS_PSUTIL and hasattr(self, 'process') and self.process:
            try:
                print("🔍 Emergency child process scan...")
                for proc in psutil.process_iter(['pid', 'ppid', 'name']):
                    try:
                        if 'overmind' in proc.info['name'].lower():
                            print(f"🔥 Emergency kill overmind-related PID {proc.info['pid']}")
                            os.kill(proc.info['pid'], signal.SIGKILL)
                    except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                        continue
            except Exception as e:
                print(f"❌ Emergency child cleanup error: {e}")

    async def _graceful_shutdown_overmind(self):
        """Perform graceful shutdown of overmind with progressive signal escalation"""
        overmind_pid = self.process.pid
        print(f"\n🚦 OVERMIND SHUTDOWN SEQUENCE STARTING (PID: {overmind_pid})")
        print("=" * 50)

        try:
            # Step 1: Send SIGQUIT for graceful shutdown (5 second timeout)
            print(f"📤 [STEP 1] Sending SIGQUIT to PID {overmind_pid} for graceful shutdown...")
            print(f"⏱️  [STEP 1] Waiting 5 seconds for graceful response...")
            self.process.send_signal(signal.SIGQUIT)

            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
                print("✅ [STEP 1] SUCCESS - Overmind shut down gracefully via SIGQUIT")
                return
            except asyncio.TimeoutError:
                print("⚠️  [STEP 1] TIMEOUT - No response to SIGQUIT after 5 seconds")

            # Step 2: Send SIGTERM for forceful shutdown (25 second timeout)  
            print(f"📤 [STEP 2] Sending SIGTERM to PID {overmind_pid} for forceful shutdown...")
            print(f"⏱️  [STEP 2] Waiting 25 seconds for termination...")
            self.process.send_signal(signal.SIGTERM)

            try:
                await asyncio.wait_for(self.process.wait(), timeout=25)
                print("✅ [STEP 2] SUCCESS - Overmind terminated via SIGTERM")
                return
            except asyncio.TimeoutError:
                print("⚠️  [STEP 2] TIMEOUT - No response to SIGTERM after 25 seconds")

            # Step 3: Send SIGKILL for immediate termination
            print(f"📤 [STEP 3] Sending SIGKILL to PID {overmind_pid} for immediate termination...")
            self.process.kill()
            await self.process.wait()
            print("✅ [STEP 3] SUCCESS - Overmind was force-killed via SIGKILL")

        except (OSError, subprocess.SubprocessError, ProcessLookupError) as e:
            print(f"❌ ERROR during overmind shutdown: {e}")
        finally:
            self.process = None
            print("🏁 Overmind process reference cleared")

        # Step 4: Clean up any remaining child processes
        print("\n🧹 CHILD PROCESS CLEANUP STARTING")
        print("=" * 40)
        await self._cleanup_child_processes(overmind_pid)

    async def _cleanup_child_processes(self, overmind_pid: int):
        """Find and cleanup any remaining child processes of overmind"""
        if not HAS_PSUTIL:
            print("⚠️  psutil not available - skipping child process cleanup")
            print("   Install psutil with: pip install psutil")
            return

        try:
            print("🔍 Scanning for remaining overmind child processes...")
            
            # Get all processes and find children of overmind
            child_pids = []
            for proc in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline']):
                try:
                    if proc.info['ppid'] == overmind_pid:
                        child_pids.append(proc.info['pid'])
                        print(f"🔸 Found child process: PID {proc.info['pid']} ({proc.info['name']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Kill remaining child processes
            if child_pids:
                print(f"🔥 Terminating {len(child_pids)} remaining child processes...")
                for pid in child_pids:
                    try:
                        print(f"📤 Sending SIGTERM to child PID {pid}")
                        os.kill(pid, signal.SIGTERM)
                        print(f"✅ SIGTERM sent to child PID {pid}")
                    except (OSError, ProcessLookupError) as e:
                        print(f"⚠️  Could not terminate PID {pid}: {e}")
                
                # Give processes a moment to cleanup, then force kill if needed
                print("⏱️  Waiting 2 seconds for children to respond to SIGTERM...")
                await asyncio.sleep(2)
                
                print("🔍 Checking for any remaining children after SIGTERM...")
                for pid in child_pids:
                    try:
                        if HAS_PSUTIL and psutil.pid_exists(pid):
                            print(f"📤 Force-killing stubborn child PID {pid} with SIGKILL")
                            os.kill(pid, signal.SIGKILL)
                            print(f"✅ SIGKILL sent to child PID {pid}")
                        else:
                            print(f"✅ Child PID {pid} already terminated")
                    except (OSError, ProcessLookupError):
                        print(f"✅ Child PID {pid} already gone")
                        
                print("✅ Child process cleanup completed")
            else:
                print("✅ No child processes found - nothing to clean up")

        except Exception as e:
            print(f"❌ ERROR during child process cleanup: {e}")

    async def _cleanup_resources(self):
        """Clean up overmind socket file and other resources"""
        print("\n🧽 RESOURCE CLEANUP STARTING")
        print("=" * 30)
        
        # Clean up socket file
        socket_file = os.path.join(self.working_directory, ".overmind.sock")
        print(f"🔍 Checking for socket file: {socket_file}")
        
        if os.path.exists(socket_file):
            try:
                print(f"🗑️  Removing socket file: {socket_file}")
                os.unlink(socket_file)
                print("✅ Successfully cleaned up .overmind.sock file")
            except OSError as e:
                print(f"❌ Could not clean up socket file: {e}")
        else:
            print("✅ No socket file found - nothing to clean up")
            
        print("🏁 Resource cleanup completed")

    async def start_process(self, process_name: str) -> bool:
        """Start a specific process"""
        try:
            env = self.get_colored_env()
            process = await asyncio.create_subprocess_exec(
                "overmind", "start", process_name,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            await process.wait()
            return process.returncode == 0
        except (OSError, subprocess.SubprocessError) as e:
            print(f"Failed to start {process_name}: {e}")
            return False

    async def stop_process(self, process_name: str) -> bool:
        """Stop a specific process"""
        try:
            env = self.get_colored_env()
            process = await asyncio.create_subprocess_exec(
                "overmind", "stop", process_name,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            await process.wait()
            return process.returncode == 0
        except (OSError, subprocess.SubprocessError) as e:
            print(f"Failed to stop {process_name}: {e}")
            return False

    async def restart_process(self, process_name: str) -> bool:
        """Restart a specific process"""
        try:
            env = self.get_colored_env()
            process = await asyncio.create_subprocess_exec(
                "overmind", "restart", process_name,
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            await process.wait()
            return process.returncode == 0
        except (OSError, subprocess.SubprocessError) as e:
            print(f"Failed to restart {process_name}: {e}")
            return False

    async def get_status(self) -> Optional[str]:
        """Get current status of all processes"""
        try:
            env = self.get_colored_env()
            process = await asyncio.create_subprocess_exec(
                "overmind", "status",
                cwd=self.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)

            if process.returncode == 0:
                return stdout.decode()
            return None
        except (OSError, subprocess.SubprocessError, asyncio.TimeoutError) as e:
            print(f"Error getting status: {e}")
            return None

    def is_running(self) -> bool:
        """Check if overmind process is running"""
        return self.process is not None and self.process.returncode is None

    async def _read_output(self):
        """Read output from overmind process"""
        if not self.process or not self.process.stdout:
            return

        try:
            while self.running and self.process.returncode is None:
                line = await self.process.stdout.readline()
                if not line:
                    break

                # Decode with error handling for potential encoding issues
                try:
                    line_str = line.decode('utf-8', errors='replace').rstrip('\n')
                except UnicodeDecodeError:
                    # Fallback to latin-1 if utf-8 fails
                    line_str = line.decode('latin-1', errors='replace').rstrip('\n')

                if line_str and self.output_callback:
                    self.output_callback(line_str)

        except (OSError, UnicodeDecodeError) as e:
            if self.running:
                print(f"Error reading output: {e}")

    async def _monitor_status(self):
        """Monitor process status periodically"""
        # Wait a bit for overmind to start up before first status check
        await asyncio.sleep(5)

        while self.running:
            try:
                status_output = await self.get_status()
                if status_output:
                    # Parse status and call callback
                    status_updates = self.parse_status_output(status_output)
                    if status_updates and self.status_callback:
                        self.status_callback(status_updates)

                # Wait 20 seconds or until shutdown
                await asyncio.sleep(20)

            except asyncio.CancelledError:
                break
            except (OSError, subprocess.SubprocessError) as e:
                if self.running:
                    print(f"Error monitoring status: {e}")
                await asyncio.sleep(20)

    def parse_status_output(self, status_text: str) -> Dict[str, str]:
        """Parse overmind status output into dict"""
        status_updates = {}
        lines = status_text.strip().splitlines()

        for line in lines:
            line = line.strip()

            # Skip header line and empty lines
            if not line or "PROCESS" in line or "PID" in line:
                continue

            # Split by whitespace and expect: PROCESS PID STATUS
            parts = line.split()
            if len(parts) >= 3:
                process_name = parts[0]
                status = parts[2]  # Skip PID, take STATUS
                status_updates[process_name] = status

        return status_updates

    def set_working_directory(self, path: str):
        """Set working directory for overmind commands"""
        if os.path.isdir(path):
            self.working_directory = path
        else:
            raise ValueError(f"Invalid directory: {path}")


class TestOvermindController(unittest.TestCase):
    """Test cases for the OvermindController"""

    def test_initialization(self):
        """Test controller initialization"""
        controller = OvermindController()
        self.assertIsNone(controller.output_callback)
        self.assertIsNone(controller.status_callback)
        self.assertEqual(controller.overmind_args, [])
        self.assertIsNone(controller.process)
        self.assertFalse(controller.running)
        self.assertEqual(controller.working_directory, os.getcwd())

    def test_initialization_with_args(self):
        """Test controller initialization with arguments"""
        def mock_callback(_line):  # pylint: disable=unused-argument
            """Mock callback function"""
            return None

        def mock_status_callback(_updates):  # pylint: disable=unused-argument
            """Mock status callback function"""
            return None

        args = ["--test"]
        controller = OvermindController(
            output_callback=mock_callback,
            status_callback=mock_status_callback,
            overmind_args=args
        )
        self.assertEqual(controller.output_callback, mock_callback)
        self.assertEqual(controller.status_callback, mock_status_callback)
        self.assertEqual(controller.overmind_args, args)

    def test_parse_status_output(self):
        """Test parsing of overmind status output"""
        controller = OvermindController()
        status_text = """
PROCESS  PID     STATUS
web      12345   running
worker   12346   stopped
redis    12347   dead
        """
        result = controller.parse_status_output(status_text)
        expected = {
            "web": "running",
            "worker": "stopped",
            "redis": "dead"
        }
        self.assertEqual(result, expected)

    def test_parse_empty_status_output(self):
        """Test parsing empty status output"""
        controller = OvermindController()
        result = controller.parse_status_output("")
        self.assertEqual(result, {})

    def test_set_working_directory(self):
        """Test setting working directory"""
        controller = OvermindController()
        # Test with current directory (should work)
        controller.set_working_directory(os.getcwd())
        self.assertEqual(controller.working_directory, os.getcwd())

        # Test with invalid directory
        with self.assertRaises(ValueError):
            controller.set_working_directory("/invalid/path/that/does/not/exist")

    def test_is_running_initial_state(self):
        """Test is_running returns False initially"""
        controller = OvermindController()
        self.assertFalse(controller.is_running())

    def test_get_colored_env(self):
        """Test environment variables for color output"""
        controller = OvermindController()
        env = controller.get_colored_env()

        # Check that color-forcing variables are set
        self.assertEqual(env['FORCE_COLOR'], '1')
        self.assertEqual(env['CLICOLOR_FORCE'], '1')
        self.assertEqual(env['TERM'], 'xterm-256color')
        self.assertEqual(env['COLORTERM'], 'truecolor')

        # Check that NO_COLOR is not present
        self.assertNotIn('NO_COLOR', env)
