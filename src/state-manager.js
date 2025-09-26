/**
 * State Manager with requestAnimationFrame Batching
 * Layer 2: Manages application state and batches updates efficiently
 */

class StateManager {
    constructor() {
        // Core state
        this.state = {
            lines: [],
            processes: {},
            stats: {},
            totalLines: 0,
            isConnected: false,
            autoScroll: true,
            searchTerm: '',
            filterText: '',
            isSearchActive: false,
            isFilterActive: false
        };
        
        // Batching system
        this.pendingUpdates = {
            newLines: [],
            statusUpdates: {},
            stateChanges: {},
            hasUpdates: false
        };
        
        // Frame scheduling
        this.rafId = null;
        this.isScheduled = false;
        
        // Subscribers
        this.subscribers = new Set();
        
        // Line limit
        this.maxLines = 5000;
        
        // Start the RAF loop
        this.scheduleUpdate();
    }
    
    /**
     * Subscribe to state changes
     */
    subscribe(callback) {
        this.subscribers.add(callback);
        return () => this.subscribers.delete(callback);
    }
    
    /**
     * Schedule an update for the next frame
     */
    scheduleUpdate() {
        if (this.isScheduled) return;
        
        this.isScheduled = true;
        this.rafId = requestAnimationFrame(() => {
            this.processPendingUpdates();
            this.isScheduled = false;
            
            // Keep the RAF loop running
            this.scheduleUpdate();
        });
    }
    
    /**
     * Process all pending updates in a single batch
     */
    processPendingUpdates() {
        if (!this.pendingUpdates.hasUpdates) return;
        
        const startTime = performance.now();
        let stateChanged = false;
        
        // Process new lines
        if (this.pendingUpdates.newLines.length > 0) {
            this.state.lines.push(...this.pendingUpdates.newLines);
            
            // Maintain line limit
            if (this.state.lines.length > this.maxLines) {
                const excess = this.state.lines.length - this.maxLines;
                this.state.lines.splice(0, excess);
            }
            
            this.pendingUpdates.newLines = [];
            stateChanged = true;
        }
        
        // Process status updates
        if (Object.keys(this.pendingUpdates.statusUpdates).length > 0) {
            Object.assign(this.state.processes, this.pendingUpdates.statusUpdates);
            this.pendingUpdates.statusUpdates = {};
            stateChanged = true;
        }
        
        // Process state changes
        if (Object.keys(this.pendingUpdates.stateChanges).length > 0) {
            Object.assign(this.state, this.pendingUpdates.stateChanges);
            this.pendingUpdates.stateChanges = {};
            stateChanged = true;
        }
        
        // Reset update flag
        this.pendingUpdates.hasUpdates = false;
        
        // Notify subscribers if state changed
        if (stateChanged) {
            const processingTime = performance.now() - startTime;
            if (processingTime > 5) {
                console.warn(`State update took ${processingTime.toFixed(2)}ms`);
            }
            
            this.notifySubscribers();
        }
    }
    
    /**
     * Notify all subscribers of state changes
     */
    notifySubscribers() {
        const frozenState = Object.freeze({ ...this.state });
        this.subscribers.forEach(callback => {
            try {
                callback(frozenState);
            } catch (error) {
                console.error('Error in state subscriber:', error);
            }
        });
    }
    
    /**
     * Add new processed lines to the pending queue
     */
    addLines(processedLines) {
        this.pendingUpdates.newLines.push(...processedLines);
        this.pendingUpdates.hasUpdates = true;
    }
    
    /**
     * Update process statuses
     */
    updateStatuses(statusUpdates) {
        Object.assign(this.pendingUpdates.statusUpdates, statusUpdates);
        this.pendingUpdates.hasUpdates = true;
    }
    
    /**
     * Update general state properties
     */
    updateState(changes) {
        Object.assign(this.pendingUpdates.stateChanges, changes);
        this.pendingUpdates.hasUpdates = true;
    }
    
    /**
     * Get current state (read-only)
     */
    getState() {
        return Object.freeze({ ...this.state });
    }
    
    /**
     * Get filtered lines based on current state
     */
    getFilteredLines() {
        let filteredLines = this.state.lines;
        
        // Apply process filter
        if (Object.keys(this.state.processes).length > 0) {
            filteredLines = filteredLines.filter(line => {
                const process = this.state.processes[line.processName];
                return !process || process.selected !== false;
            });
        }
        
        // Apply text filter
        if (this.state.isFilterActive && this.state.filterText) {
            const filterLower = this.state.filterText.toLowerCase();
            filteredLines = filteredLines.filter(line => 
                line.htmlContent.toLowerCase().includes(filterLower)
            );
        }
        
        return filteredLines;
    }
    
    /**
     * Search within filtered lines
     */
    searchLines(searchTerm) {
        if (!searchTerm) return [];
        
        const filteredLines = this.getFilteredLines();
        const searchLower = searchTerm.toLowerCase();
        
        return filteredLines
            .map((line, index) => ({
                line,
                originalIndex: this.state.lines.indexOf(line),
                filteredIndex: index
            }))
            .filter(item => item.line.htmlContent.toLowerCase().includes(searchLower));
    }
    
    /**
     * Clear all lines
     */
    clearLines() {
        this.state.lines = [];
        this.pendingUpdates.newLines = [];
        this.pendingUpdates.hasUpdates = true;
    }
    
    /**
     * Cleanup resources
     */
    destroy() {
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
        this.subscribers.clear();
        this.pendingUpdates = {
            newLines: [],
            statusUpdates: {},
            stateChanges: {},
            hasUpdates: false
        };
    }
}

// ES Module export
export default StateManager;