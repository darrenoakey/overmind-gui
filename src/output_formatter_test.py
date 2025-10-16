#!/usr/bin/env python3
"""
Tests for Output Formatter
Validates color allocation and output formatting
"""

import unittest

from output_formatter import OutputFormatter


class TestOutputFormatter(unittest.TestCase):
    """Test output formatter functionality"""

    def test_color_allocation(self):
        """Test that colors are allocated to processes"""
        processes = ["web", "api", "worker"]
        formatter = OutputFormatter(processes)

        # Check all processes have colors
        for proc in processes:
            color = formatter.get_color_for_process(proc)
            self.assertIsNotNone(color)
            self.assertTrue(color.startswith("\033["))

    def test_different_processes_different_colors(self):
        """Test that different processes get different colors initially"""
        processes = ["web", "api", "worker"]
        formatter = OutputFormatter(processes)

        web_color = formatter.get_color_for_process("web")
        api_color = formatter.get_color_for_process("api")
        worker_color = formatter.get_color_for_process("worker")

        # First three should have different colors
        self.assertNotEqual(web_color, api_color)
        self.assertNotEqual(api_color, worker_color)

    def test_color_cycling(self):
        """Test that colors cycle when more processes than colors"""
        # Create more processes than available colors
        processes = [f"proc{i}" for i in range(20)]
        formatter = OutputFormatter(processes)

        # All should get colors (cycling through the color list)
        for proc in processes:
            color = formatter.get_color_for_process(proc)
            self.assertIsNotNone(color)

    def test_format_output_line(self):
        """Test formatting of output lines"""
        processes = ["web", "api"]
        formatter = OutputFormatter(processes)

        formatted = formatter.format_output_line("web", "Server started")

        # Should contain the process name
        self.assertIn("web", formatted)
        # Should contain the text
        self.assertIn("Server started", formatted)
        # Should contain separator
        self.assertIn(" | ", formatted)
        # Should have ANSI codes
        self.assertIn("\033[", formatted)

    def test_alignment(self):
        """Test that output is aligned properly"""
        processes = ["w", "api", "worker"]
        formatter = OutputFormatter(processes)

        # All formatted lines should have same prefix length (process name padded)
        formatted_w = formatter.format_output_line("w", "text")
        formatted_api = formatter.format_output_line("api", "text")
        formatted_worker = formatter.format_output_line("worker", "text")

        # Extract prefix (before " | ")
        prefix_w = formatted_w.split(" | ")[0]
        prefix_api = formatted_api.split(" | ")[0]
        prefix_worker = formatted_worker.split(" | ")[0]

        # Strip ANSI codes for length comparison
        clean_prefix_w = OutputFormatter.strip_ansi_codes(prefix_w)
        clean_prefix_api = OutputFormatter.strip_ansi_codes(prefix_api)
        clean_prefix_worker = OutputFormatter.strip_ansi_codes(prefix_worker)

        # All should have same length (padded to longest name)
        self.assertEqual(len(clean_prefix_w), len(clean_prefix_api))
        self.assertEqual(len(clean_prefix_api), len(clean_prefix_worker))

    def test_add_process_dynamically(self):
        """Test adding processes after initialization"""
        processes = ["web", "api"]
        formatter = OutputFormatter(processes)

        self.assertEqual(formatter.get_process_count(), 2)

        formatter.add_process("worker")

        self.assertEqual(formatter.get_process_count(), 3)
        self.assertIsNotNone(formatter.get_color_for_process("worker"))

    def test_strip_ansi_codes(self):
        """Test stripping ANSI color codes"""
        text_with_ansi = "\033[31mRed Text\033[0m Normal"
        clean_text = OutputFormatter.strip_ansi_codes(text_with_ansi)

        self.assertEqual(clean_text, "Red Text Normal")
        self.assertNotIn("\033[", clean_text)

    def test_empty_process_list(self):
        """Test with empty process list"""
        formatter = OutputFormatter([])

        self.assertEqual(formatter.get_process_count(), 0)
        self.assertEqual(formatter.max_name_length, 0)

    def test_formatted_header(self):
        """Test formatted header generation"""
        processes = ["web", "api", "worker"]
        formatter = OutputFormatter(processes)

        header = formatter.get_formatted_header()

        # Should contain all process names
        for proc in processes:
            self.assertIn(proc, header)

        # Should have formatting
        self.assertIn("\033[", header)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestOutputFormatter)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
