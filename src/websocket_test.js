/**
 * Tests for websocket.js
 * Tests WebSocket manager functionality
 */

import WebSocketManager from './websocket.js';

// Test WebSocketManager constructor
function testWebSocketManagerConstructor() {
    console.log('Testing WebSocketManager constructor...');

    const wsManager = new WebSocketManager();

    if (wsManager.ws !== null) {
        throw new Error('ws should be null initially');
    }

    if (wsManager.isConnected !== false) {
        throw new Error('isConnected should be false initially');
    }

    if (wsManager.reconnectAttempts !== 0) {
        throw new Error('reconnectAttempts should be 0 initially');
    }

    if (wsManager.maxReconnectAttempts !== 5) {
        throw new Error('maxReconnectAttempts should be 5');
    }

    if (wsManager.reconnectDelay !== 1000) {
        throw new Error('reconnectDelay should be 1000ms');
    }

    if (wsManager.reconnectTimer !== null) {
        throw new Error('reconnectTimer should be null initially');
    }

    // Test event handlers are null initially
    if (wsManager.onMessage !== null) {
        throw new Error('onMessage should be null initially');
    }

    if (wsManager.onConnect !== null) {
        throw new Error('onConnect should be null initially');
    }

    if (wsManager.onDisconnect !== null) {
        throw new Error('onDisconnect should be null initially');
    }

    if (wsManager.onError !== null) {
        throw new Error('onError should be null initially');
    }

    console.log('✓ WebSocketManager constructor test passed');
}

// Test setEventHandlers method
function testSetEventHandlers() {
    console.log('Testing setEventHandlers...');

    const wsManager = new WebSocketManager();

    const mockHandlers = {
        onMessage: () => {},
        onConnect: () => {},
        onDisconnect: () => {},
        onError: () => {}
    };

    wsManager.setEventHandlers(mockHandlers);

    if (wsManager.onMessage !== mockHandlers.onMessage) {
        throw new Error('onMessage should be set');
    }

    if (wsManager.onConnect !== mockHandlers.onConnect) {
        throw new Error('onConnect should be set');
    }

    if (wsManager.onDisconnect !== mockHandlers.onDisconnect) {
        throw new Error('onDisconnect should be set');
    }

    if (wsManager.onError !== mockHandlers.onError) {
        throw new Error('onError should be set');
    }

    console.log('✓ setEventHandlers test passed');
}

// Test getConnectionState method
function testGetConnectionState() {
    console.log('Testing getConnectionState...');

    const wsManager = new WebSocketManager();

    const state = wsManager.getConnectionState();

    if (typeof state.isConnected !== 'boolean') {
        throw new Error('state.isConnected should be boolean');
    }

    if (typeof state.reconnectAttempts !== 'number') {
        throw new Error('state.reconnectAttempts should be number');
    }

    if (typeof state.maxReconnectAttempts !== 'number') {
        throw new Error('state.maxReconnectAttempts should be number');
    }

    if (state.isConnected !== wsManager.isConnected) {
        throw new Error('state.isConnected should match internal state');
    }

    if (state.reconnectAttempts !== wsManager.reconnectAttempts) {
        throw new Error('state.reconnectAttempts should match internal state');
    }

    console.log('✓ getConnectionState test passed');
}

// Test disconnect method
function testDisconnect() {
    console.log('Testing disconnect...');

    const wsManager = new WebSocketManager();

    // Set up some state as if connected
    wsManager.isConnected = true;
    wsManager.reconnectTimer = 123; // Mock timer ID

    wsManager.disconnect();

    if (wsManager.isConnected !== false) {
        throw new Error('isConnected should be false after disconnect');
    }

    if (wsManager.reconnectTimer !== null) {
        throw new Error('reconnectTimer should be null after disconnect');
    }

    console.log('✓ disconnect test passed');
}

// Test send method with no connection
function testSendWithoutConnection() {
    console.log('Testing send without connection...');

    const wsManager = new WebSocketManager();

    const result = wsManager.send({ type: 'test', data: 'hello' });

    if (result !== false) {
        throw new Error('send should return false when not connected');
    }

    console.log('✓ send without connection test passed');
}

// Test buildWebSocketUrl method
function testBuildWebSocketUrl() {
    console.log('Testing buildWebSocketUrl...');

    const wsManager = new WebSocketManager();

    // Mock window.location
    const originalLocation = window.location;
    delete window.location;
    window.location = {
        protocol: 'http:',
        host: 'localhost:8000'
    };

    const url = wsManager.buildWebSocketUrl();

    if (!url.startsWith('ws://')) {
        throw new Error('URL should start with ws:// for http protocol');
    }

    if (!url.includes('localhost:8000')) {
        throw new Error('URL should include host');
    }

    // Test with https
    window.location.protocol = 'https:';
    const secureUrl = wsManager.buildWebSocketUrl();

    if (!secureUrl.startsWith('wss://')) {
        throw new Error('URL should start with wss:// for https protocol');
    }

    // Restore original location
    window.location = originalLocation;

    console.log('✓ buildWebSocketUrl test passed');
}

// Run all tests
function runAllTests() {
    try {
        testWebSocketManagerConstructor();
        testSetEventHandlers();
        testGetConnectionState();
        testDisconnect();
        testSendWithoutConnection();
        testBuildWebSocketUrl();
        console.log('All WebSocketManager tests passed!');
        console.log('Note: Full WebSocket tests require actual WebSocket server');
    } catch (error) {
        console.error('Test failed:', error.message);
        throw error;
    }
}

// Run tests
runAllTests();