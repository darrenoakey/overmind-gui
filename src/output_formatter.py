"""
Output Formatter - Color allocation and output formatting for native daemon
Mimics overmind's colored output format: processname | text
"""

from typing import Dict, List


class OutputFormatter:
    """Handles color allocation and output formatting for processes"""

    # ANSI color codes matching overmind's color scheme
    COLORS = [
        "\033[36m",  # Cyan
        "\033[33m",  # Yellow
        "\033[32m",  # Green
        "\033[35m",  # Magenta
        "\033[34m",  # Blue
        "\033[91m",  # Light Red
        "\033[92m",  # Light Green
        "\033[93m",  # Light Yellow
        "\033[94m",  # Light Blue
        "\033[95m",  # Light Magenta
        "\033[96m",  # Light Cyan
        "\033[31m",  # Red
    ]

    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(self, process_names: List[str]):
        """
        Initialize formatter with process names
        Allocates colors and calculates output alignment
        """
        self.process_names = process_names
        self.color_map: Dict[str, str] = {}
        self.max_name_length = 0

        self._allocate_colors()
        self._calculate_alignment()

    def _allocate_colors(self):
        """Allocate colors to processes in order"""
        for i, name in enumerate(self.process_names):
            # Cycle through colors if more processes than colors
            color_index = i % len(self.COLORS)
            self.color_map[name] = self.COLORS[color_index]

    def _calculate_alignment(self):
        """Calculate max process name length for alignment"""
        if self.process_names:
            self.max_name_length = max(len(name) for name in self.process_names)
        else:
            self.max_name_length = 0

    def format_output_line(self, process_name: str, text: str) -> str:
        """
        Format a line of output with process name, color, and proper alignment
        Returns formatted string: "processname | text"
        """
        # Get color for process (default to cyan if not found)
        color = self.color_map.get(process_name, self.COLORS[0])

        # Pad process name to align output
        padded_name = process_name.ljust(self.max_name_length)

        # Format: "coloredname | text"
        formatted = f"{color}{self.BOLD}{padded_name}{self.RESET} | {text}"

        return formatted

    def get_color_for_process(self, process_name: str) -> str:
        """Get ANSI color code for a process"""
        return self.color_map.get(process_name, self.COLORS[0])

    def add_process(self, process_name: str):
        """
        Add a new process dynamically
        Useful if processes are added after initialization
        """
        if process_name not in self.process_names:
            self.process_names.append(process_name)

            # Allocate color
            index = (len(self.process_names) - 1) % len(self.COLORS)
            self.color_map[process_name] = self.COLORS[index]

            # Recalculate alignment
            self._calculate_alignment()

    def get_process_count(self) -> int:
        """Get number of processes"""
        return len(self.process_names)

    def get_formatted_header(self) -> str:
        """Get a formatted header showing all processes and their colors"""
        lines = []
        lines.append(f"\n{self.BOLD}Processes:{self.RESET}")
        for name in self.process_names:
            color = self.color_map[name]
            lines.append(f"  {color}{self.BOLD}{name}{self.RESET}")
        return "\n".join(lines)

    @staticmethod
    def strip_ansi_codes(text: str) -> str:
        """Strip ANSI color codes from text"""
        import re

        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)
