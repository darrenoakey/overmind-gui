/**
 * Polling module for Overmind GUI
 * Handles polling server for updates every 1000ms (1x per second)
 */

class PollingManager {
    constructor() {
        this.isPolling = false;
        this.pollInterval = null;
        this.lastMessageId = 0;
        this.pollFrequency = 1000; // Once per second
        this.errorRetryDelay = 2000; // 2 seconds
        this.maxRetries = 5;
        this.retryCount = 0;
        
        // Event handlers - NEW PROTOCOL
        this.onPollingResponse = null;  // NEW: handles complete polling response
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
        
        console.log('Starting polling from beginning (lastMessageId=0)');
        this.isPolling = true;
        this.retryCount = 0;
        
        // Always start polling from 0 to get full buffer
        this.lastMessageId = 0;
        
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
            const url = this.lastMessageId 
                ? `/api/poll?last_message_id=${this.lastMessageId}`
                : '/api/poll?last_message_id=0';
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Update message ID for next poll - use next_poll_message_id if provided
            this.lastMessageId = data.next_poll_message_id || data.latest_message_id;
            
            // Update stats
            this.stats = data.stats || {};
            
            // NEW PROTOCOL: Send complete response to handler
            if (this.onPollingResponse) {
                this.onPollingResponse(data);
            }
            
            // Handle status changes separately for connection indicator
            if (data.status_updates && Object.keys(data.status_updates).length > 0) {
                this.handleConsolidatedStatusUpdates([{
                    type: 'status_bulk',
                    data: { updates: data.status_updates }
                }]);
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
        // Consolidate all updates into a single batch for one DOM update
        const consolidatedUpdates = this.consolidateUpdates(updates);
        
        // Single notification with consolidated updates
        if (this.onUpdate && consolidatedUpdates.length > 0) {
            this.onUpdate(consolidatedUpdates);
        }
        
        // Handle status updates separately for onStatusChange callback
        this.handleConsolidatedStatusUpdates(updates);
    }
    
    /**
     * Consolidate updates to minimize DOM operations
     */
    consolidateUpdates(updates) {
        const outputLines = [];
        const latestStatuses = new Map(); // Process -> latest status
        const otherUpdates = [];
        
        // First pass: collect all outputs and find latest status for each process
        for (const update of updates) {
            switch (update.type) {
                case 'output':
                    outputLines.push(update);
                    break;
                case 'status':
                    // Keep only the latest status for each process
                    if (update.data && update.data.process) {
                        latestStatuses.set(update.data.process, update);
                    }
                    break;
                case 'status_bulk':
                    // Handle bulk status updates
                    if (update.data && update.data.updates) {
                        Object.entries(update.data.updates).forEach(([processName, statusInfo]) => {
                            // Create individual status update for latest status tracking
                            const statusUpdate = {
                                ...update,
                                type: 'status',
                                data: {
                                    process: processName,
                                    status: statusInfo.status,
                                    old_status: statusInfo.old_status
                                }
                            };
                            latestStatuses.set(processName, statusUpdate);
                        });
                    }
                    break;
                default:
                    otherUpdates.push(update);
            }
        }
        
        // Build final consolidated update list
        const consolidated = [];
        
        // Add all output updates (order matters for output)
        consolidated.push(...outputLines);
        
        // Add only the latest status for each process
        consolidated.push(...Array.from(latestStatuses.values()));
        
        // Add other updates
        consolidated.push(...otherUpdates);
        
        return consolidated;
    }
    
    /**
     * Handle consolidated status updates for onStatusChange callback
     */
    handleConsolidatedStatusUpdates(updates) {
        const statusChanges = {};
        
        // Collect all status changes, keeping only the latest for each process
        for (const update of updates) {
            if (update.type === 'status' && update.data && update.data.process) {
                statusChanges[update.data.process] = {
                    status: update.data.status,
                    old_status: update.data.old_status
                };
            } else if (update.type === 'status_bulk' && update.data && update.data.updates) {
                Object.entries(update.data.updates).forEach(([processName, statusInfo]) => {
                    statusChanges[processName] = statusInfo;
                });
            }
        }
        
        // Notify with consolidated status changes
        if (Object.keys(statusChanges).length > 0 && this.onStatusChange) {
            this.onStatusChange(statusChanges);
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
     * Handle batched output updates (LEGACY - not used with new protocol)
     */
    async handleBatchedOutputUpdates(outputUpdates) {
        console.warn('handleBatchedOutputUpdates called - this should not happen with new protocol');
        // This method is no longer used with the new optimized protocol
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
            this.lastMessageId = data.latest_message_id;
            
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

// ES Module export
export default PollingManager;
