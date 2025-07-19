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
    const [overmindStatus, setOvermindStatus] = useState({status: 'connecting', error: null});
    
    // Core scroll state - this is the key state that controls everything
    const [boundToEnd, setBoundToEnd] = useState(true);
    
    // Track if we're in the middle of programmatic scrolling to avoid state changes
    const [isProgrammaticScroll, setIsProgrammaticScroll] = useState(false);
    
    // Track pending actions for status refresh
    const [pendingActions, setPendingActions] = useState(new Set());
    
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
            searchManager.clearSearch();
            setBoundToEnd(true); // Always bound to end after clearing
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
                // If action failed, immediately refresh status to get current state
                requestStatusRefresh();
            } else {
                // Action succeeded, schedule delayed status refresh
                scheduleStatusRefresh(data.process_name);
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
    
    // Handle new output arriving - scroll to end if bound to end
    useEffect(() => {
        if (boundToEnd && outputRef.current) {
            setIsProgrammaticScroll(true);
            outputRef.current.scrollTop = outputRef.current.scrollHeight;
            // Reset the flag after scroll completes
            setTimeout(() => setIsProgrammaticScroll(false), 50);
        }
    }, [output, boundToEnd]);
    
    // Handle filtered output changes - if we're searching, maintain search position
    useEffect(() => {
        const searchState = searchManager.getSearchState();
        if (searchState.hasResults && searchState.currentIndex >= 0) {
            // We're actively searching, let search manager handle positioning
            setTimeout(() => {
                searchManager.scrollToCurrentResult();
            }, 50);
        }
    }, [filteredOutput]);
    
    // WebSocket communication functions
    const sendMessage = (type, data) => {
        return wsManager.sendMessage(type, data);
    };
    
    const toggleProcess = (processName) => {
        sendMessage('toggle_process', { process_name: processName });
    };
    
    // Request status refresh from backend
    const requestStatusRefresh = () => {
        sendMessage('get_initial_state', {});
    };
    
    // Schedule status refresh after action completes + 2 seconds
    const scheduleStatusRefresh = (processName) => {
        // Add to pending actions
        setPendingActions(prev => new Set(prev).add(processName));
        
        // Schedule refresh after 2 seconds
        setTimeout(() => {
            requestStatusRefresh();
            // Remove from pending actions
            setPendingActions(prev => {
                const newSet = new Set(prev);
                newSet.delete(processName);
                return newSet;
            });
        }, 2000);
    };
    
    const handleProcessAction = (processName, action) => {
        // Immediately set status to unknown
        setProcesses(prev => ({
            ...prev,
            [processName]: {
                ...prev[processName],
                status: 'unknown'
            }
        }));
        
        // Close context menu immediately
        setContextMenu(null);
        
        // Map "start" to "restart" since overmind doesn't have a start command
        const actualAction = action === 'start' ? 'restart' : action;
        sendMessage('process_action', { process_name: processName, action: actualAction });
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
    
    // Search navigation functions - these turn off boundToEnd
    const nextSearch = () => {
        if (searchManager.nextSearch()) {
            setBoundToEnd(false); // Rule b: searching turns off bound to end
        }
    };
    
    const prevSearch = () => {
        if (searchManager.prevSearch()) {
            setBoundToEnd(false); // Rule b: searching turns off bound to end
        }
    };
    
    // Handle search text changes - turn off boundToEnd when starting to search
    const handleSearchChange = (newSearchText) => {
        setSearchText(newSearchText);
        if (newSearchText.trim() !== '') {
            setBoundToEnd(false); // Rule b: non-blank search turns off bound to end
        }
    };
    
    // Clear search - NOW BINDS TO END like clicking new output
    const clearSearch = () => {
        searchManager.clearSearch();
        setSearchText('');
        setBoundToEnd(true); // NEW: clearing search binds us back to end
        scrollToBottom(); // Immediately scroll to bottom
    };
    
    // Force scroll to bottom and turn on boundToEnd - Rule a
    const scrollToBottom = () => {
        setBoundToEnd(true);
        if (outputRef.current) {
            setIsProgrammaticScroll(true);
            outputRef.current.scrollTop = outputRef.current.scrollHeight;
            setTimeout(() => setIsProgrammaticScroll(false), 50);
        }
    };
    
    // Handle user scrolling - Rule c: user scrolling can turn off boundToEnd
    const handleScroll = () => {
        // Only react to user scrolling, not programmatic scrolling
        if (isProgrammaticScroll || !outputRef.current) return;
        
        const { scrollTop, scrollHeight, clientHeight } = outputRef.current;
        const isAtBottom = scrollTop + clientHeight >= scrollHeight - 10;
        
        // If user scrolled away from bottom, turn off boundToEnd
        if (!isAtBottom && boundToEnd) {
            setBoundToEnd(false);
        }
        // Note: we don't automatically turn boundToEnd back on when user scrolls to bottom
        // That only happens when they click the "new output" button
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
                onSearchChange: handleSearchChange,
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
                boundToEnd: boundToEnd,
                onScrollToBottom: scrollToBottom,
                searchManager,
                searchTerm: searchText // Pass search term for highlighting
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
        
        // Context menu - now passes processes for smart menu
        React.createElement(window.Components.ContextMenu, {
            contextMenu,
            processes, // Pass processes so context menu can determine status
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
