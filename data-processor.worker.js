/**
 * Data Processing Web Worker
 * Layer 1: Handles all computationally intensive tasks off the main thread
 * - ANSI parsing and colorization
 * - Text processing for search/filter
 * - Batching and queuing
 */

// ANSI processing functionality (optimized for worker)
class WorkerANSIProcessor {
    constructor() {
        // Background color for contrast calculations
        this.backgroundColorHex = '#0f172a';
        
        // Cache for color contrast calculations
        this.colorCache = new Map();
        
        // 256-color palette
        this.ansi256Colors = this.buildColorPalette();
        
        // Basic color mappings
        this.ansiColors = {
            '30': '#000000', '31': '#cd0000', '32': '#00cd00', '33': '#cdcd00',
            '34': '#0000ee', '35': '#cd00cd', '36': '#00cdcd', '37': '#e5e5e5',
            '90': '#7f7f7f', '91': '#ff0000', '92': '#00ff00', '93': '#ffff00',
            '94': '#5c5cff', '95': '#ff00ff', '96': '#00ffff', '97': '#ffffff',
        };
        
        this.ansiBgColors = {
            '40': '#000000', '41': '#cd0000', '42': '#00cd00', '43': '#cdcd00',
            '44': '#0000ee', '45': '#cd00cd', '46': '#00cdcd', '47': '#e5e5e5',
            '100': '#7f7f7f', '101': '#ff0000', '102': '#00ff00', '103': '#ffff00',
            '104': '#5c5cff', '105': '#ff00ff', '106': '#00ffff', '107': '#ffffff',
        };
        
        // Compiled regex for performance
        this.ansiRegex = /[\x1b\u001b]\[([0-9;]*)m/g;
        this.resetRegex = /[\x1b\u001b]\[0*m/g;
    }
    
    buildColorPalette() {
        const colors = [];
        
        // 0-15: Standard colors
        colors.push(
            '#000000', '#800000', '#008000', '#808000', '#000080', '#800080', '#008080', '#c0c0c0',
            '#808080', '#ff0000', '#00ff00', '#ffff00', '#0000ff', '#ff00ff', '#00ffff', '#ffffff'
        );
        
        // 16-231: 216 colors (6x6x6 cube)
        for (let i = 0; i < 216; i++) {
            const r = Math.floor(i / 36);
            const g = Math.floor((i % 36) / 6);
            const b = i % 6;
            const toHex = n => n === 0 ? '00' : (55 + n * 40).toString(16).padStart(2, '0');
            colors.push(`#${toHex(r)}${toHex(g)}${toHex(b)}`);
        }
        
        // 232-255: Grayscale
        for (let i = 0; i < 24; i++) {
            const gray = (8 + i * 10).toString(16).padStart(2, '0');
            colors.push(`#${gray}${gray}${gray}`);
        }
        
        return colors;
    }
    
    enhanceColorContrast(color) {
        if (this.colorCache.has(color)) {
            return this.colorCache.get(color);
        }
        
        // Simple contrast enhancement - make colors brighter for dark theme
        const hex = color.replace('#', '');
        let r = parseInt(hex.substr(0, 2), 16);
        let g = parseInt(hex.substr(2, 2), 16);
        let b = parseInt(hex.substr(4, 2), 16);
        
        // Increase brightness
        const factor = 1.8;
        r = Math.min(255, Math.floor(r * factor));
        g = Math.min(255, Math.floor(g * factor));
        b = Math.min(255, Math.floor(b * factor));
        
        const enhanced = `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
        
        this.colorCache.set(color, enhanced);
        return enhanced;
    }
    
    ansiToHtml(text) {
        // Escape HTML first
        let html = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        
        // Replace reset codes
        html = html.replace(this.resetRegex, '</span>');
        
        // Handle other codes
        html = html.replace(this.ansiRegex, (match, codes) => {
            if (!codes) return '</span>';
            
            const codeList = codes.split(';').filter(c => c !== '');
            const styles = [];
            
            let i = 0;
            while (i < codeList.length) {
                const code = codeList[i];
                const codeNum = parseInt(code, 10);
                
                // 256-color foreground: 38;5;N
                if (codeNum === 38 && i + 2 < codeList.length && codeList[i + 1] === '5') {
                    const colorIndex = parseInt(codeList[i + 2], 10);
                    if (colorIndex >= 0 && colorIndex < this.ansi256Colors.length) {
                        const color = this.enhanceColorContrast(this.ansi256Colors[colorIndex]);
                        styles.push(`color: ${color}`);
                        i += 3;
                        continue;
                    }
                }
                
                // 24-bit RGB foreground: 38;2;r;g;b
                if (codeNum === 38 && i + 4 < codeList.length && codeList[i + 1] === '2') {
                    const r = parseInt(codeList[i + 2], 10);
                    const g = parseInt(codeList[i + 3], 10);
                    const b = parseInt(codeList[i + 4], 10);
                    if (r >= 0 && r <= 255 && g >= 0 && g <= 255 && b >= 0 && b <= 255) {
                        const color = this.enhanceColorContrast(`#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`);
                        styles.push(`color: ${color}`);
                        i += 5;
                        continue;
                    }
                }
                
                // 256-color background: 48;5;N - parse but don't apply
                if (codeNum === 48 && i + 2 < codeList.length && codeList[i + 1] === '5') {
                    const colorIndex = parseInt(codeList[i + 2], 10);
                    if (colorIndex >= 0 && colorIndex < this.ansi256Colors.length) {
                        // Background colors are parsed but not applied for readability
                        i += 3;
                        continue;
                    }
                }
                
                // 24-bit RGB background: 48;2;r;g;b - parse but don't apply
                if (codeNum === 48 && i + 4 < codeList.length && codeList[i + 1] === '2') {
                    const r = parseInt(codeList[i + 2], 10);
                    const g = parseInt(codeList[i + 3], 10);
                    const b = parseInt(codeList[i + 4], 10);
                    if (r >= 0 && r <= 255 && g >= 0 && g <= 255 && b >= 0 && b <= 255) {
                        // Background colors are parsed but not applied for readability
                        i += 5;
                        continue;
                    }
                }
                
                // Basic colors and styles
                if (this.ansiColors[code]) {
                    const color = this.enhanceColorContrast(this.ansiColors[code]);
                    styles.push(`color: ${color}`);
                } else if (this.ansiBgColors[code]) {
                    // Background colors are parsed but not applied for readability
                    // Just consume the code without adding any styles
                } else if (codeNum === 1) {
                    styles.push('font-weight: bold');
                } else if (codeNum === 3) {
                    styles.push('font-style: italic');
                } else if (codeNum === 4) {
                    styles.push('text-decoration: underline');
                }
                
                i++;
            }
            
            return styles.length > 0 ? `<span style="${styles.join('; ')}">` : '';
        });
        
        return html;
    }
    
    stripAnsi(text) {
        return text.replace(/[\x1b\u001b]\[[0-9;]*m/g, '');
    }
    
    processLine(rawLine, lineId, processName, timestamp) {
        const cleanText = this.stripAnsi(rawLine);
        const htmlContent = this.ansiToHtml(rawLine);
        
        return {
            id: lineId,
            rawText: rawLine,
            cleanText: cleanText,
            htmlContent: htmlContent,
            processName: processName,
            timestamp: timestamp,
            // Add computed properties for virtualization
            estimatedHeight: Math.ceil(cleanText.length / 80) * 20 + 4 // Rough estimate
        };
    }
}

// Initialize processor
const ansiProcessor = new WorkerANSIProcessor();

// Message handling
self.onmessage = function(e) {
    const { type, data } = e.data;
    
    switch (type) {
        case 'PROCESS_BATCH':
            // Process a batch of raw lines
            const processedLines = data.lines.map(line => 
                ansiProcessor.processLine(line.text, line.id, line.process, line.timestamp)
            );
            
            // Send back processed batch
            self.postMessage({
                type: 'BATCH_PROCESSED',
                data: {
                    processedLines: processedLines,
                    statusUpdates: data.statusUpdates || {},
                    batchId: data.batchId
                }
            });
            break;
            
        case 'PROCESS_SINGLE':
            // Process a single line (for real-time updates)
            const processedLine = ansiProcessor.processLine(
                data.text, data.id, data.process, data.timestamp
            );
            
            self.postMessage({
                type: 'LINE_PROCESSED',
                data: processedLine
            });
            break;
            
        case 'CLEAR_CACHE':
            // Clear color cache to prevent memory leaks
            ansiProcessor.colorCache.clear();
            self.postMessage({
                type: 'CACHE_CLEARED'
            });
            break;
            
        default:
            console.warn('Unknown worker message type:', type);
    }
};

// Send ready signal
self.postMessage({
    type: 'WORKER_READY'
});