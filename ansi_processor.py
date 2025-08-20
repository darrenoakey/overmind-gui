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
        return html
    
    def strip_ansi_codes(self, text: str) -> str:
        """Strip ANSI codes for searching"""
        return self.ansi_regex.sub('', text)
    
    def process_line(self, line_text: str, line_id: int, process_name: str, timestamp: float) -> Dict:
        """Process a single line and return pre-rendered data"""
        # Strip ANSI for clean text (used for searching/filtering)
        clean_text = self.strip_ansi_codes(line_text)
        
        # First escape any existing HTML characters in the raw text (before ANSI processing)
        import html
        escaped_text = html.escape(line_text, quote=False)
        
        # Then convert ANSI codes to HTML spans (this preserves our HTML tags)
        html_content = self.ansi_to_html(escaped_text)
        
        return {
            'id': line_id,
            'text': line_text,  # Original with ANSI codes
            'clean_text': clean_text,  # For search/filter
            'html': html_content,  # Pre-rendered HTML
            'process': process_name,
            'timestamp': timestamp
        }


# Global instance
ansi_processor = ANSIProcessor()