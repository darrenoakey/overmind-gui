#!/usr/bin/env python3
"""
Tests for Procfile Parser
Validates parsing logic for Procfile format
"""

import os
import tempfile
import unittest

from procfile_parser import ProcfileParser, ProcfileEntry


class TestProcfileParser(unittest.TestCase):
    """Test Procfile parser functionality"""

    def setUp(self):
        """Create temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directory"""
        import shutil

        shutil.rmtree(self.test_dir)

    def _create_procfile(self, content: str) -> str:
        """Create a test Procfile with given content"""
        procfile_path = os.path.join(self.test_dir, "Procfile")
        with open(procfile_path, "w") as f:
            f.write(content)
        return procfile_path

    def test_parse_simple_procfile(self):
        """Test parsing a simple valid Procfile"""
        procfile = self._create_procfile("""
web: python server.py
api: node api.js
worker: python worker.py
""")

        parser = ProcfileParser(procfile)
        self.assertTrue(parser.parse())
        self.assertEqual(len(parser.get_entries()), 3)
        self.assertEqual(parser.get_process_names(), ["web", "api", "worker"])

    def test_parse_with_comments(self):
        """Test parsing with comments"""
        procfile = self._create_procfile("""
# This is a comment
web: python server.py
# Another comment
api: node api.js
""")

        parser = ProcfileParser(procfile)
        self.assertTrue(parser.parse())
        self.assertEqual(len(parser.get_entries()), 2)

    def test_parse_with_empty_lines(self):
        """Test parsing with empty lines"""
        procfile = self._create_procfile("""
web: python server.py

api: node api.js

worker: python worker.py
""")

        parser = ProcfileParser(procfile)
        self.assertTrue(parser.parse())
        self.assertEqual(len(parser.get_entries()), 3)

    def test_parse_complex_commands(self):
        """Test parsing complex commands with arguments"""
        procfile = self._create_procfile("""
web: python server.py --port 3000 --host 0.0.0.0
worker: celery -A myapp worker --loglevel=info
monitor: while true; do echo "$(date)"; sleep 5; done
""")

        parser = ProcfileParser(procfile)
        self.assertTrue(parser.parse())
        self.assertEqual(len(parser.get_entries()), 3)

        # Check that commands are preserved
        web_cmd = parser.get_process_command("web")
        self.assertIn("--port 3000", web_cmd)

    def test_parse_invalid_format_no_colon(self):
        """Test parsing invalid format without colon"""
        procfile = self._create_procfile("""
web python server.py
api: node api.js
""")

        parser = ProcfileParser(procfile)
        self.assertTrue(parser.parse())  # Should still succeed for valid lines
        self.assertEqual(len(parser.get_entries()), 1)  # Only api line is valid
        self.assertTrue(parser.has_errors())
        self.assertEqual(len(parser.get_errors()), 1)

    def test_parse_duplicate_names(self):
        """Test parsing with duplicate process names"""
        procfile = self._create_procfile("""
web: python server.py
api: node api.js
web: python another_server.py
""")

        parser = ProcfileParser(procfile)
        self.assertTrue(parser.parse())
        self.assertEqual(len(parser.get_entries()), 2)  # First two are valid
        self.assertTrue(parser.has_errors())

    def test_parse_empty_command(self):
        """Test parsing with empty command"""
        procfile = self._create_procfile("""
web: python server.py
api:
worker: python worker.py
""")

        parser = ProcfileParser(procfile)
        self.assertTrue(parser.parse())
        self.assertEqual(len(parser.get_entries()), 2)  # web and worker
        self.assertTrue(parser.has_errors())

    def test_parse_invalid_process_names(self):
        """Test parsing with invalid process names"""
        procfile = self._create_procfile("""
my-web: python server.py
my_api: node api.js
my web: python server.py
123: python server.py
""")

        parser = ProcfileParser(procfile)
        parser.parse()

        # my-web and my_api should be valid
        # my web and 123 may have different validation rules
        entries = parser.get_entries()
        self.assertGreaterEqual(len(entries), 2)

    def test_get_longest_name_length(self):
        """Test calculation of longest process name"""
        procfile = self._create_procfile("""
w: python server.py
api: node api.js
verylongworker: python worker.py
""")

        parser = ProcfileParser(procfile)
        parser.parse()
        self.assertEqual(parser.get_longest_process_name_length(), len("verylongworker"))

    def test_parse_nonexistent_file(self):
        """Test parsing nonexistent Procfile"""
        parser = ProcfileParser("/nonexistent/Procfile")
        self.assertFalse(parser.parse())
        self.assertTrue(parser.has_errors())

    def test_get_process_command(self):
        """Test retrieving command for specific process"""
        procfile = self._create_procfile("""
web: python server.py
api: node api.js
""")

        parser = ProcfileParser(procfile)
        parser.parse()

        self.assertEqual(parser.get_process_command("web"), "python server.py")
        self.assertEqual(parser.get_process_command("api"), "node api.js")
        self.assertIsNone(parser.get_process_command("nonexistent"))


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestProcfileParser)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
