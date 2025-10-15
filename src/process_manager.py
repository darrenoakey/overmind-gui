"""
Process Manager - Data model for Procfile processes
Handles process state, output buffering, and status tracking for web GUI
"""

import json
import os
import re
import time
from collections import deque
from typing import Dict, List, Optional, Any


class ProcessInfo:
    """Information about a single process from the Procfile"""

    def __init__(self, name: str):
        self.name = name
        self.status: str = "unknown"  # running, stopped, disabled, dead, broken
        self.selected: bool = True  # whether output should be shown
        self.output_lines: deque = deque(maxlen=5000)  # circular buffer for output
        self.user_disabled: bool = False  # user explicitly stopped this process
        self.last_restart_time: float = time.time()  # when process was last restarted
        self.broken: bool = False  # whether process has warning patterns
        self.warning_patterns: List[str] = []  # warning patterns to look for

    def add_output(self, line: str) -> Optional[str]:
        """
        Add a line of output to this process
        Returns the matched failure string if a failure pattern is detected, None otherwise
        """
        self.output_lines.append(line)

        # Check for warning patterns (failure declarations) if we have any configured
        if self.warning_patterns and not self.broken:
            return self._check_for_warnings(line)
        return None

    def _check_for_warnings(self, line: str) -> Optional[str]:
        """
        Check if output line contains any warning patterns (failure declarations)
        Returns the matched failure string if found, None otherwise
        """
        line_lower = line.lower()
        for pattern in self.warning_patterns:
            if pattern.lower() in line_lower:
                self.broken = True
                self.status = "broken"
                return pattern  # Return the matched pattern
        return None

    def get_all_output(self) -> List[str]:
        """Get all output lines for this process"""
        return list(self.output_lines)

    def clear_output(self):
        """Clear all stored output"""
        self.output_lines.clear()

    def set_status(self, status: str):
        """Update process status"""
        old_status = self.status
        self.status = status.lower()

        # If process is starting/running again, clear broken status and update restart time
        if old_status in ("stopped", "dead", "disabled") and self.status == "running":
            self.restart()

    def restart(self):
        """Mark process as restarted - clears broken status and updates restart time"""
        self.last_restart_time = time.time()
        self.broken = False  # Clear failure detection state on restart
        # If currently broken, reset status back to unknown
        if self.status == "broken":
            self.status = "unknown"

        # Add restart separator to logs
        for _ in range(40):
            self.output_lines.append("")
        self.output_lines.append(f"🔄 Process {self.name} restarted at {time.strftime('%H:%M:%S')}")

    def set_warning_patterns(self, patterns: List[str]):
        """Set warning patterns to monitor for this process"""
        self.warning_patterns = patterns

    def is_running(self) -> bool:
        """Check if process is currently running"""
        return self.status == "running"

    def is_stopped(self) -> bool:
        """Check if process is stopped"""
        return self.status in ("stopped", "disabled")

    def is_dead(self) -> bool:
        """Check if process has crashed/died"""
        return self.status == "dead"

    def is_broken(self) -> bool:
        """Check if process has detected warning patterns"""
        return self.status == "broken" or self.broken

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "name": self.name,
            "status": self.status,
            "selected": self.selected,
            "user_disabled": self.user_disabled,
            "output_count": len(self.output_lines),
            "broken": self.broken,
            "last_restart_time": self.last_restart_time,
            "warning_patterns": self.warning_patterns,
        }


class ProcessManager:
    """Manages collection of processes and their state"""

    def __init__(self, working_directory: Optional[str] = None):
        self.processes: Dict[str, ProcessInfo] = {}
        self.failure_declarations: Dict[str, List[str]] = {}  # {process_name: [failure_strings]}
        self.working_directory = working_directory or os.getcwd()
        self._load_failure_declarations()

    def _get_failure_declarations_path(self) -> str:
        """Get path to failure_declarations.json in the same directory as the Procfile"""
        return os.path.join(self.working_directory, "failure_declarations.json")

    def _load_failure_declarations(self):
        """Load failure declarations from failure_declarations.json in Procfile directory"""
        config_path = self._get_failure_declarations_path()

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    self.failure_declarations = json.load(f)
                print(f"✅ Loaded failure declarations for {len(self.failure_declarations)} processes from {config_path}")
            except (json.JSONDecodeError, OSError) as e:
                print(f"⚠️ Could not load failure declarations from {config_path}: {e}")
                self.failure_declarations = {}
        else:
            print(f"ℹ️ No failure declarations found at {config_path}")
            self.failure_declarations = {}

    def save_failure_declarations(self) -> bool:
        """Save failure declarations to failure_declarations.json"""
        config_path = self._get_failure_declarations_path()
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.failure_declarations, f, indent=2)
            print(f"✅ Saved failure declarations to {config_path}")
            return True
        except OSError as e:
            print(f"❌ Failed to save failure declarations to {config_path}: {e}")
            return False

    def add_failure_declaration(self, process_name: str, failure_string: str) -> bool:
        """Add a failure declaration for a process"""
        if process_name not in self.failure_declarations:
            self.failure_declarations[process_name] = []

        # Don't add duplicates
        if failure_string not in self.failure_declarations[process_name]:
            self.failure_declarations[process_name].append(failure_string)
            return self.save_failure_declarations()
        return True

    def remove_failure_declaration(self, process_name: str, failure_string: str) -> bool:
        """Remove a failure declaration for a process"""
        if process_name in self.failure_declarations:
            if failure_string in self.failure_declarations[process_name]:
                self.failure_declarations[process_name].remove(failure_string)

                # Remove empty lists
                if not self.failure_declarations[process_name]:
                    del self.failure_declarations[process_name]

                return self.save_failure_declarations()
        return True

    def get_failure_declarations(self, process_name: str) -> List[str]:
        """Get failure declarations for a specific process"""
        return self.failure_declarations.get(process_name, [])

    def load_procfile(self, procfile_path: str = "Procfile") -> List[str]:
        """
        Load processes from Procfile
        Returns list of process names found
        """
        process_names = []

        try:
            with open(procfile_path, "r", encoding="utf - 8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and ":" in line:
                        process_name = line.split(":", 1)[0].strip()
                        if process_name not in self.processes:
                            process = ProcessInfo(process_name)

                            # Apply failure declarations if configured
                            if process_name in self.failure_declarations:
                                process.set_warning_patterns(self.failure_declarations[process_name])
                                print(
                                    f"Applied {len(self.failure_declarations[process_name])} "
                                    f"failure declarations to {process_name}"
                                )

                            self.processes[process_name] = process
                            process_names.append(process_name)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"Procfile not found at {procfile_path}") from exc

        return process_names

    def get_process(self, name: str) -> Optional[ProcessInfo]:
        """Get a process by name"""
        return self.processes.get(name)

    def get_all_processes(self) -> Dict[str, ProcessInfo]:
        """Get all processes"""
        return self.processes.copy()

    def get_process_names(self) -> List[str]:
        """Get list of all process names"""
        return list(self.processes.keys())

    def get_selected_processes(self) -> List[ProcessInfo]:
        """Get list of processes that are selected for output"""
        return [p for p in self.processes.values() if p.selected]

    def toggle_process_selection(self, name: str) -> bool:
        """
        Toggle whether a process is selected for output
        Returns new selection state
        """
        if name in self.processes:
            self.processes[name].selected = not self.processes[name].selected
            return self.processes[name].selected
        return False

    def select_all_processes(self):
        """Select all processes for output"""
        for process in self.processes.values():
            process.selected = True

    def deselect_all_processes(self):
        """Deselect all processes from output"""
        for process in self.processes.values():
            process.selected = False

    def restart_process(self, name: str):
        """Mark a process as restarted (clears broken status)"""
        if name in self.processes:
            self.processes[name].restart()

    def add_output_line(self, line: str) -> tuple[Optional[str], Optional[str]]:
        """
        Add an output line, parsing which process it belongs to
        Returns (process_name, failure_pattern) tuple
        - process_name: the name of the process if identified, None otherwise
        - failure_pattern: the matched failure pattern if detected, None otherwise
        """
        # Parse overmind format: "processname | actual output"
        if " | " in line:
            parts = line.split(" | ", 1)
            if len(parts) == 2:
                process_part = parts[0].strip()

                # Clean process name (remove ANSI codes and timestamps)
                clean_name = re.sub(r"\x1b\[[0 - 9;]*m", "", process_part)
                clean_name = re.sub(r"\d{2}:\d{2}:\d{2}\s+", "", clean_name).strip()

                if clean_name in self.processes:
                    failure_pattern = self.processes[clean_name].add_output(line)
                    return (clean_name, failure_pattern)

        return (None, None)

    def update_process_status(self, name: str, status: str):
        """Update status of a specific process"""
        if name in self.processes:
            self.processes[name].set_status(status)

    def get_combined_output(self, selected_only: bool = True) -> List[str]:
        """
        Get combined output from all processes
        If selected_only=True, only include selected processes
        """
        all_lines = []

        processes_to_include = self.get_selected_processes() if selected_only else self.processes.values()

        for process in processes_to_include:
            all_lines.extend(process.get_all_output())

        return all_lines

    def clear_all_output(self):
        """Clear output from all processes"""
        for process in self.processes.values():
            process.clear_output()

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about processes"""
        stats = {"total": len(self.processes), "running": 0, "stopped": 0, "dead": 0, "broken": 0, "selected": 0}

        for process in self.processes.values():
            if process.is_broken():
                stats["broken"] += 1
            elif process.is_running():
                stats["running"] += 1
            elif process.is_dead():
                stats["dead"] += 1
            else:
                stats["stopped"] += 1

            if process.selected:
                stats["selected"] += 1

        return stats

    def to_dict(self) -> Dict[str, Any]:
        """Convert entire state to dictionary for JSON serialization"""
        return {
            "processes": {name: proc.to_dict() for name, proc in self.processes.items()},
            "stats": self.get_stats(),
            "failure_declarations": self.failure_declarations,
        }
