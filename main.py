"""Main orchestrator for overmindgui multi-process application."""

import signal
import sys
import unittest
from multiprocessing import Process, Queue

from config import AppConfig, find_free_port
from process_sanic import sanic_main
from process_overmind import overmind_main
from process_frontend import frontend_main


class OvermindOrchestrator:
    """Orchestrates all processes and handles shutdown."""

    def __init__(self):
        self.processes = []
        self.config = None
        self.shutdown_requested = False

    def signal_handler(self, _signum, _frame):
        """Handle SIGINT (Ctrl+C) for graceful shutdown."""
        if self.shutdown_requested:
            print("\nForced shutdown...")
            sys.exit(1)

        print("\nShutdown requested... sending stop messages")
        self.shutdown_requested = True

        if self.config:
            # Send stop messages to all queues
            try:
                self.config.sanic_queue.put_nowait({'type': 'stop'})
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            try:
                self.config.overmind_queue.put_nowait({'type': 'stop'})
            except Exception:  # pylint: disable=broad-exception-caught
                pass
            try:
                self.config.frontend_queue.put_nowait({'type': 'stop'})
            except Exception:  # pylint: disable=broad-exception-caught
                pass

    def start_processes(self):
        """Start all processes."""
        # Find free port
        port = find_free_port()
        print(f"Using port: {port}")

        # Create queues
        sanic_queue = Queue()
        overmind_queue = Queue()
        frontend_queue = Queue()

        # Create config
        self.config = AppConfig(
            port=port,
            sanic_queue=sanic_queue,
            overmind_queue=overmind_queue,
            frontend_queue=frontend_queue
        )

        config_dict = self.config.to_dict()

        # Start processes
        sanic_process = Process(target=sanic_main, args=(config_dict,), name="sanic")
        overmind_process = Process(target=overmind_main, args=(config_dict,), name="overmind")
        frontend_process = Process(target=frontend_main, args=(config_dict,), name="frontend")

        self.processes = [sanic_process, overmind_process, frontend_process]

        print("Starting processes...")
        for process in self.processes:
            process.start()
            print(f"Started {process.name} process (PID: {process.pid})")

    def wait_for_processes(self):
        """Wait for all processes to finish."""
        try:
            for process in self.processes:
                process.join()
        except KeyboardInterrupt:
            # This shouldn't happen since we handle SIGINT
            pass

    def cleanup(self):
        """Clean up any remaining processes."""
        for process in self.processes:
            if process.is_alive():
                print(f"Terminating {process.name} process...")
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    print(f"Force killing {process.name} process...")
                    process.kill()


def main():
    """Main entry point."""
    orchestrator = OvermindOrchestrator()

    # Set up signal handler
    signal.signal(signal.SIGINT, orchestrator.signal_handler)

    try:
        orchestrator.start_processes()
        print("All processes started. Press Ctrl+C to shutdown.")
        orchestrator.wait_for_processes()
    except Exception as e:  # pylint: disable=broad-exception-caught
        print(f"Error: {e}")
    finally:
        orchestrator.cleanup()
        print("Shutdown complete.")


class TestMain(unittest.TestCase):
    """Test cases for main orchestrator."""

    def test_orchestrator_creation(self):
        """Test that orchestrator can be created."""
        orchestrator = OvermindOrchestrator()
        self.assertIsNotNone(orchestrator)
        self.assertEqual(len(orchestrator.processes), 0)
        self.assertFalse(orchestrator.shutdown_requested)

    def test_signal_handler_sets_flag(self):
        """Test that signal handler sets shutdown flag."""
        orchestrator = OvermindOrchestrator()
        orchestrator.signal_handler(signal.SIGINT, None)
        self.assertTrue(orchestrator.shutdown_requested)


if __name__ == "__main__":
    main()
