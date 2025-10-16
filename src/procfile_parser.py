"""
Procfile Parser - Parse and validate Procfile format
Handles parsing of Procfile entries for native process management
"""

import os
import re
from typing import Dict, List, Optional, Tuple


class ProcfileEntry:
    """Represents a single process definition from Procfile"""

    def __init__(self, name: str, command: str):
        self.name = name
        self.command = command

    def __repr__(self):
        return f"ProcfileEntry(name='{self.name}', command='{self.command}')"

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary"""
        return {"name": self.name, "command": self.command}


class ProcfileParser:
    """Parser for Procfile format"""

    def __init__(self, procfile_path: str):
        self.procfile_path = procfile_path
        self.entries: List[ProcfileEntry] = []
        self.parse_errors: List[Tuple[int, str]] = []

    def parse(self) -> bool:
        """
        Parse the Procfile and populate entries
        Returns True if parsing succeeded, False otherwise
        """
        if not os.path.exists(self.procfile_path):
            self.parse_errors.append((0, f"Procfile not found: {self.procfile_path}"))
            return False

        try:
            with open(self.procfile_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    self._parse_line(line_num, line)

            return len(self.entries) > 0

        except OSError as e:
            self.parse_errors.append((0, f"Error reading Procfile: {e}"))
            return False

    def _parse_line(self, line_num: int, line: str):
        """Parse a single line from the Procfile"""
        # Strip whitespace and skip empty lines or comments
        line = line.strip()
        if not line or line.startswith("#"):
            return

        # Procfile format: "name: command"
        if ":" not in line:
            self.parse_errors.append((line_num, f"Invalid format - missing colon: {line}"))
            return

        # Split on first colon only
        parts = line.split(":", 1)
        if len(parts) != 2:
            self.parse_errors.append((line_num, f"Invalid format: {line}"))
            return

        name = parts[0].strip()
        command = parts[1].strip()

        # Validate process name
        if not self._is_valid_process_name(name):
            self.parse_errors.append(
                (line_num, f"Invalid process name '{name}' - must be alphanumeric with hyphens/underscores")
            )
            return

        # Check for empty command
        if not command:
            self.parse_errors.append((line_num, f"Empty command for process '{name}'"))
            return

        # Check for duplicate names
        if any(entry.name == name for entry in self.entries):
            self.parse_errors.append((line_num, f"Duplicate process name: {name}"))
            return

        # Add valid entry
        self.entries.append(ProcfileEntry(name, command))

    def _is_valid_process_name(self, name: str) -> bool:
        """
        Validate process name
        Must be alphanumeric with optional hyphens/underscores
        """
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))

    def get_entries(self) -> List[ProcfileEntry]:
        """Get all parsed entries"""
        return self.entries

    def get_process_names(self) -> List[str]:
        """Get list of all process names"""
        return [entry.name for entry in self.entries]

    def get_process_command(self, name: str) -> Optional[str]:
        """Get command for a specific process"""
        for entry in self.entries:
            if entry.name == name:
                return entry.command
        return None

    def has_errors(self) -> bool:
        """Check if parsing encountered errors"""
        return len(self.parse_errors) > 0

    def get_errors(self) -> List[Tuple[int, str]]:
        """Get list of parsing errors"""
        return self.parse_errors

    def get_longest_process_name_length(self) -> int:
        """Get length of longest process name for output alignment"""
        if not self.entries:
            return 0
        return max(len(entry.name) for entry in self.entries)
