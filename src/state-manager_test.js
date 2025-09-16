/**
 * Tests for state-manager.js
 * Tests state management and batching functionality
 */

import StateManager from './state-manager.js';

// Test StateManager constructor
function testStateManagerConstructor() {
    console.log('Testing StateManager constructor...');

    const stateManager = new StateManager();

    // Test initial state structure
    if (!stateManager.state) {
        throw new Error('state should be initialized');
    }

    if (!Array.isArray(stateManager.state.lines)) {
        throw new Error('state.lines should be an array');
    }

    if (typeof stateManager.state.processes !== 'object') {
        throw new Error('state.processes should be an object');
    }

    if (typeof stateManager.state.stats !== 'object') {
        throw new Error('state.stats should be an object');
    }

    if (stateManager.state.totalLines !== 0) {
        throw new Error('totalLines should be 0 initially');
    }

    if (stateManager.state.isConnected !== false) {
        throw new Error('isConnected should be false initially');
    }

    if (stateManager.state.autoScroll !== true) {
        throw new Error('autoScroll should be true initially');
    }

    // Test pending updates structure
    if (!stateManager.pendingUpdates) {
        throw new Error('pendingUpdates should be initialized');
    }

    if (!Array.isArray(stateManager.pendingUpdates.newLines)) {
        throw new Error('pendingUpdates.newLines should be an array');
    }

    if (typeof stateManager.pendingUpdates.statusUpdates !== 'object') {
        throw new Error('pendingUpdates.statusUpdates should be an object');
    }

    if (stateManager.pendingUpdates.hasUpdates !== false) {
        throw new Error('hasUpdates should be false initially');
    }

    console.log('✓ StateManager constructor test passed');
}

// Test getState method
function testGetState() {
    console.log('Testing getState...');

    const stateManager = new StateManager();
    const state = stateManager.getState();

    if (state !== stateManager.state) {
        throw new Error('getState should return the internal state object');
    }

    console.log('✓ getState test passed');
}

// Test setState method
function testSetState() {
    console.log('Testing setState...');

    const stateManager = new StateManager();

    stateManager.setState({
        autoScroll: false,
        searchTerm: 'test',
        totalLines: 100
    });

    if (stateManager.state.autoScroll !== false) {
        throw new Error('autoScroll should be updated to false');
    }

    if (stateManager.state.searchTerm !== 'test') {
        throw new Error('searchTerm should be updated to "test"');
    }

    if (stateManager.state.totalLines !== 100) {
        throw new Error('totalLines should be updated to 100');
    }

    // Test that other properties are preserved
    if (!Array.isArray(stateManager.state.lines)) {
        throw new Error('lines should still be an array');
    }

    console.log('✓ setState test passed');
}

// Test addLines method
function testAddLines() {
    console.log('Testing addLines...');

    const stateManager = new StateManager();

    const testLines = [
        { id: 1, text: 'line 1', process: 'test' },
        { id: 2, text: 'line 2', process: 'test' }
    ];

    stateManager.addLines(testLines);

    // Check that lines were added to pending updates
    if (stateManager.pendingUpdates.newLines.length !== 2) {
        throw new Error(`Expected 2 pending lines, got ${stateManager.pendingUpdates.newLines.length}`);
    }

    if (stateManager.pendingUpdates.hasUpdates !== true) {
        throw new Error('hasUpdates should be true after adding lines');
    }

    console.log('✓ addLines test passed');
}

// Test updateProcesses method
function testUpdateProcesses() {
    console.log('Testing updateProcesses...');

    const stateManager = new StateManager();

    const testProcesses = {
        'process1': { status: 'running', pid: 123 },
        'process2': { status: 'stopped', pid: 456 }
    };

    stateManager.updateProcesses(testProcesses);

    if (stateManager.state.processes !== testProcesses) {
        throw new Error('processes should be updated');
    }

    console.log('✓ updateProcesses test passed');
}

// Test updateStats method
function testUpdateStats() {
    console.log('Testing updateStats...');

    const stateManager = new StateManager();

    const testStats = {
        totalMemory: 1024,
        usedMemory: 512,
        cpuUsage: 45.5
    };

    stateManager.updateStats(testStats);

    if (stateManager.state.stats !== testStats) {
        throw new Error('stats should be updated');
    }

    console.log('✓ updateStats test passed');
}

// Test subscribe and unsubscribe methods
function testSubscribeUnsubscribe() {
    console.log('Testing subscribe/unsubscribe...');

    const stateManager = new StateManager();
    let callbackCalled = false;
    let receivedState = null;

    const callback = (state) => {
        callbackCalled = true;
        receivedState = state;
    };

    // Subscribe
    const unsubscribe = stateManager.subscribe(callback);

    if (typeof unsubscribe !== 'function') {
        throw new Error('subscribe should return an unsubscribe function');
    }

    // Trigger an update
    stateManager.setState({ totalLines: 50 });

    // Note: We can't test the actual callback execution without requestAnimationFrame,
    // but we can test that the subscription was added
    if (stateManager.subscribers.length !== 1) {
        throw new Error('subscriber should be added');
    }

    // Unsubscribe
    unsubscribe();

    if (stateManager.subscribers.length !== 0) {
        throw new Error('subscriber should be removed after unsubscribe');
    }

    console.log('✓ subscribe/unsubscribe test passed');
}

// Test batchUpdates method
function testBatchUpdates() {
    console.log('Testing batchUpdates...');

    const stateManager = new StateManager();

    const callback = () => {
        stateManager.setState({ totalLines: 10 });
        stateManager.addLines([{ id: 1, text: 'test', process: 'test' }]);
    };

    stateManager.batchUpdates(callback);

    // Check that updates were batched
    if (stateManager.pendingUpdates.hasUpdates !== true) {
        throw new Error('Updates should be pending after batchUpdates');
    }

    if (stateManager.state.totalLines !== 10) {
        throw new Error('State should be updated immediately within batch');
    }

    console.log('✓ batchUpdates test passed');
}

// Test clearPendingUpdates method
function testClearPendingUpdates() {
    console.log('Testing clearPendingUpdates...');

    const stateManager = new StateManager();

    // Add some pending updates
    stateManager.addLines([{ id: 1, text: 'test', process: 'test' }]);
    stateManager.pendingUpdates.statusUpdates.test = 'update';
    stateManager.pendingUpdates.stateChanges.test = 'change';

    stateManager.clearPendingUpdates();

    if (stateManager.pendingUpdates.newLines.length !== 0) {
        throw new Error('newLines should be cleared');
    }

    if (Object.keys(stateManager.pendingUpdates.statusUpdates).length !== 0) {
        throw new Error('statusUpdates should be cleared');
    }

    if (Object.keys(stateManager.pendingUpdates.stateChanges).length !== 0) {
        throw new Error('stateChanges should be cleared');
    }

    if (stateManager.pendingUpdates.hasUpdates !== false) {
        throw new Error('hasUpdates should be false after clear');
    }

    console.log('✓ clearPendingUpdates test passed');
}

// Test that subscribers array exists
function testSubscribersArray() {
    console.log('Testing subscribers array...');

    const stateManager = new StateManager();

    if (!Array.isArray(stateManager.subscribers)) {
        throw new Error('subscribers should be an array');
    }

    if (stateManager.subscribers.length !== 0) {
        throw new Error('subscribers should be empty initially');
    }

    console.log('✓ subscribers array test passed');
}

// Run all tests
function runAllTests() {
    try {
        testStateManagerConstructor();
        testGetState();
        testSetState();
        testAddLines();
        testUpdateProcesses();
        testUpdateStats();
        testSubscribeUnsubscribe();
        testBatchUpdates();
        testClearPendingUpdates();
        testSubscribersArray();
        console.log('All StateManager tests passed!');
    } catch (error) {
        console.error('Test failed:', error.message);
        throw error;
    }
}

// Run tests
runAllTests();