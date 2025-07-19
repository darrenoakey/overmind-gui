// Utility functions for ANSI color handling

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
                    const color = ansi256Colors[colorIndex];
                    styles.push(`color: ${color}`);
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
                styles.push(`color: ${ansiColors[code]}`);
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

// Strip ANSI codes for searching (but keep them for display)
const stripAnsiCodes = (text) => {
    return text.replace(/[\x1b\u001b]\[[0-9;]*m/g, '');
};

// Export for use in other files
window.AnsiUtils = {
    ansiToHtml,
    stripAnsiCodes
};
