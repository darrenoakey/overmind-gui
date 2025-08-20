/**
 * High-Performance Overmind GUI with React Virtuoso
 * Implements proper 4-layer architecture with React components
 */

// ES Module imports using importmap
import React, { useState, useEffect, useRef, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import { Virtuoso } from 'react-virtuoso';

// React and React Virtuoso imports successful

// Local module imports
import StateManager from './state-manager.js';
import PollingManager from './polling.js';


// Layer 1: Web Worker for data processing
class DataProcessor {
    constructor() {
        this.worker = null;
        this.workerReady = false;
        this.callbacks = new Map();
        this.messageId = 0;
    }
    
    async init() {
        return new Promise((resolve, reject) => {
            try {
                this.worker = new Worker('/data-processor.worker.js');
                
                this.worker.onmessage = (e) => {
                    this.handleWorkerMessage(e.data);
                };
                
                this.worker.onerror = (error) => {
                    console.error('Worker error:', error);
                    reject(error);
                };
                
                // Wait for ready signal
                const checkReady = (e) => {
                    if (e.data.type === 'WORKER_READY') {
                        this.workerReady = true;
                        this.worker.removeEventListener('message', checkReady);
                        resolve();
                    }
                };
                
                this.worker.addEventListener('message', checkReady);
                
                setTimeout(() => {
                    if (!this.workerReady) {
                        reject(new Error('Worker timeout'));
                    }
                }, 5000);
                
            } catch (error) {
                reject(error);
            }
        });
    }
    
    handleWorkerMessage(message) {
        // Handle processed data and invoke callbacks
        if (message.type === 'BATCH_PROCESSED' && this.onBatchProcessed) {
            this.onBatchProcessed(message.data.processedLines);
        }
    }
    
    processBatch(lines) {
        if (!this.workerReady) return;
        
        // Convert API format to worker format
        const workerLines = lines.map(line => ({
            text: line.text || line.html || '',
            id: line.id,
            process: line.process,
            timestamp: line.timestamp
        }));
        
        this.worker.postMessage({
            type: 'PROCESS_BATCH',
            data: {
                lines: workerLines,
                batchId: Date.now()
            }
        });
    }
    
    destroy() {
        if (this.worker) {
            this.worker.terminate();
        }
    }
}

// Main React App Component
function OvermindApp() {
    // State
    const [lines, setLines] = useState([]);
    const [processes, setProcesses] = useState({});
    const [stats, setStats] = useState({});
    const [isConnected, setIsConnected] = useState(false);
    const [autoScroll, setAutoScroll] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterText, setFilterText] = useState('');
    const [version, setVersion] = useState('');
    
    // Refs
    const virtuosoRef = useRef(null);
    const dataProcessor = useRef(null);
    const pollingManager = useRef(null);
    const stateManager = useRef(null);
    const autoScrollRef = useRef(autoScroll);
    
    // Initialize everything
    useEffect(() => {
        initializeApp();
        fetchVersion();
        return cleanup;
    }, []);
    
    // Debug autoScroll changes and keep ref in sync
    useEffect(() => {
        console.log('AutoScroll state changed to:', autoScroll);
        autoScrollRef.current = autoScroll;
    }, [autoScroll]);
    
    const fetchVersion = async () => {
        try {
            const response = await fetch('/api/state');
            const data = await response.json();
            setVersion(data.version || '');
        } catch (error) {
            console.error('Error fetching version:', error);
            setVersion('');
        }
    };
    
    const loadProcessList = async () => {
        try {
            const response = await fetch('/api/state');
            const data = await response.json();
            console.log('Initial state data:', data); // Debug log
            
            // Try to get processes from either status_updates or processes field
            const processData = data.status_updates || data.processes || {};
            console.log('Process data:', processData); // Debug log
            
            if (Object.keys(processData).length > 0) {
                setProcesses(processData);
                console.log('Set processes:', processData);
            } else {
                console.log('No processes found in state');
            }
        } catch (error) {
            console.error('Error loading process list:', error);
        }
    };
    
    const initializeApp = async () => {
        try {
            console.log('🚀 Initializing high-performance Overmind GUI...');
            
            // Layer 1: Initialize data processor
            dataProcessor.current = new DataProcessor();
            await dataProcessor.current.init();
            
            // Load initial process list
            await loadProcessList();
            
            // Set up data processor callback
            dataProcessor.current.onBatchProcessed = (processedLines) => {
                setLines(prevLines => {
                    const newLines = [...prevLines, ...processedLines];
                    // Maintain line limit
                    return newLines.length > 5000 ? newLines.slice(-5000) : newLines;
                });
                
                // If auto-scroll is enabled, ensure we scroll to bottom after adding new lines
                setTimeout(() => {
                    if (autoScrollRef.current && virtuosoRef.current) {
                        console.log('Auto-scrolling to bottom after new lines added');
                        virtuosoRef.current.scrollToIndex({ index: 'LAST', behavior: 'auto' });
                    }
                }, 10);
            };
            
            // Layer 2: Initialize state manager
            stateManager.current = new StateManager();
            
            // Initialize polling
            pollingManager.current = new PollingManager();
            pollingManager.current.onPollingResponse = handlePollingData;
            pollingManager.current.onError = (error) => {
                console.error('Polling error:', error);
                setIsConnected(false);
            };
            
            pollingManager.current.start();
            
            console.log('✅ High-performance GUI initialized');
            
            // Hide loading overlay after successful initialization
            const loadingOverlay = document.getElementById('loading-overlay');
            if (loadingOverlay) {
                loadingOverlay.classList.add('hidden');
            }
            
        } catch (error) {
            console.error('❌ Failed to initialize:', error);
            alert('Failed to initialize: ' + error.message);
            
            // Hide loading overlay even on error
            const loadingOverlay = document.getElementById('loading-overlay');
            if (loadingOverlay) {
                loadingOverlay.classList.add('hidden');
            }
        }
    };
    
    const handlePollingData = (data) => {
        setIsConnected(true);
        
        // Update only status of existing processes
        if (data.status_updates) {
            setProcesses(prev => {
                const updated = { ...prev };
                Object.entries(data.status_updates).forEach(([processName, statusData]) => {
                    if (updated[processName]) {
                        // Update existing process status, preserve selection state
                        updated[processName] = {
                            ...updated[processName],
                            status: statusData.status || statusData,
                            // Keep existing selection state
                            selected: updated[processName].selected
                        };
                    }
                });
                return updated;
            });
        }
        
        // Update stats
        if (data.stats) {
            setStats(data.stats);
        }
        
        // Process output lines through worker
        if (data.output_lines && data.output_lines.length > 0) {
            dataProcessor.current.processBatch(data.output_lines);
        }
    };
    
    const cleanup = () => {
        if (dataProcessor.current) {
            dataProcessor.current.destroy();
        }
        if (pollingManager.current) {
            pollingManager.current.stop();
        }
        if (stateManager.current) {
            stateManager.current.destroy();
        }
    };
    
    // Filter lines based on process selection, search and filter text
    const filteredLines = lines.filter(line => {
        // Apply process selection filter
        if (line.processName && processes[line.processName]) {
            const processInfo = processes[line.processName];
            const isSelected = processInfo?.selected !== false;
            if (!isSelected) {
                return false; // Hide lines from deselected processes
            }
        }
        
        // Apply text filter
        if (filterText && !line.cleanText.toLowerCase().includes(filterText.toLowerCase())) {
            return false;
        }
        
        // Apply search filter  
        if (searchTerm && !line.cleanText.toLowerCase().includes(searchTerm.toLowerCase())) {
            return false;
        }
        
        return true;
    });
    
    // Render function for Virtuoso
    const renderLogLine = useCallback((index) => {
        const line = filteredLines[index];
        if (!line) return React.createElement('div', null, 'Loading...');
        
        return React.createElement('div', {
            key: line.id,
            className: 'output-line',
            style: {
                contain: 'content', // Layer 4: CSS contain optimization
                padding: '1px 8px', // Reduced from 2px to 1px
                fontFamily: 'monospace',
                fontSize: '14px',
                lineHeight: '1.2', // Reduced line height
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word'
            },
            dangerouslySetInnerHTML: { __html: line.htmlContent }
        });
    }, [filteredLines, searchTerm]);
    
    // Process list component with selection and controls
    const ProcessList = () => {
        const processEntries = Object.entries(processes);
        
        if (processEntries.length === 0) {
            return React.createElement('div', { 
                style: { padding: '1rem', color: '#64748b', fontStyle: 'italic' }
            }, 'No processes detected yet...');
        }
        
        const handleProcessClick = (processName) => {
            console.log('Process clicked:', processName);
            console.log('Current processes:', processes);
            
            // Toggle process selection
            const processInfo = processes[processName];
            const isSelected = processInfo?.selected !== false;
            
            console.log('Current selection state:', isSelected, 'toggling to:', !isSelected);
            
            // Update local state optimistically
            setProcesses(prev => {
                const updated = {
                    ...prev,
                    [processName]: {
                        ...prev[processName],
                        selected: !isSelected
                    }
                };
                console.log('Updated processes:', updated);
                return updated;
            });
            
            // Send to server
            if (pollingManager.current) {
                console.log('Sending toggle to server');
                pollingManager.current.toggleProcessSelection(processName);
            } else {
                console.log('No polling manager available');
            }
        };
        
        const handleStartRestartProcess = async (processName, e) => {
            e.stopPropagation();
            try {
                if (pollingManager.current) {
                    // Always call restart - there's no separate start function
                    await pollingManager.current.restartProcess(processName);
                }
            } catch (error) {
                console.error('Error starting/restarting process:', error);
            }
        };
        
        const handleStopProcess = async (processName, e) => {
            e.stopPropagation();
            try {
                if (pollingManager.current) {
                    await pollingManager.current.stopProcess(processName);
                }
            } catch (error) {
                console.error('Error stopping process:', error);
            }
        };
        
        return React.createElement('div', null,
            processEntries.map(([processName, processInfo]) => {
                const status = processInfo?.status || processInfo;
                const isSelected = processInfo?.selected !== false;
                
                return React.createElement('div', {
                    key: processName,
                    className: `process-item ${isSelected ? 'selected' : ''}`,
                    onClick: () => handleProcessClick(processName),
                    style: { cursor: 'pointer' }
                }, [
                    // Process info section
                    React.createElement('div', {
                        key: 'info',
                        className: 'process-info'
                    }, [
                        React.createElement('span', { 
                            key: 'name',
                            className: 'process-name'
                        }, processName),
                        React.createElement('span', {
                            key: 'status',
                            className: `process-status ${status}`,
                            style: {
                                fontSize: '10px', // Half the size of process name
                                marginLeft: '8px'
                            }
                        }, status)
                    ]),
                    
                    // Process action buttons
                    React.createElement('div', {
                        key: 'actions',
                        className: 'process-actions'
                    }, [
                        // Show "Start" for stopped/dead processes, "Restart" for running
                        React.createElement('button', {
                            key: 'start-restart',
                            className: 'btn btn-success',
                            onClick: (e) => handleStartRestartProcess(processName, e),
                            title: status === 'running' ? 'Restart process' : 'Start process'
                        }, status === 'running' ? '↻' : '▶'),
                        React.createElement('button', {
                            key: 'stop',
                            className: 'btn btn-danger',
                            onClick: (e) => handleStopProcess(processName, e),
                            disabled: status === 'stopped' || status === 'dead',
                            title: 'Stop process'
                        }, '⏹')
                    ])
                ]);
            })
        );
    };
    
    const getStatusColor = (status) => {
        switch (status) {
            case 'running': return '#10b981';
            case 'stopped': return '#6b7280';
            case 'dead': return '#ef4444';
            case 'broken': return '#f59e0b';
            default: return '#8b5cf6';
        }
    };
    
    // Event handlers
    const handleSearchChange = (e) => {
        setSearchTerm(e.target.value);
    };
    
    const handleFilterChange = (e) => {
        setFilterText(e.target.value);
    };
    
    const handleSelectAll = async () => {
        console.log('Select All clicked');
        console.log('Current processes:', processes);
        
        // Update local state first
        setProcesses(prev => {
            const updated = {};
            Object.keys(prev).forEach(processName => {
                updated[processName] = {
                    ...prev[processName],
                    selected: true
                };
            });
            console.log('Select All - Updated processes:', updated);
            return updated;
        });
        
        // Send to server
        if (pollingManager.current) {
            try {
                await pollingManager.current.selectAllProcesses();
                console.log('Select All sent to server');
            } catch (error) {
                console.error('Error selecting all processes:', error);
            }
        } else {
            console.log('No polling manager for Select All');
        }
    };
    
    const handleDeselectAll = async () => {
        console.log('Deselect All clicked');
        console.log('Current processes:', processes);
        
        // Update local state first
        setProcesses(prev => {
            const updated = {};
            Object.keys(prev).forEach(processName => {
                updated[processName] = {
                    ...prev[processName],
                    selected: false
                };
            });
            console.log('Deselect All - Updated processes:', updated);
            return updated;
        });
        
        // Send to server
        if (pollingManager.current) {
            try {
                await pollingManager.current.deselectAllProcesses();
                console.log('Deselect All sent to server');
            } catch (error) {
                console.error('Error deselecting all processes:', error);
            }
        } else {
            console.log('No polling manager for Deselect All');
        }
    };
    
    const handleScrollToBottom = () => {
        console.log('Scroll to bottom clicked, current lines:', filteredLines.length);
        
        // Enable auto-scroll first
        setAutoScroll(true);
        
        if (virtuosoRef.current && filteredLines.length > 0) {
            // Force scroll to bottom using LAST index
            setTimeout(() => {
                console.log('Scrolling to bottom with LAST index');
                virtuosoRef.current.scrollToIndex({ 
                    index: 'LAST',
                    behavior: 'smooth'
                });
            }, 50);
        }
    };
    
    // Main render
    return React.createElement('div', { id: 'app' },
        // Header
        React.createElement('header', { className: 'header' },
            React.createElement('div', { className: 'header-content' },
                React.createElement('div', { className: 'logo' }, [
                    React.createElement('span', { key: 'icon', className: 'logo-icon' }, '⚡'),
                    React.createElement('h1', { key: 'title' }, version ? `Overmind GUI v${version}` : 'Overmind GUI'),
                    React.createElement('div', { key: 'indicator', className: 'polling-indicator' }, [
                        React.createElement('span', {
                            key: 'dot',
                            className: `polling-dot ${isConnected ? 'connected' : ''}`,
                            style: {
                                width: '8px',
                                height: '8px',
                                borderRadius: '50%',
                                backgroundColor: isConnected ? '#10b981' : '#6b7280',
                                marginRight: '8px'
                            }
                        }),
                        React.createElement('span', { key: 'text' }, 'Live')
                    ])
                ]),
                React.createElement('div', { className: 'status-bar' }, [
                    React.createElement('div', { key: 'lines', className: 'status-item' }, [
                        React.createElement('span', { key: 'label' }, 'Lines: '),
                        React.createElement('span', { key: 'value' }, lines.length)
                    ]),
                    React.createElement('div', { key: 'autoscroll', className: 'status-item' }, [
                        React.createElement('span', { key: 'label' }, 'Autoscroll: '),
                        React.createElement('span', { 
                            key: 'value', 
                            className: `status-value ${autoScroll ? 'autoscroll-on' : 'autoscroll-off'}` 
                        }, autoScroll ? 'ON' : 'OFF')
                    ])
                ])
            )
        ),
        
        // Main content
        React.createElement('div', { className: 'main-content' },
            // Sidebar
            React.createElement('aside', { className: 'sidebar' }, [
                // Controls
                React.createElement('div', { key: 'controls', className: 'sidebar-section compact' }, [
                    React.createElement('div', { key: 'header', className: 'section-header' },
                        React.createElement('h3', null, 'Controls')
                    ),
                    React.createElement('div', { key: 'content', className: 'section-content' }, [
                        // Filter input
                        React.createElement('input', {
                            key: 'filter',
                            type: 'text',
                            placeholder: 'Filter output...',
                            value: filterText,
                            onChange: handleFilterChange,
                            className: 'filter-input',
                            style: { marginBottom: '0.5rem' }
                        }),
                        // Search input
                        React.createElement('input', {
                            key: 'search',
                            type: 'text',
                            placeholder: 'Search output...',
                            value: searchTerm,
                            onChange: handleSearchChange,
                            className: 'filter-input'
                        })
                    ])
                ]),
                
                // Process list
                React.createElement('div', { key: 'processes', className: 'sidebar-section' }, [
                    React.createElement('div', { 
                        key: 'header', 
                        className: 'section-header',
                        style: { 
                            display: 'flex', 
                            justifyContent: 'space-between', 
                            alignItems: 'center' 
                        }
                    }, [
                        React.createElement('h3', { key: 'title' }, 'Processes'),
                        React.createElement('div', { 
                            key: 'actions', 
                            className: 'section-actions',
                            style: { display: 'flex', gap: '4px' }
                        }, [
                            React.createElement('button', {
                                key: 'select-all',
                                onClick: handleSelectAll,
                                className: 'btn btn-secondary',
                                style: {
                                    padding: '2px 8px',
                                    fontSize: '11px',
                                    minWidth: 'auto',
                                    height: 'auto'
                                },
                                title: 'Select All'
                            }, 'All'),
                            React.createElement('button', {
                                key: 'deselect-all', 
                                onClick: handleDeselectAll,
                                className: 'btn btn-secondary',
                                style: {
                                    padding: '2px 8px',
                                    fontSize: '11px',
                                    minWidth: 'auto',
                                    height: 'auto'
                                },
                                title: 'Deselect All'
                            }, 'None')
                        ])
                    ]),
                    React.createElement('div', { key: 'content', className: 'section-content' },
                        React.createElement(ProcessList)
                    )
                ])
            ]),
            
            // Output panel with React Virtuoso
            React.createElement('main', { className: 'output-panel' }, [
                // React Virtuoso container (no header bar)
                React.createElement('div', {
                    key: 'virtuoso-container',
                    className: 'output-container',
                    style: { flex: 1 },
                    onWheel: (e) => {
                        // Immediately disable auto-scroll on any wheel scroll up
                        if (e.deltaY < 0 && autoScroll) { // deltaY < 0 means scrolling up
                            console.log('Mouse wheel scroll up detected, current autoScroll:', autoScroll, 'setting to false');
                            setAutoScroll(false);
                        }
                    }
                },
                    React.createElement(Virtuoso, {
                        ref: virtuosoRef,
                        totalCount: filteredLines.length,
                        itemContent: renderLogLine,
                        style: { height: '100%' },
                        followOutput: autoScroll ? 'smooth' : false,
                        onAtBottomStateChange: (atBottom) => {
                            console.log('At bottom state changed:', atBottom, 'autoScroll:', autoScroll);
                            if (!atBottom && autoScroll) {
                                console.log('Disabling autoscroll due to scroll away from bottom');
                                setAutoScroll(false);
                            }
                        }
                    })
                )
            ])
        ),
        
        // Floating auto-scroll button (only when not auto-scrolling)
        !autoScroll ? React.createElement('button', {
            className: 'auto-scroll-btn',
            onClick: handleScrollToBottom,
            style: {
                position: 'fixed',
                bottom: '2rem',
                right: '2rem',
                padding: '0.5rem 1rem',
                backgroundColor: 'var(--primary-color)',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                zIndex: 1000,
                fontSize: '14px',
                fontWeight: '500',
                boxShadow: '0 4px 12px rgba(0, 0, 0, 0.3)',
                display: 'block'
            }
        }, '↓ New Output') : null
    );
}

// Initialize when DOM is ready
function initializeApp() {
    const root = createRoot(document.getElementById('app'));
    root.render(React.createElement(OvermindApp));
}

// Initialize
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
}

console.log('🚀 React Virtuoso Overmind GUI loaded');