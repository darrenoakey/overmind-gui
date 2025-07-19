// WebSocket connection and message handling

class WebSocketManager {
    constructor() {
        this.ws = null;
        this.connected = false;
        this.messageHandlers = new Map();
        this.reconnectDelay = 3000;
        this.maxReconnectAttempts = 10;
        this.reconnectAttempts = 0;
    }

    // Register a message handler for a specific message type
    registerHandler(messageType, handler) {
        if (!this.messageHandlers.has(messageType)) {
            this.messageHandlers.set(messageType, []);
        }
        this.messageHandlers.get(messageType).push(handler);
    }

    // Remove a message handler
    unregisterHandler(messageType, handler) {
        if (this.messageHandlers.has(messageType)) {
            const handlers = this.messageHandlers.get(messageType);
            const index = handlers.indexOf(handler);
            if (index > -1) {
                handlers.splice(index, 1);
            }
        }
    }

    // Connect to WebSocket
    connect(onConnectionChange = null) {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        console.log(`Connecting to WebSocket: ${wsUrl}`);
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.connected = true;
            this.reconnectAttempts = 0;
            if (onConnectionChange) {
                onConnectionChange(true);
            }
        };
        
        this.ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                this.handleMessage(message);
            } catch (error) {
                console.error('Error parsing WebSocket message:', error);
            }
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.connected = false;
            if (onConnectionChange) {
                onConnectionChange(false);
            }
            this.attemptReconnect(onConnectionChange);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    // Attempt to reconnect with exponential backoff
    attemptReconnect(onConnectionChange) {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = Math.min(this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1), 30000);
            console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
            
            setTimeout(() => {
                this.connect(onConnectionChange);
            }, delay);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }

    // Handle incoming messages
    handleMessage(message) {
        const { type, data } = message;
        
        if (this.messageHandlers.has(type)) {
            const handlers = this.messageHandlers.get(type);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    console.error(`Error in message handler for ${type}:`, error);
                }
            });
        } else {
            console.warn(`No handler registered for message type: ${type}`);
        }
    }

    // Send a message
    sendMessage(type, data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = JSON.stringify({ type, data });
            this.ws.send(message);
            return true;
        } else {
            console.warn('WebSocket not connected, cannot send message');
            return false;
        }
    }

    // Close the connection
    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
    }

    // Get connection status
    isConnected() {
        return this.connected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

// Export for use in other files
window.WebSocketManager = WebSocketManager;
