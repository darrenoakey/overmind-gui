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
        
        console.log('Starting polling at', this.pollFrequency, 'ms intervals');
        this.isPolling = true;
        this.retryCount = 0;
        
        // Start with immediate poll, then continue with interval
        this.poll();
        
        this.pollInterval = setInterval(() => {
            this.poll();
        }, this.pollFrequency);
    }
    
    /**
     * Stop polling
     */
    stop() {
        console.log('Stopping polling');
        this.isPolling = false;
        
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
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
            
            // Process updates
            if (data.updates && data.updates.length > 0) {
                this.processUpdates(data.updates);
            }
            
            // Mark as connected and reset retry count
            this.setConnectionStatus(true);
            this.retryCount = 0;
            
        } catch (error) {
            console.error('Polling error:', error);
            this.handleError(error);
        }
    }
    
    /**
     * Process updates from server
     */
    processUpdates(updates) {
        for (const update of updates) {
            switch (update.type) {
                case 'output':
                    this.handleOutputUpdate(update);
                    break;
                case 'status':
                    this.handleStatusUpdate(update);
                    break;
                case 'status_bulk':
                    this.handleBulkStatusUpdate(update);
                    break;
                default:
                    console.warn('Unknown update type:', update.type);
            }
        }
        
        // Notify about updates
        if (this.onUpdate) {
            this.onUpdate(updates);
        }
    }
    
    /**
     * Handle output line update
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
            
            setTimeout(() => {
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
