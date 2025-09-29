#!/usr/bin/env python3
"""Tests for ansi_to_html module."""

import unittest
from ansi_to_html import AnsiToHtml


class TestAnsiToHtml(unittest.TestCase):
    """Test cases for ansi_to_html module."""

    def setUp(self):
        """Set up test environment."""
        self.converter = AnsiToHtml()

    def test_basic_ansi_colors(self):
        """Test basic ANSI color conversion."""
        # Red text
        result = self.converter.convert('\x1b[31mred text\x1b[0m')
        self.assertIn('color: #800000', result)
        self.assertIn('red text', result)
        self.assertEqual(result.count('<span'), result.count('</span>'))

        # Green text
        result = self.converter.convert('\x1b[32mgreen text\x1b[0m')
        self.assertIn('color: #008000', result)
        self.assertIn('green text', result)
        self.assertEqual(result.count('<span'), result.count('</span>'))

    def test_bright_ansi_colors(self):
        """Test bright ANSI color conversion."""
        # Bright red
        result = self.converter.convert('\x1b[91mbright red\x1b[0m')
        self.assertIn('color: #ff0000', result)
        self.assertIn('bright red', result)

        # Bright yellow
        result = self.converter.convert('\x1b[93mbright yellow\x1b[0m')
        self.assertIn('color: #ffff00', result)
        self.assertIn('bright yellow', result)

    def test_256_color_palette(self):
        """Test 256-color palette conversion."""
        # Bright red (196)
        result = self.converter.convert('\x1b[38;5;196mbright red 256\x1b[0m')
        self.assertIn('color: #ff0000', result)
        self.assertIn('bright red 256', result)

        # Blue (21)
        result = self.converter.convert('\x1b[38;5;21mblue 256\x1b[0m')
        self.assertIn('color: #0000ff', result)
        self.assertIn('blue 256', result)

    def test_true_color_rgb(self):
        """Test true color RGB conversion."""
        # Orange RGB
        result = self.converter.convert('\x1b[38;2;255;128;0morange RGB\x1b[0m')
        self.assertIn('color: #ff8000', result)
        self.assertIn('orange RGB', result)

        # Purple RGB
        result = self.converter.convert('\x1b[38;2;128;0;128mpurple RGB\x1b[0m')
        self.assertIn('color: #800080', result)
        self.assertIn('purple RGB', result)

    def test_bold_formatting(self):
        """Test bold text formatting."""
        result = self.converter.convert('\x1b[1mbold text\x1b[0m')
        self.assertIn('font-weight: bold', result)
        self.assertIn('bold text', result)
        self.assertEqual(result.count('<span'), result.count('</span>'))

    def test_bold_with_color(self):
        """Test bold combined with color."""
        result = self.converter.convert('\x1b[1;31mbold red\x1b[0m')
        self.assertIn('font-weight: bold', result)
        self.assertIn('color: #800000', result)
        self.assertIn('bold red', result)
        self.assertEqual(result.count('<span'), result.count('</span>'))

    def test_html_escaping(self):
        """Test that HTML is properly escaped."""
        result = self.converter.convert('\x1b[31m<script>alert("xss")</script>\x1b[0m')
        self.assertNotIn('<script>', result)
        self.assertIn('&lt;script&gt;', result)
        self.assertIn('color: #800000', result)

    def test_span_balance(self):
        """Test that all spans are properly balanced."""
        test_cases = [
            '\x1b[31mred\x1b[0m',
            '\x1b[1mbold\x1b[0m',
            '\x1b[1;31mbold red\x1b[0m',
            '\x1b[38;5;196m256 color\x1b[0m',
            '\x1b[38;2;255;128;0mRGB color\x1b[0m'
        ]

        for test_case in test_cases:
            result = self.converter.convert(test_case)
            open_spans = result.count('<span')
            close_spans = result.count('</span>')
            self.assertEqual(open_spans, close_spans,
                           f"Unbalanced spans in: {test_case}")

    def test_unclosed_spans_auto_close(self):
        """Test that unclosed spans are automatically closed."""
        result = self.converter.convert('\x1b[31munclosed red text')
        self.assertIn('color: #800000', result)
        self.assertIn('unclosed red text', result)
        self.assertEqual(result.count('<span'), result.count('</span>'))

    def test_realistic_overmind_output(self):
        """Test realistic overmind-style output with process names and colors."""
        overmind_line = '\x1b[1;36mweb\x1b[0m     | \x1b[32mServer started on port 3000\x1b[0m'
        result = self.converter.convert(overmind_line)

        # Should contain cyan color for 'web'
        self.assertIn('color: #008080', result)
        # Should contain green color for the message
        self.assertIn('color: #008000', result)
        # Should contain both text parts
        self.assertIn('web', result)
        self.assertIn('Server started on port 3000', result)
        # Should be balanced
        self.assertEqual(result.count('<span'), result.count('</span>'))


if __name__ == '__main__':
    unittest.main()
