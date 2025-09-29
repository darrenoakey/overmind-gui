#!/usr/bin/env python3
"""
ANSI to HTML Converter - Proper span balancing and comprehensive color support
"""

import re
import html
from typing import List


class AnsiToHtml:
    """Convert ANSI escape sequences to HTML with proper span balancing"""

    def __init__(self):
        # 256 - color palette
        self.color_palette = self._build_256_color_palette()

        # Standard ANSI color codes (maps to 256 - color palette indices)
        self.ansi_to_256_map = {
            30: 0,   # black
            31: 1,   # red
            32: 2,   # green
            33: 3,   # yellow
            34: 4,   # blue
            35: 5,   # magenta
            36: 6,   # cyan
            37: 7,   # white
            90: 8,   # bright black (gray)
            91: 9,   # bright red
            92: 10,  # bright green
            93: 11,  # bright yellow
            94: 12,  # bright blue
            95: 13,  # bright magenta
            96: 14,  # bright cyan
            97: 15,  # bright white
        }

        # Stack to track open spans
        self.span_stack = []

    def _build_256_color_palette(self) -> List[str]:
        """Build 256 - color palette"""
        colors = []

        # 0 - 15: Standard colors
        standard = [
            '#000000', '#800000', '#008000', '#808000', '#000080', '#800080', '#008080', '#c0c0c0',
            '#808080', '#ff0000', '#00ff00', '#ffff00', '#0000ff', '#ff00ff', '#00ffff', '#ffffff'
        ]
        colors.extend(standard)

        # 16 - 231: 216 - color cube (6x6x6)
        for i in range(216):
            r = i // 36
            g = (i % 36) // 6
            b = i % 6

            def to_rgb(n):
                return 0 if n == 0 else 55 + n * 40

            r_val = to_rgb(r)
            g_val = to_rgb(g)
            b_val = to_rgb(b)
            colors.append(f'#{r_val:02x}{g_val:02x}{b_val:02x}')

        # 232 - 255: Grayscale
        for i in range(24):
            gray = 8 + i * 10
            colors.append(f'#{gray:02x}{gray:02x}{gray:02x}')

        return colors

    def convert(self, text: str) -> str:
        """Convert ANSI text to HTML with proper span balancing"""
        # Reset span stack for each conversion
        self.span_stack = []

        # Escape HTML first
        text = html.escape(text, quote=False)

        # Remove terminal control sequences
        text = re.sub(r'\x1b]0;[^\x07]*\x07', '', text)

        # Process ANSI sequences
        result = []
        i = 0

        while i < len(text):
            if text[i:i + 2] == '\x1b[':
                # Find the end of the ANSI sequence
                j = i + 2
                while j < len(text) and text[j] not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz':
                    j += 1

                if j < len(text):
                    sequence = text[i:j + 1]
                    html_span = self._process_ansi_sequence(sequence)
                    if html_span:
                        result.append(html_span)
                    i = j + 1
                else:
                    # Incomplete sequence, skip the escape character
                    result.append(text[i])
                    i += 1
            else:
                result.append(text[i])
                i += 1

        # Close any remaining open spans
        while self.span_stack:
            result.append('</span>')
            self.span_stack.pop()

        return ''.join(result)

    def _process_ansi_sequence(self, sequence: str) -> str:
        """Process a single ANSI escape sequence"""
        # Extract parameters
        match = re.match(r'\x1b\[([0 - 9;]*)([a - zA - Z])', sequence)
        if not match:
            return ''

        params_str, cmd = match.groups()

        # Only handle SGR (Select Graphic Rendition) sequences
        if cmd != 'm':
            return ''

        # Parse parameters
        params = [int(p) if p else 0 for p in params_str.split(';')] if params_str else [0]

        return self._handle_sgr_params(params)

    def _handle_sgr_params(self, params: List[int]) -> str:
        """Handle SGR (color/style) parameters - unified 256 - color system"""
        result = []
        i = 0

        while i < len(params):
            param = params[i]

            if param == 0:
                # Reset - close all spans
                while self.span_stack:
                    result.append('</span>')
                    self.span_stack.pop()

            elif param == 1:
                # Bold
                result.append('<span style="font - weight: bold">')
                self.span_stack.append('bold')

            elif param in self.ansi_to_256_map:
                # Standard ANSI colors - map to 256 - color palette
                color_index = self.ansi_to_256_map[param]
                color = self.color_palette[color_index]
                result.append(f'<span style="color: {color}">')
                self.span_stack.append('color')

            elif param == 38 and i + 2 < len(params) and params[i + 1] == 5:
                # Direct 256 - color foreground: 38;5;n
                color_index = params[i + 2]
                if 0 <= color_index < len(self.color_palette):
                    color = self.color_palette[color_index]
                    result.append(f'<span style="color: {color}">')
                    self.span_stack.append('color')
                i += 2  # Skip the 5 and color index

            elif param == 38 and i + 4 < len(params) and params[i + 1] == 2:
                # True color RGB: 38;2;r;g;b
                r, g, b = params[i + 2], params[i + 3], params[i + 4]
                if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                    color = f'#{r:02x}{g:02x}{b:02x}'
                    result.append(f'<span style="color: {color}">')
                    self.span_stack.append('color')
                i += 4  # Skip the 2, r, g, b

            # Ignore background colors and other formatting

            i += 1

        return ''.join(result)


# Test cases
def test_ansi_to_html():
    """Test the ANSI to HTML converter"""
    converter = AnsiToHtml()

    test_cases = [
        # Basic ANSI colors
        ('\x1b[31mred text\x1b[0m', 'basic red'),
        ('\x1b[36mcyan text\x1b[0m', 'basic cyan'),
        ('\x1b[93mbright yellow\x1b[0m', 'bright yellow'),

        # Bold + color combinations
        ('\x1b[1;31mbold red\x1b[0m', 'bold + red combined'),
        ('\x1b[1;38;5;196mbold + 256 - color\x1b[0m', 'bold + 256 - color combined'),

        # 256 - color tests
        ('\x1b[38;5;196mbright red 256\x1b[0m', '256 - color #196 bright red'),
        ('\x1b[38;5;21mblue 256\x1b[0m', '256 - color #21 blue'),
        ('\x1b[38;5;46mgreen 256\x1b[0m', '256 - color #46 green'),

        # True color RGB
        ('\x1b[38;2;255;128;0morange RGB\x1b[0m', 'true color RGB orange'),
        ('\x1b[38;2;128;0;128mpurple RGB\x1b[0m', 'true color RGB purple'),

        # Complex realistic overmind output
        ('\x1b[1;38;5;6mweb\x1b[0m     | \x1b[38;5;2mServer started on port 3000\x1b[0m', 'realistic overmind output'),

        # Auto - closing unclosed spans
        ('\x1b[38;5;196munclosed span', 'unclosed 256 - color should auto - close'),

        # Multiple nested spans
        ('\x1b[1m\x1b[38;5;196mbold red\x1b[0m normal', 'nested bold and color'),

        # HTML escaping
        ('\x1b[31m<script>alert("xss")</script>\x1b[0m', 'HTML should be escaped'),

        # Empty sequences
        ('\x1b[m\x1b[0mnormal text', 'empty reset sequences'),
    ]

    print("Testing ANSI to HTML conversion:")
    print("=" * 50)

    for i, (input_text, description) in enumerate(test_cases, 1):
        result = converter.convert(input_text)
        print(f"Test {i}: {description}")
        print(f"Input:  {repr(input_text)}")
        print(f"Output: {result}")
        print()

        # Basic validation
        open_spans = result.count('<span')
        close_spans = result.count('</span>')
        balance_status = ('✅ BALANCED' if open_spans == close_spans
                         else '❌ UNBALANCED')
        print(f"Span balance: {open_spans} open, {close_spans} close - {balance_status}")
        print("-" * 30)


if __name__ == '__main__':
    test_ansi_to_html()
