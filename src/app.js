/**
 * High-Performance Overmind GUI with React Virtuoso
 * Implements proper 4-layer architecture with React components
 */

// ES Module imports using importmap
import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { createRoot } from 'react-dom/client';
import { Virtuoso } from 'react-virtuoso';
import { MAX_LINES_PER_PROCESS, MAX_DISPLAY_LINES } from './constants.js';

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
        
        const CHUNK_SIZE = 100; // Process in chunks of 100 lines max to prevent UI freezing
        
        if (lines.length <= CHUNK_SIZE) {
            // Small batch - process immediately
            this.processBatchChunk(lines);
        } else {
            // Large batch - break into chunks and process with delays
            console.log(`📦 Large batch detected (${lines.length} lines), processing in chunks of ${CHUNK_SIZE}`);
            
            for (let i = 0; i < lines.length; i += CHUNK_SIZE) {
                const chunk = lines.slice(i, i + CHUNK_SIZE);
                const delay = Math.floor(i / CHUNK_SIZE) * 10; // 10ms delay between chunks
                
                setTimeout(() => {
                    this.processBatchChunk(chunk);
                }, delay);
            }
        }
    }
    
    processBatchChunk(lines) {
        if (!this.workerReady) return;
        
        // Convert API format to worker format
        const workerLines = lines.map(line => ({
            html: line.html,
            id: line.id,
            process: line.process
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
    // State - using single list with process counting for optimal performance
    const [allLines, setAllLines] = useState([]); // Single chronological array
    const [processLineCounts, setProcessLineCounts] = useState({}); // { processName: count }
    const [processes, setProcesses] = useState({});
    const [stats, setStats] = useState({});
    const [isConnected, setIsConnected] = useState(false);
    const [autoScroll, setAutoScroll] = useState(true);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterText, setFilterText] = useState('');
    const [debouncedFilterText, setDebouncedFilterText] = useState('');
    const [version, setVersion] = useState('');
    
    // Search-specific state
    const [searchResults, setSearchResults] = useState([]);
    const [currentSearchIndex, setCurrentSearchIndex] = useState(-1);
    const [isSearchActive, setIsSearchActive] = useState(false);
    
    const [isShuttingDown, setIsShuttingDown] = useState(false);
    const [isRestarting, setIsRestarting] = useState(false);
    const [failureDeclarations, setFailureDeclarations] = useState({}); // {processName: [strings]}

    // Refs
    const virtuosoRef = useRef(null);
    const dataProcessor = useRef(null);
    const pollingManager = useRef(null);
    const stateManager = useRef(null);
    const autoScrollRef = useRef(autoScroll);
    const searchTimeoutRef = useRef(null);
    const searchStateRef = useRef({ searchTerm: '', isSearchActive: false });
    const isManualScrolling = useRef(false);
    const userInteractingWithScrollbar = useRef(false);
    const clearMarkers = useRef({}); // Track {processName: lastMessageIdWhenCleared}
    
    // Initialize everything and global event listeners
    useEffect(() => {
        initializeApp();
        fetchVersion();
        
        // Global mouse event listeners to handle scrollbar interactions outside container
        const handleGlobalMouseUp = () => {
            if (userInteractingWithScrollbar.current) {
                console.log('Global mouseup - user released scrollbar outside container');
                userInteractingWithScrollbar.current = false;
                setTimeout(() => { 
                    if (!userInteractingWithScrollbar.current) {
                        isManualScrolling.current = false; 
                    }
                }, 300);
            }
        };
        
        document.addEventListener('mouseup', handleGlobalMouseUp);
        
        return () => {
            document.removeEventListener('mouseup', handleGlobalMouseUp);
            cleanup();
        };
    }, []);
    
    // Debug autoScroll changes and keep ref in sync
    useEffect(() => {
        console.log('AutoScroll state changed to:', autoScroll);
        autoScrollRef.current = autoScroll;
    }, [autoScroll]);
    
    // Keep search state ref in sync
    useEffect(() => {
        searchStateRef.current = { searchTerm, isSearchActive };
    }, [searchTerm, isSearchActive]);
    
    // Debounce filter text to prevent expensive re-filtering on every keystroke
    useEffect(() => {
        const timer = setTimeout(() => {
            console.log(`🔧 Filter debounce executing: "${filterText}"`);
            setDebouncedFilterText(filterText);
        }, 300); // 300ms debounce

        return () => {
            console.log(`🔧 Filter debounce cleared for: "${filterText}"`);
            clearTimeout(timer);
        };
    }, [filterText]);
    
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

    const loadFailureDeclarations = async (processName) => {
        try {
            const response = await fetch(`/api/failure-declarations/${processName}`);
            const data = await response.json();
            if (data.declarations) {
                setFailureDeclarations(prev => ({
                    ...prev,
                    [processName]: data.declarations
                }));
            }
        } catch (error) {
            console.error(`Error loading failure declarations for ${processName}:`, error);
        }
    };

    const addFailureDeclaration = async (processName, failureString) => {
        try {
            const response = await fetch(`/api/failure-declarations/${processName}/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ failure_string: failureString })
            });
            const data = await response.json();
            if (data.success && data.declarations) {
                setFailureDeclarations(prev => ({
                    ...prev,
                    [processName]: data.declarations
                }));
                return true;
            }
            return false;
        } catch (error) {
            console.error(`Error adding failure declaration for ${processName}:`, error);
            return false;
        }
    };

    const removeFailureDeclaration = async (processName, failureString) => {
        try {
            const response = await fetch(`/api/failure-declarations/${processName}/remove`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ failure_string: failureString })
            });
            const data = await response.json();
            if (data.success && data.declarations) {
                setFailureDeclarations(prev => ({
                    ...prev,
                    [processName]: data.declarations
                }));
                return true;
            }
            return false;
        } catch (error) {
            console.error(`Error removing failure declaration for ${processName}:`, error);
            return false;
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

    const loadProcessesFromDaemon = async () => {
        try {
            console.log('🔍 Attempting to load processes from daemon...');
            const response = await fetch('/api/processes');
            const data = await response.json();

            if (data.processes && Object.keys(data.processes).length > 0) {
                console.log(`✅ Loaded ${Object.keys(data.processes).length} processes from daemon:`, Object.keys(data.processes));

                // Add system process (fake process for system messages)
                const processesWithSystem = {
                    system: {
                        name: 'system',
                        status: null, // No status for system
                        selected: true // Default to selected
                    },
                    ...data.processes
                };

                setProcesses(processesWithSystem);

                // Load failure declarations for all processes
                Object.keys(data.processes).forEach(processName => {
                    loadFailureDeclarations(processName);
                });

                return true; // Success
            } else {
                console.log('⚠️ No processes returned from daemon yet');
                return false; // No processes yet
            }
        } catch (error) {
            console.log('❌ Error loading processes from daemon:', error.message);
            return false; // Error
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

            // Start daemon process loading with retry logic (since daemon connects later)
            const startDaemonProcessRetry = async () => {
                let attempts = 0;
                const maxAttempts = 20; // Try for 20 attempts (10 seconds)
                const retryInterval = 500; // 500ms between attempts

                const retry = async () => {
                    attempts++;
                    console.log(`🔄 Daemon process loading attempt ${attempts}/${maxAttempts}`);

                    const success = await loadProcessesFromDaemon();
                    if (success) {
                        console.log('✅ Successfully loaded processes from daemon!');
                        return;
                    }

                    if (attempts < maxAttempts) {
                        console.log(`⏳ Retrying in ${retryInterval}ms...`);
                        setTimeout(retry, retryInterval);
                    } else {
                        console.log('❌ Max attempts reached. Daemon may not be ready or no processes available.');
                    }
                };

                setTimeout(retry, 1000); // Start after 1 second to let daemon initialize
            };

            startDaemonProcessRetry();
            
            // Set up throttled batch processing to prevent UI freezing with large updates
            const batchedUpdates = React.useRef([]);
            const updateTimer = React.useRef(null);

            const flushBatchedUpdates = () => {
                if (batchedUpdates.current.length === 0) return;

                const linesToProcess = batchedUpdates.current;
                batchedUpdates.current = [];
                
                console.log(`🔄 Flushing ${linesToProcess.length} batched lines to UI`);
                
                setAllLines(prevAllLines => {
                    // Simply append new lines (they arrive in chronological order)
                    let newAllLines = [...prevAllLines, ...linesToProcess];
                    
                    // Update process line counts
                    const newCounts = {};
                    linesToProcess.forEach(line => {
                        const processName = line.processName || 'unknown';
                        newCounts[processName] = (newCounts[processName] || 0) + 1;
                    });
                    
                    // Check if any process exceeds limits and perform cleanup
                    setProcessLineCounts(prevCounts => {
                        const updatedCounts = { ...prevCounts };
                        const processesToCleanup = [];
                        
                        Object.entries(newCounts).forEach(([processName, additionalCount]) => {
                            const newTotal = (updatedCounts[processName] || 0) + additionalCount;
                            updatedCounts[processName] = newTotal;
                            
                            // If process exceeds limit, mark for cleanup (now 10k per process)
                            if (newTotal > MAX_LINES_PER_PROCESS) {
                                const excessLines = newTotal - MAX_LINES_PER_PROCESS;
                                processesToCleanup.push({ processName, excessLines });
                            }
                        });
                        
                        // Perform cleanup if needed (expensive but infrequent)
                        if (processesToCleanup.length > 0) {
                            console.log(`Cleaning up excess lines for ${processesToCleanup.length} processes`);
                            
                            processesToCleanup.forEach(({ processName, excessLines }) => {
                                // Find and remove the oldest lines for this process
                                const indicesToRemove = [];
                                let removedCount = 0;
                                
                                for (let i = 0; i < newAllLines.length && removedCount < excessLines; i++) {
                                    if (newAllLines[i].processName === processName) {
                                        indicesToRemove.push(i);
                                        removedCount++;
                                    }
                                }
                                
                                // Remove lines in reverse order to maintain indices
                                for (let i = indicesToRemove.length - 1; i >= 0; i--) {
                                    newAllLines.splice(indicesToRemove[i], 1);
                                }
                                
                                // Update count
                                updatedCounts[processName] -= removedCount;
                                console.log(`Process ${processName}: removed ${removedCount} oldest lines`);
                            });
                        }
                        
                        return updatedCounts;
                    });
                    
                    return newAllLines;
                });
            };
            
            // Set up data processor callback - using batched updates for performance
            dataProcessor.current.onBatchProcessed = (processedLines) => {
                // Filter out lines that were cleared (before the clear marker for their process)
                const filteredLines = processedLines.filter(line => {
                    const processName = line.processName;
                    const clearMarker = clearMarkers.current[processName];

                    // If there's a clear marker for this process, only include lines after it
                    if (clearMarker !== undefined && line.id <= clearMarker) {
                        console.log(`Filtering out line ${line.id} for ${processName} (clear marker: ${clearMarker})`);
                        return false;
                    }
                    return true;
                });

                // Add filtered lines to batch
                if (filteredLines.length > 0) {
                    batchedUpdates.current.push(...filteredLines);
                }

                // Clear existing timer and set new one
                if (updateTimer.current) {
                    clearTimeout(updateTimer.current);
                }

                // Flush updates after 50ms of no new data, or immediately if batch gets large
                const BATCH_SIZE_LIMIT = 200;
                const BATCH_DELAY = 50;

                if (batchedUpdates.current.length >= BATCH_SIZE_LIMIT) {
                    // Large batch - flush immediately
                    console.log(`⚡ Large batch (${batchedUpdates.current.length} lines), flushing immediately`);
                    flushBatchedUpdates();
                } else {
                    // Small batch - wait for more or timeout
                    updateTimer.current = setTimeout(flushBatchedUpdates, BATCH_DELAY);
                }
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
    
    // Stable reference for filteredLines when autoscroll is OFF
    const stableFilteredLines = useRef([]);
    const lastProcessSelection = useRef('');
    
    // Build filtered lines from single list - much faster than per-process approach
    const filteredLines = useMemo(() => {
        // Step 1: Filter by selected processes and text filter (single pass)
        // Pre-compute filter values for performance
        const filterLower = debouncedFilterText ? debouncedFilterText.toLowerCase() : null;
        
        const selectedLines = allLines.filter(line => {
            const processName = line.processName || 'unknown';
            const processInfo = processes[processName];
            const isSelected = processInfo?.selected !== false;
            
            // Check process selection first (faster check)
            if (!isSelected) return false;
            
            // Check text filter (using pre-computed lowercase filter)
            if (filterLower && !line.htmlContent.toLowerCase().includes(filterLower)) {
                return false;
            }
            
            return true;
        });
        
        // Step 2: Take the last MAX_DISPLAY_LINES (most recent) - no sorting needed!
        const newResult = selectedLines.length > MAX_DISPLAY_LINES ? 
            selectedLines.slice(-MAX_DISPLAY_LINES) : 
            selectedLines;
        
        // Track process selection changes
        const currentProcessSelection = Object.entries(processes)
            .filter(([_, processInfo]) => processInfo?.selected !== false)
            .map(([name, _]) => name)
            .sort()
            .join(',');
        
        // CRITICAL: When autoscroll is OFF, only update if process selection changed
        if (!autoScroll) {
            if (stableFilteredLines.current.length > 0 && lastProcessSelection.current === currentProcessSelection) {
                console.log(`Autoscroll OFF: keeping frozen display (${stableFilteredLines.current.length} lines)`);
                return stableFilteredLines.current;
            }
            console.log(`Autoscroll OFF but process selection changed - updating display`);
        }
        
        // Update display and references
        stableFilteredLines.current = newResult;
        lastProcessSelection.current = currentProcessSelection;
        console.log(`Display updated: ${newResult.length} lines from ${allLines.length} total lines`);
        return newResult;
    }, [allLines, processes, debouncedFilterText, autoScroll]);
    
    
    // Highlight search term in HTML content
    const highlightSearchTerm = useCallback((htmlContent, term) => {
        if (!term) return htmlContent;
        
        // Create a case-insensitive regex for the search term
        const regex = new RegExp(`(${term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return htmlContent.replace(regex, '<mark style="background-color: yellow; color: black;">$1</mark>');
    }, []);
    
    // Search functionality - separate from filtering
    const performSearch = useCallback((term, preserveIndex = false) => {
        console.log(`🔍 performSearch called: term="${term}", preserveIndex=${preserveIndex}`);

        if (!term) {
            console.log('🔍 Clearing search results');
            setSearchResults([]);
            setCurrentSearchIndex(-1);
            setIsSearchActive(false);
            setAutoScroll(true); // Re-enable autoscroll when search is cleared
            return;
        }

        // Use the already computed filteredLines instead of recomputing
        // This avoids duplicate filtering work and ensures consistency
        const searchLower = term.toLowerCase();
        const results = [];

        filteredLines.forEach((line, index) => {
            if (line.htmlContent.toLowerCase().includes(searchLower)) {
                results.push({
                    lineIndex: index,
                    line: line,
                    highlightedHtml: highlightSearchTerm(line.htmlContent, term)
                });
            }
        });

        console.log(`🔍 Found ${results.length} search results in ${filteredLines.length} filtered lines`);
        setSearchResults(results);

        // Only reset index if not preserving or if there are no results
        if (!preserveIndex || results.length === 0) {
            console.log(`🔍 Resetting search index to 0 (preserveIndex=${preserveIndex})`);
            setCurrentSearchIndex(results.length > 0 ? 0 : -1);
            setIsSearchActive(results.length > 0);

            // Only disable autoscroll and jump to first result on new searches
            if (results.length > 0) {
                setAutoScroll(false);
                setTimeout(() => {
                    if (virtuosoRef.current) {
                        virtuosoRef.current.scrollToIndex({
                            index: results[0].lineIndex,
                            behavior: 'auto',
                            align: 'center'
                        });
                    }
                }, 50);
            }
        } else {
            // Preserve current index, but ensure it's within bounds
            console.log(`🔍 Preserving search index`);
            setCurrentSearchIndex(prevIndex => {
                const newIndex = Math.min(prevIndex, results.length - 1);
                const finalIndex = Math.max(0, newIndex);
                console.log(`🔍 Index preserved: ${prevIndex} → ${finalIndex}`);
                setIsSearchActive(results.length > 0);
                return finalIndex;
            });
        }
    }, [filteredLines, highlightSearchTerm]); // Simplified and more stable dependencies
    
    // Debounced search effect - ONLY depends on searchTerm
    useEffect(() => {
        console.log(`🔍 Search term changed to: "${searchTerm}"`);

        if (searchTimeoutRef.current) {
            clearTimeout(searchTimeoutRef.current);
        }

        searchTimeoutRef.current = setTimeout(() => {
            console.log(`🔍 Debounced search executing for: "${searchTerm}"`);
            performSearch(searchTerm, false); // Don't preserve index for new searches
        }, 300); // 300ms debounce

        return () => {
            if (searchTimeoutRef.current) {
                clearTimeout(searchTimeoutRef.current);
            }
        };
    }, [searchTerm]); // ONLY depend on searchTerm to prevent excessive re-runs

    // Update search results when filteredLines change (but only if search is active)
    useEffect(() => {
        if (isSearchActive && searchTerm) {
            console.log(`🔍 Filtered lines changed, updating search results for active search: "${searchTerm}"`);
            performSearch(searchTerm, true); // Preserve current index when updating
        }
    }, [filteredLines, isSearchActive, searchTerm, performSearch]); // This will update search when filter/process selection changes
    
    // Render function for Virtuoso
    const renderLogLine = useCallback((index) => {
        const line = filteredLines[index];
        if (!line) return React.createElement('div', null, 'Loading...');
        
        // Check if this line has highlighted search results
        let htmlContent = line.htmlContent;
        let isCurrentSearchResult = false;
        
        if (isSearchActive && searchResults.length > 0) {
            const searchResult = searchResults.find(result => result.lineIndex === index);
            if (searchResult) {
                htmlContent = searchResult.highlightedHtml;
                // Check if this is the current search result
                isCurrentSearchResult = searchResults[currentSearchIndex] && 
                                       searchResults[currentSearchIndex].lineIndex === index;
            }
        }
        
        return React.createElement('div', {
            key: line.id,
            className: `output-line ${isCurrentSearchResult ? 'current-search-result' : ''}`,
            style: {
                contain: 'content', // Layer 4: CSS contain optimization
                padding: '1px 8px', // Reduced from 2px to 1px
                fontFamily: 'monospace',
                fontSize: '14px',
                lineHeight: '1.2', // Reduced line height
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-word',
                backgroundColor: isCurrentSearchResult ? 'rgba(59, 130, 246, 0.1)' : 'transparent',
                border: isCurrentSearchResult ? '1px solid #3b82f6' : 'none'
            },
            dangerouslySetInnerHTML: { __html: htmlContent }
        });
    }, [filteredLines, isSearchActive, searchResults, currentSearchIndex]);
    
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

            // Send to server (but not for system process)
            if (processName !== 'system' && pollingManager.current) {
                console.log('Sending toggle to server');
                pollingManager.current.toggleProcessSelection(processName);
            } else if (processName === 'system') {
                console.log('System process - no server update needed');
            } else {
                console.log('No polling manager available');
            }
        };

        const handleProcessDoubleClick = (processName) => {
            console.log('Process double-clicked - focusing on:', processName);

            // Turn off all processes first, then turn on the target process
            setProcesses(prev => {
                const updated = {};
                Object.keys(prev).forEach(name => {
                    updated[name] = {
                        ...prev[name],
                        selected: name === processName // Only select the double-clicked process
                    };
                });
                console.log('Focus mode - Updated processes:', updated);
                return updated;
            });

            // Send focus command to server - deselect all then select target
            if (pollingManager.current) {
                console.log('Sending focus command to server');
                // First deselect all
                pollingManager.current.deselectAllProcesses().then(() => {
                    // Then select the target process
                    return pollingManager.current.toggleProcessSelection(processName);
                }).catch(error => {
                    console.error('Error during focus operation:', error);
                });
            }
        };
        
        const handleProcessContextMenu = (e, processName) => {
            e.preventDefault(); // Prevent default browser context menu

            const isSelected = processes[processName]?.selected !== false;

            // Create context menu
            const existingMenu = document.querySelector('.context-menu');
            if (existingMenu) {
                existingMenu.remove();
            }

            const menu = document.createElement('div');
            menu.className = 'context-menu';
            menu.style.cssText = `
                position: fixed;
                left: ${e.clientX}px;
                top: ${e.clientY}px;
                z-index: 10000;
                background: #1a1a1a;
                border: 1px solid #333;
                border-radius: 4px;
                padding: 4px 0;
                min-width: 120px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
            `;

            const menuItems = [
                { label: 'Focus', action: () => handleProcessDoubleClick(processName) },
                { separator: true },
                { label: isSelected ? 'Hide' : 'Show', action: () => handleProcessClick(processName) },
                { separator: true },
                { label: 'Clear Output', action: () => clearProcessOutput(processName) }
            ];

            // Add failure declarations removal options if any exist
            const declarations = failureDeclarations[processName] || [];
            if (declarations.length > 0) {
                menuItems.push({ separator: true });
                declarations.forEach(declaration => {
                    menuItems.push({
                        label: `Remove: "${declaration.length > 30 ? declaration.substring(0, 30) + '...' : declaration}"`,
                        action: async () => {
                            console.log(`Removing failure declaration: "${declaration}" from ${processName}`);
                            const success = await removeFailureDeclaration(processName, declaration);
                            if (success) {
                                console.log('✅ Failure declaration removed successfully');
                            } else {
                                console.error('❌ Failed to remove failure declaration');
                            }
                        }
                    });
                });
            }

            menuItems.forEach(item => {
                if (item.separator) {
                    const separator = document.createElement('div');
                    separator.style.cssText = 'border-top: 1px solid #333; margin: 4px 0;';
                    menu.appendChild(separator);
                } else {
                    const menuItem = document.createElement('div');
                    menuItem.textContent = item.label;
                    menuItem.style.cssText = `
                        padding: 8px 16px;
                        cursor: pointer;
                        color: #ccc;
                        font-size: 14px;
                        white-space: nowrap;
                    `;

                    menuItem.addEventListener('mouseenter', () => {
                        menuItem.style.backgroundColor = '#2a2a2a';
                    });

                    menuItem.addEventListener('mouseleave', () => {
                        menuItem.style.backgroundColor = 'transparent';
                    });

                    menuItem.addEventListener('click', () => {
                        item.action();
                        menu.remove();
                    });

                    menu.appendChild(menuItem);
                }
            });

            document.body.appendChild(menu);

            // Adjust position if menu goes off-screen
            const rect = menu.getBoundingClientRect();
            if (rect.right > window.innerWidth) {
                menu.style.left = `${e.clientX - rect.width}px`;
            }
            if (rect.bottom > window.innerHeight) {
                menu.style.top = `${e.clientY - rect.height}px`;
            }

            // Click away to close
            const closeMenu = (event) => {
                if (!menu.contains(event.target)) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                    document.removeEventListener('contextmenu', closeMenu);
                }
            };

            setTimeout(() => {
                document.addEventListener('click', closeMenu);
                document.addEventListener('contextmenu', closeMenu);
            }, 0);
        };

        const clearProcessOutput = (processName) => {
            // CRITICAL: Clear any pending batched updates for this process FIRST
            // to prevent them from being added back after we clear
            if (updateTimer.current) {
                clearTimeout(updateTimer.current);
                updateTimer.current = null;
            }

            // Filter out any batched lines for this process that haven't been flushed yet
            batchedUpdates.current = batchedUpdates.current.filter(
                line => line.processName !== processName
            );

            // Track the current polling position as the "clear marker" for this process
            // Any lines with ID <= this marker should be filtered out in future renders
            if (pollingManager.current) {
                clearMarkers.current[processName] = pollingManager.current.lastMessageId;
                console.log(`Clear marker set for ${processName} at message ID ${pollingManager.current.lastMessageId}`);
            }

            // Clear output lines for this process in the frontend
            setAllLines(prev => prev.filter(line => line.processName !== processName));

            // Update process line counts
            setProcessLineCounts(prev => ({
                ...prev,
                [processName]: 0
            }));

            // Add a cleared marker to the display
            const clearedLine = {
                id: Date.now(), // Use timestamp as fake ID for display only
                processName: processName,
                htmlContent: `<span style="color: #666; font-style: italic;">[Output cleared at ${new Date().toLocaleTimeString()}]</span>`,
                timestamp: Date.now()
            };

            setAllLines(prev => [...prev, clearedLine]);
            setProcessLineCounts(prev => ({
                ...prev,
                [processName]: 1
            }));
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
                // Handle both object format {name, status, selected} and simple string format
                const status = typeof processInfo === 'object' ? processInfo.status : processInfo;
                const isSelected = processInfo?.selected !== false;
                
                return React.createElement('div', {
                    key: processName,
                    className: `process-item ${isSelected ? 'selected' : ''}`,
                    onClick: () => handleProcessClick(processName),
                    onDoubleClick: () => handleProcessDoubleClick(processName),
                    onContextMenu: (e) => handleProcessContextMenu(e, processName),
                    style: { cursor: 'pointer' },
                    title: `Click to toggle, Double-click to focus, Right-click for menu`
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
                        status && React.createElement('span', {
                            key: 'status',
                            className: `process-status ${status}`,
                            style: {
                                fontSize: '10px', // Half the size of process name
                                marginLeft: '8px'
                            }
                        }, status)
                    ]),
                    
                    // Process action buttons (not for system process)
                    processName !== 'system' && React.createElement('div', {
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
    
    // Search navigation functions
    const goToNextSearchResult = useCallback(() => {
        if (searchResults.length === 0) return;
        
        const nextIndex = (currentSearchIndex + 1) % searchResults.length;
        console.log(`🔍 Next: ${currentSearchIndex} → ${nextIndex} of ${searchResults.length}`);
        setCurrentSearchIndex(nextIndex);
        
        // Scroll to the next result
        if (virtuosoRef.current && searchResults[nextIndex]) {
            virtuosoRef.current.scrollToIndex({
                index: searchResults[nextIndex].lineIndex,
                behavior: 'auto',
                align: 'center'
            });
        }
    }, [searchResults, currentSearchIndex]);
    
    const goToPrevSearchResult = useCallback(() => {
        if (searchResults.length === 0) return;
        
        const prevIndex = currentSearchIndex <= 0 ? searchResults.length - 1 : currentSearchIndex - 1;
        console.log(`🔍 Prev: ${currentSearchIndex} → ${prevIndex} of ${searchResults.length}`);
        setCurrentSearchIndex(prevIndex);
        
        // Scroll to the previous result
        if (virtuosoRef.current && searchResults[prevIndex]) {
            virtuosoRef.current.scrollToIndex({
                index: searchResults[prevIndex].lineIndex,
                behavior: 'auto',
                align: 'center'
            });
        }
    }, [searchResults, currentSearchIndex]);
    
    // Keyboard navigation for search results (must be after function definitions)
    useEffect(() => {
        const handleKeyDown = (e) => {
            // Only handle Tab navigation when search is active
            if (!isSearchActive || searchResults.length === 0) return;
            
            if (e.key === 'Tab') {
                e.preventDefault(); // Prevent default tab behavior
                
                if (e.shiftKey) {
                    // Shift+Tab = previous result
                    goToPrevSearchResult();
                } else {
                    // Tab = next result
                    goToNextSearchResult();
                }
            }
        };
        
        // Add event listener to document
        document.addEventListener('keydown', handleKeyDown);
        
        // Cleanup
        return () => {
            document.removeEventListener('keydown', handleKeyDown);
        };
    }, [isSearchActive, searchResults.length, goToNextSearchResult, goToPrevSearchResult]);
    
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
    

    const handleShutdown = async () => {
        try {
            setIsShuttingDown(true);
            console.log('Initiating shutdown...');

            const response = await fetch('/api/shutdown', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (response.ok && result.success) {
                console.log('Shutdown successful:', result.message);
                // The server will close the connection
            } else {
                throw new Error(result.error || `Server returned ${response.status}`);
            }

        } catch (error) {
            console.error('Shutdown failed:', error);
            setIsShuttingDown(false);
            // Could show error modal here
        }
    };

    const handleRestart = async () => {
        try {
            setIsRestarting(true);
            console.log('Restarting server process...');

            const response = await fetch('/api/restart', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            const result = await response.json();

            if (response.ok && result.success) {
                console.log('Restart successful:', result.message);
                // The server will restart and the page will lose connection
                // Show a message to the user
                alert('Server restarting... Please refresh the page in a few seconds.');
            } else {
                throw new Error(result.error || `Server returned ${response.status}`);
            }

        } catch (error) {
            console.error('Restart failed:', error);
            setIsRestarting(false);
            alert('Restart failed: ' + error.message);
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
                    behavior: 'auto'
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
                        React.createElement('span', { 
                        key: 'value', 
                        title: `Filtered: ${filteredLines.length} | Processing: ${pollingManager.current?.lastProcessingTime || 0}ms` 
                    }, allLines.length)
                    ]),
                    React.createElement('div', { key: 'autoscroll', className: 'status-item' }, [
                        React.createElement('span', { key: 'label' }, 'Autoscroll: '),
                        React.createElement('span', { 
                            key: 'value', 
                            className: `status-value ${autoScroll ? 'autoscroll-on' : 'autoscroll-off'}` 
                        }, autoScroll ? 'ON' : 'OFF')
                    ])
,
                    React.createElement('div', { key: 'restart', className: 'status-item' }, [
                        React.createElement('button', {
                            key: 'restart-btn',
                            id: 'restart-btn',
                            className: 'btn btn-warning',
                            onClick: handleRestart,
                            disabled: isRestarting,
                            title: 'Restart UI only (keeps overmind running)'
                        }, isRestarting ? 'Restarting...' : '🔄 Restart')
                    ]),
                    React.createElement('div', { key: 'shutdown', className: 'status-item' }, [
                        React.createElement('button', {
                            key: 'shutdown-btn',
                            id: 'shutdown-btn',
                            className: 'btn btn-danger',
                            onClick: handleShutdown,
                            disabled: isShuttingDown,
                            title: 'Shutdown Overmind and close server'
                        }, isShuttingDown ? 'Shutting down...' : '🔴 Shutdown')
                    ])                ])
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
                            style: { 
                                marginBottom: '0.5rem'
                            }
                        }),
                        // Search input container
                        React.createElement('div', {
                            key: 'search-container',
                            style: { position: 'relative', marginBottom: '0.25rem' }
                        }, [
                            // Search input
                            React.createElement('input', {
                                key: 'search',
                                type: 'text',
                                placeholder: 'Search output...',
                                value: searchTerm,
                                onChange: handleSearchChange,
                                className: 'filter-input',
                                style: { paddingRight: '60px' } // Make room for buttons
                            }),
                            // Search navigation buttons
                            isSearchActive ? React.createElement('div', {
                                key: 'search-nav',
                                style: {
                                    position: 'absolute',
                                    right: '4px',
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    display: 'flex',
                                    gap: '2px'
                                }
                            }, [
                                React.createElement('button', {
                                    key: 'prev',
                                    onClick: goToPrevSearchResult,
                                    disabled: searchResults.length === 0,
                                    style: {
                                        width: '24px',
                                        height: '24px',
                                        fontSize: '12px',
                                        border: '1px solid #ccc',
                                        backgroundColor: '#f8f9fa',
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center'
                                    },
                                    title: 'Previous result'
                                }, '↑'),
                                React.createElement('button', {
                                    key: 'next',
                                    onClick: goToNextSearchResult,
                                    disabled: searchResults.length === 0,
                                    style: {
                                        width: '24px',
                                        height: '24px',
                                        fontSize: '12px',
                                        border: '1px solid #ccc',
                                        backgroundColor: '#f8f9fa',
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center'
                                    },
                                    title: 'Next result'
                                }, '↓')
                            ]) : null
                        ]),
                        // Search result counter
                        isSearchActive ? React.createElement('div', {
                            key: 'search-info',
                            style: {
                                fontSize: '11px',
                                color: '#6b7280',
                                marginBottom: '0.5rem'
                            }
                        }, searchResults.length === 0 ? 'No results' : 
                           `${currentSearchIndex + 1} of ${searchResults.length} (Tab/Shift+Tab)`) : null
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
                    onContextMenu: (e) => {
                        // Handle right-click on output lines
                        const selection = window.getSelection();
                        const selectedText = selection.toString().trim();

                        // Only show menu if text is selected and it's from a single line
                        if (selectedText && selectedText.split('\n').length === 1) {
                            e.preventDefault();

                            // Find which process this line belongs to by looking at the selected element
                            let processName = null;
                            const range = selection.getRangeAt(0);
                            let container = range.commonAncestorContainer;

                            // Walk up the DOM to find the output-line div
                            while (container && container.nodeType !== 1) {
                                container = container.parentNode;
                            }

                            // Look for data-process attribute or extract from the line content
                            if (container) {
                                // Find the line in filteredLines by searching for matching content
                                const lineElement = container.closest('.output-line');
                                if (lineElement) {
                                    const lineHTML = lineElement.innerHTML;
                                    // Find the line in filteredLines
                                    const matchedLine = filteredLines.find(line => lineHTML.includes(line.htmlContent) || line.htmlContent.includes(selectedText));
                                    if (matchedLine) {
                                        processName = matchedLine.processName;
                                    }
                                }
                            }

                            if (!processName) {
                                console.log('Could not determine process name for selected text');
                                return;
                            }

                            console.log(`Selected text from process ${processName}: "${selectedText}"`);

                            // Create context menu
                            const existingMenu = document.querySelector('.text-selection-context-menu');
                            if (existingMenu) {
                                existingMenu.remove();
                            }

                            const menu = document.createElement('div');
                            menu.className = 'text-selection-context-menu';
                            menu.style.cssText = `
                                position: fixed;
                                left: ${e.clientX}px;
                                top: ${e.clientY}px;
                                z-index: 10001;
                                background: #1a1a1a;
                                border: 1px solid #333;
                                border-radius: 4px;
                                padding: 4px 0;
                                min-width: 150px;
                                box-shadow: 0 2px 8px rgba(0,0,0,0.3);
                            `;

                            const menuItem = document.createElement('div');
                            menuItem.textContent = 'Declare Failed';
                            menuItem.style.cssText = `
                                padding: 8px 16px;
                                cursor: pointer;
                                color: #ff6b6b;
                                font-size: 14px;
                                white-space: nowrap;
                            `;

                            menuItem.addEventListener('mouseenter', () => {
                                menuItem.style.backgroundColor = '#2a2a2a';
                            });

                            menuItem.addEventListener('mouseleave', () => {
                                menuItem.style.backgroundColor = 'transparent';
                            });

                            menuItem.addEventListener('click', async () => {
                                console.log(`Adding failure declaration: "${selectedText}" for process ${processName}`);
                                const success = await addFailureDeclaration(processName, selectedText);
                                if (success) {
                                    console.log('✅ Failure declaration added successfully');
                                } else {
                                    console.error('❌ Failed to add failure declaration');
                                }
                                menu.remove();
                                selection.removeAllRanges();
                            });

                            menu.appendChild(menuItem);
                            document.body.appendChild(menu);

                            // Adjust position if menu goes off-screen
                            const rect = menu.getBoundingClientRect();
                            if (rect.right > window.innerWidth) {
                                menu.style.left = `${e.clientX - rect.width}px`;
                            }
                            if (rect.bottom > window.innerHeight) {
                                menu.style.top = `${e.clientY - rect.height}px`;
                            }

                            // Click away to close
                            const closeMenu = (event) => {
                                if (!menu.contains(event.target)) {
                                    menu.remove();
                                    document.removeEventListener('click', closeMenu);
                                    document.removeEventListener('contextmenu', closeMenu);
                                }
                            };

                            setTimeout(() => {
                                document.addEventListener('click', closeMenu);
                                document.addEventListener('contextmenu', closeMenu);
                            }, 0);
                        }
                    },
                    onWheel: (e) => {
                        isManualScrolling.current = true;
                        // Immediately disable auto-scroll on any wheel scroll up
                        if (e.deltaY < 0 && autoScroll) { // deltaY < 0 means scrolling up
                            console.log('Manual mouse wheel scroll up detected, disabling autoScroll');
                            setAutoScroll(false);
                        }
                        // Reset the manual scrolling flag after a short delay
                        setTimeout(() => { isManualScrolling.current = false; }, 150);
                    },
                    onMouseDown: (e) => {
                        // Detect if user is clicking on scrollbar area (right edge of container)
                        const rect = e.currentTarget.getBoundingClientRect();
                        const scrollbarWidth = 20; // Standard scrollbar width + buffer
                        const isOnScrollbar = e.clientX >= rect.right - scrollbarWidth;
                        
                        if (isOnScrollbar) {
                            console.log('User clicked on scrollbar - enabling manual scroll detection');
                            userInteractingWithScrollbar.current = true;
                            isManualScrolling.current = true;
                        }
                    },
                    onMouseUp: () => {
                        if (userInteractingWithScrollbar.current) {
                            console.log('User released scrollbar');
                            userInteractingWithScrollbar.current = false;
                            // Keep isManualScrolling true for a bit longer to catch the resulting scroll events
                            setTimeout(() => { 
                                if (!userInteractingWithScrollbar.current) {
                                    isManualScrolling.current = false; 
                                }
                            }, 300);
                        }
                    },
                    onMouseLeave: () => {
                        // If mouse leaves container while dragging scrollbar, still handle it
                        if (userInteractingWithScrollbar.current) {
                            setTimeout(() => { 
                                userInteractingWithScrollbar.current = false;
                                isManualScrolling.current = false; 
                            }, 300);
                        }
                    }
                },
                    React.createElement(Virtuoso, {
                        ref: virtuosoRef,
                        totalCount: filteredLines.length,
                        itemContent: renderLogLine,
                        style: { height: '100%' },
                        followOutput: autoScroll,
                        atBottomThreshold: 200,
                        onAtBottomStateChange: (atBottom) => {
                            // Only handle bottom state changes from manual scrolling, not programmatic
                            if (isManualScrolling.current) {
                                console.log('Manual scroll - at bottom state changed:', atBottom, 'autoScroll:', autoScroll);
                                if (!atBottom && autoScroll) {
                                    console.log('Disabling autoscroll due to manual scroll away from bottom');
                                    setAutoScroll(false);
                                } else if (atBottom && !autoScroll) {
                                    console.log('Re-enabling autoscroll due to manual scroll to bottom');
                                    setAutoScroll(true);
                                }
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