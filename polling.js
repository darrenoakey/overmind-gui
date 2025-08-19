/**
 * Polling module for Overmind GUI
 * Handles polling server for updates every 250ms (4x per second)
 */

class PollingManager {
    constructor() {
        this.isPolling = false;
        this.pollInterval = null;
        this.lastTimestamp = null;
        this.pollFrequency = 250; // 4 times per second
        this.errorRetryDelay = 2000; // 2 seconds
        this.maxRetries = 5;
        this.retryCount = 0;
        
        // Event handlers
        this.onUpdate = null;
        this.onError = null;
        this.onStatusChange = null;
        
        // State
        this.isConnected = false;
        this.stats = {};
    }
    
    /**
     * Start polling for updates
     */
    start() {
        if (this.isPolling) {
            return;
        }
        
        console.log('Starting polling with timeout-based scheduling');
        this.isPolling = true;
        this.retryCount = 0;
        
        // Start with immediate poll
        this.poll();
    }
    
    /**
     * Stop polling
     */
    stop() {
        console.log('Stopping polling');
        this.isPolling = false;
        
        if (this.pollInterval) {
            clearTimeout(this.pollInterval);
            this.pollInterval = null;
        }
        
        this.setConnectionStatus(false);
    }
    
    /**
     * Poll server for updates
     */
    async poll() {
        if (!this.isPolling) {
            return;
        }
        
        const startTime = performance.now();
        
        try {
            const url = this.lastTimestamp 
                ? `/api/poll?since=${this.lastTimestamp}`
                : '/api/poll';
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Update timestamp
            this.lastTimestamp = data.timestamp;
            
            // Update stats
            this.stats = data.stats || {};
            
            // Process updates with batching
            if (data.updates && data.updates.length > 0) {
                await this.processUpdatesBatched(data.updates);
            }
            
            // Mark as connected and reset retry count
            this.setConnectionStatus(true);
            this.retryCount = 0;
            
            // Schedule next poll AFTER processing is complete
            this.scheduleNextPoll(startTime);
            
        } catch (error) {
            console.error('Polling error:', error);
            this.handleError(error);
            return; // Don't schedule next poll on error - handleError will handle retry
        }
    }
    
    /**
     * Schedule next poll after processing is complete
     */
    scheduleNextPoll(startTime) {
        if (!this.isPolling) {
            return;
        }
        
        const processingTime = performance.now() - startTime;
        const delay = Math.max(0, this.pollFrequency + processingTime);
        
        // Use setTimeout to schedule next poll
        this.pollInterval = setTimeout(() => {
            this.poll();
        }, delay);
    }
    
    /**
     * Process updates from server with batching
     */
    async processUpdatesBatched(updates) {
        // Separate updates by type for batched processing
        const outputUpdates = [];
        const statusUpdates = [];
        const otherUpdates = [];
        
        for (const update of updates) {
            switch (update.type) {
                case 'output':
                    outputUpdates.push(update);
                    break;
                case 'status':
                case 'status_bulk':
                    statusUpdates.push(update);
                    break;
                default:
                    console.warn('Unknown update type:', update.type);
                    otherUpdates.push(update);
            }
        }
        
        // Process output updates in batches (most critical for performance)
        if (outputUpdates.length > 0) {
            await this.handleBatchedOutputUpdates(outputUpdates);
        }
        
        // Process status updates
        if (statusUpdates.length > 0) {
            this.handleBatchedStatusUpdates(statusUpdates);
        }
        
        // Process other updates individually
        for (const update of otherUpdates) {
            this.handleGenericUpdate(update);
        }
        
        // Notify about updates (after all processing)
        if (this.onUpdate && updates.length > 0) {
            this.onUpdate(updates);
        }
    }
    
    /**
     * Legacy method for compatibility
     */
    processUpdates(updates) {
        // Use the batched version
        return this.processUpdatesBatched(updates);
    }
    
    /**
     * Handle batched output updates (critical for performance)
     */
    async handleBatchedOutputUpdates(outputUpdates) {
        if (outputUpdates.length === 0) return;
        
        // Yield control to allow DOM updates if we have many lines
        if (outputUpdates.length > 50) {
            console.log(`Processing ${outputUpdates.length} output lines in batches`);
            
            // Process in chunks of 25 to prevent UI blocking
            const CHUNK_SIZE = 25;
            for (let i = 0; i < outputUpdates.length; i += CHUNK_SIZE) {
                const chunk = outputUpdates.slice(i, i + CHUNK_SIZE);
                
                // Process chunk
                if (this.onUpdate) {
                    this.onUpdate(chunk);
                }
                
                // Yield control every chunk to prevent UI blocking
                if (i + CHUNK_SIZE < outputUpdates.length) {
                    await new Promise(resolve => setTimeout(resolve, 0));
                }
            }
        } else {
            // Process all at once for smaller batches
            if (this.onUpdate) {
                this.onUpdate(outputUpdates);
            }
        }
    }
    
    /**
     * Handle batched status updates
     */
    handleBatchedStatusUpdates(statusUpdates) {
        for (const update of statusUpdates) {
            if (update.type === 'status') {
                this.handleStatusUpdate(update);
            } else if (update.type === 'status_bulk') {
                this.handleBulkStatusUpdate(update);
            }
        }
    }
    
    /**
     * Handle generic update
     */
    handleGenericUpdate(update) {
        console.warn('Unhandled update type:', update.type);
    }
    
    /**
     * Handle output line update (legacy - single update)
     */
    handleOutputUpdate(update) {
        const line = update.data;
        
        // Notify about new output line
        if (this.onUpdate) {
            this.onUpdate([{
                type: 'output',
                data: line
            }]);
        }
    }
    
    /**
     * Handle single process status update
     */
    handleStatusUpdate(update) {
        const { process, status, old_status } = update.data;
        
        console.log(`Process ${process}: ${old_status} -> ${status}`);
        
        if (this.onStatusChange) {
            this.onStatusChange({
                [process]: {
                    status,
                    old_status
                }
            });
        }
    }
    
    /**
     * Handle bulk status updates
     */
    handleBulkStatusUpdate(update) {
        const updates = update.data.updates;
        
        console.log('Bulk status update:', updates);
        
        if (this.onStatusChange) {
            this.onStatusChange(updates);
        }
    }
    
    /**
     * Handle polling errors
     */
    handleError(error) {
        this.setConnectionStatus(false);
        this.retryCount++;
        
        if (this.onError) {
            this.onError(error);
        }
        
        // If we're still supposed to be polling, retry after delay
        if (this.isPolling && this.retryCount <= this.maxRetries) {
            console.log(`Retrying in ${this.errorRetryDelay}ms (attempt ${this.retryCount}/${this.maxRetries})`);
            
            this.pollInterval = setTimeout(() => {
                if (this.isPolling) {
                    this.poll();
                }
            }, this.errorRetryDelay);
        } else if (this.retryCount > this.maxRetries) {
            console.error('Max retries exceeded, stopping polling');
            this.stop();
        }
    }
    
    /**
     * Set connection status and notify listeners
     */
    setConnectionStatus(connected) {
        if (this.isConnected !== connected) {
            this.isConnected = connected;
            
            if (this.onStatusChange) {
                this.onStatusChange({
                    connection: {
                        status: connected ? 'connected' : 'disconnected'
                    }
                });
            }
        }
    }
    
    /**
     * Get initial state from server
     */
    async getInitialState() {
        try {
            const response = await fetch('/api/state');
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Update timestamp for future polls
            this.lastTimestamp = data.timestamp;
            
            // Update stats
            this.stats = data.stats || {};
            
            return data;
            
        } catch (error) {
            console.error('Error getting initial state:', error);
            throw error;
        }
    }
    
    /**
     * Perform API request
     */
    async apiRequest(url, options = {}) {
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            return await response.json();
            
        } catch (error) {
            console.error('API request error:', error);
            throw error;
        }
    }
    
    /**
     * Process control methods
     */
    async startProcess(processName) {
        return this.apiRequest(`/api/process/${processName}/start`, {
            method: 'POST'
        });
    }
    
    async stopProcess(processName) {
        return this.apiRequest(`/api/process/${processName}/stop`, {
            method: 'POST'
        });
    }
    
    async restartProcess(processName) {
        return this.apiRequest(`/api/process/${processName}/restart`, {
            method: 'POST'
        });
    }
    
    async toggleProcessSelection(processName) {
        return this.apiRequest(`/api/process/${processName}/toggle`, {
            method: 'POST'
        });
    }
    
    async selectAllProcesses() {
        return this.apiRequest('/api/processes/select-all', {
            method: 'POST'
        });
    }
    
    async deselectAllProcesses() {
        return this.apiRequest('/api/processes/deselect-all', {
            method: 'POST'
        });
    }
    
    async clearOutput() {
        return this.apiRequest('/api/output/clear', {
            method: 'POST'
        });
    }
    
    // Search functionality removed - frontend handles filtering now
    
    /**
     * Get current stats
     */
    getStats() {
        return this.stats;
    }
    
    /**
     * Check if currently connected
     */
    getConnectionStatus() {
        return this.isConnected;
    }
}

// Export for use in other modules
window.PollingManager = PollingManager;
