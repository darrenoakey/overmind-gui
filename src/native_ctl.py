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
    daemon_pid = get_daemon_pid(working_dir)

    # Read process information from database
    import sqlite3
    db_path = os.path.join(working_dir, "overmind.db")

    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Check if process_status table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='process_status'"
            )
            has_status_table = cursor.fetchone() is not None

            if has_status_table:
                # Get from process_status table (preferred)
                cursor = conn.execute("""
                    SELECT process_name, status, pid
                    FROM process_status
                    ORDER BY process_name
                """)

                processes = cursor.fetchall()

                print(f"Native Daemon (PID {daemon_pid})")
                print()
                print("PROCESS         PID      STATUS")
                print("-" * 40)

                if processes:
                    for row in processes:
                        process_name = row['process_name']
                        status = row['status']
                        pid = row['pid'] if row['pid'] else '-'
                        print(f"{process_name:<15} {str(pid):<8} {status}")
                else:
                    print("  (No processes found)")
            else:
                # Fallback: read from output_lines
                print(f"Native Daemon (PID {daemon_pid})")
                print()
                print("  (Process status table not available - daemon may need restart)")

    except Exception as e:
        print(f"Error reading process status: {e}")
        sys.exit(1)


def _send_daemon_command(working_dir: str, command: str, process_name: str):
    """Send a command to the daemon via database"""
    import sqlite3

    db_path = os.path.join(working_dir, "overmind.db")

    if not os.path.exists(db_path):
        print(f"Error: Database not found at {db_path}")
        sys.exit(1)

    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "INSERT INTO daemon_commands (command, process_name, timestamp) VALUES (?, ?, ?)",
                (command, process_name, time.time())
            )
            conn.commit()
        print(f"{command.capitalize()} command sent for {process_name}")
    except Exception as e:
        print(f"Error sending command: {e}")
        sys.exit(1)


def cmd_start(args):
    """Start a process"""
    if not args.process:
        print("Error: process name required")
        sys.exit(1)

    working_dir = args.working_dir or os.getcwd()
    _send_daemon_command(working_dir, "start", args.process)


def cmd_stop(args):
    """Stop a process"""
    if not args.process:
        print("Error: process name required")
        sys.exit(1)

    working_dir = args.working_dir or os.getcwd()
    _send_daemon_command(working_dir, "stop", args.process)


def cmd_restart(args):
    """Restart a process"""
    if not args.process:
        print("Error: process name required")
        sys.exit(1)

    working_dir = args.working_dir or os.getcwd()
    _send_daemon_command(working_dir, "restart", args.process)


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

    # start command
    start_parser = subparsers.add_parser("start", help="Start a process")
    start_parser.add_argument("process", help="Process name to start")
    start_parser.set_defaults(func=cmd_start)

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
