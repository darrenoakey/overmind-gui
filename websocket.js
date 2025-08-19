// Persistent WebSocket Connection for Single-Worker Architecture
// This connection is designed to stay open throughout the application lifecycle

class WebSocketConnection {
    constructor() {
        // Connection state
        this.ws = null;
        this.url = null;
        this.connected = false;
        this.connectionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectDelay = 30000; // Max 30 seconds
        
        // Message handlers - actor pattern
        this.messageHandlers = new Map();
        this.eventHandlers = new Map();
        
        // Message queue for when connection is not ready
        this.messageQueue = [];
        this.maxQueueSize = 100;
        
        // Heartbeat
        this.heartbeatTimer = null;
        this.heartbeatInterval = 25000; // 25 seconds (match server)
        this.lastActivity = Date.now();
        this.lastPong = Date.now();
        
        // Connection monitoring
        this.monitorTimer = null;
        this.monitorInterval = 5000; // Check every 5 seconds
        
        // Prevent rapid reconnection
        this.lastConnectionAttempt = 0;
        this.minTimeBetweenAttempts = 1000; // At least 1 second between attempts
        
        // Track if we've ever connected successfully
        this.hasConnectedBefore = false;
        
        // Start connection immediately
        this.establishConnection();
        this.startConnectionMonitor();
    }
    
    // Establish WebSocket connection
    establishConnection() {
        // Prevent rapid reconnection attempts
        const now = Date.now();
        const timeSinceLastAttempt = now - this.lastConnectionAttempt;
        if (timeSinceLastAttempt < this.minTimeBetweenAttempts) {
            const delay = this.minTimeBetweenAttempts - timeSinceLastAttempt;
            console.log(`[WS] Delaying connection attempt by ${delay}ms to prevent rapid reconnection`);
            setTimeout(() => this.establishConnection(), delay);
            return;
        }
        
        this.lastConnectionAttempt = now;
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        this.url = `${protocol}//${window.location.host}/ws`;
        
        console.log(`[WS] Establishing persistent connection to ${this.url} (attempt ${this.reconnectAttempts + 1})`);
        
        try {
            // Clean up old connection if exists
            if (this.ws) {
                this.ws.onopen = null;
                this.ws.onmessage = null;
                this.ws.onclose = null;
                this.ws.onerror = null;
                if (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING) {
                    this.ws.close();
                }
                this.ws = null;
            }
            
            this.ws = new WebSocket(this.url);
            this.setupEventHandlers();
        } catch (error) {
            console.error('[WS] Failed to create WebSocket:', error);
            // Retry with exponential backoff
            const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.maxReconnectDelay);
            setTimeout(() => this.establishConnection(), delay);
        }
    }
    
    // Setup WebSocket event handlers
    setupEventHandlers() {
        if (!this.ws) return;
        
        this.ws.onopen = () => {
            console.log('[WS] ✅ Connection established - persistent connection active');
            this.connected = true;
            this.hasConnectedBefore = true;
            this.lastActivity = Date.now();
            this.lastPong = Date.now();
            this.reconnectAttempts = 0; // Reset on successful connection
            
            // Start heartbeat
            this.startHeartbeat();
            
            // Emit connection event
            this.emit('connected', true);
            
            // Process queued messages
            this.processMessageQueue();
            
            // Request initial state after connection is stable
            setTimeout(() => {
                if (this.connected && this.ws && this.ws.readyState === WebSocket.OPEN) {
                    console.log('[WS] Requesting initial state');
                    this.send('get_initial_state', {});
                }
            }, 200);
        };
        
        this.ws.onmessage = (event) => {
            this.lastActivity = Date.now();
            try {
                const message = JSON.parse(event.data);
                
                // Handle connection acknowledgment
                if (message.type === 'connected' && message.data && message.data.connection_id) {
                    this.connectionId = message.data.connection_id;
                    console.log(`[WS] Connection acknowledged with ID: ${this.connectionId}`);
                }
                
                // Update lastPong for pong messages
                if (message.type === 'pong') {
                    this.lastPong = Date.now();
                }
                
                this.handleMessage(message);
            } catch (error) {
                console.error('[WS] Failed to parse message:', error, 'Raw data:', event.data);
                // Don't close - just ignore bad messages
            }
        };
        
        this.ws.onclose = (event) => {
            // In single-worker mode, this should rarely happen
            if (this.hasConnectedBefore) {
                console.error(`[WS] ⚠️ CONNECTION CLOSED - Unexpected in single-worker mode!`);
                console.error(`[WS] Close code: ${event.code}, Reason: ${event.reason || 'No reason provided'}`);
                console.error(`[WS] This indicates the server may have restarted or crashed`);
            } else {
                console.warn(`[WS] Initial connection failed - server may not be ready`);
            }
            
            this.connected = false;
            this.connectionId = null;
            this.stopHeartbeat();
            
            // Emit disconnection event
            this.emit('disconnected', false);
            
            // Calculate reconnect delay with exponential backoff
            this.reconnectAttempts++;
            const baseDelay = Math.min(1000 * Math.pow(2, Math.min(this.reconnectAttempts - 1, 6)), this.maxReconnectDelay);
            const jitter = Math.random() * 1000; // Add up to 1 second of jitter
            const delay = baseDelay + jitter;
            
            console.log(`[WS] Will attempt reconnection in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts})`);
            
            // Clear the current connection
            this.ws = null;
            
            // Reconnect with delay
            setTimeout(() => this.establishConnection(), delay);
        };
        
        this.ws.onerror = (error) => {
            console.error('[WS] Connection error:', error);
            // Don't close on error - let onclose handle reconnection
        };
    }
    
    // Process queued messages
    processMessageQueue() {
        if (this.messageQueue.length > 0) {
            console.log(`[WS] Processing ${this.messageQueue.length} queued messages`);
            const queue = [...this.messageQueue];
            this.messageQueue = [];
            
            queue.forEach(({ type, data }) => {
                this.send(type, data);
            });
        }
    }
    
    // Handle incoming messages - Actor pattern
    handleMessage(message) {
        const { type, data } = message;
        
        // Handle system messages
        if (type === 'ping') {
            this.send('pong', { timestamp: Date.now() });
            return;
        } else if (type === 'pong') {
            // Connection is alive, already handled above
            return;
        }
        
        // Emit message to handlers
        if (this.messageHandlers.has(type)) {
            const handlers = this.messageHandlers.get(type);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`[WS] Error in handler for ${type}:`, error);
                    // Never close on handler error
                }
            });
        }
        
        // Also emit as generic message event
        this.emit('message', { type, data });
    }
    
    // Send message - Actor pattern with queuing
    send(type, data) {
        // Check if we can send immediately
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
                const message = JSON.stringify({ type, data: data || {} });
                this.ws.send(message);
                this.lastActivity = Date.now();
                return true;
            } catch (error) {
                console.error('[WS] Send failed:', error);
                // Queue the message for retry
                this.queueMessage(type, data);
                return false;
            }
        } else {
            // Queue message if not connected
            this.queueMessage(type, data);
            
            // Ensure we're trying to connect
            if (!this.ws || (this.ws.readyState !== WebSocket.CONNECTING && this.ws.readyState !== WebSocket.OPEN)) {
                console.log('[WS] Not connected, initiating connection...');
                this.establishConnection();
            }
            
            return false;
        }
    }
    
    // Queue a message for later sending
    queueMessage(type, data) {
        // Don't queue certain message types
        if (type === 'ping' || type === 'pong') {
            return;
        }
        
        // Limit queue size to prevent memory issues
        if (this.messageQueue.length >= this.maxQueueSize) {
            console.warn('[WS] Message queue full, dropping oldest message');
            this.messageQueue.shift();
        }
        
        this.messageQueue.push({ type, data });
        console.log(`[WS] Message queued: ${type} (queue size: ${this.messageQueue.length})`);
    }
    
    // Register message handler
    on(messageType, handler) {
        if (!this.messageHandlers.has(messageType)) {
            this.messageHandlers.set(messageType, []);
        }
        this.messageHandlers.get(messageType).push(handler);
    }
    
    // Unregister message handler
    off(messageType, handler) {
        if (this.messageHandlers.has(messageType)) {
            const handlers = this.messageHandlers.get(messageType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }
    
    // Event emitter for connection events
    emit(event, data) {
        if (this.eventHandlers.has(event)) {
            const handlers = this.eventHandlers.get(event);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`[WS] Error in event handler for ${event}:`, error);
                }
            });
        }
    }
    
    // Register event handler
    onEvent(event, handler) {
        if (!this.eventHandlers.has(event)) {
            this.eventHandlers.set(event, []);
        }
        this.eventHandlers.get(event).push(handler);
    }
    
    // Start heartbeat
    startHeartbeat() {
        this.stopHeartbeat();
        
        this.heartbeatTimer = setInterval(() => {
            if (this.connected && this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.send('ping', { timestamp: Date.now() });
                
                // Check if we've received a pong recently
                const timeSincePong = Date.now() - this.lastPong;
                if (timeSincePong > 60000) {
                    console.warn(`[WS] No pong received for ${Math.round(timeSincePong / 1000)}s, connection may be stale`);
                }
            }
        }, this.heartbeatInterval);
    }
    
    // Stop heartbeat
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }
    
    // Connection monitor - ensures connection stays alive
    startConnectionMonitor() {
        this.monitorTimer = setInterval(() => {
            const now = Date.now();
            const timeSinceActivity = now - this.lastActivity;
            const timeSincePong = now - this.lastPong;
            
            // Log connection status periodically
            if (this.connected) {
                console.log(`[WS] Monitor: Connected (ID: ${this.connectionId}, Activity: ${Math.round(timeSinceActivity / 1000)}s ago, Last pong: ${Math.round(timeSincePong / 1000)}s ago)`);
            } else {
                console.log(`[WS] Monitor: Not connected (Attempts: ${this.reconnectAttempts})`);
            }
            
            // If no pong for 90 seconds and connected, force reconnect
            if (this.connected && timeSincePong > 90000) {
                console.error('[WS] No pong for 90s, connection is dead, forcing reconnection');
                if (this.ws) {
                    this.ws.close();
                }
            }
            
            // Always ensure we're trying to connect if not connected
            if (!this.connected && !this.ws) {
                console.log('[WS] Monitor: Initiating connection attempt');
                this.establishConnection();
            }
        }, this.monitorInterval);
    }
    
    // Check if connected
    isConnected() {
        return this.connected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }
    
    // Get connection info
    getConnectionInfo() {
        return {
            connected: this.connected,
            connectionId: this.connectionId,
            reconnectAttempts: this.reconnectAttempts,
            queuedMessages: this.messageQueue.length,
            lastActivity: new Date(this.lastActivity).toLocaleTimeString(),
            lastPong: new Date(this.lastPong).toLocaleTimeString()
        };
    }
}

// Global singleton instance - there should only ever be ONE connection
window.wsConnection = new WebSocketConnection();

// Backward compatibility wrapper
class WebSocketManager {
    constructor() {
        // Use the global singleton
        this.connection = window.wsConnection;
    }
    
    registerHandler(messageType, handler) {
        this.connection.on(messageType, handler);
    }
    
    unregisterHandler(messageType, handler) {
        this.connection.off(messageType, handler);
    }
    
    connect(onConnectionChange = null) {
        if (onConnectionChange) {
            this.connection.onEvent('connected', () => onConnectionChange(true));
            this.connection.onEvent('disconnected', () => onConnectionChange(false));
        }
        // Connection is always trying to be established
    }
    
    sendMessage(type, data) {
        return this.connection.send(type, data);
    }
    
    isConnected() {
        return this.connection.isConnected();
    }
    
    getConnectionInfo() {
        return this.connection.getConnectionInfo();
    }
    
    // These methods do nothing - we never intentionally disconnect
    disconnect() {
        console.warn('[WS] disconnect() called but ignored - connection is persistent');
    }
}

window.WebSocketManager = WebSocketManager;

// Log connection info periodically in development
if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    setInterval(() => {
        const info = window.wsConnection.getConnectionInfo();
        console.log('[WS] Status:', info);
    }, 30000); // Every 30 seconds
}
