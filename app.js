// Overmind GUI React Application - Main App Component
const { useState, useEffect, useRef, useCallback } = React;
const { createRoot } = ReactDOM;

function App() {
    // State management
    const [processes, setProcesses] = useState({});
    const [stats, setStats] = useState({total: 0, running: 0, selected: 0});
    const [output, setOutput] = useState([]);
    const [filterText, setFilterText] = useState('');
    const [searchText, setSearchText] = useState('');
    const [connected, setConnected] = useState(false);
    const [contextMenu, setContextMenu] = useState(null);
    const [autoScroll, setAutoScroll] = useState(true);
    const [overmindStatus, setOvermindStatus] = useState({status: 'connecting', error: null});
    
    // Refs
    const outputRef = useRef(null);
    
    // Initialize search manager
    const searchManagerRef = useRef(new window.SearchManager());
    const searchManager = searchManagerRef.current;
    
    // Initialize WebSocket manager
    const wsManagerRef = useRef(new window.WebSocketManager());
    const wsManager = wsManagerRef.current;
    
    // Set output ref for search manager
    useEffect(() => {
        searchManager.setOutputRef(outputRef);
    }, []);
    
    // WebSocket message handlers
    useEffect(() => {
        const handleInitialState = (data) => {
            setProcesses(data.processes.processes || {});
            setStats(data.processes.stats || {total: 0, running: 0, selected: 0});
            setOutput(data.output || []);
        };
        
        const handleProcessUpdated = (data) => {
            setProcesses(prev => ({
                ...prev,
                [data.name]: {
                    ...prev[data.name],
                    selected: data.selected
                }
            }));
        };
        
        const handleStatusUpdate = (data) => {
            setProcesses(prev => {
                const updated = {...prev};
                Object.entries(data.updates || {}).forEach(([name, status]) => {
                    if (updated[name]) {
                        updated[name].status = status.toLowerCase();
                    }
                });
                return updated;
            });
            setStats(data.stats || stats);
        };
        
        const handleOutputLine = (data) => {
            setOutput(prev => [...prev, data.line]);
        };
        
        const handleOutputUpdated = (data) => {
            setOutput(data.lines || []);
        };
        
        const handleOutputCleared = () => {
            setOutput([]);
            // Clear search when output is cleared
            searchManager.clearSearch();
        };
        
        const handleOvermindStatus = (data) => {
            setOvermindStatus({
                status: data.status,
                error: data.error
            });
        };
        
        const handleActionResult = (data) => {
            if (!data.success) {
                alert(`Failed to ${data.action} ${data.process_name}`);
            }
        };
        
        // Register handlers
        wsManager.registerHandler('initial_state', handleInitialState);
        wsManager.registerHandler('process_updated', handleProcessUpdated);
        wsManager.registerHandler('status_update', handleStatusUpdate);
        wsManager.registerHandler('output_line', handleOutputLine);
        wsManager.registerHandler('output_updated', handleOutputUpdated);
        wsManager.registerHandler('output_cleared', handleOutputCleared);
        wsManager.registerHandler('overmind_status', handleOvermindStatus);
        wsManager.registerHandler('action_result', handleActionResult);
        
        // Connect to WebSocket
        wsManager.connect(setConnected);
        
        // Cleanup on unmount
        return () => {
            wsManager.disconnect();
        };
    }, []);
    
    // Filter output based on filter text and selected processes
    const filteredOutput = output.filter(line => {
        // First check if line matches filter text (search in clean text)
        const cleanLine = window.AnsiUtils.stripAnsiCodes(line);
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
    
    // Update search when search text or filtered output changes
    useEffect(() => {
        searchManager.updateSearch(searchText, filteredOutput);
    }, [searchText, filteredOutput]);
    
    // WebSocket communication functions
    const sendMessage = (type, data) => {
        return wsManager.sendMessage(type, data);
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
    
    // Search navigation functions
    const nextSearch = () => {
        if (searchManager.nextSearch()) {
            setAutoScroll(false); // Disable auto-scroll when actively searching
        }
    };
    
    const prevSearch = () => {
        if (searchManager.prevSearch()) {
            setAutoScroll(false); // Disable auto-scroll when actively searching
        }
    };
    
    // Clear search and re-enable auto-scroll
    const clearSearch = () => {
        searchManager.clearSearch();
        setSearchText('');
        setAutoScroll(true);
    };
    
    // Auto-scroll output (only when not actively searching)
    useEffect(() => {
        const searchState = searchManager.getSearchState();
        if (outputRef.current && autoScroll && !searchState.hasResults && !searchState.isNavigating) {
            outputRef.current.scrollTop = outputRef.current.scrollHeight;
        }
    }, [output, autoScroll]);
    
    // Handle scroll events to manage auto-scroll
    const handleScroll = () => {
        if (outputRef.current) {
            const { scrollTop, scrollHeight, clientHeight } = outputRef.current;
            const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10;
            
            // Only manage auto-scroll if we're not actively searching
            const searchState = searchManager.getSearchState();
            if (!searchState.hasResults && !searchState.isNavigating) {
                if (isAtBottom) {
                    setAutoScroll(true);
                } else {
                    setAutoScroll(false);
                }
            }
        }
    };
    
    const scrollToBottom = () => {
        setAutoScroll(true);
        if (outputRef.current) {
            outputRef.current.scrollTop = outputRef.current.scrollHeight;
        }
    };
    
    // Close context menu when clicking elsewhere
    useEffect(() => {
        const handleClick = () => setContextMenu(null);
        document.addEventListener('click', handleClick);
        return () => document.removeEventListener('click', handleClick);
    }, []);
    
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
            
            // Escape key to clear search
            if (e.key === 'Escape') {
                if (searchText) {
                    clearSearch();
                }
            }
        };
        
        document.addEventListener('keydown', handleKeyDown);
        return () => document.removeEventListener('keydown', handleKeyDown);
    }, [searchText]);
    
    // Show loading screen if not connected
    if (!connected) {
        return React.createElement(window.Components.LoadingScreen);
    }
    
    return React.createElement('div', { className: 'app' },
        // Error banner
        React.createElement(window.Components.ErrorBanner, {
            status: overmindStatus.status,
            error: overmindStatus.error
        }),
        
        // Process bar
        React.createElement(window.Components.ProcessBar, {
            processes,
            onToggleProcess: toggleProcess,
            onContextMenu: handleContextMenu
        }),
        
        // Content area
        React.createElement('div', { className: 'content' },
            // Filter controls
            React.createElement(window.Components.FilterControls, {
                filterText,
                onFilterChange: setFilterText,
                searchText,
                onSearchChange: setSearchText,
                searchManager,
                onNextSearch: nextSearch,
                onPrevSearch: prevSearch,
                onClearFilter: () => setFilterText(''),
                onClearSearch: clearSearch
            }),
            
            // Output display
            React.createElement(window.Components.OutputDisplay, {
                filteredOutput,
                output,
                outputRef,
                onScroll: handleScroll,
                autoScroll,
                onScrollToBottom: scrollToBottom,
                searchManager
            })
        ),
        
        // Footer
        React.createElement(window.Components.Footer, {
            stats,
            filteredOutput,
            output,
            onSelectAll: selectAllProcesses,
            onDeselectAll: deselectAllProcesses,
            onClearOutput: clearOutput
        }),
        
        // Context menu
        React.createElement(window.Components.ContextMenu, {
            contextMenu,
            onProcessAction: handleProcessAction
        })
    );
}

// Initialize the app
const initializeApp = () => {
    const root = createRoot(document.getElementById('root'));
    root.render(React.createElement(App));
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initializeApp);

// Also initialize immediately in case DOMContentLoaded already fired
if (document.readyState !== 'loading') {
    initializeApp();
}
