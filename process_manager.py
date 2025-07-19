"""
Process Manager - Data model for Procfile processes
Handles process state, output buffering, and status tracking for web GUI
"""

import re
import unittest
from collections import deque
from typing import Dict, List, Optional, Any


class ProcessInfo:
    """Information about a single process from the Procfile"""

    def __init__(self, name: str):
        self.name = name
        self.status: str = "unknown"        # running, stopped, disabled, dead
        self.selected: bool = True          # whether output should be shown
        self.output_lines: deque = deque(maxlen=10000)  # circular buffer for output
        self.user_disabled: bool = False    # user explicitly stopped this process

    def add_output(self, line: str):
        """Add a line of output to this process"""
        self.output_lines.append(line)

    def get_all_output(self) -> List[str]:
        """Get all output lines for this process"""
        return list(self.output_lines)

    def clear_output(self):
        """Clear all stored output"""
        self.output_lines.clear()

    def set_status(self, status: str):
        """Update process status"""
        self.status = status.lower()

    def is_running(self) -> bool:
        """Check if process is currently running"""
        return self.status == "running"

    def is_stopped(self) -> bool:
        """Check if process is stopped"""
        return self.status in ("stopped", "disabled")

    def is_dead(self) -> bool:
        """Check if process has crashed/died"""
        return self.status == "dead"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'status': self.status,
            'selected': self.selected,
            'user_disabled': self.user_disabled,
            'output_count': len(self.output_lines)
        }


class ProcessManager:
    """Manages collection of processes and their state"""

    def __init__(self):
        self.processes: Dict[str, ProcessInfo] = {}

    def load_procfile(self, procfile_path: str = "Procfile") -> List[str]:
        """
        Load processes from Procfile
        Returns list of process names found
        """
        process_names = []

        try:
            with open(procfile_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and ":" in line:
                        process_name = line.split(":", 1)[0].strip()
                        if process_name not in self.processes:
                            self.processes[process_name] = ProcessInfo(process_name)
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

    def add_output_line(self, line: str) -> Optional[str]:
        """
        Add an output line, parsing which process it belongs to
        Returns the process name if identified, None otherwise
        """
        # Parse overmind format: "processname | actual output"
        if " | " in line:
            parts = line.split(" | ", 1)
            if len(parts) == 2:
                process_part = parts[0].strip()

                # Clean process name (remove ANSI codes and timestamps)
                clean_name = re.sub(r'\x1b\[[0-9;]*m', '', process_part)
                clean_name = re.sub(r'\d{2}:\d{2}:\d{2}\s+', '', clean_name).strip()

                if clean_name in self.processes:
                    self.processes[clean_name].add_output(line)
                    return clean_name

        return None

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

        processes_to_include = (
            self.get_selected_processes() if selected_only
            else self.processes.values()
        )

        for process in processes_to_include:
            all_lines.extend(process.get_all_output())

        return all_lines

    def clear_all_output(self):
        """Clear output from all processes"""
        for process in self.processes.values():
            process.clear_output()

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about processes"""
        stats = {
            "total": len(self.processes),
            "running": 0,
            "stopped": 0,
            "dead": 0,
            "selected": 0
        }

        for process in self.processes.values():
            if process.is_running():
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
            'processes': {name: proc.to_dict() for name, proc in self.processes.items()},
            'stats': self.get_stats()
        }


class TestProcessInfo(unittest.TestCase):
    """Test cases for ProcessInfo class"""

    def test_initialization(self):
        """Test ProcessInfo initialization"""
        process = ProcessInfo("test_process")
        self.assertEqual(process.name, "test_process")
        self.assertEqual(process.status, "unknown")
        self.assertTrue(process.selected)
        self.assertFalse(process.user_disabled)
        self.assertEqual(len(process.output_lines), 0)

    def test_add_output(self):
        """Test adding output lines"""
        process = ProcessInfo("test")
        process.add_output("line 1")
        process.add_output("line 2")
        self.assertEqual(len(process.output_lines), 2)
        self.assertEqual(process.get_all_output(), ["line 1", "line 2"])

    def test_clear_output(self):
        """Test clearing output"""
        process = ProcessInfo("test")
        process.add_output("line 1")
        process.clear_output()
        self.assertEqual(len(process.output_lines), 0)

    def test_set_status(self):
        """Test setting process status"""
        process = ProcessInfo("test")
        process.set_status("RUNNING")
        self.assertEqual(process.status, "running")

    def test_status_checks(self):
        """Test status checking methods"""
        process = ProcessInfo("test")

        process.set_status("running")
        self.assertTrue(process.is_running())
        self.assertFalse(process.is_stopped())
        self.assertFalse(process.is_dead())

        process.set_status("stopped")
        self.assertFalse(process.is_running())
        self.assertTrue(process.is_stopped())
        self.assertFalse(process.is_dead())

        process.set_status("dead")
        self.assertFalse(process.is_running())
        self.assertFalse(process.is_stopped())
        self.assertTrue(process.is_dead())

    def test_to_dict(self):
        """Test conversion to dictionary"""
        process = ProcessInfo("test")
        process.add_output("test line")
        result = process.to_dict()

        expected_keys = ['name', 'status', 'selected', 'user_disabled', 'output_count']
        self.assertEqual(set(result.keys()), set(expected_keys))
        self.assertEqual(result['name'], 'test')
        self.assertEqual(result['output_count'], 1)


class TestProcessManager(unittest.TestCase):
    """Test cases for ProcessManager class"""

    def test_initialization(self):
        """Test ProcessManager initialization"""
        manager = ProcessManager()
        self.assertEqual(len(manager.processes), 0)

    def test_add_output_line_parsing(self):
        """Test parsing of output lines"""
        manager = ProcessManager()
        # First add a process
        manager.processes["web"] = ProcessInfo("web")

        # Test valid overmind format
        result = manager.add_output_line("web | Starting server...")
        self.assertEqual(result, "web")

        # Test invalid format
        result = manager.add_output_line("invalid line")
        self.assertIsNone(result)

    def test_toggle_process_selection(self):
        """Test toggling process selection"""
        manager = ProcessManager()
        manager.processes["test"] = ProcessInfo("test")

        # Initially selected
        self.assertTrue(manager.processes["test"].selected)

        # Toggle to deselected
        result = manager.toggle_process_selection("test")
        self.assertFalse(result)
        self.assertFalse(manager.processes["test"].selected)

        # Toggle back to selected
        result = manager.toggle_process_selection("test")
        self.assertTrue(result)
        self.assertTrue(manager.processes["test"].selected)

    def test_get_stats(self):
        """Test getting process statistics"""
        manager = ProcessManager()
        manager.processes["web"] = ProcessInfo("web")
        manager.processes["worker"] = ProcessInfo("worker")

        manager.processes["web"].set_status("running")
        manager.processes["worker"].set_status("dead")
        manager.processes["worker"].selected = False

        stats = manager.get_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["running"], 1)
        self.assertEqual(stats["dead"], 1)
        self.assertEqual(stats["selected"], 1)

    def test_select_deselect_all(self):
        """Test selecting and deselecting all processes"""
        manager = ProcessManager()
        manager.processes["web"] = ProcessInfo("web")
        manager.processes["worker"] = ProcessInfo("worker")

        manager.deselect_all_processes()
        self.assertFalse(manager.processes["web"].selected)
        self.assertFalse(manager.processes["worker"].selected)

        manager.select_all_processes()
        self.assertTrue(manager.processes["web"].selected)
        self.assertTrue(manager.processes["worker"].selected)

    def test_get_combined_output(self):
        """Test getting combined output"""
        manager = ProcessManager()
        web = ProcessInfo("web")
        worker = ProcessInfo("worker")

        web.add_output("web line 1")
        worker.add_output("worker line 1")
        worker.selected = False

        manager.processes["web"] = web
        manager.processes["worker"] = worker

        # Test selected only
        output = manager.get_combined_output(selected_only=True)
        self.assertEqual(output, ["web line 1"])

        # Test all processes
        output = manager.get_combined_output(selected_only=False)
        self.assertEqual(set(output), {"web line 1", "worker line 1"})

    def test_to_dict(self):
        """Test conversion to dictionary"""
        manager = ProcessManager()
        manager.processes["test"] = ProcessInfo("test")

        result = manager.to_dict()
        self.assertIn('processes', result)
        self.assertIn('stats', result)
        self.assertIn('test', result['processes'])
