/**
 * Tests for polling.js
 * Tests polling manager functionality
 */

import PollingManager from './polling.js';

// Test PollingManager constructor
function testPollingManagerConstructor() {
    console.log('Testing PollingManager constructor...');

    const pollingManager = new PollingManager();

    if (pollingManager.isPolling !== false) {
        throw new Error('isPolling should be false initially');
    }

    if (pollingManager.pollInterval !== null) {
        throw new Error('pollInterval should be null initially');
    }

    if (pollingManager.lastMessageId !== 0) {
        throw new Error('lastMessageId should be 0 initially');
    }

    if (pollingManager.pollFrequency !== 1000) {
        throw new Error('pollFrequency should be 1000ms');
    }

    if (pollingManager.maxPollFrequency !== 5000) {
        throw new Error('maxPollFrequency should be 5000ms');
    }

    if (pollingManager.minPollFrequency !== 500) {
        throw new Error('minPollFrequency should be 500ms');
    }

    if (pollingManager.adaptivePollingThreshold !== 500) {
        throw new Error('adaptivePollingThreshold should be 500ms');
    }

    if (pollingManager.errorRetryDelay !== 2000) {
        throw new Error('errorRetryDelay should be 2000ms');
    }

    if (pollingManager.maxRetries !== 5) {
        throw new Error('maxRetries should be 5');
    }

    if (pollingManager.retryCount !== 0) {
        throw new Error('retryCount should be 0 initially');
    }

    if (pollingManager.lastProcessingTime !== 0) {
        throw new Error('lastProcessingTime should be 0 initially');
    }

    if (pollingManager.isConnected !== false) {
        throw new Error('isConnected should be false initially');
    }

    if (typeof pollingManager.stats !== 'object') {
        throw new Error('stats should be an object');
    }

    // Test event handlers are null initially
    if (pollingManager.onPollingResponse !== null) {
        throw new Error('onPollingResponse should be null initially');
    }

    if (pollingManager.onError !== null) {
        throw new Error('onError should be null initially');
    }

    if (pollingManager.onStatusChange !== null) {
        throw new Error('onStatusChange should be null initially');
    }

    console.log('✓ PollingManager constructor test passed');
}

// Test setEventHandlers method
function testSetEventHandlers() {
    console.log('Testing setEventHandlers...');

    const pollingManager = new PollingManager();

    const mockHandlers = {
        onPollingResponse: () => {},
        onError: () => {},
        onStatusChange: () => {}
    };

    pollingManager.setEventHandlers(mockHandlers);

    if (pollingManager.onPollingResponse !== mockHandlers.onPollingResponse) {
        throw new Error('onPollingResponse should be set');
    }

    if (pollingManager.onError !== mockHandlers.onError) {
        throw new Error('onError should be set');
    }

    if (pollingManager.onStatusChange !== mockHandlers.onStatusChange) {
        throw new Error('onStatusChange should be set');
    }

    console.log('✓ setEventHandlers test passed');
}

// Test stop method
function testStop() {
    console.log('Testing stop...');

    const pollingManager = new PollingManager();

    // Set up some state as if polling was running
    pollingManager.isPolling = true;
    pollingManager.pollInterval = 123; // Mock interval ID
    pollingManager.retryCount = 3;

    pollingManager.stop();

    if (pollingManager.isPolling !== false) {
        throw new Error('isPolling should be false after stop');
    }

    if (pollingManager.pollInterval !== null) {
        throw new Error('pollInterval should be null after stop');
    }

    if (pollingManager.retryCount !== 0) {
        throw new Error('retryCount should be reset to 0 after stop');
    }

    console.log('✓ stop test passed');
}

// Test isActive method
function testIsActive() {
    console.log('Testing isActive...');

    const pollingManager = new PollingManager();

    if (pollingManager.isActive() !== false) {
        throw new Error('isActive should return false initially');
    }

    pollingManager.isPolling = true;

    if (pollingManager.isActive() !== true) {
        throw new Error('isActive should return true when polling');
    }

    console.log('✓ isActive test passed');
}

// Test getStats method
function testGetStats() {
    console.log('Testing getStats...');

    const pollingManager = new PollingManager();

    const stats = pollingManager.getStats();

    if (stats !== pollingManager.stats) {
        throw new Error('getStats should return the internal stats object');
    }

    // Test with some mock stats
    pollingManager.stats = { requests: 10, errors: 1 };
    const updatedStats = pollingManager.getStats();

    if (updatedStats.requests !== 10) {
        throw new Error('stats.requests should be 10');
    }

    if (updatedStats.errors !== 1) {
        throw new Error('stats.errors should be 1');
    }

    console.log('✓ getStats test passed');
}

// Test getConnectionStatus method
function testGetConnectionStatus() {
    console.log('Testing getConnectionStatus...');

    const pollingManager = new PollingManager();

    if (pollingManager.getConnectionStatus() !== false) {
        throw new Error('getConnectionStatus should return false initially');
    }

    pollingManager.isConnected = true;

    if (pollingManager.getConnectionStatus() !== true) {
        throw new Error('getConnectionStatus should return true when connected');
    }

    console.log('✓ getConnectionStatus test passed');
}

// Test updateLastMessageId method
function testUpdateLastMessageId() {
    console.log('Testing updateLastMessageId...');

    const pollingManager = new PollingManager();

    pollingManager.updateLastMessageId(100);

    if (pollingManager.lastMessageId !== 100) {
        throw new Error('lastMessageId should be updated to 100');
    }

    // Test that it only updates if the new ID is higher
    pollingManager.updateLastMessageId(50);

    if (pollingManager.lastMessageId !== 100) {
        throw new Error('lastMessageId should not decrease');
    }

    pollingManager.updateLastMessageId(150);

    if (pollingManager.lastMessageId !== 150) {
        throw new Error('lastMessageId should be updated to 150');
    }

    console.log('✓ updateLastMessageId test passed');
}

// Test calculateAdaptiveDelay method
function testCalculateAdaptiveDelay() {
    console.log('Testing calculateAdaptiveDelay...');

    const pollingManager = new PollingManager();

    // Test normal processing time (under threshold)
    pollingManager.lastProcessingTime = 200;
    let delay = pollingManager.calculateAdaptiveDelay();

    if (delay !== pollingManager.pollFrequency) {
        throw new Error(`Expected normal delay ${pollingManager.pollFrequency}, got ${delay}`);
    }

    // Test slow processing time (over threshold)
    pollingManager.lastProcessingTime = 800;
    delay = pollingManager.calculateAdaptiveDelay();

    if (delay <= pollingManager.pollFrequency) {
        throw new Error('Delay should be increased for slow processing');
    }

    if (delay > pollingManager.maxPollFrequency) {
        throw new Error('Delay should not exceed maxPollFrequency');
    }

    console.log('✓ calculateAdaptiveDelay test passed');
}

// Run all tests
function runAllTests() {
    try {
        testPollingManagerConstructor();
        testSetEventHandlers();
        testStop();
        testIsActive();
        testGetStats();
        testGetConnectionStatus();
        testUpdateLastMessageId();
        testCalculateAdaptiveDelay();
        console.log('All PollingManager tests passed!');
    } catch (error) {
        console.error('Test failed:', error.message);
        throw error;
    }
}

// Run tests
runAllTests();