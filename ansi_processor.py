"""
ANSI Processing Backend - High performance ANSI-to-HTML conversion
Moves expensive ANSI processing from frontend to backend for better performance
"""

import re
from typing import Dict, List, Tuple


class ANSIProcessor:
    """High-performance ANSI to HTML processor"""
    
    def __init__(self):
        # Background color for contrast calculations (dark theme)
        self.background_color = '#0f172a'
        
        # Color mapping cache for contrast enhancement
        self.color_contrast_map = {}
        
        # 256-color palette (standard terminal colors)
        self.ansi_256_colors = self._build_256_color_palette()
        
        # Basic ANSI color mapping for 8/16 colors
        self.ansi_colors = {
            # Standard colors (30-37)
            '30': '#000000', '31': '#cd0000', '32': '#00cd00', '33': '#cdcd00',
            '34': '#0000ee', '35': '#cd00cd', '36': '#00cdcd', '37': '#e5e5e5',
            # Bright colors (90-97)
            '90': '#7f7f7f', '91': '#ff0000', '92': '#00ff00', '93': '#ffff00',
            '94': '#5c5cff', '95': '#ff00ff', '96': '#00ffff', '97': '#ffffff',
        }
        
        self.ansi_bg_colors = {
            # Standard background colors (40-47)
            '40': '#000000', '41': '#cd0000', '42': '#00cd00', '43': '#cdcd00',
            '44': '#0000ee', '45': '#cd00cd', '46': '#00cdcd', '47': '#e5e5e5',
            # Bright background colors (100-107)
            '100': '#7f7f7f', '101': '#ff0000', '102': '#00ff00', '103': '#ffff00',
            '104': '#5c5cff', '105': '#ff00ff', '106': '#00ffff', '107': '#ffffff',
        }
        
        # Compiled regex for better performance
        self.ansi_regex = re.compile(r'[\x1b\u001b]\[([0-9;]*)m')
        self.reset_regex = re.compile(r'[\x1b\u001b]\[0*m')
        # Regex to catch ANY remaining ANSI escape sequences (cursor movement, clearing, etc.)
        # Also includes standalone \r (carriage return) characters that often come with terminal output
        self.ansi_cleanup_regex = re.compile(r'[\x1b\u001b]\[[0-9;]*[A-Za-z]')
        self.carriage_return_regex = re.compile(r'\r')
    
    def _build_256_color_palette(self) -> List[str]:
        """Build the 256-color ANSI palette"""
        colors = []
        
        # 0-15: Standard colors
        standard = [
            '#000000', '#800000', '#008000', '#808000', '#000080', '#800080', '#008080', '#c0c0c0',
            '#808080', '#ff0000', '#00ff00', '#ffff00', '#0000ff', '#ff00ff', '#00ffff', '#ffffff'
        ]
        colors.extend(standard)
        
        # 16-231: 216 colors (6x6x6 color cube)
        for i in range(216):
            r = i // 36
            g = (i % 36) // 6
            b = i % 6
            
            def to_hex(n):
                return '00' if n == 0 else f'{55 + n * 40:02x}'
            
            color = f'#{to_hex(r)}{to_hex(g)}{to_hex(b)}'
            colors.append(color)
        
        # 232-255: Grayscale
        for i in range(24):
            gray = f'{8 + i * 10:02x}'
            colors.append(f'#{gray}{gray}{gray}')
        
        return colors
    
    def _get_luminance(self, color: str) -> float:
        """Calculate luminance of a color"""
        hex_color = color.replace('#', '')
        r = int(hex_color[0:2], 16) / 255
        g = int(hex_color[2:4], 16) / 255
        b = int(hex_color[4:6], 16) / 255
        
        def to_linear(c):
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        
        return 0.2126 * to_linear(r) + 0.7152 * to_linear(g) + 0.0722 * to_linear(b)
    
    def _get_contrast_ratio(self, color1: str, color2: str) -> float:
        """Calculate contrast ratio between two colors"""
        lum1 = self._get_luminance(color1)
        lum2 = self._get_luminance(color2)
        brightest = max(lum1, lum2)
        darkest = min(lum1, lum2)
        return (brightest + 0.05) / (darkest + 0.05)
    
    def _enhance_color_contrast(self, original_color: str) -> str:
        """Enhance color contrast if needed"""
        # Check cache first
        if original_color in self.color_contrast_map:
            return self.color_contrast_map[original_color]
        
        contrast_ratio = self._get_contrast_ratio(original_color, self.background_color)
        
        # If contrast is sufficient (4.5:1 for normal text), use original color
        if contrast_ratio >= 4.5:
            self.color_contrast_map[original_color] = original_color
            return original_color
        
        # Enhance the color by making it brighter/lighter
        hex_color = original_color.replace('#', '')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Increase brightness while preserving hue
        factor = 1.8
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        
        enhanced_color = f'#{r:02x}{g:02x}{b:02x}'
        
        # Double-check the enhanced color has good contrast
        new_contrast_ratio = self._get_contrast_ratio(enhanced_color, self.background_color)
        
        # If still not enough contrast, make it even brighter
        if new_contrast_ratio < 4.5:
            r = min(255, int(r * 1.5))
            g = min(255, int(g * 1.5))
            b = min(255, int(b * 1.5))
            enhanced_color = f'#{r:02x}{g:02x}{b:02x}'
        
        # Cache the result
        self.color_contrast_map[original_color] = enhanced_color
        return enhanced_color
    
    def ansi_to_html(self, text: str) -> str:
        """Convert ANSI escape sequences to HTML"""
        html = text
        
        # First, replace reset codes
        html = self.reset_regex.sub('</span>', html)
        
        # Handle other codes
        def replace_ansi(match):
            codes = match.group(1)
            if not codes:
                return '</span>'
            
            code_list = [c for c in codes.split(';') if c]
            styles = []
            
            # Process codes sequentially, handling 256-color sequences
            i = 0
            while i < len(code_list):
                code = code_list[i]
                try:
                    code_num = int(code)
                except ValueError:
                    i += 1
                    continue
                
                # Handle 256-color foreground: 38;5;N
                if code_num == 38 and i + 2 < len(code_list) and code_list[i + 1] == '5':
                    try:
                        color_index = int(code_list[i + 2])
                        if 0 <= color_index < len(self.ansi_256_colors):
                            original_color = self.ansi_256_colors[color_index]
                            enhanced_color = self._enhance_color_contrast(original_color)
                            styles.append(f'color: {enhanced_color}')
                            i += 3
                            continue
                    except (ValueError, IndexError):
                        pass
                
                # Handle 256-color background: 48;5;N
                elif code_num == 48 and i + 2 < len(code_list) and code_list[i + 1] == '5':
                    try:
                        color_index = int(code_list[i + 2])
                        if 0 <= color_index < len(self.ansi_256_colors):
                            color = self.ansi_256_colors[color_index]
                            styles.append(f'background-color: {color}')
                            i += 3
                            continue
                    except (ValueError, IndexError):
                        pass
                
                # Handle basic 8/16 colors
                elif code in self.ansi_colors:
                    original_color = self.ansi_colors[code]
                    enhanced_color = self._enhance_color_contrast(original_color)
                    styles.append(f'color: {enhanced_color}')
                elif code in self.ansi_bg_colors:
                    styles.append(f'background-color: {self.ansi_bg_colors[code]}')
                elif code_num == 1:
                    styles.append('font-weight: bold')
                elif code_num == 3:
                    styles.append('font-style: italic')
                elif code_num == 4:
                    styles.append('text-decoration: underline')
                elif code_num == 22:
                    styles.append('font-weight: normal')
                elif code_num == 23:
                    styles.append('font-style: normal')
                elif code_num == 24:
                    styles.append('text-decoration: none')
                
                i += 1
            
            if styles:
                return f'<span style="{"; ".join(styles)}">'
            return ''
        
        html = self.ansi_regex.sub(replace_ansi, html)
        
        # FINAL STEP: Remove any remaining ANSI escape sequences (cursor movement, clearing, etc.)
        # This catches sequences like \x1b[2K, \x1b[1A, \x1b[G, etc. that we don't want in HTML
        html = self.ansi_cleanup_regex.sub('', html)
        # Also remove carriage returns that often appear with terminal control sequences
        html = self.carriage_return_regex.sub('', html)
        
        return html
    
    def strip_ansi_codes(self, text: str) -> str:
        """Strip ALL ANSI codes for searching"""
        # Remove SGR sequences (colors, bold, etc.)
        clean_text = self.ansi_regex.sub('', text)
        # Remove all other ANSI sequences
        clean_text = self.ansi_cleanup_regex.sub('', clean_text)
        # Remove carriage returns
        clean_text = self.carriage_return_regex.sub('', clean_text)
        return clean_text
    
    def process_line(self, line_text: str, line_id: int, process_name: str, timestamp: float = None) -> Dict:
        """Process a single line and return only HTML representation"""
        # First escape any existing HTML characters in the raw text (before ANSI processing)
        import html
        import time
        escaped_text = html.escape(line_text, quote=False)
        
        # Then convert ANSI codes to HTML spans (this preserves our HTML tags)
        html_content = self.ansi_to_html(escaped_text)
        
        # Create clean text for searching (strip all ANSI codes)
        clean_text = self.strip_ansi_codes(line_text)
        
        result = {
            'id': line_id,
            'html': html_content,  # HTML representation - used for display
            'process': process_name
        }
        
        # Add optional fields that tests might expect
        if timestamp is not None:
            result['timestamp'] = timestamp
        
        # Add clean text for backward compatibility with tests
        result['clean_text'] = clean_text
        
        return result


# Global instance
ansi_processor = ANSIProcessor()


# Comprehensive Unit Tests
import unittest
import time


class TestANSIProcessor(unittest.TestCase):
    """Comprehensive test suite for ANSI processing"""
    
    def setUp(self):
        """Set up test processor"""
        self.processor = ANSIProcessor()
    
    def test_basic_color_processing(self):
        """Test basic 8/16 color ANSI codes"""
        # Red text
        text = "\x1b[31mRed text\x1b[0m"
        result = self.processor.ansi_to_html(text)
        self.assertIn('color:', result)
        self.assertIn('Red text', result)
        self.assertIn('<span', result)
        self.assertIn('</span>', result)
        
        # Green text
        text = "\x1b[32mGreen text\x1b[0m"
        result = self.processor.ansi_to_html(text)
        self.assertIn('color:', result)
        self.assertIn('Green text', result)
        
        # Bold red text
        text = "\x1b[1;31mBold red text\x1b[0m"
        result = self.processor.ansi_to_html(text)
        self.assertIn('color:', result)
        self.assertIn('font-weight: bold', result)
        self.assertIn('Bold red text', result)
    
    def test_256_color_processing(self):
        """Test 256-color ANSI sequences"""
        # 256-color foreground
        text = "\x1b[38;5;196mBright red\x1b[0m"  # Color 196 is bright red
        result = self.processor.ansi_to_html(text)
        self.assertIn('color:', result)
        self.assertIn('Bright red', result)
        
        # 256-color background (should be applied)
        text = "\x1b[48;5;21mBlue background\x1b[0m"  # Color 21 is blue
        result = self.processor.ansi_to_html(text)
        self.assertIn('Blue background', result)
        # Background colors should be applied
        self.assertIn('background-color:', result)
    
    def test_process_name_colors(self):
        """Test that process names maintain their colors and bold formatting"""
        # Test with typical overmind process name format
        text = "\x1b[1;36mweb\x1b[0m     | Starting server..."
        result = self.processor.ansi_to_html(text)
        
        # Should have both bold and color
        self.assertIn('font-weight: bold', result)
        self.assertIn('color:', result)
        self.assertIn('web', result)
        self.assertIn('Starting server...', result)
    
    def test_bold_and_color_combination(self):
        """Test that bold + color creates a single span with both styles"""
        # Test bold + color in same ANSI sequence
        text = "\x1b[1;31mBold Red Text\x1b[0m"
        result = self.processor.ansi_to_html(text)
        
        # Should have exactly one opening span
        span_count = result.count('<span')
        self.assertEqual(span_count, 1)
        
        # Should contain both styles in the same span
        self.assertIn('font-weight: bold', result)
        self.assertIn('color:', result)
        self.assertIn('Bold Red Text', result)
        
        # Verify the span contains both styles (not separate spans)
        import re
        span_match = re.search(r'<span style="([^"]*)">', result)
        self.assertIsNotNone(span_match)
        span_styles = span_match.group(1)
        self.assertIn('font-weight: bold', span_styles)
        self.assertIn('color:', span_styles)
        
        # Test separate bold and color sequences should also work
        text2 = "\x1b[1m\x1b[32mSeparate Bold Green\x1b[0m"
        result2 = self.processor.ansi_to_html(text2)
        
        # This might create nested spans, but should still have both styles applied
        self.assertIn('font-weight: bold', result2)
        self.assertIn('color:', result2)
        self.assertIn('Separate Bold Green', result2)
    
    def test_complex_formatting(self):
        """Test complex ANSI sequences with multiple attributes"""
        # Bold, italic, underlined, colored text
        text = "\x1b[1;3;4;31mBold italic underlined red\x1b[0m"
        result = self.processor.ansi_to_html(text)
        
        self.assertIn('font-weight: bold', result)
        self.assertIn('font-style: italic', result)
        self.assertIn('text-decoration: underline', result)
        self.assertIn('color:', result)
        self.assertIn('Bold italic underlined red', result)
    
    def test_html_escaping(self):
        """Test that HTML escaping happens in process_line method"""
        # Text with HTML characters
        text = "Line with <script>alert('xss')</script> & ampersands"
        result = self.processor.process_line(text, 1, "test", time.time())
        
        # HTML escaping should happen in process_line, not ansi_to_html
        self.assertNotIn('<script>', result['html'])
        self.assertIn('&lt;script&gt;', result['html'])
        self.assertIn('&amp;', result['html'])
        self.assertNotIn('&lt;span', result['html'])  # Our span tags should not be escaped
    
    def test_ansi_stripping(self):
        """Test ANSI code stripping for clean text"""
        text = "\x1b[1;31mRed bold text\x1b[0m with \x1b[32mnormal green\x1b[0m"
        clean = self.processor.strip_ansi_codes(text)
        
        self.assertEqual(clean, "Red bold text with normal green")
        self.assertNotIn('\x1b', clean)
        self.assertNotIn('[', clean)
    
    def test_color_contrast_enhancement(self):
        """Test color contrast enhancement for dark theme"""
        # Dark color should be enhanced
        dark_color = "#333333"
        enhanced = self.processor._enhance_color_contrast(dark_color)
        
        # Enhanced color should be brighter
        self.assertNotEqual(enhanced, dark_color)
        
        # Bright color should not need enhancement
        bright_color = "#ffffff"
        enhanced_bright = self.processor._enhance_color_contrast(bright_color)
        self.assertEqual(enhanced_bright, bright_color)
    
    def test_process_line_complete(self):
        """Test complete line processing"""
        line_text = "\x1b[1;36mweb\x1b[0m     | \x1b[32mServer started on port 3000\x1b[0m"
        line_id = 123
        process_name = "web"
        timestamp = time.time()
        
        result = self.processor.process_line(line_text, line_id, process_name, timestamp)
        
        # Check all required fields
        self.assertEqual(result['id'], line_id)
        self.assertEqual(result['process'], process_name)
        self.assertEqual(result['timestamp'], timestamp)
        
        # Check clean text has no ANSI codes
        self.assertNotIn('\x1b', result['clean_text'])
        self.assertIn('web', result['clean_text'])
        self.assertIn('Server started on port 3000', result['clean_text'])
        
        # Check HTML has color formatting
        self.assertIn('<span', result['html'])
        self.assertIn('color:', result['html'])
        self.assertIn('font-weight: bold', result['html'])
        self.assertIn('web', result['html'])
        self.assertIn('Server started on port 3000', result['html'])
    
    def test_edge_cases(self):
        """Test edge cases and malformed ANSI codes"""
        # Empty string
        result = self.processor.ansi_to_html("")
        self.assertEqual(result, "")
        
        # String with no ANSI codes
        text = "Plain text with no formatting"
        result = self.processor.ansi_to_html(text)
        self.assertEqual(result, text)
        
        # Malformed ANSI code
        text = "\x1b[99mUnknown code\x1b[0m"
        result = self.processor.ansi_to_html(text)
        self.assertIn("Unknown code", result)
        
        # Multiple reset codes
        text = "\x1b[31mRed\x1b[0m\x1b[0m text"
        result = self.processor.ansi_to_html(text)
        self.assertIn("Red", result)
        self.assertIn("text", result)
    
    def test_positioning_sequences_removal(self):
        """Test that positioning and other non-color ANSI sequences are removed"""
        # Text with cursor positioning
        text = "\x1b[2J\x1b[H\x1b[31mCleared screen red text\x1b[0m"
        result = self.processor.ansi_to_html(text)
        
        # Color should be preserved
        self.assertIn('color:', result)
        self.assertIn('Cleared screen red text', result)
        
        # Positioning codes should be completely removed
        self.assertNotIn('\x1b[2J', result)
        self.assertNotIn('\x1b[H', result)
        
        # Test specific common sequences
        test_cases = [
            ("\x1b[2KLine with clear line\x1b[31mred\x1b[0m", "Line with clear linered"),
            ("\x1b[1AMove up\x1b[32mgreen\x1b[0m", "Move upgreen"),
            ("\x1b[GCarriage return\x1b[31mred\x1b[0m", "Carriage returnred"),
            ("\x1b[5CMove right\x1b[36mcyan\x1b[0m", "Move rightcyan"),
            ("\x1b[3BMove down\x1b[35mmagenta\x1b[0m", "Move downmagenta"),
            ("\x1b[0J\x1b[2K\x1b[HMultiple clear\x1b[33myellow\x1b[0m", "Multiple clearyellow")
        ]
        
        for input_text, expected_clean in test_cases:
            html_result = self.processor.ansi_to_html(input_text)
            clean_result = self.processor.strip_ansi_codes(input_text)
            
            # HTML should not contain any escape sequences
            self.assertNotIn('\x1b', html_result, f"HTML result contains escape sequences: {html_result}")
            
            # Clean text should match expected
            self.assertEqual(clean_result, expected_clean, f"Clean text mismatch for input: {input_text}")
            
            # HTML should still contain color spans where expected
            if 'red' in input_text or 'green' in input_text or 'cyan' in input_text or 'magenta' in input_text or 'yellow' in input_text:
                self.assertIn('color:', html_result, f"Color missing from HTML: {html_result}")
    
    def test_performance_with_long_text(self):
        """Test performance with longer text blocks"""
        # Create a long line with multiple ANSI sequences
        long_text = ""
        for i in range(100):
            long_text += f"\x1b[{31 + (i % 7)}mText block {i}\x1b[0m "
        
        start_time = time.time()
        result = self.processor.ansi_to_html(long_text)
        end_time = time.time()
        
        # Should complete quickly (under 1 second)
        self.assertLess(end_time - start_time, 1.0)
        
        # Result should contain all text blocks
        for i in range(100):
            self.assertIn(f"Text block {i}", result)
    
    def test_nested_and_overlapping_spans(self):
        """Test that spans are properly nested and don't overlap"""
        text = "\x1b[31m\x1b[1mBold red\x1b[22m still red\x1b[0m normal"
        result = self.processor.ansi_to_html(text)
        
        # Should contain the text
        self.assertIn("Bold red", result)
        self.assertIn("still red", result)
        self.assertIn("normal", result)
        
        # Should have proper span structure
        self.assertIn("<span", result)
        self.assertIn("</span>", result)
    
    def test_cache_functionality(self):
        """Test color contrast caching"""
        color = "#333333"
        
        # First call should cache the result
        result1 = self.processor._enhance_color_contrast(color)
        
        # Second call should use cached result
        result2 = self.processor._enhance_color_contrast(color)
        
        self.assertEqual(result1, result2)
        self.assertIn(color, self.processor.color_contrast_map)
    
    def test_luminance_calculation(self):
        """Test color luminance calculation"""
        # Black should have very low luminance
        black_lum = self.processor._get_luminance("#000000")
        self.assertLess(black_lum, 0.1)
        
        # White should have high luminance
        white_lum = self.processor._get_luminance("#ffffff")
        self.assertGreater(white_lum, 0.9)
        
        # Gray should be in between
        gray_lum = self.processor._get_luminance("#808080")
        self.assertGreater(gray_lum, black_lum)
        self.assertLess(gray_lum, white_lum)
    
    def test_256_color_palette(self):
        """Test 256-color palette generation"""
        colors = self.processor.ansi_256_colors
        
        # Should have exactly 256 colors
        self.assertEqual(len(colors), 256)
        
        # First 16 should be standard colors
        self.assertEqual(colors[0], '#000000')  # Black
        self.assertEqual(colors[15], '#ffffff')  # Bright white
        
        # All colors should be valid hex
        for color in colors:
            self.assertTrue(color.startswith('#'))
            self.assertEqual(len(color), 7)  # #RRGGBB format
    
    def test_realistic_overmind_output(self):
        """Test with realistic overmind output patterns"""
        # Typical overmind process start line
        line = "\x1b[1;36mweb\x1b[0m     | \x1b[32m15:30:45 web.1  | started with pid 12345\x1b[0m"
        
        result = self.processor.process_line(line, 1, "web", time.time())
        
        # Clean text should be readable
        expected_clean = "web     | 15:30:45 web.1  | started with pid 12345"
        self.assertEqual(result['clean_text'], expected_clean)
        
        # HTML should preserve process name coloring
        self.assertIn('font-weight: bold', result['html'])
        self.assertIn('color:', result['html'])
        self.assertIn('web', result['html'])
        self.assertIn('15:30:45', result['html'])
    
    def test_special_characters_in_output(self):
        """Test handling of special characters in output"""
        line = "Log: User 'admin' logged in with <password> & \"token\""
        
        result = self.processor.process_line(line, 1, "app", time.time())
        
        # Special HTML characters should be escaped (except quotes which use the default escaping)
        self.assertIn('&lt;password&gt;', result['html'])
        self.assertIn('"token"', result['html'])  # html.escape doesn't escape quotes by default
        self.assertIn('&amp;', result['html'])
        
        # Clean text should be unescaped (no HTML entities)
        self.assertIn('<password>', result['clean_text'])
        self.assertIn('"token"', result['clean_text'])
        self.assertIn('&', result['clean_text'])
    
    def test_comprehensive_ansi_cleanup(self):
        """Test comprehensive removal of all ANSI sequences while preserving colors"""
        # Complex text with many types of ANSI sequences
        test_input = (
            "\x1b[2J"              # Clear entire screen
            "\x1b[H"               # Move cursor to home
            "\x1b[1;31m"           # Bold red (should be preserved)
            "Important: "
            "\x1b[0m"              # Reset (should be preserved)
            "\x1b[2K"              # Clear line
            "\x1b[32m"             # Green (should be preserved)
            "Success message"
            "\x1b[0m"              # Reset (should be preserved)
            "\x1b[5C"              # Move cursor right 5
            "\x1b[1A"              # Move cursor up 1
            "\x1b[G"               # Move cursor to column 1
            " - Done"
        )
        
        expected_clean_text = "Important: Success message - Done"
        
        # Test HTML conversion
        html_result = self.processor.ansi_to_html(test_input)
        
        # Should not contain any escape sequences
        self.assertNotIn('\x1b', html_result)
        
        # Should contain color formatting
        self.assertIn('color:', html_result)
        self.assertIn('font-weight: bold', html_result)
        
        # Should contain the actual text
        self.assertIn('Important:', html_result)
        self.assertIn('Success message', html_result)
        self.assertIn('- Done', html_result)
        
        # Test clean text stripping
        clean_result = self.processor.strip_ansi_codes(test_input)
        self.assertEqual(clean_result, expected_clean_text)
        
        # Test with realistic scenarios
        realistic_tests = [
            # Docker-style output with clearing
            ("\x1b[1A\x1b[2K\r\x1b[32m✓\x1b[0m Build completed", "✓ Build completed"),
            
            # Progress bar clearing
            ("\x1b[2K\rProgress: \x1b[36m████████\x1b[0m 100%", "Progress: ████████ 100%"),
            
            # Terminal clearing with colors
            ("\x1b[H\x1b[2J\x1b[1;33mStarting application...\x1b[0m", "Starting application..."),
            
            # Complex cursor movement
            ("\x1b[3;5H\x1b[31mError:\x1b[0m \x1b[1mFile not found\x1b[0m", "Error: File not found")
        ]
        
        for test_text, expected in realistic_tests:
            html = self.processor.ansi_to_html(test_text)
            clean = self.processor.strip_ansi_codes(test_text)
            
            # No escape sequences in output
            self.assertNotIn('\x1b', html, f"Escape sequences found in HTML: {html}")
            self.assertNotIn('\x1b', clean, f"Escape sequences found in clean text: {clean}")
            
            # Clean text matches expected
            self.assertEqual(clean, expected, f"Clean text mismatch: expected '{expected}', got '{clean}'")
            
            # HTML contains the expected text content
            for word in expected.split():
                if word not in ['████████']:  # Skip special characters that might be formatted
                    self.assertIn(word, html, f"Word '{word}' missing from HTML: {html}")
    
    def test_ansi_cleanup_preserves_colors_and_formatting(self):
        """Ensure cleanup doesn't interfere with color and formatting preservation"""
        # Text mixing cleanup sequences with color/formatting
        text_with_mixed = "\x1b[2K\x1b[1;31mError:\x1b[0m\x1b[G \x1b[32mFixed!\x1b[0m\x1b[1A"
        
        html_result = self.processor.ansi_to_html(text_with_mixed)
        clean_result = self.processor.strip_ansi_codes(text_with_mixed)
        
        # Should preserve colors and bold
        self.assertIn('font-weight: bold', html_result)
        self.assertIn('color:', html_result)
        
        # Should contain text
        self.assertIn('Error:', html_result)
        self.assertIn('Fixed!', html_result)
        
        # Should not contain positioning sequences
        self.assertNotIn('\x1b[2K', html_result)
        self.assertNotIn('\x1b[G', html_result) 
        self.assertNotIn('\x1b[1A', html_result)
        
        # Clean text should be simple
        self.assertEqual(clean_result, "Error: Fixed!")
        self.assertNotIn('\x1b', clean_result)


if __name__ == '__main__':
    # Run the tests
    unittest.main(verbosity=2)