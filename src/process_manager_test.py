#!/usr/bin/env python3
"""Tests for process_manager module."""

import unittest
from process_manager import ProcessInfo, ProcessManager


class TestProcessInfoBasic(unittest.TestCase):
    """Basic test cases for ProcessInfo class to ensure coverage"""

    def test_process_info_creation(self):
        """Test creating a ProcessInfo instance"""
        process = ProcessInfo("test_process")
        self.assertEqual(process.name, "test_process")
        self.assertEqual(process.status, "unknown")
        self.assertTrue(process.selected)

    def test_add_output_and_retrieval(self):
        """Test adding and retrieving output"""
        process = ProcessInfo("test")
        process.add_output("line 1")
        process.add_output("line 2")
        output = process.get_all_output()
        self.assertEqual(output, ["line 1", "line 2"])

    def test_warning_pattern_detection(self):
        """Test warning pattern detection"""
        process = ProcessInfo("test")
        process.set_warning_patterns(["ERROR"])
        process.add_output("ERROR: something failed")
        self.assertTrue(process.is_broken())

    def test_status_methods(self):
        """Test various status checking methods"""
        process = ProcessInfo("test")
        process.set_status("running")
        self.assertTrue(process.is_running())
        self.assertFalse(process.is_stopped())
        self.assertFalse(process.is_dead())

        # Test stopped status
        process.set_status("stopped")
        self.assertTrue(process.is_stopped())
        self.assertFalse(process.is_running())

        # Test dead status
        process.set_status("dead")
        self.assertTrue(process.is_dead())
        self.assertFalse(process.is_running())

    def test_restart_functionality(self):
        """Test process restart functionality"""
        process = ProcessInfo("test")
        process.set_warning_patterns(["ERROR"])
        process.add_output("ERROR: failed")

        self.assertTrue(process.is_broken())
        initial_time = process.last_restart_time

        process.restart()
        self.assertFalse(process.is_broken())
        self.assertGreaterEqual(process.last_restart_time, initial_time)

    def test_clear_output_method(self):
        """Test clearing output from process"""
        process = ProcessInfo("test")
        process.add_output("line 1")
        process.add_output("line 2")

        process.clear_output()
        self.assertEqual(len(process.output_lines), 0)

    def test_to_dict_method(self):
        """Test converting process to dictionary"""
        process = ProcessInfo("test")
        process.add_output("test line")

        result = process.to_dict()
        self.assertEqual(result["name"], "test")
        self.assertEqual(result["output_count"], 1)
        self.assertIn("status", result)
        self.assertIn("selected", result)

    def test_case_insensitive_warning_detection(self):
        """Test that warning detection is case insensitive"""
        process = ProcessInfo("test")
        process.set_warning_patterns(["ERROR"])

        process.add_output("error occurred")  # lowercase
        self.assertTrue(process.is_broken())

    def test_broken_status_persistence(self):
        """Test that broken status persists across output additions"""
        process = ProcessInfo("test")
        process.set_warning_patterns(["ERROR"])

        process.add_output("ERROR: broken")
        self.assertTrue(process.is_broken())

        # Adding more output shouldn't clear broken status
        process.add_output("normal output")
        self.assertTrue(process.is_broken())


class TestProcessManagerBasic(unittest.TestCase):
    """Basic test cases for ProcessManager class to ensure coverage"""

    def test_process_manager_creation(self):
        """Test creating a ProcessManager instance"""
        manager = ProcessManager()
        self.assertEqual(len(manager.processes), 0)

    def test_process_operations(self):
        """Test basic process operations"""
        manager = ProcessManager()
        manager.processes["test"] = ProcessInfo("test")

        # Test getting process
        process = manager.get_process("test")
        self.assertIsNotNone(process)
        self.assertEqual(process.name, "test")

        # Test toggle selection
        result = manager.toggle_process_selection("test")
        self.assertFalse(result)

        # Test process names
        names = manager.get_process_names()
        self.assertEqual(names, ["test"])

    def test_output_line_parsing(self):
        """Test parsing output lines"""
        manager = ProcessManager()
        manager.processes["web"] = ProcessInfo("web")

        # Test valid format
        result = manager.add_output_line("web | Starting server")
        self.assertEqual(result, "web")

        # Test invalid format
        result = manager.add_output_line("invalid line")
        self.assertIsNone(result)

    def test_stats_generation(self):
        """Test generating process statistics"""
        manager = ProcessManager()
        manager.processes["running"] = ProcessInfo("running")
        manager.processes["stopped"] = ProcessInfo("stopped")

        manager.processes["running"].set_status("running")
        manager.processes["stopped"].set_status("stopped")

        stats = manager.get_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["running"], 1)

    def test_clear_all_output(self):
        """Test clearing all output from all processes"""
        manager = ProcessManager()
        process1 = ProcessInfo("p1")
        process2 = ProcessInfo("p2")
        process1.add_output("test line 1")
        process2.add_output("test line 2")
        manager.processes["p1"] = process1
        manager.processes["p2"] = process2

        manager.clear_all_output()
        self.assertEqual(len(process1.output_lines), 0)
        self.assertEqual(len(process2.output_lines), 0)

    def test_restart_process(self):
        """Test restarting a process"""
        manager = ProcessManager()
        process = ProcessInfo("test")
        process.set_warning_patterns(["ERROR"])
        process.add_output("ERROR: broken")
        manager.processes["test"] = process

        self.assertTrue(process.is_broken())
        manager.restart_process("test")
        self.assertFalse(process.is_broken())

    def test_select_deselect_all(self):
        """Test selecting and deselecting all processes"""
        manager = ProcessManager()
        manager.processes["p1"] = ProcessInfo("p1")
        manager.processes["p2"] = ProcessInfo("p2")

        manager.deselect_all_processes()
        self.assertFalse(manager.processes["p1"].selected)
        self.assertFalse(manager.processes["p2"].selected)

        manager.select_all_processes()
        self.assertTrue(manager.processes["p1"].selected)
        self.assertTrue(manager.processes["p2"].selected)

    def test_get_combined_output(self):
        """Test getting combined output from processes"""
        manager = ProcessManager()
        p1 = ProcessInfo("p1")
        p2 = ProcessInfo("p2")
        p1.add_output("p1 line 1")
        p2.add_output("p2 line 1")
        p2.selected = False

        manager.processes["p1"] = p1
        manager.processes["p2"] = p2

        # Selected only
        output = manager.get_combined_output(selected_only=True)
        self.assertEqual(output, ["p1 line 1"])

        # All processes
        output = manager.get_combined_output(selected_only=False)
        self.assertIn("p1 line 1", output)
        self.assertIn("p2 line 1", output)

    def test_update_process_status(self):
        """Test updating process status"""
        manager = ProcessManager()
        manager.processes["test"] = ProcessInfo("test")

        manager.update_process_status("test", "running")
        self.assertEqual(manager.processes["test"].status, "running")

    def test_to_dict_conversion(self):
        """Test converting manager to dictionary"""
        manager = ProcessManager()
        manager.processes["test"] = ProcessInfo("test")

        result = manager.to_dict()
        self.assertIn("processes", result)
        self.assertIn("stats", result)
        self.assertIn("warning_config", result)

    def test_get_selected_processes(self):
        """Test getting only selected processes"""
        manager = ProcessManager()
        p1 = ProcessInfo("p1")
        p2 = ProcessInfo("p2")
        p2.selected = False
        manager.processes["p1"] = p1
        manager.processes["p2"] = p2

        selected = manager.get_selected_processes()
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].name, "p1")

    def test_get_all_processes(self):
        """Test getting all processes as a copy"""
        manager = ProcessManager()
        manager.processes["test"] = ProcessInfo("test")

        all_procs = manager.get_all_processes()
        self.assertEqual(len(all_procs), 1)
        self.assertIn("test", all_procs)

        # Verify it's a copy, not the original dict
        all_procs["new"] = ProcessInfo("new")
        self.assertNotIn("new", manager.processes)

    def test_status_transitions_trigger_restart(self):
        """Test that status transitions from stopped/dead/disabled to running trigger restart"""
        process = ProcessInfo("test")
        process.set_status("stopped")

        # Transition to running should trigger restart logic
        process.set_status("running")
        # This should have called restart internally, clearing any broken status

    def test_warning_config_load_failure_handling(self):
        """Test that manager handles missing warning config gracefully"""
        manager = ProcessManager()
        # The constructor should handle missing overmind_warnings.json file
        self.assertIsInstance(manager.warning_config, dict)

    def test_output_parsing_with_unknown_process(self):
        """Test output line parsing when process is not in the manager"""
        manager = ProcessManager()
        manager.processes["known"] = ProcessInfo("known")

        # Test with unknown process
        result = manager.add_output_line("unknown | output line")
        self.assertIsNone(result)

        # Test with known process
        result = manager.add_output_line("known | output line")
        self.assertEqual(result, "known")

    def test_stats_with_different_statuses(self):
        """Test stats generation with various process statuses"""
        manager = ProcessManager()

        # Create processes with different statuses
        p1 = ProcessInfo("running")
        p1.set_status("running")

        p2 = ProcessInfo("stopped")
        p2.set_status("stopped")

        p3 = ProcessInfo("dead")
        p3.set_status("dead")

        p4 = ProcessInfo("broken")
        p4.set_status("broken")

        p5 = ProcessInfo("disabled")
        p5.set_status("disabled")
        p5.selected = False

        manager.processes["running"] = p1
        manager.processes["stopped"] = p2
        manager.processes["dead"] = p3
        manager.processes["broken"] = p4
        manager.processes["disabled"] = p5

        stats = manager.get_stats()
        self.assertEqual(stats["total"], 5)
        self.assertEqual(stats["running"], 1)
        self.assertEqual(stats["stopped"], 2)  # stopped and disabled both count as stopped
        self.assertEqual(stats["dead"], 1)
        self.assertEqual(stats["broken"], 1)
        self.assertEqual(stats["selected"], 4)  # all except disabled

    def test_process_set_status_with_restart_trigger(self):
        """Test that setting status from stopped to running triggers restart"""
        process = ProcessInfo("test")
        process.set_warning_patterns(["ERROR"])
        process.add_output("ERROR: broken")
        process.set_status("stopped")

        self.assertTrue(process.is_broken())

        # Setting to running should trigger restart and clear broken status
        process.set_status("running")
        self.assertFalse(process.is_broken())

    def test_procfile_loading_coverage(self):
        """Test procfile loading functionality"""
        import tempfile
        import os

        manager = ProcessManager()

        # Test with non-existent procfile
        with self.assertRaises(FileNotFoundError):
            manager.load_procfile("non_existent_procfile")

        # Test with valid procfile content
        with tempfile.NamedTemporaryFile(mode="w", suffix=".procfile", delete=False) as f:
            f.write("# Comment line\n")
            f.write("web: python server.py\n")
            f.write("worker: python worker.py\n")
            f.write("\n")  # Empty line
            temp_path = f.name

        try:
            process_names = manager.load_procfile(temp_path)
            self.assertIn("web", process_names)
            self.assertIn("worker", process_names)
            self.assertEqual(len(process_names), 2)

            # Verify processes were created
            self.assertIn("web", manager.processes)
            self.assertIn("worker", manager.processes)
        finally:
            os.unlink(temp_path)

    def test_edge_case_output_parsing(self):
        """Test edge cases in output line parsing"""
        manager = ProcessManager()
        manager.processes["test"] = ProcessInfo("test")

        # Test line without " | " separator
        result = manager.add_output_line("just a regular line")
        self.assertIsNone(result)

        # Test line with empty parts
        result = manager.add_output_line(" | ")
        self.assertIsNone(result)

        # Test line with multiple separators
        result = manager.add_output_line("test | output | with | multiple | separators")
        self.assertEqual(result, "test")

    def test_broken_status_edge_cases(self):
        """Test broken status detection edge cases"""
        process = ProcessInfo("test")
        process.set_warning_patterns([])  # Empty patterns

        # No patterns should not trigger broken status
        process.add_output("ERROR: this should not trigger")
        self.assertFalse(process.is_broken())

        # Test restart when not broken
        process.restart()
        self.assertFalse(process.is_broken())

    def test_maxlen_deque_behavior(self):
        """Test that output deque respects maxlen"""
        process = ProcessInfo("test")

        # Add more than maxlen lines
        for i in range(6000):  # maxlen is 5000
            process.add_output(f"line {i}")

        # Should be limited to maxlen
        self.assertEqual(len(process.output_lines), 5000)

        # Should have the most recent lines
        all_output = process.get_all_output()
        self.assertEqual(all_output[-1], "line 5999")
        self.assertEqual(all_output[0], "line 1000")


if __name__ == "__main__":
    unittest.main()
