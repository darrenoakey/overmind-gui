/**
 * Tests for ui.js
 * Tests UI manager functionality (basic structure tests)
 */

// Note: ui.js requires DOM elements to be present, so these are basic structural tests
import './ui.js';

// Test UIManager class exists and can be instantiated
function testUIManagerExists() {
    console.log('Testing UIManager exists...');

    if (typeof window.UIManager !== 'function') {
        throw new Error('UIManager should be available on window object');
    }

    // Test basic instantiation (this will fail if DOM elements are missing)
    try {
        const ui = new window.UIManager();

        // Test basic properties exist
        if (!Array.isArray(ui.currentLines)) {
            throw new Error('currentLines should be an array');
        }

        if (typeof ui.maxLines !== 'number') {
            throw new Error('maxLines should be a number');
        }

        if (!(ui.lineIdMap instanceof Map)) {
            throw new Error('lineIdMap should be a Map');
        }

        if (!(ui.selectedProcesses instanceof Set)) {
            throw new Error('selectedProcesses should be a Set');
        }

        if (!(ui.filteredLineIds instanceof Set)) {
            throw new Error('filteredLineIds should be a Set');
        }

        if (!(ui.searchMatchIds instanceof Set)) {
            throw new Error('searchMatchIds should be a Set');
        }

        if (typeof ui.currentSearchIndex !== 'number') {
            throw new Error('currentSearchIndex should be a number');
        }

        if (!Array.isArray(ui.searchMatches)) {
            throw new Error('searchMatches should be an array');
        }

        if (typeof ui.autoScroll !== 'boolean') {
            throw new Error('autoScroll should be a boolean');
        }

        if (typeof ui.isSearchActive !== 'boolean') {
            throw new Error('isSearchActive should be a boolean');
        }

        if (typeof ui.isFilterActive !== 'boolean') {
            throw new Error('isFilterActive should be a boolean');
        }

        if (typeof ui.programmaticScroll !== 'boolean') {
            throw new Error('programmaticScroll should be a boolean');
        }

        console.log('✓ UIManager basic structure test passed');

    } catch (error) {
        if (error.message.includes('getElementById')) {
            console.log('⚠ UIManager DOM test skipped (requires DOM elements)');
        } else {
            throw error;
        }
    }
}

// Test UIManager methods exist
function testUIManagerMethods() {
    console.log('Testing UIManager methods exist...');

    const uiProto = window.UIManager.prototype;

    const expectedMethods = [
        'init',
        'bindElements',
        'bindEvents',
        'enableAutoScroll',
        'shutdownOvermind',
        'applyFilter',
        'performSearch',
        'highlightAllMatches',
        'clearSearch',
        'searchNext',
        'searchPrevious',
        'scrollToSearchMatch',
        'updateSearchResults',
        'updateDisplayedLineCount',
        'selectAllProcesses',
        'deselectAllProcesses',
        'updateProcesses',
        'updateStatus',
        'showErrorModal',
        'hideErrorModal',
        'addOutputLine',
        'addOutputLines',
        'createLineElement',
        'shouldShowLine',
        'updateSearchMatchesForPreRenderedLines',
        'updateSearchMatchesForNewLines',
        'getVisibleLineCount',
        'scrollToBottom',
        'updateAutoScrollButton',
        'updatePollingIndicator',
        'startScrollMonitoring',
        'cleanupDebounceTimers',
        'loadInitialState'
    ];

    for (const methodName of expectedMethods) {
        if (typeof uiProto[methodName] !== 'function') {
            throw new Error(`UIManager should have ${methodName} method`);
        }
    }

    console.log('✓ UIManager methods existence test passed');
}

// Run all tests
function runAllTests() {
    try {
        testUIManagerExists();
        testUIManagerMethods();
        console.log('All UIManager structural tests passed!');
        console.log('Note: Full UI tests require DOM environment');
    } catch (error) {
        console.error('Test failed:', error.message);
        throw error;
    }
}

// Run tests
runAllTests();