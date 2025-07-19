// Overmind GUI React Application
const { useState, useEffect, useRef, useCallback } = React;
const { createRoot } = ReactDOM;

// WebSocket connection
let ws = null;

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

// Component to render HTML safely
const AnsiText = ({ children }) => {
    const html = ansiToHtml(children);
    return <span dangerouslySetInnerHTML={{ __html: html }} />;
};

function App() {
    const [processes, setProcesses] = useState({});
    const [stats, setStats] = useState({total: 0, running: 0, selected: 0});
    const [output, setOutput] = useState([]);
    const [filterText, setFilterText] = useState('');
    const [searchText, setSearchText] = useState('');
    const [searchResults, setSearchResults] = useState([]);
    const [currentSearchIndex, setCurrentSearchIndex] = useState(-1);
    const [connected, setConnected] = useState(false);
    const [contextMenu, setContextMenu] = useState(null);
    const [autoScroll, setAutoScroll] = useState(true);
    const [overmindStatus, setOvermindStatus] = useState({status: 'connecting', error: null});
    
    const outputRef = useRef(null);
    const wsRef = useRef(null);
    
    // Initialize WebSocket connection
    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        const connectWebSocket = () => {
            ws = new WebSocket(wsUrl);
            wsRef.current = ws;
            
            ws.onopen = () => {
                console.log('WebSocket connected');
                setConnected(true);
            };
            
            ws.onmessage = (event) => {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            };
            
            ws.onclose = () => {
                console.log('WebSocket disconnected');
                setConnected(false);
                // Try to reconnect after 3 seconds
                setTimeout(connectWebSocket, 3000);
            };
            
            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };
        };
        
        connectWebSocket();
        
        return () => {
            if (ws) {
                ws.close();
            }
        };
    }, []);
    
    const handleWebSocketMessage = (message) => {
        switch (message.type) {
            case 'initial_state':
                setProcesses(message.data.processes.processes || {});
                setStats(message.data.processes.stats || {total: 0, running: 0, selected: 0});
                setOutput(message.data.output || []);
                break;
                
            case 'process_updated':
                setProcesses(prev => ({
                    ...prev,
                    [message.data.name]: {
                        ...prev[message.data.name],
                        selected: message.data.selected
                    }
                }));
                break;
                
            case 'status_update':
                // Update process statuses
                setProcesses(prev => {
                    const updated = {...prev};
                    Object.entries(message.data.updates || {}).forEach(([name, status]) => {
                        if (updated[name]) {
                            updated[name].status = status.toLowerCase();
                        }
                    });
                    return updated;
                });
                setStats(message.data.stats || stats);
                break;
                
            case 'output_line':
                setOutput(prev => [...prev, message.data.line]);
                break;
                
            case 'output_updated':
                setOutput(message.data.lines || []);
                break;
                
            case 'output_cleared':
                setOutput([]);
                break;
                
            case 'overmind_status':
                setOvermindStatus({
                    status: message.data.status,
                    error: message.data.error
                });
                break;
                
            case 'action_result':
                if (!message.data.success) {
                    alert(`Failed to ${message.data.action} ${message.data.process_name}`);
                }
                break;
        }
    };
    
    const sendMessage = (type, data) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type, data }));
        }
    };
    
    const toggleProcess = (processName) => {
        sendMessage('toggle_process', { process_name: processName });
    };
    
    const handleProcessAction = (processName, action) => {
        sendMessage('process_action', { process_name: processName, action });
        setContextMenu(null);
    };
    
    const clearOutput = () => {
        sendMessage('clear_output', {});
    };
    
    const selectAllProcesses = () => {
        Object.keys(processes).forEach(name => {
            if (!processes[name].selected) {
                toggleProcess(name);
            }
        });
    };
    
    const deselectAllProcesses = () => {
        Object.keys(processes).forEach(name => {
            if (processes[name].selected) {
                toggleProcess(name);
            }
        });
    };
    
    const handleContextMenu = (e, processName) => {
        e.preventDefault();
        setContextMenu({
            x: e.clientX,
            y: e.clientY,
            processName
        });
    };
    
    // Close context menu when clicking elsewhere
    useEffect(() => {
        const handleClick = () => setContextMenu(null);
        document.addEventListener('click', handleClick);
        return () => document.removeEventListener('click', handleClick);
    }, []);
    
    // Strip ANSI codes for searching (but keep them for display)
    const stripAnsiCodes = (text) => {
        return text.replace(/[\x1b\u001b]\[[0-9;]*m/g, '');
    };
    
    // Filter output based on filter text and selected processes
    const filteredOutput = output.filter(line => {
        // First check if line matches filter text (search in clean text)
        const cleanLine = stripAnsiCodes(line);
        const matchesFilter = !filterText || cleanLine.toLowerCase().includes(filterText.toLowerCase());
        
        // Then check if this line belongs to a selected process
        // Parse process name from line (format: "processname | output")
        if (cleanLine.includes(' | ')) {
            const processName = cleanLine.split(' | ')[0].trim();
            // Remove timestamps from process name
            const cleanName = processName.replace(/\d{2}:\d{2}:\d{2}\s+/, '').trim();
            const process = processes[cleanName];
            const isSelected = process ? process.selected : true; // Show unrecognized lines by default
            return matchesFilter && isSelected;
        }
        
        return matchesFilter; // Show non-process lines if they match filter
    });
    
    // Search functionality
    useEffect(() => {
        if (!searchText) {
            setSearchResults([]);
            setCurrentSearchIndex(-1);
            return;
        }
        
        const results = [];
        const searchLower = searchText.toLowerCase();
        
        filteredOutput.forEach((line, index) => {
            // Search in clean text without ANSI codes
            const cleanLine = stripAnsiCodes(line);
            if (cleanLine.toLowerCase().includes(searchLower)) {
                results.push(index);
            }
        });
        
        setSearchResults(results);
        setCurrentSearchIndex(results.length > 0 ? 0 : -1);
    }, [searchText, filteredOutput]);
    
    const nextSearch = () => {
        if (searchResults.length > 0) {
            setCurrentSearchIndex((prev) => (prev + 1) % searchResults.length);
        }
    };
    
    const prevSearch = () => {
        if (searchResults.length > 0) {
            setCurrentSearchIndex((prev) => 
                prev <= 0 ? searchResults.length - 1 : prev - 1
            );
        }
    };
    
    // Auto-scroll output
    useEffect(() => {
        if (outputRef.current && autoScroll && currentSearchIndex === -1) {
            outputRef.current.scrollTop = outputRef.current.scrollHeight;
        }
    }, [output, autoScroll]);
    
    // Scroll to search result
    useEffect(() => {
        if (currentSearchIndex >= 0 && outputRef.current) {
            const lineElements = outputRef.current.children;
            const lineElement = lineElements[searchResults[currentSearchIndex]];
            if (lineElement) {
                lineElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setAutoScroll(false); // Disable auto-scroll when searching
            }
        }
    }, [currentSearchIndex, searchResults]);
    
    // Handle scroll events to manage auto-scroll
    const handleScroll = () => {
        if (outputRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = outputRef.current;
            const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10;
            setAutoScroll(isAtBottom);
        }
    };
    
    // Handle keyboard shortcuts
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (e.ctrlKey || e.metaKey) {
                switch (e.key) {
                    case 'f':
                        e.preventDefault();
                        document.querySelector('.filter-input[placeholder*="Search"]')?.focus();
                        break;
                    case 'k':
                        e.preventDefault();
                        clearOutput();
                        break;
                }
            }
        };
        
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, []);
    
    if (!connected) {
        return (
            <div className="loading">
                <h1>Connecting to Overmind...</h1>
                <div className="spinner"></div>
                <p style={{marginTop: '20px', opacity: 0.8}}>
                    Make sure Overmind is running and accessible
                </p>
            </div>
        );
    }
    
    return (
        <div className="app">
            {/* Error banner for overmind failures */}
            {overmindStatus.status === 'failed' && (
                <div className="error-banner">
                    <div className="error-content">
                        <span className="error-icon">⚠️</span>
                        <div className="error-text">
                            <strong>Overmind Failed to Start</strong>
                            <div className="error-detail">{overmindStatus.error}</div>
                        </div>
                    </div>
                </div>
            )}
            
            <div className="process-bar">
                {Object.entries(processes).length === 0 ? (
                    <div style={{color: '#6c757d', fontStyle: 'italic'}}>
                        No processes loaded. Make sure there's a Procfile in the current directory.
                    </div>
                ) : (
                    Object.entries(processes).map(([name, process]) => (
                        <div
                            key={name}
                            className={`process-button ${process.selected ? 'selected' : ''} ${process.status}`}
                            onClick={() => toggleProcess(name)}
                            onContextMenu={(e) => handleContextMenu(e, name)}
                            title={`${name} - ${process.status} (Click to toggle, Right-click for actions)`}
                        >
                            <div className="process-name">{name}</div>
                            <div className={`process-status status-${process.status}`}>
                                {process.status}
                            </div>
                        </div>
                    ))
                )}
            </div>
            
            <div className="content">
                <div className="filters">
                    <div className="filter-group">
                        <label>Filter:</label>
                        <input
                            type="text"
                            className="filter-input"
                            placeholder="Filter output by text..."
                            value={filterText}
                            onChange={(e) => setFilterText(e.target.value)}
                            title="Filter output lines containing this text"
                        />
                        {filterText && (
                            <button 
                                className="btn" 
                                onClick={() => setFilterText('')}
                                title="Clear filter"
                            >
                                ✕
                            </button>
                        )}
                    </div>
                    
                    <div className="filter-group">
                        <label>Search:</label>
                        <input
                            type="text"
                            className="filter-input"
                            placeholder="Search and navigate..."
                            value={searchText}
                            onChange={(e) => setSearchText(e.target.value)}
                            title="Search through filtered output (Ctrl/Cmd+F)"
                        />
                        <div className="search-nav">
                            <button 
                                className="search-btn" 
                                onClick={prevSearch}
                                disabled={searchResults.length === 0}
                                title="Previous match"
                            >
                                ◀
                            </button>
                            <button 
                                className="search-btn" 
                                onClick={nextSearch}
                                disabled={searchResults.length === 0}
                                title="Next match"
                            >
                                ▶
                            </button>
                        </div>
                        {searchText && (
                            <>
                                <div className="search-count">
                                    {searchResults.length > 0 ? 
                                        `${currentSearchIndex + 1} of ${searchResults.length}` : 
                                        'No matches'
                                    }
                                </div>
                                <button 
                                    className="btn" 
                                    onClick={() => setSearchText('')}
                                    title="Clear search"
                                >
                                    ✕
                                </button>
                            </>
                        )}
                    </div>
                </div>
                
                <div className="output-container">
                    <div 
                        className="output" 
                        ref={outputRef}
                        onScroll={handleScroll}
                    >
                        {filteredOutput.length === 0 ? (
                            <div style={{color: '#6c757d', fontStyle: 'italic', textAlign: 'center', marginTop: '50px'}}>
                                {output.length === 0 ? 
                                    'No output yet. Waiting for process output...' :
                                    'No output matches current filter/selection.'
                                }
                            </div>
                        ) : (
                            filteredOutput.map((line, index) => (
                                <div
                                    key={index}
                                    className={`output-line ${
                                        searchResults.includes(index) && 
                                        searchResults[currentSearchIndex] === index ? 'highlight' : ''
                                    }`}
                                >
                                    <AnsiText>{line}</AnsiText>
                                </div>
                            ))
                        )}
                    </div>
                    
                    {!autoScroll && (
                        <div 
                            style={{
                                position: 'absolute',
                                bottom: '20px',
                                right: '20px',
                                background: 'rgba(0,123,255,0.9)',
                                color: 'white',
                                padding: '8px 12px',
                                borderRadius: '20px',
                                cursor: 'pointer',
                                fontSize: '12px',
                                boxShadow: '0 2px 10px rgba(0,0,0,0.2)'
                            }}
                            onClick={() => {
                                setAutoScroll(true);
                                if (outputRef.current) {
                                    outputRef.current.scrollTop = outputRef.current.scrollHeight;
                                }
                            }}
                            title="Click to return to bottom"
                        >
                            ↓ New output
                        </div>
                    )}
                </div>
            </div>
            
            <div className="footer">
                <div className="stats">
                    <span>Processes: {stats.total || 0}</span>
                    <span>Running: {stats.running || 0}</span>
                    <span>Selected: {stats.selected || 0}</span>
                    <span>Output Lines: {filteredOutput.length}</span>
                    <span>Total Lines: {output.length}</span>
                </div>
                <div className="action-buttons">
                    <button 
                        className="btn" 
                        onClick={selectAllProcesses}
                        title="Select all processes for output"
                    >
                        Select All
                    </button>
                    <button 
                        className="btn" 
                        onClick={deselectAllProcesses}
                        title="Deselect all processes"
                    >
                        Select None
                    </button>
                    <button 
                        className="btn btn-danger" 
                        onClick={clearOutput}
                        title="Clear all output (Ctrl/Cmd+K)"
                    >
                        Clear Output
                    </button>
                </div>
            </div>
            
            {contextMenu && (
                <div
                    className="context-menu"
                    style={{ left: contextMenu.x, top: contextMenu.y }}
                >
                    <div
                        className="context-menu-item"
                        onClick={() => handleProcessAction(contextMenu.processName, 'start')}
                    >
                        🟢 Start
                    </div>
                    <div
                        className="context-menu-item"
                        onClick={() => handleProcessAction(contextMenu.processName, 'stop')}
                    >
                        🛑 Stop
                    </div>
                    <div
                        className="context-menu-item"
                        onClick={() => handleProcessAction(contextMenu.processName, 'restart')}
                    >
                        🔄 Restart
                    </div>
                </div>
            )}
        </div>
    );
}

// Initialize the app
document.addEventListener('DOMContentLoaded', () => {
    const root = createRoot(document.getElementById('root'));
    root.render(<App />);
});

// Also initialize immediately in case DOMContentLoaded already fired
if (document.readyState === 'loading') {
    // Still loading, wait for DOMContentLoaded
} else {
    // Already loaded
    const root = createRoot(document.getElementById('root'));
    root.render(<App />);
}
