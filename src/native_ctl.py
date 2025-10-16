#!/usr/bin/env python3
"""
Native Control CLI - Command-line interface for native daemon
Provides commands like: ps, restart, stop, quit (similar to overmind commands)
"""

import argparse
import json
import os
import signal
import sys
import time


def get_daemon_pid(working_dir: str) -> int:
    """Get daemon PID from PID file"""
    pid_file = os.path.join(working_dir, "overmind-daemon.pid")

    if not os.path.exists(pid_file):
        print("Error: No daemon running (PID file not found)")
        print(f"  Expected PID file: {pid_file}")
        sys.exit(1)

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())

        # Verify process exists
        try:
            os.kill(pid, 0)
            return pid
        except OSError:
            print(f"Error: Daemon PID {pid} is not running (stale PID file)")
            sys.exit(1)

    except (ValueError, OSError) as e:
        print(f"Error reading PID file: {e}")
        sys.exit(1)


def get_socket_path(working_dir: str) -> str:
    """Get socket path for daemon communication"""
    return os.path.join(working_dir, ".native-daemon.sock")


def cmd_ps(args):
    """Show process status"""
    working_dir = args.working_dir or os.getcwd()

    # Get daemon PID
    pid = get_daemon_pid(working_dir)

    print(f"Native Daemon (PID {pid})")
    print()

    # Try to load process status from daemon's state
    # For now, just show that daemon is running
    # In a full implementation, this would communicate with daemon via socket/API

    print("Processes:")
    print("  (Process status available via GUI API)")
    print()
    print("Note: Use the web GUI to see detailed process status")


def cmd_restart(args):
    """Restart a process"""
    if not args.process:
        print("Error: process name required")
        print("Usage: native_ctl restart <process_name>")
        sys.exit(1)

    working_dir = args.working_dir or os.getcwd()
    process_name = args.process

    print(f"Restarting process: {process_name}")
    print()
    print("Note: Process restart is available via the web GUI API")
    print("      The native daemon doesn't support direct CLI restart yet")
    print("      Use the GUI or make an API call to /api/restart")


def cmd_stop(args):
    """Stop a process"""
    if not args.process:
        print("Error: process name required")
        print("Usage: native_ctl stop <process_name>")
        sys.exit(1)

    working_dir = args.working_dir or os.getcwd()
    process_name = args.process

    print(f"Stopping process: {process_name}")
    print()
    print("Note: Process stop is available via the web GUI API")
    print("      The native daemon doesn't support direct CLI stop yet")
    print("      Use the GUI or make an API call to /api/stop")


def cmd_quit(args):
    """Quit the daemon"""
    working_dir = args.working_dir or os.getcwd()

    pid = get_daemon_pid(working_dir)

    print(f"Stopping native daemon (PID {pid})...")

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)

        # Wait for daemon to exit
        for i in range(30):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                # Process no longer exists
                print("✓ Daemon stopped successfully")
                return

        # If still running, warn
        print("Warning: Daemon did not stop within 15 seconds")
        print(f"  You may need to manually kill PID {pid}")

    except OSError as e:
        print(f"Error stopping daemon: {e}")
        sys.exit(1)


def cmd_status(args):
    """Show daemon status"""
    working_dir = args.working_dir or os.getcwd()

    try:
        pid = get_daemon_pid(working_dir)
        print(f"✓ Native daemon is running (PID {pid})")
        print(f"  Working directory: {working_dir}")
        print(f"  PID file: {os.path.join(working_dir, 'overmind-daemon.pid')}")
        print(f"  Database: {os.path.join(working_dir, 'overmind.db')}")
    except SystemExit:
        print("✗ Native daemon is not running")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Native Control - CLI for native daemon (overmind replacement)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  ps               Show process status
  restart <proc>   Restart a process
  stop <proc>      Stop a process
  quit             Stop the daemon and all processes
  status           Show daemon status

Examples:
  native_ctl ps
  native_ctl restart web
  native_ctl stop api
  native_ctl quit
""",
    )

    parser.add_argument("--working-dir", "-d", type=str, help="Working directory (default: current directory)")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # ps command
    ps_parser = subparsers.add_parser("ps", help="Show process status")
    ps_parser.set_defaults(func=cmd_ps)

    # restart command
    restart_parser = subparsers.add_parser("restart", help="Restart a process")
    restart_parser.add_argument("process", help="Process name to restart")
    restart_parser.set_defaults(func=cmd_restart)

    # stop command
    stop_parser = subparsers.add_parser("stop", help="Stop a process")
    stop_parser.add_argument("process", help="Process name to stop")
    stop_parser.set_defaults(func=cmd_stop)

    # quit command
    quit_parser = subparsers.add_parser("quit", help="Stop daemon and all processes")
    quit_parser.set_defaults(func=cmd_quit)

    # status command
    status_parser = subparsers.add_parser("status", help="Show daemon status")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Execute command
    args.func(args)


if __name__ == "__main__":
    main()
