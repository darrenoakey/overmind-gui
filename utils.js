// Utility functions for ANSI color handling

// Background color for contrast calculations (dark theme)
const BACKGROUND_COLOR = '#0f172a'; // --bg-primary from CSS

// Color mapping cache for contrast enhancement
const colorContrastMap = new Map();

// Calculate color contrast ratio between two colors
const getContrastRatio = (color1, color2) => {
    const getLuminance = (color) => {
        const hex = color.replace('#', '');
        const r = parseInt(hex.substr(0, 2), 16) / 255;
        const g = parseInt(hex.substr(2, 2), 16) / 255;
        const b = parseInt(hex.substr(4, 2), 16) / 255;
        
        const toLinear = (c) => c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
        
        return 0.2126 * toLinear(r) + 0.7152 * toLinear(g) + 0.0722 * toLinear(b);
    };
    
    const lum1 = getLuminance(color1);
    const lum2 = getLuminance(color2);
    const brightest = Math.max(lum1, lum2);
    const darkest = Math.min(lum1, lum2);
    
    return (brightest + 0.05) / (darkest + 0.05);
};

// Enhance color contrast if needed
const enhanceColorContrast = (originalColor) => {
    // Check cache first
    if (colorContrastMap.has(originalColor)) {
        return colorContrastMap.get(originalColor);
    }
    
    const contrastRatio = getContrastRatio(originalColor, BACKGROUND_COLOR);
    
    // If contrast is sufficient (4.5:1 for normal text), use original color
    if (contrastRatio >= 4.5) {
        colorContrastMap.set(originalColor, originalColor);
        return originalColor;
    }
    
    // Enhance the color by making it brighter/lighter
    const hex = originalColor.replace('#', '');
    let r = parseInt(hex.substr(0, 2), 16);
    let g = parseInt(hex.substr(2, 2), 16);
    let b = parseInt(hex.substr(4, 2), 16);
    
    // Increase brightness while preserving hue
    const factor = 1.8; // Increase brightness
    r = Math.min(255, Math.floor(r * factor));
    g = Math.min(255, Math.floor(g * factor));
    b = Math.min(255, Math.floor(b * factor));
    
    const enhancedColor = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    
    // Double-check the enhanced color has good contrast
    const newContrastRatio = getContrastRatio(enhancedColor, BACKGROUND_COLOR);
    
    let finalColor = enhancedColor;
    
    // If still not enough contrast, make it even brighter
    if (newContrastRatio < 4.5) {
        r = Math.min(255, Math.floor(r * 1.5));
        g = Math.min(255, Math.floor(g * 1.5));
        b = Math.min(255, Math.floor(b * 1.5));
        finalColor = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
    }
    
    // Cache the result
    colorContrastMap.set(originalColor, finalColor);
    
    return finalColor;
};

// 256-color palette (standard terminal colors)
const ansi256Colors = [
    // 0-15: Standard colors
    '#000000', '#800000', '#008000', '#808000', '#000080', '#800080', '#008080', '#c0c0c0',
    '#808080', '#ff0000', '#00ff00', '#ffff00', '#0000ff', '#ff00ff', '#00ffff', '#ffffff',
    
    // 16-231: 216 colors (6x6x6 color cube)
    ...Array.from({length: 216}, (_, i) => {
        const r = Math.floor(i / 36);
        const g = Math.floor((i % 36) / 6);
        const b = i % 6;
        const toHex = n => n === 0 ? '00' : (55 + n * 40).toString(16).padStart(2, '0');
        return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
    }),
    
    // 232-255: Grayscale
    ...Array.from({length: 24}, (_, i) => {
        const gray = (8 + i * 10).toString(16).padStart(2, '0');
        return `#${gray}${gray}${gray}`;
    })
];

// Basic ANSI color mapping for 8/16 colors
const ansiColors = {
    // Standard colors (30-37)
    '30': '#000000', // black
    '31': '#cd0000', // red
    '32': '#00cd00', // green
    '33': '#cdcd00', // yellow
    '34': '#0000ee', // blue
    '35': '#cd00cd', // magenta
    '36': '#00cdcd', // cyan
    '37': '#e5e5e5', // white
    
    // Bright colors (90-97)
    '90': '#7f7f7f', // bright black (gray)
    '91': '#ff0000', // bright red
    '92': '#00ff00', // bright green
    '93': '#ffff00', // bright yellow
    '94': '#5c5cff', // bright blue
    '95': '#ff00ff', // bright magenta
    '96': '#00ffff', // bright cyan
    '97': '#ffffff', // bright white
};

const ansiBgColors = {
    // Standard background colors (40-47)
    '40': '#000000', // black
    '41': '#cd0000', // red
    '42': '#00cd00', // green
    '43': '#cdcd00', // yellow
    '44': '#0000ee', // blue
    '45': '#cd00cd', // magenta
    '46': '#00cdcd', // cyan
    '47': '#e5e5e5', // white
    
    // Bright background colors (100-107)
    '100': '#7f7f7f', // bright black (gray)
    '101': '#ff0000', // bright red
    '102': '#00ff00', // bright green
    '103': '#ffff00', // bright yellow
    '104': '#5c5cff', // bright blue
    '105': '#ff00ff', // bright magenta
    '106': '#00ffff', // bright cyan
    '107': '#ffffff', // bright white
};

// Convert ANSI escape sequences to HTML
const ansiToHtml = (text) => {
    let html = text;
    
    // Handle both \x1b and \u001b escape sequences
    const ansiRegex = /[\x1b\u001b]\[([0-9;]*)m/g;
    
    // First, replace reset codes
    html = html.replace(/[\x1b\u001b]\[0*m/g, '</span>');
    
    // Handle other codes
    html = html.replace(ansiRegex, (match, codes) => {
        if (!codes) return '</span>';
        
        const codeList = codes.split(';').filter(c => c !== '');
        let styles = [];
        
        // Process codes sequentially, handling 256-color sequences
        for (let i = 0; i < codeList.length; i++) {
            const code = codeList[i];
            const codeNum = parseInt(code, 10);
            
            // Handle 256-color foreground: 38;5;N
            if (codeNum === 38 && i + 2 < codeList.length && codeList[i + 1] === '5') {
                const colorIndex = parseInt(codeList[i + 2], 10);
                if (colorIndex >= 0 && colorIndex < ansi256Colors.length) {
                    const originalColor = ansi256Colors[colorIndex];
                    const enhancedColor = enhanceColorContrast(originalColor);
                    styles.push(`color: ${enhancedColor}`);
                    i += 2; // Skip the next two codes (5 and colorIndex)
                    continue;
                }
            }
            
            // Handle 256-color background: 48;5;N
            if (codeNum === 48 && i + 2 < codeList.length && codeList[i + 1] === '5') {
                const colorIndex = parseInt(codeList[i + 2], 10);
                if (colorIndex >= 0 && colorIndex < ansi256Colors.length) {
                    const color = ansi256Colors[colorIndex];
                    styles.push(`background-color: ${color}`);
                    i += 2; // Skip the next two codes (5 and colorIndex)
                    continue;
                }
            }
            
            // Handle basic 8/16 colors
            if (ansiColors[code]) {
                const originalColor = ansiColors[code];
                const enhancedColor = enhanceColorContrast(originalColor);
                styles.push(`color: ${enhancedColor}`);
            } else if (ansiBgColors[code]) {
                styles.push(`background-color: ${ansiBgColors[code]}`);
            } else if (codeNum === 1) {
                styles.push('font-weight: bold');
            } else if (codeNum === 3) {
                styles.push('font-style: italic');
            } else if (codeNum === 4) {
                styles.push('text-decoration: underline');
            } else if (codeNum === 22) {
                styles.push('font-weight: normal');
            } else if (codeNum === 23) {
                styles.push('font-style: normal');
            } else if (codeNum === 24) {
                styles.push('text-decoration: none');
            }
        }
        
        if (styles.length > 0) {
            const result = `<span style="${styles.join('; ')}">`;
            return result;
        }
        
        return '';
    });
    
    return html;
};

// Highlight search terms in text while preserving ANSI formatting
const highlightSearchInHtml = (html, searchTerm) => {
    if (!searchTerm) return html;
    
    // Create a regex for the search term (case insensitive)
    const searchRegex = new RegExp(`(${searchTerm.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
    
    // We need to be careful not to highlight inside HTML tags
    // Split by HTML tags to process only text content
    const parts = html.split(/(<[^>]*>)/);
    
    return parts.map(part => {
        // If this part is an HTML tag, leave it unchanged
        if (part.startsWith('<') && part.endsWith('>')) {
            return part;
        }
        // Otherwise, highlight search terms in the text content
        return part.replace(searchRegex, '<mark class="search-highlight">$1</mark>');
    }).join('');
};

// Strip ANSI codes for searching (but keep them for display)
const stripAnsiCodes = (text) => {
    return text.replace(/[\x1b\u001b]\[[0-9;]*m/g, '');
};

// Get color mapping stats for debugging
const getColorMappingStats = () => {
    const stats = {
        totalMappings: colorContrastMap.size,
        enhancedColors: 0,
        originalColors: 0,
        mappings: {}
    };
    
    for (const [original, enhanced] of colorContrastMap.entries()) {
        stats.mappings[original] = enhanced;
        if (original === enhanced) {
            stats.originalColors++;
        } else {
            stats.enhancedColors++;
        }
    }
    
    return stats;
};

// Export for use in other files
window.AnsiUtils = {
    ansiToHtml,
    highlightSearchInHtml,
    stripAnsiCodes,
    getColorMappingStats,
    enhanceColorContrast // For debugging
};
